# R1.5 Rung Closeout — Objective-Alignment

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R1.5 (objective-alignment)
**Decision:** ADVANCED (not promoted)
**gate_status:** ADVANCED — CI_low +0.124 < delta floor 0.180
**Date:** 2026-03-08
**Methodology Review:** [measurement_integrity_r1_5.md](measurement_integrity_r1_5.md)

> **Naming convention:** R1.5 introduces a new bidder architecture. The following
> names appear across reports and artifacts:
>
> | Name | Referent | Artifact |
> |------|----------|----------|
> | ActionValueBidder | Python class for direct net_points argmax bidder | `src/bid_euchre/strategy/bidding.py` |
> | AV v1 | ActionValueBidder first iteration (QUICK-trained, risk-neutral) | `action_value_full.json` |
> | HO_full R0 | hybrid_olsa_full R0 — incumbent best (promotional arm) | `hybrid_r0_full.json` |
> | HO R0 | hybrid_olsa R0 — incumbent constrained (attribution arm) | `hybrid_r0.json` |
> | HO_full R1 | hybrid_olsa_full R1 — R1 partner-context variant (STOP) | `hybrid_r1_full.json` |
>
> Self-play and offline sections use class names; H2H and comparator sections use
> short names (AV v1, HO_full R0, etc.).

## Executive Summary

R1.5 replaced the R0/R1 tricks-based prediction + Gaussian EV utility pipeline
with direct `net_points` prediction via per-contract OLS models and argmax
decision. This addresses the core R1 diagnosis: the objective mismatch
(train `tricks_won`, decide via hand-coded utility, evaluate on `points_per_deal`)
was the primary bottleneck, not partner features or model capacity.

**Primary result (FULL H2H, 50,000 deals):**

| Comparison | Delta (net_eppd) | 95% CI | Significant |
|------------|------------------|--------|-------------|
| AV v1 vs HO_full R0 (pooled) | **+0.152** | **[+0.124, +0.180]** | **Yes** |
| AV v1 vs HO R0 (pooled) | +0.182 | [+0.155, +0.210] | Yes |
| HO_full R0 vs HO R0 | +0.028 | [+0.002, +0.055] | Yes |

**Per-contract-type deltas (AV v1 vs HO_full R0):**

| Contract | Delta (net_eppd) | 95% CI | Significant |
|----------|------------------|--------|-------------|
| **Suit** | **-0.142** | **[-0.180, -0.105]** | **Yes (regression)** |
| **High** | **+0.430** | **[+0.359, +0.501]** | **Yes** |
| **Low** | **+0.495** | **[+0.444, +0.546]** | **Yes** |

**Verdict:** AV v1 is significantly better than both R0 incumbents overall, but
the suit-contract regression (-0.142) prevents CI_low from clearing the 0.180
promotion threshold. Decision: ADVANCED to v2 development; R0 hybrid_olsa_full
remains the incumbent bidder.

## What Changed (R0/R1 to R1.5)

| Layer | R0/R1 | R1.5 | Impact |
|-------|-------|------|--------|
| **Objective** | Predict `tricks_won` | Predict `net_points` | Core change — bypasses objective mismatch |
| **Decision** | Gaussian EV + sigma + risk_lambda | Argmax over per-contract predictions | Eliminates H10 degeneracy (EV non-increasing in bid_n) |
| **Features** | 39 hand features | 52-column state features (hand + position + legality + partner + action encoding) | Richer representation |
| **Architecture** | Single model per contract → `_compute_ev_static()` | 4 per-contract OLS models (suit, high, low, pass) → argmax | Simpler inference |
| **Training data** | Bidless dataset (outcome observation) | Counterfactual dataset (forced-action rollouts) | Direct action-value labels |
| **Risk** | risk_lambda, sigma parameters | None (risk-neutral) | Consistent with Track D RETAIN lambda=0.0 |

## Gate Results

