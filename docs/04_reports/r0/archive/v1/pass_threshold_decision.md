# Pass-Threshold Tuning Decision — B0

> **⚠ SUPERSEDED** — This is the v1 version, archived for reference.
> The current version is at [`../pass_threshold_decision.md`](../pass_threshold_decision.md).
> See [README.md](README.md) for the v1→v2 delta summary.

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-02
**Purpose:** Determine whether tuning the pass gate threshold improves R0 net-differential

## Executive Summary

**Decision: RETAIN (t=0)**

A pre-registered sweep of 11 threshold candidates (t ∈ {0.00, 0.25, ..., 5.00})
found that the current pass gate (`utility ≤ 0`) is already optimal for R0's model.
Net-differential **decreases monotonically** with higher thresholds:

| t | Train net_diff | Val net_diff | Bid Rate | Make Rate |
|---|---------------|-------------|----------|-----------|
| 0.00 | +0.2886 | +0.3360 | 19.8% | 83.9% |
| 0.25 | +0.2852 | +0.3102 | 38.1% | 79.4% |
| 0.50 | +0.2695 | +0.2487 | 52.2% | 80.0% |
| 1.00 | +0.1131 | +0.0277 | 81.6% | 78.9% |
| 2.00 | −0.1611 | −0.2440 | 97.7% | 78.4% |

**Key insight:** Despite 82% of oracle regret stemming from the pass-threshold
(PR #472), lowering it hurts R0 performance. The marginal hands admitted by a
lower threshold are ones the model predicts near-zero utility for — these hands
fail to make their contracts at disproportionate rates, generating set penalties
that exceed the gains from newly-profitable hands. The pass-threshold regret can
only be recovered through better predictions (R1+ model improvements), not
through a threshold shift on R0's model.

No code changes required. The pass gate remains `best_utility <= 0`.

## 1. Motivation

The contract selection oracle analysis (PR #472) attributed 82% of total regret
to the pass-threshold — the model passes on hands where the oracle (with perfect
hindsight) would profitably bid. This B0 sweep investigates whether shifting the
pass gate from `utility ≤ 0` to `utility ≤ -t` recovers value.

**Protocol:** `plans/r0_pass_threshold_protocol.md` v1 (pre-registered)

## 2. Methodology

- **Dataset:** `canonical_bidless_dataset_glutton_42_20260221_175752` (same as oracle)
- **Mode:** QUICK (10,000 deals → 40,000 hands)
- **Split:** 60/40 by `deal_id` hash (seed=42). Train: 23,764 hands. Val: 16,236 hands
- **Grid:** 11 candidates: {0.00, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 2.50, 3.00, 4.00, 5.00}
- **Primary endpoint:** Mean net-differential per hand on validation
- **Bootstrap:** 10,000 resamples, grouped by deal_id, seed 42
- **SESOI:** 0.05 net_diff per hand
- **Guardrails:** make_rate ≥ 60% (hard), overbid_regret ≤ 10% (hard), bid_rate ≤ 95% (soft)
- **Notebook:** `notebooks/arc_d/r0/56_pass_threshold_sweep.py`

## 3. Results

### 3.1 Train Partition Sweep

| t | net_diff | bid_rate | make_rate | pass_reg% | cs_reg% | overbid% | Guards |
|---|---------|---------|----------|-----------|---------|----------|--------|
| 0.00 | +0.2886 | 0.198 | 0.839 | 81.7% | 17.1% | 1.2% | ✓ |
| 0.25 | +0.2852 | 0.381 | 0.794 | 60.8% | 35.5% | 3.7% | ✓ |
| 0.50 | +0.2695 | 0.522 | 0.800 | 46.0% | 48.9% | 5.1% | ✓ |
| 0.75 | +0.1626 | 0.759 | 0.792 | 21.0% | 72.0% | 7.0% | ✓ |
| 1.00 | +0.1131 | 0.816 | 0.789 | 15.1% | 77.3% | 7.5% | ✓ |
| 1.50 | +0.0364 | 0.881 | 0.788 | 9.3% | 82.1% | 8.6% | ✓ |
| 2.00 | −0.1611 | 0.977 | 0.784 | 1.7% | 88.3% | 10.0% | ✗ |
| 2.50 | −0.1995 | 0.994 | 0.782 | 0.4% | 89.4% | 10.2% | ✗ |
| 3.00 | −0.2192 | 0.999 | 0.782 | 0.1% | 89.6% | 10.4% | ✗ |
| 4.00 | −0.2240 | 1.000 | 0.781 | 0.0% | 89.6% | 10.4% | ✗ |
| 5.00 | −0.2240 | 1.000 | 0.781 | 0.0% | 89.6% | 10.4% | ✗ |

**Selected t\* = 0.00** (current behavior is the best candidate on train).

### 3.2 Validation

Since t\* = 0.00 = baseline, the validation delta is exactly 0. The bootstrap CI
is [0.0000, 0.0000] — trivially fails to exclude zero.

### 3.3 Guardrails

- t ∈ {2.00, 2.50, 3.00, 4.00, 5.00} disqualified by overbid_regret > 10% (t=2.00 displays as 10.0% due to rounding; actual value exceeds threshold)
- All candidates t ≤ 1.50 pass all guardrails
- Make rate remains high (≥78%) across the entire grid — the model's bid_n
  (floor of predicted tricks) is conservative enough that make rate stays stable

## 4. Interpretation

The monotonic decline of net_diff with increasing t reveals a fundamental property
of R0's model: **the marginal hands near utility ≈ 0 are not worth bidding on
with the current prediction quality.**

The regret decomposition shows the mechanism:
- At t=0, pass-threshold regret is 82% of total (model is conservative)
- At t=1, pass-threshold regret drops to 15% but contract-selection regret
  rises to 77% — the newly-admitted hands bid on wrong contracts or get set
- The total regret *increases* despite the regret rebalancing

This means the oracle's 82% pass-threshold regret is a **model accuracy problem**,
not a **threshold calibration problem**. The model can't distinguish the subset of
currently-passed hands that would actually be profitable — they all look similar
in predicted utility space. Better features (R1) or a better model architecture
may enable profitable threshold tuning in the future.

## 5. Decision

| Criterion | Result |
|-----------|--------|
| t\* on train | 0.00 (current behavior) |
| Validation delta | +0.0000 |
| 95% CI | [+0.0000, +0.0000] |
| CI excludes 0 | No |
| SESOI (0.05) exceeded | No |
| **Decision** | **RETAIN** |

No code changes. The pass gate at `bidding.py:1043` remains `best_utility <= 0`.

## 6. Implications for Future Rungs

- **R1 re-tune:** Each rung that improves model predictions should re-run this
  protocol (or an updated v2). Better predictions may make threshold tuning viable.
- **Feature importance:** The pass-threshold regret is fundamentally about prediction
  accuracy for marginal hands. Features that improve calibration near the bid/pass
  boundary (e.g., opponent context in R2) may unlock threshold gains.
- **Protocol reuse:** The pre-registered protocol and notebook can be re-executed
  on R1 data by changing only the artifact path and dataset path.

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | RETAIN (B0 decision gate — no code change) |
| Protocol | `plans/r0_pass_threshold_protocol.md` v1 |
| Notebook | `notebooks/arc_d/r0/56_pass_threshold_sweep.py` |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Model artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| Split seed | 42 |
| Bootstrap seed | 42 |
| Mode | QUICK (10,000 deals) |
| Repro command | `PYTHONPATH=src uv run papermill notebooks/arc_d/r0/56_pass_threshold_sweep.ipynb /tmp/out.ipynb -p MODE QUICK` |
