"""Public Python API for KoreanFA."""

from ._version import __version__
from .aligner import Aligner
from .api import align, align_directory, discover_pairs
from .engine import ensure_installed
from .engine import install as install_engine
from .errors import AlignmentError, EngineNotFoundError, EngineUnavailableError, KoreanFAError, PairingError
from .fa import align_directory_files, align_file
from .result import AlignmentFailure, AlignmentResult, BatchAlignmentResult, InputPair

__all__ = [
    "align",
    "align_directory",
    "align_directory_files",
    "align_file",
    "Aligner",
    "discover_pairs",
    "AlignmentError",
    "AlignmentFailure",
    "AlignmentResult",
    "BatchAlignmentResult",
    "EngineNotFoundError",
    "EngineUnavailableError",
    "InputPair",
    "KoreanFAError",
    "PairingError",
    "ensure_installed",
    "install_engine",
    "__version__",
]
