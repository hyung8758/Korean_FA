"""Language selection for KoreanFA's Korean and Japanese models."""

from __future__ import annotations

import re
from pathlib import Path

from .errors import PairingError

LANGUAGES = frozenset({"auto", "kor", "jap"})
HANGUL = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
JAPANESE_KANA = re.compile(r"[\u3040-\u30ff\uff66-\uff9f]")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def normalize_language(language: str) -> str:
    normalized = language.lower().strip()
    aliases = {"ko": "kor", "korean": "kor", "ja": "jap", "jpn": "jap", "japanese": "jap"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in LANGUAGES:
        raise ValueError("lang must be one of: auto, kor, jap")
    return normalized


def detect_language(transcript: str | Path) -> str:
    """Detect Korean or Japanese from transcription characters.

    Hangul selects Korean. Hiragana/Katakana select Japanese. Kanji-only text
    is treated as Japanese because ordinary Korean transcriptions use Hangul.
    Mixed Hangul/Kana text is intentionally rejected: callers must force a
    model with ``lang='kor'`` or ``lang='jap'``.
    """
    text = Path(transcript).read_text(encoding="utf-8") if isinstance(transcript, Path) else transcript
    has_hangul = bool(HANGUL.search(text))
    has_kana = bool(JAPANESE_KANA.search(text))
    if has_hangul and has_kana:
        raise PairingError("Mixed Korean and Japanese scripts require an explicit lang='kor' or lang='jap'.")
    if has_hangul:
        return "kor"
    if has_kana or CJK.search(text):
        return "jap"
    raise PairingError("Could not detect Korean or Japanese text. Set lang='kor' or lang='jap'.")
