# R1.5-v2 Calibration Diagnostics Report

**Date:** 2026-03-09
**Script:** `scripts/internal/generate_r1_5_diagnostics.py`
**Seed:** 42

## 1. Executive Summary

This report presents within-rung calibration diagnostics for both R1.5
(action-value, target=net_points) and R0 (hybrid OLSa, target=tricks_won),
plus a cross-rung pattern comparison and training data distribution analysis.

The goal is to identify structural modeling deficiencies — particularly in the
suit contract — that may explain R1.5's suit deficit (-0.142 net_eppd vs R0 in
the FULL H2H battery) and inform R1.5-v2 design decisions.

**Key findings:** [TBD after running diagnostics]

## 2. R1.5 Within-Rung Diagnostics

Per-contract model diagnostics using the test split (10% of deals, split by
deal_id for leakage prevention).

### 2.1 Suit Contract

| Metric | Value |
|--------|-------|
| N (test) | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |
| RMSE | [TBD] |
| Mean residual | [TBD] |
| Residual skewness | [TBD] |
| Residual kurtosis | [TBD] |

**Calibration:** [TBD — describe calibration curve shape: over/under-prediction
regions, any systematic bias at prediction extremes]

**Heteroscedasticity:** [TBD — describe residual spread vs predicted value:
fan shape, constant variance, or discrete clusters]

**Residuals by bower count:** [TBD — do residuals shift systematically with
0/1/2+ bowers? Mean residual per group.]

### 2.2 High Contract

| Metric | Value |
|--------|-------|
| N (test) | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |
| RMSE | [TBD] |
| Mean residual | [TBD] |
| Residual skewness | [TBD] |
| Residual kurtosis | [TBD] |

**Calibration:** [TBD]

**Heteroscedasticity:** [TBD]

### 2.3 Low Contract

| Metric | Value |
|--------|-------|
| N (test) | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |
| RMSE | [TBD] |
| Mean residual | [TBD] |
| Residual skewness | [TBD] |
| Residual kurtosis | [TBD] |

**Calibration:** [TBD]

**Heteroscedasticity:** [TBD]

### 2.4 Pass Action

| Metric | Value |
|--------|-------|
| N (test) | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |
| RMSE | [TBD] |
| Mean residual | [TBD] |
| Residual skewness | [TBD] |
| Residual kurtosis | [TBD] |

**Calibration:** [TBD]

## 3. R0 Within-Rung Diagnostics

Per-contract diagnostics using R0's FULL eval data (50k deals). Note: R0
predicts tricks_won, not net_points — absolute R² values are not comparable
across rungs.

### 3.1 Suit Contract

| Metric | Value |
|--------|-------|
| N | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |
| RMSE | [TBD] |
| Mean residual | [TBD] |
| Residual skewness | [TBD] |
| Residual kurtosis | [TBD] |

**Calibration:** [TBD]

**Heteroscedasticity:** [TBD]

**Residuals by bower count:** [TBD]

### 3.2 High Contract

| Metric | Value |
|--------|-------|
| N | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |

### 3.3 Low Contract

| Metric | Value |
|--------|-------|
| N | [TBD] |
| R² | [TBD] |
| MAE | [TBD] |

## 4. Cross-Rung Pattern Comparison

> **Caveat:** R0 targets tricks_won; R1.5 targets net_points. Absolute R² values
> are not comparable. This section focuses on qualitative patterns only.

### 4.1 Which Contract Has Worst Calibration?

| Rung | Worst-calibrated contract | Evidence |
|------|--------------------------|----------|
| R0 | [TBD] | [TBD] |
| R1.5 | [TBD] | [TBD] |

### 4.2 Heteroscedasticity Pattern

| Rung | Contract | Pattern |
|------|----------|---------|
| R0 | suit | [TBD] |
| R0 | high | [TBD] |
| R0 | low | [TBD] |
| R1.5 | suit | [TBD] |
| R1.5 | high | [TBD] |
| R1.5 | low | [TBD] |

### 4.3 Residual Distribution Shape

