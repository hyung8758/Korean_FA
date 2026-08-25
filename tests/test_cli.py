from collections.abc import Callable
from pathlib import Path

import pytest

from koreanfa import __version__
from koreanfa.cli import build_parser, main
from koreanfa.errors import EngineUnavailableError
from koreanfa.result import AlignmentFailure, BatchAlignmentResult


def test_cli_accepts_directory_alignment() -> None:
    args = build_parser().parse_args(["align-dir", "example/kor_files", "-l", "kor", "-nj", "2", "-iu"])
    assert args.command == "align-dir"
    assert args.lang == "kor"
    assert args.num_jobs == 2
    assert args.ignore_unmatched is True


def test_cli_defaults_to_four_parallel_files() -> None:
    args = build_parser().parse_args(["align-dir", "example/kor_files"])
    assert args.num_jobs == 4
    assert args.ignore_unmatched is True


def test_cli_accepts_an_explicit_ignore_unmatched_value() -> None:
    args = build_parser().parse_args(["align-dir", "example/kor_files", "--ignore-unmatched", "false"])
    assert args.ignore_unmatched is False


def test_cli_stops_cleanly_for_unmatched_files_when_disabled(tmp_path: Path, capsys) -> None:
    (tmp_path / "paired.wav").write_bytes(b"")
    (tmp_path / "paired.txt").write_text("테스트", encoding="utf-8")
    (tmp_path / "orphan.wav").write_bytes(b"")

    assert main(["align-dir", str(tmp_path), "--ignore-unmatched", "false"]) == 2

    captured = capsys.readouterr()
    assert "Unmatched corpus files" in captured.err
    assert "Traceback" not in captured.err


