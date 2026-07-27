#!/usr/bin/env python3
"""Tokenize prepared Common Voice text and create KoreanFA Kaldi lexicons."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


SPLITS = ("train", "dev", "test")


def parse_mecab_output(stdout: str, expected_count: int) -> list[list[tuple[str, str]]]:
    result: list[list[tuple[str, str]]] = []
    tokens: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        if line == "EOS":
            result.append(tokens)
            tokens = []
            continue
        if "\t" not in line:
            raise ValueError(f"Unexpected MeCab output: {line!r}")
        word, details = line.split("\t", 1)
        fields = details.split(",")
        pronunciation = fields[8] if len(fields) > 8 else "*"
        if pronunciation == "*" and len(fields) > 7:
            pronunciation = fields[7]
        if not word or pronunciation == "*":
            raise ValueError(f"No IPADIC pronunciation for {word!r}")
        tokens.append((word, pronunciation))
    if tokens or len(result) != expected_count:
        raise ValueError(f"MeCab returned {len(result)} sentences; expected {expected_count}")
    return result


def _mecab(binary: Path, sentences: list[str]) -> list[list[tuple[str, str]]]:
    completed = subprocess.run([str(binary)], input="\n".join(sentences) + "\n", text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"MeCab exited {completed.returncode}")
    return parse_mecab_output(completed.stdout, len(sentences))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mecab-bin", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()
    root, repo, mecab = args.data_root.resolve(), args.repo_root.resolve(), args.mecab_bin.resolve()
    if args.batch_size < 1 or not mecab.is_file():
        raise ValueError("A positive --batch-size and an existing --mecab-bin are required")
    dictionary = root / "local" / "dict"
    if dictionary.exists():
        raise FileExistsError(f"Refusing to overwrite {dictionary}")
    dictionary.mkdir(parents=True)
    utterances: list[tuple[str, str, str]] = []
    for split in SPLITS:
        for line in (root / split / "text.raw").read_text(encoding="utf-8").splitlines():
            utt, sentence = line.split(maxsplit=1)
            utterances.append((split, utt, sentence))
    tokenized: dict[str, list[tuple[str, str]]] = {}
    rejected: dict[str, str] = {}
    for start in range(0, len(utterances), args.batch_size):
        batch = utterances[start:start + args.batch_size]
        try:
            parsed = _mecab(mecab, [item[2] for item in batch])
            for (_, utt, _), tokens in zip(batch, parsed, strict=True):
                if tokens:
                    tokenized[utt] = tokens
                else:
                    rejected[utt] = "MeCab returned no tokens"
        except (RuntimeError, ValueError):
            for _, utt, sentence in batch:
                try:
                    tokenized[utt] = _mecab(mecab, [sentence])[0]
                except (RuntimeError, ValueError) as error:
                    rejected[utt] = str(error)
    entries = sorted({f"{word}+{pron}" for tokens in tokenized.values() for word, pron in tokens})
    vocabulary, converted, errors = dictionary / "mecab_vocabulary.txt", dictionary / "converted_pronunciations.tsv", dictionary / "unmapped_pronunciations.txt"
    vocabulary.write_text("\n".join(entries) + "\n", encoding="utf-8")
    conversion = subprocess.run(["perl", str(repo / "runtime/pipeline/vocab2dic.pl"), "-p", str(repo / "runtime/pipeline/kana2phone"), "-e", str(errors), "-o", str(converted), str(vocabulary)], text=True, capture_output=True, check=False)
    if conversion.returncode:
        raise RuntimeError(conversion.stderr.strip() or "vocab2dic.pl failed")
    mapped, lexicon = set(), {("<sil>", "<sil>"), ("<unk>", "<unk>")}
    for line in converted.read_text(encoding="utf-8").splitlines():
        entry, _, phones = line.split("\t")
        mapped.add(entry)
        lexicon.add((entry.split("+", 1)[0], phones.strip()))
    (dictionary / "lexicon.txt").write_text("".join(f"{word} {phones}\n" for word, phones in sorted(lexicon)), encoding="utf-8")
    accepted: dict[str, list[str]] = defaultdict(list)
    for split, utt, _ in utterances:
        if utt in rejected:
            continue
        tokens = tokenized[utt]
        missing = [f"{word}+{pron}" for word, pron in tokens if f"{word}+{pron}" not in mapped]
        if missing:
            rejected[utt] = "unmapped pronunciation: " + ", ".join(missing[:3])
        else:
            accepted[split].append(f"{utt} {' '.join(word for word, _ in tokens)}\n")
    for split in SPLITS:
        if not accepted[split]:
            raise ValueError(f"No usable utterances remain in {split}")
        (root / split / "text").write_text("".join(accepted[split]), encoding="utf-8")
    reports = root / "local" / "reports"
    reports.mkdir(parents=True, exist_ok=False)
    (reports / "rejected_utterances.tsv").write_text("utterance_id\treason\n" + "".join(f"{utt}\t{reason}\n" for utt, reason in sorted(rejected.items())), encoding="utf-8")
    summary = {"input_utterances": len(utterances), "accepted_by_split": {split: len(accepted[split]) for split in SPLITS}, "rejected_utterances": len(rejected), "unique_word_pronunciations": len(entries), "mapped_word_pronunciations": len(mapped)}
    (dictionary / "lexicon_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
