"""Explicit CSV pairing, validation, and dispatch contracts."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from koreanfa import Aligner, BatchAlignmentResult, PairingError, align_manifest
from koreanfa.cli import main
from koreanfa.manifest import read_manifest
from koreanfa.validation import validate


def _manifest(root: Path, rows: str) -> Path:
    path = root / "corpus.csv"
    path.write_text("audio,transcript,language,output_id\n" + rows, encoding="utf-8")
    return path


def test_manifest_resolves_explicit_pairs_and_language_defaults(tmp_path: Path) -> None:
    path = _manifest(tmp_path, "clips/k.wav,text/k.txt,kor,speaker/k\nclips/j.wav,text/j.txt,,\n")

    entries = read_manifest(path)

    assert [(entry.pair.audio, entry.pair.transcript, entry.pair.relative_stem, entry.pair.language) for entry in entries] == [
        (tmp_path / "clips/k.wav", tmp_path / "text/k.txt", Path("speaker/k"), "kor"),
        (tmp_path / "clips/j.wav", tmp_path / "text/j.txt", Path("j"), "auto"),
    ]
    assert [entry.line for entry in entries] == [2, 3]
    assert read_manifest(path, lang="jap")[1].pair.language == "jap"


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ("a.wav,a.txt,kor,../escape\n", "safe relative path"),
        ("a.wav,a.txt,kor,/absolute\n", "safe relative path"),
        ("a.wav,a.txt,kor,C:/windows\n", "safe relative path"),
        ("a.wav,a.txt,kor,one\\two\n", "safe relative path"),
        ("a.wav,a.txt,kor,same\nb.wav,b.txt,jap,SAME\n", "conflicts with line 2"),
        ("a.wav,a.txt,wrong,sample\n", ":2:"),
        ("a\x00.wav,a.txt,kor,sample\n", "cannot contain NUL"),
        ("a.wav,a.txt,kor\n", "four CSV columns"),
    ],
)
def test_manifest_rejects_invalid_rows(tmp_path: Path, rows: str, message: str) -> None:
    with pytest.raises(PairingError, match=message):
        read_manifest(_manifest(tmp_path, rows))


def test_manifest_rejects_invalid_header_and_encoding(tmp_path: Path) -> None:
    path = tmp_path / "corpus.csv"
    path.write_text("audio,text,language,output_id\na.wav,a.txt,kor,a\n", encoding="utf-8")
    with pytest.raises(PairingError, match="expected CSV header"):
        read_manifest(path)
    path.write_bytes(b"audio,transcript,language,output_id\n\xff")
    with pytest.raises(PairingError, match="not valid UTF-8"):
        read_manifest(path)


def test_manifest_accepts_utf8_bom_and_quoted_input_paths(tmp_path: Path) -> None:
    path = tmp_path / "corpus.csv"
    path.write_text(
        '\ufeffaudio,transcript,language,output_id\n"audio,one.wav","text,one.txt",,out/one\n',
        encoding="utf-8",
    )
    entry = read_manifest(path)[0]
    assert entry.pair.audio == tmp_path / "audio,one.wav"
    assert entry.pair.transcript == tmp_path / "text,one.txt"
    assert entry.pair.relative_stem == Path("out/one")


def test_manifest_rejects_unicode_normalized_output_collisions(tmp_path: Path) -> None:
    path = _manifest(tmp_path, "a.wav,a.txt,kor,café\nb.wav,b.txt,jap,cafe\u0301\n")
    with pytest.raises(PairingError, match="conflicts with line 2"):
        read_manifest(path)


def test_manifest_validate_uses_each_row_language(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    write_wav(tmp_path / "k.wav")
    write_wav(tmp_path / "j.wav")
    (tmp_path / "k.txt").write_text("한국어 문장", encoding="utf-8")
    (tmp_path / "j.txt").write_text("日本語です", encoding="utf-8")
    manifest = _manifest(tmp_path, "k.wav,k.txt,kor,k\nj.wav,j.txt,,j\n")

    report = validate(manifest, check_engine=False)

    assert report.valid
    assert [pair.language for pair in report.pairs] == ["kor", "jap"]
    assert main(["validate", str(manifest), "--no-engine-check"]) == 0


def test_manifest_validation_reports_missing_inputs(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, "missing.wav,missing.txt,kor,one\n")
    report = validate(manifest, check_engine=False)
    assert {issue.code for issue in report.issues} == {"audio.missing", "transcript.missing"}


def test_align_manifest_preserves_output_ids_and_partial_language_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for stem, text in (("k", "한국어"), ("unknown", "<laugh>")):
        (tmp_path / f"{stem}.wav").write_bytes(b"wav")
        (tmp_path / f"{stem}.txt").write_text(text, encoding="utf-8")
    manifest = _manifest(tmp_path, "k.wav,k.txt,,speaker/k\nunknown.wav,unknown.txt,,speaker/u\n")
    captured: dict[str, Any] = {}

    def fake_align(*args: Any, **kwargs: Any) -> BatchAlignmentResult:
        captured["pairs"] = args[0]
        captured["output_dir"] = args[1]
        captured["failures"] = args[8]
        captured["protected"] = kwargs["protected_inputs"]
        return BatchAlignmentResult((), args[1], failures=args[8])

    monkeypatch.setattr("koreanfa._manifest_alignment.align_pairs", fake_align)
    batch = Aligner().align(manifest)

    assert isinstance(batch, BatchAlignmentResult)
    assert captured["output_dir"] == tmp_path / "aligned"
    assert captured["pairs"][0].relative_stem == Path("speaker/k")
    assert captured["pairs"][0].language == "kor"
    assert batch.failures[0].audio.name == "unknown.wav"
    assert manifest in captured["protected"]


def test_manifest_cannot_overwrite_its_inputs_or_validation_report(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    write_wav(tmp_path / "sample.wav")
    (tmp_path / "sample.txt").write_text("한국어", encoding="utf-8")
    manifest = _manifest(tmp_path, "sample.wav,sample.txt,kor,corpus\n")
    manifest = manifest.rename(tmp_path / "corpus.alignment.csv")
    original = manifest.read_bytes()

    with pytest.raises(PairingError, match="overwrite an input"):
        align_manifest(manifest, output_dir=tmp_path, exports=("csv",))
    with pytest.raises(ValueError, match="overwrite an input"):
        validate(manifest, check_engine=False, report_path=tmp_path / "SAMPLE.WAV")
    assert manifest.read_bytes() == original


def test_invalid_manifest_cannot_overwrite_an_unparsed_input(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    audio = write_wav(tmp_path / "sample.wav")
    original = audio.read_bytes()
    manifest = tmp_path / "corpus.csv"
    manifest.write_text("wrong,header\nsample.wav,sample.txt\n", encoding="utf-8")

    with pytest.raises(ValueError, match="overwrite an input"):
        validate(manifest, check_engine=False, report_path=audio)
    assert audio.read_bytes() == original


def test_manifest_validation_cannot_overwrite_pronunciation_dictionary(
    tmp_path: Path, write_wav: Callable[[Path], Path]
) -> None:
    write_wav(tmp_path / "sample.wav")
    (tmp_path / "sample.txt").write_text("한국어", encoding="utf-8")
    manifest = _manifest(tmp_path, "sample.wav,sample.txt,kor,sample\n")
    dictionary = tmp_path / "pronunciations.tsv"
    dictionary.write_text("language\tword\tpronunciation\n", encoding="utf-8")
    original = dictionary.read_bytes()

    with pytest.raises(ValueError, match="pronunciation dictionary"):
        validate(manifest, check_engine=False, pronunciation_dictionary=dictionary, report_path=dictionary)
    assert dictionary.read_bytes() == original


def test_manifest_rejects_output_file_directory_conflicts(tmp_path: Path) -> None:
    for stem in ("one", "two"):
        (tmp_path / f"{stem}.wav").write_bytes(b"wav")
        (tmp_path / f"{stem}.txt").write_text("한국어", encoding="utf-8")
    manifest = _manifest(tmp_path, "one.wav,one.txt,kor,foo\ntwo.wav,two.txt,kor,foo.TextGrid/bar\n")

    with pytest.raises(PairingError, match="file/directory path"):
        align_manifest(manifest)


def test_manifest_rejects_input_file_as_output_directory(tmp_path: Path) -> None:
    (tmp_path / "sample.wav").write_bytes(b"wav")
    transcript = tmp_path / "sample.txt"
    transcript.write_text("한국어", encoding="utf-8")
    manifest = _manifest(tmp_path, "sample.wav,sample.txt,kor,sample.txt/child\n")

    with pytest.raises(PairingError, match="input file as a directory"):
        align_manifest(manifest, output_dir=tmp_path)
    assert transcript.read_text(encoding="utf-8") == "한국어"


def test_cli_rejects_a_transcript_for_a_manifest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = _manifest(tmp_path, "a.wav,a.txt,kor,a\n")
    assert main(["align", str(manifest), "unwanted.txt"]) == 2
    assert "do not pass transcript" in capsys.readouterr().err
