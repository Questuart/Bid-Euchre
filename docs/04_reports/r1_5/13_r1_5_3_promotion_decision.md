# R1.5.3 Promotion Decision — GBT Action-Value Bidder

> For the canonical rung summary, see [rung_closeout.md](rung_closeout.md).

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Date:** 2026-03-13
**Predecessor:** [07_promotion_decision.md](07_promotion_decision.md) (R1.5 v1 OLS — ADVANCED)

## Decision: <!-- PENDING — fill after GBT FULL results -->

GBTActionValueBidder v1 is **<!-- PROMOTED / ADVANCED -->** <!-- based on FULL
validation results -->.

### Decision Criteria

| Criterion | Threshold | Result | Status |
|-----------|-----------|--------|--------|
| Pooled CI_low vs R0 | > 0.180 | <!-- CI_low from FULL --> | <!-- PASS/FAIL --> |
| Suit delta vs R0 | > 0.0 | <!-- suit delta from FULL --> | <!-- PASS/FAIL --> |
| No seed reversals | 0/3 seeds negative | <!-- seed stability --> | <!-- PASS/FAIL --> |
| Pooled point estimate > 0 | > 0.0 | <!-- point estimate --> | <!-- PASS/FAIL --> |

## 1. Executive Summary

R1.5.3 systematically explored three paths to resolve the OLS suit regression
(-0.142) that blocked R1.5 v1 promotion:

| Track | Approach | Result | Verdict |
|-------|----------|--------|---------|
| **GBT prototype** | Gradient-boosted trees on N=1 labels | +1.1 net_eppd vs R0 (QUICK) | **PROTOTYPE VALIDATED** |
| **2×2 model×label matrix** | OLS vs GBT × N=1 vs N=20 | Model capacity >> labels (35×) | **H15 CONFIRMED** |
| **Two-stage OLS (H16)** | P(make) × E[pts|make] + (1−P) × E[pts|set] | +0.124 vs OLS, −0.750 vs GBT | **PARTIAL — cannot close gap** |
| **GBT FULL validation** | 3-seed, 50K deals, 9 matchups | <!-- PENDING --> | <!-- PENDING --> |

**Key conclusion:** GBT resolves the structural suit regression that OLS could
not address through any feature engineering, label improvement, or architectural
variation. The model capacity advantage is decisive (35× the label quality
effect). OLS is formally retired as an action-value architecture.

## 2. Evidence Chain

### 2.1 GBT Prototype (QUICK, 2,500 deals)

Source: [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md)

| Comparison | Pooled | Suit | High | Low |
|-----------|--------|------|------|-----|
| GBT vs Hybrid R0 | **+1.067** [+0.925, +1.208] | +1.110 [+0.946, +1.276] | +1.467 [+1.030, +1.900] | +0.736 [+0.396, +1.079] |
| GBT vs OLS AV v1 | **+1.112** [+0.986, +1.244] | +1.190 [+1.011, +1.373] | +1.112 [+0.702, +1.518] | +0.931 [+0.605, +1.260] |

GBT is the **first model in the R1.5 arc to show positive suit delta vs R0**.
All per-contract CIs exclude zero in the expected direction.

**Behavioral profile:**

| Metric | GBT AV | OLS AV v1 | Hybrid R0 |
|--------|--------|-----------|-----------|
| Pass rate | 31.9% | 0.0% | 5.7% |
| Avg winning bid | 5.44 | 4.00 | 3.77 |
| Make rate (self-play) | 87.1% | 94.6% | 96.6% |
| CVaR₅ | -6.63 | -1.80 | -0.71 |

GBT learned selective, aggressive bidding — a qualitatively different strategy
from both OLS (always bid minimum) and Hybrid R0 (conservative selection).

### 2.2 Model vs Label Decomposition (H15)

Source: [10_model_label_matrix.md](10_model_label_matrix.md)

| Cell | Model | Labels | vs R0 (pooled) | vs R0 (suit) |
|------|-------|--------|---------------|-------------|
| A | OLS | N=1 | +0.165 | -0.139 |
| B | OLS | N=20 | +0.139 | -0.264 |
| C | GBT | N=1 | **+1.067** | **+1.112** |
| D | GBT | N=20 | **+1.111** | **+0.945** |

