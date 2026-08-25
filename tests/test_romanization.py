from pathlib import Path

import pytest

import koreanfa.romanization as romanization
from koreanfa.romanization import romanize_japanese_reading, romanize_korean_pronunciation

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("pronunciation", "expected"),
    (
        ("그는", "geuneun"),
        ("괜차는", "gwaenchaneun"),
        ("궁물", "gungmul"),
        ("실라", "silla"),
        ("가치", "gachi"),
    ),
)
def test_romanizes_resolved_korean_pronunciation(pronunciation: str, expected: str) -> None:
    assert romanize_korean_pronunciation(pronunciation) == expected


def test_preserves_non_hangul_display_text() -> None:
    assert romanize_korean_pronunciation("A그는!") == "Ageuneun!"


@pytest.mark.parametrize(
    ("reading", "expected"),
    (
        ("ニホンゴ", "nihongo"),
        ("トウキョウ", "toukyou"),
        ("ガッコウ", "gakkou"),
        ("シンヨウ", "shin'you"),
        ("コーヒー", "koohii"),
    ),
)
def test_romanizes_japanese_katakana_readings(reading: str, expected: str) -> None:
    assert romanize_japanese_reading(reading) == expected


def test_japanese_trailing_sokuon_uses_the_following_reading() -> None:
    assert romanize_japanese_reading("トッ", "テ") == "tot"


def test_japanese_romanization_covers_the_packaged_japanese_g2p_kana() -> None:
    kana_table = (ROOT / "koreanfa" / "runtime" / "languages" / "jap" / "kana2phone").read_text(encoding="utf-8")
    inventory = {line.split("+", 1)[0] for line in kana_table.splitlines() if "+" in line}
    assert inventory <= set(romanization._JAPANESE_ROMANIZATION) | {"ッ", "ン", "ー"}
