"""Read KoreanFA TextGrids and write optional machine-readable exports."""

import csv
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path

from ._io import atomic_write_text
from .errors import AlignmentError
from .result import AlignmentInterval, AlignmentOutputs, ExportFormat


@dataclass(frozen=True)
class ParsedAlignment:
    """Canonical representation shared by the API and all exporters."""

    duration: float
    words: tuple[AlignmentInterval, ...]
    phones: tuple[AlignmentInterval, ...]
    romanizations: tuple[AlignmentInterval, ...] = ()


def _quoted(value: str, *, context: str) -> str:
    if len(value) < 2 or not value.startswith('"') or not value.endswith('"'):
        raise ValueError(f"Expected a quoted {context}, got {value!r}")
    inner = value[1:-1]
    result: list[str] = []
    index = 0
    while index < len(inner):
        if inner[index] != '"':
            result.append(inner[index])
            index += 1
            continue
        if index + 1 >= len(inner) or inner[index + 1] != '"':
            raise ValueError(f"Unescaped quote in {context}: {value!r}")
        result.append('"')
        index += 2
    return "".join(result)


def _float(value: str, *, context: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"Invalid {context}: {value!r}") from error
    if parsed < 0 or not parsed < float("inf"):
        raise ValueError(f"Invalid {context}: {value!r}")
    return parsed


def parse_textgrid(path: str | Path) -> ParsedAlignment:
    """Parse and validate the short TextGrid format emitted by KoreanFA."""
    source = Path(path)
    try:
        lines = [line.strip() for line in source.read_text(encoding="utf-8", errors="strict").splitlines()]
    except (OSError, UnicodeDecodeError) as error:
        raise AlignmentError(f"Could not read TextGrid as UTF-8: {source}: {error}", work_dir=None) from error
    lines = [line for line in lines if line]
    try:
        if len(lines) < 6 or lines[0] != 'File type = "ooTextFile short"' or lines[1] != '"TextGrid"':
            raise ValueError("Unsupported or malformed TextGrid header")
        index = 2
        minimum = _float(lines[index], context="TextGrid minimum time")
        maximum = _float(lines[index + 1], context="TextGrid maximum time")
        if minimum != 0 or maximum < minimum or lines[index + 2] != "<exists>":
            raise ValueError("Invalid TextGrid bounds")
        tier_count = int(lines[index + 3])
        if tier_count < 1:
            raise ValueError("TextGrid has no tiers")
        index += 4
        tiers: dict[str, tuple[AlignmentInterval, ...]] = {}
        for _ in range(tier_count):
            if lines[index] != '"IntervalTier"':
                raise ValueError("Only IntervalTier TextGrids are supported")
            name = _quoted(lines[index + 1], context="tier name")
            tier_minimum = _float(lines[index + 2], context=f"{name} tier minimum time")
            tier_maximum = _float(lines[index + 3], context=f"{name} tier maximum time")
            interval_count = int(lines[index + 4])
            if (
                name in tiers
                or interval_count < 0
                or tier_minimum != minimum
                or not math.isclose(tier_maximum, maximum, rel_tol=0.0, abs_tol=1e-9)
            ):
                raise ValueError(f"Invalid {name!r} tier metadata")
            index += 5
            intervals: list[AlignmentInterval] = []
            cursor = tier_minimum
            for _interval in range(interval_count):
                start = _float(lines[index], context=f"{name} interval start")
                end = _float(lines[index + 1], context=f"{name} interval end")
                label = _quoted(lines[index + 2], context=f"{name} interval label")
                if (
                    not math.isclose(start, cursor, rel_tol=0.0, abs_tol=1e-9)
                    or end < start
                    or end > tier_maximum + 1e-9
                ):
                    raise ValueError(f"Non-continuous or out-of-bounds interval in {name!r} tier")
                intervals.append(AlignmentInterval(start, end, label))
                cursor = end
                index += 3
            if not intervals or not math.isclose(cursor, tier_maximum, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError(f"Incomplete {name!r} tier")
            tiers[name] = tuple(intervals)
        if index != len(lines):
            raise ValueError("Unexpected trailing TextGrid content")
        if not set(tiers).issubset({"word", "phone", "romanization"}):
            raise ValueError("TextGrid contains an unsupported tier")
    except (IndexError, ValueError) as error:
        raise AlignmentError(f"Invalid KoreanFA TextGrid: {source}: {error}", work_dir=None) from error
    return ParsedAlignment(maximum, tiers.get("word", ()), tiers.get("phone", ()), tiers.get("romanization", ()))


def is_valid_textgrid(
    path: Path, *, word_tier: bool, phone_tier: bool, romanization_tier: bool = False
) -> bool:
    """Return whether an existing output is structurally valid for this request."""
    try:
        parsed = parse_textgrid(path)
        require_tiers(
            parsed,
            word_tier=word_tier,
            phone_tier=phone_tier,
            romanization_tier=romanization_tier,
        )
    except AlignmentError:
        return False
    return True


def require_tiers(
    parsed: ParsedAlignment, *, word_tier: bool, phone_tier: bool, romanization_tier: bool = False
) -> None:
    """Reject a runtime output that omitted a tier requested by the caller."""
    missing = []
    if word_tier and not parsed.words:
        missing.append("word")
    if phone_tier and not parsed.phones:
        missing.append("phone")
    if romanization_tier and not parsed.romanizations:
        missing.append("romanization")
    if missing:
        raise AlignmentError(f"TextGrid is missing requested tier(s): {', '.join(missing)}", work_dir=None)


def _csv_content(parsed: ParsedAlignment) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("tier", "start", "end", "duration", "label"))
    for tier_name, intervals in (
        ("word", parsed.words),
        ("phone", parsed.phones),
        ("romanization", parsed.romanizations),
    ):
        for interval in intervals:
            writer.writerow(
                (tier_name, f"{interval.start:.6f}", f"{interval.end:.6f}", f"{interval.duration:.6f}", interval.label)
            )
    return stream.getvalue()


