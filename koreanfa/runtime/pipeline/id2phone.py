"""Join Kaldi CTM phone IDs with phone symbols and segment times."""

import argparse
from pathlib import Path


def _rows(path: Path) -> list[list[str]]:
    return [line.split() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def convert(phones_path: Path, segments_path: Path, ctm_path: Path, destination: Path) -> None:
    phones = _rows(phones_path)
    phone_by_id = {row[1]: row[0] for row in phones if len(row) >= 2}
    segments = {row[0]: row for row in _rows(segments_path) if len(row) >= 4}
    converted: list[list[str]] = []
    for number, row in enumerate(_rows(ctm_path), start=1):
        if len(row) < 5:
            raise ValueError(f"Malformed CTM row {number}")
        utterance, channel, start, duration, phone_id = row[:5]
        if phone_id not in phone_by_id:
            raise ValueError(f"Unknown phone ID {phone_id!r} in CTM row {number}")
        if utterance not in segments:
            raise ValueError(f"No segment for utterance {utterance!r}")
        segment = segments[utterance]
        absolute_start = float(segment[2]) + float(start)
        absolute_end = absolute_start + float(duration)
        converted.append([
            utterance, segment[1], phone_id, channel, start, duration, phone_by_id[phone_id], segment[2], segment[3],
            f"{absolute_start:.6f}", f"{absolute_end:.6f}",
        ])
    destination.write_text("".join("\t".join(row) + "\n" for row in converted), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phones", type=Path)
    parser.add_argument("segments", type=Path)
    parser.add_argument("ctm", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    convert(args.phones, args.segments, args.ctm, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
