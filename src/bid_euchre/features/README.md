# features/ — Feature Extraction

Extract features from hands for ML training and analysis.

## Key Files

| File | Purpose |
|------|---------|
| `hand_eval.py` | Hand evaluation features — strength scoring |

## Dependencies
- Imports from: `core/` (cards)
- Used by: `datasets/`, `models/`

## Contract
- Features must be **deterministic** — same hand always produces same features
- Historical spec archived at `docs/archive/BIDLESS_FEATURES.md`. Current features defined in `hand_eval.py` docstrings.
- See [docs/01_core/BIDLESS_DATASET.md](../../../docs/01_core/BIDLESS_DATASET.md) for dataset context
