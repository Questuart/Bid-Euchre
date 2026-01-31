# Phase 0: Bidless Hand Analysis

Diagnostic and exploratory notebooks for analyzing bidless hand datasets (pre-bidding simulation data).

## What is Phase 0?

Phase 0 represents pre-bidding analysis: hands dealt with contracts assigned, but no bidding decisions made. This data is used for:

- Training initial ML bidding models (B0)
- Understanding feature distributions and correlations
- Detecting bias in deal generation
- Validating game mechanics

**Key characteristics:**
- **No bidding phase**: Contracts and trumps are assigned exogenously (not chosen through bidding)
- **Scenario-driven assignment**: Contracts/trumps come from explicit scenario list in experiment config
- **Policy-dependent outcomes**: The `tricks_won` values depend on the play strategy used (e.g., RandomLegalStrategy, GreedyStrategy)
- **Determinism**: Seed controls both deal generation and any strategy randomness

## Quick Start: Three Workflows

### Workflow 1: Quick Dataset Health Check (Start Here!)

**Use case:** You just generated a dataset and want to verify it's valid.

1. Generate a small test dataset:
   ```bash
   PYTHONPATH=src python experiments/run_experiment.py \
     --config experiments/configs/bidless_dataset_collection.yaml \
     --seed 42 --n_per 2000 --emit-bidless-dataset
   ```

2. Open [10_health_checks.ipynb](10_health_checks.ipynb) and update `DATASET_DIR`:
   ```python
   DATASET_DIR = "../../data/runs/bidless_dataset_collection_YYYYMMDD_HHMMSS/datasets"
   ```

3. Run all cells. Look for the Health Scorecard (Section 0):
   - ✅ All PASS = dataset is ready
   - ⚠️ WARN = review warnings
   - ❌ FAIL = fix issues before using dataset

**Expected runtime:** ~30 seconds for 2,000 hands

**Why 2,000 hands?** Meets minimum threshold for bias detection (per `docs/rules/05_rigor.md`: ≥2,000 for seat/suit bias checks).

### Workflow 2: Production-Quality Analysis

**Use case:** You're preparing a report or validating a large production dataset.

1. Generate a large dataset (this takes time!):
   ```bash
   PYTHONPATH=src python experiments/run_experiment.py \
     --config experiments/configs/bidless_dataset_collection.yaml \
     --seed 42 --n_per 50000 --emit-bidless-dataset
   ```

2. Open [20_charts_reference.ipynb](20_charts_reference.ipynb)

3. Set MODE in Config cell:
   ```python
   MODE = "full"        # Production quality
   DEMO_MODE = False    # Load existing dataset
   RUN_DIR = "../../data/runs/bidless_dataset_collection_YYYYMMDD_HHMMSS"
   ```

4. Run Phase 00-02 (Setup + Data Loading)

5. Run Phase 03 (Fail-Fast Tests) - **STOP if gates fail**

6. Explore Phases 04-08 for detailed analysis:
   - Phase 04: Feature Quality Checks
   - Phase 05: Bidless Analysis Charts
   - Phase 06: Outcome Evaluation & Reporting
   - Phase 07: Strategy Comparison & Multi-Suit Analysis
   - Phase 08: Summary & Quick Reference

**Expected runtime:**
- QUICK mode (~5000 hands): ~20 minutes
- FULL mode (≥50000 hands): ~2 hours (with caching, second run is instant)

**Why 50,000 hands?** Meets production threshold (per `docs/rules/05_rigor.md`: ≥50,000 for production reports).

### Workflow 3: Custom Exploration

**Use case:** You want to explore a specific hypothesis or feature relationship.

1. Copy the starter template:
   ```bash
   cp notebooks/phase0_bidless/30_model_dev_and_eval.ipynb \
      notebooks/sandbox/$(date +%Y_%m_%d)_my_hypothesis.ipynb
   ```

2. Follow the template structure (autoreload is pre-configured)

3. Use helpers from `src/bid_euchre/diagnostics/`:
   ```python
   from bid_euchre.diagnostics import (
       load_bidless_dataset,
       plot_feature_correlation,
       compute_seat_balance,
   )
   ```

