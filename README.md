# KoreanFA

[한국어 문서](README.ko.md)

KoreanFA is a forced-alignment library for Korean and Japanese speech.  It
creates Praat TextGrid files from WAV audio and matching UTF-8 transcripts.
The public interface is a Python library and a command-line tool; Docker is
not required to run the current package.

Korean and Japanese models are selected automatically by default.  The native
alignment engine is installed separately once, so Python package updates and
Kaldi engine updates can be released independently.

## Supported platform

The first engine release supports **Linux x86_64** and Python **3.12**.  macOS
and Windows engine archives are not available yet.

## Installation

Install the Python package, then install the compatible native engine once.

```bash
python -m pip install koreanfa
koreanfa engine install
```

The engine command downloads a version-pinned Kaldi, MeCab, and IPADIC runtime
from a KoreanFA GitHub Release.  It verifies the archive SHA-256 before
installing it under `~/.cache/koreanfa/engines/`.

Check the installed runtime at any time:

```bash
koreanfa engine status
```

If alignment is requested before the engine is installed, KoreanFA stops with
an actionable error instead of attempting a partial alignment:

```text
KoreanFA engine is not installed. Run 'koreanfa engine install' ...
```

For Python applications, install or check the engine explicitly:

```python
from koreanfa.engine import ensure_installed, install

install()                 # first installation
ensure_installed()        # raises a clear error if it is unavailable
```

## Command line

### Align a WAV/TXT pair

```bash
koreanfa align recording.wav recording.txt
```

The resulting `recording.TextGrid` is written beside the WAV file by default.

### Align a directory

KoreanFA finds files with the same relative stem, such as
`session_01.wav` and `session_01.txt`, then writes one TextGrid per matched
pair.

```bash
koreanfa align example/kor_files
koreanfa align example/jap_files
```

Use `--recursive` for nested corpora and `--output-dir` to keep generated
TextGrids outside the input directory.

```bash
koreanfa align corpus --recursive --output-dir aligned
```

### Choose a model

`--lang auto` is the default.  Hangul selects the Korean model;
Hiragana, Katakana, or Kanji selects the Japanese model.  Mixed Korean and
Japanese scripts require an explicit choice.

```bash
koreanfa align recording.wav recording.txt --lang kor
koreanfa align recording.wav recording.txt --lang jap
```

Other useful options are `--no-word`, `--no-phone`, `--keep-workdir`, and
`--allow-unmatched`.  Run `koreanfa align --help` for the full CLI reference.

## Python library

### One pair

```python
from koreanfa import align

result = align("recording.wav", "recording.txt", lang="auto")
print(result.textgrid)
print(result.language)  # "kor" or "jap"
```

### A corpus directory

```python
from koreanfa import Aligner

aligner = Aligner(lang="auto", num_jobs=2)
batch = aligner.align("example/kor_files")
for result in batch.results:
    print(result.textgrid)
```

For a directory input, KoreanFA requires matching `.wav` and `.txt` files.
It raises a `PairingError` for unmatched files by default.  Pass
`strict=False` through the Python API or `--allow-unmatched` through the CLI
to align only complete pairs.

## Input requirements

- Audio must be a readable WAV file. KoreanFA normalizes it to mono, 16 kHz,
  PCM WAV inside its temporary workspace.
- Each transcript must be a UTF-8 `.txt` file paired with one WAV file.
- Keep one sentence per transcript. Extra spaces, tabs, line breaks, and
  legacy unsupported punctuation are normalized by the alignment pipeline.
- Japanese alignment uses the MeCab and IPADIC data bundled in the engine; no
  separate system MeCab installation is needed.

## Engine management

```bash
koreanfa engine install          # download the compatible version
koreanfa engine status           # show version and install path
koreanfa engine install --force  # replace an incomplete local installation
koreanfa engine remove --yes     # remove the compatible engine
```

`KOREANFA_ENGINE_HOME` can change the cache location.  Advanced users can
still set `KOREANFA_KALDI_DIR` or pass `kaldi_dir=` to use an externally
managed Kaldi runtime; those settings take precedence over the installed
engine.

## Development and release layout

- `koreanfa/`: public Python API, CLI, engine installer, and manifest
- `runtime/`: legacy alignment pipeline and configuration
- `model/`: Korean and Japanese acoustic models
- `engine/`: reproducible Linux engine builder and archive verifier

The Linux engine workflow is a manual candidate build. It builds and verifies
the `0.3.0` archive, then retains both the archive and its SHA-256 file as a
GitHub Actions artifact for 14 days. It does not create a tag, GitHub Release,
or PyPI publication.

The legacy Docker/Web API implementation is preserved in the `docker_api`
branch and the `docker-api-v1.7.0` tag.

## License

KoreanFA is distributed under the Apache-2.0 license. Engine archives also
include the applicable Kaldi, MeCab, and IPADIC license notices.

## History

The original Korean forced aligner was released in 2016 and evolved through
the Docker/Web API release `v1.7.0` in 2023. Version `0.3.0` introduces the
Python package interface, automatic Korean/Japanese model selection, and the
separately versioned native engine distribution.
