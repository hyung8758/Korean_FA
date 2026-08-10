"""Focused forced-alignment functions for file and directory inputs."""

from pathlib import Path

from .api import DEFAULT_NUM_JOBS, ProgressCallback, align, align_directory
from .result import AlignmentResult, BatchAlignmentResult


def align_file(
    audio: str | Path,
    transcript: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = DEFAULT_NUM_JOBS,
    word_tier: bool = True,
    phone_tier: bool = True,
    keep_workdir: bool = False,
    progress: ProgressCallback | None = None,
) -> AlignmentResult:
    """Force-align one WAV/TXT pair and return its TextGrid result."""
    return align(
        audio,
        transcript,
        lang=lang,
        output_dir=output_dir,
        kaldi_dir=kaldi_dir,
        num_jobs=num_jobs,
        word_tier=word_tier,
        phone_tier=phone_tier,
        keep_workdir=keep_workdir,
        progress=progress,
    )


def align_directory_files(
    directory: str | Path,
    *,
    lang: str = "auto",
    output_dir: str | Path | None = None,
    kaldi_dir: str | Path | None = None,
    num_jobs: int = DEFAULT_NUM_JOBS,
    recursive: bool = False,
    ignore_unmatched: bool = True,
    word_tier: bool = True,
    phone_tier: bool = True,
    keep_workdir: bool = False,
    progress: ProgressCallback | None = None,
) -> BatchAlignmentResult:
    """Force-align every automatically discovered WAV/TXT pair in a directory."""
    return align_directory(
        directory,
        lang=lang,
        output_dir=output_dir,
        kaldi_dir=kaldi_dir,
        num_jobs=num_jobs,
        recursive=recursive,
        ignore_unmatched=ignore_unmatched,
        word_tier=word_tier,
        phone_tier=phone_tier,
        keep_workdir=keep_workdir,
        progress=progress,
    )


# A concise alias for users who prefer ``fa.directory(...)``.
directory = align_directory_files

__all__ = ["align_file", "align_directory_files", "directory"]
