"""Focused tests for runtime scripts that run outside the Python package."""

import importlib.util
import os
import shutil
import subprocess
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
    words.write_text("테스트 테스트\n", encoding="utf-8")
    text_num = tmp_path / "text_num.txt"
    text_num.write_text("1\n", encoding="utf-8")
    output = tmp_path / "output"

    generated = module.generate(source, words, text_num, output, no_word=False, no_phone=False)

    text = generated.read_text(encoding="utf-8")
    assert '"phone"' in text
    assert '"word"' in text
    assert '"romanization"' in text
    assert '"테스트"' in text
    assert '"teseuteu"' in text
    assert "0.000000\n0.200000\n\"<sil>\"" in text
    assert text.count('"IntervalTier"') == 3


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

    generated = module.generate(
        source, words, number, tmp_path / "output", no_word=True, no_phone=False, no_romanization=True
    )

    text = generated.read_text(encoding="utf-8")
    assert '"phone"' in text
    assert '"word"' not in text
    with pytest.raises(ValueError, match="At least one"):
        module.generate(source, words, number, tmp_path / "none", no_word=True, no_phone=True)


def test_generate_textgrid_romanizes_the_resolved_korean_pronunciation(tmp_path: Path) -> None:
    module = _load_script("generate_textgrid.py")
    source = tmp_path / "result"
    source.mkdir()
    (source / "tagged_final_ali.txt").write_text(
        "header\nutt\tfile\t1\t1\t0\t1\ta_S\t0\t1\t0\t1\n", encoding="utf-8"
    )
    words = tmp_path / "words.txt"
    # The displayed spelling and aligned pronunciation intentionally differ.
    words.write_text("국물 궁물\n", encoding="utf-8")
    number = tmp_path / "number.txt"
    number.write_text("1\n", encoding="utf-8")

    text = module.generate(source, words, number, tmp_path / "output", no_word=False, no_phone=False).read_text(
        encoding="utf-8"
    )

    assert '"국물"' in text
    assert '"gungmul"' in text


def test_generate_textgrid_romanizes_japanese_mecab_readings(tmp_path: Path) -> None:
    module = _load_script("generate_textgrid.py")
    source = tmp_path / "result"
    source.mkdir()
    (source / "tagged_final_ali.txt").write_text(
        "header\nutt\tfile\t1\t1\t0\t1\ta_S\t0\t1\t0\t1\n", encoding="utf-8"
    )
    words = tmp_path / "words.txt"
    words.write_text("東京 t o u ky o u\n", encoding="utf-8")
    readings = tmp_path / "readings.txt"
    readings.write_text("トウキョウ\n", encoding="utf-8")
    number = tmp_path / "number.txt"
    number.write_text("1\n", encoding="utf-8")

    text = module.generate(
        source,
        words,
        number,
        tmp_path / "output",
        no_word=False,
        no_phone=False,
        language="jap",
        romanization_file=readings,
    ).read_text(encoding="utf-8")

    assert '"romanization"' in text
    assert '"toukyou"' in text


def test_prepare_data_matches_wav_and_text_by_exact_stem(tmp_path: Path) -> None:
    module = _load_script("fa_prep_data.py")
    # The pairing check happens before opening WAV headers, so text-only input
    # is enough to verify that substring matches are no longer accepted.
    (tmp_path / "a.wav").write_bytes(b"")
    (tmp_path / "a-long.txt").write_text("text", encoding="utf-8")

    with pytest.raises(ValueError, match="WAV without TXT"):
        module.prepare_data(tmp_path, tmp_path / "prepared")


def test_shell_pairing_helper_uses_nul_delimited_deterministic_records(tmp_path: Path) -> None:
    nested = tmp_path / "space 日本語"
    nested.mkdir()
    (nested / "b.wav").write_bytes(b"")
    (nested / "b.txt").write_text("日本語", encoding="utf-8")
    (tmp_path / "a.wav").write_bytes(b"")
    (tmp_path / "a.txt").write_text("한국어", encoding="utf-8")
    (tmp_path / "orphan.wav").write_bytes(b"")

    completed = subprocess.run(
        [sys.executable, ROOT / "koreanfa" / "runtime" / "pipeline" / "pair_corpus.py", tmp_path],
        check=True,
        capture_output=True,
    )
    fields = completed.stdout.decode("utf-8", errors="strict").split("\0")

    assert fields[-1] == ""
    records = [tuple(fields[index : index + 4]) for index in range(0, len(fields) - 1, 4)]
    assert [(record[0], record[1]) for record in records] == [
        ("PAIR", "a"),
        ("PAIR", str(Path("space 日本語") / "b")),
        ("MISSING_TEXT", "orphan"),
    ]


def test_shell_workers_start_new_pairs_without_waiting_for_a_whole_batch(tmp_path: Path) -> None:
    """A completed worker must continue while a different worker is still slow."""
    runtime = tmp_path / "runtime"
    pipeline = runtime / "pipeline"
    language_profile = runtime / "languages" / "kor" / "profile.sh"
    pipeline.mkdir(parents=True)
    language_profile.parent.mkdir(parents=True)
    language_profile.write_text("\n", encoding="utf-8")
    shutil.copy2(ROOT / "koreanfa" / "runtime" / "pipeline" / "forced_align.sh", pipeline)
    (runtime / "path.sh").write_text("return 0\n", encoding="utf-8")
    (pipeline / "pair_corpus.py").write_text(
        "import os\n"
        "import sys\n"
        "for index in range(4):\n"
        "    stem = f'pair_{index}'\n"
        "    fields = ('PAIR', stem, os.path.join(sys.argv[1], stem + '.wav'), os.path.join(sys.argv[1], stem + '.txt'))\n"
        "    sys.stdout.buffer.write(b'\\0'.join(value.encode() for value in fields) + b'\\0')\n",
        encoding="utf-8",
    )
    (pipeline / "main_fa.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        "job=$2; log_dir=$3; output=$4\n"
        "if [[ $job == 0 ]]; then\n"
        "  sleep 0.20\n"
        "  [[ -f $log_dir/job-3-started ]] || { printf 'FAIL\\t%s\\n' \"$job\" >> \"$log_dir/history.tsv\"; exit 1; }\n"
        "elif [[ $job == 1 ]]; then\n"
        "  sleep 0.02\n"
        "elif [[ $job == 3 ]]; then\n"
        "  touch \"$log_dir/job-3-started\"\n"
        "fi\n"
        "touch \"$output\"\n"
        "printf 'SUCCESS\\t%s\\n' \"$job\" >> \"$log_dir/history.tsv\"\n",
        encoding="utf-8",
    )
    corpus = tmp_path / "corpus"
    engine = tmp_path / "engine"
    logs = tmp_path / "logs"
    corpus.mkdir()
    engine.mkdir()
    for index in range(4):
        (corpus / f"pair_{index}.wav").write_bytes(b"audio")
        (corpus / f"pair_{index}.txt").write_text("text", encoding="utf-8")

    environment = os.environ | {
        "KOREANFA_KALDI_DIR": str(engine),
        "KOREANFA_LANG": "kor",
        "KOREANFA_LOG_DIR": str(logs),
        "KOREANFA_PYTHON_EXECUTABLE": sys.executable,
    }
    completed = subprocess.run(
        ["bash", pipeline / "forced_align.sh", "--num-jobs", "2", corpus],
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert "KOREANFA_SUMMARY\ttotal=4\tsuccess=4\tfailed=0" in completed.stdout
    assert (logs / "job-3-started").is_file()
    assert all((corpus / f"pair_{index}.TextGrid").is_file() for index in range(4))
