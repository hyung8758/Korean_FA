from pathlib import Path

import pytest

from koreanfa import Aligner
from koreanfa.errors import EngineNotFoundError


def test_aligner_defaults_to_auto_language() -> None:
    aligner = Aligner()
    assert aligner.lang == "auto"


def test_aligner_requires_text_for_file_input(tmp_path: Path) -> None:
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"")
    with pytest.raises(ValueError, match="requires its matching TXT"):
        Aligner().align(wav)


def test_aligner_finds_directory_before_requesting_engine(tmp_path: Path) -> None:
    (tmp_path / "sample.wav").write_bytes(b"")
    (tmp_path / "sample.txt").write_text("테스트", encoding="utf-8")
    with pytest.raises(EngineNotFoundError):
        Aligner().align(tmp_path)