| Effect | Value | Interpretation |
|--------|-------|---------------|
| Model effect (N=1): C−A | **+0.902** | GBT massively outperforms OLS |
| Label effect (OLS): B−A | -0.026 | Better labels do NOT help OLS gameplay |
| B vs C | **-1.206** | Multi-rollout OLS loses badly to single-rollout GBT |
| **Effect ratio** | **~35×** | **Model capacity dominates label quality** |

**H15 CONFIRMED:** Model capacity is the binding constraint. Multi-rollout
labels cannot rescue OLS from the structural bimodal-mean limitation. Better
labels actually *worsen* OLS suit performance (-0.264 vs -0.139) because they
center predictions more tightly around the bimodal mean, further from the
optimal decision boundary.

### 2.3 Two-Stage OLS (H16)

Source: [11_two_stage_evaluation.md](11_two_stage_evaluation.md)

| Matchup | Symmetrized delta |
|---------|-------------------|
| Two-Stage vs OLS AV | +0.124 |
| Two-Stage vs Hybrid R0 | +0.191 |
| Two-Stage vs GBT | **-0.750** |

**H16 PARTIAL:** Two-stage OLS improves over flat OLS by +0.124 net_eppd via
explicit make/set decomposition (P(make) logistic AUC=0.9363). However, it
falls 0.750 behind GBT — far outside the 0.3 threshold for "closing the gap."
The make/set decomposition helps, but GBT discovers equivalent (or superior)
structure automatically from data.

### 2.4 GBT FULL Validation (Phase 2)

<!-- PENDING: Fill from 12_gbt_full_validation.md when available -->

**Setup:** 3-seed (42, 123, 456) × 50,000 deals × 9 matchups (3-bidder roster:
GBT AV v1, OLS AV v1, Hybrid R0).

**Success gates:**
- Pooled CI_low > 0.180 (delta floor from R0 calibration)
- Suit delta > 0 (regression resolved)
- No seed reversals (all 3 seeds show positive pooled delta)

<!--
**Results:**

| Metric | Value | Gate |
|--------|-------|------|
| Pooled delta | | |
| Pooled CI | | |
| Suit delta | | |
| Suit CI | | |
| High delta | | |
| Low delta | | |
| Seed 42 pooled | | |
| Seed 123 pooled | | |
| Seed 456 pooled | | |

**Behavioral stability:**

| Metric | Seed 42 | Seed 123 | Seed 456 | Stable? |
|--------|---------|----------|----------|---------|
| Pass rate | | | | |
| Make rate | | | | |
| Avg bid | | | | |
-->

## 3. Hypothesis Ledger Update

### New/Updated since R1.5 v1 (report 07)

| ID | Hypothesis | Status | Evidence |
|----|-----------|--------|----------|
| H12 | Bimodal make/set target causes suit regression | **SUPPORTED** | OLS suit delta negative at any label quality; GBT resolves |
| H14 | Multi-rollout label averaging improves OLS R² | **CONFIRMED** | +0.121 suit R² (4× gate), all families improve |
| H15 | Model capacity >> label quality for gameplay | **CONFIRMED** | 35× effect ratio; B vs C = -1.206 |
| H16 | Two-stage OLS closes the GBT gap | **PARTIAL** | +0.124 vs flat OLS; -0.750 vs GBT (threshold: 0.3) |

### Full Ledger (cumulative)

**Confirmed:** H1 (objective mismatch), H2 (decision-layer degeneracy), H3
(partner features → action selection), H4 (objective+decision synergistic),
H14 (multi-rollout R²), H15 (model >> labels)

**Supported:** H12 (bimodal suit target)

**Refuted:** H5 (poor suit fit), H6 (more features), H7 (interaction terms),
H8 (partner features harmful), H9 (CF data helps R0), H10 (partner features
irrelevant)

**Closed:** H11 (declare/defend — wrong axis), H13 (bid-level optimization —
2.3% headroom), H16 (two-stage — partial, cannot close gap)

## 4. OLS Retirement Decision

OLS is formally retired as an action-value bidder architecture based on
convergent evidence from four independent evaluations:

