"""Preflight validation for KoreanFA file pairs and corpora."""

import tempfile
from pathlib import Path

from ._io import report_output_path
from ._validation_report import (
    ValidatedPair,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from .audio import normalize_wav
from .engine import status as engine_status
from .errors import AudioPreparationError, KoreanFAError, PairingError
from .language import detect_language, normalize_language
from .pairing import _portable_path_key, discover_corpus_files
from .pronunciation import (
    PronunciationDictionary,
    PronunciationDictionaryError,
    korean_oov_tokens,
    load_pronunciation_dictionary,
)

__all__ = ["ValidatedPair", "ValidationIssue", "ValidationReport", "validate"]


def validate(
    input_path: str | Path,
    transcript: str | Path | None = None,
    *,
    lang: str = "auto",
    recursive: bool = False,
    ignore_unmatched: bool = True,
    check_engine: bool = True,
    report_path: str | Path | None = None,
    pronunciation_dictionary: str | Path | None = None,
) -> ValidationReport:
    """Validate a WAV/TXT pair or directory without running forced alignment."""
    source = Path(input_path).expanduser().resolve()
    report_destination: Path | None = None
    if report_path is not None:
        report_destination = report_output_path(report_path)
        protected_inputs = _validation_input_paths(source, transcript, recursive=recursive)
        protected_keys = {_portable_path_key(path.resolve()) for path in protected_inputs}
        if _portable_path_key(report_destination) in protected_keys:
            raise ValueError("report_path must not overwrite an input file")
    requested_language = normalize_language(lang)
    issues: list[ValidationIssue] = []
    dictionary = _load_dictionary(pronunciation_dictionary, issues)
    check_korean_oov = pronunciation_dictionary is None or dictionary is not None
    candidates: list[tuple[Path, Path]] = []
    root = source if source.is_dir() else source.parent
    if source.is_dir():
        if transcript is not None:
            raise ValueError("A directory input discovers its own WAV/TXT pairs; do not pass transcript.")
        try:
            discovery = discover_corpus_files(source, recursive=recursive, require_both=False)
        except PairingError as error:
            issues.append(
                ValidationIssue("corpus.discovery", "error", source, str(error), "Provide matching WAV and UTF-8 TXT files.")
            )
        else:
            candidates.extend((pair.audio, pair.transcript) for pair in discovery.pairs)
            if not discovery.pairs and not discovery.missing_text and not discovery.missing_audio:
                issues.append(
                    ValidationIssue(
                        "corpus.empty", "error", source, "No WAV or TXT files were found.",
                        "Add matching WAV and UTF-8 TXT files.",
                    )
                )
            elif not discovery.pairs:
                issues.append(
                    ValidationIssue(
                        "corpus.no_pairs", "error", source, "No matching WAV/TXT pair was found.",
                        "Add at least one WAV and TXT file with the same relative stem.",
                    )
                )
            severity: ValidationSeverity = "warning" if ignore_unmatched else "error"
            for path in discovery.unmatched_audio:
                issues.append(
                    ValidationIssue(
                        "pair.missing_transcript", severity, path,
                        "WAV file has no matching TXT transcript.", "Add the matching TXT file or remove the WAV file.",
                    )
                )
            for path in discovery.unmatched_transcripts:
                issues.append(
                    ValidationIssue(
                        "pair.missing_audio", severity, path,
                        "TXT transcript has no matching WAV audio.", "Add the matching WAV file or remove the TXT file.",
                    )
                )
    else:
        if transcript is None:
            issues.append(
                ValidationIssue(
                    "pair.missing_transcript", "error", source, "A WAV input requires a TXT transcript.",
                    "Pass the transcript path as the second argument.",
                )
            )
        else:
            candidates.append((source, Path(transcript).expanduser().resolve()))

    passed: list[ValidatedPair] = []
    with tempfile.TemporaryDirectory(prefix="koreanfa-validate-") as temporary:
        temporary_root = Path(temporary)
        for index, (audio, text) in enumerate(candidates):
            pair_issues = _validate_candidate(
                audio,
                text,
                requested_language,
                temporary_root / f"{index:06d}.wav",
                dictionary,
                check_korean_oov,
            )
            issues.extend(pair_issues)
            if not any(issue.severity == "error" for issue in pair_issues):
                language = requested_language if requested_language != "auto" else detect_language(text)
                passed.append(ValidatedPair(audio, text, language))

    installed: bool | None = None
    platform: str | None = None
    version: str | None = None
    if check_engine:
        try:
            state = engine_status()
            installed, platform, version = state.installed, state.platform, state.version
            if not state.installed:
                issues.append(
                    ValidationIssue(
                        "engine.not_installed", "error", None, "The compatible KoreanFA engine is not installed.",
                        "Run 'koreanfa engine install' before alignment.",
                    )
                )
        except KoreanFAError as error:
            issues.append(
                ValidationIssue(
                    "engine.unsupported", "error", None, str(error),
                    "Use a supported Linux or macOS environment listed in the README.",
                )
            )
    report = ValidationReport(root, tuple(passed), tuple(issues), installed, platform, version)
    if report_path is not None:
        report.write_json(report_path)
    return report


def _validation_input_paths(
    source: Path, transcript: str | Path | None, *, recursive: bool
) -> tuple[Path, ...]:
    """Collect report-protected inputs even when corpus discovery is ambiguous."""
    if not source.is_dir():
        values = [source]
        if transcript is not None:
            values.append(Path(transcript).expanduser().resolve())
        return tuple(values)
    candidates = source.rglob("*") if recursive else source.iterdir()
    return tuple(
        path
        for path in candidates
        if path.is_file() and path.suffix.lower() in {".wav", ".txt"}
    )


def _validate_candidate(
    audio: Path,
    transcript: Path,
    requested_language: str,
    normalized_audio: Path,
    pronunciation_dictionary: PronunciationDictionary | None,
    check_korean_oov: bool,
) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    if not audio.is_file() or audio.suffix.lower() != ".wav":
        issues.append(
            ValidationIssue("audio.missing", "error", audio, "Audio is not an existing WAV file.", "Provide a readable WAV file.")
        )
    if not transcript.is_file() or transcript.suffix.lower() != ".txt":
        issues.append(
            ValidationIssue(
                "transcript.missing", "error", transcript, "Transcript is not an existing TXT file.",
                "Provide a matching UTF-8 TXT file.",
            )
        )
    text: str | None = None
    if transcript.is_file() and transcript.suffix.lower() == ".txt":
        try:
            text = transcript.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            issues.append(
                ValidationIssue(
                    "transcript.invalid_utf8", "error", transcript, "Transcript is not valid UTF-8.",
                    "Convert and save the transcript as UTF-8.",
                )
            )
        except OSError as error:
            issues.append(
                ValidationIssue(
                    "transcript.unreadable", "error", transcript, f"Transcript could not be read: {error}",
                    "Check the file permissions and retry.",
                )
            )
    if text is not None:
        if not text.strip():
            issues.append(
                ValidationIssue("transcript.empty", "error", transcript, "Transcript is empty.", "Add the spoken text.")
            )
        elif "\x00" in text or any(ord(char) < 32 and char not in "\n\r\t" for char in text):
            issues.append(
                ValidationIssue(
                    "transcript.control_character", "error", transcript,
                    "Transcript contains a NUL or unsupported control character.", "Remove binary/control characters.",
                )
            )
        else:
            effective_language: str | None = requested_language if requested_language != "auto" else None
            try:
                detected = detect_language(text)
                effective_language = detected if requested_language == "auto" else effective_language
                if requested_language != "auto" and detected != requested_language:
                    issues.append(
                        ValidationIssue(
                            "language.forced_mismatch", "warning", transcript,
                            f"Text looks like {detected}, but {requested_language} was forced.",
                            "Use lang='auto' or confirm the forced model is intentional.",
                        )
                    )
            except PairingError as error:
                issues.append(
                    ValidationIssue(
                        "language.undetermined",
                        "error" if requested_language == "auto" else "warning",
                        transcript,
                        str(error),
                        "Use Korean/Japanese text or force the intended language explicitly.",
                    )
                )
            if effective_language == "kor" and check_korean_oov:
                oov_tokens = korean_oov_tokens(text, pronunciation_dictionary)
                if oov_tokens:
                    issues.append(
                        ValidationIssue(
                            "transcript.oov",
                            "error",
                            transcript,
                            f"Korean G2P could not derive pronunciations for {len(oov_tokens)} token(s).",
                            "Add kor rows for these tokens to --pronunciation-dictionary, then validate again.",
                            oov_tokens,
                        )
                    )
    if audio.is_file() and audio.suffix.lower() == ".wav":
        try:
            normalize_wav(audio, normalized_audio)
        except AudioPreparationError:
            issues.append(
                ValidationIssue(
                    "audio.invalid", "error", audio, "Audio could not be completely decoded and normalized as WAV.",
                    "Replace or re-encode the file as valid PCM/float WAV audio.",
                )
            )
    return tuple(issues)


def _load_dictionary(
    path: str | Path | None, issues: list[ValidationIssue]
) -> PronunciationDictionary | None:
    if path is None:
        return None
    source = Path(path).expanduser()
    try:
        return load_pronunciation_dictionary(source)
    except PronunciationDictionaryError as error:
        issues.append(
            ValidationIssue(
                "pronunciation_dictionary.invalid",
                "error",
                source,
                str(error),
                "Use a UTF-8 TSV headed by language, word, and pronunciation.",
            )
        )
        return None
