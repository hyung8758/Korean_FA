# KoreanFA

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

## Install

Install the Python package and then install the matching alignment engine once.

```bash
python -m pip install koreanfa
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
koreanfa align corpus --recursive --output-dir aligned
```

Files are paired by their relative stem: for example, `session_01.wav` is
matched with `session_01.txt`. Unmatched files stop the command by default;
use `--allow-unmatched` to process complete pairs only.

### Language selection

`--lang auto` is the default. Hangul selects the Korean model, while Hiragana,
Katakana, or Kanji selects the Japanese model. Choose a model explicitly for
mixed-script transcripts.

```bash
koreanfa align recording.wav recording.txt --lang kor
koreanfa align recording.wav recording.txt --lang jap
```

Run `koreanfa align --help` for all options.

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

aligner = Aligner(lang="auto", num_jobs=2)
batch = aligner.align("corpus", recursive=True)
for result in batch.results:
    print(result.textgrid)
```

## Input notes

- Each WAV file needs a matching UTF-8 `.txt` transcript.
- One sentence per transcript is recommended.
- Audio is normalized to mono 16 kHz PCM WAV in a temporary workspace.
- Japanese support includes the required MeCab and IPADIC resources in the
  managed engine.

## Engine management

```bash
koreanfa engine install
koreanfa engine status
koreanfa engine install --force
koreanfa engine remove --yes
```

Set `KOREANFA_ENGINE_HOME` to choose the engine cache location. Advanced users
can set `KOREANFA_KALDI_DIR` or pass `kaldi_dir=` to use an externally managed
Kaldi runtime instead.

## License

KoreanFA is licensed under [Apache-2.0](license).
