# Comparisons - Wrapper Scripts Only

**Status**: This folder contains backward-compatibility wrappers that forward to the unified runner.

⚠️ **Do not add new scripts to this folder.** Use configs + the canonical runner instead.

## Current Contents

- **`run_head_to_head.py`** - Deprecated wrapper for head-to-head matchups
  - **Use instead**: `experiments/run_experiment.py --mode head_to_head_matrix`
  - This wrapper is kept for backward compatibility only

## Canonical Workflow

For reproducible experiments, always use:

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

All outputs must go under `data/runs/<run_id>/` only.

**Never write to**:
- `data/reports/`
- `data/models/`
- `data/training/`
- Repository root

## Note

This folder contains only the blessed wrapper (`run_head_to_head.py`).

Other comparison scripts were quarantined and deleted (PR B2) because they bypassed the unified runner, wrote to legacy paths, or were one-off analyses.
