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

**Key findings:**

1. Suit is the BEST-fitting R1.5 model (R^2=0.557), not the worst — the suit
   gameplay deficit (-0.142 net_eppd) is NOT explained by poor model fit.
2. Bimodality is UNIVERSAL across all R1.5 contracts (suit delta_BIC=4081,
   high=1469, low=1286), driven by the make/set structure in net_points.
3. R0 residuals are unimodal for high/low (tricks_won is naturally unimodal)
   and weakly bimodal for suit only (delta_BIC=31).
4. The suit regression is a decision-layer interaction, not a prediction
   quality issue — suit has the best R^2 but the worst gameplay delta.
5. Pass model has R^2=0.042 with n=10,000 training rows (only 2.1% of data)
   — near-zero predictive power, but this reflects that pass net_points
   depends on the declaring team's outcome, not the passer's hand.

## 2. R1.5 Within-Rung Diagnostics

Per-contract model diagnostics using the test split (10% of deals, split by
deal_id for leakage prevention).

### 2.1 Suit Contract

| Metric | Value |
|--------|-------|
| N (test) | 30,896 |
| R^2 | 0.557 |
| MAE | 4.128 |
| RMSE | 5.391 |
| Mean residual | 0.087 |
| Residual skewness | 0.827 |
| Residual kurtosis | 0.812 |

**Calibration:** Systematic positive bias (mean residual +0.087) indicating
slight under-prediction of net_points on average. Predictions cluster in the
mid-range between the make and set modes, systematically wrong for both
regimes — over-predicting for set outcomes and under-predicting for make
outcomes.

**Heteroscedasticity:** Strong heteroscedastic pattern with bimodal residual
clusters. Residuals split into two distinct groups corresponding to make
(positive net_points) and set (negative net_points) outcomes. The OLS model
predicts the mean of the bimodal distribution, producing residuals that
inherit the two-mode structure.

**Residuals by bower count:** Bower count modulates the make/set probability
but does not eliminate bimodality. Hands with 2+ bowers have higher make rates
(smaller negative residuals on average), but the bimodal cluster structure
persists across all bower counts.

### 2.2 High Contract

| Metric | Value |
|--------|-------|
| N (test) | 7,724 |
| R^2 | 0.525 |
| MAE | 4.222 |
| RMSE | 5.595 |
| Mean residual | 0.115 |
| Residual skewness | 1.006 |
| Residual kurtosis | 1.192 |

**Calibration:** Positive bias (mean residual +0.115), slightly worse than
suit. The same between-mode prediction pattern as suit — OLS averages over the
make/set bifurcation.

**Heteroscedasticity:** Bimodal residual clusters matching the make/set
structure. Pattern is qualitatively identical to suit but with slightly higher
skewness (1.006 vs 0.827), indicating a more asymmetric make/set split.

### 2.3 Low Contract

| Metric | Value |
|--------|-------|
| N (test) | 7,724 |
| R^2 | 0.514 |
| MAE | 4.277 |
| RMSE | 5.631 |
| Mean residual | 0.116 |
| Residual skewness | 0.916 |
| Residual kurtosis | 0.983 |

**Calibration:** Positive bias (mean residual +0.116), comparable to high.
Lowest R^2 among bid contracts (0.514) but the gap is modest.

**Heteroscedasticity:** Bimodal residual clusters, same pattern as suit and
high. The make/set bifurcation drives the same structural issue across all
bid contracts.

### 2.4 Pass Action

| Metric | Value |
|--------|-------|
| N (test) | 1,000 |
| R^2 | 0.042 |
| MAE | 3.524 |
| RMSE | 5.195 |
| Mean residual | 0.160 |
| Residual skewness | 0.455 |
| Residual kurtosis | 1.253 |

**Calibration:** Near-zero predictive power (R^2=0.042). The model explains
almost none of the variance in pass net_points. This is expected: a passer's
net_points depends on the declaring team's contract outcome (which team
declares, what they bid, whether they make), not on the passer's own hand
features. The positive bias (+0.160) is the largest across contracts.

## 3. R0 Within-Rung Diagnostics

Per-contract diagnostics using R0's FULL eval data (50k deals). Note: R0
predicts tricks_won, not net_points — absolute R^2 values are not comparable
across rungs.

### 3.1 Suit Contract

| Metric | Value |
|--------|-------|
| N | 121,172 |
| R^2 | 0.223 |
| MAE | 1.523 |
| RMSE | 1.901 |
| Mean residual | -0.004 |
| Residual skewness | 0.138 |
| Residual kurtosis | -0.152 |

