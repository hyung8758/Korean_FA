# Japanese Romanization tier

KoreanFA writes a `romanization` interval tier for Japanese alignments by
default. Its intervals match the `word` tier, while each label is rendered from
the Katakana reading selected by MeCab for the aligned token.

The labels use readable ASCII Hepburn-style Romanization. Long vowels are kept
explicit rather than replaced with macrons: for example, `トウキョウ` is written
as `toukyou`. This preserves the reading in plain ASCII TextGrid labels.

The tier is a reading aid. It is not an IPA transcription, does not replace
Japanese model-phone labels, and should not be used as an authoritative
linguistic transcription. It follows the MeCab reading and any applicable
KoreanFA Japanese pronunciation-dictionary override. Use
`--no-romanization` in the CLI or `romanization_tier=False` in the Python API
to omit it.

The conversion follows conventional Hepburn spellings for common kana, such
as `shi`, `chi`, `tsu`, and `fu`; it also handles small kana, sokuon (`ッ`),
the moraic nasal (`ン`), and the long-sound mark (`ー`).
