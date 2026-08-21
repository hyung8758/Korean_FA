from pathlib import Path

import pytest

from koreanfa import Aligner
from koreanfa.errors import EngineNotFoundError
from koreanfa.result import AlignmentResult, BatchAlignmentResult


def test_aligner_defaults_to_auto_language() -> None:
    aligner = Aligner()
    assert aligner.lang == "auto"
    assert aligner.num_jobs == 4


def test_aligner_requires_text_for_file_input(tmp_path: Path) -> None:
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"")
    with pytest.raises(ValueError, match="requires its matching TXT"):
        Aligner().align(wav)


def test_aligner_finds_directory_before_requesting_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "sample.wav").write_bytes(b"")
    (tmp_path / "sample.txt").write_text("테스트", encoding="utf-8")
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "empty-engine-cache"))
    with pytest.raises(EngineNotFoundError):
        Aligner().align(tmp_path)


def test_aligner_forwards_explicit_file_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "sample.wav"
    text = tmp_path / "sample.txt"
    output = tmp_path / "output"
    report = tmp_path / "run.json"
    wav.write_bytes(b"")
    text.write_text("테스트", encoding="utf-8")
    expected = AlignmentResult(wav, text, output / "sample.TextGrid", "kor")
    received: dict[str, object] = {}

    def fake_align(audio: Path, transcript: Path, **options: object) -> AlignmentResult:
        received.update(options)
        assert audio == wav
        assert transcript == text
        return expected

    monkeypatch.setattr("koreanfa.aligner.align", fake_align)
    result = Aligner(lang="auto", kaldi_dir="default-engine", num_jobs=4).align(
        wav,
        text,
        lang="kor",
        output_dir=output,
        kaldi_dir="override-engine",
        num_jobs=2,
        word_tier=False,
        keep_workdir=True,
        existing="error",
        exports=("json", "ctm"),
        report_path=report,
    )

    assert result is expected
    assert received == {
        "lang": "kor",
        "output_dir": output,
        "kaldi_dir": "override-engine",
        "num_jobs": 2,
        "word_tier": False,
        "phone_tier": True,
        "keep_workdir": True,
        "progress": None,
        "existing": "error",
        "exports": ("json", "ctm"),
        "report_path": report,
    }


def test_aligner_forwards_explicit_directory_options(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "output"
    report = tmp_path / "run.json"
    expected = BatchAlignmentResult((), output)
    received: dict[str, object] = {}

    def fake_align_directory(directory: Path, **options: object) -> BatchAlignmentResult:
        received.update(options)
        assert directory == tmp_path
        return expected

    monkeypatch.setattr("koreanfa.aligner.align_directory", fake_align_directory)
    result = Aligner(lang="jap", num_jobs=3).align(
        tmp_path,
        output_dir=output,
        recursive=True,
        ignore_unmatched=False,
        phone_tier=False,
        existing="skip",
        exports=("csv",),
        report_path=report,
    )

    assert result is expected
    assert received == {
        "lang": "jap",
        "output_dir": output,
        "kaldi_dir": None,
        "num_jobs": 3,
        "recursive": True,
        "ignore_unmatched": False,
        "word_tier": True,
        "phone_tier": False,
        "keep_workdir": False,
        "progress": None,
        "existing": "skip",
        "exports": ("csv",),
        "report_path": report,
    }
