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
├── configs/           (12 YAML)    - Experiment configurations
├── suites/            (1 YAML)     - Experiment suite definitions
├── _deprecated/       (15 scripts) - Superseded experiments
├── __init__.py                     - Auto-setup (no sys.path needed!)
├── REGISTRY.yaml                   - Complete experiment catalog (includes active, stable, and deprecated)
└── run_experiment.py               - Main unified runner
```

**Total:** 34 active scripts (down from 50+)

---

## 🎯 Quick Start

### Single Experiment
```bash
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/baseline_greedy.yaml
```

### Experiment Suite
```bash
PYTHONPATH=src python scripts/run_suite.py experiments/suites/baseline_tiny.yaml
```

### Generate Report
```bash
PYTHONPATH=src python scripts/generate_report.py --experiment baseline_greedy
```

---

## 📁 Subdirectory Guide

### `comparisons/` - Head-to-Head Comparisons

**Purpose:** Compare strategies against each other

**Scripts:**
- `run_head_to_head.py` - Backward-compatibility wrapper (use configs instead)

**When to add here:** Only backward-compatibility wrappers. Use configs + unified runner for new comparisons.

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
- `baseline_greedy.yaml`
- `bidder_training_data.yaml`
- `hand_eval_test_greedy.yaml`
- `hand_eval_test_random.yaml`
- `head_to_head_vs_random.yaml`
- `position_test.yaml`
- `prelim_hand_eval.yaml`
- `quick_test.yaml`
- `strategy_comparison.yaml`
- `train_bidder_models.yaml`

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

### `suites/` - Experiment Suite Definitions

**Purpose:** Define collections of experiments to run together

**Current suites:**
- `baseline_tiny.yaml` - Small test suite for validation

**When to add here:** YAML files defining multiple experiments to run as a batch

---

### `_deprecated/` - Superseded Experiments

**Purpose:** Historical experiments no longer used

**See:** `_deprecated/README.md` for details on each deprecated script

**When to add here:**
- Script superseded by better version
- One-off exploration completed
- Functionality integrated into unified runner

---

## 🚀 Creating New Experiments

Follow these steps (from `CONTRIBUTING.md`):

1. **Check if you need a new script**
   - Can `run_experiment.py` handle this? → Use config only
   - Need custom logic? → Proceed to step 2

2. **Create config file FIRST**
   - `experiments/configs/my_experiment.yaml`

3. **Choose subdirectory**
   - Comparison → `comparisons/` (wrappers only)
   - Model training → `training/` (legacy scripts only)

4. **Write script**
   - Accept `--config` argument
   - Use config for all parameters
   - No `sys.path` manipulation needed!

5. **Write integration test**
   - `tests/integration/test_my_experiment.py`

6. **Update registry**
   - Add entry to `REGISTRY.yaml`

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

**Config files:** 12

**Suite files:** 1

**Deprecated:** 15

---

## 🔍 Finding Scripts

**Use the registry:**
```bash
# Find experiment by name
grep -A 10 "experiment_name" experiments/REGISTRY.yaml

# Find experiments by function
ls experiments/<subdirectory>/
```

**Or see:** `experiments/REGISTRY.yaml` for complete catalog with descriptions, usage, and outputs.
*Note: Includes both current (active/stable) and deprecated experiments.*

---

## 🧹 Maintenance

### Quarterly Audit
- [ ] Check for duplicate functionality
- [ ] Move superseded scripts to `_deprecated/`
- [ ] Update REGISTRY.yaml
- [ ] Consolidate similar scripts if > 5 in a category

### When Deprecating
1. Move to appropriate `_deprecated/` subdirectory
2. Update `_deprecated/README.md` with reason
3. Update REGISTRY.yaml status to "deprecated"
4. Keep for 6 months, then consider deleting if unused

---

**See also:**
- `REGISTRY.yaml` - Complete experiment catalog (active, stable, and deprecated experiments)
- `configs/` - All experiment configurations
- `docs/CONTRIBUTING.md` - Experiment standards
- `docs/ANTI_PATTERNS.md` - What to avoid

