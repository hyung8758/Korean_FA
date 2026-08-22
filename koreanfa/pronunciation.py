"""Read and apply explicit KoreanFA pronunciation dictionaries.

The dictionary is deliberately small and portable: UTF-8 TSV with the
``language``, ``word``, and ``pronunciation`` header.  Pronunciations are
language-native readings, not model-internal phone symbols.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

_HEADER = ("language", "word", "pronunciation")
_LANGUAGES = frozenset({"kor", "jap"})


class PronunciationDictionaryError(ValueError):
    """A user-supplied pronunciation dictionary is not usable."""


@dataclass(frozen=True)
class PronunciationEntry:
    """One language-specific exact-token pronunciation override."""

    language: str
    word: str
    pronunciation: str
    line: int


@dataclass(frozen=True)
class PronunciationDictionary:
    """A validated immutable snapshot of a TSV pronunciation dictionary."""

    source: Path
    entries: tuple[PronunciationEntry, ...]

    def for_language(self, language: str) -> dict[str, str]:
        """Return exact-token overrides for one KoreanFA language ID."""
        return {entry.word: entry.pronunciation for entry in self.entries if entry.language == language}

    def write_snapshot(self, destination: Path) -> Path:
        """Write the validated contents for an isolated runtime invocation."""
        lines = ["\t".join(_HEADER)]
        lines.extend("\t".join((entry.language, entry.word, entry.pronunciation)) for entry in self.entries)
        destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return destination


def load_pronunciation_dictionary(path: str | Path) -> PronunciationDictionary:
    """Load a strict UTF-8 TSV dictionary and validate every entry.

    Each ``word`` is one token after normal transcript whitespace
    normalization. Korean readings must be Hangul pronunciations. Japanese
    readings accept Hiragana or Katakana and are normalized to Katakana.
    """
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise PronunciationDictionaryError(f"Pronunciation dictionary is not a readable file: {source}")
    try:
        contents = source.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PronunciationDictionaryError(f"Pronunciation dictionary is not valid UTF-8: {source}") from error
    except OSError as error:
        raise PronunciationDictionaryError(f"Could not read pronunciation dictionary {source}: {error}") from error

    entries: list[PronunciationEntry] = []
    header_seen = False
    seen: set[tuple[str, str]] = set()
    for number, raw_line in enumerate(contents.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        columns = tuple(raw_line.split("\t"))
        if not header_seen:
            if columns != _HEADER:
                expected = "\t".join(_HEADER)
                raise PronunciationDictionaryError(
                    f"Expected TSV header {expected!r} at {source}:{number}."
                )
            header_seen = True
            continue
        if len(columns) != 3:
            raise PronunciationDictionaryError(
                f"Expected exactly three tab-separated columns at {source}:{number}."
            )
        language, word, pronunciation = (value.strip() for value in columns)
        if language not in _LANGUAGES:
            raise PronunciationDictionaryError(
                f"Unsupported dictionary language {language!r} at {source}:{number}; use kor or jap."
            )
        if not word or any(character.isspace() for character in word):
            raise PronunciationDictionaryError(
                f"Dictionary word must be one non-empty token at {source}:{number}."
            )
        if not pronunciation or any(character.isspace() for character in pronunciation):
            raise PronunciationDictionaryError(
                f"Dictionary pronunciation must be one non-empty reading at {source}:{number}."
            )
        if language == "jap":
            pronunciation = _katakana(pronunciation)
        key = language, word
        if key in seen:
            raise PronunciationDictionaryError(
                f"Duplicate dictionary entry for {language}:{word!r} at {source}:{number}."
            )
        _validate_pronunciation(language, pronunciation, source, number)
        seen.add(key)
        entries.append(PronunciationEntry(language, word, pronunciation, number))
    if not header_seen:
        raise PronunciationDictionaryError(f"Pronunciation dictionary has no TSV header: {source}")
    return PronunciationDictionary(source, tuple(entries))


def korean_oov_tokens(text: str, dictionary: PronunciationDictionary | None) -> tuple[str, ...]:
    """Return unique Korean tokens that cannot obtain a pronunciation."""
    from ._korean_g2p import KoreanG2PError, phones_for_word

    overrides = dictionary.for_language("kor") if dictionary else {}
    invalid: list[str] = []
    seen: set[str] = set()
    for word in text.split():
        if word in seen:
            continue
        seen.add(word)
        if word in overrides:
            continue
        try:
            phones_for_word(word)
        except KoreanG2PError:
            invalid.append(word)
    return tuple(invalid)


def rewrite_japanese_mecab(
    dictionary_path: str | Path,
    mecab_input: Path,
    mecab_output: Path,
    applied_output: Path,
) -> None:
    """Replace MeCab readings for exact dictionary surface forms.

    ``mecab.sh`` emits ``surface+reading+metadata`` tokens.  Rewriting only
    the reading keeps MeCab's tokenization and all existing Japanese G2P
    behavior intact.
    """
    overrides = load_pronunciation_dictionary(dictionary_path).for_language("jap")
    applied: set[str] = set()
    rewritten_lines: list[str] = []
    for line in mecab_input.read_text(encoding="utf-8", errors="strict").splitlines():
        tokens: list[str] = []
        for token in line.split():
            surface, separator, remainder = token.partition("+")
            if not separator or surface not in overrides:
                tokens.append(token)
                continue
            _, metadata_separator, metadata = remainder.partition("+")
            tokens.append(surface + "+" + overrides[surface] + ("+" + metadata if metadata_separator else ""))
            applied.add(surface)
        rewritten_lines.append(" ".join(tokens))
    mecab_output.write_text("\n".join(rewritten_lines) + ("\n" if rewritten_lines else ""), encoding="utf-8")
    applied_output.write_text("\n".join(sorted(applied)) + ("\n" if applied else ""), encoding="utf-8")


def _validate_pronunciation(language: str, pronunciation: str, source: Path, line: int) -> None:
    if language == "kor":
        from ._korean_g2p import KoreanG2PError, pronunciation_to_phones

        try:
            pronunciation_to_phones(pronunciation)
        except KoreanG2PError as error:
            raise PronunciationDictionaryError(
                f"Invalid Korean pronunciation at {source}:{line}: {error}"
            ) from error
        return
    normalized = _katakana(pronunciation)
    if any(not ("ァ" <= character <= "ヺ" or character == "ー") for character in normalized):
        raise PronunciationDictionaryError(
            f"Japanese pronunciation must be Hiragana or Katakana at {source}:{line}."
        )


def _katakana(value: str) -> str:
    return "".join(chr(ord(character) + 0x60) if "ぁ" <= character <= "ゖ" else character for character in value)


def main(argv: list[str] | None = None) -> int:
    """Expose the Japanese rewrite step to the isolated shell runtime."""
    parser = argparse.ArgumentParser(description="Apply KoreanFA pronunciation dictionary overrides.")
    commands = parser.add_subparsers(dest="command", required=True)
    japanese = commands.add_parser("rewrite-japanese-mecab")
    japanese.add_argument("--dictionary", required=True, type=Path)
    japanese.add_argument("--input", required=True, type=Path)
    japanese.add_argument("--output", required=True, type=Path)
    japanese.add_argument("--applied", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        rewrite_japanese_mecab(arguments.dictionary, arguments.input, arguments.output, arguments.applied)
    except (OSError, PronunciationDictionaryError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the shell runtime
    sys.exit(main())
