# Training - Legacy Training Scripts

**Status**: This folder contains legacy training scripts that are **not yet integrated** with the canonical experiment runner.

⚠️ **Do not add new scripts to this folder.** Future training should be config-driven via `experiments/run_experiment.py`.

## Current Contents

- **`train_bidder_aware_models.py`** - Train bidder-aware regression models (OLSa_v2, OLSa_SR_v2)
  - Includes `is_bidder` feature for positional awareness
  - Supersedes all legacy training scripts in `_deprecated/training/`
  - **Note**: This script does NOT use the config system; it has hardcoded paths

## Usage

Run the training script directly (no config flag):

```bash
PYTHONPATH=src python experiments/training/train_bidder_aware_models.py
```

**Outputs**:
- `data/models/current/olsa_v2/olsa_v2_{suit,high,low}.pkl`
- `data/models/current/olsa_sr_v2/olsa_sr_v2_{suit,high,low}.pkl`
- `data/reports/bidder_models_comparison.txt`

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
