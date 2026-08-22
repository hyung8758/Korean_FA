import json
from collections.abc import Callable
from pathlib import Path

import pytest

from koreanfa.cli import main
from koreanfa.validation import ValidationIssue, ValidationReport, validate


def test_validation_collects_multiple_pair_problems(tmp_path: Path, write_wav: Callable[[Path], Path]) -> None:
    write_wav(tmp_path / "good.wav")
    (tmp_path / "good.txt").write_text("한국어 문장", encoding="utf-8")
    (tmp_path / "broken.wav").write_bytes(b"not a wav")
    (tmp_path / "broken.txt").write_bytes(b"\xff\xfe")
    write_wav(tmp_path / "orphan.wav")

    report = validate(tmp_path, check_engine=False)

    assert not report.valid
    assert {issue.code for issue in report.issues} >= {
        "audio.invalid", "transcript.invalid_utf8", "pair.missing_transcript",
    }
    assert len(report.pairs) == 1
    assert report.pairs[0].language == "kor"


def test_validation_lists_every_orphan_when_only_one_file_type_exists(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    write_wav(tmp_path / "first.wav")
    write_wav(tmp_path / "second.wav")

    report = validate(tmp_path, check_engine=False)

    assert not report.valid
    assert [issue.code for issue in report.issues] == [
        "corpus.no_pairs", "pair.missing_transcript", "pair.missing_transcript",
    ]
    assert {
        issue.path.name for issue in report.issues if issue.code == "pair.missing_transcript" and issue.path
    } == {"first.wav", "second.wav"}


def test_validation_rejects_empty_corpus(tmp_path: Path) -> None:
    report = validate(tmp_path, check_engine=False)

    assert not report.valid
    assert [issue.code for issue in report.issues] == ["corpus.empty"]


def test_validation_preserves_actual_case_of_unmatched_file_paths(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    audio = write_wav(tmp_path / "ORPHAN.WAV")

    report = validate(tmp_path, check_engine=False)
    orphan = next(issue for issue in report.issues if issue.code == "pair.missing_transcript")

    assert orphan.path == audio.resolve()
    assert orphan.path.is_file()


def test_validation_report_uses_relative_paths_and_no_transcript_content(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    write_wav(tmp_path / "sample.wav")
    secret_text = "외부에 복사하지 않을 원문"
    (tmp_path / "sample.txt").write_text(secret_text, encoding="utf-8")
    destination = tmp_path / "validation.json"

    report = validate(tmp_path, check_engine=False, report_path=destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))

    assert report.valid
    assert payload["pairs"][0]["audio"] == "sample.wav"
    assert str(tmp_path) not in destination.read_text(encoding="utf-8")
    assert secret_text not in destination.read_text(encoding="utf-8")


def test_cli_validate_succeeds_without_engine_check(
    tmp_path: Path, write_wav: Callable[[Path], Path], capsys
) -> None:
    write_wav(tmp_path / "sample.wav")
    (tmp_path / "sample.txt").write_text("日本語です", encoding="utf-8")

    assert main(["validate", str(tmp_path), "--no-engine-check"]) == 0
    captured = capsys.readouterr()
    assert "pairs=1 errors=0 warnings=0 valid=true" in captured.out


def test_validation_reports_korean_oov_tokens_without_persisting_transcript_content(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    audio = write_wav(tmp_path / "sample.wav")
    transcript = tmp_path / "sample.txt"
    transcript.write_text("KoreanFA", encoding="utf-8")
    report_path = tmp_path / "validation.json"

    report = validate(audio, transcript, lang="kor", check_engine=False, report_path=report_path)

    oov = next(issue for issue in report.issues if issue.code == "transcript.oov")
    assert oov.details == ("KoreanFA",)
    assert "KoreanFA" not in report_path.read_text(encoding="utf-8")


def test_validation_uses_korean_dictionary_to_clear_an_oov(tmp_path: Path, write_wav: Callable[[Path], Path]) -> None:
    audio = write_wav(tmp_path / "sample.wav")
    transcript = tmp_path / "sample.txt"
    transcript.write_text("KoreanFA", encoding="utf-8")
    dictionary = tmp_path / "dictionary.tsv"
    dictionary.write_text("language\tword\tpronunciation\nkor\tKoreanFA\t코리안에프에이\n", encoding="utf-8")

    report = validate(audio, transcript, lang="kor", check_engine=False, pronunciation_dictionary=dictionary)

    assert not any(issue.code == "transcript.oov" for issue in report.issues)
    assert report.valid


def test_validation_returns_a_structured_error_for_an_invalid_dictionary(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    dictionary = tmp_path / "dictionary.tsv"
    dictionary.write_text("kor\tword\t발음\n", encoding="utf-8")
    audio = write_wav(tmp_path / "sample.wav")
    transcript = tmp_path / "sample.txt"
    transcript.write_text("KoreanFA", encoding="utf-8")

    report = validate(audio, transcript, lang="kor", check_engine=False, pronunciation_dictionary=dictionary)

    assert {issue.code for issue in report.issues} == {
        "pronunciation_dictionary.invalid",
        "language.undetermined",
    }
    assert not any(issue.code == "transcript.oov" for issue in report.issues)


def test_validation_report_cannot_overwrite_an_input(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    audio = write_wav(tmp_path / "sample.wav")
    transcript = tmp_path / "sample.txt"
    transcript.write_text("테스트", encoding="utf-8")
    original = audio.read_bytes()

    with pytest.raises(ValueError, match="must not overwrite an input"):
        validate(audio, transcript, check_engine=False, report_path=audio)
    with pytest.raises(ValueError, match="must not overwrite an input"):
        validate(audio, transcript, check_engine=False, report_path=tmp_path / "SAMPLE.WAV")
    assert audio.read_bytes() == original


def test_invalid_validation_report_does_not_leak_absolute_root(tmp_path: Path) -> None:
    (tmp_path / "broken.wav").write_bytes(b"broken")
    (tmp_path / "broken.txt").write_bytes(b"\xff")
    destination = tmp_path / "invalid-validation.json"

    validate(tmp_path, check_engine=False, report_path=destination)

    assert str(tmp_path) not in destination.read_text(encoding="utf-8")


def test_validation_report_symlink_does_not_overwrite_its_target(tmp_path: Path) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("keep", encoding="utf-8")
    destination = tmp_path / "validation.json"
    destination.symlink_to(target)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        validate(tmp_path, check_engine=False, report_path=destination)

    assert target.read_text(encoding="utf-8") == "keep"


def test_ambiguous_corpus_report_cannot_overwrite_an_input(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    audio = write_wav(tmp_path / "sample.wav")
    duplicate = tmp_path / "sample.WAV"
    duplicate.write_bytes(audio.read_bytes())
    original = audio.read_bytes()

    with pytest.raises(ValueError, match="must not overwrite an input"):
        validate(tmp_path, check_engine=False, report_path=audio)

    assert audio.read_bytes() == original


def test_validation_report_redacts_known_external_issue_path(tmp_path: Path) -> None:
    external = tmp_path.parent / "private" / "secret.wav"
    external.parent.mkdir(exist_ok=True)
    report = ValidationReport(
        tmp_path,
        (),
        (
            ValidationIssue(
                "audio.unreadable", "error", external,
                f"Failed reading {external}", f"Replace {external} and retry.",
            ),
        ),
        None,
        None,
        None,
    )
    destination = tmp_path / "validation.json"

    report.write_json(destination)
    content = destination.read_text(encoding="utf-8")

    assert str(external) not in content
    assert "secret.wav" in content
