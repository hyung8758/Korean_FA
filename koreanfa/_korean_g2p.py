"""Korean pronunciation-to-phone conversion for the packaged Kaldi model.

``ko-speech-tools`` supplies the Korean pronunciation rules.  This module
converts its phonetic Hangul result to the fixed phone symbols expected by
KoreanFA's Korean Kaldi acoustic model.  The Unicode syllable decomposition
below is deliberately self-contained: it does not use the retired KoG2P
implementation or its rulebook.
"""

import argparse
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Protocol, Sequence, cast

from .pronunciation import PronunciationDictionaryError

_HANGUL_START = 0xAC00
_HANGUL_END = 0xD7A3
_CODA_COUNT = 28
_SYLLABLES_PER_ONSET = 21 * _CODA_COUNT

# The order follows the Unicode Hangul syllable decomposition tables.  The
# values are the phone labels used when the bundled Korean Kaldi model was
# trained, not IPA symbols.
_ONSETS = (
    "k0", "kk", "nn", "t0", "tt", "rr", "mm", "p0", "pp", "s0",
    "ss", "", "c0", "cc", "ch", "kh", "th", "ph", "h0",
)
_VOWELS = (
    "aa", "qq", "ya", "yq", "vv", "ee", "yv", "ye", "oo", "wa",
    "wq", "wo", "yo", "uu", "wv", "we", "wi", "yu", "xx", "xi",
    "ii",
)
_CODAS = (
    "", "kf", "kk", "ks", "nf", "nc", "nh", "tf", "ll", "lk",
    "lm", "lb", "ls", "lt", "lp", "lh", "mf", "pf", "ps", "s0",
    "ss", "ng", "c0", "ch", "kh", "th", "ph", "h0",
)


class KoreanG2PError(ValueError):
    """A transcript cannot be converted to KoreanFA model phones."""


class _Pronouncer(Protocol):
    def __call__(self, text: str) -> str:
        """Return the normalized phonetic Hangul for one token."""


@lru_cache(maxsize=1)
def _pronouncer() -> _Pronouncer:
    """Create one MeCab-backed G2P instance per Python process."""
    try:
        from ko_speech_tools import G2p
    except ImportError as error:  # pragma: no cover - dependency metadata is tested elsewhere
        raise KoreanG2PError(
            "Korean G2P support is unavailable. Reinstall KoreanFA with its required dependencies."
        ) from error
    try:
        return cast(_Pronouncer, G2p())
    except Exception as error:  # pragma: no cover - depends on the local MeCab runtime
        raise KoreanG2PError("Korean G2P could not initialize its bundled MeCab dictionary.") from error


def pronunciation_to_phones(pronunciation: str) -> tuple[str, ...]:
    """Convert phonetic Hangul to KoreanFA's fixed Kaldi phone labels.

    Punctuation and whitespace do not represent acoustic phones. Any other
    remaining non-Hangul character indicates that the upstream G2P could not
    normalize the input, so silently dropping it would create a false lexicon.
    """
    phones: list[str] = []
    unsupported: list[str] = []
    for character in pronunciation:
        codepoint = ord(character)
        if _HANGUL_START <= codepoint <= _HANGUL_END:
            offset = codepoint - _HANGUL_START
            onset_index, remainder = divmod(offset, _SYLLABLES_PER_ONSET)
            vowel_index, coda_index = divmod(remainder, _CODA_COUNT)
            onset = _ONSETS[onset_index]
            if onset:
                phones.append(onset)
            phones.append(_VOWELS[vowel_index])
            coda = _CODAS[coda_index]
            if coda:
                phones.append(coda)
        elif character.isspace() or unicodedata.category(character).startswith("P"):
            continue
        else:
            unsupported.append(character)
    if unsupported:
        rendered = " ".join(repr(character) for character in unsupported)
        raise KoreanG2PError(
            f"Korean G2P left unsupported characters after pronunciation conversion: {rendered}"
        )
    if not phones:
        raise KoreanG2PError("Korean G2P produced no phones from the supplied transcript.")
    return tuple(phones)


def phones_for_word(word: str) -> tuple[str, ...]:
    """Return the model phone sequence for one whitespace-delimited token."""
    if not word or any(character.isspace() for character in word):
        raise KoreanG2PError("Korean G2P accepts exactly one non-empty whitespace-delimited token.")
    return pronunciation_to_phones(_pronouncer()(word))


def convert_word_file(
    input_path: Path,
    output_path: Path,
    pronunciation_dictionary: Path | None = None,
) -> None:
    """Convert one input token per line into one Kaldi phone sequence per line."""
    overrides: dict[str, str] = {}
    if pronunciation_dictionary is not None:
        from .pronunciation import load_pronunciation_dictionary

        overrides = load_pronunciation_dictionary(pronunciation_dictionary).for_language("kor")
    outputs: list[str] = []
    for line_number, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            phones = pronunciation_to_phones(overrides[line]) if line in overrides else phones_for_word(line)
            outputs.append(" ".join(phones))
        except KoreanG2PError as error:
            raise KoreanG2PError(f"Korean G2P failed at {input_path}:{line_number}: {error}") from error
    output_path.write_text("\n".join(outputs) + ("\n" if outputs else ""), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Provide the file-based interface used by the legacy Kaldi shell job."""
    parser = argparse.ArgumentParser(description="Convert Korean tokens to KoreanFA Kaldi phones.")
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 file containing one token per line")
    parser.add_argument("--output", required=True, type=Path, help="destination lexicon-pronunciation file")
    parser.add_argument("--pronunciation-dictionary", type=Path, help="optional KoreanFA TSV pronunciation dictionary")
    arguments = parser.parse_args(argv)
    try:
        convert_word_file(arguments.input, arguments.output, arguments.pronunciation_dictionary)
    except (OSError, KoreanG2PError, PronunciationDictionaryError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess tests
    sys.exit(main())