def test_align_dir_reports_a_missing_directory_as_a_directory_error(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing-corpus"

    assert main(["align-dir", str(missing)]) == 2

    captured = capsys.readouterr()
    assert "Input directory does not exist" in captured.err
    assert "requires its matching TXT" not in captured.err


def test_cli_reports_partial_batch_failures_without_a_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    audio = tmp_path / "rejected.wav"
    transcript = tmp_path / "rejected.txt"
    audio.write_bytes(b"")
    transcript.write_text("<laugh>", encoding="utf-8")
    result = BatchAlignmentResult(
        (), tmp_path, failures=(AlignmentFailure(audio, transcript, "jap", "no alignable entries"),),
    )
    monkeypatch.setattr("koreanfa.cli.Aligner.align", lambda *_args, **_kwargs: result)

    assert main(["align-dir", str(tmp_path), "--lang", "jap"]) == 2

    captured = capsys.readouterr()
    assert "failed rejected.wav: no alignable entries" in captured.err
    assert "Traceback" not in captured.err


def test_cli_supports_short_version_option(capsys) -> None:
    with pytest.raises(SystemExit, match="0"):
        build_parser().parse_args(["-v"])
    assert f"koreanfa {__version__}" in capsys.readouterr().out


def test_cli_accepts_single_alignment() -> None:
    args = build_parser().parse_args(["align", "audio.wav", "audio.txt", "-np"])
    assert args.command == "align"
    assert args.no_phone is True


def test_cli_accepts_workflow_outputs_and_validation_options() -> None:
    align_args = build_parser().parse_args(
        [
            "align", "corpus", "--existing", "skip", "--export", "json", "--export", "ctm",
            "--report", "run.json", "--quality-report", "quality.json",
        ]
    )
    validate_args = build_parser().parse_args(
        [
            "validate", "corpus", "--recursive", "--strict", "--no-engine-check", "--report", "validation.json",
            "--pronunciation-dictionary", "dictionary.tsv",
        ]
    )

    assert align_args.existing == "skip"
    assert align_args.exports == ["json", "ctm"]
    assert align_args.report == Path("run.json")
    assert align_args.quality_report == Path("quality.json")
    assert validate_args.recursive is True
    assert validate_args.strict is True
    assert validate_args.no_engine_check is True
    assert validate_args.pronunciation_dictionary == Path("dictionary.tsv")


def test_cli_supports_short_forms_for_every_alignment_option() -> None:
    args = build_parser().parse_args(
        [
            "align-dir", "corpus", "-l", "jap", "-o", "output", "-kd", "kaldi", "-nj", "3",
            "-r", "-iu", "-nw", "-np", "-nr", "-kw",
        ]
    )

    assert args.lang == "jap"
    assert args.output_dir == Path("output")
    assert args.kaldi_dir == Path("kaldi")
    assert args.num_jobs == 3
    assert args.recursive is True
    assert args.ignore_unmatched is True
    assert args.no_word is True
    assert args.no_phone is True
    assert args.no_romanization is True
    assert args.keep_workdir is True


@pytest.mark.parametrize("legacy_option", ["-j", "--allow-unmatched", "--strict-unmatched"])
def test_cli_rejects_removed_legacy_alignment_options(legacy_option: str) -> None:
    with pytest.raises(SystemExit, match="2"):
        build_parser().parse_args(["align-dir", "corpus", legacy_option])


def test_cli_accepts_engine_commands() -> None:
    args = build_parser().parse_args(["engine", "install", "-f"])
    assert args.command == "engine"
    assert args.engine_command == "install"
    assert args.force is True

    remove_args = build_parser().parse_args(["engine", "remove", "-y"])
    assert remove_args.yes is True


def test_cli_reports_engine_download_progress_and_actionable_failure(monkeypatch, capsys) -> None:
    def failed_install(*, force: bool, progress) -> None:
        assert force is False
        progress("downloading engine (attempt 1/3)...")
        progress("checksum verification failed on attempt 1/3; retrying...")
        raise EngineUnavailableError(
            "KoreanFA engine checksum mismatch after 3 download attempts. "
            "Please try again later or see docs/troubleshooting.md."
        )

    monkeypatch.setattr("koreanfa.cli.install_engine", failed_install)

    assert main(["engine", "install"]) == 2

    captured = capsys.readouterr()
    assert "downloading engine (attempt 1/3)" in captured.err
    assert "checksum verification failed" in captured.err
    assert "koreanfa: error:" in captured.err
    assert "try again later" in captured.err
    assert "docs/troubleshooting.md" in captured.err
    assert captured.out == ""


def test_cli_explains_unsupported_glibc_before_downloading(
    tmp_path: Path, monkeypatch, capsys, write_test_manifest: Callable[..., Path]
) -> None:
    monkeypatch.setattr("koreanfa._engine_config.platform.system", lambda: "Linux")
    monkeypatch.setattr("koreanfa._engine_config.platform.machine", lambda: "x86_64")
    monkeypatch.setattr(
        "koreanfa._engine_config.linux_libc", lambda: ("glibc", (2, 16))
    )
    manifest = write_test_manifest(
        tmp_path,
        url="https://example.invalid/engine.tar.gz",
        sha256="0" * 64,
        minimum_glibc="2.17",
    )
    monkeypatch.setenv("KOREANFA_ENGINE_MANIFEST", str(manifest))
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "cache"))

    assert main(["engine", "install"]) == 2

    captured = capsys.readouterr()
    assert "koreanfa: error:" in captured.err
    assert "requires x86_64 Linux with glibc 2.17 or later" in captured.err
    assert "detected glibc 2.16" in captured.err
    assert "downloading engine" not in captured.err
    assert captured.out == ""


def test_align_dir_alias_reaches_engine_validation(
    tmp_path: Path, monkeypatch, capsys, write_test_manifest: Callable[..., Path]
) -> None:
    (tmp_path / "sample.wav").write_bytes(b"")
    (tmp_path / "sample.txt").write_text("테스트", encoding="utf-8")
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "engine-cache"))
    manifest = write_test_manifest(tmp_path, url=None, sha256=None)
    monkeypatch.setenv("KOREANFA_ENGINE_MANIFEST", str(manifest))

    assert main(["align-dir", str(tmp_path)]) == 2
    assert "koreanfa engine install" in capsys.readouterr().err


def test_cli_writes_validation_errors_to_standard_error(tmp_path: Path, capsys) -> None:
    audio = tmp_path / "sample.wav"
    transcript = tmp_path / "sample.txt"
    audio.write_bytes(b"")
    transcript.write_text("테스트", encoding="utf-8")

    assert main(["align", str(audio), str(transcript), "--no-word", "--no-phone"]) == 2

    captured = capsys.readouterr()
    assert "At least one" in captured.err
    assert captured.out == ""


def test_cli_reports_filesystem_errors_without_a_traceback(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("koreanfa.cli.validate", lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("denied")))

    assert main(["validate", str(tmp_path)]) == 2

    captured = capsys.readouterr()
    assert "koreanfa: error: denied" in captured.err
    assert "Traceback" not in captured.err
