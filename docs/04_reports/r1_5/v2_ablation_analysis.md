# R1.5-v2 Ablation Analysis Report

**Date:** 2026-03-10
**Plan:** `plans/sessions/2026-03-09_r1-5-v2-diagnostic-plan.md` (Phase 1, Step 3)
**Seed:** 42
**Scale:** QUICK (2,500 deals per matchup for H2H; ~10,000 hands per contract for R²)

## 1. Executive Summary

This report documents the R1.5-v2 ablation experiments that decompose the R0→R1.5
improvement (+0.152 net_eppd at FULL scale) into three candidate factors: features,
objective, and data+architecture.

**Key findings:**

1. **Features are irrelevant** — Cell A (39 R0 features vs 52 full features) shows
   R² delta < 0.005 on the same target and data.
2. **Objective alignment is critical** — Cell B' (tricks_won target with AV
   architecture) bids 10 on every hand with 1% make rate. The AV argmax decision
   layer catastrophically degenerates without net_points.
3. **Counterfactual data is noisier for R0-style models** — Option A (R0 sparse
   OLS on counterfactual data) yields suit R²=0.084 vs 0.223 on bidless data.
   The data alone does not explain the improvement.
4. **Phase 2 gate criterion #1 FAIL** — Declare/defend regime split provides
   only +0.01 R² improvement (threshold was >0.05). The defending subset has
   near-zero R² because the focal player's hand can't predict the other team's
   outcome.

## 2. R² Ablation Matrix

### 2.1 Feature × Objective Matrix (counterfactual data)

All cells trained on the same counterfactual dataset
(data/runs/action_value_quick_42_v2/datasets/action_value.parquet, 468,388 rows,
seed=42). R² measured on 20% held-out test split grouped by hand_id.

|                    | R0 features (39) | Full features (52) |
|--------------------|------------------|--------------------|
| **net_points**     | Cell A: suit=0.561, high=0.531, low=0.512 | AV v1: suit=0.565, high=0.533, low=0.514 |
| **tricks_won**     | Cell C: suit=0.169, high=0.149, low=0.118 | Cell B': suit=0.183, high=0.151, low=0.127 |

**Feature effect (same target, same data):**
- net_points: AV v1 - Cell A = +0.004 / +0.002 / +0.002 (negligible)
- tricks_won: Cell B' - Cell C = +0.014 / +0.002 / +0.009 (negligible)

**Conclusion:** The 13 extra state features (partner context, positional, contract
indicators) contribute virtually nothing to prediction quality.

### 2.2 Cross-Target Caveat

The R² difference between net_points (~0.55) and tricks_won (~0.17) rows does NOT
mean "net_points is a better objective." R² is measured against different targets
with different variance structures. Higher net_points R² means net_points is more
*predictable* from hand features (because it encodes the bid decision structure),
not that models trained on it make better *decisions*. Only gameplay evaluation
(Section 3) can test objective alignment.

### 2.3 Option A: R0-Style OLS on Counterfactual Data

Collapses counterfactual data to 1 row per (hand, contract) by averaging
tricks_won across bid levels. Trains R0's 3 sparse features per contract
(CONTRACT_FEATURES: suit=[bowers, trump_count, offsuit_aces], high=[offsuit_aces,
quick_tricks], low=[offsuit_tens_count, quick_tricks]).

| Model | Architecture | Data | Target | Suit R² | High R² | Low R² |
|-------|-------------|------|--------|---------|---------|--------|
| R0-CF (Option A) | R0 sparse (3 feat) | Counterfactual | tricks_won | 0.084 | 0.164 | 0.164 |
| R0 baseline | R0 sparse (3 feat) | Bidless | tricks_won | 0.223 | 0.219 | 0.206 |

**Delta (counterfactual - bidless):** suit=-0.139, high=-0.055, low=-0.042

