"""Public Python API for KoreanFA."""

from ._version import __version__
from .aligner import Aligner
from .api import align, align_directory, discover_pairs
from .engine import ensure_installed
from .engine import install as install_engine
from .errors import AlignmentError, EngineNotFoundError, EngineUnavailableError, KoreanFAError, PairingError
from .fa import align_directory_files, align_file
from .result import (
    AlignmentFailure,
    AlignmentInterval,
    AlignmentOutputs,
    AlignmentReport,
    AlignmentResult,
    AlignmentSkip,
    AlignmentSummary,
    BatchAlignmentResult,
    ExistingOutputPolicy,
    ExportFormat,
    InputPair,
    QualityReport,
    QualitySummary,
)
from .validation import ValidatedPair, ValidationIssue, ValidationReport, validate

__all__ = [
    "align",
    "align_directory",
    "align_directory_files",
    "align_file",
    "Aligner",
    "discover_pairs",
    "AlignmentError",
    "AlignmentFailure",
    "AlignmentInterval",
    "AlignmentOutputs",
    "AlignmentReport",
    "AlignmentResult",
    "AlignmentSkip",
    "AlignmentSummary",
    "BatchAlignmentResult",
    "EngineNotFoundError",
    "EngineUnavailableError",
    "ExistingOutputPolicy",
    "ExportFormat",
    "InputPair",
    "KoreanFAError",
    "PairingError",
    "QualityReport",
    "QualitySummary",
    "ensure_installed",
    "install_engine",
    "validate",
    "ValidatedPair",
    "ValidationIssue",
    "ValidationReport",
    "__version__",
]
