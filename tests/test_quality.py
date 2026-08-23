import json
from pathlib import Path

from koreanfa.quality import write_quality_report
from koreanfa.result import AlignmentInterval, AlignmentResult, AlignmentSkip


def _result(
    root: Path,
    name: str,
    *,
    duration: float,
    words: tuple[AlignmentInterval, ...],
    phones: tuple[AlignmentInterval, ...] = (),
    attempts: int = 1,
) -> AlignmentResult:
    audio = root / "input" / f"{name}.wav"
    transcript = root / "input" / f"{name}.txt"
    textgrid = root / "output" / f"{name}.TextGrid"
    return AlignmentResult(audio, transcript, textgrid, "kor", duration=duration, words=words, phones=phones, attempts=attempts)


def test_quality_report_marks_reviewable_silence_duration_and_retry(tmp_path: Path) -> None:
    words = (
        AlignmentInterval(0.0, 2.0, "<SIL>"),
        AlignmentInterval(2.0, 2.01, "가"),
        AlignmentInterval(2.01, 2.8, "나"),
        AlignmentInterval(2.8, 4.5, "<sil>"),
    )
    phones = (
        AlignmentInterval(0.0, 2.0, "<SIL>"),
        AlignmentInterval(2.0, 2.005, "k0"),
        AlignmentInterval(2.005, 2.8, "aa"),
        AlignmentInterval(2.8, 4.5, "<SIL>"),
    )
    report_path = tmp_path / "output" / "quality.json"
    report = write_quality_report(
        report_path,
        results=(_result(tmp_path, "sample", duration=4.5, words=words, phones=phones, attempts=2),),
        skipped=(),
        output_dir=tmp_path / "output",
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    item = payload["items"][0]
    assert report.summary.clean == 0 and report.summary.review == 1
    assert item["textgrid"] == "sample.TextGrid"
    assert item["status"] == "review"
    assert item["metrics"]["spoken_word_count"] == 2
    assert {flag["code"] for flag in item["flags"]} >= {
        "leading_silence.long",
        "trailing_silence.long",
        "word.duration.short",
        "phone.duration.short",
        "phone.duration.long",
        "alignment.retried",
    }
    assert str(tmp_path) not in report_path.read_text(encoding="utf-8")


def test_quality_report_uses_existing_source_without_a_retry_warning(tmp_path: Path) -> None:
    words = (AlignmentInterval(0.0, 1.0, "테스트"),)
    skipped = AlignmentSkip(
        tmp_path / "input.wav",
        tmp_path / "input.txt",
        tmp_path / "output" / "input.TextGrid",
        "kor",
        duration=1.0,
        words=words,
    )
    path = tmp_path / "output" / "quality.json"

    report = write_quality_report(path, results=(), skipped=(skipped,), output_dir=tmp_path / "output")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert report.summary.clean == 1
    assert payload["items"][0]["source"] == "existing"
    assert not payload["items"][0]["flags"]


def test_quality_report_marks_corpus_speech_rate_outliers(tmp_path: Path) -> None:
    durations = (1.0, 0.9, 1.1, 0.8, 0.2)
    results = tuple(
        _result(
            tmp_path,
            f"sample-{index}",
            duration=duration,
            words=(AlignmentInterval(0.0, duration, "테스트"),),
        )
        for index, duration in enumerate(durations)
    )
    path = tmp_path / "output" / "quality.json"

    write_quality_report(path, results=results, skipped=(), output_dir=tmp_path / "output")

    payload = json.loads(path.read_text(encoding="utf-8"))
    outliers = [item for item in payload["items"] if item["textgrid"] == "sample-4.TextGrid"]
    assert {flag["code"] for flag in outliers[0]["flags"]} >= {"speech_rate.outlier"}


def test_quality_report_uses_phone_metrics_when_the_word_tier_is_omitted(tmp_path: Path) -> None:
    phones = (
        AlignmentInterval(0.0, 0.2, "<sil>"),
        AlignmentInterval(0.2, 0.8, "a"),
        AlignmentInterval(0.8, 1.0, "<sil>"),
    )
    path = tmp_path / "output" / "quality.json"

    write_quality_report(
        path,
        results=(_result(tmp_path, "phone-only", duration=1.0, words=(), phones=phones),),
        skipped=(),
        output_dir=tmp_path / "output",
    )

    item = json.loads(path.read_text(encoding="utf-8"))["items"][0]
    assert item["metrics"]["spoken_word_count"] is None
    assert item["metrics"]["spoken_phone_count"] == 1
    assert item["metrics"]["speech_ratio"] == 0.6