Counterfactual data is *worse* for R0-style predictions than bidless data. This is
because counterfactual rollouts include off-policy actions (forced bids on hands
that wouldn't naturally bid that contract), creating noisier tricks_won targets.
The data dimension is not an improvement source — it's a noise source that the
net_points objective overcomes.

## 3. Gameplay Decomposition (H2H Battery)

### 3.1 Experimental Design

3-bidder QUICK H2H battery with paired deals (seed=42, n=2,500 per matchup):
- **AV v1:** ActionValueBidder, net_points target, full features (52+2)
- **Cell B':** ActionValueBidder, tricks_won target, full features (52+2)
- **R0 full:** HybridOLSaBidder, tricks_won target, sparse features, bid_level_search

9 matchups: 3 self-play + 6 cross-matchups (both seat rotations).

Run directory: data/runs/r1_5_v2_ablation_h2h_42_20260309_202431/

### 3.2 Results

| Matchup | Rotation-Averaged Net eppd | Interpretation |
|---------|---------------------------|----------------|
| AV v1 vs Cell B' | **+13.658** | Objective effect (massive) |
| Cell B' vs R0 | **-13.658** | Cell B' catastrophically worse than R0 |
| AV v1 vs R0 | **+0.165** | Full R1.5 improvement (consistent with FULL: +0.152) |

Self-play net eppd (should be ~0): AV v1=+0.003, Cell B'=+0.062, R0=+0.019.

### 3.3 Cell B' Behavioral Catastrophe

Cell B' (tricks_won target, AV argmax architecture) exhibits pathological behavior:

| Metric | AV v1 (net_points) | Cell B' (tricks_won) | R0 (HybridOLSa) |
|--------|-------------------|---------------------|-----------------|
| Bid level | Always 4 | **Always 10** | 2-4 (distributed) |
| Make rate | 94.6% | **1.0%** | 96.6% |
| Contract mix | suit 46%, low 37%, high 18% | suit 72%, low 19%, high 8% | — |

**Mechanism:** The tricks_won target with action features (bid_n, bid_n_sq) creates
a perverse incentive. In training data, higher bids correlate with more tricks won
(strong hands bid high AND win more tricks). The quadratic bid_n_sq term makes
bid_n=10 have the highest predicted tricks_won for any hand. Argmax always picks
the maximum bid, resulting in 99% set rate and catastrophic -10 penalty per hand.

**Why R0 doesn't have this problem:** R0 also predicts tricks_won, but its
decision layer (Gaussian EV + sigma + threshold) includes hand-coded logic that
prevents overbidding. The sigma parameter models uncertainty, and the
bid_level_search evaluates each bid level's expected utility accounting for the
set penalty. The AV architecture's argmax has no such safety mechanism — it
requires the training objective to encode the set penalty directly.

### 3.4 Decomposition Interpretation

The linear decomposition (objective + data_arch = total) breaks down because
Cell B' is so catastrophic that the deltas cancel out. The correct interpretation
is non-linear:

- **The AV architecture requires net_points to function.** Without it, argmax
  degenerates to maximum bid. This is not "objective matters a little" — it's
  "without the right objective, the architecture is fundamentally broken."
- **R0's architecture compensates for the wrong objective.** The Gaussian EV
  decision layer includes hand-coded bid evaluation logic that makes tricks_won
  viable despite being the wrong target. This is the "decision layer bottleneck"
  identified in R1 closeout.
- **The +0.165 total delta** comes from the entire package working together:
  net_points objective + argmax architecture + counterfactual action enumeration.
  No single component can be cleanly attributed because they are synergistic.

## 4. Declare/Defend Conditional R² Analysis

### 4.1 Phase 2 Go/No-Go Gate: Criterion #1

Split the counterfactual training data by `focal_declared` (True = focal player's
team won the auction). Fit separate OLS models on each regime. Compute composite
R² using regime-appropriate models.

| Contract | Pooled R² | Declare R² | Defend R² | Composite R² | Delta | Gate |
|----------|-----------|------------|-----------|-------------|-------|------|
| suit | 0.568 | 0.595 | 0.003 | 0.580 | +0.012 | FAIL |
| high | 0.534 | 0.549 | 0.005 | 0.543 | +0.010 | FAIL |
| low | 0.534 | 0.552 | 0.003 | 0.545 | +0.012 | FAIL |

**Gate threshold:** >0.05 R² improvement. **Result: FAIL** for all contracts.

### 4.2 Why the Gate Failed

1. **87% declaring:** The pooled model is already predominantly a declaring model.
   Splitting only improves the 87% slightly and gains nothing from the 13%.
2. **Defend R² ≈ 0:** When the focal player is defending, their hand features
   cannot predict net_points (which depends on the declaring team's bid/make/set).
   A regime-specific defend model can't fix this — the features simply lack the
   signal.
3. **Wrong split level:** The bimodality in net_points comes from make/set within
   the declaring regime, not from declare/defend. The declaring subset
   (R²=0.59) is still bimodal internally — the regime split doesn't address the
   source of the bimodality.

### 4.3 Implications

The declare/defend two-stage model (Phase 2 Step 4 in the plan) is unlikely to
improve gameplay. The productive decomposition would be:
- **Make/set split within declaring regime**: model P(make|hand,bid) separately
  from E[points|make] and E[points|set]
- **Interaction terms** (Phase 3): bower × trump_length, trump_count² etc.
  to capture the suit non-linearity directly

Gate criteria #2 (conditional residual pattern) and #3 (small pilot) remain
untested but are less likely to pass given the fundamental limitation that defend
R² ≈ 0 makes the defend model worthless.

## 5. Partner Feature Ablation (Step 7b)

### 5.1 Experiment Design

Trained ActionValueBidder with partner features (`partner_bid_level`,
`partner_passed`, `partner_suit_match`) zeroed out at training time. The model
artifact retains full 54-element feature_names (loads normally), but partner
coefficients are exactly 0.0. This isolates partner context contribution
without confounding architecture or objective changes.

### 5.2 R² Comparison

| Contract | Full (AV v1) | No-Partner | Delta |
|----------|-------------|------------|-------|
| suit | 0.5653 | 0.5619 | -0.0034 |
| high | 0.5327 | 0.5331 | +0.0004 |
| low | 0.5139 | 0.5117 | -0.0022 |
| pass | 0.0463 | 0.0054 | **-0.0409** |

R² is nearly identical for suit/high/low (delta < 0.005). But the **pass model
collapses** from 0.046 to 0.005 — partner context is the dominant signal for
pass decisions.

### 5.3 H2H Gameplay Results

| Comparison | Delta (pts/deal) | Interpretation |
|-----------|-----------------|----------------|
| AV v1 vs R0 | **+0.224** | Full AV improvement |
| no-partner vs R0 | **-0.492** | AV without partner features loses to R0 |
| no-partner vs AV v1 | **-0.752** | Partner features worth ~0.75 pts/deal |

Run: data/runs/r1_5_v2_partner_ablation_h2h_42_20260310_130936 (9 matchups,
seed=42, n=2,500).

### 5.4 Key Finding

**Partner features are the single most valuable component of AV v1.** Despite
R² showing near-zero contribution for suit/high/low prediction, partner
context fundamentally changes *which actions the bidder selects* — particularly
pass decisions. Without partner context, the bidder's pass model degrades to
near-random, and gameplay drops below R0.

This contradicts the Phase 1 conclusion that "features are irrelevant." R²
measures prediction accuracy for a *given action*, but partner features affect
*action selection* — knowing your partner bid changes which contracts you
consider, not how accurately you predict their outcome.

**Implication for Phase 3:** Interaction terms (Step 8) should use the full
feature set including partner features. The partner features are essential
and should not be removed.

## 6. Updated Effect Decomposition

| Factor | R² Evidence | Gameplay Evidence | Conclusion |
|--------|------------|-------------------|------------|
| Features (39→52 non-partner) | Delta < 0.005 | Not tested (Cell A can't load) | **Irrelevant for prediction** |
| Partner features (3) | Delta < 0.005 for suit/high/low, -0.041 for pass | -0.492 vs R0 without, +0.224 with | **Critical for action selection** |
| Objective (tricks→net_pts) | R² not comparable across targets | Cell B' bids 10/hand, -13.7 net_eppd vs AV v1 | **Critical — architecture requires it** |
| Data (bidless→counterfactual) | Counterfactual *worse* for R0 (suit -0.139 R²) | Confounded with architecture | **Not an independent improvement source** |
| Architecture (HybridOLSa→AV) | N/A | Confounded with data and objective | **Synergistic with objective** |
| Declare/defend split | +0.01 R² (gate FAIL) | Not tested | **Insufficient** |
| Interaction terms (3) | Delta < 0.001 for all contracts | +0.002 vs AV v1 (noise) | **No effect — Q5 answered** |

## 7. Interaction Term Ablation (Step 8)

### 7.1 Experiment Design

Added 3 interaction features computed from existing hand features:
- `bowers_x_trump_count` — bowers × trump_count
- `trump_count_sq` — trump_count²
- `bowers_sq` — bowers²

These target bower-specific non-linearities in the suit model. Features are
computed in the training pipeline (`_build_feature_matrix()`) and at inference
time (`compute_interaction_features()`), without modifying `STATE_FEATURE_NAMES`
or requiring dataset regeneration.

### 7.2 R² Comparison

| Contract | Full (AV v1) | Interaction | Delta |
|----------|-------------|-------------|-------|
| suit | 0.5653 | 0.5652 | -0.0001 |
| high | 0.5327 | 0.5328 | +0.0001 |
| low | 0.5139 | 0.5143 | +0.0004 |
| pass | 0.0463 | 0.0456 | -0.0007 |

All deltas < 0.001. The interaction terms provide zero additional predictive
power. The `lstsq` fallback during training indicates the interaction features
are near-collinear with existing features.

### 7.3 H2H Gameplay Results

| Comparison | Delta (pts/deal) | Interpretation |
|-----------|-----------------|----------------|
| interaction vs AV v1 | **+0.002** | No difference (noise) |
| interaction vs R0 | **+0.165** | Same as AV v1 vs R0 |
| AV v1 vs R0 | **+0.165** | Baseline reference |

Run: data/runs/r1_5_v2_interaction_h2h_42_20260310_160346 (9 matchups,
seed=42, n=2,500).

### 7.4 Key Finding: Q5 Answered

**OLS linearity is NOT the problem.** The interaction terms provide zero
benefit in both offline R² and gameplay. The suit regression (-0.142 net_eppd)
is not caused by missing non-linear feature interactions.

Combined with the Phase 2 gate failure (declare/defend split +0.01 R²), this
confirms the structural diagnosis: the bimodal net_points distribution
(make vs set) creates a target that OLS cannot serve well regardless of feature
engineering. The OLS prediction falls between the two modes (make ~+bid,
set ~-bid), producing suboptimal expected-value estimates for the argmax
decision layer.

**Implication:** Further feature engineering on the current OLS + argmax
architecture is unlikely to close the suit gap. Progress requires either:
1. A two-stage model (P(make) × E[points|make] + P(set) × E[points|set])
2. A fundamentally different model class (logistic regression, tree-based)
3. Direct policy optimization bypassing the prediction → decision pipeline

## 8. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — diagnostic ablation, no formal gate |
| Plan | `plans/sessions/2026-03-09_r1-5-v2-diagnostic-plan.md` Phase 1 Step 3 |
| Cell A artifact | data/runs/cell_a_r0_features_42/action_value_r0_features.json |
| Cell B' artifact | data/runs/action_value_quick_42_v2/action_value_full.json |
| Cell C artifact | data/runs/cell_c_r0_tricks_42/ (gate X2 failed on pass, ran with --skip-validation) |
| Dataset v2 | data/runs/action_value_quick_42_v2/datasets/action_value.parquet (468,388 rows) |
| H2H run (ablation) | data/runs/r1_5_v2_ablation_h2h_42_20260309_202431/ (9 matchups, seed=42, n=2500) |
| No-partner artifact | data/runs/av_no_partner_42/action_value_no-partner_features.json |
| H2H run (partner) | data/runs/r1_5_v2_partner_ablation_h2h_42_20260310_130936/ (9 matchups, seed=42, n=2500) |
| Interaction artifact | data/runs/av_interaction_42/action_value_interaction_features.json |
| H2H run (interaction) | data/runs/r1_5_v2_interaction_h2h_42_20260310_160346/ (9 matchups, seed=42, n=2500) |
| Diagnostics | data/reports/arc_d/r1_5_v2/diagnostics/ (18 charts + diagnostic_summary.json) |
| analysis_base_sha | 4bfdd77 |

### Reproduction Commands

```bash
# Cell A (R0 features, net_points target)
uv run python scripts/internal/train_action_value.py \
  --seed 42 --feature-set r0 --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/cell_a_r0_features_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

# Cell B' (full features, tricks_won target)
uv run python scripts/internal/train_action_value.py \
  --seed 42 --feature-set full --target tricks_won \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/action_value_quick_42_v2 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

# H2H battery (ablation) — config generated locally, not committed
# See ablation_h2h_config.yaml structure: 3 bidders (AV v1, Cell B', R0),
# 9 matchups (3 self-play + 6 cross), paired deals, n=2500
uv run python experiments/run_experiment.py --seed 42 \
  --config data/runs/ablation_h2h_quick_42/ablation_h2h_config.yaml

# No-partner model (--skip-validation required: pass R²=0.005 < gate threshold)
uv run python scripts/internal/train_action_value.py \
  --seed 42 --feature-set no-partner --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_no_partner_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --skip-validation

# H2H battery (partner ablation) — config generated locally, not committed
# See partner_ablation_h2h_config.yaml structure: 3 bidders (AV v1, no-partner, R0),
# 9 matchups (3 self-play + 6 cross), paired deals, n=2500
uv run python experiments/run_experiment.py --seed 42 \
  --config data/runs/partner_ablation_h2h_quick_42/partner_ablation_h2h_config.yaml

# Interaction model
uv run python scripts/internal/train_action_value.py \
  --seed 42 --feature-set interaction --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_interaction_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

# H2H battery (interaction) — config generated locally, not committed
# See interaction_h2h_config.yaml structure: 3 bidders (AV v1, interaction, R0),
# 9 matchups (3 self-play + 6 cross), paired deals, n=2500
uv run python experiments/run_experiment.py --seed 42 \
  --config data/runs/interaction_h2h_quick_42/interaction_h2h_config.yaml
```
