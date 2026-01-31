# Sandbox Notebooks

**Purpose:** Rapid exploration and hypothesis testing during Arc B development.

---

## Phase 0 Notebooks Have Moved!

Phase 0 (bidless hand analysis) notebooks are now in `notebooks/phase0_bidless/`:
- `00_charts_reference.ipynb` → `../phase0_bidless/20_charts_reference.ipynb`
- `00_starter_b0_exploration.ipynb` → `../phase0_bidless/30_model_dev_and_eval.ipynb`

See [Phase 0 README](../phase0_bidless/README.md) for details.

---

## What Goes Here

- Feature distribution analysis
- Model debugging and inspection
- Hand value correlation plots
- Contract type comparisons
- Bidless dataset exploration

---

## Workflow

1. **Create notebook** — Name with date prefix: `2026_01_27_explore_B0_features.ipynb`
2. **Explore freely** — Charts, stats, hypothesis testing
3. **Extract patterns** — Promote useful code to `src/bid_euchre/`
4. **Clear outputs** — Before committing
5. **Archive or delete** — After extracting value

---

## Naming Convention

```
YYYY_MM_DD_<topic>.ipynb
```

Examples:
- `2026_01_27_b0_feature_correlations.ipynb`
- `2026_01_28_trump_count_vs_tricks.ipynb`
- `2026_01_30_bidless_dataset_inspection.ipynb`

---

## Common Imports

```python
# Standard
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Project
from bid_euchre.datasets.bidless import BidlessDatasetCollector
from bid_euchre.features.hand_eval import get_hand_features
from bid_euchre.sim.deals import generate_deal
```

---

## Tips

- Use `%load_ext autoreload` + `%autoreload 2` for hot-reloading src changes
- Keep notebooks focused on one question/hypothesis
- Link to relevant PRs or docs in markdown cells
