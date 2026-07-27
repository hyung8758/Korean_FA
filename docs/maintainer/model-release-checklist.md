# Model release checklist

This is a maintainer release checklist. It is not distributed in the Python
wheel and is not a public model notice.

Keep each model's `NOTICE.md` synchronized with the verified facts below.
Each notice must state its copyright holder, licence or permitted-use terms,
and any required attribution.

## Current status: not cleared for public model redistribution

The Korean model's owner, high-level training-data description, and
proprietary terms are recorded in `model/kor_model/NOTICE.md`. The Japanese
replacement model has its initial provenance and Apache-2.0 notice recorded in
`model/jap_model/NOTICE.md`. The Japanese model still needs its reproducibility
and held-out evaluation records before a final public-model release.

## Required maintainer confirmations

| Asset | Required record | Status |
| --- | --- | --- |
| `model/kor_model/` | Mediazen-owned model; approximately 1,000 hours of Mediazen-collected Korean spontaneous/read speech; proprietary KoreanFA-only use, no modification or redistribution without written permission | **Maintainer confirmation recorded in `model/kor_model/NOTICE.md`** |
| replacement `model/jap_model/` | Common Voice Scripted Speech 26.0 Japanese (`cmqim4lxy00tunr07cjkcupeg`), `validated.tsv` only; exact training command, archive SHA-256, held-out evaluation, and Apache-2.0 model notice | **Replacement and functional validation complete; reproducibility and held-out evaluation pending** |

The former KoG2P `g2p.py` and `rulebook.txt` are not shipped. Korean
pronunciation conversion now uses the Apache-2.0 `ko-speech-tools` dependency;
see `THIRD_PARTY_NOTICES.md` for the accompanying runtime dependencies.

## Before a public release

For each model, record a stable source URL, DOI, internal record, or written
permission reference; the exact licence; a confirmation that it permits
redistribution of the trained weights; required attribution or restrictions;
and the maintainer's verification date.

If a training corpus prohibits model redistribution, obtain written permission
or remove and retrain the affected model before publishing it.
