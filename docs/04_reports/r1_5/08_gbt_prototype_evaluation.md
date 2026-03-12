# R1.5.3 Track B: GBT Prototype Evaluation

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Date:** 2026-03-11
**Purpose:** Evaluate gradient boosted tree (GBT) action-value bidder against OLS AV v1 and R0 Hybrid baselines

## Executive Summary

1. **What is this?** An initial evaluation of a GBT-based action-value bidder as an
   alternative to the OLS linear model used in R1.5 v1.

2. **What did we do?** Trained 4 GBT models (suit/high/low/pass) on the same
   counterfactual action-value dataset used for OLS AV v1 (2,500 deals, seed=42).
   Ran a 3-bidder QUICK H2H battery (9 matchups × 2,500 deals, paired deals).

3. **What did we find?** GBT dominates both baselines by ~+1.1 net_eppd, winning
   all three contract types. The suit regression that blocked OLS AV v1 promotion
   is fully resolved. GBT achieves this via selective bidding: 31.9% pass rate vs
   OLS's 0%, with higher average bids when it does bid (5.44 vs 4.00).

   | Metric | GBT AV | OLS AV v1 | Hybrid R0 |
   |--------|--------|-----------|-----------|
   | net_eppd vs Hybrid R0 | +1.067 | +0.165 | — |
   | net_eppd vs OLS AV v1 | +1.112 | — | -0.165 |
   | Self-play eppd | 4.29 | 4.82 | 4.88 |
   | Self-play pass rate | 31.9% | 0.0% | 5.7% |
   | Self-play make rate | 87.1% | 94.6% | 96.6% |
   | Self-play CVaR_5 | -6.63 | -1.80 | -0.71 |

4. **What are the caveats?**
   - QUICK sample size only (2,500 deals) — per-contract CIs are wide, some
     contract facets have n < 2,000.
   - GBT trained with default sklearn hyperparameters (no tuning).
   - Pass model R² is very low (0.030) — may not reliably predict pass EV.
   - GBT sacrifices interpretability: feature coefficients are not available,
     only feature importances.
   - Higher tail risk: CVaR_5 of -6.63 vs -1.80 (OLS) and -0.71 (Hybrid).

5. **What's the decision?** **PROTOTYPE VALIDATED** — GBT resolves the structural
   suit regression that blocked OLS AV v1. Recommend proceeding to FULL battery
   (50k deals) and hyperparameter tuning. The interpretability tradeoff and tail
   risk require further investigation.

## 1. Motivation

R1.5 v1 concluded with the ActionValueBidder ADVANCED but not promoted. The core
blocker was a persistent suit-contract regression: OLS AV v1 scored -0.142 net_eppd
vs R0 Hybrid in suit contracts, despite gains of +0.430 (high) and +0.495 (low).

The R1.5-v2 ablation series ([v2_ablation_analysis.md](v2_ablation_analysis.md))
identified the cause: the bimodal distribution of suit net_points (declare vs
defend outcomes have very different score distributions) is poorly captured by
OLS's linear assumption. Interaction terms provided no relief (R² delta < 0.001,
H2H delta +0.002, PR #603).

This motivates exploring non-linear model architectures that can capture the
suit target distribution without the linearity constraint.

### Questions Addressed

- **Q1:** Does a tree-based model improve offline fit (R²) vs OLS?
- **Q2:** Does improved offline fit translate to gameplay improvement?
- **Q3:** Does GBT resolve the suit regression specifically?
- **Q4:** What behavioral differences emerge from a non-linear decision surface?

## 2. Methodology

### 2.1 Training

GBT models were trained using `sklearn.GradientBoostingRegressor` with default
hyperparameters on the same counterfactual dataset used for OLS AV v1:

- **Dataset:** 2,500 deals × 4 contracts × variable actions per state
- **Target:** `net_points` (same as OLS AV v1)
- **Features:** 52-column state + action encoding (same as OLS AV v1)
- **Split:** GroupKFold by `hand_id` (same as OLS AV v1 pipeline)
- **Training seed:** 42

