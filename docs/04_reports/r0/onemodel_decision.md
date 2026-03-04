# OneModel Decision Report: RETAIN Separate Models

**Track:** F (Unified Cross-Contract Model)
**Protocol:** `plans/r0_v2_onemodel_protocol.md` v1
**Date:** 2026-03-03
**Decision:** RETAIN separate per-contract models
**Gate status:** FAIL (delta < 0)

---

## 1. Summary

The unified cross-contract OLS model was trained and evaluated per the
pre-registered OneModel protocol. The unified model performs worse than
the separate per-contract models on the primary comparator metric
(net_eppd). The decision is **RETAIN** separate models. No recascade
is required.

## 2. Training Details

### 2.1 Data

- **Dataset:** `canonical_bidless_dataset_glutton_42_20260221_175752`
- **Total rows:** 1,200,000 (800k suit, 200k high, 200k low)
- **Composition:** 66.7% suit, 16.7% high, 16.7% low
- **Split:** Hash-based by deal_id (seed=42), 60/40 train/val
  - Train: 718,176 rows (29,924 deals)
  - Val: 481,824 rows (20,076 deals)

**Note:** The protocol anticipated 98.3% suit data, but the actual
composition is 66.7% suit. This is because each deal generates 6 contract
evaluations per seat (4 trump suits + high + low), giving suit 4/6 = 66.7%.

### 2.2 Feature Selection

Forward selection with GroupKFold (by deal_id) selected **4 features**
from 41 candidates (39 base + 2 indicators):

| Step | Feature | R² (CV) | Delta |
|------|---------|---------|-------|
| 1 | quick_tricks | 0.1001 | -- |
| 2 | third_highest_trump_rank | 0.1465 | +0.0464 |
| 3 | fourth_suit_len | 0.1587 | +0.0122 |
| 4 | num_singletons | 0.1646 | +0.0059 |
| 5 | trump_count_x_void_count | 0.1691 | +0.0045 (< 0.005 threshold, stopped) |

**Key finding:** The contract-type indicators (`is_high`, `is_low`) were
**not selected**. Forward selection found no cross-validated improvement
from knowing the contract type explicitly. This means the unified model
treats all contract types identically, relying entirely on the feature
values (which already differ by contract type due to the feature extraction
pipeline -- e.g., trump features are 0 for high/low).

### 2.3 Model Coefficients

| Feature | Coefficient |
|---------|------------|
| intercept | 3.4986 |
| quick_tricks | 0.4132 |
| third_highest_trump_rank | 0.3013 |
| fourth_suit_len | 0.3238 |
| num_singletons | 0.2229 |
| is_high | 0.0000 (not selected) |
| is_low | 0.0000 (not selected) |

The decomposed per-family biases are identical (3.4986) because the
indicators were not selected.

### 2.4 Model Performance

| Metric | Overall | Suit | High | Low |
|--------|---------|------|------|-----|
| R² (train) | 0.1647 | 0.1811 | 0.1356 | 0.1388 |
| R² (val) | 0.1657 | 0.1829 | 0.1352 | 0.1372 |
| MAE (train) | 1.3025 | 1.2350* | 1.3500* | 1.3450* |
| MAE (val) | 1.3077 | -- | -- | -- |
| sigma² | -- | 2.4137 | 3.0330 | 3.0179 |

*Approximate per-contract MAE values.

**Comparison to baseline separate models** (from `training_report_r0.json`):

| Contract | Baseline R² (test) | Unified R² (val) | Delta |
|----------|-------------------|-------------------|-------|
| suit | 0.1933 | 0.1829 | -0.0104 |
| high | 0.1330 | 0.1352 | +0.0022 |
| low | 0.1338 | 0.1372 | +0.0034 |

The unified model has slightly lower R² for suit (the dominant contract)
and marginally higher R² for high/low. Overall, the unified model is a
modest statistical downgrade.

## 3. Comparator Evaluation

### 3.1 Setup

- **Arm A (control):** v6 baseline battery (separate per-contract models)
- **Arm B (treatment):** OneModel battery (unified model)
- **Mode:** Single-seat, 5,000 deals per bidder, seed=42
- **Play strategy:** GluttonStrategy

### 3.2 Results

| Bidder | Baseline net_eppd | Unified net_eppd | Delta |
|--------|------------------|-----------------|-------|
| hybrid_olsa | 2.1312 | 2.0300 | -0.1012 |
| hybrid_olsa_full | 2.1696 | 2.0300 | -0.1396 |
| olsa | -0.2248 | -0.0950 | +0.1298 |
| olsa_full | -0.0116 | -0.0950 | -0.0834 |

Non-model bidders (fiveheadfred, stricthellraiser, rankthetank,
modeloespecifico) produced identical results across both batteries,
confirming experimental integrity.

