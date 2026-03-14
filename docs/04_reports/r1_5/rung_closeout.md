# R1.5 Rung Closeout — Objective-Alignment through Model-Architecture

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R1.5 through R1.5.3
**Decision:** PROMOTED
**gate_status:** PROMOTED — GBT AV v1 replaces hybrid_olsa_full R0 as incumbent
**Date:** 2026-03-13 (R1.5.3 PROMOTED); 2026-03-08 (R1.5 v1 ADVANCED)
**Methodology Review:** [measurement_integrity_r1_5.md](measurement_integrity_r1_5.md)

> **Naming convention:** R1.5 introduces the action-value bidder architecture.
> R1.5.3 replaces the OLS model with GBT.
>
> | Name | Referent | Artifact |
> |------|----------|----------|
> | AV v1 (OLS) | ActionValueBidder — OLS per-contract models, argmax | `action_value_full.json` |
> | **GBT AV v1** | **GBTActionValueBidder — GBT per-contract models, argmax** | **`action_value_gbt.json`** |
> | HO_full R0 | hybrid_olsa_full R0 — former incumbent | `hybrid_r0_full.json` |
> | HO R0 | hybrid_olsa R0 — former constrained arm | `hybrid_r0.json` |

## Executive Summary

R1.5 replaced the R0/R1 tricks-based prediction + Gaussian EV utility pipeline
with direct `net_points` prediction via per-contract models and argmax decision.
R1.5 v1 (OLS) showed the approach was sound (+0.152 pooled) but a structural
suit regression (-0.142) blocked promotion. R1.5.2 exhausted feature-based
fixes. R1.5.3 resolved the suit regression by replacing OLS with gradient-boosted
trees (GBT), which capture the bimodal make/set decision boundary that linear
models cannot represent.

**Definitive result (GBT FULL H2H, 3 seeds x 50,000 deals):**

| Contract | 3-Seed Mean | Range | Significant |
|----------|-------------|-------|-------------|
| **Suit** | **+0.827** | +0.818 to +0.843 | **Yes** — regression resolved |
| **High** | **+0.333** | +0.258 to +0.404 | **Yes** |
| **Low** | -0.041 | -0.089 to -0.008 | No — parity with R0 |
| **Pooled** | **+0.570** | +0.557 to +0.595 | **Yes** |

All promotion gates pass: CI_low > +0.50 (threshold: 0.180), suit delta > 0,
no seed reversals (3/3 positive). Cross-seed CV: 3.7% pooled, 1.6% suit.

**Verdict:** GBT AV v1 is PROMOTED to incumbent, replacing hybrid_olsa_full R0.

## R1.5 Arc Progression

| Sub-rung | Model | Pooled vs R0 | Suit vs R0 | Decision |
|----------|-------|-------------|------------|----------|
| **R1.5 v1** | OLS | +0.152 | **-0.142** | ADVANCED — suit regression blocks |
| **R1.5.2** | (diagnostics) | — | — | Features exhausted, bimodal target identified |
| **R1.5.3** | GBT | **+0.570** | **+0.827** | **PROMOTED** — suit resolved |

### What Each Phase Contributed

**R1.5 v1 (OLS, Mar 6-8):** Proved objective alignment works. Reversed R1's
-0.348 regression to +0.152. Unlocked high (+0.430) and low (+0.495).
Identified suit regression as sole blocker.

**R1.5.2 (diagnostics, Mar 9-10):** Six ablation experiments eliminated all
feature-based hypotheses. Partner features are critical for action selection
(not prediction). Bimodal suit target identified as structural OLS limitation.

**R1.5.3 (GBT, Mar 11-13):** GBT prototype validated at QUICK (+1.067).
2x2 model x label matrix proved model capacity >> label quality (35x).
Two-stage OLS partial (+0.124 but -0.750 vs GBT). GBT FULL validation:
+0.570 pooled, all gates pass across 3 seeds.

## What Changed (R0 to R1.5.3)

| Layer | R0 | R1.5.3 (GBT) | Impact |
|-------|-----|-------------|--------|
| **Objective** | `tricks_won` | `net_points` | Eliminates objective mismatch |
| **Decision** | Gaussian EV + sigma + risk_lambda | Argmax over GBT predictions | Eliminates H10 degeneracy |
| **Model** | Per-contract OLSa | Per-contract GBT (100 trees, depth 3) | Captures bimodal make/set boundary |
| **Features** | 39 hand features | 52-column state (hand + position + partner + action) | Richer representation |
| **Training data** | Bidless (outcome observation) | Counterfactual (forced-action rollouts) | Direct action-value labels |
| **Risk** | risk_lambda, sigma | None (risk-neutral) | Consistent with Track D RETAIN lambda=0.0 |

## Gate Results (Final — R1.5.3 GBT)

