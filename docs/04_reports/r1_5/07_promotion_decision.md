# R1.5 Step 10: Promotion Decision

> For the canonical rung summary, see [rung_closeout.md](rung_closeout.md).

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08

## Decision: ADVANCED

ActionValueBidder v1 is **ADVANCED** to R1.5-v2 development. It is not promoted
to incumbent status.

## 1. Gate Summary

| Gate | Result | Evidence |
|------|--------|----------|
| X1 (dataset) | PASS | 2,000+ deals generated, schema validated |
| X2 (training) | PASS | QUICK: Suit R²=0.565, High=0.533, Low=0.514, Pass=0.046 (SMOKE was higher; QUICK is canonical) |
| X3 (offline ranking) | ADJUDICATED ADVANCED | Top-1 accuracy below threshold due to oracle noise |
| X4 (QUICK H2H) | PASS | +0.165 net_eppd, delta > -0.10 |
| X4 (FULL H2H) | **ADVANCED** | +0.152 net_eppd, CI [+0.124, +0.180] |
| Promotion gate | **FAIL** | CI_low +0.124 < delta floor 0.180 |

### Per-Contract-Type Promotion Blockers

| Contract | Delta | CI | Promotion Blocker? |
|----------|-------|-----|-------------------|
| Suit | -0.142 | [-0.180, -0.105] | **Yes** — regression; primary obstacle |
| High | +0.430 | [+0.359, +0.501] | No — large gain |
| Low | +0.495 | [+0.444, +0.546] | No — large gain |

The suit regression alone accounts for the gap between the pooled delta (+0.152)
and the promotion threshold (0.180).

## 2. Rationale

### What Worked

1. **Objective alignment validated.** Direct net_points prediction bypasses the
   R0/R1 decision-layer bottleneck (Gaussian EV utility). The R1 closeout
   diagnosis — that the objective mismatch was the primary issue — is confirmed.

2. **Strong no-trump performance.** High (+0.430) and low (+0.495) contract
   deltas are large and significant. The OLS action-value model captures
   decision structure well for these simpler contract types.

3. **Behavioral stability.** QUICK→FULL point estimate shrinkage is only 8%
   (+0.165 → +0.152). Behavioral metrics (56-57% bid rate, ~95% make rate)
   are stable across scales.

4. **Quantity-over-quality strategy emerges.** V1 independently discovers a
   valid strategy of bidding frequently at minimum level (bid=4) rather than
   being selective. This is a genuine strategic innovation from the data, not
   a hand-coded heuristic.

### What Blocked Promotion

1. **Suit regression (-0.142).** The single largest deficit. Suit contracts
   involve bower interactions and trump effects that create non-linearities
   the OLS model cannot capture. This regression alone accounts for the gap
   between the observed delta (+0.152) and the promotion threshold (0.180).

2. **CI_low below threshold.** Even if the point estimate were higher, the
   CI width at FULL scale means CI_low (+0.124) cannot clear 0.180. Promotion
   would require both reducing the suit deficit and potentially increasing
   sample size.

## 3. Decision Outcomes

| Outcome | Criteria | Status |
|---------|----------|--------|
| ~~PROMOTED~~ | CI_low > 0.180 vs R0 best | Not met |
| **ADVANCED** | CI_low > -0.10, point estimate > 0 | **Met** |
| ~~HALT~~ | Fundamental issues with approach | Not applicable |

**ADVANCED** means:
- v1 remains available for further development (v2)
- R0 hybrid_olsa_full remains the incumbent bidder
- The action-value approach is validated as promising

## 4. Recommended Next Steps (R1.5-v2)

### Priority 1: Suit-Contract Improvement

The -0.142 suit deficit is the critical blocker. Options:

1. **Non-linear suit model:** Replace OLS with piecewise linear or interaction
   terms for suit contracts (bower × trump features)
2. **Hybrid routing:** Use AV v1 for high/low decisions, R0 HybridOLSa for
   suit contracts — directly eliminates the regression
3. **Contract-conditional features:** Add suit-specific features (bower count,
   trump length, partner trump signals) to the action-value model

### Priority 2: Risk Treatment (deferred from Step 7)

If the suit deficit is resolved, revisit risk treatment:
- Pass threshold for marginal hands
- CVaR penalty for high-variance bids

### Priority 3: FULL Retraining

Retrain action-value models on FULL dataset (50k deals) to reduce
variance in predictions. Currently using QUICK-trained models.

## 5. R1.5 Timeline Summary

| Step | Date | Result |
|------|------|--------|
| 0 — Foundations | 2026-03-06 | PR #560 |
| 1 — Dataset generator | 2026-03-06 | PRs #564, #565 |
| 2 — Training pipeline | 2026-03-08 | PR #567 |
| 3 — Offline eval (X3) | 2026-03-07 | PR #572 (adjudicated) |
| 5 — Gameplay screen | 2026-03-08 | PR #576 |
| 6 — H2H QUICK (X4) | 2026-03-08 | PR #577 (+0.165) |
| 7 — Risk treatment | 2026-03-08 | SKIPPED |
| 8 — H2H FULL | 2026-03-08 | +0.152 (ADVANCED) |
| 9 — Ablation | 2026-03-08 | Suit regression confirmed |
| 10 — Promotion decision | 2026-03-08 | **ADVANCED** |

## 6. Provenance

| Item | Value |
|------|-------|
| gate_status | ADVANCED — v1 shows significant improvement, below promotion threshold |
| FULL H2H report | [05_h2h_battery_full.md](05_h2h_battery_full.md) |
| Ablation report | [06_ablation.md](06_ablation.md) |
| QUICK H2H report | [03_h2h_battery_quick.md](03_h2h_battery_quick.md) |
| Risk treatment | [04_risk_treatment.md](04_risk_treatment.md) — SKIPPED |
| Governing plan | `plans/archive/v1_root/r1_5_training_plan.md` |
| analysis_base_sha | c15f7dd |
