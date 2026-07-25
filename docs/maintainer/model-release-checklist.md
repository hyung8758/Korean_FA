# Model release checklist

This is a maintainer release checklist. It is not distributed in the Python
wheel and is not a public model card.

Create a root-level `MODEL_CARD.md` only after the facts below are verified.
Use the established model-card structure: model summary, intended use,
limitations, model licence, training-data summary, evaluation, and contact.

## Current status: not cleared for public model redistribution

The repository currently contains Korean and Japanese Kaldi model artifacts,
but it does not record their trainer/owner, training data, or the licence that
authorizes redistribution. The commit messages that introduced the files do
not provide this evidence.

## Required maintainer confirmations

| Asset | Required record | Status |
| --- | --- | --- |
| `model/kor_model/` | Owner or authorized distributor; training procedure; every training/evaluation corpus and its redistribution terms; model-weight licence | **Pending maintainer confirmation** |
| `model/jap_model/` | Owner or authorized distributor; training procedure; every training/evaluation corpus and its redistribution terms; model-weight licence | **Pending maintainer confirmation** |
| `runtime/pipeline/kor/data/lang/rulebook.txt` | Copyright holder and licence or written permission allowing redistribution | **Pending maintainer confirmation** |

## Before creating `MODEL_CARD.md`

For each model, record a stable source URL, DOI, internal record, or written
permission reference; the exact licence; a confirmation that it permits
redistribution of the trained weights; required attribution or restrictions;
and the maintainer's verification date.

If a training corpus prohibits model redistribution, obtain written permission
or remove and retrain the affected model before publishing it.
