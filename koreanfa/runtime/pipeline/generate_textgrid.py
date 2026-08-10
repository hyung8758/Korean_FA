"""Create a valid Praat TextGrid from KoreanFA's phone-level CTM output.

The legacy implementation searched rows repeatedly, compared lists by object
identity, and could emit incomplete intervals.  This version writes continuous
interval tiers and keeps the historic command-line arguments for compatibility.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class PhoneEvent:
    label: str
    start: float
    end: float


def _escape(label: str) -> str:
    return label.replace('"', '""')


def _base_phone(label: str) -> str:
    if label.startswith("<") and label.endswith(">"):
        return label
    stem, separator, suffix = label.rpartition("_")
    return stem if separator and suffix in {"B", "E", "I", "S"} else label


def _read_events(source_dir: Path) -> list[PhoneEvent]:
    files = sorted(source_dir.glob("*.txt"))
    if len(files) != 1:
        raise ValueError(f"Expected exactly one alignment TXT file in {source_dir}, found {len(files)}")
    lines = files[0].read_text(encoding="utf-8").splitlines()
    events: list[PhoneEvent] = []
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split("\t")
        if len(fields) < 11:
            raise ValueError(f"Malformed alignment row {line_number}: {line!r}")
        try:
            start, end = float(fields[9]), float(fields[10])
        except ValueError as error:
            raise ValueError(f"Invalid alignment time on row {line_number}: {line!r}") from error
        if end < start:
            raise ValueError(f"Alignment end precedes its start on row {line_number}")
        events.append(PhoneEvent(fields[6], start, end))
    if not events:
        raise ValueError("The alignment produced no phone intervals")
    return sorted(events, key=lambda event: (event.start, event.end))


def _read_words(path: Path) -> list[str]:
    words: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if fields:
            words.append(fields[0])
    return words


def _continuous(items: list[tuple[float, float, str]], end_time: float) -> list[tuple[float, float, str]]:
    """Fill timing gaps so Praat receives a complete, monotonic interval tier."""
    result: list[tuple[float, float, str]] = []
    cursor = 0.0
    for start, end, label in items:
        start = max(cursor, start)
        end = max(start, end)
        if start > cursor:
            result.append((cursor, start, ""))
        if end > start:
            result.append((start, end, label))
        cursor = max(cursor, end)
    if end_time > cursor:
        result.append((cursor, end_time, ""))
    if not result:  # guarded above, but retain a valid tier for future callers.
        result.append((0.0, max(0.0, end_time), ""))
    return result


def _word_items(events: list[PhoneEvent], words: list[str]) -> list[tuple[float, float, str]]:
    """Join B/I/E/S phone sequences to transcript words in lexical order."""
    items: list[tuple[float, float, str]] = []
    word_index = 0
    group_start: float | None = None
    group_end: float | None = None

    def close_group() -> None:
        nonlocal group_start, group_end, word_index
        if group_start is None or group_end is None:
            return
        if word_index >= len(words):
            raise ValueError("More aligned word groups than entries in the pronunciation lexicon")
        items.append((group_start, group_end, words[word_index]))
        word_index += 1
        group_start = group_end = None

    for event in events:
        label = event.label
        if label.startswith("<") and label.endswith(">"):
            close_group()
            items.append((event.start, event.end, label))
            continue
        _, separator, tag = label.rpartition("_")
        if separator and tag == "B":
            close_group()
            group_start, group_end = event.start, event.end
        elif separator and tag in {"I", "E"}:
            if group_start is None:
                group_start = event.start
            group_end = event.end
            if tag == "E":
                close_group()
        elif separator and tag == "S":
            close_group()
            group_start, group_end = event.start, event.end
            close_group()
        else:
            # Older models without position-dependent phone names still get a
            # useful word tier rather than silently writing invalid output.
            close_group()
            group_start, group_end = event.start, event.end
            close_group()
    close_group()
    return items


def _write_tier(stream: TextIO, name: str, end_time: float, intervals: list[tuple[float, float, str]]) -> None:
    stream.write(f'"IntervalTier"\n"{_escape(name)}"\n0\n{end_time:.6f}\n{len(intervals)}\n')
    for start, end, label in intervals:
        stream.write(f"{start:.6f}\n{end:.6f}\n\"{_escape(label)}\"\n")


def generate(source_dir: Path, word_file: Path, _text_num: Path, save_dir: Path, *, no_word: bool, no_phone: bool) -> Path:
    if no_word and no_phone:
        raise ValueError("At least one of word or phone tiers must be enabled")
    events = _read_events(source_dir)
    end_time = max(event.end for event in events)
    tiers: list[tuple[str, list[tuple[float, float, str]]]] = []
    if not no_phone:
        tiers.append(("phone", _continuous([(event.start, event.end, _base_phone(event.label)) for event in events], end_time)))
    if not no_word:
        tiers.append(("word", _continuous(_word_items(events, _read_words(word_file)), end_time)))
    save_dir.mkdir(parents=True, exist_ok=True)
    destination = save_dir / "tagged_final_ali.TextGrid"
    with destination.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write('File type = "ooTextFile short"\n"TextGrid"\n\n')
        stream.write(f"0\n{end_time:.6f}\n<exists>\n{len(tiers)}\n")
        for name, intervals in tiers:
            _write_tier(stream, name, end_time, intervals)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-word", action="store_true", help="Do not write the word tier")
    parser.add_argument("--no-phone", action="store_true", help="Do not write the phone tier")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("word_file", type=Path)
    parser.add_argument("text_num", type=Path, help="Retained for backwards compatibility")
    parser.add_argument("save_dir", type=Path)
    args = parser.parse_args(argv)
    generate(args.source_dir, args.word_file, args.text_num, args.save_dir, no_word=args.no_word, no_phone=args.no_phone)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
