"""Optional real-Kaldi smoke tests.

Run these after setting KOREANFA_KALDI_DIR to a compiled Kaldi checkout or to
the future bundled KoreanFA engine.  They are intentionally skipped on normal
Python-only test runs.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from koreanfa import align_directory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
KALDI_DIR = os.environ.get("KOREANFA_KALDI_DIR")


@pytest.mark.skipif(not KALDI_DIR, reason="requires KOREANFA_KALDI_DIR and a compiled Kaldi runtime")
def test_aligns_korean_example_directory(tmp_path: Path) -> None:
    result = align_directory(
        PROJECT_ROOT / "example" / "kor_files",
        output_dir=tmp_path,
        kaldi_dir=KALDI_DIR,
        num_jobs=1,
    )
    assert len(result.results) == 3
    assert all(item.textgrid.is_file() for item in result.results)
