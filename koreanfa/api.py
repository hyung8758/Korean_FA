"""File and directory forced-alignment APIs."""

import os
import shutil
import subprocess
import sys
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Callable

from .audio import normalize_wav
from .engine import installed_engine
from .errors import AlignmentError, EngineNotFoundError, PairingError
from .language import detect_language, normalize_language
from .pairing import discover_corpus_files
from .resources import runtime_root
from .result import AlignmentFailure, AlignmentResult, BatchAlignmentResult, InputPair


_LIBRARY_PATH_VARIABLES = frozenset({"LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"})
DEFAULT_NUM_JOBS = 4
ProgressCallback = Callable[[str, int, int, str], None]


def discover_pairs(
    directory: str | Path, *, recursive: bool = False, ignore_unmatched: bool = True, lang: str = "auto"
) -> tuple[InputPair, ...]:
    """Find matching WAV/TXT pairs and resolve the model language for each.

    Orphaned WAV/TXT files are skipped with a warning by default. Set
    ``ignore_unmatched=False`` to reject a corpus containing an orphan.
    """
    pairs, _ = _collect_pairs(directory, recursive=recursive, ignore_unmatched=ignore_unmatched, lang=lang)
    return pairs


def _collect_pairs(
    directory: str | Path, *, recursive: bool, ignore_unmatched: bool, lang: str,
    collect_language_failures: bool = False,
) -> tuple[tuple[InputPair, ...], tuple[AlignmentFailure, ...]]:
    """Discover pairs, optionally retaining auto-detection rejections per file."""
    root = Path(directory).expanduser().resolve()
    requested_lang = normalize_language(lang)
    discovery = discover_corpus_files(root, recursive=recursive)
    missing_audio = list(discovery.missing_audio)
    missing_text = list(discovery.missing_text)
    if not ignore_unmatched and (missing_audio or missing_text):
        raise PairingError("Unmatched corpus files. " + _unmatched_details(missing_text, missing_audio))
    if ignore_unmatched and (missing_audio or missing_text):
        warnings.warn(
            "Ignoring unmatched corpus files. " + _unmatched_details(missing_text, missing_audio),
            UserWarning,
            stacklevel=2,
        )
    pairs: list[InputPair] = []
    failures: list[AlignmentFailure] = []
    for discovered in discovery.pairs:
        try:
            language = _resolve_language(discovered.transcript, requested_lang)
        except PairingError as error:
            if not collect_language_failures:
                raise
            failures.append(AlignmentFailure(discovered.audio, discovered.transcript, "auto", str(error)))
            continue
        pairs.append(
            InputPair(
                audio=discovered.audio,
                transcript=discovered.transcript,
                relative_stem=discovered.relative_stem,
                language=language,
            )
        )
    return tuple(pairs), tuple(failures)


def _unmatched_details(missing_text: list[Path], missing_audio: list[Path]) -> str:
    """Format unmatched relative stems consistently for errors and warnings."""
    details = []
    if missing_text:
        details.append("WAV without TXT: " + ", ".join(map(str, missing_text)))
    if missing_audio:
        details.append("TXT without WAV: " + ", ".join(map(str, missing_audio)))
    return " | ".join(details)


def align(
    audio: str | Path,
    transcript: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = DEFAULT_NUM_JOBS,
    word_tier: bool = True,
    phone_tier: bool = True,
    keep_workdir: bool = False,
    progress: ProgressCallback | None = None,
) -> AlignmentResult:
    """Align one WAV/TXT pair with ``lang='auto'``, ``'kor'``, or ``'jap'``."""
    audio_path, text_path = Path(audio).expanduser().resolve(), Path(transcript).expanduser().resolve()
    _validate_pair(audio_path, text_path)
    pair = InputPair(audio_path, text_path, Path(audio_path.stem), _resolve_language(text_path, normalize_language(lang)))
    destination = Path(output_dir).expanduser().resolve() if output_dir else audio_path.parent
    batch = _align_pairs((pair,), destination, kaldi_dir, num_jobs, word_tier, phone_tier, keep_workdir, progress)
    if batch.failures:
        failure = batch.failures[0]
        diagnostics = f"; diagnostics: {failure.work_dir}" if failure.work_dir else ""
        raise AlignmentError(
            f"{failure.language} Kaldi alignment failed: {failure.reason}{diagnostics}", work_dir=failure.work_dir,
        )
    return batch.results[0]


def align_directory(
    directory: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = DEFAULT_NUM_JOBS,
    recursive: bool = False,
    ignore_unmatched: bool = True,
    word_tier: bool = True,
    phone_tier: bool = True,
    keep_workdir: bool = False,
    progress: ProgressCallback | None = None,
) -> BatchAlignmentResult:
    """Align all matched pairs in a directory, selecting a model per TXT file."""
    root = Path(directory).expanduser().resolve()
    pairs, language_failures = _collect_pairs(
        root, recursive=recursive, ignore_unmatched=ignore_unmatched, lang=lang, collect_language_failures=True,
    )
    destination = Path(output_dir).expanduser().resolve() if output_dir else root
    return _align_pairs(
        pairs, destination, kaldi_dir, num_jobs, word_tier, phone_tier, keep_workdir, progress, language_failures,
    )


