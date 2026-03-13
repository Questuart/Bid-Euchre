# R1.5 Arc Retrospective — From Objective Alignment to Model Architecture

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 through R1.5.3 Phase 1A
**Date:** 2026-03-12
**Purpose:** Comprehensive research retrospective covering the complete action-value
bidder arc, from R1.5 conception through R1.5.3 Phase 1A model×label decomposition
**PRs covered:** #555–#626 (2026-03-06 through 2026-03-12)
**Predecessor:** [post_r1_retro.md](post_r1_retro.md) (covers R0v2 through R1.5.2)

## Executive Summary

1. **What is this?** A retrospective covering the entire R1.5 research arc: the
   action-value bidder (AV) pipeline that replaced R0/R1's tricks-based prediction
   with direct `net_points` optimization, followed by systematic diagnostics and
   alternative model architectures.

2. **What did we do?** Built the AV pipeline (counterfactual datasets, 4 OLS
   models, argmax decision), ran FULL H2H evaluation (50k deals), executed a
   6-experiment diagnostic campaign (feature ablation, objective ablation,
   regime split, partner ablation, interaction terms), built a GBT prototype,
   tested multi-rollout label smoothing, and ran a 2×2 model×label factorial
   experiment. 21 reports across ~70 PRs.

3. **What did we find?**

   | Finding | Evidence | Impact |
   |---------|----------|--------|
   | Objective alignment reverses R1 regression | +0.152 net_eppd (vs R1's -0.348) | Core R1 diagnosis validated |
   | Suit regression is structural (OLS × bimodal) | -0.142 suit delta; feature engineering exhausted | OLS cannot solve this |
   | Partner features critical for action selection | H2H: -0.492 without vs +0.224 with | Most valuable AV component |
   | GBT resolves suit completely | +1.1 net_eppd vs OLS; suit +1.11 vs R0 | Architecture is the answer |
   | Model capacity >> label quality (H15) | B vs C: -1.206 net_eppd; 35× effect ratio | Multi-rollout can't rescue OLS |
   | R² ≠ gameplay quality | +0.14 R² gain → zero gameplay gain (OLS) | Prediction accuracy ≠ decision quality |

4. **What are the caveats?** GBT results are QUICK-scale only (2,500 deals).
   Higher tail risk (CVaR₅ -6.63 vs R0's -0.71). Default hyperparameters (no
   tuning). Single seed throughout. Interpretability loss vs OLS.

5. **What's the decision?** **GBT action-value bidder advances to FULL
   validation** (Phase 2, 50k deals). R0 hybrid_olsa_full remains incumbent.
   OLS is retired as a viable AV architecture — model capacity is the
   binding constraint. Cell D (GBT, N=20) is the primary candidate; Cell C
   (GBT, N=1) is the cost-efficient fallback.

---

## 1. Arc Timeline

The R1.5 arc spans 7 calendar days (2026-03-06 to 2026-03-12) across five
phases:

| Phase | Dates | PRs | Theme | Key Result |
|-------|-------|-----|-------|------------|
| **R1.5 v1** | Mar 6–8 | #555–#584 | Build AV pipeline, evaluate | +0.152 net_eppd, ADVANCED (suit -0.142 blocks) |
| **R1.5.2** | Mar 9–10 | #588–#603 | Ablation diagnostics | Features irrelevant, objective critical, bimodal target identified |
| **R1.5.3 Step 0** | Mar 11–12 | #610–#613 | Error taxonomy + sanity checks | Boundary=28.5%, play-policy confound stable |
| **R1.5.3 Track B** | Mar 11 | #614 | GBT prototype | +1.1 net_eppd, suit resolved, PROTOTYPE VALIDATED |
| **R1.5.3 Phase 0–1A** | Mar 12 | #623–#626 | Multi-rollout + 2×2 matrix | H14 CONFIRMED (R²), H15 CONFIRMED (model > labels) |

**PR type distribution:** 15 feat, 12 docs, 5 fix, 3 chore, 1 refactor.

**Incumbent throughout:** `hybrid_olsa_full` R0 (`hybrid_r0_full.json`).
No rung was promoted; R0 remains the incumbent bidder.

---

## 2. R1.5 v1 — Objective Alignment (Steps 0–10)

### 2.1 Motivation

R1 regressed by -0.348 net_eppd despite achieving higher suit R² (0.63 vs
R0's 0.25). Root cause analysis (PRs #550–#553) identified two interacting
problems:

1. **Objective mismatch:** Training on `tricks_won` while evaluating on
   `points_per_deal` creates an unbridged gap that hand-coded utility
   (Gaussian EV) must fill.
2. **Decision-layer degeneracy (H10):** `_compute_ev_static()` produces EV
   monotonically non-increasing in bid_n for sigma > 0, causing
   `compute_best_bid()` to always select the minimum legal bid.
   Proven analytically with 101 parametric tests (PR #552).

R1.5 eliminates both by training directly on `net_points` and using pure
argmax over predicted values.

### 2.2 Architecture Change

| Layer | R0/R1 | R1.5 |
|-------|-------|------|
| Objective | `tricks_won` | `net_points` |
| Decision | Gaussian EV + sigma + risk_lambda | Argmax over predictions |
| Features | 39 hand features | 52-col state (hand + position + partner + action) |
| Models | 1 per contract → `_compute_ev_static()` | 4 per-contract OLS (suit/high/low/pass) → argmax |
| Data | Bidless (outcome observation) | Counterfactual (forced-action rollouts) |

See [00_step0_foundations.md](00_step0_foundations.md) for infrastructure details.

### 2.3 Pipeline Gate Results

| Gate | Criterion | Result | Evidence |
|------|-----------|--------|----------|
| X1 (dataset) | Schema valid, 2,000+ deals | **PASS** | 2,500 deals, 468k rows |
| X2 (training) | R² > 0.05 per contract | **PASS** | suit=0.565, high=0.533, low=0.514, pass=0.046 |
| X3 (offline ranking) | Top-1 accuracy ≥ 40% | **FAILED** (adjudicated ADVANCED) | 26.6% top-1; oracle noise from single-rollout labels. Robust alternatives show signal: 84.6% pairwise accuracy, 67.6% regret reduction |
| X4 QUICK | Delta > -0.10 | **PASS** | +0.165 net_eppd |
| X4 FULL | CI_low > 0.180 (promotion) | **FAIL** | CI_low = +0.124 |
| X4 FULL | CI_low > -0.10, delta > 0 (advancement) | **PASS** | +0.152 net_eppd |

See [01_offline_gate_x3_report.md](01_offline_gate_x3_report.md) for Gate X3
adjudication rationale; [05_h2h_battery_full.md](05_h2h_battery_full.md) for
FULL battery.

### 2.4 FULL H2H Results (50,000 deals)

**Symmetrized pairwise deltas:**

| Comparison | net_eppd Delta | 95% CI | Significant |
|------------|----------------|--------|-------------|
| AV v1 vs HO_full R0 (pooled) | **+0.152** | **[+0.124, +0.180]** | **Yes** |
| AV v1 vs HO R0 (pooled) | +0.182 | [+0.155, +0.210] | Yes |
| HO_full R0 vs HO R0 | +0.028 | [+0.002, +0.055] | Yes |

**Per-contract-type deltas (AV v1 vs HO_full R0):**

| Contract | Delta | 95% CI | Significant |
|----------|-------|--------|-------------|
| **Suit** | **-0.142** | **[-0.180, -0.105]** | **Yes (regression)** |
| High | +0.430 | [+0.359, +0.501] | Yes |
| Low | +0.495 | [+0.444, +0.546] | Yes |

High and low are strongly positive — OLS captures no-trump structure well.
The suit regression (-0.142) is statistically significant and blocks
promotion: CI_low (+0.124) falls below the delta floor (0.180).

### 2.5 Behavioral Profile

| Metric | AV v1 | HO_full R0 |
|--------|-------|------------|
| Bid rate | 56–57% | 43–44% |
| Make rate (self-play) | 94.6% | 96.8% |
| Bid level | Always 4 | Variable (4–7+) |
| Pass rate | ~0% | ~43% |

AV v1 independently discovered a "quantity over quality" strategy: bid on
nearly every hand at minimum level, accepting low set risk. This is a genuine
strategic innovation from the data, not a hand-coded heuristic — but it is
also a symptom of OLS's limitation. The negative bid_n coefficient (-0.058
for suit) makes predicted EV monotonically decreasing in bid level, so
argmax always selects the lowest legal bid.

### 2.6 Decision

**ADVANCED, not promoted.** R0 hybrid_olsa_full remains incumbent. The suit
regression is the sole blocker; high/low gains are large and significant.
See [07_promotion_decision.md](07_promotion_decision.md) and
[rung_closeout.md](rung_closeout.md).

---

## 3. R1.5.2 — Diagnostic Campaign

### 3.1 Motivation

With R1.5 v1 ADVANCED, the question became: *why does suit regress?* Is it
features, data, model capacity, or something else? The diagnostic campaign
systematically tested each hypothesis.

### 3.2 Ablation Results

Six controlled experiments, each isolating a single factor:

| Experiment | Factor Tested | R² Effect | H2H Effect | Verdict |
|-----------|---------------|-----------|------------|---------|
| **Cell A** (39 vs 52 features) | Extra state features | Δ < 0.005 | — | **Irrelevant** |
| **Cell B'** (tricks_won target) | Objective alignment | — | -13.7 net_eppd, bids 10/hand | **Critical** |
| **Option A** (R0 on CF data) | Data source | Suit R² 0.084 vs 0.223 (bidless) | — | CF data noisier for R0 |
| **Declare/defend split** | Regime decomposition | +0.01 R² (gate >0.05) | — | **Wrong decomposition** |
| **Partner zeroed** | Partner features | Suit/high/low Δ < 0.005; pass -0.041 | -0.492 vs R0 | **Critical for action selection** |
| **Interaction terms** | OLS non-linearity | Δ < 0.001 | +0.002 (noise) | **No effect — Q5 answered** |

See [v2_ablation_analysis.md](v2_ablation_analysis.md) for full analysis.

### 3.3 Key Finding: Features Exhausted, Target Structure is the Problem

Feature engineering is conclusively exhausted. Neither expanding the feature
set (39→52, Δ<0.005), adding interaction terms (bower×trump, trump², bowers²;
Δ<0.001), nor splitting by declare/defend regime (+0.01 R²) moves the needle.

The problem is **structural**: suit net_points has a bimodal distribution
(make ≈ +bid, set ≈ -bid), and OLS fits the mean of both modes — a prediction
that's optimal for neither. This was confirmed with GMM analysis
(suit ΔBIC=4,081 for bimodal vs unimodal fit; see
[diagnostic_calibration.md](diagnostic_calibration.md)).

### 3.4 The Partner Feature Surprise

Partner features contribute almost nothing to per-action prediction quality
(R² Δ<0.005 for suit/high/low) yet are AV v1's **most valuable component**
in gameplay: H2H without partner features is -0.492 vs R0 (worse than R0),
versus +0.224 with partner features.

The mechanism is action selection, not prediction accuracy. Partner features
affect *which action the bidder selects* (particularly pass decisions:
pass R² drops 0.046→0.005 without partner context). Knowing your partner bid
strongly changes whether you compete or defer — an effect invisible to
per-contract R² metrics.

### 3.5 The Cell B' Catastrophe (Objective Necessity Proof)

Cell B' (AV architecture + `tricks_won` target) is the most informative
ablation. The model bids 10 on every hand with a 1% make rate and -13.7
net_eppd — catastrophically worse than random bidding.

**Mechanism:** With action features (bid_n, bid_n²), higher bids correlate
with more tricks in the training data (strong hands bid high AND win more
tricks). The quadratic term makes bid_n=10 maximize predicted tricks for all
hands. Argmax always picks the maximum bid.

R0 avoids this because its Gaussian EV utility layer includes hand-coded
set-penalty logic that prevents overbidding. The AV architecture's argmax has
no such guardrail — it *requires* the training objective to encode penalties
directly. This proves the objective and decision rule are synergistic (H4).

---

## 4. R1.5.3 Step 0 — Error Taxonomy and Sanity Checks

### 4.1 Where Do Suit Errors Concentrate?

Using the FULL H2H data (51,741 suit hands) and counterfactual dataset,
errors were decomposed into regions:

| Error Region | Share of Total Error | Description |
|-------------|---------------------|-------------|
| Boundary (P(make)=0.3–0.7) | 28.5% | Close make/set calls |
| Clear-set (P(make)<0.3) | 43.0% | Model should know it'll get set |
| Wrong contract | 26.5% | Should have bid high/low instead |
| Wrong bid level (H13) | 2.3% | Bid-level optimization irrelevant |

Errors are **spread across the calibration range**, not concentrated at the
make/set boundary. This has gate implications:

- Boundary < 60% → **Track A (two-stage P(make) model) deprioritized**
- Wrong contract = 26.5% → Contract-selection is a real issue
- H13 answered: bid-level headroom is negligible (2.3%)

See [suit_decision_diagnostic.md](suit_decision_diagnostic.md).

### 4.2 Play-Policy Sanity Check (H7/H8)

Does using GluttonStrategy for trick play during label generation bias
bidder rankings?

**Result:** No. Spearman ρ=1.0, zero ranking inversions across all bidders
tested (4 bidders, seed=42, n=2,000). Glutton is uniformly better than Greedy
(mean +0.19–0.21 tricks, p<0.0001) but the advantage is consistent — it
doesn't change which bidder wins. Labels generated with GluttonStrategy are
trustworthy for comparative evaluation.

---

## 5. R1.5.3 Track B — GBT Prototype

### 5.1 Motivation

With feature engineering exhausted and Track A (two-stage model) deprioritized
by the error taxonomy (boundary < 60%), the primary path became non-linear
model architecture: gradient-boosted trees (GBT).

### 5.2 Results (QUICK, 2,500 deals)

**Pairwise H2H deltas (symmetrized):**

| Comparison | Pooled | Suit | High | Low |
|-----------|--------|------|------|-----|
| GBT vs OLS AV | **+1.112** [+0.986, +1.244] | +1.190 [+1.011, +1.373] | +1.112 [+0.702, +1.518] | +0.931 [+0.605, +1.260] |
| GBT vs Hybrid R0 | **+1.067** [+0.925, +1.208] | +1.110 [+0.946, +1.276] | +1.467 [+1.030, +1.900] | +0.736 [+0.396, +1.079] |
| OLS AV vs Hybrid R0 | +0.165 [+0.080, +0.249] | -0.136 [-0.303, +0.032] | +0.454 [+0.141, +0.774] | +0.519 [+0.299, +0.739] |

All CIs exclude zero for pooled comparisons. GBT dominates both baselines
across **all three contract types** — the first model in the entire R1.5 arc
to show positive suit delta versus R0.

**Sample size caveat:** 2,500 deals is QUICK-tier. Per-contract facets for
high contracts have as few as 300 deals, well below the 2,000-deal minimum.

### 5.3 Why GBT Resolves Suit

GBT's tree structure naturally partitions the feature space into regions
corresponding to different outcome modes. Where OLS fits a single linear
surface through both the "will make" and "will get set" populations, GBT
can learn separate prediction rules for each regime — effectively performing
the two-stage decomposition (P(make) × E[pts|make] + P(set) × E[pts|set])
that Track A would have built explicitly, but discovered from data.

### 5.4 Behavioral Innovation: Selective Bidding

| Metric | GBT AV | OLS AV v1 | Hybrid R0 |
|--------|--------|-----------|-----------|
| Pass rate | **31.9%** | 0.0% | 5.7% |
| Avg winning bid | 5.44 | 4.00 | 3.77 |
| Make rate (self-play) | 87.1% | 94.6% | 96.6% |
| Bid range | 1–10 | Always 4 | 1–4 |
| CVaR₅ | -6.63 | -1.80 | -0.71 |

GBT learned the value of information: passing when all available actions
predict poor outcomes is better than bidding defensively at minimum level.
This resolves the long-standing 0% pass rate pathology of OLS AV v1, where
the bimodal-mean prediction for any bid always looked better than the pass
model's prediction.

### 5.5 Variance–Return Tradeoff

GBT's higher variance (score std 3.60 vs OLS 2.41, Hybrid 2.24) and worse
tail risk (CVaR₅ -6.63 vs -0.71 to -1.80) reflect its aggressive bidding.
The +1.1 net_eppd advantage compensates in expected-value terms, but tail
risk may matter in specific domains.

See [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) for
full analysis.

---

## 6. R1.5.3 Phase 0 and Phase 1A — Label Quality vs Model Capacity

### 6.1 Phase 0: Multi-Rollout Label Smoothing (H14)

**Hypothesis:** Single-rollout labels produce bimodal targets. Averaging over
multiple opponent hand configurations should smooth the target toward the true
expected value, improving OLS fit.

**Three datasets generated** at SMOKE scale (500 deals, seed=42):

| N (opponent samples) | OLS Suit R² | Δ from N=1 |
|---------------------|-------------|-----------|
| 1 (baseline) | 0.587 | — |
| 5 | 0.677 | +0.090 |
| 20 | 0.708 | **+0.121** |

**H14 CONFIRMED:** The +0.121 suit R² gain is the **largest single R²
improvement in the entire R1.5 arc** — exceeding the gate threshold (+0.03) by
4×. All contract families improve: high +0.150, low +0.152, pass +0.103.

N=5 captures 74% of the N=20 suit gain (diminishing returns).

**GBT on N=20 labels:** Suit R² 0.749 (marginal +0.041 over OLS N=20). But
GBT pass R² collapses (0.082 vs OLS 0.256) — likely overfitting to single-
rollout noise patterns that multi-rollout removes.

See [09_multi_rollout_diagnostic.md](09_multi_rollout_diagnostic.md).

### 6.2 Phase 1A: The Critical Experiment (H15)

**Question:** Does the R² improvement from multi-rollout labels translate to
gameplay improvement? Does multi-rollout OLS match single-rollout GBT?

**2×2 factorial design** (5-bidder QUICK H2H, 25 matchups, 2,500 deals):

| Cell | Model | Labels | vs R0 (pooled) | vs R0 (suit) |
|------|-------|--------|---------------|-------------|
| A | OLS | N=1 | +0.165 | **-0.139** |
| B | OLS | N=20 | +0.139 | **-0.264** |
| C | GBT | N=1 | **+1.067** | **+1.112** |
| D | GBT | N=20 | **+1.111** | **+0.945** |

### 6.3 Effect Decomposition

| Effect | Value | Interpretation |
|--------|-------|---------------|
| Label effect (OLS): B−A | **-0.026** | Multi-rollout labels do NOT help OLS gameplay |
| Label effect (GBT): D−C | +0.044 | Marginal benefit (CI spans zero) |
| Model effect (N=1): C−A | **+0.902** | GBT massively outperforms OLS on same labels |
| Model effect (N=20): D−B | **+0.972** | GBT advantage even larger with better labels |
| **B vs C (labels > model?)** | **-1.206** | **Multi-rollout OLS loses badly to single-rollout GBT** |

**H15 CONFIRMED: Model capacity matters ~35× more than label quality for
gameplay.**

The model effect (C−A = +0.902) dwarfs the label effect (B−A = -0.026).
Multi-rollout OLS (B) loses to single-rollout GBT (C) by 1.206 net_eppd.
Better labels cannot rescue OLS from the suit regression — the problem is
fundamentally about model capacity, not label noise.

### 6.4 The R²–Gameplay Paradox

This is the arc's most important methodological finding. Multi-rollout labels
improve OLS suit R² by +0.14 but produce **zero gameplay benefit**. OLS suit
delta actually *worsens* with better labels (-0.264 vs -0.139 at N=1).

**Explanation:** Smoother labels center OLS predictions even more tightly
around the bimodal mean. This improves R² (predictions are closer to the
smoothed target) but pushes predictions further from the implicit make/set
decision boundary. OLS cannot express the nonlinear threshold that separates
"should bid" from "should not bid" — regardless of label quality.

See [10_model_label_matrix.md](10_model_label_matrix.md).

---

## 7. Hypothesis Ledger

### 7.1 Confirmed Hypotheses

| ID | Hypothesis | Evidence | Quality |
|----|-----------|----------|---------|
| H1 | Objective mismatch was the main R1 failure mode | Cell B' catastrophe (bids 10/hand, -13.7 eppd). R1→R1.5 reversal (+0.152 vs -0.348). | Decisive |
| H2 | Decision-layer bottleneck (H10: Gaussian EV non-increasing) | Analytical proof: 101 parametric tests (PR #552). | Decisive — mathematical proof |
| H3 | Partner features matter for action selection (not prediction) | Pass R² drops 0.046→0.005. H2H: -0.492 without vs +0.224 with. | Decisive |
| H4 | Objective and decision layer are synergistic | Cell B' proves argmax requires net_points. R0's Gaussian EV compensates for wrong objective. | Decisive |
| H14 | Multi-rollout label averaging improves OLS suit R² | Suit R²: 0.587→0.708 (+0.121), 4× gate threshold. All families improve. | Decisive (offline) |
| H15 | Model capacity matters more than label quality for gameplay | B vs C: -1.206 net_eppd. Model effect 35× label effect. | Decisive |

### 7.2 Refuted Hypotheses

| ID | Hypothesis | Evidence | Quality |
|----|-----------|----------|---------|
| H5 | Suit regression caused by poor model fit | Suit has best R² (0.557) among all contracts. | Decisive |
| H6 | More features (39→52) explain the improvement | R² Δ < 0.005 on same data and target. | Decisive |
| H7 | Non-linear interaction terms fix suit regression | R² Δ < 0.001; H2H +0.002 (noise). | Decisive |
| H8 | Partner features are intrinsically harmful | R1.5 uses same features with positive delta. Ablation shows they are most valuable component. | Decisive |
| H9 | Counterfactual data improves R0-style models | Suit R² 0.084 (CF) vs 0.223 (bidless). Off-policy actions create noise. | Decisive |
| H10 | Partner features are irrelevant to AV | No-partner AV: -0.492 vs R0. | Decisive |

### 7.3 Supported Hypotheses

| ID | Hypothesis | Status | Evidence |
|----|-----------|--------|----------|
| H12 | Bimodal make/set target causes suit regression via between-mode OLS prediction | **SUPPORTED** | OLS suit delta stays negative regardless of label quality (even worse with better labels: -0.264). GBT resolves it. GMM ΔBIC=4,081. Feature engineering exhausted. |

### 7.4 Closed Hypotheses

| ID | Hypothesis | Status | Evidence |
|----|-----------|--------|----------|
| H11 | Declare/defend regime split addresses bimodality | **CLOSED (wrong axis)** | Gate FAIL: +0.01 R² (threshold >0.05). Defend R²≈0. 87% of data is declaring. The productive decomposition is make/set within declaring, not declare/defend. |
| H13 | Bid-level optimization is the bottleneck | **CLOSED (refuted)** | Only 2.3% of hands improvable via level adjustment. Headroom per hand: 0.132 net_pts. |

---

## 8. Causal Attribution

### 8.1 What Drives the R0→R1.5 Improvement (+0.152 net_eppd)

| Factor | Direction | Magnitude | Separable? | Confidence |
|--------|-----------|-----------|------------|------------|
| **Objective** (tricks_won → net_points) | Positive | Dominant | No — synergistic with decision rule | High |
| **Decision rule** (Gaussian EV → argmax) | Positive | Dominant | No — synergistic with objective | High |
| **Partner context** (3 features) | Positive | +0.75 pts/deal | Yes — controlled ablation | High |
| **Data generation** (bidless → counterfactual) | Enabling | N/A | Required for argmax, not independent source | Medium |
| **OLS on bimodal suit target** | **Negative** | -0.142 deficit | Yes — isolated to suit | High |

### 8.2 Per-Contract Attribution (Most Informative Axis)

| Contract | Delta vs R0 | Primary Factor | Secondary |
|----------|-------------|---------------|-----------|
| High | +0.430 | Objective + decision rule | Partner context |
| Low | +0.495 | Objective + decision rule | Partner context |
| Suit | -0.142 | Model capacity (bimodal target, *negative*) | Partially offset by objective |

### 8.3 What Drives the OLS→GBT Improvement (+1.1 net_eppd)

| Factor | Direction | Magnitude | Evidence |
|--------|-----------|-----------|----------|
| **Non-linear decision surface** | Dominant | ~35× label effect | Phase 1A: C−A = +0.902 |
| **Selective bidding (learned passing)** | Positive | Part of above | GBT 31.9% pass vs OLS 0% |
| **Better R²** | Marginal | +0.03 R² | Offline fit modest vs gameplay gain |
| **Label quality (multi-rollout)** | Negligible for gameplay | ~0 (OLS), +0.04 (GBT) | Phase 1A: B−A = -0.026 |

---

## 9. Key Findings and Emergent Insights

### 9.1 The Three Pivotal Results

**1. Objective alignment is non-negotiable.** The switch from `tricks_won` to
`net_points` reversed R1's regression (-0.348 → +0.152) and unlocked
previously inaccessible high/low gains (+0.43/+0.49). Cell B' proves the
architecture *requires* the right objective — argmax on the wrong objective
is catastrophically worse than hand-coded utility on the wrong objective.

**2. R² ≠ gameplay quality.** This insight emerged three times:
- R1: higher R² than R0, worse gameplay (-0.348)
- R1.5: suit has best R² (0.557), worst gameplay delta (-0.142)
- Phase 1A: +0.14 R² from multi-rollout → zero gameplay gain for OLS

**Implication:** Prediction accuracy and decision quality are distinct metrics.
A model can be more accurate in squared-error terms while producing worse
decisions. This occurs when the improved accuracy doesn't change the decision
boundary — it just fits the target surface better without crossing any
threshold that would flip an action choice. All future evaluation must include
gameplay (H2H) alongside offline metrics.

**3. Model capacity is the binding constraint.** The Phase 1A 2×2 decomposition
is definitive: model effect is 35× the label effect. Multi-rollout labels
improve R² dramatically but cannot rescue OLS from the structural limitation
that its linear surface cannot represent the make/set decision boundary.
GBT's tree structure resolves this by discovering the boundary from data.

### 9.2 Emergent Findings

**Quantity-over-quality bidding.** OLS AV v1 independently discovered a valid
strategy: bid on ~57% of hands at minimum level. This contrasts with R0's
selective approach (~43% bid rate, variable levels). GBT discovered a third
approach: selective but aggressive (31.9% pass rate, avg bid 5.44 when
bidding). The progression OLS→GBT can be read as: simple model → simple
strategy (always bid low) → complex model → sophisticated strategy (be
selective, bid high when strong).

**Bimodality is universal.** All R1.5 contracts show bimodal residuals
(high ΔBIC=1,469; low ΔBIC=1,286; suit ΔBIC=4,081). The difference is that
high/low gains are large enough to overcome their bimodality; suit's steeper
bower-driven make/set cliff makes the between-mode prediction error more
costly for decisions.

**Partner features work through pass decisions.** Despite contributing
<0.005 R² to bid-contract predictions, partner features are worth +0.75
pts/deal in gameplay. They gate the pass decision: knowing your partner bid
strongly changes whether you compete or defer. This is an action-selection
effect that R² cannot measure — a methodological lesson for feature
importance analysis in decision-making systems.

---

## 10. What Worked / What Did Not

### 10.1 What Worked

1. **Objective alignment.** The single most impactful intervention in the arc.
   Reversing R1's regression and unlocking high/low validates the R1 closeout
   diagnosis.

2. **Systematic hypothesis elimination.** The R1.5.2 diagnostic campaign
   eliminated 6 hypotheses in 5 experiments, narrowing suit regression to a
   single leading theory (bimodal target, H12). This prevented wasted effort
   on feature engineering that could not help.

3. **Pre-registered gating methodology.** Each experiment had formal gates
   with pre-specified thresholds. This prevented premature promotion
   (CI_low +0.124 < 0.180), identified real blockers, and provided clear
   decision criteria. Gate X3 adjudication demonstrated that gates can be
   overridden with documented justification when the specification is flawed.

4. **Counterfactual dataset design.** Forced-action rollouts provide the
   action-value labels that make argmax viable. Without counterfactual data,
   the model cannot compare alternative actions for the same hand state.

5. **2×2 factorial decomposition.** The model×label matrix cleanly separated
   two confounded factors (model capacity vs label quality) and produced a
   decisive answer. This experimental design should be the template for any
   future two-factor question.

6. **Rapid iteration speed.** The entire arc — pipeline build, FULL
   evaluation, diagnostic campaign, GBT prototype, multi-rollout test,
   factorial experiment — completed in 7 calendar days across ~70 PRs.

### 10.2 What Did Not Work

1. **Feature engineering for suit regression.** Both feature expansion
   (39→52, Δ<0.005), interaction terms (bower×trump, trump², bowers²;
   Δ<0.001), and regime splitting (declare/defend, +0.01 R²) yielded zero
   measurable improvement. The problem was never in the feature space.

2. **Multi-rollout labels for OLS gameplay.** Despite the dramatic offline
   R² gain (+0.14), multi-rollout labels produced zero gameplay benefit for
   OLS and actually worsened the suit delta (-0.264 vs -0.139). Better labels
   center OLS predictions more tightly around the bimodal mean, which is
   further from the optimal decision boundary.

3. **R² as a gameplay proxy.** Repeatedly, offline R² improvements did not
   translate to decision quality. This is not a failure of the metric itself
   but of using it as a proxy for gameplay. Future work should treat R² as a
   diagnostic (does the model learn?), not a predictor of gameplay quality.

4. **OLS as AV architecture.** OLS cannot represent the nonlinear make/set
   decision boundary for suit contracts. This is conclusive across all
   interventions: features, labels, regime splits, interaction terms.

### 10.3 Process Observations

1. **Diagnostic-before-fix discipline saved time.** After R1.5 v1 ADVANCED,
   the temptation was to try fixes immediately. The disciplined diagnostic
   campaign (R1.5.2) eliminated dead-end directions before investing in them,
   preventing at least 3 wasted implementation efforts (feature expansion,
   interaction terms, regime split).

2. **Gate adjudication protocol is valuable.** Gate X3's formal FAILED →
   adjudicated ADVANCED precedent established that gates are decision aids,
   not mechanical rules. The adjudication required documented reasoning and
   alternative metrics, which strengthened confidence in advancement.

3. **QUICK→FULL shrinkage is predictable.** QUICK (+0.165) to FULL (+0.152)
   showed 8% shrinkage, providing a calibration reference for future QUICK
   screening.

---

## 11. Open Questions and Next Steps

### 11.1 Immediate (Phase 2)

| Question | Method | Priority |
|----------|--------|----------|
| GBT at FULL scale (50k deals) | FULL H2H battery with Cell D (GBT, N=20) and/or Cell C (GBT, N=1) | **P0 — required for promotion** |
| Cell D vs Cell C cost-benefit | Label effect for GBT is +0.044 (not significant at QUICK). Is N=1 sufficient? | P0 — determines dataset cost |
| Hyperparameter tuning | Grid search: `n_estimators`, `max_depth`, `learning_rate`, `min_samples_leaf` | P1 |
| Multi-seed validation | Seeds 42, 123, 456 | P1 |

### 11.2 Deferred

| Direction | Why Deferred | Reactivation Trigger |
|-----------|-------------|---------------------|
| Feature engineering sweep | H6 and H7 show features are not the bottleneck. | Evidence that the problem is in feature space (contradicted) |
| Multi-rollout OLS as primary path | H15 shows model capacity >> labels. | N/A — definitively resolved |
| Partner-feature removal | H3 and H10: partner features are AV's most valuable component. | N/A — definitively refuted |
| Hybrid routing (AV high/low + R0 suit) | Captures gains but teaches nothing about suit. | Promotion urgency with no GBT path |
| Track A (two-stage P(make) model) | Boundary=28.5% < 60% threshold; GBT naturally discovers the decomposition. | GBT fails at FULL scale |
| OLS as AV architecture | H12 SUPPORTED, H15 CONFIRMED: model capacity is the binding constraint. | N/A — conclusively retired |

### 11.3 Decision Tree Status

```
R1.5 v1: ADVANCED (suit regression)
  └─ R1.5.2 diagnostics: CONCLUDED (features exhausted, bimodal target)
      └─ R1.5.3 Step 0: Track B selected (boundary < 60%)
          ├─ Play-policy gate: PASS (ρ=1.0)
          ├─ Track B (GBT): PROTOTYPE VALIDATED (+1.1 net_eppd)
          ├─ Phase 0 (H14): CONFIRMED (R² +0.121)
          ├─ Phase 1A (H15): CONFIRMED (model >> labels, 35×)
          └─ Phase 2 (FULL validation): ← YOU ARE HERE
```

---

## 12. Experiment Inventory

| # | Experiment | Scale | Key Result | Report |
|---|-----------|-------|------------|--------|
| 1 | AV v1 pipeline (Steps 0–2) | QUICK (2,500) | Infrastructure validated | [00_step0_foundations.md](00_step0_foundations.md) et al. |
| 2 | Offline ranking (Gate X3) | QUICK | 26.6% top-1 (adjudicated ADVANCED) | [01_offline_gate_x3_report.md](01_offline_gate_x3_report.md) |
| 3 | 3-seed gameplay screen | 3×QUICK | WR 49.9–51.1%, 0% pass rate | [02_gameplay_screen_report.md](02_gameplay_screen_report.md) |
| 4 | H2H battery QUICK (X4) | QUICK | +0.165 net_eppd, PASS | [03_h2h_battery_quick.md](03_h2h_battery_quick.md) |
| 5 | H2H battery FULL (X4) | FULL (50k) | +0.152, CI [+0.124, +0.180], ADVANCED | [05_h2h_battery_full.md](05_h2h_battery_full.md) |
| 6 | Feature ablation (Cell A) | QUICK | R² Δ < 0.005 | [v2_ablation_analysis.md](v2_ablation_analysis.md) §2 |
| 7 | Objective ablation (Cell B') | QUICK | Bids 10/hand, -13.7 eppd | [v2_ablation_analysis.md](v2_ablation_analysis.md) §3 |
| 8 | Data source (Option A) | QUICK | CF worse for R0 (suit R² 0.084 vs 0.223) | [v2_ablation_analysis.md](v2_ablation_analysis.md) §2.3 |
| 9 | Declare/defend regime split | QUICK | +0.01 R², gate FAIL | [v2_ablation_analysis.md](v2_ablation_analysis.md) §4 |
| 10 | Partner feature ablation | QUICK | -0.492 vs R0, pass R² 0.046→0.005 | [v2_ablation_analysis.md](v2_ablation_analysis.md) §5 |
| 11 | Interaction term ablation | QUICK | R² Δ < 0.001, H2H +0.002 | [v2_ablation_analysis.md](v2_ablation_analysis.md) §7 |
| 12 | Suit error taxonomy | FULL (51k hands) | Boundary=28.5%, wrong-contract=26.5% | [suit_decision_diagnostic.md](suit_decision_diagnostic.md) |
| 13 | Play-policy gate (H7/H8) | SMOKE (2k) | ρ=1.0, zero inversions | PR #613 |
| 14 | GBT prototype (Track B) | QUICK | +1.1 net_eppd, suit resolved | [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) |
| 15 | Multi-rollout H14 test | SMOKE (500) | Suit R² 0.587→0.708 (+0.121) | [09_multi_rollout_diagnostic.md](09_multi_rollout_diagnostic.md) |
| 16 | 2×2 model×label matrix (H15) | QUICK | Model effect 35× label effect | [10_model_label_matrix.md](10_model_label_matrix.md) |

---

## Companion Reports

| Report | Focus |
|--------|-------|
| [rung_closeout.md](rung_closeout.md) | R1.5 v1 canonical closeout |
| [07_promotion_decision.md](07_promotion_decision.md) | Promotion decision — ADVANCED |
| [05_h2h_battery_full.md](05_h2h_battery_full.md) | FULL H2H battery (definitive R1.5 v1 evidence) |
| [06_ablation.md](06_ablation.md) | Per-contract attribution |
| [v2_ablation_analysis.md](v2_ablation_analysis.md) | Diagnostic ablation campaign (6 experiments) |
| [suit_decision_diagnostic.md](suit_decision_diagnostic.md) | Error taxonomy + gate inputs |
| [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) | GBT prototype — VALIDATED |
| [09_multi_rollout_diagnostic.md](09_multi_rollout_diagnostic.md) | H14 — label quality test |
| [10_model_label_matrix.md](10_model_label_matrix.md) | H15 — 2×2 model×label decomposition |
| [measurement_integrity_r1_5.md](measurement_integrity_r1_5.md) | Methodology review + deviations |
| [post_r1_retro.md](post_r1_retro.md) | Prior retrospective (R1 through R1.5.2) |
| [appendix_experiment_ledger.md](appendix_experiment_ledger.md) | Full experiment ledger |

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — retrospective document, not a gate artifact |
| PR range | #555–#626 |
| Date range | 2026-03-06 to 2026-03-12 |
| Calendar days | 7 |
| Incumbent | hybrid_olsa_full R0 (hybrid_r0_full.json) |
| R0 tag | `r0-canonical-v2` at commit `4e26d44` |
| R1.5 v1 closeout | rung_closeout.md |
| Forward decision tree | plans/r1_5_forward_decision_tree.md |
| analysis_base_sha | 1d868f4 |