| Evidence | Finding | Conclusive? |
|----------|---------|-------------|
| R1.5 v1 FULL H2H | Suit regression -0.142, CI excludes 0 | Yes |
| Feature engineering (6 experiments) | All Δ < 0.005, exhausted | Yes |
| H15 (2×2 matrix) | Model effect 35× label effect | Yes |
| H16 (two-stage) | +0.124 improvement, still -0.750 behind GBT | Yes |

**No path exists to promote OLS AV to incumbent status.** The bimodal suit
target (H12) is a structural limitation of linear models that cannot be
resolved through features, labels, or decomposition. GBT resolves it
automatically.

The two-stage architecture retains value as an **interpretable reference** for
understanding GBT decisions (the P(make) logistic provides calibrated make
probability), but it is not competitive for gameplay.

## 5. R1.5 → R1.6 Transition

### What R1.5.3 Established

1. **GBT as the AV architecture** — conclusive evidence across QUICK and (FULL
   pending) evaluations
2. **Partner features remain critical** — the most valuable AV component for
   action selection (H3, H10)
3. **Single-rollout labels are sufficient** — N=1 GBT vs N=20 GBT: +0.044
   (CI spans zero at QUICK)
4. **Selective bidding emerges naturally** — GBT discovers pass-when-weak
   without explicit encoding

### R1.6 Scope (Partner Semantics)

R1.6 extends partner features from 3 → 4 with suit-relative channels:

| Feature | Description | Replaces |
|---------|-------------|----------|
| `partner_level_same_suit` | Partner bid level when bidding same suit | `partner_bid_level` (partial) |
| `partner_level_same_color` | Partner bid level when bidding same-color offsuit | `partner_bid_level` (partial) |
| `partner_level_off_color` | Partner bid level when bidding off-color offsuit | `partner_bid_level` (partial) |
| `partner_passed` | Partner passed (unchanged) | — |

Schema: v7 (52 features) → v8 (53 features). PR #631 (artifact-driven feature
extraction) enables v7/v8 coexistence in H2H batteries.

Plan: `plans/sessions/2026-03-13_r1-6-partner-semantics.md`

## 6. Timeline (R1.5.3)

| Step | Date | Result | Report |
|------|------|--------|--------|
| Step 0 — Error taxonomy | 2026-03-11 | Boundary=28.5%, Track B selected | [suit_decision_diagnostic.md](suit_decision_diagnostic.md) |
| Step 0 — Play-policy gate | 2026-03-12 | ρ=1.0, PASS | PR #613 |
| Track B — GBT prototype | 2026-03-11 | +1.1 net_eppd, VALIDATED | [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) |
| Phase 0 — Multi-rollout (H14) | 2026-03-12 | R² +0.121, CONFIRMED | [09_multi_rollout_diagnostic.md](09_multi_rollout_diagnostic.md) |
| Phase 1A — 2×2 matrix (H15) | 2026-03-12 | Model >> labels, CONFIRMED | [10_model_label_matrix.md](10_model_label_matrix.md) |
| Two-stage OLS (H16) | 2026-03-12 | +0.124, -0.750 vs GBT, PARTIAL | [11_two_stage_evaluation.md](11_two_stage_evaluation.md) |
| GBT FULL validation | 2026-03-13 | <!-- PENDING --> | [12_gbt_full_validation.md](12_gbt_full_validation.md) |
| Promotion decision | 2026-03-13 | <!-- PENDING --> | This document |

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | <!-- PENDING --> |
| Predecessor decision | ADVANCED (R1.5 v1, 07_promotion_decision.md) |
| GBT FULL report | [12_gbt_full_validation.md](12_gbt_full_validation.md) |
| 2×2 matrix report | [10_model_label_matrix.md](10_model_label_matrix.md) |
| Two-stage report | [11_two_stage_evaluation.md](11_two_stage_evaluation.md) |
| GBT prototype report | [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) |
| Arc retrospective | [11_r1_5_arc_retrospective.md](11_r1_5_arc_retrospective.md) |
| R1.6 plan | `plans/sessions/2026-03-13_r1-6-partner-semantics.md` |
| PR #631 (schema infra) | artifact-driven feature extraction |
| Governing plan | `plans/sessions/2026-03-12_r1-5-3-forward-plan-v2.md` |
| analysis_base_sha | 1d14737 |
