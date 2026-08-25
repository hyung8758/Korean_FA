#!/usr/bin/env python3
"""Validate KoreanFA TextGrid label sequences against Linux golden fixtures."""

import argparse
import json
from pathlib import Path


def _quoted_value(line: str, *, context: str) -> str:
    if len(line) < 2 or not line.startswith('"') or not line.endswith('"'):
        raise ValueError(f"Expected a quoted {context}, received: {line!r}")
    return line[1:-1].replace('""', '"')


def read_short_textgrid_labels(path: Path) -> dict[str, list[str]]:
    """Return ordered interval labels from a Praat short TextGrid."""

    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    if not lines or lines[0] != 'File type = "ooTextFile short"':
        raise ValueError(f"KoreanFA expected a Praat short TextGrid: {path}")
    tiers: dict[str, list[str]] = {}
    index = 0
    while index < len(lines):
        if lines[index] != '"IntervalTier"':
            index += 1
            continue
        if index + 4 >= len(lines):
            raise ValueError(f"Truncated interval tier in {path}")
        name = _quoted_value(lines[index + 1], context="tier name")
        try:
            interval_count = int(lines[index + 4])
        except ValueError as error:
            raise ValueError(f"Invalid interval count for tier {name!r} in {path}") from error
        first_interval = index + 5
        tier_end = first_interval + interval_count * 3
        if tier_end > len(lines):
            raise ValueError(f"Truncated {name!r} intervals in {path}")
        if name in tiers:
            raise ValueError(f"Duplicate tier {name!r} in {path}")
        labels = [
            _quoted_value(lines[first_interval + offset * 3 + 2], context="interval label")
            for offset in range(interval_count)
        ]
        tiers[name] = labels
        index = tier_end
    if not tiers:
        raise ValueError(f"TextGrid contains no interval tiers: {path}")
    return tiers


def validate_labels(textgrid: Path, expected: dict[str, list[str]]) -> None:
    """Validate golden model labels and the required readable Romanization tier."""

    actual = read_short_textgrid_labels(textgrid)
    expected_tiers = set(expected)
    received_model_tiers = set(actual) - {"romanization"}
    if received_model_tiers != expected_tiers:
        raise RuntimeError(
            f"TextGrid model tiers differ for {textgrid}: "
            f"expected {sorted(expected_tiers)}, received {sorted(received_model_tiers)}"
        )
    for tier, expected_labels in expected.items():
        actual_labels = actual[tier]
        if actual_labels == expected_labels:
            continue
        difference = next(
            (
                index
                for index, (actual_label, expected_label) in enumerate(zip(actual_labels, expected_labels))
                if actual_label != expected_label
            ),
            min(len(actual_labels), len(expected_labels)),
        )
        expected_label = expected_labels[difference] if difference < len(expected_labels) else "<end>"
        actual_label = actual_labels[difference] if difference < len(actual_labels) else "<end>"
        raise RuntimeError(
            f"{tier!r} labels differ at index {difference} for {textgrid}: "
            f"expected {expected_label!r}, received {actual_label!r} "
            f"(expected {len(expected_labels)} labels, received {len(actual_labels)})"
        )
    _validate_romanization(textgrid, actual)


def _validate_romanization(textgrid: Path, tiers: dict[str, list[str]]) -> None:
    """Check the display tier without changing phone/word golden fixtures."""
    romanization = tiers.get("romanization")
    words = tiers.get("word")
    if romanization is None:
        raise RuntimeError(f"TextGrid is missing the required romanization tier: {textgrid}")
    if words is None or len(romanization) != len(words):
        raise RuntimeError(f"Romanization tier does not match word-tier intervals: {textgrid}")
    for index, (word, label) in enumerate(zip(words, romanization, strict=True)):
        if word.startswith("<") and word.endswith(">"):
            if label != word:
                raise RuntimeError(f"Romanization silence label differs at index {index} for {textgrid}")
        elif word == "":
            if label:
                raise RuntimeError(f"Romanization gap is not empty at index {index} for {textgrid}")
        elif not label or not label.isascii():
            raise RuntimeError(f"Invalid Romanization label at index {index} for {textgrid}: {label!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("language", choices=("kor", "jap"))
    parser.add_argument("textgrid", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    validate_labels(args.textgrid, fixture["languages"][args.language]["tiers"])
    print(f"Validated {args.language} labels: {args.textgrid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