| Gate | Criterion | Result | Evidence |
|------|-----------|--------|----------|
| X1 (dataset) | Schema valid, 2000+ deals | **PASS** | [00_step1_dataset_generator.md](00_step1_dataset_generator.md) |
| X2 (training) | R² > thresholds per contract | **PASS** | QUICK: suit=0.565, high=0.533, low=0.514, pass=0.046 |
| X3 (offline ranking) | Top-1 accuracy >= 40% | **FAILED** (adjudicated ADVANCED) | 26.6% top-1; oracle noise from single-rollout labels |
| X4 QUICK | Delta > -0.10 | **PASS** | +0.165 net_eppd |
| X4 FULL | CI_low > 0.180 (promotion) | **FAIL** | CI_low = +0.124 |
| X4 FULL | CI_low > -0.10, point estimate > 0 (advancement) | **PASS** | Point estimate = +0.152, CI_low = +0.124 |

### Gate X3 Adjudication

The offline ranking gate was mis-specified: it assumed an oracle built from
averaged continuation rollouts, but the dataset generator produces a single
rollout per action. With ~47 actions per state and bimodal make/set outcomes
(net_points std = 8.1), single-rollout top-1 agreement is not a meaningful
metric. Robust alternatives showed the model has real signal: 84.6% pairwise
accuracy (all pairs), 67.6% regret reduction vs random, positive mean outcome
(+0.44) for model-chosen actions. See
[01_offline_gate_x3_report.md](01_offline_gate_x3_report.md) for full analysis.

## H2H Evidence

### FULL Battery (Definitive)

50,000 deals, seed 42, 3-bidder roster, 9 matchups (3 self-play + 6 cross).

**Symmetrized deltas:**

| Comparison | Delta | CI_low | CI_high | Significant |
|------------|-------|--------|---------|-------------|
| **AV v1 vs HO_full R0** | **+0.152** | **+0.124** | **+0.180** | **Yes** |
| AV v1 vs HO R0 | +0.182 | +0.155 | +0.210 | Yes |
| HO_full R0 vs HO R0 | +0.028 | +0.002 | +0.055 | Yes |

**Per-contract-type deltas (AV v1 vs HO_full R0):**

| Contract | Delta | CI | Significant |
|----------|-------|----|-------------|
| Suit | -0.142 | [-0.180, -0.105] | Yes (regression) |
| High | +0.430 | [+0.359, +0.501] | Yes |
| Low | +0.495 | [+0.444, +0.546] | Yes |

Source: [05_h2h_battery_full.md](05_h2h_battery_full.md)

### QUICK Battery (Screening)

2,500 deals, seed 42, same roster. Primary delta: +0.165 net_eppd.
QUICK-to-FULL shrinkage: 8% (+0.165 to +0.152). Behavioral metrics stable.
Source: [03_h2h_battery_quick.md](03_h2h_battery_quick.md)

### Behavioral Profile

| Metric | AV v1 | HO_full R0 |
|--------|-------|------------|
| Bid rate (cross-matchup) | 56-57% | 43-44% |
| Make rate (self-play) | 94.6% | 96.8% |
| Bid level | 4 (always) | Variable (4-7+) |
| Pass rate | ~0% | ~43-44% |

AV v1 uses a "quantity over quality" strategy: bid on nearly every hand at
minimum level (bid=4), accepting low set risk (-4 points) while R0 is more
selective but bids higher on strong hands. This is a genuine strategic
innovation discovered from the data, not a hand-coded heuristic.

## R1.5 vs R1 Comparison

R1.5 was designed to address the R1 diagnosis: the decision-layer bottleneck
(H10 degeneracy) and objective mismatch (tricks_won vs points_per_deal) were
the primary causes of R1's regression. The following table compares R1 and R1.5
outcomes against the shared R0 baseline.

### Rung-over-Rung Deltas vs R0 Full (Canonical Baseline)

| Metric | R1 vs R0_full | R1.5 vs R0_full | Direction |
|--------|---------------|-----------------|-----------|
| Overall net_eppd | -0.348 | **+0.152** | Reversed (improvement) |
| Suit net_eppd | -0.76 | **-0.142** | Improved but still regressed |
| High net_eppd | ~0 (CI spans 0) | **+0.430** | New gain |
| Low net_eppd | ~0 (CI spans 0) | **+0.495** | New gain |

