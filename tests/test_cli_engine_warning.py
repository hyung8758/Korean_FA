from pathlib import Path

from koreanfa.cli import main


def test_cli_warns_when_alignment_needs_an_engine(tmp_path: Path, capsys, monkeypatch) -> None:
    audio = tmp_path / "sample.wav"
    transcript = tmp_path / "sample.txt"
    audio.write_bytes(b"")
    transcript.write_text("테스트", encoding="utf-8")
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "engine-cache"))

    assert main(["align", str(audio), str(transcript)]) == 2

    captured = capsys.readouterr()
    assert "warning:" in captured.err
    assert "koreanfa engine install" in captured.err