| Gate | Criterion | Result | Evidence |
|------|-----------|--------|----------|
| G1 | Pooled CI_low > 0.180 | **PASS** — CI_low > +0.50 (all seeds) | [12_gbt_full_validation.md](12_gbt_full_validation.md) |
| G2 | Suit delta > 0 | **PASS** — +0.827 (3-seed mean) | [12_gbt_full_validation.md](12_gbt_full_validation.md) |
| G3 | No seed reversals | **PASS** — 3/3 positive | [12_gbt_full_validation.md](12_gbt_full_validation.md) |

### Historical Gates (R1.5 v1 OLS)

| Gate | Result | Notes |
|------|--------|-------|
| X1-X2 | PASS | Dataset and training validated |
| X3 | Adjudicated ADVANCED | Oracle noise; robust alternatives show signal |
| X4 QUICK | PASS | +0.165 |
| X4 FULL | ADVANCED (not promoted) | CI_low +0.124 < 0.180 |

## H2H Evidence

### GBT FULL Battery (Definitive — R1.5.3)

3 seeds (42, 123, 456) x 50,000 deals x 9 matchups = 1,350,000 total hands.

**GBT vs Hybrid R0 symmetrized deltas:**

| Contract | Seed 42 | Seed 123 | Seed 456 | Mean |
|----------|---------|----------|----------|------|
| Suit | +0.843 | +0.818 | +0.819 | +0.827 |
| High | +0.404 | +0.258 | +0.336 | +0.333 |
| Low | -0.027 | -0.008 | -0.089 | -0.041 |
| Pooled | +0.595 | +0.557 | +0.558 | +0.570 |

Source: [12_gbt_full_validation.md](12_gbt_full_validation.md)

### OLS FULL Battery (Historical — R1.5 v1)

50,000 deals, seed 42, 3-bidder roster.

| Comparison | Pooled | Suit | High | Low |
|------------|--------|------|------|-----|
| OLS AV v1 vs HO_full R0 | +0.152 | -0.142 | +0.430 | +0.495 |

Source: [05_h2h_battery_full.md](05_h2h_battery_full.md)

### QUICK to FULL Shrinkage

| Model | QUICK | FULL (mean) | Shrinkage |
|-------|-------|-------------|-----------|
| OLS AV v1 | +0.165 | +0.152 | 8% |
| GBT AV v1 | +1.067 | +0.570 | 47% |

GBT's larger shrinkage reflects QUICK-trained model evaluated at FULL scale.
Despite 47% shrinkage, CI_low (+0.50+) remains 2.8x the promotion threshold.

### Behavioral Profile

| Metric | GBT AV v1 | OLS AV v1 | HO_full R0 |
|--------|-----------|-----------|------------|
| Bid rate (cross) | ~68% | ~57% | ~32% |
| Make rate (self-play) | 84.6% | 94.6% | 96.7% |
| Pass rate | ~32% | ~0% | ~5.7% |
| Self-play eppd | 4.16 | 4.82 | 4.89 |
| CVaR5 (self-play) | -6.84 | -1.80 | -0.74 |

GBT discovered selective, aggressive bidding: pass on ~32% of hands, bid
higher when bidding (avg 5.44 vs OLS's fixed 4). Both are valid strategies
discovered from data, but GBT's captures more value.

## Rung-over-Rung Progression vs R0 Full

| Metric | R1 | R1.5 v1 (OLS) | R1.5.3 (GBT) | Direction |
|--------|-----|---------------|-------------|-----------|
| Overall | -0.348 | +0.152 | **+0.570** | Steady improvement |
| Suit | -0.76 | -0.142 | **+0.827** | Regression resolved |
| High | ~0 | +0.430 | +0.333 | R1.5 unlocked, GBT stable |
| Low | ~0 | +0.495 | -0.041 | R1.5 unlocked, parity at GBT |

## Key Hypotheses Resolved

| ID | Hypothesis | Status | Rung |
|----|-----------|--------|------|
| H1 | Objective mismatch was main R1 failure | CONFIRMED | R1.5 |
| H12 | Bimodal suit target causes OLS regression | SUPPORTED | R1.5.2 |
| H15 | Model capacity >> label quality | CONFIRMED (35x) | R1.5.3 |
| H16 | Two-stage OLS closes GBT gap | PARTIAL (-0.750 behind) | R1.5.3 |

See [11_r1_5_arc_retrospective.md](11_r1_5_arc_retrospective.md) for full
hypothesis ledger (H1-H16).

## Next Steps (R1.6)

R1.6 extends partner features with suit-relative channels:

| Feature | Description |
|---------|-------------|
| `partner_level_same_suit` | Partner bid level when bidding same suit |
| `partner_level_same_color` | Partner bid level when bidding same-color offsuit |
| `partner_level_off_color` | Partner bid level when bidding off-color offsuit |
| `partner_passed` | Partner passed (unchanged) |

Schema: v7 (52 features) to v8 (53 features). PR #631 (artifact-driven feature
extraction) enables v7/v8 coexistence.
Plan: `plans/archive/v1_sessions/2026-03-13_r1-6-partner-semantics.md`