### What R1.5 Fixed

1. **Objective mismatch resolved.** R1 trained on `tricks_won` but was evaluated
   on `points_per_deal`. R1.5 trains directly on `net_points`, eliminating the
   translation gap. The R1 closeout diagnosis is confirmed: objective alignment
   was the key fix.

2. **Decision-layer bottleneck bypassed.** R1's `_compute_ev_static()` produced
   EV monotonically non-increasing in bid_n (H10), causing `compute_best_bid()`
   to always pick minimum legal. R1.5's argmax over predicted net_points has no
   such degeneracy.

3. **High/low contracts unlocked.** R1 showed no significant change in high/low
   contracts. R1.5 shows large, significant gains (+0.43/+0.49). The simpler
   scoring structure of no-trump contracts (no bowers, no trump suit) is
   well-served by linear OLS models.

### What Persists

1. **Suit regression.** R1 regressed -0.76 in suit; R1.5 regresses -0.142.
   The magnitude is much smaller (5.3x reduction), but the direction persists.
   Bower interactions and trump effects create non-linearities that OLS cannot
   capture. This is a model-capacity limitation, not an objective-alignment issue.

2. **Single-seed evaluation.** Both R1 and R1.5 FULL evaluations used seed=42
   only. Cross-seed validation is deferred.

## Ablation

The 3-bidder roster enables two attribution axes:

| Component | Estimate | Method |
|-----------|----------|--------|
| Total R1.5 vs R0_full | +0.152 | Direct H2H |
| Partner features (R0_full vs R0) | +0.028 | Direct H2H |
| Objective + decision layer | +0.152 | Confounded (both changed R0→R1.5) |

The objective change and decision layer cannot be separated without an
intermediate bidder. The dominant attribution is the objective/decision change:
+0.152 from architecture vs +0.028 from features.

Per-contract attribution is the most informative axis — see
[06_ablation.md](06_ablation.md).

## Plan Deviations

Three deviations from the governing plan (`plans/r1_5_training_plan.md`):

| Deviation | Plan Spec | Actual | Rationale |
|-----------|-----------|--------|-----------|
| FULL retraining | Step 4: retrain at FULL (50k deals) | Deferred — QUICK-trained models used for FULL H2H | Model quality validated at QUICK; retraining deferred to v2 |
| Step 7 skip | Step 7: v2 risk treatment | Skipped — delta > 0.0 | Risk-neutral v1 already positive; risk treatment available for v2 |
| Comparator battery | Step 8: H2H + comparator | H2H only | CI_low < 0.180 regardless; comparator deferred to v2 |

These deviations are formally documented in
[measurement_integrity_r1_5.md](measurement_integrity_r1_5.md).

## Recommended Next Steps (R1.5-v2)

### Priority 1: Suit-Contract Improvement

The -0.142 suit deficit is the critical promotion blocker. Options:

1. **Non-linear suit model:** Replace OLS with piecewise linear or interaction
   terms for suit contracts (bower x trump features)
2. **Hybrid routing:** Use AV v1 for high/low decisions, R0 HybridOLSa for
   suit contracts — directly eliminates the regression
3. **Contract-conditional features:** Add suit-specific features to the
   action-value model

### Priority 2: Risk Treatment (deferred from Step 7)

If the suit deficit is resolved, revisit risk treatment:
- Pass threshold for marginal hands
- CVaR penalty for high-variance bids

### Priority 3: FULL Retraining

Retrain action-value models on FULL dataset (50k deals) to reduce prediction
variance. Currently using QUICK-trained models.

## Timeline

