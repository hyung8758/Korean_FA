"""Validate staged UTF-8 transcripts without modifying source corpora."""

import argparse
import re
import sys
from pathlib import Path


def normalize_transcript(text: str) -> str:
    """Collapse whitespace while preserving language-specific punctuation."""
    return re.sub(r"\s+", " ", text).strip()


def check_directory(directory: Path) -> tuple[Path, ...]:
    transcripts = tuple(sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".txt"))
    if not transcripts:
        raise ValueError(f"No TXT files found in {directory}")
    for transcript in transcripts:
        try:
            original = transcript.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"Transcript is not valid UTF-8: {transcript}") from error
        normalized = normalize_transcript(original)
        if not normalized:
            raise ValueError(f"Transcript is empty: {transcript}")
        # The caller passes an isolated staging directory, so normalization is
        # safe and does not alter the user's original corpus.
        transcript.write_text(normalized + "\n", encoding="utf-8")
    return transcripts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate KoreanFA staged transcripts")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        transcripts = check_directory(args.directory)
    except ValueError as error:
        print(f"koreanfa: error: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(transcripts)} UTF-8 transcript(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
