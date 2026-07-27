# Japanese Common Voice training

This reproducible workspace prepares KoreanFA's Japanese Kaldi training data.
It never places Common Voice audio in the repository, wheel, or engine archive.

Use only Mozilla Common Voice Scripted Speech 26.0 — Japanese: dataset ID
`cmqim4lxy00tunr07cjkcupeg`, CC0-1.0, and `validated.tsv` clips only.

```bash
python training/japanese_common_voice/prepare_data.py \
  --corpus-dir /path/to/unpacked-common-voice-ja \
  --output-dir /path/to/koreanfa-cv26/data
python training/japanese_common_voice/prepare_lexicon.py \
  --data-root /path/to/koreanfa-cv26/data \
  --repo-root "$PWD" --mecab-bin /path/to/mecab
```

The first command creates a deterministic speaker-disjoint 90/5/5 split. The
second uses MeCab/IPADIC plus KoreanFA's existing `kana2phone` mapping and
records rejected pronunciations before Kaldi training starts.
