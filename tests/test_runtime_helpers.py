"""Focused tests for runtime scripts that run outside the Python package."""

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "koreanfa" / "runtime" / "pipeline" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generate_textgrid_writes_continuous_phone_and_word_tiers(tmp_path: Path) -> None:
    module = _load_script("generate_textgrid.py")
    source = tmp_path / "result"
    source.mkdir()
    (source / "tagged_final_ali.txt").write_text(
        "header\n"
        "utt\tfile\t1\t1\t0\t0.2\t<sil>\t0\t1\t0\t0.2\n"
        "utt\tfile\t2\t1\t0.2\t0.2\ta_B\t0\t1\t0.2\t0.4\n"
        "utt\tfile\t3\t1\t0.4\t0.2\tb_E\t0\t1\t0.4\t0.6\n"
        "utt\tfile\t4\t1\t0.6\t0.2\t<sil>\t0\t1\t0.6\t1\n",
        encoding="utf-8",
    )
    words = tmp_path / "words.txt"
    words.write_text("테스트 a b\n", encoding="utf-8")
    text_num = tmp_path / "text_num.txt"
    text_num.write_text("1\n", encoding="utf-8")
    output = tmp_path / "output"

    generated = module.generate(source, words, text_num, output, no_word=False, no_phone=False)

    text = generated.read_text(encoding="utf-8")
    assert '"phone"' in text
    assert '"word"' in text
    assert '"테스트"' in text
    assert "0.000000\n0.200000\n\"<sil>\"" in text
    assert text.count('"IntervalTier"') == 2


def test_generate_textgrid_supports_a_single_requested_tier(tmp_path: Path) -> None:
    module = _load_script("generate_textgrid.py")
    source = tmp_path / "result"
    source.mkdir()
    (source / "tagged_final_ali.txt").write_text(
        "header\nutt\tfile\t1\t1\t0\t1\ta_S\t0\t1\t0\t1\n", encoding="utf-8"
    )
    words = tmp_path / "words.txt"
    words.write_text("a a\n", encoding="utf-8")
    number = tmp_path / "number.txt"
    number.write_text("1\n", encoding="utf-8")

    generated = module.generate(source, words, number, tmp_path / "output", no_word=True, no_phone=False)

    text = generated.read_text(encoding="utf-8")
    assert '"phone"' in text
    assert '"word"' not in text
    with pytest.raises(ValueError, match="At least one"):
        module.generate(source, words, number, tmp_path / "none", no_word=True, no_phone=True)


def test_prepare_data_matches_wav_and_text_by_exact_stem(tmp_path: Path) -> None:
    module = _load_script("fa_prep_data.py")
    # The pairing check happens before opening WAV headers, so text-only input
    # is enough to verify that substring matches are no longer accepted.
    (tmp_path / "a.wav").write_bytes(b"")
    (tmp_path / "a-long.txt").write_text("text", encoding="utf-8")

    with pytest.raises(ValueError, match="WAV without TXT"):
        module.prepare_data(tmp_path, tmp_path / "prepared")
