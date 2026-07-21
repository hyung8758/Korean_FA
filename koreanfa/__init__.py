"""Public Python API for KoreanFA."""

from .aligner import Aligner
from .api import align, align_directory, discover_pairs
from .engine import ensure_installed, install as install_engine
from .errors import AlignmentError, EngineNotFoundError, EngineUnavailableError, KoreanFAError, PairingError
from .result import AlignmentResult, BatchAlignmentResult, InputPair

__all__ = [
    "align",
    "align_directory",
    "Aligner",
    "discover_pairs",
    "AlignmentError",
    "AlignmentResult",
    "BatchAlignmentResult",
    "EngineNotFoundError",
    "EngineUnavailableError",
    "InputPair",
    "KoreanFAError",
    "PairingError",
    "ensure_installed",
    "install_engine",
]

__version__ = "0.3.0"
