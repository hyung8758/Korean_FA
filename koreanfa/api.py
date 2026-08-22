"""Public file and directory forced-alignment APIs."""

import warnings
from pathlib import Path

from ._workflow import align_pairs as _align_pairs
from .errors import AlignmentError, PairingError
from .language import detect_language, normalize_language
from .pairing import discover_corpus_files
from .pronunciation import PronunciationDictionary, load_pronunciation_dictionary
from .result import (
    AlignmentFailure,
    AlignmentResult,
    AlignmentSkip,
    BatchAlignmentResult,
    ExistingOutputPolicy,
    ExportFormat,
    InputPair,
    ProgressCallback,
)

DEFAULT_NUM_JOBS = 4


def discover_pairs(
    directory: str | Path,
    *,
    recursive: bool = False,
    ignore_unmatched: bool = True,
    lang: str = "auto",
) -> tuple[InputPair, ...]:
    """Find matching WAV/TXT pairs and resolve each model language."""
    pairs, _, _ = _collect_pairs(
        directory, recursive=recursive, ignore_unmatched=ignore_unmatched, lang=lang
    )
    return pairs


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
    existing: ExistingOutputPolicy = "overwrite",
    exports: tuple[ExportFormat, ...] = (),
    report_path: str | Path | None = None,
    pronunciation_dictionary: str | Path | None = None,
) -> AlignmentResult | AlignmentSkip:
    """Align one WAV/TXT pair with automatic or forced language selection."""
    audio_path = Path(audio).expanduser().resolve()
    transcript_path = Path(transcript).expanduser().resolve()
    _validate_pair(audio_path, transcript_path)
    requested_language = normalize_language(lang)
    dictionary = _load_dictionary(pronunciation_dictionary)
    pair = InputPair(
        audio_path,
        transcript_path,
        Path(audio_path.stem),
        _resolve_language(transcript_path, requested_language),
    )
    destination = Path(output_dir).expanduser().resolve() if output_dir else audio_path.parent
    batch = _align_pairs(
        (pair,),
        destination,
        kaldi_dir,
        num_jobs,
        word_tier,
        phone_tier,
        keep_workdir,
        progress,
        existing=existing,
        exports=exports,
        report_path=report_path,
        input_root=audio_path.parent,
        requested_language=requested_language,
        pronunciation_dictionary=dictionary,
    )
    if batch.failures:
        failure = batch.failures[0]
        diagnostics = f"; diagnostics: {failure.work_dir}" if failure.work_dir else ""
        raise AlignmentError(
            f"{failure.language} Kaldi alignment failed: {failure.reason}{diagnostics}",
            work_dir=failure.work_dir,
        )
    if batch.results:
        return batch.results[0]
    return batch.skipped[0]


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
    existing: ExistingOutputPolicy = "overwrite",
    exports: tuple[ExportFormat, ...] = (),
    report_path: str | Path | None = None,
    pronunciation_dictionary: str | Path | None = None,
) -> BatchAlignmentResult:
    """Align every matched pair in a directory using the appropriate model."""
    root = Path(directory).expanduser().resolve()
    dictionary = _load_dictionary(pronunciation_dictionary)
    pairs, failures, protected_inputs = _collect_pairs(
        root,
        recursive=recursive,
        ignore_unmatched=ignore_unmatched,
        lang=lang,
        collect_language_failures=True,
    )
    destination = Path(output_dir).expanduser().resolve() if output_dir else root
    return _align_pairs(
        pairs,
        destination,
        kaldi_dir,
        num_jobs,
        word_tier,
        phone_tier,
        keep_workdir,
        progress,
        failures,
        existing=existing,
        exports=exports,
        report_path=report_path,
        input_root=root,
        requested_language=normalize_language(lang),
        recursive=recursive,
        ignore_unmatched=ignore_unmatched,
        protected_inputs=protected_inputs,
        pronunciation_dictionary=dictionary,
    )


def _collect_pairs(
    directory: str | Path,
    *,
    recursive: bool,
    ignore_unmatched: bool,
    lang: str,
    collect_language_failures: bool = False,
) -> tuple[tuple[InputPair, ...], tuple[AlignmentFailure, ...], tuple[Path, ...]]:
    root = Path(directory).expanduser().resolve()
    requested_language = normalize_language(lang)
    discovery = discover_corpus_files(root, recursive=recursive)
    _handle_unmatched(
        list(discovery.missing_text),
        list(discovery.missing_audio),
        ignore_unmatched=ignore_unmatched,
    )
    pairs: list[InputPair] = []
    failures: list[AlignmentFailure] = []
    for discovered in discovery.pairs:
        try:
            language = _resolve_language(discovered.transcript, requested_language)
        except PairingError as error:
            if not collect_language_failures:
                raise
            failures.append(
                AlignmentFailure(discovered.audio, discovered.transcript, "auto", str(error))
            )
            continue
        pairs.append(
            InputPair(
                discovered.audio,
                discovered.transcript,
                discovered.relative_stem,
                language,
            )
        )
    protected_inputs = tuple(
        path for pair in discovery.pairs for path in (pair.audio, pair.transcript)
    ) + discovery.unmatched_audio + discovery.unmatched_transcripts
    return tuple(pairs), tuple(failures), protected_inputs


def _handle_unmatched(
    missing_text: list[Path], missing_audio: list[Path], *, ignore_unmatched: bool
) -> None:
    if not missing_text and not missing_audio:
        return
    details = _unmatched_details(missing_text, missing_audio)
    if not ignore_unmatched:
        raise PairingError("Unmatched corpus files. " + details)
    warnings.warn("Ignoring unmatched corpus files. " + details, UserWarning, stacklevel=3)


def _unmatched_details(missing_text: list[Path], missing_audio: list[Path]) -> str:
    details = []
    if missing_text:
        details.append("WAV without TXT: " + ", ".join(map(str, missing_text)))
    if missing_audio:
        details.append("TXT without WAV: " + ", ".join(map(str, missing_audio)))
    return " | ".join(details)


def _resolve_language(transcript: Path, requested: str) -> str:
    return detect_language(transcript) if requested == "auto" else requested


def _validate_pair(audio: Path, transcript: Path) -> None:
    if not audio.is_file() or audio.suffix.lower() != ".wav":
        raise PairingError(f"Audio must be an existing WAV file: {audio}")
    if not transcript.is_file() or transcript.suffix.lower() != ".txt":
        raise PairingError(f"Transcript must be an existing TXT file: {transcript}")


def _load_dictionary(path: str | Path | None) -> PronunciationDictionary | None:
    return load_pronunciation_dictionary(path) if path is not None else None