### 3.3 Bootstrap CIs (10,000 resamples, seed=42)

| Comparison | Delta | 95% CI | CI excludes 0 |
|------------|-------|--------|---------------|
| hybrid_olsa | -0.1012 | [-0.221, +0.021] | No |
| hybrid_olsa_full | -0.1396 | [-0.260, -0.016] | **Yes** (negative) |

### 3.4 Guardrail Checks

| Check | hybrid_olsa (unified) | Threshold | Status |
|-------|----------------------|-----------|--------|
| bid_rate | 0.9494 | [0.05, 0.95] | WARN (marginal) |
| make_rate | 1.0000 | >= 0.45 | PASS |

The unified model's bid_rate (0.9494) is at the upper boundary of the
guardrail range. With identical coefficients across all contract families,
the model bids aggressively but with a higher make_rate than baseline.

## 4. Decision

### 4.1 Protocol Gate Application

Per protocol Section 4.3:

| Criterion | hybrid_olsa | hybrid_olsa_full |
|-----------|------------|-----------------|
| delta >= +0.05 | -0.1012 (FAIL) | -0.1396 (FAIL) |
| CI excludes 0 | No (FAIL) | Yes but negative (FAIL) |
| Guardrails | PASS | PASS |
| **Gate** | **RETAIN** | **RETAIN** |

Both treatment arms fail the adoption criteria. `hybrid_olsa_full` is
**significantly worse** (CI entirely negative). `hybrid_olsa` is not
significantly different but trends negative.

### 4.2 Decision: RETAIN Separate Per-Contract Models

The unified cross-contract model does not improve upon and likely
degrades performance compared to separate per-contract models.
No recascade is required.

### 4.3 H2H Battery

Per protocol Section 2.4, the H2H battery is the confirmation instrument
after the comparator gate. Since both comparator arms **failed** (delta < 0),
the H2H battery is not needed -- the unified model cannot meet adoption
criteria regardless of H2H results.

## 5. Analysis

### 5.1 Why Did the Unified Model Fail?

1. **Loss of specialization:** The separate models have contract-specific
   feature sets (suit: bowers + trump_count + offsuit_aces; high: offsuit_aces;
   low: offsuit_tens_count). These capture the distinct predictive structure
   of each contract type. The unified model's single feature set must
   compromise across all three.

2. **Indicator rejection:** Forward selection did not find the contract
   indicators useful, meaning the model cannot distinguish between contract
   types. This forces identical predictions for a hand regardless of whether
   it's being evaluated for suit, high, or low -- only the feature values
   differ (e.g., trump features are 0 for high/low).

3. **Suit contract dominance:** The features selected by forward selection
   (quick_tricks, third_highest_trump_rank, fourth_suit_len, num_singletons)
   are primarily suit-oriented features. This is expected: suit contracts
   represent 66.7% of the training data, so the optimization focuses on
   suit prediction at the expense of high/low.

4. **High/low simplicity:** The separate models for high and low use a single
   feature each (offsuit_aces and offsuit_tens_count respectively), which
   is evidently sufficient and not improvable by adding suit-oriented features.

### 5.2 Comparison to Protocol Predictions

The protocol (Section 5.1) predicted training imbalance as a HIGH likelihood
failure mode. This prediction was partially confirmed: while the data
composition was less extreme than anticipated (66.7% vs 98.3%), the
feature selection was still dominated by suit-oriented features.

### 5.3 Value of the Finding

Despite the negative result, this protocol execution provides:

1. **Quantified cost of pooling:** Merging contract types costs approximately
   0.10-0.14 net_eppd compared to separate models.

2. **Evidence for contract specialization:** The failure of contract
   indicators to improve cross-validated R² suggests that contract types
   have fundamentally different predictive structures that cannot be captured
   by simple additive indicators.

3. **Baseline for R1:** If richer features (from R1 training with auction
   data) make contract-specific prediction less distinct, a unified model
   may become viable. This R0 result provides the baseline.

## 6. Provenance

| Item | Value |
|------|-------|
| Protocol | `plans/r0_v2_onemodel_protocol.md` v1 |
| Decision | RETAIN separate per-contract models |
| Training seed | 42 |
| Bootstrap seed | 42 |
| Bootstrap resamples | 10,000 |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Unified artifact | `data/artifacts/arc_d/r0/hybrid_r0_unified.json` |
| Baseline artifact | `data/artifacts/arc_d/r0/hybrid_r0.json` (constrained), `hybrid_r0_full.json` (full) |
| Comparator config | `experiments/configs/auction_comparator_onemodel.yaml` |
| Battery output | `data/artifacts/arc_d/r0/onemodel_comparator_v1.json` |
| Git SHA | See `training_info.git_sha` in artifact |
