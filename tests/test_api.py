import subprocess
from pathlib import Path

import pytest

from koreanfa import BatchAlignmentResult, InputPair, PairingError, discover_pairs
from koreanfa._alignment_runtime import run_language_group as _run_language_group
from koreanfa._alignment_runtime import runtime_attempt_counts as _runtime_attempt_counts
from koreanfa._alignment_runtime import runtime_failure_reasons as _runtime_failure_reasons
from koreanfa.api import align_directory
from koreanfa.errors import AudioPreparationError
from koreanfa.pairing import (
    _index_corpus_path,
    _portable_output_key,
    _reject_output_collisions,
    _textgrid_relative_path,
)

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


def test_pairing_rejects_case_insensitive_textgrid_collisions() -> None:
    with pytest.raises(PairingError, match="case-insensitive filesystem"):
        _reject_output_collisions({Path("Speaker/Sample"), Path("speaker/sample")})


def test_pairing_normalizes_unicode_before_comparing_textgrid_paths() -> None:
    composed = Path("café/sample")
    decomposed = Path("cafe\u0301/sample")

    assert _portable_output_key(composed) == _portable_output_key(decomposed)
    with pytest.raises(PairingError, match="share a TextGrid path"):
        _reject_output_collisions({composed, decomposed})


def test_pairing_allows_portably_distinct_textgrid_paths() -> None:
    _reject_output_collisions({Path("speaker-a/sample"), Path("speaker-b/sample")})


def test_textgrid_path_preserves_dots_in_the_corpus_stem() -> None:
    assert _textgrid_relative_path(Path("speaker/session.v1")) == Path("speaker/session.v1.TextGrid")
    _reject_output_collisions({Path("foo"), Path("foo.bar")})


def test_reads_per_file_runtime_failure_reasons() -> None:
    output = (
        "KOREANFA_EVENT\tfailed\t7\tpair_7\tJapanese transcript produced no entries.\n"
        "KOREANFA_SUMMARY\ttotal=8\tsuccess=7\tfailed=1\n"
    )

    assert _runtime_failure_reasons(output) == {
        "pair_000007": "Japanese transcript produced no entries.",
    }


def test_reads_greatest_runtime_attempt_count() -> None:
    output = (
        "KOREANFA_EVENT\tattempt\t0\tpair_0\t1/3\n"
        "KOREANFA_EVENT\tattempt\t0\tpair_0\t2/3\n"
        "KOREANFA_EVENT\tattempt\t1\tpair_1\t1/3\n"
    )

    assert _runtime_attempt_counts(output) == {"pair_000000": 2, "pair_000001": 1}


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


def test_audio_preparation_failure_does_not_abort_the_rest_of_a_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_root = tmp_path / "source"
    output_root = tmp_path / "output"
    input_root.mkdir()
    output_root.mkdir()
    pairs = []
    for stem in ("broken", "good"):
        audio = input_root / f"{stem}.wav"
        transcript = input_root / f"{stem}.txt"
        audio.write_bytes(b"audio")
        transcript.write_text("테스트", encoding="utf-8")
        pairs.append(InputPair(audio, transcript, Path(stem), "kor"))

    def fake_normalize(source: Path, destination: Path) -> None:
        if source.stem == "broken":
            raise AudioPreparationError("invalid test audio")
        destination.write_bytes(b"normalized")

    def fake_runtime(command, *_args, **_kwargs):
        staged = Path(command[-1])
        (staged / "pair_000000.TextGrid").write_text("textgrid", encoding="utf-8")
        return subprocess.CompletedProcess(
            command,
            0,
            "KOREANFA_SUMMARY\ttotal=1\tsuccess=1\tfailed=0\n",
            "",
        )

    monkeypatch.setattr("koreanfa._alignment_runtime.normalize_wav", fake_normalize)
    monkeypatch.setattr("koreanfa._alignment_runtime.run_runtime_command", fake_runtime)

    results, failures, work_dir = _run_language_group(
        tuple(pairs),
        "kor",
        output_root,
        tmp_path / "engine",
        {},
        tmp_path / "resources",
        1,
        True,
        True,
        False,
        None,
        0,
        2,
        None,
    )

    assert work_dir is None
    assert [result.audio.stem for result in results] == ["good"]
    assert [failure.audio.stem for failure in failures] == ["broken"]
    assert failures[0].reason == "invalid test audio"
    assert results[0].textgrid.is_file()
