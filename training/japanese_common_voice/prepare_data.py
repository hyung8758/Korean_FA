#!/usr/bin/env python3
"""Create speaker-disjoint Kaldi data directories from Common Voice Japanese."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


SPLITS = ("train", "dev", "test")


def split_for_speaker(speaker: str) -> str:
    bucket = int(hashlib.sha256(speaker.encode("utf-8")).hexdigest()[:8], 16) % 100
    return "test" if bucket < 5 else "dev" if bucket < 10 else "train"


def _sentence(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).replace("\u3000", " ").split())


def read_validated_clips(corpus_dir: Path) -> list[dict[str, str]]:
    metadata, clips = corpus_dir / "validated.tsv", corpus_dir / "clips"
    if not metadata.is_file() or not clips.is_dir():
        raise FileNotFoundError(f"Expected validated.tsv and clips/ under {corpus_dir}")
    result: list[dict[str, str]] = []
    identifiers: set[str] = set()
    with metadata.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required = {"client_id", "path", "sentence"}
        if not reader.fieldnames or not required <= set(reader.fieldnames):
            raise ValueError("validated.tsv requires client_id, path, and sentence columns")
        for number, row in enumerate(reader, 2):
            path, speaker, text = (row["path"] or "").strip(), (row["client_id"] or "").strip(), _sentence(row["sentence"] or "")
            if not path or not speaker or not text:
                continue
            utterance = Path(path).stem
            if utterance in identifiers:
                raise ValueError(f"Duplicate utterance id in validated.tsv:{number}: {utterance}")
            if not (clips / path).is_file():
                raise FileNotFoundError(f"Missing audio referenced by validated.tsv:{number}: {clips / path}")
            identifiers.add(utterance)
            result.append({"id": utterance, "speaker": speaker, "path": path, "text": text})
    if not result:
        raise ValueError("No usable validated clips")
    return result


def write_kaldi_data(corpus_dir: Path, output_dir: Path, clips: list[dict[str, str]]) -> None:
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_dir}")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for clip in clips:
        groups[split_for_speaker(clip["speaker"])].append(clip)
    if any(not groups[split] for split in SPLITS):
        raise ValueError("Speaker split produced an empty partition")
    output_dir.mkdir(parents=True)
    summary: dict[str, object] = {
        "source": {"name": "Mozilla Common Voice Scripted Speech 26.0 - Japanese", "dataset_id": "cmqim4lxy00tunr07cjkcupeg", "release_date": "2026-06-17", "license": "CC0-1.0", "metadata_file": "validated.tsv"},
        "split_policy": "sha256(client_id) modulo 100: train 90%, dev 5%, test 5%",
        "splits": {},
    }
    for split in SPLITS:
        subset = sorted(groups[split], key=lambda clip: clip["id"])
        target = output_dir / split
        target.mkdir()
        wav, text, utt2spk = [], [], []
        speakers: dict[str, list[str]] = defaultdict(list)
        for clip in subset:
            audio = (corpus_dir / "clips" / clip["path"]).resolve()
            wav.append(f"{clip['id']} ffmpeg -nostdin -loglevel error -i {shlex.quote(str(audio))} -ac 1 -ar 16000 -acodec pcm_s16le -f wav - |\n")
            text.append(f"{clip['id']} {clip['text']}\n")
            utt2spk.append(f"{clip['id']} {clip['speaker']}\n")
            speakers[clip["speaker"]].append(clip["id"])
        (target / "wav.scp").write_text("".join(wav), encoding="utf-8")
        (target / "text.raw").write_text("".join(text), encoding="utf-8")
        (target / "utt2spk").write_text("".join(utt2spk), encoding="utf-8")
        (target / "spk2utt").write_text("".join(f"{speaker} {' '.join(sorted(ids))}\n" for speaker, ids in sorted(speakers.items())), encoding="utf-8")
        summary["splits"][split] = {"utterances": len(subset), "speakers": len(speakers)}
    (output_dir / "data_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    corpus = args.corpus_dir.resolve()
    clips = read_validated_clips(corpus)
    write_kaldi_data(corpus, args.output_dir.resolve(), clips)
    print(f"Prepared {len(clips)} validated clips.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
