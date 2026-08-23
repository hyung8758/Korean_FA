import json
from collections.abc import Callable
from pathlib import Path

import pytest

from koreanfa._alignment_outputs import publish_file as _publish_file
from koreanfa._alignment_outputs import publish_output_set as _publish_output_set
from koreanfa._workflow import align_pairs as _align_pairs
from koreanfa.api import align_directory
from koreanfa.errors import AlignmentError
from koreanfa.pairing import _textgrid_relative_path
from koreanfa.reporting import write_execution_report
from koreanfa.result import AlignmentFailure, AlignmentResult, AlignmentSummary, InputPair


def _pair(root: Path) -> InputPair:
    audio = root / "source" / "sample.wav"
    transcript = root / "source" / "sample.txt"
    audio.parent.mkdir()
    audio.write_bytes(b"audio")
    transcript.write_text("테스트", encoding="utf-8")
    return InputPair(audio, transcript, Path("nested/sample"), "kor")


def _fake_runtime(write_textgrid: Callable[..., Path]):
    def run(pairs, _language, output_dir, *_args):
        results = []
        for pair in pairs:
            textgrid = write_textgrid(output_dir / pair.relative_stem.with_suffix(".TextGrid"))
            results.append(AlignmentResult(pair.audio, pair.transcript, textgrid, pair.language, attempts=2))
        return results, [], None

    return run


def test_skip_valid_existing_output_without_resolving_engine(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    output = tmp_path / "output"
    existing = write_textgrid(output / "nested/sample.TextGrid")
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: pytest.fail("engine must not be resolved"))

    result = _align_pairs(
        (pair,), output, None, 1, True, True, False, None, existing="skip", exports=("json", "ctm"),
        input_root=pair.audio.parent, report_path=output / "run.json", quality_report_path=output / "quality.json",
    )

    assert result.results == ()
    assert result.skipped[0].textgrid == existing
    assert result.skipped[0].duration == 1.0
    assert result.skipped[0].words and result.skipped[0].phones
    assert result.skipped[0].outputs is not None
    assert result.skipped[0].outputs["json"].is_file()
    assert result.skipped[0].outputs["words_ctm"].is_file()
    assert result.skipped[0].outputs["phones_ctm"].is_file()
    assert result.summary and result.summary.skipped == 1
    report_item = json.loads((output / "run.json").read_text(encoding="utf-8"))["items"][0]
    assert report_item["status"] == "skipped" and report_item["attempts"] == 0
    assert result.quality_report is not None and result.quality_report.summary.review == 1
    quality_item = json.loads((output / "quality.json").read_text(encoding="utf-8"))["items"][0]
    assert quality_item["source"] == "existing" and quality_item["attempts"] == 0
    assert {flag["code"] for flag in quality_item["flags"]} == {"phone.duration.long"}


def test_error_policy_fails_before_alignment(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    output = tmp_path / "output"
    write_textgrid(output / "nested/sample.TextGrid")
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: pytest.fail("engine must not be resolved"))

    with pytest.raises(AlignmentError, match="Output already exists"):
        _align_pairs((pair,), output, None, 1, True, True, False, None, existing="error")