**Calibration:** Well-calibrated with near-zero mean residual (-0.004). No
systematic bias. The tricks_won target is naturally unimodal (centered near 5),
so OLS predictions track the single mode effectively.

**Heteroscedasticity:** Near-homoscedastic residuals. No bimodal clustering.
Residual variance is approximately constant across the prediction range,
consistent with the unimodal tricks_won target.

**Residuals by bower count:** Residual skewness is low (0.138) and kurtosis
is slightly negative (-0.152), indicating near-normal residuals without the
bimodal structure seen in R1.5.

### 3.2 High Contract

| Metric | Value |
|--------|-------|
| N | 30,512 |
| R^2 | 0.219 |
| MAE | 1.424 |

### 3.3 Low Contract

| Metric | Value |
|--------|-------|
| N | 48,316 |
| R^2 | 0.206 |
| MAE | 1.403 |

## 4. Cross-Rung Pattern Comparison

> **Caveat:** R0 targets tricks_won; R1.5 targets net_points. Absolute R^2 values
> are not comparable. This section focuses on qualitative patterns only.

### 4.1 Which Contract Has Worst Calibration?

| Rung | Worst-calibrated contract | Evidence |
|------|--------------------------|----------|
| R0 | low | Lowest R^2 (0.206) among R0 contracts |
| R1.5 | pass | R^2=0.042 — near-zero predictive power; n=1,000 (2.1% of training data). Among bid contracts, low is worst (R^2=0.514) |

### 4.2 Heteroscedasticity Pattern

| Rung | Contract | Pattern |
|------|----------|---------|
| R0 | suit | Near-homoscedastic; residuals approximately constant variance across predictions |
| R0 | high | Near-homoscedastic; unimodal tricks_won target produces well-behaved residuals |
| R0 | low | Near-homoscedastic; same pattern as high |
| R1.5 | suit | Heteroscedastic with bimodal residual clusters (make/set regimes) |
| R1.5 | high | Heteroscedastic with bimodal residual clusters (make/set regimes) |
| R1.5 | low | Heteroscedastic with bimodal residual clusters (make/set regimes) |

### 4.3 Residual Distribution Shape

| Rung | Contract | Unimodal/Bimodal | Evidence (GMM BIC delta) |
|------|----------|-----------------|--------------------------|
| R0 | suit | Weakly bimodal | delta_BIC=31 |
| R0 | high | Unimodal | delta_BIC=-183 |
| R0 | low | Unimodal | delta_BIC=-287 |
| R1.5 | suit | Bimodal (strong) | delta_BIC=4,081 |
| R1.5 | high | Bimodal (strong) | delta_BIC=1,469 |
| R1.5 | low | Bimodal (strong) | delta_BIC=1,286 |
| R1.5 | pass | Bimodal (strong) | delta_BIC=185 |

## 5. Training Data Distribution

### 5.1 Contract Balance

| Contract Family | Count | Percentage |
|----------------|-------|------------|
| suit | 305,592 | 65.3% |
| high | 76,398 | 16.3% |
| low | 76,398 | 16.3% |
| pass | 10,000 | 2.1% |
| **Total** | **468,388** | **100%** |

### 5.2 net_points Distribution Shape

| Contract | Mean | Std | Skewness | Kurtosis | Min | Max | Median |
|----------|------|-----|----------|----------|-----|-----|--------|
| suit | -6.89 | 8.00 | 0.53 | -1.15 | -20 | 14 | -11 |
| high | -7.23 | 8.06 | 0.59 | -1.03 | -20 | 14 | -11 |
| low | -7.31 | 8.01 | 0.61 | -0.99 | -20 | 14 | -11 |
| pass | -0.45 | 5.10 | 0.42 | 0.35 | -14 | 14 | 0 |

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
| R1.5 | suit | 4,081 | Strong |
| R1.5 | high | 1,469 | Strong |
| R1.5 | low | 1,286 | Strong |
| R1.5 | pass | 185 | Strong |
| R0 | suit | 31 | Weak |
| R0 | high | -183 | None |
| R0 | low | -287 | None |

### 6.2 Target Variable Bimodality (R1.5 Training Data)

| Contract | delta_BIC | Evidence |
|----------|-----------|----------|
| suit | 249,573 | Strong |
| high | 58,648 | Strong |
| low | 57,949 | Strong |
| pass | 730 | Strong |

