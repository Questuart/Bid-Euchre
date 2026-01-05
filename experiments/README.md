# Experiments Directory

**Last updated:** 2026-01-04
**Organization:** Function-based subdirectories

This directory contains all experiment scripts for Bid Euchre simulation and analysis.

---

## 📂 Directory Structure

```
experiments/
├── analysis/          (7 scripts)  - Analyze simulation results
├── comparisons/       (9 scripts)  - Head-to-head strategy comparisons
├── dashboards/        (9 scripts)  - Multi-panel dashboard generators
├── data_generation/   (3 scripts)  - Training data generation
├── plotting/          (5 scripts)  - Individual plot generators
├── training/          (1 script)   - Model training
├── configs/           (10 YAML)    - Experiment configurations
├── _deprecated/       (15 scripts) - Superseded experiments
├── __init__.py                     - Auto-setup (no sys.path needed!)
├── REGISTRY.yaml                   - Complete experiment catalog
└── run_experiment.py               - Main unified runner
```

**Total:** 34 active scripts (down from 50+)

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
PYTHONPATH=src python experiments/dashboards/generate_bidder_models_dashboard.py
```

**Option 3: Find in Registry**
```bash
# Check REGISTRY.yaml for usage instructions
cat experiments/REGISTRY.yaml | grep -A 10 "my_experiment"
```

---

## 📁 Subdirectory Guide

### `analysis/` - Analysis Scripts

**Purpose:** Analyze simulation outputs, extract insights

**Scripts:**
- `analyze_bid_winners.py` - Which position wins bids?
- `analyze_bidding_distributions.py` - Bid amount distributions
- `analyze_position_impact.py` - Impact of bidder position
- `analyze_predicted_vs_actual.py` - Model calibration
- `analyze_suit_trick_distribution.py` - Trick distributions
- `evaluate_bidding_performance.py` - Bidding metrics
- `run_position_test.py` - Position validation test

**When to add here:** Scripts that process existing simulation results

---

### `comparisons/` - Head-to-Head Comparisons

**Purpose:** Compare strategies against each other

**Scripts:**
- `compare_top_four.py` - Top 4 strategies
- `compare_top_three.py` - Top 3 strategies
- `generate_paired_comparison.py` - Paired statistical comparison
- `run_bidding_comparison.py` - Three-horse race
- `run_full_head_to_head.py` - All-pairs comparison
- `run_head_to_head.py` - Simple head-to-head
- `run_olsa_policy_comparison.py` - Compare rounding policies
- `run_olsa_vs_ccrider.py` - Specific matchup
- `run_six_way_head_to_head.py` - Six-way comparison

**When to add here:** Scripts that run strategy vs strategy simulations

---

### `dashboards/` - Dashboard Generators

**Purpose:** Create multi-panel visualizations

**Scripts:**
- `generate_advanced_visualizations.py` - Hexbin, violin plots
- `generate_auction_points_heatmaps.py` - Auction analysis
- `generate_bidder_models_dashboard.py` - Model comparison
- `generate_hand_eval_dashboard.py` - Feature analysis
- `generate_head_to_head_report.py` - H2H results
- `generate_reports_from_split.py` - Split-specific reports
- `generate_strategy_comparison_dashboard.py` - Strategy overview
- `generate_top_four_metrics_heatmap.py` - Top 4 heatmap
- `generate_trick_strategy_dashboard.py` - Trick analysis

**When to add here:** Scripts that create comprehensive multi-panel figures

**Note:** Consider consolidating these using a base `DashboardGenerator` class

---

### `data_generation/` - Training Data Pipelines

**Purpose:** Generate and prepare training datasets

**Scripts:**
- `generate_bidder_training_data.py` - Run simulations for training
- `split_train_val_test.py` - Split JSONL into train/val/test
- `convert_splits_to_csv.py` - JSONL → CSV conversion

**When to add here:** Scripts that create or transform training data

---

### `plotting/` - Individual Plot Generators

**Purpose:** Create focused single plots

**Scripts:**
- `plot_all_feature_correlations.py` - All 40 features
- `plot_correlations_by_contract.py` - By contract type
- `plot_predicted_vs_actual.py` - Model calibration
- `plot_top_features_improved.py` - Hexbin/violin for top 9
- `plot_top_features_scatter.py` - Scatter with regression

**When to add here:** Scripts that create single-purpose visualizations

**vs dashboards/:** Use `plotting/` for single plots, `dashboards/` for multi-panel

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
   - Analysis → `analysis/`
   - Dashboard → `dashboards/`
   - Comparison → `comparisons/`
   - Training data → `data_generation/`
   - Plot → `plotting/`
   - Model training → `training/`

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
- analysis/: 7
- comparisons/: 9
- dashboards/: 9
- data_generation/: 3
- plotting/: 5
- training/: 1
- **Total active:** 34

**Config files:** 10

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
- `REGISTRY.yaml` - Complete experiment catalog
- `configs/` - All experiment configurations
- `docs/CONTRIBUTING.md` - Experiment standards
- `docs/ANTI_PATTERNS.md` - What to avoid
