# R1.5 Step 7: Risk Treatment — SKIP

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08
**Purpose:** Evaluate whether risk treatment is needed before FULL evaluation

## Executive Summary

Risk treatment is **skipped for v1**. The QUICK H2H battery (Step 6, PR #577)
produced a primary delta of **+0.165 net_eppd** (CI [+0.004, +0.350], excludes
zero), well above the design spec's "delta > 0.0: strong signal, proceed to
FULL" threshold. The risk-neutral v1 bidder already outperforms both R0
baselines without any pass threshold, CVaR penalty, or risk model.

**Decision:** Proceed directly to Step 8 (FULL H2H battery) with the v1
risk-neutral ActionValueBidder. Risk treatment remains available for a future
v2 iteration if FULL results warrant refinement.

## 1. Motivation

The R1.5 design spec (plans/r1_5_training_plan.md, Step 7) defines three risk
treatment options:

1. **Pass threshold:** Minimum EV gap required to bid (vs pass value)
2. **CVaR penalty:** Penalize high-variance bids using conditional tail risk
3. **Risk model:** Train a separate variance model for CVaR-weighted decisions

These were designed as potential improvements over the risk-neutral v1 baseline.
The spec's Step 6 decision tree provides a clear skip criterion: if the QUICK
delta exceeds 0.0, the signal is strong enough to proceed directly to FULL
evaluation.

## 2. Rationale for Skipping

### 2.1 Gate X4 Exceeded Skip Threshold

The QUICK H2H delta of +0.165 exceeds the spec's 0.0 threshold for proceeding
to FULL. Both rotation CIs are consistent in direction:

| Matchup | Delta | CI |
|---------|-------|----|
| AV v1 vs HO_full R0 (rotation 1) | +0.176 | [+0.004, +0.350] |
| HO_full R0 vs AV v1 (rotation 2) | -0.154 | [-0.328, +0.020] |
| **Pooled** | **+0.165** | — |

### 2.2 Behavioral Profile Already Conservative

The v1 bidder's behavioral profile suggests it is already implicitly
conservative:

- **Bid level:** All bids at level 4 (minimum legal). This is the
  lowest-risk bid available — set penalty is only -4 points.
- **Make rate:** 95.4%, comparable to R0's 96%+ despite bidding more
  aggressively. The model rarely commits to losing contracts.
- **Strategy:** "Quantity over quality" — high bid rate (56-57%) with low
  per-contract risk. This is a naturally risk-managed approach.

Adding a pass threshold would reduce the bid rate, potentially losing the
volume advantage that drives the positive delta. Adding CVaR penalty would
penalize variance in a bidder that already takes minimal variance (bid=4).

### 2.3 Risk-Neutral by Design

The v1 ActionValueBidder has no risk_lambda parameter and no sigma (variance
estimate). It uses direct argmax over predicted net_points. This is consistent
with the R1 decision (Track D: RETAIN lambda=0.0) which found that risk
aversion hurt H2H performance.

### 2.4 FULL Retraining Deferred

The design spec's Step 4 calls for repeating Steps 1-2 at FULL scale
(50k+ deals). For the v1 evaluation, FULL retraining is deferred: the
QUICK-trained models are used directly in the FULL H2H battery. The rationale
is that model decision quality was already validated at QUICK scale (Gate X4
passed), and the H2H evaluation tests gameplay outcomes, not model accuracy.
FULL retraining may be revisited in v2 if the FULL H2H results suggest model
accuracy is a limiting factor.

## 3. What Would Trigger v2 Risk Treatment

Risk treatment should be revisited if any of the following emerge from the
FULL battery (Step 8):

- **FULL delta regresses below promotion threshold** (CI_low < 0.180):
  A pass threshold might improve quality per bid at the cost of volume.
- **Contract-type regression:** If suit or high/low deltas are significantly
  negative despite positive pooled delta, targeted risk treatment by contract
  type could help.
- **High set-rate variance:** If v1's set rate shows high variance across
  seeds, CVaR penalty could stabilize performance.
- **Bid-level plateau:** If v1 is stuck at bid=4 due to model limitations,
  a calibrated threshold might enable higher bids on strong hands.

## 4. Arc Context

| Step | Status | Gate |
|------|--------|------|
| 0-2 | DONE | Infrastructure + training |
| 3 | DONE | X3 offline ranking (failed, but model has signal) |
| 5 | DONE | Self-play screen (passed) |
| 6 | DONE | X4 QUICK H2H (passed, +0.165) |
| **7** | **SKIPPED** | **Delta > 0.0, proceed to FULL** |
| 8 | NEXT | FULL H2H battery + promotion gate |
| 9 | Pending | Ablation |
| 10 | Pending | Promotion decision |

## 5. Provenance

| Item | Value |
|------|-------|
| gate_status | SKIPPED — delta > 0.0 threshold met, risk treatment not required for v1 |
| Decision basis | Step 6 results (PR #577): pooled delta +0.165, CI [+0.004, +0.350] |
| Design spec | plans/r1_5_training_plan.md, Step 7 |
| Prior report | [03_h2h_battery_quick.md](03_h2h_battery_quick.md) |
| FULL retraining | Deferred — QUICK-trained models used for FULL H2H evaluation |
