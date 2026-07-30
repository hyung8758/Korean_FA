# KoreanFA

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Platform](https://img.shields.io/badge/Platform-Linux%20x86__64-FCC624?logo=linux&logoColor=black)](#requirements)
[![License](https://img.shields.io/badge/License-Apache--2.0%20%2B%20proprietary-3DA639)](license)

[한국어](README.ko.md)

KoreanFA creates Praat TextGrid files from Korean or Japanese WAV audio and a
matching UTF-8 transcript. It provides both a Python API and a command-line
interface, with automatic Korean/Japanese model selection by default.

## Features

- Align one WAV/TXT pair or an entire directory of pairs
- Select Korean or Japanese automatically, or choose a model explicitly
- Produce word and phone tiers in a Praat TextGrid
- Use a managed Kaldi-based engine; Docker and a web server are not required

## Requirements

- Linux x86_64
- Python 3.12 or later
- WAV audio and UTF-8 text transcripts

macOS and Windows are not supported yet.

## Install from source

KoreanFA is not published on PyPI yet. Standard `pip install koreanfa` will
be available after the upcoming PyPI release. Until then, install the tested
release source from GitHub on Linux x86_64, then install the matching alignment
engine once.

```bash
git clone --branch v2.1.0 --depth 1 https://github.com/hyung8758/Korean_FA.git
cd Korean_FA
python -m pip install .
koreanfa engine install
```

Check its status at any time:

```bash
koreanfa engine status
```

If the engine is missing, an alignment command explains how to install it.

## Command line

Align one WAV/TXT pair:

```bash
koreanfa align recording.wav recording.txt
```

This creates `recording.TextGrid` beside the input audio by default.

Align every matching pair in a directory:

```bash
koreanfa align corpus
koreanfa align corpus -r -o aligned
```

Files are paired by their relative stem: for example, `session_01.wav` is
matched with `session_01.txt`. Unmatched files are skipped by default and a
warning identifies them.

The CLI reports each file's preparation/decode stage, a directory progress
bar, and a final `total / success / failed` summary. Successful files keep
their TextGrids even if other files fail; the CLI then exits with status 2 and
prints each rejected file's reason. Add `--keep-workdir` to retain
`logs/summary.tsv` and per-file Kaldi logs for diagnosis.

### Language selection

`-l auto` / `--lang auto` is the default. Hangul selects the Korean model, while Hiragana,
Katakana, or Kanji selects the Japanese model. Choose a model explicitly for
mixed-script transcripts. In a directory, a transcript that has neither
script (for example, `<laugh>` or English-only text) is reported in
`batch.failures`; other files continue to run.

```bash
koreanfa align recording.wav recording.txt -l kor
koreanfa align recording.wav recording.txt -l jap
```

Run `koreanfa align --help` for all options.

### Alignment options

- `-nj N`, `--num-jobs N`: align up to `N` files concurrently; the default is 4. In Python, use `num_jobs=N`.
- `-o DIR`, `--output-dir DIR`: write TextGrids under `DIR` (`output_dir=DIR`).
- `-kd DIR`, `--kaldi-dir DIR`: use an external Kaldi runtime (`kaldi_dir=DIR`).
- `-l {auto,kor,jap}`, `--lang ...`: choose a language adapter (`lang=...`).
- `-r`, `--recursive`: include subdirectories when aligning a directory (`recursive=True`).
- `-iu`, `--ignore-unmatched [true|false]`: skip WAV/TXT files without a same-stem counterpart and issue a warning; this is the default (`ignore_unmatched=True`). Set it to `false` to stop before alignment when an unmatched file is found.
- `-nw`, `--no-word`; `-np`, `--no-phone`: omit the corresponding TextGrid tier (`word_tier=False` / `phone_tier=False`).
- `-kw`, `--keep-workdir`: retain successful-run Kaldi logs and staged diagnostics (`keep_workdir=True`).

Use `-h` / `--help` for command help and `-v` / `--version` for the package version.

## Python API

Install the engine once, then align a pair:

```python
from koreanfa import align, install_engine

install_engine()
result = align("recording.wav", "recording.txt", lang="auto")
print(result.textgrid)
print(result.language)  # "kor" or "jap"
```

For a directory, use `Aligner`:

```python
from koreanfa import Aligner

aligner = Aligner(lang="auto", num_jobs=4)
batch = aligner.align("corpus", recursive=True)
for result in batch.results:
    print(result.textgrid)
for failure in batch.failures:
    print(f"rejected: {failure.audio} ({failure.reason})")
```

Library calls do not print progress by default; unmatched input files are
reported through Python's warning system. Pass a `progress` callback when the
host application wants structured progress events, and use `keep_workdir=True`
when it needs to retain `logs/summary.tsv`. Directory alignment returns
successful files in `batch.results` and controlled per-file rejections in
`batch.failures`.

## Input notes

- Each WAV file needs a matching UTF-8 `.txt` transcript.
- One sentence per transcript is recommended.
- Audio is normalized to mono 16 kHz PCM WAV in a temporary workspace.
- Korean pronunciation conversion is provided by the package dependency
  `ko-speech-tools` and its Korean MeCab dictionary; no separate Korean G2P
  installation is required.
- Japanese support includes the required MeCab and IPADIC resources in the
  managed engine.

## Engine management

```bash
koreanfa engine install
koreanfa engine status
koreanfa engine install -f
koreanfa engine remove -y
```

Set `KOREANFA_ENGINE_HOME` to choose the engine cache location. Advanced users
can set `KOREANFA_KALDI_DIR` or pass `kaldi_dir=` to use an externally managed
Kaldi runtime instead.

## License

KoreanFA code and the Japanese acoustic model are licensed under
[Apache-2.0](license). The Korean acoustic model is proprietary to Mediazen
and may be used only as part of KoreanFA; see its
[model notice](koreanfa/runtime/model/kor_model/NOTICE.md). See the
[third-party notices](THIRD_PARTY_NOTICES.md) for bundled source material and
the separately downloaded engine.
