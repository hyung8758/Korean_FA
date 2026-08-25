"""Validated options shared by alignment execution and reports."""

from dataclasses import dataclass

from .pronunciation import PronunciationDictionary
from .result import ExistingOutputPolicy, ExportFormat


@dataclass(frozen=True)
class WorkflowOptions:
    existing: ExistingOutputPolicy
    exports: tuple[ExportFormat, ...]
    num_jobs: int
    threads_per_job: int
    word_tier: bool
    phone_tier: bool
    romanization_tier: bool
    keep_workdir: bool
    requested_language: str
    recursive: bool
    ignore_unmatched: bool
    pronunciation_dictionary: PronunciationDictionary | None

    def report_values(self) -> dict[str, object]:
        """Return the stable subset recorded in execution reports."""
        return {
            "existing": self.existing,
            "exports": list(self.exports),
            "num_jobs": self.num_jobs,
            "threads_per_job": self.threads_per_job,
            "word_tier": self.word_tier,
            "phone_tier": self.phone_tier,
            "romanization_tier": self.romanization_tier,
            "keep_workdir": self.keep_workdir,
            "language": self.requested_language,
            "recursive": self.recursive,
            "ignore_unmatched": self.ignore_unmatched,
            "pronunciation_dictionary": self.pronunciation_dictionary is not None,
        }


def normalize_workflow_options(
    existing: ExistingOutputPolicy,
    exports: tuple[ExportFormat, ...],
    num_jobs: int,
    threads_per_job: int,
    word_tier: bool,
    phone_tier: bool,
    keep_workdir: bool,
    requested_language: str,
    recursive: bool,
    ignore_unmatched: bool,
    pronunciation_dictionary: PronunciationDictionary | None,
    romanization_tier: bool = False,
) -> WorkflowOptions:
    """Validate user options once before filesystem or engine work."""
    if num_jobs < 1:
        raise ValueError("num_jobs must be at least 1")
    if threads_per_job < 1:
        raise ValueError("threads_per_job must be at least 1")
    if not word_tier and not phone_tier:
        raise ValueError("At least one of word_tier or phone_tier must be enabled")
    if existing not in {"overwrite", "skip", "error"}:
        raise ValueError("existing must be one of: overwrite, skip, error")
    normalized_exports = tuple(dict.fromkeys(exports))
    if any(value not in {"json", "csv", "ctm"} for value in normalized_exports):
        raise ValueError("exports must contain only: json, csv, ctm")
    return WorkflowOptions(
        existing,
        normalized_exports,
        num_jobs,
        threads_per_job,
        word_tier,
        phone_tier,
        romanization_tier,
        keep_workdir,
        requested_language,
        recursive,
        ignore_unmatched,
        pronunciation_dictionary,
    )
