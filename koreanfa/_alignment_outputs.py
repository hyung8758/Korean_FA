"""Plan, stage, and atomically publish alignment output sets."""

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from stat import S_IMODE

from .errors import AlignmentError
from .formats import ParsedAlignment, parse_textgrid, planned_export_paths, require_tiers, write_exports
from .pairing import _textgrid_relative_path
from .result import (
    _ALIGNMENT_EXPORT_FIELDS,
    AlignmentFailure,
    AlignmentOutputs,
    AlignmentResult,
    AlignmentSkip,
    ExportFormat,
    InputPair,
)


@dataclass(frozen=True)
class OutputPlan:
    """Every destination associated with one input pair."""

    pair: InputPair
    outputs: AlignmentOutputs


def plan_outputs(
    pairs: tuple[InputPair, ...], output_dir: Path, exports: tuple[ExportFormat, ...]
) -> tuple[OutputPlan, ...]:
    """Calculate all public output paths without writing files."""
    return tuple(
        OutputPlan(
            pair,
            planned_export_paths(output_dir / _textgrid_relative_path(pair.relative_stem), exports),
        )
        for pair in pairs
    )


def output_paths(plans: tuple[OutputPlan, ...]) -> tuple[Path, ...]:
    """Flatten planned paths in deterministic pair and format order."""
    return tuple(
        path
        for plan in plans
        for path in (plan.outputs.textgrid, *(getattr(plan.outputs, name) for name in _ALIGNMENT_EXPORT_FIELDS))
        if path is not None
    )


def require_writable_destinations(paths: tuple[Path, ...]) -> None:
    """Reject directories and other non-file objects before alignment starts."""
    invalid = next((path for path in paths if path.exists() and not path.is_file()), None)
    if invalid is not None:
        raise AlignmentError(f"Output path exists but is not a file: {invalid}", work_dir=None)


def reject_existing_outputs(paths: tuple[Path, ...], output_dir: Path) -> None:
    """Implement ``existing='error'`` before any expensive runtime work."""
    conflicts = [path for path in paths if path.exists()]
    if not conflicts:
        return
    displayed = ", ".join(str(path.relative_to(output_dir)) for path in conflicts[:5])
    suffix = " ..." if len(conflicts) > 5 else ""
    raise AlignmentError(f"Output already exists ({len(conflicts)}): {displayed}{suffix}", work_dir=None)


def partition_skipped_outputs(
    plans: tuple[OutputPlan, ...],
    output_dir: Path,
    exports: tuple[ExportFormat, ...],
    *,
    word_tier: bool,
    phone_tier: bool,
) -> tuple[tuple[InputPair, ...], tuple[AlignmentSkip, ...], tuple[AlignmentFailure, ...]]:
    """Reuse valid TextGrids and transactionally generate requested exports."""
    retained: list[InputPair] = []
    skipped: list[AlignmentSkip] = []
    failures: list[AlignmentFailure] = []
    for plan in plans:
        textgrid = plan.outputs.textgrid
        try:
            parsed = parse_textgrid(textgrid)
            require_tiers(parsed, word_tier=word_tier, phone_tier=phone_tier)
        except AlignmentError:
            retained.append(plan.pair)
            continue
        try:
            _publish_skipped_exports(plan, parsed, output_dir, exports)
        except (AlignmentError, OSError, ValueError) as error:
            failures.append(
                AlignmentFailure(
                    plan.pair.audio,
                    plan.pair.transcript,
                    plan.pair.language,
                    f"Could not publish exports for skipped output: {error}",
                )
            )
            continue
        skipped.append(
            AlignmentSkip(
                plan.pair.audio,
                plan.pair.transcript,
                textgrid,
                plan.pair.language,
                duration=parsed.duration,
                words=parsed.words,
                phones=parsed.phones,
                outputs=plan.outputs,
            )
        )
    return tuple(retained), tuple(skipped), tuple(failures)


def _publish_skipped_exports(
    plan: OutputPlan,
    parsed: ParsedAlignment,
    output_dir: Path,
    exports: tuple[ExportFormat, ...],
) -> None:
    with tempfile.TemporaryDirectory(prefix=".koreanfa-skip-", dir=output_dir) as temporary:
        staged_textgrid = Path(temporary) / _textgrid_relative_path(plan.pair.relative_stem)
        staged = write_exports(
            staged_textgrid,
            parsed,
            exports,
            audio=plan.pair.audio,
            transcript=plan.pair.transcript,
            language=plan.pair.language,
            relative_stem=plan.pair.relative_stem,
        )
        files = tuple(
            (source, destination)
            for name in _ALIGNMENT_EXPORT_FIELDS
            if (source := getattr(staged, name)) is not None
            and (destination := getattr(plan.outputs, name)) is not None
        )
        if files:
            publish_output_set(files, output_dir=output_dir)


