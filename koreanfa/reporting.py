"""Stable JSON execution reports for corpus automation."""

import json
from collections.abc import Callable
from pathlib import Path

from ._io import atomic_write_text, report_output_path
from ._version import __version__
from .engine import status as engine_status
from .errors import KoreanFAError
from .result import (
    _ALIGNMENT_EXPORT_FIELDS,
    AlignmentFailure,
    AlignmentOutputs,
    AlignmentReport,
    AlignmentResult,
    AlignmentSkip,
    AlignmentSummary,
)


def _output_values(
    textgrid: Path,
    outputs: AlignmentOutputs | None,
    relative_path: Callable[[Path], str],
) -> dict[str, str]:
    values = {"textgrid": relative_path(textgrid)}
    if outputs is not None:
        for name in _ALIGNMENT_EXPORT_FIELDS:
            if (path := getattr(outputs, name)) is not None:
                values[name] = relative_path(path)
    return values


def write_execution_report(
    destination: str | Path,
    *,
    input_root: Path,
    output_dir: Path,
    results: tuple[AlignmentResult, ...],
    failures: tuple[AlignmentFailure, ...],
    skipped: tuple[AlignmentSkip, ...],
    summary: AlignmentSummary,
    options: dict[str, object],
    engine_source: str,
) -> AlignmentReport:
    """Write one atomic, relative-path-only alignment report."""
    path = report_output_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    def input_path(value: Path) -> str:
        try:
            return value.absolute().relative_to(input_root.resolve()).as_posix()
        except ValueError:
            return value.name

    def output_path(value: Path) -> str:
        try:
            return value.absolute().relative_to(output_dir.resolve()).as_posix()
        except ValueError:
            return value.name

    engine: dict[str, object] = {"source": engine_source, "installed": None, "platform": None, "version": None}
    if engine_source == "managed":
        try:
            state = engine_status()
            engine.update(installed=state.installed, platform=state.platform, version=state.version)
        except KoreanFAError:
            pass

    def safe_reason(failure: AlignmentFailure) -> str:
        reason = failure.reason
        replacements = {
            input_root.resolve(): ".",
            output_dir.resolve(): ".",
            failure.audio.resolve(): input_path(failure.audio),
            failure.transcript.resolve(): input_path(failure.transcript),
        }
        if failure.work_dir is not None:
            replacements[failure.work_dir.resolve()] = "<diagnostics>"
        for source, replacement in sorted(replacements.items(), key=lambda item: len(str(item[0])), reverse=True):
            reason = reason.replace(str(source), replacement)
        return reason

    items: list[dict[str, object]] = []
    for result in results:
        items.append(
            {
                "audio": input_path(result.audio),
                "transcript": input_path(result.transcript),
                "language": result.language,
                "status": "succeeded",
                "attempts": result.attempts,
                "duration": result.duration,
                "outputs": _output_values(result.textgrid, result.outputs, output_path),
            }
        )
    for failure in failures:
        items.append(
            {
                "audio": input_path(failure.audio),
                "transcript": input_path(failure.transcript),
                "language": failure.language,
                "status": "failed",
                "reason": safe_reason(failure),
                "attempts": failure.attempts,
                "outputs": {},
            }
        )
    for item in skipped:
        items.append(
            {
                "audio": input_path(item.audio),
                "transcript": input_path(item.transcript),
                "language": item.language,
                "status": "skipped",
                "reason": item.reason,
                "attempts": 0,
                "duration": item.duration,
                "outputs": _output_values(item.textgrid, item.outputs, output_path),
            }
        )
    items.sort(key=lambda item: (str(item["audio"]), str(item["status"])))
    payload = {
        "schema_version": 1,
        "koreanfa_version": __version__,
        "engine": engine,
        "options": options,
        "summary": {
            "total": summary.total,
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "elapsed_seconds": round(summary.elapsed_seconds, 6),
        },
        "items": items,
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return AlignmentReport(path, 1, summary)
