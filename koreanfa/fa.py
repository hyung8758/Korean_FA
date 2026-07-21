"""Focused forced-alignment functions for file and directory inputs."""

from __future__ import annotations

from pathlib import Path

from .api import align, align_directory
from .result import AlignmentResult, BatchAlignmentResult


def align_file(audio: str | Path, transcript: str | Path, **options: object) -> AlignmentResult:
    """Force-align one WAV/TXT pair and return its TextGrid result."""
    return align(audio, transcript, **options)


def align_directory_files(directory: str | Path, **options: object) -> BatchAlignmentResult:
    """Force-align every automatically discovered WAV/TXT pair in a directory."""
    return align_directory(directory, **options)


# A concise alias for users who prefer ``fa.directory(...)``.
directory = align_directory_files
