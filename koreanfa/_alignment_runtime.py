"""Kaldi process execution for the alignment workflow."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .audio import normalize_wav
from .errors import AlignmentError, AudioPreparationError
from .pairing import _textgrid_relative_path
from .result import AlignmentFailure, AlignmentResult, InputPair, ProgressCallback

_LIBRARY_PATH_VARIABLES = frozenset({"LD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"})


def run_language_group(
    pairs: tuple[InputPair, ...],
    language: str,
    output_dir: Path,
    runtime: Path,
    engine_env: dict[str, str],
    resources: Path,
    num_jobs: int,
    word_tier: bool,
    phone_tier: bool,
    keep_workdir: bool,
    progress: ProgressCallback | None,
    completed_before: int,
    total: int,
    diagnostics_root: Path | None,
) -> tuple[list[AlignmentResult], list[AlignmentFailure], Path | None]:
    """Normalize and align every pair assigned to one language model."""
    work_dir = _work_directory(language, diagnostics_root)
    input_dir, log_dir = work_dir / "input", work_dir / "logs"
    input_dir.mkdir()
    log_dir.mkdir()
    staged, failures = _stage_pairs(
        pairs, language, input_dir, work_dir, keep_workdir, progress, completed_before, total
    )
    completed_normally = False
    try:
        if not staged:
            completed_normally = True
            return [], failures, work_dir if keep_workdir else None
        command = _runtime_command(resources, input_dir, num_jobs, word_tier, phone_tier)
        environment = _runtime_environment(runtime, log_dir, language, engine_env)
        completed = run_runtime_command(
            command,
            resources,
            environment,
            progress,
            completed_before + len(failures),
            total,
            tuple(pair.audio.name for pair, _ in staged),
        )
        _require_complete_runtime_summary(completed, staged, input_dir, language, work_dir)
        results = _collect_runtime_outputs(
            staged, input_dir, output_dir, language, work_dir, keep_workdir, completed.stdout, failures
        )
        completed_normally = True
        return results, failures, work_dir if keep_workdir else None
    finally:
        if completed_normally and not keep_workdir:
            shutil.rmtree(work_dir, ignore_errors=True)


def _work_directory(language: str, diagnostics_root: Path | None) -> Path:
    prefix = f"{language}-" if diagnostics_root else f"koreanfa-{language}-"
    return Path(tempfile.mkdtemp(prefix=prefix, dir=diagnostics_root))


def _stage_pairs(
    pairs: tuple[InputPair, ...],
    language: str,
    input_dir: Path,
    work_dir: Path,
    keep_workdir: bool,
    progress: ProgressCallback | None,
    completed_before: int,
    total: int,
) -> tuple[list[tuple[InputPair, str]], list[AlignmentFailure]]:
    staged: list[tuple[InputPair, str]] = []
    failures: list[AlignmentFailure] = []
    for pair in pairs:
        stem = f"pair_{len(staged):06d}"
        try:
            normalize_wav(pair.audio, input_dir / f"{stem}.wav")
        except AudioPreparationError as error:
            failures.append(
                AlignmentFailure(
                    pair.audio, pair.transcript, language, str(error), work_dir if keep_workdir else None
                )
            )
            if progress:
                progress("failed", completed_before + len(failures), total, f"{pair.audio.name} ({error})")
            continue
        shutil.copy2(pair.transcript, input_dir / f"{stem}.txt")
        staged.append((pair, stem))
    return staged, failures


def _runtime_command(
    resources: Path, input_dir: Path, num_jobs: int, word_tier: bool, phone_tier: bool
) -> list[str]:
    command = ["bash", str(resources / "pipeline" / "forced_align.sh"), "-nj", str(num_jobs)]
    if not word_tier:
        command.append("-nw")
    if not phone_tier:
        command.append("-np")
    command.append(str(input_dir))
    return command


def _runtime_environment(
    runtime: Path, log_dir: Path, language: str, engine_environment: dict[str, str]
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "KOREANFA_KALDI_DIR": str(runtime),
            "KOREANFA_LOG_DIR": str(log_dir),
            "KOREANFA_LANG": language,
            "KOREANFA_PYTHON_EXECUTABLE": sys.executable,
        }
    )
    merge_engine_environment(environment, engine_environment)
    return environment


def _require_complete_runtime_summary(
    completed: subprocess.CompletedProcess[str],
    staged: list[tuple[InputPair, str]],
    input_dir: Path,
    language: str,
    work_dir: Path,
) -> None:
    missing = [stem for _, stem in staged if not (input_dir / f"{stem}.TextGrid").is_file()]
    if completed.returncode == 0 and not missing:
        return
    total, success, failed = runtime_summary(completed.stdout)
    if total != len(staged) or success + failed != len(staged):
        raise AlignmentError(
            f"{language} Kaldi alignment failed (exit code {completed.returncode}); diagnostics: {work_dir}",
            work_dir=work_dir,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def _collect_runtime_outputs(
    staged: list[tuple[InputPair, str]],
    input_dir: Path,
    output_dir: Path,
    language: str,
    work_dir: Path,
    keep_workdir: bool,
    output: str,
    failures: list[AlignmentFailure],
) -> list[AlignmentResult]:
    reasons, attempts = runtime_failure_reasons(output), runtime_attempt_counts(output)
    results: list[AlignmentResult] = []
    for pair, stem in staged:
        source = input_dir / f"{stem}.TextGrid"
        if not source.is_file():
            failures.append(
                AlignmentFailure(
                    pair.audio,
                    pair.transcript,
                    language,
                    reasons.get(stem, "The runtime did not produce a TextGrid."),
                    work_dir if keep_workdir else None,
                    attempts.get(stem, 0),
                )
            )
            continue
        destination = output_dir / _textgrid_relative_path(pair.relative_stem)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        results.append(
            AlignmentResult(
                pair.audio,
                pair.transcript,
                destination,
                language,
                work_dir if keep_workdir else None,
                attempts=attempts.get(stem, 1),
            )
        )
    return results


def runtime_summary(output: str) -> tuple[int, int, int]:
    """Read the batch runtime's final summary record, if present."""
    for line in reversed(output.splitlines()):
        fields = line.split("\t")
        if fields and fields[0] == "KOREANFA_SUMMARY":
            values = dict(field.split("=", 1) for field in fields[1:] if "=" in field)
            return int(values.get("total", "0")), int(values.get("success", "0")), int(values.get("failed", "0"))
    return 0, 0, 0


