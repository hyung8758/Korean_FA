# Pronunciation dictionaries

KoreanFA accepts an optional UTF-8 TSV pronunciation dictionary through
`--pronunciation-dictionary PATH` or the Python `pronunciation_dictionary`
argument. It changes only the exact tokens listed in the file; all other
tokens continue through the packaged Korean or Japanese G2P path.

## File format

The first non-comment row must be this exact header. Blank rows and rows whose
first non-whitespace character is `#` are ignored.

```tsv
language	word	pronunciation
kor	KoreanFA	코리안에프에이
jap	大切	タイセツ
```

Each following row has exactly three tab-separated values.

- `language` is `kor` or `jap`.
- `word` is one exact source token with no whitespace.
- `pronunciation` is one reading with no whitespace.

Korean readings use Hangul pronunciation spelling, such as `갑시`; they are
converted to the Korean model's fixed phone inventory. Japanese readings use
Hiragana or Katakana. Hiragana is normalized to Katakana before the existing
Japanese Kana-to-phone conversion.

The dictionary does not accept Kaldi phone symbols. This keeps it portable if
the implementation of a model's internal phone inventory changes.

## Matching rules

Korean transcripts are normalized for whitespace before preparation, then
matched as exact whitespace-delimited tokens. Japanese entries match exact
MeCab surface tokens. If MeCab splits a compound word, add entries for the
tokens that MeCab produces rather than for the unsplit phrase.

Use the same dictionary for Korean and Japanese corpora when useful; the
`language` column keeps the entries separate.

An override does not alter automatic language detection. When a transcript has
no Korean or Japanese script, pass `--lang kor` or `--lang jap` explicitly.

## Preflight

Run validation before a large job:

```bash
koreanfa validate corpus --recursive --pronunciation-dictionary pronunciations.tsv
```

Invalid TSV rows are reported as `pronunciation_dictionary.invalid`. Korean
tokens that the default G2P cannot convert are reported as `transcript.oov`.
The CLI prints the affected token names locally. JSON validation reports retain
the count but intentionally omit raw transcript tokens.

For Japanese, dictionary syntax is validated before alignment. Final reading
conversion still uses the packaged MeCab and Kana-to-phone pipeline, so an
override incompatible with the model's phone inventory is rejected by the
affected alignment instead of being silently ignored.
