from pathlib import Path

import koreanfa.fa as fa
from koreanfa import align_directory_files, align_file
from koreanfa.result import AlignmentResult, BatchAlignmentResult


def test_align_file_forwards_every_public_option(tmp_path: Path, monkeypatch) -> None:
    wav = tmp_path / "sample.wav"
    text = tmp_path / "sample.txt"
    output = tmp_path / "output"
    report = tmp_path / "run.json"
    quality_report = tmp_path / "quality.json"
    dictionary = tmp_path / "pronunciations.tsv"
    expected = AlignmentResult(wav, text, output / "sample.TextGrid", "kor")
    received: dict[str, object] = {}

    def fake_align(audio: Path, transcript: Path, **options: object) -> AlignmentResult:
        received.update(options)
        assert (audio, transcript) == (wav, text)
        return expected

    monkeypatch.setattr(fa, "align", fake_align)
    result = align_file(
        wav,
        text,
        lang="kor",
        output_dir=output,
        kaldi_dir="engine",
        num_jobs=2,
        word_tier=False,
        phone_tier=True,
        keep_workdir=True,
        existing="error",
        exports=("json",),
        report_path=report,
        quality_report_path=quality_report,
        pronunciation_dictionary=dictionary,
    )

    assert result is expected
    assert received == {
        "lang": "kor",
        "output_dir": output,
        "kaldi_dir": "engine",
        "num_jobs": 2,
        "word_tier": False,
        "phone_tier": True,
        "romanization_tier": True,
        "keep_workdir": True,
        "progress": None,
        "existing": "error",
        "exports": ("json",),
        "report_path": report,
        "quality_report_path": quality_report,
        "pronunciation_dictionary": dictionary,
    }


def test_align_directory_files_and_alias_forward_every_public_option(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    report = tmp_path / "run.json"
    quality_report = tmp_path / "quality.json"
    dictionary = tmp_path / "pronunciations.tsv"
    expected = BatchAlignmentResult((), output)
    received: dict[str, object] = {}

    def fake_align_directory(directory: Path, **options: object) -> BatchAlignmentResult:
        received.update(options)
        assert directory == tmp_path
        return expected

    monkeypatch.setattr(fa, "align_directory", fake_align_directory)
    result = fa.directory(
        tmp_path,
        lang="jap",
        output_dir=output,
        kaldi_dir="engine",
        num_jobs=3,
        recursive=True,
        ignore_unmatched=False,
        word_tier=True,
        phone_tier=False,
        keep_workdir=True,
        existing="skip",
        exports=("csv", "ctm"),
        report_path=report,
        quality_report_path=quality_report,
        pronunciation_dictionary=dictionary,
    )

    assert result is expected
    assert align_directory_files is fa.align_directory_files
    assert received == {
        "lang": "jap",
        "output_dir": output,
        "kaldi_dir": "engine",
        "num_jobs": 3,
        "recursive": True,
        "ignore_unmatched": False,
        "word_tier": True,
        "phone_tier": False,
        "romanization_tier": True,
        "keep_workdir": True,
        "progress": None,
        "existing": "skip",
        "exports": ("csv", "ctm"),
        "report_path": report,
        "quality_report_path": quality_report,
        "pronunciation_dictionary": dictionary,
    }
