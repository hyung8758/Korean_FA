"""Structured values returned by the public alignment API."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputPair:
    """A WAV file and its matching UTF-8 text transcription."""

    audio: Path
    transcript: Path
    relative_stem: Path
    language: str = "auto"


@dataclass(frozen=True)
class AlignmentResult:
    """One successfully aligned WAV/TXT pair."""

    audio: Path
    transcript: Path
    textgrid: Path
    language: str
    work_dir: Path | None = None


@dataclass(frozen=True)
class AlignmentFailure:
    """One input pair that the runtime rejected without aborting its batch."""

    audio: Path
    transcript: Path
    language: str
    reason: str
    work_dir: Path | None = None


@dataclass(frozen=True)
class BatchAlignmentResult:
    """Successful results and controlled per-file failures from one batch."""

    results: tuple[AlignmentResult, ...]
    output_dir: Path
    work_dir: Path | None = None
    failures: tuple[AlignmentFailure, ...] = ()
