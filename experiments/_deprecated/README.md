# Deprecated Experiments

This directory contains experiments that have been superseded, are one-offs that shouldn't be rerun, or are no longer maintained.

**Last updated:** 2026-01-04

---

## Directory Structure

```
_deprecated/
├── README.md (this file)
├── training/       # Old model training scripts
├── reports/        # Outdated report generators
├── analysis/       # One-off analysis scripts
├── generate_strategy_comparison.py
├── run_baseline_greedy.py
├── run_extended_comparison.py
└── run_strategy_comparison.py
```

---

## Why Scripts Are Deprecated

### Root Level (Original Deprecated Scripts)

**Status:** Superseded by unified `run_experiment.py`  
**Date deprecated:** ~2025-12-15  
**Reason:** These were early custom runners before the unified experiment framework was established.

- `generate_strategy_comparison.py` → Use `run_experiment.py` with `strategy_comparison.yaml`
- `run_baseline_greedy.py` → Use `run_experiment.py` with `baseline_greedy.yaml`
- `run_extended_comparison.py` → Use `run_experiment.py` with custom config
- `run_strategy_comparison.py` → Use `run_experiment.py` with `strategy_comparison.yaml`

---

## training/ - Deprecated Training Scripts

**Status:** Superseded by `train_bidder_aware_models.py`  
**Date deprecated:** 2026-01-04  
**Reason:** These scripts trained models without `is_bidder` feature. The new bidder-aware models (OLSa_v2, OLSa_SR_v2) include positional awareness and are strictly better.

### `train_baseline_regression.py`
- **Purpose:** Train original OLS models (trump_count, bowers, aces)
- **Superseded by:** `train_bidder_aware_models.py` (OLSa_v2)
- **Models produced:** `data/models/baseline_ols/` (may still exist)
- **Issue:** No is_bidder feature → can't distinguish bidder advantage

### `train_hand_value_ols.py`
- **Purpose:** Train Hand Value (rank sum) models
- **Superseded by:** `train_bidder_aware_models.py` (OLSa_SR_v2)
- **Models produced:** `data/models/hand_value_ols/` (still used by OLSa_SR)
- **Issue:** No is_bidder feature

### `train_linear_v2_regression.py`
- **Purpose:** Train "improved" baseline OLS (v2)
- **Superseded by:** `train_bidder_aware_models.py`
- **Issue:** Iteration on features, but missing is_bidder

### `train_simple_rank_ols.py`
- **Purpose:** Train simple rank-based OLS
- **Superseded by:** `train_hand_value_ols.py` and then `train_bidder_aware_models.py`
- **Issue:** Exploratory, not production quality

### `train_expanded_ols.py`
- **Purpose:** Train OLS with many features to test multicollinearity
- **Outcome:** Found severe multicollinearity (VIF > 10 for many features)
- **Status:** Research/exploratory only
- **Recommendation:** Use Ridge if expanding features

### `train_ridge_regression.py`
- **Purpose:** Train Ridge regression to handle multicollinearity
- **Outcome:** Minimal R² improvement over simple OLS (~0.01)
- **Status:** Not worth complexity for current feature sets
- **Note:** May revisit if adding many correlated features

**Migration path:**
- If you need models without is_bidder, use existing `data/models/baseline_ols/` or `data/models/hand_value_ols/`
- For new production models, always use `train_bidder_aware_models.py`

---

## reports/ - Deprecated Report Generators

**Status:** Outdated or superseded  
**Date deprecated:** 2026-01-04

### `generate_health_dashboard.py`
- **Purpose:** System health monitoring dashboard
- **Reason:** Not maintained, unclear what "health" means
- **Status:** Abandoned

### `generate_all_reports.py`
- **Purpose:** Master script to run all report generators
- **Reason:** Many reports have changed, script is out of date
- **Recommendation:** Run specific report generators as needed

### `generate_dashboard.py`
- **Purpose:** Generic dashboard generator (early version)
- **Superseded by:** Specific dashboard generators like:
  - `generate_strategy_comparison_dashboard.py`
  - `generate_bidder_models_dashboard.py`
  - `generate_hand_eval_dashboard.py`

**Migration path:**
- Use specific dashboard generators for current needs
- If creating new dashboards, follow existing patterns in active generators

---

## analysis/ - One-Off Analysis Scripts

**Status:** One-off explorations, not meant to be rerun  
**Date deprecated:** 2026-01-04

### `analyze_ccrider_vs_ceiling.py`
- **Purpose:** Deep dive on OLSa_CCrider vs OLSa_Ceiling comparison
- **Context:** Part of rounding policy exploration (floor, ceil, ccrider)
- **Outcome:** CCrider didn't significantly outperform, not pursued further
- **Status:** Historical analysis, results documented in reports

### `evaluate_dummy_baseline.py`
- **Purpose:** Evaluate "always bid 5" dummy baseline
- **Context:** Established baseline for bidding model comparison
- **Outcome:** FiveHeadFred strategy created, baseline established
- **Status:** One-time baseline establishment, no need to rerun

**Migration path:**
- If you need similar analysis, copy structure but update for current models
- Results from these scripts are in `data/reports/` (if still relevant)

---

## How to Use Deprecated Scripts

### Option 1: Don't (Recommended)
Most of these scripts should not be rerun. Their functionality has been:
- **Integrated into unified runner** (for strategy comparisons)
- **Superseded by better models** (for training scripts)
- **Completed one-time** (for exploratory analysis)

### Option 2: Reference for New Work
If building something similar:
1. Read the script to understand approach
2. Copy useful patterns/structure
3. Create new script with current best practices:
   - Add YAML config
   - Use unified experiment framework where possible
   - Include proper metadata and reproducibility hooks

### Option 3: Resurrect (Last Resort)
If you really need to run one:
1. Check `experiments/REGISTRY.yaml` for modern equivalent
2. If none exists and you need this functionality, consider:
   - Updating script to current standards (config, metadata, etc.)
   - Moving back to `experiments/` if it will be used regularly
   - Keeping here if truly a one-off

---

## Cleanup Policy

### When to Deprecate
Move scripts here if:
- ✅ Superseded by a better script
- ✅ One-off exploration that's complete
- ✅ No longer maintained and broken
- ✅ Functionality integrated into unified framework

Keep in main `experiments/` if:
- ❌ Actively used in production
- ❌ Part of regular analysis workflow
- ❌ Referenced in current documentation
- ❌ Generates reports still being reviewed

### Retention Policy
- **Keep for 6 months** minimum (in case we need to reference)
- **Delete after 1 year** if:
  - No references in current code
  - Superseded functionality is stable
  - Results no longer relevant

### Documentation Requirements
When deprecating, document:
1. Why it was deprecated
2. What supersedes it (if anything)
3. Where to find any results it produced
4. Migration path for anyone who needs similar functionality

---

## Recovery Procedure

If you need to recover a deprecated script:

```bash
# Check git history
git log -- experiments/_deprecated/<script_name>.py

# Restore if needed
git checkout <commit_hash> -- experiments/_deprecated/<script_name>.py
mv experiments/_deprecated/<script_name>.py experiments/

# Update to current standards before using!
```

---

## Questions?

If unclear why something was deprecated or you need similar functionality:
1. Check `experiments/REGISTRY.yaml` for current experiments
2. Review this README for superseding scripts
3. Search git history for context: `git log --all --grep="<script_name>"`
4. Ask in project discussions if still unclear

---

**Remember:** Deprecation is healthy! It means we're evolving and improving. These scripts served their purpose and helped us get to where we are now. 🚀
