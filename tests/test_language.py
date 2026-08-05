from pathlib import Path

import pytest

from koreanfa import PairingError
from koreanfa.language import detect_language, normalize_language


def test_detects_korean_and_japanese() -> None:
    assert detect_language("강제 정렬 테스트") == "kor"
    assert detect_language("こんにちは世界") == "jap"
    assert detect_language("日本語") == "jap"


def test_rejects_mixed_scripts_without_forced_language() -> None:
    with pytest.raises(PairingError, match="Mixed Korean"):
        detect_language("한국어と日本語")


def test_rejects_an_empty_transcript_with_a_pairing_error(tmp_path: Path) -> None:
    transcript = tmp_path / "empty.txt"
    transcript.write_text("  \n", encoding="utf-8")

    with pytest.raises(PairingError, match="Transcript is empty"):
        detect_language(transcript)


def test_rejects_invalid_utf8_with_a_pairing_error(tmp_path: Path) -> None:
    transcript = tmp_path / "invalid.txt"
    transcript.write_bytes(b"\xff\xfe")

    with pytest.raises(PairingError, match="not valid UTF-8"):
        detect_language(transcript)


def test_normalizes_language_aliases() -> None:
    assert normalize_language("ko") == "kor"
    assert normalize_language("ja") == "jap"