4. Clear outputs before committing:
   ```bash
   jupyter nbconvert --ClearOutputPreprocessor.enabled=True \
     --inplace notebooks/sandbox/$(date +%Y_%m_%d)_my_hypothesis.ipynb
   ```

**Note:** Dated notebooks in `sandbox/` are exploratory and may be archived later.

## Understanding Directory Paths

### RUN_DIR vs DATASET_DIR

When you run an experiment, it creates a timestamped run directory:

```
data/runs/bidless_dataset_collection_20260130_143022/
├── meta.json                 # Experiment metadata
├── config_effective.yaml     # Config snapshot
├── perf.json                 # Performance metrics
└── datasets/                 # <-- DATASET_DIR (what notebooks need)
    ├── bidless.parquet       # Main dataset (fast loading)
    ├── bidless.jsonl         # Alternate format
    └── bidless_meta.json     # Dataset metadata
```

**In notebooks:**
- Set `DATASET_DIR = "../../data/runs/<run_id>/datasets"` (points to datasets subfolder)
- Set `RUN_DIR = "../../data/runs/<run_id>"` (points to run root)

**Why the distinction?**
- `10_health_checks.ipynb` uses `DATASET_DIR` (only needs parquet files)
- `20_charts_reference.ipynb` uses `RUN_DIR` (may load from run root or generate data)
- `30_model_dev_and_eval.ipynb` uses either (depends on your exploration)

## Which Notebook Should I Use?

| Notebook | Purpose | Input | Runtime | When to Use |
|----------|---------|-------|---------|-------------|
| [10_health_checks.ipynb](10_health_checks.ipynb) | Quick health check | Existing dataset | 30 sec | After generating any dataset |
| [20_charts_reference.ipynb](20_charts_reference.ipynb) | Comprehensive analysis | Loads or generates data | 20 min - 2 hrs | Production reports, deep validation |
| [30_model_dev_and_eval.ipynb](30_model_dev_and_eval.ipynb) | Custom analysis | Copy & modify | Varies | Hypothesis testing, feature exploration |

**Rule of thumb:**
- **Not sure?** Start with `10_health_checks.ipynb`
- **Need rigor?** Use `20_charts_reference.ipynb`
- **Exploring?** Copy `30_model_dev_and_eval.ipynb` to `sandbox/`

## Architecture

All Phase 0 notebooks use importable helpers from `src/bid_euchre/diagnostics/`:

```
src/bid_euchre/diagnostics/
├── loaders.py           # load_bidless_dataset(), load_meta()
├── health_checks.py     # compute_health_scorecard()
├── charts.py            # plot_*() functions
├── stats.py             # statistical analysis helpers
└── strategy_charts.py   # strategy comparison plots
```

**Benefits:**
- Notebooks stay thin (orchestration only)
- Code is testable and reusable
- No fork-and-drift between notebooks

## Dependencies

Install all dev dependencies:
```bash
pip install -e ".[dev]"
```

Required packages:
- pandas, matplotlib, numpy, scipy

Optional (for enhanced visualizations):
- seaborn

## Sample Size Guidelines

From `docs/rules/05_rigor.md`:

| Analysis Type | Minimum Sample Size | Purpose |
|---------------|---------------------|---------|
| Bias detection (seat/suit) | ≥2,000 deals | Quick validation |
| Feature correlation | ≥1,000 samples per group | Initial exploration |
| Tail analysis (CDF/CCDF) | ≥5,000 samples | Distribution tails |
| Production reports | ≥50,000 samples | Statistical rigor |

**For quick tests:** Use `--n_per 2000`
**For production:** Use `--n_per 50000` or higher

## See Also

- **Development Plan:** `docs/03_TODO/BIDDING_DEVELOPMENT_PLAN.md` - Phase 0 context
- **Diagnostics Module:** `src/bid_euchre/diagnostics/` - Importable helpers
- **Data Contract:** `docs/01_core/DATA_CONTRACT.md` - Dataset schema
- **Experiment Configs:** `experiments/configs/bidless_dataset_collection.yaml`
- **Rigor Standards:** `docs/rules/05_rigor.md` - Statistical requirements
- **Reproducibility:** `docs/01_core/REPRODUCIBILITY.md` - Determinism guarantees
