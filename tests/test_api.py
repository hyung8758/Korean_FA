from pathlib import Path

import pytest

from koreanfa import BatchAlignmentResult, PairingError, discover_pairs
from koreanfa.api import _runtime_failure_reasons, align_directory
from koreanfa.pairing import _index_corpus_path


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


def test_ignores_unmatched_files_with_a_warning_by_default(tmp_path: Path) -> None:
    (tmp_path / "paired.wav").write_bytes(b"")
    (tmp_path / "paired.txt").write_text("테스트", encoding="utf-8")
    (tmp_path / "orphan.wav").write_bytes(b"")

    with pytest.warns(UserWarning, match="WAV without TXT: orphan"):
        discover_pairs(tmp_path)


def test_can_reject_unmatched_files(tmp_path: Path) -> None:
    (tmp_path / "paired.wav").write_bytes(b"")
    (tmp_path / "paired.txt").write_text("테스트", encoding="utf-8")
    (tmp_path / "orphan.txt").write_text("고아", encoding="utf-8")

    with pytest.raises(PairingError, match="TXT without WAV: orphan"):
        discover_pairs(tmp_path, ignore_unmatched=False)


def test_recursive_pairing_preserves_relative_paths_and_unusual_names(tmp_path: Path) -> None:
    nested = tmp_path / "하위 폴더"
    nested.mkdir()
    stem = "줄바꿈\n日本語"
    (nested / f"{stem}.WAV").write_bytes(b"")
    (nested / f"{stem}.TXT").write_text("日本語", encoding="utf-8")

    pairs = discover_pairs(tmp_path, recursive=True, lang="jap")

    assert len(pairs) == 1
    assert pairs[0].relative_stem == Path("하위 폴더") / stem
    assert pairs[0].audio.suffix == ".WAV"


def test_pairing_rejects_duplicate_case_insensitive_extensions(tmp_path: Path) -> None:
    audio: dict[Path, Path] = {}
    text: dict[Path, Path] = {}
    _index_corpus_path(tmp_path, tmp_path / "same.wav", audio, text)

    with pytest.raises(PairingError, match="Ambiguous corpus files"):
        _index_corpus_path(tmp_path, tmp_path / "same.WAV", audio, text)


def test_reads_per_file_runtime_failure_reasons() -> None:
    output = (
        "KOREANFA_EVENT\tfailed\t7\tpair_7\tJapanese transcript produced no entries.\n"
        "KOREANFA_SUMMARY\ttotal=8\tsuccess=7\tfailed=1\n"
    )

    assert _runtime_failure_reasons(output) == {
        "pair_000007": "Japanese transcript produced no entries.",
    }


def test_directory_auto_mode_collects_unknown_language_as_a_file_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "known.wav").write_bytes(b"")
    (tmp_path / "known.txt").write_text("테스트", encoding="utf-8")
    (tmp_path / "unknown.wav").write_bytes(b"")
    (tmp_path / "unknown.txt").write_text("<laugh>", encoding="utf-8")

    def fake_align(*args, **_kwargs):
        return BatchAlignmentResult((), args[1], failures=args[-1])

    monkeypatch.setattr("koreanfa.api._align_pairs", fake_align)
    result = align_directory(tmp_path)

    assert len(result.failures) == 1
    assert result.failures[0].audio.name == "unknown.wav"
    assert "Could not detect" in result.failures[0].reason
