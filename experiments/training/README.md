# Training - Active Training Scripts

**Status**: This folder contains current, blessed training scripts.

## Current Contents

- **`train_bidder_aware_models.py`** - Train bidder-aware regression models (OLSa_v2, OLSa_SR_v2)
  - Includes `is_bidder` feature for positional awareness
  - Supersedes all legacy training scripts in `_deprecated/training/`

## Usage

Train models with explicit configuration:

```bash
PYTHONPATH=src python experiments/training/train_bidder_aware_models.py \
  --config experiments/configs/train_bidder_models.yaml
```

## Output Contract

Training outputs should go under:
- Model binaries: `data/models/<model_name>/` (persisted models)
- Training logs/metrics: `data/runs/<run_id>/` (if using experiment framework)

## Deprecated Training Scripts

Older training scripts have been moved to `experiments/_deprecated/training/`:
- `train_baseline_regression.py` - Original OLS models (no is_bidder feature)
- `train_hand_value_ols.py` - Hand Value models (no is_bidder feature)
- `train_ridge_regression.py` - Ridge regression experiments
- And others...

These are superseded by `train_bidder_aware_models.py`.
