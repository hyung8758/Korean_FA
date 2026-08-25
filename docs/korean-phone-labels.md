# Korean phone labels

This reference explains the labels in the `phone` tier produced by KoreanFA's
Korean model. They are a fixed ASCII phone inventory for the acoustic model;
they are neither Revised Romanization nor a narrow IPA transcription.

KoreanFA first converts a transcript to a Korean pronunciation, then maps its
Hangul syllables to this inventory. The same labels must remain stable because
they are part of the packaged model's lexicon and acoustic-model contract.

## Example

For `그는`, the model phone sequence is `k0 xx nn xx nf`:

- `k0`: onset ㄱ
- `xx`: vowel ㅡ
- `nn`: onset ㄴ
- `nf`: coda ㄴ

Onset and coda labels are deliberately distinct where the inventory needs to
distinguish them. The labels are useful for phone-boundary timing and
speech-processing analysis, but they should not be treated as a direct
replacement for a context-sensitive IPA transcription.

## Inventory

The tables give the Hangul component represented by each model label. IPA is a
broad guide only: surface realization varies with phonological context,
speaker, and dialect.

### Onsets

| Label | Hangul | Broad IPA guide |
| --- | --- | --- |
| `k0` | ㄱ | /k~g/ |
| `kk` | ㄲ | /k͈/ |
| `nn` | ㄴ | /n/ |
| `t0` | ㄷ | /t~d/ |
| `tt` | ㄸ | /t͈/ |
| `rr` | ㄹ | /ɾ~l/ |
| `mm` | ㅁ | /m/ |
| `p0` | ㅂ | /p~b/ |
| `pp` | ㅃ | /p͈/ |
| `s0` | ㅅ | /s/ |
| `ss` | ㅆ | /s͈/ |
| `c0` | ㅈ | /tɕ~dʑ/ |
| `cc` | ㅉ | /tɕ͈/ |
| `ch` | ㅊ | /tɕʰ/ |
| `kh` | ㅋ | /kʰ/ |
| `th` | ㅌ | /tʰ/ |
| `ph` | ㅍ | /pʰ/ |
| `h0` | ㅎ | /h/ |

Initial ㅇ does not have a phone label because it is silent before a vowel.

### Vowels

| Label | Hangul | Broad IPA guide |
| --- | --- | --- |
| `aa` | ㅏ | /a/ |
| `qq` | ㅐ | /ɛ~e/ |
| `ya` | ㅑ | /ja/ |
| `yq` | ㅒ | /jɛ~je/ |
| `vv` | ㅓ | /ʌ/ |
| `ee` | ㅔ | /e/ |
| `yv` | ㅕ | /jʌ/ |
| `ye` | ㅖ | /je/ |
| `oo` | ㅗ | /o/ |
| `wa` | ㅘ | /wa/ |
| `wq` | ㅙ | /wɛ~we/ |
| `wo` | ㅚ | /ø~we/ |
| `yo` | ㅛ | /jo/ |
| `uu` | ㅜ | /u/ |
| `wv` | ㅝ | /wʌ/ |
| `we` | ㅞ | /we/ |
| `wi` | ㅟ | /wi/ |
| `yu` | ㅠ | /ju/ |
| `xx` | ㅡ | /ɯ/ |
| `xi` | ㅢ | /ɯi/ |
| `ii` | ㅣ | /i/ |

### Codas

| Label | Hangul component | Broad IPA guide |
| --- | --- | --- |
| `kf` | ㄱ | /k̚/ |
| `kk` | ㄲ | /k̚/ |
| `ks` | ㄳ | /ks/ |
| `nf` | ㄴ | /n/ |
| `nc` | ㄵ | /ntɕ/ |
| `nh` | ㄶ | /nh/ |
| `tf` | ㄷ | /t̚/ |
| `ll` | ㄹ | /l/ |
| `lk` | ㄺ | /lk/ |
| `lm` | ㄻ | /lm/ |
| `lb` | ㄼ | /lp/ |
| `ls` | ㄽ | /ls/ |
| `lt` | ㄾ | /lt/ |
| `lp` | ㄿ | /lpʰ/ |
| `lh` | ㅀ | /lh/ |
| `mf` | ㅁ | /m/ |
| `pf` | ㅂ | /p̚/ |
| `ps` | ㅄ | /ps/ |
| `s0` | ㅅ | /t̚/ |
| `ss` | ㅆ | /t̚/ |
| `ng` | ㅇ | /ŋ/ |
| `c0` | ㅈ | /t̚/ |
| `ch` | ㅊ | /t̚/ |
| `kh` | ㅋ | /k̚/ |
| `th` | ㅌ | /t̚/ |
| `ph` | ㅍ | /p̚/ |
| `h0` | ㅎ | /t̚/ |

Complex coda entries describe the model's Hangul-component convention, not a
promise that every component is realized as a separate acoustic segment or a
narrow IPA transcription. The pronunciation conversion already applies Korean
phonological rules before alignment.

## Readable Romanization tier

For Korean alignments, KoreanFA also writes a `romanization` interval tier by
default. It has the same word boundaries as `word`, but renders the
pronunciation that was actually aligned in readable Revised Romanization. For
example, `그는` is shown as `geuneun`; a word affected by Korean pronunciation
rules is romanized from that resolved pronunciation rather than from the
model-phone labels.

This tier is intended as a reading aid. It is neither an IPA tier nor an
alternative phone inventory, and the `phone` tier remains the authoritative
model-alignment output. Use `--no-romanization` in the CLI or
`romanization_tier=False` in the Python API to omit it. Japanese alignment
uses its own [Japanese Romanization tier](japanese-romanization.md).

## Provenance and scope

The inventory matches the phone-label convention documented for the Seoul
Corpus, also known as the Korean Corpus of Spontaneous Speech. See Yun et al.,
2015, [The Korean Corpus of Spontaneous Speech](https://doi.org/10.13064/KSSS.2015.7.2.103),
and the corresponding [reference implementation's inventory](https://github.com/Kyubyong/kss/blob/master/g2p.py#L921-L938).

This reference describes the label convention, not KoreanFA's model training
data. The KoreanFA Korean model was trained with Mediazen-collected Korean
speech data, as described in its bundled model notice. KoreanFA does not bundle
or use the KoG2P implementation.

The Romanization tier follows the National Institute of Korean Language's
[Revised Romanization rules](https://www.korean.go.kr/front_eng/roman/roman_01.do),
which are based on standard Korean pronunciation.
