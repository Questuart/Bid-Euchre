# Training - Legacy Training Scripts

**Status**: This folder contains legacy training scripts that are **not yet integrated** with the canonical experiment runner.

⚠️ **Do not add new scripts to this folder.** Future training should be config-driven via `experiments/run_experiment.py`.

## Current Contents

**REMOVED**: `train_bidder_aware_models.py` - Legacy pickle model training script

## Usage

**REMOVED**: Legacy training script usage

## Canonical Workflow (Future)

Future training should follow the same pattern as experiments:

**Single run:**
```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/<config>.yaml \
  --seed 42 \
  --n_per 100
```

**Suite run (coming soon):**
```bash
PYTHONPATH=src python scripts/run_suite.py \
  --suite experiments/suites/<suite>.yaml
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
