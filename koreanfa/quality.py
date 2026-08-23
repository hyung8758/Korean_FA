"""Heuristic, TextGrid-based alignment quality diagnostics.

These diagnostics identify recordings worth reviewing; they do not estimate
acoustic-model confidence or guarantee alignment accuracy.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from ._io import atomic_write_text, report_output_path
from .result import AlignmentInterval, AlignmentResult, AlignmentSkip, QualityReport, QualitySummary

_SILENCE_LABELS = frozenset({"<sil>", "<sp>", "sil", "sp", "silence"})
_LONG_BOUNDARY_SILENCE_SECONDS = 1.5
_LOW_SPEECH_RATIO = 0.2
_SHORT_WORD_SECONDS = 0.02
_LONG_WORD_SECONDS = 2.0
_SHORT_PHONE_SECONDS = 0.01
_LONG_PHONE_SECONDS = 0.5
_OUTLIER_ROBUST_Z = 3.5


@dataclass(frozen=True)
class _QualityFlag:
    code: str
    message: str
    value: float
    threshold: float

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": "warning",
            "message": self.message,
            "value": round(self.value, 6),
            "threshold": round(self.threshold, 6),
        }


@dataclass
class _QualityItem:
    textgrid: Path
    language: str
    source: str
    attempts: int
    metrics: dict[str, float | int | None]
    flags: list[_QualityFlag]


def write_quality_report(
    destination: str | Path,
    *,
    results: tuple[AlignmentResult, ...],
    skipped: tuple[AlignmentSkip, ...],
    output_dir: Path,
) -> QualityReport:
    """Write an atomic diagnostic report for completed or reused TextGrids."""
    path = report_output_path(destination)
    items = [_quality_item(result, "aligned") for result in results]
    items.extend(_quality_item(item, "existing") for item in skipped)
    _add_corpus_outliers(items)
    items.sort(key=lambda item: item.textgrid.as_posix())
    review_count = sum(bool(item.flags) for item in items)
    summary = QualitySummary(len(items), len(items) - review_count, review_count)
    payload = {
        "schema_version": 1,
        "kind": "heuristic_alignment_quality",
        "summary": {
            "total": summary.total,
            "clean": summary.clean,
            "review": summary.review,
        },
        "items": [_item_payload(item, output_dir) for item in items],
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return QualityReport(path, 1, summary)


def _quality_item(item: AlignmentResult | AlignmentSkip, source: str) -> _QualityItem:
    words = tuple(interval for interval in item.words if not _is_silence(interval))
    phones = tuple(interval for interval in item.phones if not _is_silence(interval))
    boundary_tier = item.words or item.phones
    speech_intervals = words if item.words else phones
    duration = item.duration
    speech_seconds = sum(interval.duration for interval in speech_intervals)
    metrics: dict[str, float | int | None] = {
        "duration_seconds": _round(duration),
        "speech_seconds": _round(speech_seconds) if speech_intervals else None,
        "speech_ratio": _round(speech_seconds / duration) if duration and speech_intervals else None,
        "leading_silence_seconds": _round(_leading_silence(boundary_tier)),
        "trailing_silence_seconds": _round(_trailing_silence(boundary_tier)),
        "spoken_word_count": len(words) if item.words else None,
        "spoken_phone_count": len(phones) if item.phones else None,
        "words_per_speech_second": _round(len(words) / speech_seconds) if words and speech_seconds else None,
        "short_word_count": _count_short(words, _SHORT_WORD_SECONDS) if item.words else None,
        "long_word_count": _count_long(words, _LONG_WORD_SECONDS) if item.words else None,
        "short_phone_count": _count_short(phones, _SHORT_PHONE_SECONDS) if item.phones else None,
        "long_phone_count": _count_long(phones, _LONG_PHONE_SECONDS) if item.phones else None,
    }
    attempts = item.attempts if isinstance(item, AlignmentResult) else 0
    flags = _individual_flags(metrics, attempts)
    return _QualityItem(item.textgrid, item.language, source, attempts, metrics, flags)


def _individual_flags(metrics: dict[str, float | int | None], attempts: int) -> list[_QualityFlag]:
    flags: list[_QualityFlag] = []
    _append_if_above(
        flags,
        "leading_silence.long",
        "Leading silence is longer than the review threshold.",
        metrics["leading_silence_seconds"],
        _LONG_BOUNDARY_SILENCE_SECONDS,
    )
    _append_if_above(
        flags,
        "trailing_silence.long",
        "Trailing silence is longer than the review threshold.",
        metrics["trailing_silence_seconds"],
        _LONG_BOUNDARY_SILENCE_SECONDS,
    )
    speech_ratio = metrics["speech_ratio"]
    if isinstance(speech_ratio, float) and speech_ratio < _LOW_SPEECH_RATIO:
        flags.append(
            _QualityFlag(
                "speech_ratio.low",
                "Aligned speech covers a small fraction of the recording.",
                speech_ratio,
                _LOW_SPEECH_RATIO,
            )
        )
    _append_if_positive(
        flags,
        "word.duration.short",
        "One or more spoken words are shorter than the review threshold.",
        metrics["short_word_count"],
        _SHORT_WORD_SECONDS,
    )
    _append_if_positive(
        flags,
        "word.duration.long",
        "One or more spoken words are longer than the review threshold.",
        metrics["long_word_count"],
        _LONG_WORD_SECONDS,
    )
    _append_if_positive(
        flags,
        "phone.duration.short",
        "One or more non-silence phones are shorter than the review threshold.",
        metrics["short_phone_count"],
        _SHORT_PHONE_SECONDS,
    )
    _append_if_positive(
        flags,
        "phone.duration.long",
        "One or more non-silence phones are longer than the review threshold.",
        metrics["long_phone_count"],
        _LONG_PHONE_SECONDS,
    )
    if attempts > 1:
        flags.append(
            _QualityFlag(
                "alignment.retried",
                "The alignment required more than one Kaldi attempt.",
                float(attempts),
                1.0,
            )
        )
    return flags


def _append_if_above(
    flags: list[_QualityFlag], code: str, message: str, value: float | int | None, threshold: float
) -> None:
    if isinstance(value, (float, int)) and value > threshold:
        flags.append(_QualityFlag(code, message, float(value), threshold))


def _append_if_positive(
    flags: list[_QualityFlag], code: str, message: str, value: float | int | None, threshold: float
) -> None:
    if isinstance(value, int) and value > 0:
        flags.append(_QualityFlag(code, message, float(value), threshold))


def _add_corpus_outliers(items: list[_QualityItem]) -> None:
    """Flag robust duration-rate outliers only when a corpus is large enough."""
    for metric, code, message in (
        ("speech_ratio", "speech_ratio.outlier", "Speech coverage is a corpus-level outlier."),
        ("words_per_speech_second", "speech_rate.outlier", "Speech rate is a corpus-level outlier."),
    ):
        observations = [
            (item, float(value))
            for item in items
            if isinstance((value := item.metrics[metric]), (float, int))
        ]
        if len(observations) < 5:
            continue
        center = median(value for _, value in observations)
        spread = median(abs(value - center) for _, value in observations)
        if spread <= 1e-12:
            continue
        scale = 1.4826 * spread
        for item, value in observations:
            score = abs(value - center) / scale
            if score > _OUTLIER_ROBUST_Z:
                item.flags.append(_QualityFlag(code, message, value, _OUTLIER_ROBUST_Z))


def _item_payload(item: _QualityItem, output_dir: Path) -> dict[str, object]:
    try:
        textgrid = item.textgrid.resolve().relative_to(output_dir.resolve()).as_posix()
    except ValueError:
        textgrid = item.textgrid.name
    return {
        "textgrid": textgrid,
        "language": item.language,
        "source": item.source,
        "attempts": item.attempts,
        "status": "review" if item.flags else "clean",
        "metrics": item.metrics,
        "flags": [flag.as_dict() for flag in item.flags],
    }


def _is_silence(interval: AlignmentInterval) -> bool:
    return interval.label.strip().casefold() in _SILENCE_LABELS


def _leading_silence(intervals: tuple[AlignmentInterval, ...]) -> float | None:
    if intervals and _is_silence(intervals[0]):
        return intervals[0].duration
    return 0.0 if intervals else None


def _trailing_silence(intervals: tuple[AlignmentInterval, ...]) -> float | None:
    if intervals and _is_silence(intervals[-1]):
        return intervals[-1].duration
    return 0.0 if intervals else None


def _count_short(intervals: tuple[AlignmentInterval, ...], threshold: float) -> int:
    return sum(interval.duration < threshold for interval in intervals)


def _count_long(intervals: tuple[AlignmentInterval, ...], threshold: float) -> int:
    return sum(interval.duration > threshold for interval in intervals)


def _round(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None