def prepare_and_publish(
    results: list[AlignmentResult],
    staging_output: Path,
    output_dir: Path,
    exports: tuple[ExportFormat, ...],
    *,
    word_tier: bool,
    phone_tier: bool,
) -> tuple[list[AlignmentResult], list[AlignmentFailure]]:
    """Parse staged TextGrids and publish each valid pair as one transaction."""
    published: list[AlignmentResult] = []
    failures: list[AlignmentFailure] = []
    for result in results:
        try:
            parsed = parse_textgrid(result.textgrid)
            require_tiers(parsed, word_tier=word_tier, phone_tier=phone_tier)
            relative = result.textgrid.relative_to(staging_output)
            relative_stem = relative.parent / relative.name.removesuffix(".TextGrid")
            staged = write_exports(
                result.textgrid,
                parsed,
                exports,
                audio=result.audio,
                transcript=result.transcript,
                language=result.language,
                relative_stem=relative_stem,
            )
        except (AlignmentError, OSError, ValueError) as error:
            reason = str(error).replace(str(staging_output), "<staging>")
            failures.append(
                AlignmentFailure(
                    result.audio,
                    result.transcript,
                    result.language,
                    f"Could not prepare alignment outputs: {reason}",
                    result.work_dir,
                    result.attempts,
                )
            )
            continue
        try:
            final_outputs = _publish_staged_outputs(staged, staging_output, output_dir)
        except OSError as error:
            reason = str(error).replace(str(staging_output), "<staging>")
            failures.append(
                AlignmentFailure(
                    result.audio,
                    result.transcript,
                    result.language,
                    f"Could not publish alignment outputs: {reason}",
                    result.work_dir,
                    result.attempts,
                )
            )
            continue
        published.append(
            AlignmentResult(
                result.audio,
                result.transcript,
                final_outputs.textgrid,
                result.language,
                result.work_dir,
                parsed.duration,
                parsed.words,
                parsed.phones,
                result.attempts,
                final_outputs,
            )
        )
    return published, failures


def _publish_staged_outputs(
    staged: AlignmentOutputs, staging_output: Path, output_dir: Path
) -> AlignmentOutputs:
    destinations: dict[str, Path | None] = {}
    files: list[tuple[Path, Path]] = []
    for name in _ALIGNMENT_EXPORT_FIELDS:
        source = getattr(staged, name)
        destination = output_dir / source.relative_to(staging_output) if source is not None else None
        destinations[name] = destination
        if source is not None and destination is not None:
            files.append((source, destination))
    textgrid = output_dir / staged.textgrid.relative_to(staging_output)
    files.append((staged.textgrid, textgrid))
    publish_output_set(tuple(files), output_dir=output_dir)
    return AlignmentOutputs(textgrid, **destinations)


def publish_file(source: Path, destination: Path) -> None:
    """Atomically replace one output while preserving an existing mode."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        previous_mode = S_IMODE(destination.stat().st_mode) if destination.is_file() else None
        shutil.copy2(source, temporary)
        if previous_mode is not None:
            temporary.chmod(previous_mode)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def publish_output_set(files: tuple[tuple[Path, Path], ...], *, output_dir: Path) -> None:
    """Publish one pair's files together, restoring prior outputs on failure."""
    backup_root = Path(tempfile.mkdtemp(prefix=".koreanfa-rollback-", dir=output_dir))
    backups: dict[Path, Path | None] = {}
    published: list[Path] = []
    try:
        for index, (_, destination) in enumerate(files):
            if destination.exists():
                if not destination.is_file():
                    raise OSError(f"Output path exists but is not a file: {destination}")
                backup = backup_root / f"{index:04d}"
                shutil.copy2(destination, backup)
                backups[destination] = backup
            else:
                backups[destination] = None
        for source, destination in files:
            publish_file(source, destination)
            published.append(destination)
    except BaseException as error:
        _restore_outputs(published, backups, error)
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)


def _restore_outputs(
    published: list[Path], backups: dict[Path, Path | None], publish_error: BaseException
) -> None:
    rollback_errors: list[str] = []
    for destination in reversed(published):
        try:
            backup = backups[destination]
            if backup is None:
                destination.unlink(missing_ok=True)
            else:
                publish_file(backup, destination)
        except OSError as error:  # pragma: no cover - requires repeated filesystem failure
            rollback_errors.append(f"{destination}: {error}")
    if rollback_errors:
        raise AlignmentError(
            "Could not restore outputs after a publish failure: " + "; ".join(rollback_errors),
            work_dir=None,
        ) from publish_error
