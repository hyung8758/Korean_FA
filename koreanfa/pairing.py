"""Shared WAV/TXT corpus discovery used by the API and shell runtime."""

from dataclasses import dataclass
from pathlib import Path

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
        suffix = path.suffix.lower()
        destination = audio if suffix == ".wav" else text if suffix == ".txt" else None
        if destination is None:
            continue
        relative_stem = path.relative_to(root).with_suffix("")
        previous = destination.get(relative_stem)
        if previous is not None:
            raise PairingError(
                "Ambiguous corpus files share the same relative stem: "
                f"{previous.relative_to(root)} and {path.relative_to(root)}"
            )
        destination[relative_stem] = path

    if not audio or not text:
        raise PairingError(f"A corpus needs both WAV and TXT files: {root}")

    audio_stems = set(audio)
    text_stems = set(text)
    pairs = tuple(
        DiscoveredFilePair(stem, audio[stem], text[stem])
        for stem in sorted(audio_stems & text_stems)
    )
    return CorpusDiscovery(
        pairs=pairs,
        missing_text=tuple(sorted(audio_stems - text_stems)),
        missing_audio=tuple(sorted(text_stems - audio_stems)),
    )
