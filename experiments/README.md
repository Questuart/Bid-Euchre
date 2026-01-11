# Experiments Directory

**Last updated:** 2026-01-04  
**Organization:** Function-based subdirectories

This directory contains all experiment scripts for Bid Euchre simulation and analysis.

---

## 📂 Directory Structure

```
experiments/
├── comparisons/       (1 script)   - Head-to-head strategy comparisons
├── training/          (1 script)   - Model training
├── configs/           (10 YAML)    - Experiment configurations
├── suites/            (2 YAML)     - Experiment suite definitions
├── _deprecated/       (15 scripts) - Superseded experiments
├── __init__.py                     - Auto-setup (no sys.path needed!)
├── REGISTRY.md                     - Complete experiment catalog (includes active, stable, and deprecated)
└── run_experiment.py               - Main unified runner
```

**Total:** 2 active scripts

---

## 🎯 Quick Start

### Running an Experiment

**Option 1: Use Unified Runner** (Preferred)
```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml
```

**Option 2: Run Specific Script**
```bash
PYTHONPATH=src python experiments/comparisons/run_head_to_head.py
```

**Option 3: Find in Registry**
```bash
# Check configs/ for current experiment configurations
ls experiments/configs/
```

---

## 📁 Subdirectory Guide


### `comparisons/` - Head-to-Head Comparisons

**Purpose:** Compare strategies against each other

**Scripts:**
- `run_head_to_head.py` - Simple head-to-head

**When to add here:** Scripts that run strategy vs strategy simulations

---




### `training/` - Model Training

**Purpose:** Train machine learning models

**Scripts:**
- `train_bidder_aware_models.py` - OLSa_v2 & OLSa_SR_v2

**When to add here:** Scripts that train and save models

**Requirements:**
- Must have corresponding YAML config
- Must use `model_io.save_model()`
- Must include train/val/test evaluation
- Must update `data/models/README.md`

---

### `configs/` - YAML Configurations ⭐

**Purpose:** Configuration files for all experiments

**Current configs:**
- `auction_smoke.yaml` - Auction mode smoke test
- `baseline_greedy.yaml` - Greedy strategy baseline
- `baseline_matchups.yaml` - 4x4 strategy matchup matrix
- `hand_eval_test_greedy.yaml` - Hand evaluation with greedy
- `hand_eval_test_random.yaml` - Hand evaluation with random
- `head_to_head_vs_random.yaml` - Head-to-head vs random
- `prelim_hand_eval.yaml` - Preliminary hand evaluation
- `quick_test.yaml` - Quick validation test
- `quick_test_random.yaml` - Quick test with random strategy
- `strategy_comparison.yaml` - Multi-strategy comparison

**Naming convention:** `<experiment_name>.yaml`

**Required fields:**
```yaml
experiment_name: my_experiment
parameters:
  n_hands: 10000
  seed: 42
# ... other parameters
```

---

### Deprecated experiments (`_deprecated/`) ⚠️

Content under `experiments/_deprecated/` is kept for reference only and is intentionally **not** held to the same bar as supported experiments.

- **Not supported from a clean checkout**: scripts may depend on external artifacts (local data, legacy outputs, trained models, etc.) that are not included in this repo.
- **Not for CI**: deprecated scripts are not expected to run in CI or as part of the standard `make` targets.
- **May require external artifacts/models**: you may need to generate or fetch artifacts before running anything under `_deprecated/`.

**See:** `experiments/_deprecated/README.md` for details and alternatives.  
**Preferred workflow:** `experiments/run_experiment.py` with `experiments/configs/`.

---

### `suites/` - Experiment Suite Definitions

**Purpose:** Define collections of experiments to run together

**Current suites:**
- `baseline_tiny.yaml` - Fast validation (~760 hands, seconds)
- `baseline_full.yaml` - Comprehensive regression (~5 min, 16 matchups + auction smoke)

**When to add here:** YAML files defining multiple experiments to run as a batch

---

## 🚀 Creating New Experiments

Follow these steps:

1. **Check if you need a new script**
   - Can `run_experiment.py` handle this? → Use config only
   - Need custom logic? → Proceed to step 2

2. **Create config file FIRST**
   - `experiments/configs/my_experiment.yaml`

3. **Choose subdirectory**
   - Comparison → `comparisons/`
   - Model training → `training/`

4. **Write script**
   - Accept `--config` argument
   - Use config for all parameters
   - No `sys.path` manipulation needed!

5. **Write integration test**
   - `tests/integration/test_my_experiment.py`

6. **Update registry**
   - Add entry to `REGISTRY.md`

7. **Run and validate**
   - Test with small dataset first
   - Check outputs are correct
   - Document results

---

## 📊 Statistics

**Script counts:**
- comparisons/: 1
- training/: 1
- **Total active:** 2

**Config files:** 10

**Deprecated:** 15

---

## 🔍 Finding Scripts

**Use the registry:**
```bash
# Find experiment by name
grep -A 10 "experiment_name" experiments/REGISTRY.md

# Find experiments by function
ls experiments/<subdirectory>/
```

**Or see:** `experiments/REGISTRY.md` for complete catalog with descriptions, usage, and outputs.
*Note: Includes both current (active/stable) and deprecated experiments.*

---

## 🧹 Maintenance

### Quarterly Audit
- [ ] Check for duplicate functionality
- [ ] Move superseded scripts to `_deprecated/`
- [ ] Update REGISTRY.md
- [ ] Consolidate similar scripts if > 5 in a category

### When Deprecating
1. Move to appropriate `_deprecated/` subdirectory
2. Update `_deprecated/README.md` with reason
3. Update REGISTRY.md status to "deprecated"
4. Keep for 6 months, then consider deleting if unused

---

**See also:**
- `REGISTRY.md` - Complete experiment catalog (active, stable, and deprecated experiments)
- `configs/` - All experiment configurations
- `docs/archive/ANTI_PATTERNS.md` - What to avoid

