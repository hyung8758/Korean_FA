from pathlib import Path

import pytest

from koreanfa._korean_g2p import convert_word_file
from koreanfa._korean_g2p import main as korean_g2p_main
from koreanfa.pronunciation import (
    PronunciationDictionaryError,
    korean_oov_tokens,
    load_pronunciation_dictionary,
    rewrite_japanese_mecab,
)


def _write_dictionary(path: Path, *entries: str) -> Path:
    path.write_text("language\tword\tpronunciation\n" + "\n".join(entries) + "\n", encoding="utf-8")
    return path


def test_dictionary_requires_unique_language_specific_tokens(tmp_path: Path) -> None:
    source = _write_dictionary(tmp_path / "dictionary.tsv", "kor\tKoreanFA\t코리안에프에이", "kor\tKoreanFA\t코리안")

    with pytest.raises(PronunciationDictionaryError, match="Duplicate dictionary entry"):
        load_pronunciation_dictionary(source)


def test_dictionary_normalizes_hiragana_readings_and_writes_a_snapshot(tmp_path: Path) -> None:
    dictionary = load_pronunciation_dictionary(
        _write_dictionary(tmp_path / "dictionary.tsv", "jap\t大切\tたいせつ", "kor\tKoreanFA\t코리안에프에이")
    )
    snapshot = dictionary.write_snapshot(tmp_path / "snapshot.tsv")

    assert dictionary.for_language("jap") == {"大切": "タイセツ"}
    assert snapshot.read_text(encoding="utf-8") == (
        "language\tword\tpronunciation\n"
        "jap\t大切\tタイセツ\n"
        "kor\tKoreanFA\t코리안에프에이\n"
    )


def test_korean_dictionary_replaces_default_g2p_for_an_exact_token(tmp_path: Path) -> None:
    dictionary = _write_dictionary(tmp_path / "dictionary.tsv", "kor\t값이\t갑시")
    words = tmp_path / "words.txt"
    words.write_text("값이\n", encoding="utf-8")
    output = tmp_path / "phones.txt"

    convert_word_file(words, output, dictionary)

    assert output.read_text(encoding="utf-8").strip() == "k0 aa pf s0 ii"


def test_korean_g2p_cli_reports_invalid_dictionary_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dictionary = tmp_path / "invalid.tsv"
    dictionary.write_text("word\tpronunciation\nKoreanFA\t코리안에프에이\n", encoding="utf-8")
    words = tmp_path / "words.txt"
    words.write_text("한국어\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="2"):
        korean_g2p_main(
            [
                "--input",
                str(words),
                "--output",
                str(tmp_path / "phones.txt"),
                "--pronunciation-dictionary",
                str(dictionary),
            ]
        )

    assert "Expected TSV header" in capsys.readouterr().err


def test_korean_oov_tokens_are_suppressed_by_a_dictionary_entry(tmp_path: Path) -> None:
    dictionary = load_pronunciation_dictionary(
        _write_dictionary(tmp_path / "dictionary.tsv", "kor\tKoreanFA\t코리안에프에이")
    )

    assert korean_oov_tokens("한국어 KoreanFA <noise>", dictionary) == ("<noise>",)


def test_japanese_dictionary_rewrites_only_mecab_readings_for_matching_tokens(tmp_path: Path) -> None:
    dictionary = _write_dictionary(tmp_path / "dictionary.tsv", "jap\t大切\tたいせつ")
    mecab_input = tmp_path / "mecab.txt"
    mecab_input.write_text("大切+ダイジ+名詞 東京+トウキョウ+名詞\n", encoding="utf-8")
    rewritten, applied = tmp_path / "rewritten.txt", tmp_path / "applied.txt"

    rewrite_japanese_mecab(dictionary, mecab_input, rewritten, applied)

    assert rewritten.read_text(encoding="utf-8") == "大切+タイセツ+名詞 東京+トウキョウ+名詞\n"
    assert applied.read_text(encoding="utf-8") == "大切\n"