Four separate models were trained (suit, high, low, pass), matching the OLS
architecture.

### 2.2 H2H Battery

A 3-bidder QUICK H2H battery was run with the following roster:

| Bidder | Class | Artifact |
|--------|-------|----------|
| gbt_av | `GBTActionValueBidder` | data/runs/av_gbt_42/action_value_gbt.json |
| ols_av | `ActionValueBidder` | data/artifacts/arc_d/r1_5/action_value_full.json |
| hybrid_olsa_full | `HybridOLSaBidder` | data/artifacts/arc_d/r0/hybrid_r0_full.json |

**Parameters:** 2,500 deals per matchup, seed=42, paired deals, 9 matchups
(3 self-play + 6 cross-play), `GluttonStrategy` for all play policies.

**Config:** data/runs/av_gbt_42/h2h_gbt_vs_ols_config.yaml

**Statistical method:** Bootstrap CIs with 10,000 resamples, seed=42.
Pairwise deltas are symmetrized across seat assignment (average of A-vs-B
and negated B-vs-A).

### 2.3 Correction Note

An earlier H2H run (PR #614 original analysis) used a stale OLS artifact
(data/runs/action_value_quick_42_v2/action_value_full.json, R²=0.183) instead of
the correct Step 6 baseline. That artifact had an inverted bid_n coefficient
(+0.082 instead of -0.058), causing degenerate bidding at level 10. The corrected
run uses the canonical R1.5 artifact confirmed against the committed Step 6 config
(experiments/configs/r1_5_h2h_battery_quick.yaml).

## 3. Results

### 3.1 Offline Model Fit

| Contract | GBT R² | OLS R² | Delta | GBT MAE | OLS MAE |
|----------|--------|--------|-------|---------|---------|
| Suit     | 0.594  | 0.565  | +0.029 | 3.627  | 4.072  |
| High     | 0.550  | 0.533  | +0.017 | 3.849  | 4.169  |
| Low      | 0.538  | 0.514  | +0.024 | 3.873  | 4.230  |
| Pass     | 0.030  | 0.046  | -0.016 | 3.318  | 3.236  |

GBT achieves modestly higher R² for all bid contracts (+0.017 to +0.029) and
lower MAE. The pass model is weak for both architectures (R² < 0.05), reflecting
the inherent difficulty of predicting defender outcomes from hand features alone.

GBT's pass R² (0.030) is lower than OLS's (0.046), suggesting OLS's linear
structure captures the limited pass signal slightly better, or that GBT overfits
on the small pass training set (n=8,000).

### 3.2 Pairwise H2H Deltas (Symmetrized)

| Comparison | Pooled | 95% CI | Suit | High | Low |
|------------|--------|--------|------|------|-----|
| GBT vs OLS AV | **+1.112** | [+0.986, +1.244] | +1.190 [+1.011, +1.373] | +1.112 [+0.702, +1.518] | +0.931 [+0.605, +1.260] |
| GBT vs Hybrid R0 | **+1.067** | [+0.951, +1.188] | +1.110 [+0.946, +1.276] | +1.467 [+1.030, +1.900] | +0.736 [+0.396, +1.079] |
| OLS AV vs Hybrid R0 | **+0.165** | [+0.080, +0.249] | -0.136 [-0.303, +0.032] | +0.454 [+0.141, +0.774] | +0.519 [+0.299, +0.739] |

All CIs exclude zero for pooled comparisons. GBT dominates both baselines across
all three contract types — a result qualitatively different from OLS AV v1, which
showed suit regression (-0.142) against Hybrid R0.

The OLS vs Hybrid comparison (+0.165) is consistent with the Step 6 QUICK result
(+0.165) and FULL result (+0.152), serving as an internal consistency check.

### 3.3 Self-Play Profiles

| Metric | GBT AV | OLS AV v1 | Hybrid R0 |
|--------|--------|-----------|-----------|
| Avg winning bid | 5.44 | 4.00 | 3.77 |
| Make rate | 87.1% | 94.6% | 96.6% |
| Pass rate (actions) | 31.9% | 0.0% | 5.7% |
| Redeals | 0 | 0 | 0 |
| eppd (team mean) | 4.29 | 4.82 | 4.88 |
| Score std | 3.60 | 2.41 | 2.24 |
| Score min | -9 | -4 | -4 |
| Score max | 10 | 10 | 10 |
| CVaR_5 | -6.63 | -1.80 | -0.71 |
| % Suit | 61.2% | 45.5% | 61.2% |
| % High | 12.6% | 17.8% | 15.0% |
| % Low | 26.2% | 36.7% | 23.8% |

**Bid level distribution (GBT self-play):**

| Level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|-------|---|---|---|---|---|---|---|---|---|----|
| Count | 1094 | 912 | 1029 | 1137 | 1003 | 1064 | 511 | 59 | 3 | 1 |

**OLS self-play:** Every seat bids mechanically — levels escalate 1→2→3→4 with
100% regularity. This is the known bid_n pathology: OLS's negative bid_n
coefficient (-0.058 for suit) produces monotonically decreasing EV predictions,
so each seat bids the minimum legal level and never passes.

**Hybrid R0 self-play:** Uses Gaussian EV wrapper with bid-level search. Bids at
levels 1–4 with 5.7% pass rate, reflecting the sigma-based uncertainty.

**GBT self-play:** Uses the full bid spectrum (1–10) with a broad peak at levels
1–6. The 31.9% pass rate shows GBT learned that some hands should not bid.
This selective bidding is the key behavioral innovation.

### 3.4 Cross-Play Auction Dynamics

| Matchup | GBT Auction Win% | Avg Bid | Make Rate | GBT Pass% | Opponent Pass% |
|---------|-------------------|---------|-----------|-----------|----------------|
| GBT vs OLS | 61.7% | 4.82 | 89.8% | 19.2% | 22.0% |
| GBT vs Hybrid | 68.1% | 4.74 | 93.4% | 19.2% | 27.0% |

| Matchup | OLS Auction Win% | Avg Bid | Make Rate | OLS Pass% | Hybrid Pass% |
|---------|-------------------|---------|-----------|-----------|--------------|
| OLS vs Hybrid | 56.3% | 3.88 | 95.7% | 0.0% | 5.8% |

GBT wins the majority of auctions against both opponents. Against OLS, GBT outbids
at 61.7% rate; against Hybrid, 68.1%. Despite winning more auctions at higher bid
levels, GBT maintains 89.8–93.4% make rates — indicating it bids aggressively
only when hand strength justifies it.

OLS never passes in cross-play (0.0%), confirming the bid_n pathology persists
regardless of opponent.

### 3.5 Per-Matchup Detail (Raw, Non-Symmetrized)

| Matchup | Team0 | Team1 | net_eppd (T0) | 95% CI |
|---------|-------|-------|---------------|--------|
| gbt_av_self_play | GBT | GBT | +0.029 | [-0.206, +0.265] |
| ols_av_self_play | OLS | OLS | +0.003 | [-0.172, +0.180] |
| hybrid_self_play | Hybrid | Hybrid | +0.019 | [-0.149, +0.188] |
| gbt_av_vs_ols_av | GBT | OLS | +1.162 | [+0.952, +1.371] |
| ols_av_vs_gbt_av | OLS | GBT | -1.062 | [-1.271, -0.854] |
| gbt_av_vs_hybrid | GBT | Hybrid | +1.073 | [+0.878, +1.269] |
| hybrid_vs_gbt_av | Hybrid | GBT | -1.062 | [-1.260, -0.861] |
| ols_av_vs_hybrid | OLS | Hybrid | +0.176 | [+0.008, +0.348] |
| hybrid_vs_ols_av | Hybrid | OLS | -0.154 | [-0.324, +0.024] |

Self-play controls show near-zero net_eppd (0.003–0.029), confirming seat balance.

## 4. Interpretation

### 4.1 Why GBT Resolves Suit Regression

The R1.5-v2 ablation ([v2_ablation_analysis.md](v2_ablation_analysis.md))
identified OLS's structural limitation: suit net_points has a bimodal target
distribution (declare outcomes cluster around ±bid, defend outcomes cluster
around ±opponent's bid). OLS fits a single linear surface through both modes,
producing a compromised prediction that's accurate for neither.

GBT's tree structure naturally partitions the feature space into regions
corresponding to different outcome modes. The tree can learn separate prediction
rules for "strong hand, should declare" vs "weak hand, will defend" without
requiring the mapping to be linear. This is visible in GBT's feature importances:
bid_n and bid_n_sq account for ~85% of importance in suit/high/low models,
showing the tree learned to partition primarily along the action dimension.

### 4.2 Selective Bidding as Emergent Behavior

GBT's 31.9% pass rate is the most significant behavioral finding. Neither OLS
(0%) nor Hybrid (5.7%) passes at this rate. GBT appears to have learned the
value of information: passing when your hand predicts poor outcomes for all
available actions is better than bidding defensively at minimum level.

This resolves a long-standing concern from the R1.5 v1 analysis: OLS AV v1's 0%
pass rate (and near-0% in H2H) meant it always declared, even when defending
would have been more profitable. GBT's pass model, despite its low R² (0.030),
produces pass-EV predictions that are competitive enough to trigger passes in
31.9% of auction actions.

### 4.3 Variance-Return Tradeoff

GBT's higher variance (score std 3.60 vs 2.24–2.41) and worse tail risk
(CVaR_5 -6.63 vs -0.71 to -1.80) reflect its aggressive bidding strategy.
The minimum score of -9 (vs -4 for both baselines) shows GBT occasionally bids
at 9 and gets set. This is a rational tradeoff in expected-value terms — the
+1.1 net_eppd advantage more than compensates — but may be undesirable in
settings where tail risk matters.

### 4.4 Offline Fit vs Gameplay Gap

The offline R² improvement is modest (+0.017 to +0.029), yet the gameplay
improvement is massive (+1.1 net_eppd). This echoes the R1.5 v1 finding where
R² improvements of similar magnitude produced only +0.152 net_eppd. The
difference is that GBT's non-linear decision surface enables qualitatively
different bidding behavior (selective passing), which OLS cannot express
regardless of R².

This suggests that **decision-surface shape matters more than prediction
accuracy** for auction bidding. A model that's slightly more accurate but can
represent "don't bid" decisions produces disproportionate gameplay gains.

### 4.5 Limitations and Caveats

- **Sample size:** 2,500 deals is QUICK-tier. Per-contract facets for high
  contracts have as few as 300 deals, well below the 2,000-deal minimum for
  reliable bias detection. FULL (50k) battery is required before promotion
  decisions.
- **No hyperparameter tuning:** Default sklearn parameters (`n_estimators=100`,
  `max_depth=3`, `learning_rate=0.1`). Tuned models may perform differently.
- **Single seed:** Only seed=42 was tested. Multi-seed validation is needed.
- **Interpretability loss:** OLS coefficients directly reveal how features
  influence predictions. GBT feature importances show which features matter
  but not how they combine. This complicates debugging and understanding failure
  modes.
- **Pass model weakness:** R² of 0.030 means the pass model explains ~3% of
  variance. The pass decision may be largely driven by relative comparisons
  (pass EV vs best bid EV) rather than accurate absolute predictions.

## 5. Impact & Decisions

### 5.1 Answers to Motivating Questions

| Question | Answer | Evidence |
|----------|--------|----------|
| Q1: Better offline fit? | **Yes**, modestly | R² +0.017 to +0.029 for bid contracts |
| Q2: Better gameplay? | **Yes**, substantially | +1.112 net_eppd vs OLS, +1.067 vs Hybrid |
| Q3: Suit regression resolved? | **Yes** | Suit delta +1.190 vs OLS, +1.110 vs Hybrid |
| Q4: Behavioral differences? | **Yes**, selective bidding | 31.9% pass rate, full bid spectrum |

### 5.2 Recommended Next Steps

1. **FULL H2H battery** (50k deals) — Required before any promotion decision.
   The QUICK results are promising but below rigor thresholds.
2. **Hyperparameter tuning** — Grid search over `n_estimators`, `max_depth`,
   `learning_rate`, `min_samples_leaf`. The default-parameter prototype may
   understate or overstate GBT's potential.
3. **Multi-seed validation** — Run with seeds 42, 123, 456 to verify stability.
4. **Interpretability investigation** — Explore SHAP values or partial dependence
   plots to understand GBT's decision surface. Consider interpretable
   alternatives (EBM, bucketed models) if interpretability is a priority.
5. **Tail risk analysis** — Deeper investigation of the CVaR_5 gap. Is the
   higher variance acceptable, or does it indicate systematic overbidding on
   certain hand types?

### 5.3 Implications for R1.5.3

This prototype validates the hypothesis that non-linear models can resolve
the suit regression. The decision-layer problem identified in R1.5 v1
(OLS × bimodal target) is confirmed as architectural, not data-driven.

The GBT prototype does not by itself warrant promotion over R0 Hybrid — that
requires a FULL battery with tuned hyperparameters. But it establishes that
the action-value framework with a non-linear model has strong potential.

## 6. Arc Context

### 6.1 Progression

| Rung | Model | Result | Key Finding |
|------|-------|--------|-------------|
| R0 | Hybrid OLSa | PROMOTED | Gaussian EV + bid-level search baseline |
| R1 | Hybrid OLSa + partner features | HALTED | Decision-layer bottleneck (H10) |
| R1.5 v1 | OLS AV (action-value) | ADVANCED | +0.152 pooled, suit regression -0.142 |
| R1.5 v2 | OLS AV + ablations | CONCLUDED | Suit regression is structural (OLS × bimodal) |
| **R1.5.3** | **GBT AV (prototype)** | **VALIDATED** | **+1.1 pooled, suit resolved, 31.9% pass** |

### 6.2 What This Changes

The R1.5 v2 conclusion was that OLS linearity is the fundamental bottleneck.
This prototype confirms that conclusion and demonstrates a concrete path forward.
The next rung should focus on model architecture (GBT tuning, or alternative
non-linear models) rather than feature engineering or objective changes.

### Companion Reports

| Report | Focus |
|--------|-------|
| [06_ablation.md](06_ablation.md) | R1.5 v1 attribution — suit regression confirmed |
| [v2_ablation_analysis.md](v2_ablation_analysis.md) | v2 diagnostics — OLS×bimodal identified |
| [07_promotion_decision.md](07_promotion_decision.md) | R1.5 v1 promotion — ADVANCED |
| [05_h2h_battery_full.md](05_h2h_battery_full.md) | FULL battery — +0.152 net_eppd |

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | PROTOTYPE VALIDATED |
| GBT artifact | data/runs/av_gbt_42/action_value_gbt.json |
| OLS AV artifact | data/artifacts/arc_d/r1_5/action_value_full.json |
| Hybrid R0 artifact | data/artifacts/arc_d/r0/hybrid_r0_full.json |
| H2H config | data/runs/av_gbt_42/h2h_gbt_vs_ols_config.yaml |
| H2H run dir | data/runs/arc_d_gbt_vs_ols_h2h_42_20260311_214915 |
| Git SHA (GBT code) | 5a5945d (PR #614) |
| Seed | 42 |
| n_deals per matchup | 2,500 |
| Total hands | 22,500 (9 matchups) |

## 8. Reproduction

### Training

```bash
uv run python scripts/internal/train_action_value_gbt.py \
  --dataset data/runs/action_value_dataset_42/action_value_dataset.parquet \
  --output-dir data/runs/av_gbt_42 \
  --seed 42
```

### H2H Battery

```bash
uv run python experiments/run_experiment.py \
  --config data/runs/av_gbt_42/h2h_gbt_vs_ols_config.yaml \
  --seed 42
```

### Dependencies

- GBT training requires the counterfactual dataset from R1.5 Step 1
  (data/runs/action_value_dataset_42/)
- H2H requires all three artifacts listed in the Provenance table
- `GBTActionValueBidder` class (PR #614) must be available in
  `src/bid_euchre/strategy/bidding.py`
