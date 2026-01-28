# Bidless Diagnostics Notebook

Interactive diagnostic notebook for analyzing bidless simulation datasets.

## Quick Start

1. **Generate a dataset** (if you don't have one):
   ```bash
   PYTHONPATH=src python scripts/collect_bidless_dataset.py \
     --config experiments/configs/bidless_dataset_collection.yaml \
     --seed 42 --n-per 1000
   ```

2. **Open the notebook**:
   ```bash
   jupyter lab notebooks/diagnostics/bidless_diagnostics.ipynb
   ```

3. **Update the DATASET_DIR** in the Configuration cell to point to your dataset:
   ```python
   DATASET_DIR = "../../data/runs/YOUR_RUN_ID/datasets"
   ```

4. **Run all cells** to generate the diagnostic report.

## What This Notebook Checks

### Section 0: Health Scorecard
Quick pass/warn/fail summary at the top so you don't have to scroll through everything.

### Section 1: Run Summary
- Metadata (run_id, schema versions)
- Row counts, hands, contracts distribution

### Section 2: Dataset Integrity
- Row uniqueness: (hand_id, seat) pairs must be unique
- Seats per hand: Each hand must have exactly 4 seats
- NaN/Inf detection in features

### Section 3: By Contract/Trump
- Hand value distributions by contract type (suit/high/low)
- Hand value by trump suit (for suit contracts)

### Section 4: By Seat Analysis (CRITICAL)
- Hand value by seat (should be balanced)
- Team comparison (seats 0,2 vs 1,3)
- **If seats look identical, the per-seat feature bug may exist!**

### Section 5: Feature Distributions
- Histograms of top features by variance
- Feature statistics table

### Section 6: Feature-Label Relationships
- Correlation heatmap
- Correlation ranking with hand_value
- Scatter plots for key features

### Section 7: Drift Analysis
- Rolling mean over time
- First vs last batch comparison

## Architecture

The notebook is a **thin orchestration layer** that calls importable helpers:

```
src/bid_euchre/diagnostics/
    loaders.py        # load_bidless_dataset(), load_meta()
    health_checks.py  # compute_health_scorecard()
    charts.py         # plot_*() functions
    stats.py          # compare_first_last_batch(), compute_seat_balance()
```

This prevents notebook code from forking away from production code.
You can use the same helpers in scripts:

```python
from bid_euchre.diagnostics import load_bidless_dataset, compute_health_scorecard

df = load_bidless_dataset("path/to/datasets")
scorecard = compute_health_scorecard(df)
```

## Dependencies

Required:
- pandas
- matplotlib
- numpy
- scipy

Optional (for enhanced visualizations):
- seaborn

Install all dev dependencies:
```bash
pip install -e ".[dev]"
```
