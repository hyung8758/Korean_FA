"""Batch alignment policy and orchestration."""

import os
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from ._alignment_outputs import (
    output_paths,
    partition_skipped_outputs,
    plan_outputs,
    prepare_and_publish,
    reject_existing_outputs,
    require_writable_destinations,
)
from ._alignment_runtime import run_language_group
from ._io import report_output_path
from ._kaldi import resolve_kaldi_dir
from ._workflow_options import WorkflowOptions, normalize_workflow_options
from .errors import PairingError
from .pairing import _portable_path_key
from .reporting import write_execution_report
from .resources import runtime_root
from .result import (
    AlignmentFailure,
    AlignmentResult,
    AlignmentSkip,
    AlignmentSummary,
    BatchAlignmentResult,
    ExistingOutputPolicy,
    ExportFormat,
    InputPair,
    ProgressCallback,
)


def align_pairs(
    pairs: tuple[InputPair, ...],
    output_dir: Path,
    kaldi_dir: str | Path | None,
    num_jobs: int,
    word_tier: bool,
    phone_tier: bool,
    keep_workdir: bool,
    progress: ProgressCallback | None,
    initial_failures: tuple[AlignmentFailure, ...] = (),
    *,
    existing: ExistingOutputPolicy = "overwrite",
    exports: tuple[ExportFormat, ...] = (),
    report_path: str | Path | None = None,
    input_root: Path | None = None,
    requested_language: str = "auto",
    recursive: bool = False,
    ignore_unmatched: bool = True,
    protected_inputs: tuple[Path, ...] = (),
) -> BatchAlignmentResult:
    """Apply output policy, execute language groups, and publish one batch."""
    started_at = time.monotonic()
    options = normalize_workflow_options(
        existing,
        exports,
        num_jobs,
        word_tier,
        phone_tier,
        keep_workdir,
        requested_language,
        recursive,
        ignore_unmatched,
    )
    if not pairs and not initial_failures:
        raise PairingError("No alignable WAV/TXT pairs were found.")
    output_dir.mkdir(parents=True, exist_ok=True)
    plans = plan_outputs(pairs, output_dir, options.exports)
    planned_paths = output_paths(plans)
    require_writable_destinations(planned_paths)
    _protect_report(report_path, pairs, initial_failures, protected_inputs, planned_paths)
    if options.existing == "error":
        reject_existing_outputs(planned_paths, output_dir)

    skipped: tuple[AlignmentSkip, ...] = ()
    if options.existing == "skip":
        pairs, skipped, skip_failures = partition_skipped_outputs(
            plans,
            output_dir,
            options.exports,
            word_tier=word_tier,
            phone_tier=phone_tier,
        )
        initial_failures += skip_failures
    if not pairs:
        return _finish_batch(
            (),
            initial_failures,
            skipped,
            output_dir,
            None,
            started_at,
            progress,
            report_path,
            input_root,
            kaldi_dir,
            options,
            emit_items=True,
        )
    return _execute_batch(
        pairs,
        initial_failures,
        skipped,
        output_dir,
        kaldi_dir,
        started_at,
        progress,
        report_path,
        input_root,
        options,
    )


def _protect_report(
    report_path: str | Path | None,
    pairs: tuple[InputPair, ...],
    failures: tuple[AlignmentFailure, ...],
    protected_inputs: tuple[Path, ...],
    planned_outputs: tuple[Path, ...],
) -> None:
    if report_path is None:
        return
    destination = report_output_path(report_path)
    inputs = {path.resolve() for pair in pairs for path in (pair.audio, pair.transcript)}
    inputs.update(path.resolve() for path in protected_inputs)
    inputs.update(path.resolve() for failure in failures for path in (failure.audio, failure.transcript))
    protected = inputs | {path.resolve() for path in planned_outputs}
    if _portable_path_key(destination) in {_portable_path_key(path) for path in protected}:
        raise ValueError("report_path must not overwrite an input or alignment output file")