## Timeline

| Step | Date | Result | Report |
|------|------|--------|--------|
| **R1.5 v1** | | | |
| 0-2 — Infrastructure | 2026-03-06-08 | PRs #560-#567 | [00_step0_foundations.md](00_step0_foundations.md) et al. |
| 3 — Offline eval | 2026-03-07 | Adjudicated ADVANCED | [01_offline_gate_x3_report.md](01_offline_gate_x3_report.md) |
| 5-8 — H2H batteries | 2026-03-08 | +0.152 (ADVANCED) | [05_h2h_battery_full.md](05_h2h_battery_full.md) |
| 10 — Promotion decision | 2026-03-08 | ADVANCED | [07_promotion_decision.md](07_promotion_decision.md) |
| **R1.5.2** | | | |
| Ablation campaign | 2026-03-09-10 | Features exhausted | [v2_ablation_analysis.md](v2_ablation_analysis.md) |
| **R1.5.3** | | | |
| Error taxonomy | 2026-03-11 | Boundary=28.5% | [suit_decision_diagnostic.md](suit_decision_diagnostic.md) |
| GBT prototype | 2026-03-11 | +1.067 QUICK | [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) |
| 2x2 matrix (H15) | 2026-03-12 | Model >> labels | [10_model_label_matrix.md](10_model_label_matrix.md) |
| Two-stage (H16) | 2026-03-12 | PARTIAL | [11_two_stage_evaluation.md](11_two_stage_evaluation.md) |
| GBT FULL validation | 2026-03-13 | All gates PASS | [12_gbt_full_validation.md](12_gbt_full_validation.md) |
| **Promotion decision** | **2026-03-13** | **PROMOTED** | [13_r1_5_3_promotion_decision.md](13_r1_5_3_promotion_decision.md) |

## Artifact Manifest

| Artifact | Path |
|----------|------|
| **GBT AV v1 model (incumbent)** | **`data/artifacts/arc_d/r1_5/action_value_gbt.json`** |
| OLS AV v1 model (historical) | `data/artifacts/arc_d/r1_5/action_value_full.json` |
| GBT FULL battery config | `data/runs/gbt_full_validation/h2h_battery_full_config.yaml` |
| OLS FULL H2H battery | `data/artifacts/arc_d/r1_5/h2h_battery_full.json` |
| Dataset generator | `scripts/internal/generate_action_value_dataset.py` |
| Training pipeline | `scripts/internal/train_action_value.py` |
| Governing plan | `plans/archive/v1_root/r1_5_training_plan.md` |
| R1.5.3 plan | `plans/archive/v1_sessions/2026-03-12_r1-5-3-forward-plan-v2.md` |

## Companion Reports

### R1.5.3 (Promotion)
- [13_r1_5_3_promotion_decision.md](13_r1_5_3_promotion_decision.md) — **Promotion decision — PROMOTED**
- [12_gbt_full_validation.md](12_gbt_full_validation.md) — GBT FULL H2H (3-seed, definitive)
- [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) — GBT prototype (QUICK)
- [10_model_label_matrix.md](10_model_label_matrix.md) — H15: model >> labels (2x2 matrix)
- [11_two_stage_evaluation.md](11_two_stage_evaluation.md) — H16: two-stage OLS (PARTIAL)
- [11_r1_5_arc_retrospective.md](11_r1_5_arc_retrospective.md) — Full arc retrospective

### R1.5 v1 (ADVANCED — historical)
- [07_promotion_decision.md](07_promotion_decision.md) — OLS promotion decision — ADVANCED
- [05_h2h_battery_full.md](05_h2h_battery_full.md) — OLS FULL H2H
- [06_ablation.md](06_ablation.md) — Per-contract attribution
- [v2_ablation_analysis.md](v2_ablation_analysis.md) — R1.5.2 diagnostic campaign

### Methodology
- [measurement_integrity_r1_5.md](measurement_integrity_r1_5.md) — Full methodology review

## Provenance

| Item | Value |
|------|-------|
| gate_status | PROMOTED — all 3 gates pass, +0.570 pooled net_eppd (3-seed) |
| New incumbent | GBT AV v1 (`action_value_gbt.json`, SHA `9dd2bfca704fa7f3c6071ea925fd5abe7a1260b752f884648edbb30592773a1f`) |
| Former incumbent | hybrid_olsa_full R0 (`hybrid_r0_full.json`, SHA `5436b759f525466976244766dee8d98472dcfe243ac1d4542885e6cd0e6dcbc7`) |
| Gate thresholds | delta_floor=0.180, regression=-0.184 (from R0 calibration) |
| Eval seeds | 42, 123, 456 |
| FULL n_per | 50,000 per matchup per seed |
| Total hands evaluated | 1,350,000 |
| analysis_base_sha | b53d31b |
| R1 closeout | `docs/04_reports/r1/01_r1_outcome_summary.md` |
| R0 promotion | `docs/04_reports/r0/01_r0_promotion_report.md` |