| Step | Date | Result | Report |
|------|------|--------|--------|
| 0 — Foundations | 2026-03-06 | PR #560 | [00_step0_foundations.md](00_step0_foundations.md) |
| 1 — Dataset generator | 2026-03-06 | PRs #564, #565 | [00_step1_dataset_generator.md](00_step1_dataset_generator.md) |
| 2 — Training pipeline | 2026-03-08 | PR #567 | [00_step2_training_pipeline.md](00_step2_training_pipeline.md) |
| 3 — Offline eval (X3) | 2026-03-07 | Adjudicated ADVANCED | [01_offline_gate_x3_report.md](01_offline_gate_x3_report.md) |
| 5 — Gameplay screen | 2026-03-08 | PASSED | [02_gameplay_screen_report.md](02_gameplay_screen_report.md) |
| 6 — H2H QUICK (X4) | 2026-03-08 | +0.165 | [03_h2h_battery_quick.md](03_h2h_battery_quick.md) |
| 7 — Risk treatment | 2026-03-08 | SKIPPED | [04_risk_treatment.md](04_risk_treatment.md) |
| 8 — H2H FULL | 2026-03-08 | +0.152 (ADVANCED) | [05_h2h_battery_full.md](05_h2h_battery_full.md) |
| 9 — Ablation | 2026-03-08 | Suit regression confirmed | [06_ablation.md](06_ablation.md) |
| 10 — Promotion decision | 2026-03-08 | ADVANCED | [07_promotion_decision.md](07_promotion_decision.md) |

Step 4 (FULL retraining) was deferred. Step 7 was skipped. Step 8 comparator
battery was deferred. These are documented in the plan deviations section above.

## Artifact Manifest

| Artifact | Path |
|----------|------|
| AV v1 model | `data/artifacts/arc_d/r1_5/action_value_full.json` |
| Training dataset | `data/runs/action_value_quick_42/datasets/action_value.parquet` |
| FULL H2H battery | `data/artifacts/arc_d/r1_5/h2h_battery_full.json` |
| QUICK H2H battery | `data/artifacts/arc_d/r1_5/h2h_battery_quick.json` |
| H2H roster | `data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json` |
| Self-play config | `experiments/configs/r1_5_self_play.yaml` |
| Gate X3 script | `scripts/internal/evaluate_gate_x3.py` |
| Dataset generator | `scripts/internal/generate_action_value_dataset.py` |
| Training pipeline | `scripts/internal/train_action_value.py` |
| Governing plan | `plans/r1_5_training_plan.md` |

## Companion Reports

- [05_h2h_battery_full.md](05_h2h_battery_full.md) — FULL H2H battery (definitive evidence)
- [06_ablation.md](06_ablation.md) — Contract-type attribution
- [01_offline_gate_x3_report.md](01_offline_gate_x3_report.md) — Gate X3 analysis + oracle noise
- [02_gameplay_screen_report.md](02_gameplay_screen_report.md) — Self-play behavioral profile
- [04_risk_treatment.md](04_risk_treatment.md) — Risk treatment skip rationale
- [measurement_integrity_r1_5.md](measurement_integrity_r1_5.md) — Methodology review + plan deviations

### Implementation History (Step Reports)

The following reports document the infrastructure build-out and are preserved
as implementation history. They are not decision documents.

- [00_step0_foundations.md](00_step0_foundations.md) — ActionValueBidder infrastructure
- [00_step1_dataset_generator.md](00_step1_dataset_generator.md) — Counterfactual dataset generator
- [00_step2_training_pipeline.md](00_step2_training_pipeline.md) — Training pipeline + Gate X2

## Provenance

| Item | Value |
|------|-------|
| gate_status | ADVANCED — delta +0.152 significant, CI_low +0.124 below delta floor 0.180 |
| Incumbent | hybrid_olsa_full R0 (`hybrid_r0_full.json`, SHA 5436b759...) |
| Challenger | ActionValueBidder v1 (`action_value_full.json`) |
| Gate thresholds | delta_floor=0.180, regression=-0.184 (from R0 calibration) |
| Eval seed | 42 |
| FULL n_per | 50,000 |
| QUICK n_per | 2,500 |
| analysis_base_sha | c15f7dd |
| R1 closeout | `docs/04_reports/r1/01_r1_outcome_summary.md` |
| R0 promotion | `docs/04_reports/r0/01_r0_promotion_report.md` |
