# Deprecated Experiment Configurations

These experiment configurations have been moved from `experiments/configs/` because they reference external artifacts (models, training data, large datasets) that are not available in a clean checkout.

## Moved Configurations

### position_test.yaml
**Requires:** Pre-trained baseline regression models in `data/models/baseline_regression/` and output directory `data/hand_logs/`
**Purpose:** Test positional tracking features using regression-based bidding strategies
**To restore:** Train baseline models first, then run this config

### train_bidder_models.yaml
**Requires:** Training data files in `data/training/` (bidder_aware_train.csv, bidder_aware_val.csv, bidder_aware_test.csv) and model output directories in `data/models/`
**Purpose:** Train bidder-aware OLS regression models for bidding
**To restore:** Generate training data using bidder training data generation scripts, then run this config

### bidder_training_data.yaml
**Requires:** Legacy hand value OLS models in `data/models/legacy/hand_value_ols/` (hand_value_ols_suit.pkl, hand_value_ols_high.pkl, hand_value_ols_low.pkl)
**Purpose:** Generate training data for bidder-aware models using existing hand evaluation models
**To restore:** Ensure legacy hand value models are available, then run this config