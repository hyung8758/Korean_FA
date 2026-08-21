# KoreanFA

[![PyPI](https://img.shields.io/pypi/v/koreanfa?logo=pypi&logoColor=white)](https://pypi.org/project/koreanfa/)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://github.com/hyung8758/Korean_FA/blob/master/pyproject.toml)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04%20LTS-E95420?logo=ubuntu&logoColor=white)](#requirements)
[![macOS](https://img.shields.io/badge/macOS-12%2B%20%7C%20Apple%20Silicon%20%7C%20Intel-000000?logo=apple&logoColor=white)](#requirements)
[![License](https://img.shields.io/badge/License-Apache--2.0%20%2B%20proprietary-3DA639)](https://github.com/hyung8758/Korean_FA/blob/master/license)

[한국어](https://github.com/hyung8758/Korean_FA/blob/master/README.ko.md)

KoreanFA creates Praat TextGrid files from Korean or Japanese WAV audio and a matching UTF-8 transcript. It provides both a Python API and a command-line interface, with automatic Korean/Japanese model selection by default.

## Features

- Align one WAV/TXT pair or an entire directory of pairs
- Select Korean or Japanese automatically, or choose a model explicitly
- Produce word and phone tiers in a Praat TextGrid
- Validate a corpus before alignment and record reproducible JSON run reports
- Export structured intervals as JSON, CSV, or word/phone CTM files
- Use a managed Kaldi-based engine; Docker and a web server are not required

## Requirements

- Linux x86_64 with glibc 2.17 or later
  - Officially supported and tested: Ubuntu 22.04 LTS and 24.04 LTS
  - Older Ubuntu releases and other glibc-based Linux distributions may work, but are not currently covered by KoreanFA's official test matrix
- macOS 12 or later on Apple Silicon (arm64) or Intel (x86_64)
- Python 3.12 or 3.13
- WAV audio and UTF-8 text transcripts

Windows is not supported yet. KoreanFA automatically downloads the native engine matching a supported Linux or macOS system.

## Installation

Install KoreanFA from PyPI, then install the native alignment engine matching the current system once:

```bash
python -m pip install koreanfa
koreanfa engine install
```

To use the latest development source from the default branch instead:

```bash
git clone --depth 1 https://github.com/hyung8758/Korean_FA.git
cd Korean_FA
python -m pip install .
koreanfa engine install
```

Check the engine status at any time:

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

Files are paired by their relative stem: for example, `session_01.wav` is matched with `session_01.txt`. Unmatched files are skipped by default and a warning identifies them.

Validate pairing, UTF-8 transcripts, language detection, complete WAV decoding, and engine readiness without running Kaldi:

```bash
koreanfa validate corpus -r --report validation.json
```

Validation collects all detected problems instead of stopping at the first file. It exits with status 2 for errors; add `--strict` to make warnings fail as well. `--no-engine-check` is available when checking data on a machine that will not perform alignment.

The CLI reports each file's preparation/decode stage, a directory progress bar, and a final `total / success / failed / skipped` summary. Successful files keep their TextGrids even if other files fail; the CLI then exits with status 2 and prints each rejected file's reason. Add `--keep-workdir` to retain `logs/summary.tsv` and per-file Kaldi logs for diagnosis.

### Language selection

`-l auto` / `--lang auto` is the default. Hangul selects the Korean model, while Hiragana, Katakana, or Kanji selects the Japanese model. Choose a model explicitly for mixed-script transcripts. In a directory, a transcript that has neither script (for example, `<laugh>` or English-only text) is reported in `batch.failures`; other files continue to run.

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
- `--existing {overwrite,skip,error}`: overwrite existing TextGrids (the compatible default), skip realignment for structurally valid TextGrids, or stop before alignment if a requested output already exists (`existing=...`). Requested JSON/CSV/CTM files are still generated from a valid skipped TextGrid; a damaged TextGrid is never treated as a successful skip.
- `--export {json,csv,ctm}`: write an additional machine-readable format; repeat the option for multiple formats (`exports=("json", "csv", "ctm")`). CTM export writes separate word and phone files, omits only empty gap intervals, and uses the corpus-relative stem as its recording ID. Whitespace, control characters, and `%` in CTM recording IDs or labels are UTF-8 percent-encoded to preserve the five-field format; JSON and CSV labels remain unchanged.
- `--report PATH`: atomically write a versioned JSON run report containing relative paths, options, outcomes, attempt counts, and engine metadata (`report_path=PATH`). Transcript contents are not copied into the report.

Use `-h` / `--help` for command help and `-v` / `--version` for the package version.

## Python API

Install the engine once, then align a pair:

```python
from koreanfa import align, install_engine

install_engine()
result = align("recording.wav", "recording.txt", lang="auto")
print(result.textgrid)
print(result.language)  # "kor" or "jap"
for word in result.words:
    print(word.start, word.end, word.label)
```

For a directory, use `Aligner`:

```python
from koreanfa import Aligner

aligner = Aligner(lang="auto", num_jobs=4)
batch = aligner.align(
    "corpus",
    output_dir="aligned",
    recursive=True,
    existing="skip",
    exports=("json", "csv", "ctm"),
    report_path="aligned/run.json",
)
for result in batch.results:
    print(result.textgrid, result.outputs["json"])
for skipped in batch.skipped:
    print(f"unchanged: {skipped.textgrid}")
for failure in batch.failures:
    print(f"rejected: {failure.audio} ({failure.reason})")
```

`result.words` and `result.phones` contain typed intervals in seconds, including named silence intervals. `result.outputs` identifies every emitted file. Directory alignment returns successes in `batch.results`, valid existing outputs in `batch.skipped`, and controlled per-file rejections in `batch.failures`; aggregate counts and elapsed time are available from `batch.summary`.

Library calls do not print progress by default; unmatched input files are reported through Python's warning system. Pass a `progress` callback when the host application wants structured progress events, and use `keep_workdir=True` when it needs to retain `logs/summary.tsv`.

The same preflight is available in Python as `validate("corpus", recursive=True)`. Its `ValidationReport` contains every valid pair and every structured issue; pass `check_engine=False` when validating data only.

## Input notes

- Each WAV file needs a matching UTF-8 `.txt` transcript.
- One sentence per transcript is recommended.
- Audio is normalized to mono 16 kHz PCM WAV in a temporary workspace.
- Korean pronunciation conversion is provided by the package dependency `ko-speech-tools` and its Korean MeCab dictionary; no separate Korean G2P installation is required.
- Japanese support includes the required MeCab and IPADIC resources in the managed engine.

## Engine management

```bash
koreanfa engine install
koreanfa engine status
koreanfa engine install -f
koreanfa engine remove -y
```

Set `KOREANFA_ENGINE_HOME` to choose the engine cache location. Advanced users can set `KOREANFA_KALDI_DIR` or pass `kaldi_dir=` to use an externally managed Kaldi runtime instead.

If an engine download or checksum verification fails, see the [engine installation troubleshooting guide](https://github.com/hyung8758/Korean_FA/blob/master/docs/troubleshooting.md). KoreanFA never installs an engine whose SHA-256 checksum does not match the published manifest.

## Citation

If you use KoreanFA in academic work, please cite the specific version used in your research. Citation metadata is provided in [`CITATION.cff`](https://github.com/hyung8758/Korean_FA/blob/master/CITATION.cff) and through the **Cite this repository** menu on GitHub.

## License

KoreanFA code and the Japanese acoustic model are licensed under [Apache-2.0](https://github.com/hyung8758/Korean_FA/blob/master/license). The Korean acoustic model is proprietary to Mediazen and may be used for commercial or non-commercial purposes only as part of KoreanFA; modification or separate redistribution requires prior written permission. See the Korean model [notice](https://github.com/hyung8758/Korean_FA/blob/master/koreanfa/runtime/model/kor_model/NOTICE.md), the [example-data notice](https://github.com/hyung8758/Korean_FA/blob/master/example/NOTICE.md), and the [third-party notices](https://github.com/hyung8758/Korean_FA/blob/master/THIRD_PARTY_NOTICES.md) for bundled source material and the separately downloaded engine.
