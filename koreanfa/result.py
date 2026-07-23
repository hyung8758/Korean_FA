"""Structured values returned by the public alignment API."""

from __future__ import annotations

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
class BatchAlignmentResult:
    """Results from one directory-level Kaldi invocation."""

    results: tuple[AlignmentResult, ...]
    output_dir: Path
    work_dir: Path | None = None
