"""Normalize CTM timings while preserving independent utterance timelines."""

import argparse
from pathlib import Path


def fix_ctm(source: Path, destination: Path) -> None:
    previous_end: dict[tuple[str, str], float] = {}
    fixed: list[str] = []
    for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if len(fields) < 5:
            raise ValueError(f"Malformed CTM row {number}: {line!r}")
        key = (fields[0], fields[1])
        try:
            start, duration = float(fields[2]), float(fields[3])
        except ValueError as error:
            raise ValueError(f"Invalid CTM timing on row {number}: {line!r}") from error
        corrected_start = previous_end.get(key, start)
        fields[2] = f"{corrected_start:.6f}".rstrip("0").rstrip(".")
        previous_end[key] = corrected_start + duration
        fixed.append(" ".join(fields))
    destination.write_text("\n".join(fixed) + ("\n" if fixed else ""), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctm_file", type=Path)
    parser.add_argument("adjusted_ctm_file", type=Path)
    args = parser.parse_args(argv)
    fix_ctm(args.ctm_file, args.adjusted_ctm_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
