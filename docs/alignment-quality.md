# Alignment quality diagnostics

KoreanFA can write an optional JSON quality diagnostic report after alignment:

```bash
koreanfa align corpus --output-dir aligned --quality-report aligned/quality.json
```

Use `quality_report_path="aligned/quality.json"` with the Python API. The
report is generated from completed or reused TextGrids; it does not run Kaldi
again and does not change TextGrid labels or timestamps.

## What the report means

This is a heuristic review aid, not an acoustic confidence score or an
accuracy guarantee. A `review` status means that the recording has one or
more measurable conditions worth checking in audio or Praat. It is not an
alignment failure.

Each item includes only a relative TextGrid path, language, source
(`aligned` or `existing`), attempt count, numerical metrics, and diagnostic
flags. It intentionally does not copy transcript text or labels into the
report.

## Diagnostics

- `leading_silence.long` and `trailing_silence.long`: boundary silence exceeds
  1.5 seconds.
- `speech_ratio.low`: non-silence interval coverage is below 20% of the recording.
- `word.duration.short` / `word.duration.long`: a spoken word is shorter than
  20 ms or longer than 2 seconds.
- `phone.duration.short` / `phone.duration.long`: a non-silence phone is
  shorter than 10 ms or longer than 500 ms.
- `alignment.retried`: Kaldi required more than one attempt.
- `speech_ratio.outlier` / `speech_rate.outlier`: a robust corpus-level
  outlier. These require at least five completed or reused TextGrids and use a
  median absolute deviation rule.

Silence labels such as `<sil>` and `<SIL>` are treated equivalently. If a
requested TextGrid omits the word or phone tier, metrics that need that tier
are `null` rather than inferred.

## Example

```json
{
  "schema_version": 1,
  "kind": "heuristic_alignment_quality",
  "summary": {"total": 100, "clean": 93, "review": 7},
  "items": [
    {
      "textgrid": "speaker_01/line_01.TextGrid",
      "language": "kor",
      "source": "aligned",
      "attempts": 1,
      "status": "review",
      "metrics": {"speech_ratio": 0.18},
      "flags": [{"code": "speech_ratio.low", "severity": "warning"}]
    }
  ]
}
```