def test_invalid_existing_output_is_realigned_and_exports_and_report_are_published(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    output = tmp_path / "output"
    invalid = output / "nested/sample.TextGrid"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("broken", encoding="utf-8")
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: (tmp_path / "engine", {}))
    monkeypatch.setattr("koreanfa._workflow.runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr("koreanfa._workflow.run_language_group", _fake_runtime(write_textgrid))
    report_path = output / "run.json"
    quality_path = output / "quality.json"

    batch = _align_pairs(
        (pair,), output, None, 1, True, True, False, None, existing="skip",
        exports=("json", "csv", "ctm"), report_path=report_path, quality_report_path=quality_path,
        input_root=pair.audio.parent,
    )

    assert len(batch.results) == 1
    result = batch.results[0]
    assert result.duration == 1.0
    assert result.words[0].label == "테스트"
    assert result.attempts == 2
    assert result.outputs is not None
    assert all(path.is_file() for path in (
        result.outputs.textgrid, result.outputs["json"], result.outputs["csv"],
        result.outputs["words_ctm"], result.outputs["phones_ctm"],
    ))
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["succeeded"] == 1
    assert payload["summary"]["failed"] == 0
    assert payload["summary"]["skipped"] == 0
    assert payload["summary"]["elapsed_seconds"] >= 0
    assert payload["engine"]["source"] == "managed"
    assert payload["items"][0]["audio"] == "sample.wav"
    assert str(tmp_path) not in report_path.read_text(encoding="utf-8")
    assert batch.quality_report is not None and batch.quality_report.summary.review == 1
    quality_item = json.loads(quality_path.read_text(encoding="utf-8"))["items"][0]
    assert {flag["code"] for flag in quality_item["flags"]} == {
        "alignment.retried",
        "phone.duration.long",
    }


def test_execution_report_cannot_overwrite_an_input_or_alignment_output(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    output = tmp_path / "output"
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: (tmp_path / "engine", {}))
    monkeypatch.setattr("koreanfa._workflow.runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr("koreanfa._workflow.run_language_group", _fake_runtime(write_textgrid))

    for forbidden in (pair.audio, output / "nested/sample.TextGrid"):
        with pytest.raises(ValueError, match="must not overwrite"):
            _align_pairs(
                (pair,), output, None, 1, True, True, False, None,
                report_path=forbidden, input_root=pair.audio.parent,
            )

    with pytest.raises(ValueError, match="must not overwrite"):
        _align_pairs(
            (pair,), output, None, 1, True, True, False, None,
            report_path=output / "nested/SAMPLE.textgrid", input_root=pair.audio.parent,
        )

    with pytest.raises(ValueError, match="must be different"):
        _align_pairs(
            (pair,), output, None, 1, True, True, False, None,
            report_path=output / "run.json", quality_report_path=output / "run.json", input_root=pair.audio.parent,
        )

    with pytest.raises(ValueError, match="must not overwrite"):
        _align_pairs(
            (pair,), output, None, 1, True, True, False, None,
            quality_report_path=pair.audio, input_root=pair.audio.parent,
        )


def test_malformed_runtime_textgrid_is_a_file_failure_while_valid_output_is_published(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _pair(tmp_path)
    second_audio = first.audio.with_name("second.wav")
    second_text = first.transcript.with_name("second.txt")
    second_audio.write_bytes(b"audio")
    second_text.write_text("테스트", encoding="utf-8")
    second = InputPair(second_audio, second_text, Path("nested/second"), "kor")
    output = tmp_path / "output"

    def malformed_runtime(pairs, _language, output_dir, *_args):
        valid = write_textgrid(output_dir / pairs[0].relative_stem.with_suffix(".TextGrid"))
        invalid = output_dir / pairs[1].relative_stem.with_suffix(".TextGrid")
        invalid.parent.mkdir(parents=True, exist_ok=True)
        invalid.write_text("broken", encoding="utf-8")
        return [
            AlignmentResult(pairs[0].audio, pairs[0].transcript, valid, "kor"),
            AlignmentResult(pairs[1].audio, pairs[1].transcript, invalid, "kor", attempts=2),
        ], [], None

    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: (tmp_path / "engine", {}))
    monkeypatch.setattr("koreanfa._workflow.runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr("koreanfa._workflow.run_language_group", malformed_runtime)

    result = _align_pairs((first, second), output, None, 1, True, True, False, None)

    assert len(result.results) == 1 and len(result.failures) == 1
    assert result.failures[0].audio == second.audio
    assert result.failures[0].attempts == 2
    assert "Could not prepare alignment outputs" in result.failures[0].reason
    assert (output / "nested/sample.TextGrid").is_file()
    assert not (output / "nested/second.TextGrid").exists()


def test_runtime_textgrid_missing_requested_tier_is_a_file_failure(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    output = tmp_path / "output"

    def phone_only_runtime(pairs, _language, output_dir, *_args):
        textgrid = write_textgrid(
            output_dir / _textgrid_relative_path(pairs[0].relative_stem), word=False, phone=True
        )
        return [AlignmentResult(pairs[0].audio, pairs[0].transcript, textgrid, "kor")], [], None

    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: (tmp_path / "engine", {}))
    monkeypatch.setattr("koreanfa._workflow.runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr("koreanfa._workflow.run_language_group", phone_only_runtime)

    result = _align_pairs((pair,), output, None, 1, True, True, False, None)

    assert not result.results and len(result.failures) == 1
    assert "missing requested tier(s): word" in result.failures[0].reason
    assert not (output / "nested/sample.TextGrid").exists()


def test_partial_failure_report_preserves_success_and_redacts_absolute_paths(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _pair(tmp_path)
    second_audio = first.audio.with_name("failed.wav")
    second_text = first.transcript.with_name("failed.txt")
    second_audio.write_bytes(b"audio")
    second_text.write_text("테스트", encoding="utf-8")
    second = InputPair(second_audio, second_text, Path("nested/failed"), "kor")
    output = tmp_path / "output"
    report_path = output / "report.json"
    external_work_dir = tmp_path.parent / "private-diagnostics"

    def partial_runtime(pairs, _language, output_dir, *_args):
        textgrid = write_textgrid(output_dir / pairs[0].relative_stem.with_suffix(".TextGrid"))
        return [AlignmentResult(pairs[0].audio, pairs[0].transcript, textgrid, "kor")], [
            AlignmentFailure(
                pairs[1].audio, pairs[1].transcript, "kor",
                f"Invalid audio at {pairs[1].audio}; see {external_work_dir}",
                work_dir=external_work_dir, attempts=3,
            )
        ], None

    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: (tmp_path / "engine", {}))
    monkeypatch.setattr("koreanfa._workflow.runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr("koreanfa._workflow.run_language_group", partial_runtime)

    result = _align_pairs(
        (first, second), output, None, 1, True, True, False, None,
        report_path=report_path, input_root=first.audio.parent,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert len(result.results) == 1 and len(result.failures) == 1
    assert payload["summary"] | {"elapsed_seconds": 0} == {
        "total": 2, "succeeded": 1, "failed": 1, "skipped": 0, "elapsed_seconds": 0,
    }
    assert {item["status"] for item in payload["items"]} == {"succeeded", "failed"}
    assert next(item for item in payload["items"] if item["status"] == "failed")["attempts"] == 3
    assert str(tmp_path) not in report_path.read_text(encoding="utf-8")
    assert str(external_work_dir) not in report_path.read_text(encoding="utf-8")


def test_execution_report_symlink_is_rejected_before_engine_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    target = tmp_path / "outside.txt"
    target.write_text("keep", encoding="utf-8")
    report = tmp_path / "run.json"
    report.symlink_to(target)
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: pytest.fail("engine must not be resolved"))

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        _align_pairs((pair,), tmp_path / "output", None, 1, True, True, False, None, report_path=report)

    assert target.read_text(encoding="utf-8") == "keep"


def test_directory_report_cannot_overwrite_an_ignored_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sample.wav").write_bytes(b"audio")
    (tmp_path / "sample.txt").write_text("테스트", encoding="utf-8")
    orphan = tmp_path / "orphan.wav"
    orphan.write_bytes(b"orphan")
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: pytest.fail("engine must not be resolved"))

    with pytest.warns(UserWarning, match="Ignoring unmatched"), pytest.raises(
        ValueError, match="must not overwrite"
    ):
        align_directory(tmp_path, report_path=orphan)

    assert orphan.read_bytes() == b"orphan"


def test_pair_output_publish_rolls_back_new_and_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = tmp_path / "staging"
    output = tmp_path / "output"
    staging.mkdir()
    output.mkdir()
    new_source = staging / "sample.alignment.csv"
    old_source = staging / "sample.alignment.json"
    textgrid_source = staging / "sample.TextGrid"
    new_source.write_text("new csv", encoding="utf-8")
    old_source.write_text("new json", encoding="utf-8")
    textgrid_source.write_text("new grid", encoding="utf-8")
    new_destination = output / new_source.name
    old_destination = output / old_source.name
    textgrid_destination = output / textgrid_source.name
    old_destination.write_text("old json", encoding="utf-8")
    original_publish = _publish_file

    def fail_on_textgrid(source: Path, destination: Path) -> None:
        if destination == textgrid_destination:
            raise OSError("simulated final publish failure")
        original_publish(source, destination)

    monkeypatch.setattr("koreanfa._alignment_outputs.publish_file", fail_on_textgrid)

    with pytest.raises(OSError, match="simulated final publish failure"):
        _publish_output_set(
            (
                (new_source, new_destination),
                (old_source, old_destination),
                (textgrid_source, textgrid_destination),
            ),
            output_dir=output,
        )

    assert not new_destination.exists()
    assert old_destination.read_text(encoding="utf-8") == "old json"
    assert not textgrid_destination.exists()


def test_publish_file_preserves_existing_destination_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.write_text("new", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")
    destination.chmod(0o640)

    _publish_file(source, destination)

    assert destination.read_text(encoding="utf-8") == "new"
    assert destination.stat().st_mode & 0o777 == 0o640


def test_report_directory_is_rejected_before_engine_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    report = tmp_path / "report.json"
    report.mkdir()
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: pytest.fail("engine must not be resolved"))

    with pytest.raises(ValueError, match="exists but is not a file"):
        _align_pairs((pair,), tmp_path / "output", None, 1, True, True, False, None, report_path=report)


def test_skip_export_publish_failure_restores_all_previous_exports(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    pair = _pair(tmp_path)
    output = tmp_path / "output"
    write_textgrid(output / "nested/sample.TextGrid")
    json_path = output / "nested/sample.alignment.json"
    csv_path = output / "nested/sample.alignment.csv"
    json_path.write_text("old json", encoding="utf-8")
    csv_path.write_text("old csv", encoding="utf-8")
    original_publish = _publish_file

    def fail_on_csv(source: Path, destination: Path) -> None:
        if destination == csv_path:
            raise OSError("simulated export publish failure")
        original_publish(source, destination)

    monkeypatch.setattr("koreanfa._alignment_outputs.publish_file", fail_on_csv)
    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: pytest.fail("engine must not be resolved"))

    batch = _align_pairs(
        (pair,), output, None, 1, True, True, False, None, existing="skip", exports=("json", "csv"),
    )

    assert not batch.skipped and len(batch.failures) == 1
    assert "Could not publish exports for skipped output" in batch.failures[0].reason
    assert json_path.read_text(encoding="utf-8") == "old json"
    assert csv_path.read_text(encoding="utf-8") == "old csv"


def test_dotted_stems_publish_to_distinct_textgrid_paths(
    tmp_path: Path, write_textgrid: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    pairs: list[InputPair] = []
    for stem in ("foo", "foo.bar"):
        audio = source / f"{stem}.wav"
        transcript = source / f"{stem}.txt"
        audio.write_bytes(b"audio")
        transcript.write_text("테스트", encoding="utf-8")
        pairs.append(InputPair(audio, transcript, Path(stem), "kor"))

    def runtime(runtime_pairs, _language, output_dir, *_args):
        results = []
        for pair in runtime_pairs:
            textgrid = write_textgrid(output_dir / _textgrid_relative_path(pair.relative_stem))
            results.append(AlignmentResult(pair.audio, pair.transcript, textgrid, pair.language))
        return results, [], None

    monkeypatch.setattr("koreanfa._workflow.resolve_kaldi_dir", lambda *_args: (tmp_path / "engine", {}))
    monkeypatch.setattr("koreanfa._workflow.runtime_root", lambda: tmp_path / "runtime")
    monkeypatch.setattr("koreanfa._workflow.run_language_group", runtime)

    batch = _align_pairs(tuple(pairs), tmp_path / "output", None, 1, True, True, False, None)

    assert {result.textgrid.name for result in batch.results} == {"foo.TextGrid", "foo.bar.TextGrid"}


def test_execution_report_preserves_lexical_relative_path_for_symlink_input(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    nested = corpus / "nested"
    nested.mkdir(parents=True)
    external_audio = tmp_path / "external.wav"
    external_audio.write_bytes(b"audio")
    audio = nested / "sample.wav"
    audio.symlink_to(external_audio)
    transcript = nested / "sample.txt"
    transcript.write_text("테스트", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    textgrid = output / "nested/sample.TextGrid"
    textgrid.parent.mkdir()
    textgrid.write_text("grid", encoding="utf-8")
    report = output / "run.json"
    summary = AlignmentSummary(1, 1, 0, 0, 0.1)

    write_execution_report(
        report,
        input_root=corpus,
        output_dir=output,
        results=(AlignmentResult(audio, transcript, textgrid, "kor"),),
        failures=(),
        skipped=(),
        summary=summary,
        options={},
        engine_source="external",
    )

    item = json.loads(report.read_text(encoding="utf-8"))["items"][0]
    assert item["audio"] == "nested/sample.wav"
    assert item["transcript"] == "nested/sample.txt"
