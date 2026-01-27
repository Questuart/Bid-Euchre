# features/ — Feature Extraction

Extract features from hands for ML training and analysis.

## Key Files

| File | Purpose |
|------|---------|
| `hand_eval.py` | Hand evaluation features — strength scoring |
| `bidless_hand_features.py` | Features for bidless dataset (v1 deterministic extractor) |

## Dependencies
- Imports from: `core/` (cards)
- Used by: `datasets/`, `models/`

## Contract
- Features must be **deterministic** — same hand always produces same features
- See [docs/01_core/BIDLESS_FEATURES.md](../../../docs/01_core/BIDLESS_FEATURES.md) for feature specification
- See [docs/01_core/BIDLESS_DATASET.md](../../../docs/01_core/BIDLESS_DATASET.md) for dataset context
