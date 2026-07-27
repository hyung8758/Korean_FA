from __future__ import annotations

from pathlib import Path

import pytest

from koreanfa._korean_g2p import KoreanG2PError, phones_for_word, pronunciation_to_phones


ROOT = Path(__file__).resolve().parents[1]


def _model_phones() -> set[str]:
    return set((ROOT / "model" / "kor_model" / "lexicon.txt").read_text(encoding="utf-8").split()[1:])


def test_pronunciation_to_phones_uses_korean_model_inventory() -> None:
    phones = pronunciation_to_phones("갑씨 비싸다.")
    assert phones == ("k0", "aa", "pf", "ss", "ii", "p0", "ii", "ss", "aa", "t0", "aa")
    assert set(phones) <= _model_phones()


def test_apache_g2p_output_converts_to_model_phones() -> None:
    phones = phones_for_word("값이")
    assert phones == ("k0", "aa", "pf", "ss", "ii")
    assert set(phones) <= _model_phones()


def test_all_packaged_korean_examples_map_to_model_phones() -> None:
    words = {
        word
        for transcript in (ROOT / "example" / "kor_files").glob("*.txt")
        for word in transcript.read_text(encoding="utf-8").split()
    }
    for word in words:
        assert set(phones_for_word(word)) <= _model_phones(), word


def test_unconverted_characters_are_rejected() -> None:
    with pytest.raises(KoreanG2PError, match="unsupported characters"):
        pronunciation_to_phones("KoreanFA")