| Rung | Contract | Unimodal/Bimodal | Evidence (GMM BIC delta) |
|------|----------|-----------------|--------------------------|
| R0 | suit | [TBD] | [TBD] |
| R0 | high | [TBD] | [TBD] |
| R0 | low | [TBD] | [TBD] |
| R1.5 | suit | [TBD] | [TBD] |
| R1.5 | high | [TBD] | [TBD] |
| R1.5 | low | [TBD] | [TBD] |
| R1.5 | pass | [TBD] | [TBD] |

## 5. Training Data Distribution

### 5.1 Contract Balance

| Contract Family | Count | Percentage |
|----------------|-------|------------|
| suit | [TBD] | [TBD] |
| high | [TBD] | [TBD] |
| low | [TBD] | [TBD] |
| pass | [TBD] | [TBD] |

### 5.2 net_points Distribution Shape

| Contract | Mean | Std | Skewness | Kurtosis | Min | Max |
|----------|------|-----|----------|----------|-----|-----|
| suit | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| high | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| low | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |
| pass | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] | [TBD] |

## 6. Bimodality Analysis

Bimodality is tested via Gaussian mixture model BIC comparison: fit 1-component
and 2-component GMMs, compute delta_BIC = BIC_1 - BIC_2. Positive delta
indicates 2-component model is a better fit (bimodal evidence).

| Classification | delta_BIC threshold |
|---------------|-------------------|
| None | < 2 |
| Weak | 2 to 10 |
| Strong | > 10 |

### 6.1 Residual Bimodality

| Rung | Contract | delta_BIC | Evidence |
|------|----------|-----------|----------|
| R1.5 | suit | [TBD] | [TBD] |
| R1.5 | high | [TBD] | [TBD] |
| R1.5 | low | [TBD] | [TBD] |
| R1.5 | pass | [TBD] | [TBD] |
| R0 | suit | [TBD] | [TBD] |
| R0 | high | [TBD] | [TBD] |
| R0 | low | [TBD] | [TBD] |

### 6.2 Target Variable Bimodality (R1.5 Training Data)

| Contract | delta_BIC | Evidence |
|----------|-----------|----------|
| suit | [TBD] | [TBD] |
| high | [TBD] | [TBD] |
| low | [TBD] | [TBD] |
| pass | [TBD] | [TBD] |

### 6.3 Interpretation

[TBD — If suit net_points is strongly bimodal (made/set bifurcation), this
explains why a linear model struggles: the residuals inherit the bimodal
structure of the target. This would motivate non-linear modeling (e.g., mixture
of experts, or separate made/set sub-models) as a Phase 2 direction.]

## 7. Implications for Phase 2

Based on the diagnostic findings above, the following specific recommendations
inform R1.5-v2 design:

### 7.1 Suit Contract Improvement

[TBD — e.g., if bimodality is confirmed: consider mixture model or
made-probability routing. If heteroscedasticity is bower-dependent: bower
interaction terms or bower-conditioned sub-models.]

### 7.2 Model Architecture

[TBD — e.g., if calibration curves show systematic bias at extremes: consider
non-linear transformation of predictions or quantile regression. If all
contracts show similar residual patterns: the issue is target choice, not
model architecture.]

### 7.3 Training Data

[TBD — e.g., if contract distribution is heavily imbalanced: consider
oversampling minority contracts. If pass dominates: the pass model's low R²
may be a sample-size issue.]

### 7.4 Priority Ranking

1. [TBD — highest-impact intervention based on findings]
2. [TBD]
3. [TBD]

## Provenance

- R1.5 artifact: `data/artifacts/arc_d/r1_5/action_value_full.json`
- R1.5 dataset: `data/runs/action_value_quick_42/datasets/action_value.parquet`
- R0 artifact: `data/artifacts/arc_d/r0/hybrid_r0_full.json`
- R0 eval data: `data/runs/arc_d_eval_r0_full_42_20260303_201732`
- Seed: 42
- Reproduction command:
```bash
uv run python scripts/internal/generate_r1_5_diagnostics.py \
  --r15-artifact data/artifacts/arc_d/r1_5/action_value_full.json \
  --r15-dataset data/runs/action_value_quick_42/datasets/action_value.parquet \
  --r0-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --r0-eval-dir data/runs/arc_d_eval_r0_full_42_20260303_201732 \
  --output-dir data/reports/arc_d/r1_5_v2/diagnostics \
  --seed 42
```
