"""The primary high-level KoreanFA interface."""

from pathlib import Path
from typing import overload

from .api import DEFAULT_NUM_JOBS, align, align_directory
from .language import normalize_language
from .result import (
    AlignmentResult,
    AlignmentSkip,
    BatchAlignmentResult,
    ExistingOutputPolicy,
    ExportFormat,
    ProgressCallback,
)


class Aligner:
    """Align files or corpus directories using ``lang='auto'`` by default."""

    def __init__(
        self, *, lang: str = "auto", kaldi_dir: str | Path | None = None, num_jobs: int = DEFAULT_NUM_JOBS
    ) -> None:
        self.lang = normalize_language(lang)
        self.kaldi_dir = kaldi_dir
        self.num_jobs = num_jobs

    @overload
    def align(
        self,
        input_path: str | Path,
        transcript: str | Path,
        *,
        lang: str | None = None,
        output_dir: str | Path | None = None,
        kaldi_dir: str | Path | None = None,
        num_jobs: int | None = None,
        recursive: bool = False,
        ignore_unmatched: bool = True,
        word_tier: bool = True,
        phone_tier: bool = True,
        keep_workdir: bool = False,
        progress: ProgressCallback | None = None,
        existing: ExistingOutputPolicy = "overwrite",
        exports: tuple[ExportFormat, ...] = (),
        report_path: str | Path | None = None,
    ) -> AlignmentResult | AlignmentSkip: ...

    @overload
    def align(
        self,
        input_path: str | Path,
        transcript: None = None,
        *,
        lang: str | None = None,
        output_dir: str | Path | None = None,
        kaldi_dir: str | Path | None = None,
        num_jobs: int | None = None,
        recursive: bool = False,
        ignore_unmatched: bool = True,
        word_tier: bool = True,
        phone_tier: bool = True,
        keep_workdir: bool = False,
        progress: ProgressCallback | None = None,
        existing: ExistingOutputPolicy = "overwrite",
        exports: tuple[ExportFormat, ...] = (),
        report_path: str | Path | None = None,
    ) -> BatchAlignmentResult: ...

    def align(
        self,
        input_path: str | Path,
        transcript: str | Path | None = None,
        *,
        lang: str | None = None,
        output_dir: str | Path | None = None,
        kaldi_dir: str | Path | None = None,
        num_jobs: int | None = None,
        recursive: bool = False,
        ignore_unmatched: bool = True,
        word_tier: bool = True,
        phone_tier: bool = True,
        keep_workdir: bool = False,
        progress: ProgressCallback | None = None,
        existing: ExistingOutputPolicy = "overwrite",
        exports: tuple[ExportFormat, ...] = (),
        report_path: str | Path | None = None,
    ) -> AlignmentResult | AlignmentSkip | BatchAlignmentResult:
        """Align one WAV/TXT pair or every discovered pair in a directory.

        Values configured on the instance remain the defaults. ``lang``,
        ``kaldi_dir``, and ``num_jobs`` may be overridden for one call.
        Directory-only options are ignored for a single WAV/TXT pair, matching
        the historical ``**options`` behavior.
        """
        path = Path(input_path)
        effective_lang = self.lang if lang is None else normalize_language(lang)
        effective_kaldi_dir = self.kaldi_dir if kaldi_dir is None else kaldi_dir
        effective_num_jobs = self.num_jobs if num_jobs is None else num_jobs
        if path.is_dir():
            if transcript is not None:
                raise ValueError("A directory input discovers its own WAV/TXT pairs; do not pass transcript.")
            return align_directory(
                path,
                lang=effective_lang,
                output_dir=output_dir,
                kaldi_dir=effective_kaldi_dir,
                num_jobs=effective_num_jobs,
                recursive=recursive,
                ignore_unmatched=ignore_unmatched,
                word_tier=word_tier,
                phone_tier=phone_tier,
                keep_workdir=keep_workdir,
                progress=progress,
                existing=existing,
                exports=exports,
                report_path=report_path,
            )
        if transcript is None:
            raise ValueError("A WAV input requires its matching TXT transcript.")
        return align(
            path,
            transcript,
            lang=effective_lang,
            output_dir=output_dir,
            kaldi_dir=effective_kaldi_dir,
            num_jobs=effective_num_jobs,
            word_tier=word_tier,
            phone_tier=phone_tier,
            keep_workdir=keep_workdir,
            progress=progress,
            existing=existing,
            exports=exports,
            report_path=report_path,
        )