def _execute_batch(
    pairs: tuple[InputPair, ...],
    failures: tuple[AlignmentFailure, ...],
    skipped: tuple[AlignmentSkip, ...],
    output_dir: Path,
    kaldi_dir: str | Path | None,
    started_at: float,
    progress: ProgressCallback | None,
    report_path: str | Path | None,
    input_root: Path | None,
    options: WorkflowOptions,
) -> BatchAlignmentResult:
    runtime, engine_env = resolve_kaldi_dir(kaldi_dir)
    resources = runtime_root()
    staging_output = Path(tempfile.mkdtemp(prefix=".koreanfa-output-", dir=output_dir))
    diagnostics_root = Path(tempfile.mkdtemp(prefix="koreanfa-batch-")) if options.keep_workdir else None
    raw_results: list[AlignmentResult] = []
    all_failures = list(failures)
    total = len(pairs) + len(failures) + len(skipped)
    _emit_initial_progress(failures, skipped, total, progress)
    try:
        grouped: dict[str, list[InputPair]] = defaultdict(list)
        for pair in pairs:
            grouped[pair.language].append(pair)
        completed_before = len(failures) + len(skipped)
        for language, group in grouped.items():
            results, group_failures, _ = run_language_group(
                tuple(group),
                language,
                staging_output,
                runtime,
                engine_env,
                resources,
                options.num_jobs,
                options.word_tier,
                options.phone_tier,
                options.keep_workdir,
                progress,
                completed_before,
                total,
                diagnostics_root,
            )
            raw_results.extend(results)
            all_failures.extend(group_failures)
            completed_before += len(group)
        results, output_failures = prepare_and_publish(
            raw_results,
            staging_output,
            output_dir,
            options.exports,
            word_tier=options.word_tier,
            phone_tier=options.phone_tier,
        )
        all_failures.extend(output_failures)
        return _finish_batch(
            tuple(results),
            tuple(all_failures),
            skipped,
            output_dir,
            diagnostics_root,
            started_at,
            progress,
            report_path,
            input_root,
            kaldi_dir,
            options,
            emit_items=False,
        )
    finally:
        shutil.rmtree(staging_output, ignore_errors=True)


def _finish_batch(
    results: tuple[AlignmentResult, ...],
    failures: tuple[AlignmentFailure, ...],
    skipped: tuple[AlignmentSkip, ...],
    output_dir: Path,
    work_dir: Path | None,
    started_at: float,
    progress: ProgressCallback | None,
    report_path: str | Path | None,
    input_root: Path | None,
    kaldi_dir: str | Path | None,
    options: WorkflowOptions,
    *,
    emit_items: bool,
) -> BatchAlignmentResult:
    results = tuple(sorted(results, key=lambda item: str(item.audio)))
    failures = tuple(sorted(failures, key=lambda item: str(item.audio)))
    skipped = tuple(sorted(skipped, key=lambda item: str(item.audio)))
    total = len(results) + len(failures) + len(skipped)
    summary = AlignmentSummary(total, len(results), len(failures), len(skipped), time.monotonic() - started_at)
    if progress:
        if emit_items:
            _emit_initial_progress(failures, skipped, total, progress)
        progress(
            "summary", total, total,
            f"total={total} success={len(results)} failed={len(failures)} skipped={len(skipped)}",
        )
    report = None
    if report_path is not None:
        report = write_execution_report(
            report_path,
            input_root=input_root or output_dir,
            output_dir=output_dir,
            results=results,
            failures=failures,
            skipped=skipped,
            summary=summary,
            options=options.report_values(),
            engine_source="external" if kaldi_dir or os.environ.get("KOREANFA_KALDI_DIR") else "managed",
        )
    return BatchAlignmentResult(results, output_dir, work_dir, failures, skipped, summary, report)


def _emit_initial_progress(
    failures: tuple[AlignmentFailure, ...],
    skipped: tuple[AlignmentSkip, ...],
    total: int,
    progress: ProgressCallback | None,
) -> None:
    if progress is None:
        return
    for index, failure in enumerate(failures, start=1):
        progress("failed", index, total, f"{failure.audio.name} ({failure.reason})")
    for index, item in enumerate(skipped, start=len(failures) + 1):
        progress("skipped", index, total, f"{item.audio.name} ({item.reason})")
