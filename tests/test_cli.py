from pathlib import Path

from koreanfa.cli import build_parser, main


def test_cli_accepts_directory_alignment() -> None:
    args = build_parser().parse_args(["align-dir", "example/kor_files", "-j", "2"])
    assert args.command == "align-dir"
    assert args.num_jobs == 2


def test_cli_accepts_single_alignment() -> None:
    args = build_parser().parse_args(["align", "audio.wav", "audio.txt", "--no-phone"])
    assert args.command == "align"
    assert args.no_phone is True


def test_cli_accepts_engine_commands() -> None:
    args = build_parser().parse_args(["engine", "install", "--force"])
    assert args.command == "engine"
    assert args.engine_command == "install"
    assert args.force is True


def test_align_dir_alias_reaches_engine_validation(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "sample.wav").write_bytes(b"")
    (tmp_path / "sample.txt").write_text("테스트", encoding="utf-8")
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "engine-cache"))

    assert main(["align-dir", str(tmp_path)]) == 2
    assert "koreanfa engine install" in capsys.readouterr().err