### 6.3 Interpretation

The bimodality is structural: net_points has a make/set bifurcation where the
declaring team either wins tricks (positive net_points) or loses the bid
(negative net_points). This creates two distinct modes in the target
distribution for ALL bid contracts, not just suit. The OLS model predicts the
mean of this bimodal distribution, which lies between the two modes —
systematically wrong for both regimes.

This explains the contrast with R0: tricks_won is naturally unimodal
(approximately centered near 5 for any hand), so R0's OLS model tracks a
single-mode distribution effectively. R0's high/low residuals are unimodal
(delta_BIC negative), and even R0's suit residuals are only weakly bimodal
(delta_BIC=31 vs R1.5's 4,081).

The pass contract shows the smallest bimodal evidence among R1.5 contracts
(delta_BIC=185 vs >1,000 for bid contracts), consistent with pass outcomes
being driven by the declaring team's result rather than a direct make/set
decision by the passer.

This motivates the Phase 2 two-stage decomposition (Q14): separating
declare/defend regimes should produce more unimodal within-regime targets.
The OLS model would then predict within each regime rather than averaging
across the bifurcation. Per the governing plan
(`plans/sessions/2026-03-09_r1-5-v2-diagnostic-plan.md`), Phase 2 splits on
the observed declare/defend regime — not make/set — because declare/defend is
directly observable in training data.

## 7. Implications for Phase 2

Based on the diagnostic findings above, the following specific recommendations
inform R1.5-v2 design:

### 7.1 Suit Contract Improvement

Suit has the best R^2 (0.557) but the worst gameplay delta (-0.142). The
problem is NOT prediction quality — it is a decision-layer interaction.

The suit make/set cliff is steeper than high/low because bowers create binary
outcomes: a hand with two bowers either dominates trump (makes) or faces
opposing bowers and gets set. The OLS model's between-mode prediction may cause
more decision errors for suit than high/low because the gap between the two
modes is wider and the transition is sharper.

Phase 2 two-stage decomposition (declare/defend split per the governing plan)
should help suit most: separating E[points|declare] from E[points|defend]
and weighting by P(declare) gives the decision layer regime-specific
predictions rather than a single EV that averages across the bifurcation.
Whether a further make/set sub-split within the declaring regime is needed
is an open question (Q16) to be evaluated during Phase 2 diagnostics.

### 7.2 Model Architecture

All contracts show bimodal residuals — the issue is universal, not
suit-specific. The two-stage decomposition (observed-regime split) is the
highest-priority architectural intervention.

Interaction terms (e.g., bower x trump_length) are lower priority since the
problem is in the target distribution structure, not the feature space. Adding
interactions would slightly improve within-mode predictions but would not
address the fundamental issue of averaging across two distinct outcome regimes.

### 7.3 Training Data

Pass is underrepresented (2.1%) with near-zero R^2 (0.042). However, more pass
training data is unlikely to help — the pass model's low R^2 reflects that pass
net_points depends on the declaring team's outcome, not the passer's hand
features. The passer's hand has almost no predictive power for what another
team will bid and whether they will make.

Suit is overrepresented (65.3%) but has the best fit — more data is not the
bottleneck. The continuation policy bids suit most often, which naturally
produces more suit training rows.

### 7.4 Priority Ranking

1. **Two-stage regime decomposition (Q14)** — addresses universal bimodality,
   expected to help all contracts especially suit. Separating P(declare) from
   E[points|regime] should produce unimodal within-regime targets that OLS can
   fit more accurately.
2. **Ablation H2H evaluation** — Cell B' (tricks_won target on AV architecture)
   bids 10 every hand (1% make rate), proving objective alignment is critical.
   This confirms that the net_points target is essential, not just convenient.
3. **Interaction terms for suit** — lower priority since R^2 is already highest
   among contracts; bimodality, not feature gaps, is the dominant issue. Defer
   to Phase 3 fallback if two-stage decomposition does not close the suit gap.

## Provenance

- R1.5 artifact: `data/artifacts/arc_d/r1_5/action_value_full.json`
- R1.5 dataset: `data/runs/action_value_quick_42/datasets/action_value.parquet`
- R0 artifact: `data/artifacts/arc_d/r0/hybrid_r0_full.json`
- R0 eval data: `data/runs/arc_d_eval_r0_full_42_20260303_201732`
- Seed: 42
- gate_status: N/A (diagnostic report — not a promotion gate artifact; feeds into R1.5-v2 design decisions)
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
