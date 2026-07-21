"""File and directory forced-alignment APIs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .errors import AlignmentError, EngineNotFoundError, PairingError
from .audio import normalize_wav
from .language import detect_language, normalize_language
from .resources import runtime_root
from .result import AlignmentResult, BatchAlignmentResult, InputPair


def discover_pairs(
    directory: str | Path, *, recursive: bool = False, strict: bool = True, lang: str = "auto"
) -> tuple[InputPair, ...]:
    """Find matching WAV/TXT pairs and resolve the model language for each."""
    root = Path(directory).expanduser().resolve()
    requested_lang = normalize_language(lang)
    if not root.is_dir():
        raise PairingError(f"Input directory does not exist: {root}")
    files: Iterable[Path] = root.rglob("*") if recursive else root.iterdir()
    audio: dict[Path, Path] = {}
    text: dict[Path, Path] = {}
    for path in files:
        if path.is_file():
            key = path.relative_to(root).with_suffix("")
            if path.suffix.lower() == ".wav":
                audio[key] = path
            elif path.suffix.lower() == ".txt":
                text[key] = path
    if not audio or not text:
        raise PairingError(f"A corpus needs both WAV and TXT files: {root}")
    missing_audio, missing_text = sorted(set(text) - set(audio)), sorted(set(audio) - set(text))
    if strict and (missing_audio or missing_text):
        details = []
        if missing_text:
            details.append("WAV without TXT: " + ", ".join(map(str, missing_text)))
        if missing_audio:
            details.append("TXT without WAV: " + ", ".join(map(str, missing_audio)))
        raise PairingError("Unmatched corpus files. " + " | ".join(details))
    return tuple(
        InputPair(audio=audio[key], transcript=text[key], relative_stem=key, language=_resolve_language(text[key], requested_lang))
        for key in sorted(set(audio) & set(text))
    )


def align(
    audio: str | Path,
    transcript: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = 1,
    word_tier: bool = True,
    phone_tier: bool = True,
    keep_workdir: bool = False,
) -> AlignmentResult:
    """Align one WAV/TXT pair with ``lang='auto'``, ``'kor'``, or ``'jap'``."""
    audio_path, text_path = Path(audio).expanduser().resolve(), Path(transcript).expanduser().resolve()
    _validate_pair(audio_path, text_path)
    pair = InputPair(audio_path, text_path, Path(audio_path.stem), _resolve_language(text_path, normalize_language(lang)))
    destination = Path(output_dir).expanduser().resolve() if output_dir else audio_path.parent
    return _align_pairs((pair,), destination, kaldi_dir, num_jobs, word_tier, phone_tier, keep_workdir).results[0]


def align_directory(
    directory: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = 1,
    recursive: bool = False,
    strict: bool = True,
    word_tier: bool = True,
    phone_tier: bool = True,
    keep_workdir: bool = False,
) -> BatchAlignmentResult:
    """Align all matched pairs in a directory, selecting a model per TXT file."""
    root = Path(directory).expanduser().resolve()
    pairs = discover_pairs(root, recursive=recursive, strict=strict, lang=lang)
    destination = Path(output_dir).expanduser().resolve() if output_dir else root
    return _align_pairs(pairs, destination, kaldi_dir, num_jobs, word_tier, phone_tier, keep_workdir)


def _align_pairs(
    pairs: tuple[InputPair, ...], output_dir: Path, kaldi_dir: str | Path | None, num_jobs: int,
    word_tier: bool, phone_tier: bool, keep_workdir: bool,
) -> BatchAlignmentResult:
    if num_jobs < 1:
        raise ValueError("num_jobs must be at least 1")
    if not word_tier and not phone_tier:
        raise ValueError("At least one of word_tier or phone_tier must be enabled")
    runtime, resources = _resolve_kaldi_dir(kaldi_dir), runtime_root()
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[InputPair]] = defaultdict(list)
    for pair in pairs:
        grouped[pair.language].append(pair)
    all_results: list[AlignmentResult] = []
    batch_workdir: Path | None = None
    for language, group in grouped.items():
        results, work_dir = _run_language_group(tuple(group), language, output_dir, runtime, resources, num_jobs, word_tier, phone_tier, keep_workdir)
        all_results.extend(results)
        batch_workdir = work_dir or batch_workdir
    return BatchAlignmentResult(tuple(sorted(all_results, key=lambda item: str(item.audio))), output_dir, batch_workdir)


def _run_language_group(
    pairs: tuple[InputPair, ...], language: str, output_dir: Path, runtime: Path, resources: Path,
    num_jobs: int, word_tier: bool, phone_tier: bool, keep_workdir: bool,
) -> tuple[list[AlignmentResult], Path | None]:
    work_dir = Path(tempfile.mkdtemp(prefix=f"koreanfa-{language}-"))
    input_dir, log_dir = work_dir / "input", work_dir / "logs"
    input_dir.mkdir(); log_dir.mkdir()
    staged: list[tuple[InputPair, str]] = []
    succeeded = False
    try:
        for index, pair in enumerate(pairs):
            stem = f"pair_{index:06d}"
            normalize_wav(pair.audio, input_dir / f"{stem}.wav")
            shutil.copy2(pair.transcript, input_dir / f"{stem}.txt")
            staged.append((pair, stem))
        command = ["bash", str(resources / "forced_align.sh"), "-nj", str(num_jobs)]
        if not word_tier: command.append("-nw")
        if not phone_tier: command.append("-np")
        command.append(str(input_dir))
        env = os.environ.copy()
        env.update({"KOREANFA_KALDI_DIR": str(runtime), "KOREANFA_LOG_DIR": str(log_dir), "KOREANFA_LANG": language})
        completed = subprocess.run(command, cwd=resources, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        missing = [stem for _, stem in staged if not (input_dir / f"{stem}.TextGrid").is_file()]
        if completed.returncode != 0 or missing:
            raise AlignmentError(
                f"{language} Kaldi alignment failed (exit code {completed.returncode}); diagnostics: {work_dir}",
                work_dir=work_dir, stdout=completed.stdout, stderr=completed.stderr,
            )
        results = []
        for pair, stem in staged:
            textgrid = output_dir / pair.relative_stem.with_suffix(".TextGrid")
            textgrid.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_dir / f"{stem}.TextGrid", textgrid)
            results.append(AlignmentResult(pair.audio, pair.transcript, textgrid, language, work_dir if keep_workdir else None))
        succeeded = True
        return results, work_dir if keep_workdir else None
    finally:
        if succeeded and not keep_workdir:
            shutil.rmtree(work_dir, ignore_errors=True)


def _resolve_language(transcript: Path, requested: str) -> str:
    return detect_language(transcript) if requested == "auto" else requested


def _validate_pair(audio: Path, transcript: Path) -> None:
    if not audio.is_file() or audio.suffix.lower() != ".wav":
        raise PairingError(f"Audio must be an existing WAV file: {audio}")
    if not transcript.is_file() or transcript.suffix.lower() != ".txt":
        raise PairingError(f"Transcript must be an existing TXT file: {transcript}")


def _resolve_kaldi_dir(kaldi_dir: str | Path | None) -> Path:
    candidate = kaldi_dir or os.environ.get("KOREANFA_KALDI_DIR")
    if not candidate:
        raise EngineNotFoundError("Kaldi is not configured. Set KOREANFA_KALDI_DIR or install the future koreanfa-engine wheel.")
    root = Path(candidate).expanduser().resolve()
    if not (root / "src" / "bin" / "ali-to-phones").is_file():
        raise EngineNotFoundError(f"No usable Kaldi runtime at {root}")
    return root
