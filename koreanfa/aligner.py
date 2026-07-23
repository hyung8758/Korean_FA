"""The primary high-level KoreanFA interface."""

from __future__ import annotations

from pathlib import Path

from .api import align, align_directory
from .language import normalize_language
from .result import AlignmentResult, BatchAlignmentResult


class Aligner:
    """Align files or corpus directories using ``lang='auto'`` by default."""

    def __init__(self, *, lang: str = "auto", kaldi_dir: str | Path | None = None, num_jobs: int = 1) -> None:
        self.lang = normalize_language(lang)
        self.kaldi_dir = kaldi_dir
        self.num_jobs = num_jobs

    def align(
        self, input_path: str | Path, transcript: str | Path | None = None, **options: object
    ) -> AlignmentResult | BatchAlignmentResult:
        path = Path(input_path)
        common = {"lang": self.lang, "kaldi_dir": self.kaldi_dir, "num_jobs": self.num_jobs} | options
        if path.is_dir():
            if transcript is not None:
                raise ValueError("A directory input discovers its own WAV/TXT pairs; do not pass transcript.")
            return align_directory(path, **common)
        if transcript is None:
            raise ValueError("A WAV input requires its matching TXT transcript.")
        common.pop("recursive", None)
        common.pop("strict", None)
        return align(path, transcript, **common)
