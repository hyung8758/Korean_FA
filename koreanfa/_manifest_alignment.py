"""Preflight and execute explicit CSV-manifest alignment batches."""

from pathlib import Path

from ._alignment_outputs import output_paths, plan_outputs
from ._workflow import align_pairs
from .errors import PairingError
from .language import detect_language, normalize_language
from .manifest import ManifestEntry, read_manifest
from .pairing import _portable_path_key, validate_explicit_pair
from .pronunciation import load_pronunciation_dictionary
from .result import (
    AlignmentFailure,
    BatchAlignmentResult,
    ExistingOutputPolicy,
    ExportFormat,
    InputPair,
    ProgressCallback,
)


def align_manifest(
    manifest: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = 4,
    word_tier: bool = True,
    phone_tier: bool = True,
    romanization_tier: bool = True,
    keep_workdir: bool = False,
    progress: ProgressCallback | None = None,
    existing: ExistingOutputPolicy = "overwrite",
    exports: tuple[ExportFormat, ...] = (),
    report_path: str | Path | None = None,
    quality_report_path: str | Path | None = None,
    pronunciation_dictionary: str | Path | None = None,
) -> BatchAlignmentResult:
    """Align explicit WAV/TXT pairs listed in a UTF-8 CSV manifest."""
    source = Path(manifest).expanduser().resolve()
    requested_language = normalize_language(lang)
    entries = read_manifest(source, lang=requested_language)
    invalid: list[str] = []
    for entry in entries:
        try:
            validate_explicit_pair(entry.pair.audio, entry.pair.transcript)
        except PairingError as error:
            invalid.append(f"line {entry.line}: {error}")
    if invalid:
        raise PairingError("Invalid manifest inputs:\n" + "\n".join(invalid))

    dictionary = (
        load_pronunciation_dictionary(pronunciation_dictionary)
        if pronunciation_dictionary is not None else None
    )
    destination = Path(output_dir).expanduser().resolve() if output_dir else source.parent / "aligned"
    protected_inputs = (source,) + tuple(
        path for entry in entries for path in (entry.pair.audio, entry.pair.transcript)
    )
    if dictionary is not None:
        protected_inputs += (dictionary.source,)
    _protect_inputs_and_outputs(entries, destination, exports, protected_inputs)

    pairs: list[InputPair] = []
    failures: list[AlignmentFailure] = []
    for entry in entries:
        pair = entry.pair
        try:
            language = detect_language(pair.transcript) if pair.language == "auto" else pair.language
        except PairingError as error:
            failures.append(AlignmentFailure(pair.audio, pair.transcript, "auto", str(error)))
            continue
        pairs.append(InputPair(pair.audio, pair.transcript, pair.relative_stem, language))
    return align_pairs(
        tuple(pairs),
        destination,
        kaldi_dir,
        num_jobs,
        word_tier,
        phone_tier,
        keep_workdir,
        progress,
        tuple(failures),
        existing=existing,
        exports=exports,
        report_path=report_path,
        quality_report_path=quality_report_path,
        input_root=source.parent,
        requested_language=requested_language,
        protected_inputs=protected_inputs,
        pronunciation_dictionary=dictionary,
        romanization_tier=romanization_tier,
    )


def _protect_inputs_and_outputs(
    entries: tuple[ManifestEntry, ...],
    destination: Path,
    exports: tuple[ExportFormat, ...],
    protected_inputs: tuple[Path, ...],
) -> None:
    """Reject collisions before any output directory or engine work begins."""
    protected_keys = {_portable_path_key(path) for path in protected_inputs}
    planned = output_paths(plan_outputs(tuple(entry.pair for entry in entries), destination, exports))
    planned_keys = {_portable_path_key(path.resolve()) for path in planned}
    for path in planned:
        if _portable_path_key(path.resolve()) in protected_keys:
            raise PairingError(f"Manifest output would overwrite an input file: {path}")
        if any(_portable_path_key(parent.resolve()) in protected_keys for parent in path.parents):
            raise PairingError(f"Manifest output would use an input file as a directory: {path}")
        if any(_portable_path_key(parent.resolve()) in planned_keys for parent in path.parents):
            raise PairingError(f"Manifest outputs conflict at a file/directory path: {path}")
