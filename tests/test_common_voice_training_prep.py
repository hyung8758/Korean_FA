"""Regression tests for the source-only Common Voice Kaldi preparation step."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "training" / "japanese_common_voice" / "prepare_data.py"
SPEC = importlib.util.spec_from_file_location("common_voice_prepare", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_prepare_data_uses_only_validated_speaker_disjoint_clips(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    clips = corpus / "clips"
    clips.mkdir(parents=True)
    rows = ["client_id\tpath\tsentence\n"]
    selected_splits: set[str] = set()
    index = 0
    while len(selected_splits) < 3:
        speaker = f"speaker-{index}"
        split = MODULE.split_for_speaker(speaker)
        if split not in selected_splits:
            selected_splits.add(split)
            filename = f"clip-{index}.mp3"
            (clips / filename).touch()
            rows.append(f"{speaker}\t{filename}\t テスト　文章 {index} \n")
        index += 1
    (corpus / "validated.tsv").write_text("".join(rows), encoding="utf-8")

    output = tmp_path / "prepared"
    MODULE.write_kaldi_data(corpus, output, MODULE.read_validated_clips(corpus))

    manifest = json.loads((output / "data_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"]["license"] == "CC0-1.0"
    assert set(manifest["splits"]) == {"train", "dev", "test"}
    for split in ("train", "dev", "test"):
        text = (output / split / "text.raw").read_text(encoding="utf-8")
        assert "テスト 文章" in text
        wav_scp = (output / split / "wav.scp").read_text(encoding="utf-8")
        assert "-ac 1 -ar 16000 -acodec pcm_s16le -f wav - |" in wav_scp


def test_parse_mecab_output_uses_ipadic_pronunciation() -> None:
    lexicon_script = SCRIPT.with_name("prepare_lexicon.py")
    lexicon_spec = importlib.util.spec_from_file_location("common_voice_lexicon", lexicon_script)
    assert lexicon_spec and lexicon_spec.loader
    lexicon_module = importlib.util.module_from_spec(lexicon_spec)
    sys.modules[lexicon_spec.name] = lexicon_module
    lexicon_spec.loader.exec_module(lexicon_module)

    parsed = lexicon_module.parse_mecab_output(
        "今日\t名詞,一般,*,*,*,*,今日,キョウ,キョー\nEOS\n", expected_count=1
    )
    assert parsed == [[("今日", "キョー")]]


def test_lexicon_preparation_filters_through_the_runtime_phone_mapper(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    clips = corpus / "clips"
    clips.mkdir(parents=True)
    rows = ["client_id\tpath\tsentence\n"]
    selected_splits: set[str] = set()
    index = 0
    while len(selected_splits) < 3:
        speaker = f"speaker-{index}"
        split = MODULE.split_for_speaker(speaker)
        if split not in selected_splits:
            selected_splits.add(split)
            filename = f"clip-{index}.mp3"
            (clips / filename).touch()
            rows.append(f"{speaker}\t{filename}\t今日\n")
        index += 1
    (corpus / "validated.tsv").write_text("".join(rows), encoding="utf-8")
    data_root = tmp_path / "prepared"
    MODULE.write_kaldi_data(corpus, data_root, MODULE.read_validated_clips(corpus))

    fake_mecab = tmp_path / "mecab"
    fake_mecab.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "for line in sys.stdin:\n"
        "    if line.strip():\n"
        "        print('今日\\t名詞,一般,*,*,*,*,今日,キョウ,キョー')\n"
        "    print('EOS')\n",
        encoding="utf-8",
    )
    fake_mecab.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT.with_name("prepare_lexicon.py")),
            "--data-root",
            str(data_root),
            "--repo-root",
            str(SCRIPT.parents[2]),
            "--mecab-bin",
            str(fake_mecab),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert '"rejected_utterances": 0' in result.stdout
    assert "今日 ky o:" in (data_root / "local" / "dict" / "lexicon.txt").read_text(encoding="utf-8")
    for split in ("train", "dev", "test"):
        assert " 今日\n" in (data_root / split / "text").read_text(encoding="utf-8")
