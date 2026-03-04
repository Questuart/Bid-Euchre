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

## Quick Start

### Prerequisites

Ensure all dependencies are installed:
```bash
# From repo root
uv sync --all-extras
```

### Workflow

**Step 1:** Run a notebook with on-the-fly data generation

```bash
# Navigate to notebook directory
cd notebooks/phase0_bidless

# Launch Jupyter
jupyter lab
```

**Step 2:** Open any notebook and configure:

```python
MODE = "QUICK"  # Fast iteration (~2k deals, <1 min)
# MODE = "FULL"   # Statistical rigor (~50k deals, ~5-10 min)

SEED = 42       # For reproducibility
```

Notebooks generate data on-the-fly using `load_or_generate_*()` functions, controlled by `MODE` (SMOKE/QUICK/FULL). Data is cached after first generation.

**Step 3:** Run all cells. Data will be generated automatically on first run and cached for subsequent runs.

## Notebooks

### 10_feature_health_checks.ipynb
**Purpose:** Feature validation and bias detection

**What it does:**
- Validates hand feature distributions
- Checks for seat bias (seats should have equal feature distributions)
- Checks for trump bias (trump suits should be balanced)
- Verifies feature schema compliance

**When to use:**
- After generating any bidless dataset
- To validate feature extraction logic
- Before training ML models

**Runtime:** ~30 seconds (uses existing dataset, no generation needed)

---

### 20_outcome_health_checks.ipynb
**Purpose:** Outcome validation (tricks_won)

**What it does:**
- Generates gameplay outcomes on-the-fly using `load_or_generate_outcomes()`
- Validates outcome ranges (0-10 tricks)
- Checks contract-type breakdown (suit/high/low)
- Tests reproducibility (same seed → same results)
- Analyzes outcome distributions by contract, seat, trump
- Strategy matchup analysis (if multiple strategies)
- CDF/CCDF tail analysis

**When to use:**
- To validate simulation outcomes
- To check for gameplay bugs or biases
- Before using outcomes for model training

**Runtime:**
- QUICK mode: ~30 seconds (generates ~300 hands)
- FULL mode: ~5-10 min (generates ~10k+ hands, first run only - cached thereafter)

**Key feature:** Uses `load_or_generate_outcomes()` which automatically:
1. Generates experiment config
2. Runs simulation
3. Parses logs to extract tricks_won
4. Caches results for instant reload

---

### 30_feature_outcome_eval.ipynb
**Purpose:** Feature-outcome relationship analysis

**What it does:**
- Loads features + outcomes using `load_or_generate_features()`
- **Section 2:** Computes feature-outcome correlations by contract type
- **Section 3:** Analyzes seat position effects
- **Section 4:** Examines trump suit effects (suit contracts only)
- **Section 5:** Compares feature importance across contract types
- **Section 6:** Health scorecard and model development recommendations

**When to use:**
- To identify predictive features for ML models
- To understand which features matter for each contract type
- Before feature selection or model training

**Runtime:**
- QUICK mode: ~1 min (includes data generation + analysis)
- FULL mode: ~10-15 min (first run only)

**Key outputs:**
- Top 10-15 features per contract type (ranked by |correlation|)
- Statistical significance tests (p-values)
- Visualization: correlation bar charts, violin plots, heatmaps

---

## Data Generation Workflow

All notebooks use the new `load_or_generate_*()` functions from `bid_euchre.diagnostics.notebook_data`:

```python
from bid_euchre.diagnostics.notebook_data import (
    load_or_generate_outcomes,    # Outcomes only (tricks_won)
    load_or_generate_features,    # Features + outcomes
)

# Generate or load cached outcomes
df = load_or_generate_outcomes(
    mode="QUICK",  # or "FULL"
    seed=42,
    contracts=['suit', 'high', 'low'],
    trumps=['C', 'D', 'H', 'S'],
    seats=[0, 1, 2, 3],
)
```

**How it works:**
1. Computes cache key from parameters (mode, seed, contracts, trumps, seats)
2. Checks scratchpad cache for existing data
3. If cache hit: loads and returns instantly
4. If cache miss:
   - Generates experiment config YAML on-the-fly
   - Runs `experiments/run_experiment.py` via subprocess
   - Parses JSONL logs to extract tricks_won
   - Joins with bidless dataset (for features)
   - Caches result
   - Returns DataFrame

**Benefits:**
- ✅ No pre-generated datasets required
- ✅ Reproducible (same seed → same results)
- ✅ Fast iteration (cached after first run)
- ✅ Mode-aware (QUICK for demos, FULL for rigor)

## Which Notebook Should I Use?

| Notebook | Purpose | Input | Runtime | When to Use |
|----------|---------|-------|---------|-------------|
| [10_feature_health_checks.ipynb](10_feature_health_checks.ipynb) | Feature validation | Existing dataset | ~30 sec | After generating any dataset |
| [20_outcome_health_checks.ipynb](20_outcome_health_checks.ipynb) | Outcome validation | Generates on-the-fly | ~30 sec (QUICK) | To validate simulation outcomes |
| [30_feature_outcome_eval.ipynb](30_feature_outcome_eval.ipynb) | Feature-outcome analysis | Generates on-the-fly | ~1 min (QUICK) | Before model training, feature selection |

**Rule of thumb:**
- **Not sure?** Start with `10_feature_health_checks.ipynb` on an existing dataset
- **No dataset?** Use `20_outcome_health_checks.ipynb` to generate and validate outcomes
- **ML prep?** Use `30_feature_outcome_eval.ipynb` to identify predictive features

## Architecture

All Phase 0 notebooks use importable helpers from `src/bid_euchre/diagnostics/`:

```
src/bid_euchre/diagnostics/
├── loaders.py           # load_bidless_dataset(), load_meta()
├── notebook_data.py     # load_or_generate_outcomes(), load_or_generate_features()
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

```bash
# Install all dev dependencies
uv sync --all-extras
```

Required packages:
- pandas, matplotlib, numpy, scipy, seaborn
- pyarrow (for Parquet support)
- pyyaml (for config generation)

## Sample Size Guidelines

From `.claude/rules/05_rigor.md`:

| Analysis Type | Minimum Sample Size | Mode | Purpose |
|---------------|---------------------|------|---------|
| Bias detection (seat/suit) | ≥2,000 deals | QUICK | Quick validation |
| Feature correlation | ≥1,000 samples per group | QUICK | Initial exploration |
| Tail analysis (CDF/CCDF) | ≥5,000 samples | FULL | Distribution tails |
| Production reports | ≥50,000 samples | FULL+ | Statistical rigor |

**For quick tests:** Use `MODE="QUICK"` (~2k deals)
**For production:** Use `MODE="FULL"` (~50k deals) or customize `n_per` in config

## Archived Notebooks

Older notebooks have been archived to `archive/`:
- `20_charts_reference.ipynb` - Monolithic comprehensive analysis (superseded by focused 20/30 notebooks)
- `30_model_dev_and_eval.ipynb` - Old template (superseded by 30_feature_outcome_eval.ipynb)

See `archive/README.md` for details on archived notebooks.

## See Also

- **Diagnostics Module:** `src/bid_euchre/diagnostics/` - Importable helpers
- **Data Contract:** `docs/01_core/DATA_CONTRACT.md` - Dataset schema
- **Experiment Configs:** `experiments/configs/bidless_dataset_collection.yaml`
- **Rigor Standards:** `.claude/rules/05_rigor.md` - Statistical requirements
- **Reproducibility:** `docs/01_core/REPRODUCIBILITY.md` - Determinism guarantees
