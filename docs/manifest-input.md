# CSV manifest input

Use a CSV manifest when an audio file and its transcript have different names, live in different directories, or need an explicit output name or language. Directory discovery remains available for same-stem WAV/TXT pairs.

The file must be UTF-8 CSV with this exact header and four columns:

```csv
audio,transcript,language,output_id
audio/session01.wav,transcripts/utterance01.txt,kor,speaker01/session01
audio/session02.wav,transcripts/utterance02.txt,jap,speaker02/session02
audio/session03.wav,transcripts/utterance03.txt,,
```

- `audio` and `transcript` are required paths to existing `.wav` and `.txt` files. Relative paths are resolved from the manifest's directory; absolute paths also work.
- `language` is `kor`, `jap`, or `auto`. An empty cell uses the command/API `lang` setting, which defaults to `auto`.
- `output_id` is the relative output stem. For example, `speaker01/session01` becomes `speaker01/session01.TextGrid` under the output directory. An empty cell uses the audio filename stem. Output IDs cannot be absolute, contain `..`, or collide on a case-insensitive filesystem.
- One row describes one alignment. Unlike directory discovery, the WAV and TXT filenames do not need to match.

Validate and align from the CLI:

```bash
koreanfa validate corpus.csv
koreanfa align corpus.csv --output-dir aligned --report aligned/run.json
```

Or use the Python API:

```python
from koreanfa import align_manifest, validate

preflight = validate("corpus.csv")
if preflight.valid:
    batch = align_manifest("corpus.csv", output_dir="aligned")
    for result in batch.results:
        print(result.textgrid)
    for failure in batch.failures:
        print(failure.audio, failure.reason)
```

`Aligner().align("corpus.csv")` is equivalent to `align_manifest("corpus.csv")`. The usual alignment options, including `num_jobs`, `existing`, `exports`, reports, and pronunciation dictionaries, also apply. Without an explicit output directory, manifest outputs go into an `aligned/` directory beside the CSV. Invalid manifest structure stops before alignment; an undetectable `auto`-language row is reported as an individual batch failure so other rows can continue.