def _align_pairs(
    pairs: tuple[InputPair, ...], output_dir: Path, kaldi_dir: str | Path | None, num_jobs: int,
    word_tier: bool, phone_tier: bool, keep_workdir: bool, progress: ProgressCallback | None,
    initial_failures: tuple[AlignmentFailure, ...] = (),
) -> BatchAlignmentResult:
    if num_jobs < 1:
        raise ValueError("num_jobs must be at least 1")
    if not word_tier and not phone_tier:
        raise ValueError("At least one of word_tier or phone_tier must be enabled")
    if not pairs and not initial_failures:
        raise PairingError("No alignable WAV/TXT pairs were found.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not pairs:
        if progress:
            progress(
                "summary", len(initial_failures), len(initial_failures),
                f"total={len(initial_failures)} success=0 failed={len(initial_failures)}",
            )
        return BatchAlignmentResult((), output_dir, failures=initial_failures)
    (runtime, engine_env), resources = _resolve_kaldi_dir(kaldi_dir), runtime_root()
    staging_output = Path(tempfile.mkdtemp(prefix=".koreanfa-output-", dir=output_dir))
    diagnostics_root = Path(tempfile.mkdtemp(prefix="koreanfa-batch-")) if keep_workdir else None
    grouped: dict[str, list[InputPair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.language].append(pair)
    all_results: list[AlignmentResult] = []
    all_failures: list[AlignmentFailure] = list(initial_failures)
    try:
        total = len(pairs) + len(initial_failures)
        completed_before = len(initial_failures)
        if progress:
            for index, failure in enumerate(initial_failures, start=1):
                progress("failed", index, total, f"{failure.audio.name} ({failure.reason})")
        for language, group in grouped.items():
            results, failures, work_dir = _run_language_group(
                tuple(group), language, staging_output, runtime, engine_env, resources, num_jobs, word_tier, phone_tier, keep_workdir,
                progress, completed_before, total, diagnostics_root,
            )
            all_results.extend(results)
            all_failures.extend(failures)
            completed_before += len(group)
        published: list[AlignmentResult] = []
        for result in all_results:
            relative = result.textgrid.relative_to(staging_output)
            destination = output_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result.textgrid, destination)
            published.append(AlignmentResult(result.audio, result.transcript, destination, result.language, result.work_dir))
        if progress:
            progress(
                "summary", total, total,
                f"total={total} success={len(published)} failed={len(all_failures)}",
            )
        return BatchAlignmentResult(
            tuple(sorted(published, key=lambda item: str(item.audio))), output_dir, diagnostics_root,
            tuple(sorted(all_failures, key=lambda item: str(item.audio))),
        )
    finally:
        shutil.rmtree(staging_output, ignore_errors=True)
        if not keep_workdir and diagnostics_root:
            shutil.rmtree(diagnostics_root, ignore_errors=True)


def _run_language_group(
    pairs: tuple[InputPair, ...], language: str, output_dir: Path, runtime: Path, engine_env: dict[str, str], resources: Path,
    num_jobs: int, word_tier: bool, phone_tier: bool, keep_workdir: bool, progress: ProgressCallback | None,
    completed_before: int, total: int, diagnostics_root: Path | None,
) -> tuple[list[AlignmentResult], list[AlignmentFailure], Path | None]:
    work_dir = Path(tempfile.mkdtemp(prefix=f"{language}-", dir=diagnostics_root)) if diagnostics_root else Path(
        tempfile.mkdtemp(prefix=f"koreanfa-{language}-")
    )
    input_dir, log_dir = work_dir / "input", work_dir / "logs"
    input_dir.mkdir(); log_dir.mkdir()
    staged: list[tuple[InputPair, str]] = []
    completed_normally = False
    try:
        for index, pair in enumerate(pairs):
            stem = f"pair_{index:06d}"
            normalize_wav(pair.audio, input_dir / f"{stem}.wav")
            shutil.copy2(pair.transcript, input_dir / f"{stem}.txt")
            staged.append((pair, stem))
        command = ["bash", str(resources / "pipeline" / "forced_align.sh"), "-nj", str(num_jobs)]
        if not word_tier: command.append("-nw")
        if not phone_tier: command.append("-np")
        command.append(str(input_dir))
        env = os.environ.copy()
        env.update({
            "KOREANFA_KALDI_DIR": str(runtime),
            "KOREANFA_LOG_DIR": str(log_dir),
            "KOREANFA_LANG": language,
            "KOREANFA_PYTHON_EXECUTABLE": sys.executable,
        })
        _merge_engine_environment(env, engine_env)
        completed = _run_runtime_command(
            command, resources, env, progress, completed_before, total, tuple(pair.audio.name for pair, _ in staged),
        )
        missing = [stem for _, stem in staged if not (input_dir / f"{stem}.TextGrid").is_file()]
        if completed.returncode != 0 or missing:
            group_total, group_success, group_failed = _runtime_summary(completed.stdout)
            if group_total != len(staged) or group_success + group_failed != len(staged):
                raise AlignmentError(
                    f"{language} Kaldi alignment failed (exit code {completed.returncode}); diagnostics: {work_dir}",
                    work_dir=work_dir, stdout=completed.stdout, stderr=completed.stderr,
                )
        failure_reasons = _runtime_failure_reasons(completed.stdout)
        results = []
        failures = []
        for pair, stem in staged:
            textgrid_source = input_dir / f"{stem}.TextGrid"
            if not textgrid_source.is_file():
                failures.append(
                    AlignmentFailure(
                        pair.audio, pair.transcript, language,
                        failure_reasons.get(stem, "The runtime did not produce a TextGrid."),
                        work_dir if keep_workdir else None,
                    )
                )
                continue
            textgrid = output_dir / pair.relative_stem.with_suffix(".TextGrid")
            textgrid.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(textgrid_source, textgrid)
            results.append(AlignmentResult(pair.audio, pair.transcript, textgrid, language, work_dir if keep_workdir else None))
        completed_normally = True
        return results, failures, work_dir if keep_workdir else None
    finally:
        if completed_normally and not keep_workdir:
            shutil.rmtree(work_dir, ignore_errors=True)


def _runtime_summary(output: str) -> tuple[int, int, int]:
    """Read the batch runtime's final summary record, if it was emitted."""
    for line in reversed(output.splitlines()):
        fields = line.split("\t")
        if fields and fields[0] == "KOREANFA_SUMMARY":
            values = dict(field.split("=", 1) for field in fields[1:] if "=" in field)
            return tuple(int(values.get(key, "0")) for key in ("total", "success", "failed"))
    return 0, 0, 0


def _runtime_failure_reasons(output: str) -> dict[str, str]:
    """Map staged pair stems to the reason emitted by the shell runtime."""
    failures: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t", 4)
        if len(fields) == 5 and fields[:2] == ["KOREANFA_EVENT", "failed"]:
            failures[f"pair_{int(fields[2]):06d}"] = fields[4]
    return failures


def _run_runtime_command(
    command: list[str], cwd: Path, env: dict[str, str], progress: ProgressCallback | None, completed_before: int, total: int,
    input_names: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Run the shell runtime while preserving its diagnostics and progress events.

    The runtime emits tab-separated ``KOREANFA_EVENT`` records.  Ordinary
    Kaldi output stays available on ``AlignmentError.stdout`` rather than
    leaking from library calls.
    """
    process = subprocess.Popen(
        command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    assert process.stdout is not None
    output: list[str] = []
    local_done = 0
    for line in process.stdout:
        output.append(line)
        fields = line.rstrip("\n").split("\t")
        if fields[0] == "KOREANFA_SUMMARY":
            continue
        if len(fields) < 2 or fields[0] != "KOREANFA_EVENT":
            continue
        phase = fields[1]
        if phase in {"completed", "failed", "skipped"}:
            local_done += 1
        if progress:
            detail = fields[3] if len(fields) >= 4 else ""
            if len(fields) >= 3 and fields[2].isdigit() and int(fields[2]) < len(input_names):
                detail = input_names[int(fields[2])]
            if phase == "attempt" and len(fields) >= 5:
                detail += f" (attempt {fields[4]})"
            if phase == "failed" and len(fields) >= 5:
                detail += f" ({fields[4]})"
            progress(phase, min(completed_before + local_done, total), total, detail)
    returncode = process.wait()
    return subprocess.CompletedProcess(command, returncode, "".join(output), "")


def _resolve_language(transcript: Path, requested: str) -> str:
    return detect_language(transcript) if requested == "auto" else requested


def _merge_engine_environment(environment: dict[str, str], engine_environment: dict[str, str]) -> None:
    """Add engine settings without discarding a caller's library search paths."""
    for key, value in engine_environment.items():
        if key in _LIBRARY_PATH_VARIABLES:
            environment[key] = ":".join(filter(None, (value, environment.get(key))))
        else:
            environment.setdefault(key, value)


def _validate_pair(audio: Path, transcript: Path) -> None:
    if not audio.is_file() or audio.suffix.lower() != ".wav":
        raise PairingError(f"Audio must be an existing WAV file: {audio}")
    if not transcript.is_file() or transcript.suffix.lower() != ".txt":
        raise PairingError(f"Transcript must be an existing TXT file: {transcript}")


def _resolve_kaldi_dir(kaldi_dir: str | Path | None) -> tuple[Path, dict[str, str]]:
    candidate = kaldi_dir or os.environ.get("KOREANFA_KALDI_DIR")
    if candidate:
        return _validate_kaldi_dir(Path(candidate).expanduser().resolve()), {}
    engine = installed_engine()
    if engine is None:
        raise EngineNotFoundError(
            "KoreanFA native engine is required but not installed. Run 'koreanfa engine install' or call "
            "'from koreanfa.engine import install; install()'."
        )
    return engine.kaldi_dir, engine.environment


def _validate_kaldi_dir(root: Path) -> Path:
    if not (root / "src" / "bin" / "ali-to-phones").is_file():
        raise EngineNotFoundError(f"No usable Kaldi runtime at {root}")
    return root