def _ctm_content(recording_id: str, intervals: tuple[AlignmentInterval, ...]) -> str:
    return "".join(
        f"{recording_id} 1 {item.start:.6f} {item.duration:.6f} {_ctm_token(item.label)}\n"
        for item in intervals
        if item.label
    )


def _ctm_token(text: str) -> str:
    """Encode whitespace/control characters without changing readable Unicode."""
    value: list[str] = []
    for character in text:
        if character == "%" or character.isspace() or not character.isprintable():
            value.extend(f"%{byte:02X}" for byte in character.encode("utf-8"))
        else:
            value.append(character)
    return "".join(value)


def _recording_id(relative_stem: Path) -> str:
    """Create a corpus-unique CTM token while retaining readable Unicode."""
    return _ctm_token(relative_stem.as_posix())


def write_exports(
    textgrid: Path,
    parsed: ParsedAlignment,
    formats: tuple[ExportFormat, ...],
    *,
    audio: Path,
    transcript: Path,
    language: str,
    relative_stem: Path | None = None,
) -> AlignmentOutputs:
    """Write requested exports next to a TextGrid and return their paths."""
    requested = frozenset(formats)
    unknown = requested - {"json", "csv", "ctm"}
    if unknown:
        raise ValueError("exports must contain only: json, csv, ctm")
    paths = planned_export_paths(textgrid, formats)
    recording_id = _recording_id(relative_stem or Path(audio.stem))
    json_path, csv_path, words_ctm, phones_ctm = paths.json, paths.csv, paths.words_ctm, paths.phones_ctm
    if json_path:
        payload = {
            "schema_version": 1,
            "audio": audio.name,
            "transcript": transcript.name,
            "recording_id": recording_id,
            "language": language,
            "duration": parsed.duration,
            "tiers": {
                "word": [vars(item) for item in parsed.words],
                "phone": [vars(item) for item in parsed.phones],
                "romanization": [vars(item) for item in parsed.romanizations],
            },
        }
        atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if csv_path:
        atomic_write_text(csv_path, _csv_content(parsed))
    if words_ctm:
        atomic_write_text(words_ctm, _ctm_content(recording_id, parsed.words))
    if phones_ctm:
        atomic_write_text(phones_ctm, _ctm_content(recording_id, parsed.phones))
    return AlignmentOutputs(textgrid, json_path, csv_path, words_ctm, phones_ctm)


def planned_export_paths(textgrid: Path, formats: tuple[ExportFormat, ...]) -> AlignmentOutputs:
    """Return deterministic output paths without creating any files."""
    requested = frozenset(formats)
    base = textgrid.with_suffix("")
    return AlignmentOutputs(
        textgrid=textgrid,
        json=base.with_name(base.name + ".alignment.json") if "json" in requested else None,
        csv=base.with_name(base.name + ".alignment.csv") if "csv" in requested else None,
        words_ctm=base.with_name(base.name + ".words.ctm") if "ctm" in requested else None,
        phones_ctm=base.with_name(base.name + ".phones.ctm") if "ctm" in requested else None,
    )
