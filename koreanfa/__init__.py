"""Public Python API for KoreanFA."""

from .aligner import Aligner
from .api import align, align_directory, discover_pairs
from .errors import AlignmentError, EngineNotFoundError, KoreanFAError, PairingError
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
    "InputPair",
    "KoreanFAError",
    "PairingError",
]

__version__ = "0.2.0"
