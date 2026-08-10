"""Shared WAV/TXT corpus discovery used by the API and shell runtime."""

from dataclasses import dataclass
from pathlib import Path
from unicodedata import normalize

from .errors import PairingError


@dataclass(frozen=True)
class DiscoveredFilePair:
    """One exact relative-stem match inside a corpus directory."""

    relative_stem: Path
    audio: Path
    transcript: Path


@dataclass(frozen=True)
class CorpusDiscovery:
    """Matched pairs and orphan stems from one deterministic scan."""

    pairs: tuple[DiscoveredFilePair, ...]
    missing_text: tuple[Path, ...]
    missing_audio: tuple[Path, ...]


def _portable_output_key(relative_stem: Path) -> str:
    """Represent a TextGrid path as case-insensitive, normalized Unicode."""
    return normalize("NFC", relative_stem.as_posix()).casefold()


def _reject_output_collisions(relative_stems: set[Path]) -> None:
    """Reject pairs that could overwrite each other on a common macOS volume."""
    destinations: dict[str, Path] = {}
    for relative_stem in sorted(relative_stems):
        key = _portable_output_key(relative_stem)
        previous = destinations.get(key)
        if previous is not None and previous != relative_stem:
            raise PairingError(
                "Corpus pairs would share a TextGrid path on a case-insensitive filesystem: "
                f"{previous.with_suffix('.TextGrid')} and {relative_stem.with_suffix('.TextGrid')}"
            )
        destinations[key] = relative_stem


def _index_corpus_path(
    root: Path, path: Path, audio: dict[Path, Path], text: dict[Path, Path]
) -> None:
    """Index one known file while enforcing case-insensitive extension uniqueness."""
    suffix = path.suffix.lower()
    destination = audio if suffix == ".wav" else text if suffix == ".txt" else None
    if destination is None:
        return
    relative_stem = path.relative_to(root).with_suffix("")
    previous = destination.get(relative_stem)
    if previous is not None:
        raise PairingError(
            "Ambiguous corpus files share the same relative stem: "
            f"{previous.relative_to(root)} and {path.relative_to(root)}"
        )
    destination[relative_stem] = path


def discover_corpus_files(directory: str | Path, *, recursive: bool) -> CorpusDiscovery:
    """Index WAV and TXT files once and match them by exact relative stem.

    A corpus containing two audio or transcript files with the same relative
    stem is ambiguous (for example, ``sample.wav`` and ``sample.WAV``), so it
    is rejected instead of silently selecting whichever file was scanned last.
    """

    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise PairingError(f"Input directory does not exist: {root}")

    files = root.rglob("*") if recursive else root.iterdir()
    audio: dict[Path, Path] = {}
    text: dict[Path, Path] = {}
    for path in files:
        if not path.is_file():
            continue
        _index_corpus_path(root, path, audio, text)

    if not audio or not text:
        raise PairingError(f"A corpus needs both WAV and TXT files: {root}")

    audio_stems = set(audio)
    text_stems = set(text)
    matched_stems = audio_stems & text_stems
    _reject_output_collisions(matched_stems)
    pairs = tuple(
        DiscoveredFilePair(stem, audio[stem], text[stem])
        for stem in sorted(matched_stems)
    )
    return CorpusDiscovery(
        pairs=pairs,
        missing_text=tuple(sorted(audio_stems - text_stems)),
        missing_audio=tuple(sorted(text_stems - audio_stems)),
    )