def runtime_failure_reasons(output: str) -> dict[str, str]:
    """Map staged pair stems to failure reasons emitted by the runtime."""
    failures: dict[str, str] = {}
    for line in output.splitlines():
        fields = line.split("\t", 4)
        if len(fields) == 5 and fields[:2] == ["KOREANFA_EVENT", "failed"]:
            try:
                failures[f"pair_{int(fields[2]):06d}"] = fields[4]
            except ValueError:
                continue
    return failures


def runtime_attempt_counts(output: str) -> dict[str, int]:
    """Map staged pair stems to their greatest emitted attempt number."""
    attempts: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) < 5 or fields[:2] != ["KOREANFA_EVENT", "attempt"]:
            continue
        try:
            stem = f"pair_{int(fields[2]):06d}"
            attempt = int(fields[4].split("/", 1)[0])
        except ValueError:
            continue
        attempts[stem] = max(attempts.get(stem, 1), attempt)
    return attempts


def run_runtime_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    progress: ProgressCallback | None,
    completed_before: int,
    total: int,
    input_names: tuple[str, ...],
) -> subprocess.CompletedProcess[str]:
    """Run the shell pipeline while converting its events into callbacks."""
    process = subprocess.Popen(
        command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    assert process.stdout is not None
    output: list[str] = []
    completed_count = 0
    with process.stdout:
        for line in process.stdout:
            output.append(line)
            fields = line.rstrip("\n").split("\t")
            if not fields or fields[0] == "KOREANFA_SUMMARY" or len(fields) < 2 or fields[0] != "KOREANFA_EVENT":
                continue
            phase = fields[1]
            if phase in {"completed", "failed", "skipped"}:
                completed_count += 1
            if progress:
                detail = _event_detail(fields, input_names)
                progress(phase, min(completed_before + completed_count, total), total, detail)
    return subprocess.CompletedProcess(command, process.wait(), "".join(output), "")


def _event_detail(fields: list[str], input_names: tuple[str, ...]) -> str:
    detail = fields[3] if len(fields) >= 4 else ""
    if len(fields) >= 3 and fields[2].isdigit() and int(fields[2]) < len(input_names):
        detail = input_names[int(fields[2])]
    if fields[1] == "attempt" and len(fields) >= 5:
        return f"{detail} (attempt {fields[4]})"
    if fields[1] == "failed" and len(fields) >= 5:
        return f"{detail} ({fields[4]})"
    return detail


def merge_engine_environment(environment: dict[str, str], engine_environment: dict[str, str]) -> None:
    """Add engine settings without discarding caller library paths."""
    for key, value in engine_environment.items():
        if key in _LIBRARY_PATH_VARIABLES:
            environment[key] = ":".join(filter(None, (value, environment.get(key))))
        else:
            environment.setdefault(key, value)
