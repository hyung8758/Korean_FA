#!/usr/bin/env python3
"""Emit NUL-delimited corpus records for the Bash 3.2 batch runtime."""

import sys
from pathlib import Path


# This script is invoked from package data as a file.  Make the installed
# package (or source checkout) importable without depending on the caller's cwd.
PACKAGE_PARENT = Path(__file__).resolve().parents[3]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from koreanfa.errors import PairingError  # noqa: E402
from koreanfa.pairing import discover_corpus_files  # noqa: E402


def _emit(*fields: str | Path) -> None:
    for field in fields:
        value = str(field)
        if "\0" in value:
            raise PairingError("A corpus path cannot contain a NUL character.")
        sys.stdout.buffer.write(value.encode("utf-8", errors="strict") + b"\0")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} DIRECTORY", file=sys.stderr)
        return 2
    try:
        discovery = discover_corpus_files(sys.argv[1], recursive=True)
        for pair in discovery.pairs:
            _emit("PAIR", pair.relative_stem, pair.audio, pair.transcript)
        for stem in discovery.missing_text:
            _emit("MISSING_TEXT", stem, "", "")
        for stem in discovery.missing_audio:
            _emit("MISSING_AUDIO", stem, "", "")
    except (OSError, PairingError, UnicodeError) as error:
        print(f"koreanfa: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
