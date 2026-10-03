"""Read explicit WAV/TXT pairs from a UTF-8 CSV manifest."""

import csv
from dataclasses import dataclass
from pathlib import Path

from .errors import PairingError
from .language import normalize_language
from .pairing import _portable_output_key
from .result import InputPair

_HEADER = ("audio", "transcript", "language", "output_id")


@dataclass(frozen=True)
class ManifestEntry:
    """One parsed manifest row and its CSV line number."""

    pair: InputPair
    line: int


def read_manifest(path: str | Path, *, lang: str = "auto") -> tuple[ManifestEntry, ...]:
    """Parse a manifest before alignment, resolving input paths relative to it."""
    source = Path(path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".csv":
        raise PairingError(f"Manifest must be an existing CSV file: {source}")
    default_language = normalize_language(lang)
    entries: list[ManifestEntry] = []
    destinations: dict[str, int] = {}
    try:
        with source.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
            rows = csv.reader(stream, strict=True)
            header = next(rows, None)
            if header != list(_HEADER):
                raise PairingError(f"Manifest {source}: expected CSV header {','.join(_HEADER)}")
            for row in rows:
                if not row:
                    continue
                line = rows.line_num
                if len(row) != len(_HEADER):
                    raise PairingError(f"Manifest {source}:{line}: expected four CSV columns")
                audio_value, transcript_value, language_value, output_value = (value.strip() for value in row)
                if not audio_value or not transcript_value:
                    raise PairingError(f"Manifest {source}:{line}: audio and transcript paths are required")
                if "\x00" in audio_value or "\x00" in transcript_value:
                    raise PairingError(f"Manifest {source}:{line}: input paths cannot contain NUL characters")
                audio = _input_path(source.parent, audio_value)
                transcript = _input_path(source.parent, transcript_value)
                if not output_value:
                    output_value = audio.stem
                output_id = _output_id(output_value, source, line)
                key = _portable_output_key(output_id)
                if previous := destinations.get(key):
                    raise PairingError(
                        f"Manifest {source}:{line}: output_id {output_value!r} conflicts with line {previous}"
                    )
                destinations[key] = line
                try:
                    language = normalize_language(language_value or default_language)
                except ValueError as error:
                    raise PairingError(f"Manifest {source}:{line}: {error}") from error
                entries.append(ManifestEntry(InputPair(audio, transcript, output_id, language), line))
    except UnicodeDecodeError as error:
        raise PairingError(f"Manifest is not valid UTF-8: {source}") from error
    except (OSError, csv.Error) as error:
        raise PairingError(f"Could not read manifest {source}: {error}") from error
    if not entries:
        raise PairingError(f"Manifest contains no WAV/TXT pairs: {source}")
    return tuple(entries)


def _input_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _output_id(value: str, source: Path, line: int) -> Path:
    parts = value.split("/")
    if (
        value.startswith("/")
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in parts)
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PairingError(f"Manifest {source}:{line}: output_id must be a safe relative path")
    return Path(value)
