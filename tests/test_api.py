from pathlib import Path

import pytest

from koreanfa import PairingError, discover_pairs


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_discovers_korean_example_pairs() -> None:
    pairs = discover_pairs(PROJECT_ROOT / "example" / "kor_files")
    assert len(pairs) == 3
    assert [pair.audio.stem for pair in pairs] == ["fv01_t01_s01", "fv01_t01_s02", "fv01_t02_s50"]
    assert {pair.language for pair in pairs} == {"kor"}


def test_discovers_japanese_example_pairs() -> None:
    pairs = discover_pairs(PROJECT_ROOT / "example" / "jap_files")
    assert len(pairs) == 5
    assert all(pair.audio.stem == pair.transcript.stem for pair in pairs)
    assert {pair.language for pair in pairs} == {"jap"}


def test_reports_unmatched_files(tmp_path: Path) -> None:
    (tmp_path / "paired.wav").write_bytes(b"")
    (tmp_path / "paired.txt").write_text("테스트", encoding="utf-8")
    (tmp_path / "orphan.wav").write_bytes(b"")

    with pytest.raises(PairingError, match="WAV without TXT: orphan"):
        discover_pairs(tmp_path)


def test_can_ignore_unmatched_files(tmp_path: Path) -> None:
    (tmp_path / "paired.wav").write_bytes(b"")
    (tmp_path / "paired.txt").write_text("테스트", encoding="utf-8")
    (tmp_path / "orphan.txt").write_text("고아", encoding="utf-8")

    pairs = discover_pairs(tmp_path, strict=False)
    assert len(pairs) == 1
    assert pairs[0].relative_stem == Path("paired")
