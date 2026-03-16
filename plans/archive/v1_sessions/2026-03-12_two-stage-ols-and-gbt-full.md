# R1.5.3 Two-Stage OLS + GBT FULL Validation

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Parent plan:** `plans/sessions/2026-03-12_r1-5-3-forward-plan-v2.md`

## Goal

Run two parallel tracks:
- **Track A (GBT FULL):** Validate Cell C (GBT, N=1) at FULL scale (50K deals, 3 seeds)
- **Track B (Two-Stage OLS):** Test H16 — does explicit make/set decomposition close the GBT gap?

## Motivation

Phase 1A (PR #626) showed model capacity (+0.902) dwarfs label quality (-0.026) by 35x.
GBT is the clear mainline. But two-stage make/set was never actually tested, and the
declare/defend failure (R1.5.2) does NOT rule it out — different decomposition entirely.

## Track B: Two-Stage OLS (H16)

### Make/set derivation
- Formula: `made = net_points >= 2*bid_n - 10` (verified: gap >= 2 per bid_n)
- Suit make rate: 40.1% across all counterfactual actions
- E[pts|made] = +2.01, E[pts|set] = -12.85 (14.9 point gap)

### Components
1. P(make | state, bid_n) — logistic regression
2. E[net_points | make] — OLS on made subset
3. E[net_points | set] — OLS on set subset
4. Composite: P(make) * E[pts|make] + (1-P(make)) * E[pts|set]

### Files to modify
- `scripts/internal/train_action_value.py` — add two-stage training
- `src/bid_euchre/strategy/bidding.py` — add TwoStageActionValueBidder
- `src/bid_euchre/strategy/__init__.py` — export
- `src/bid_euchre/experiments/config.py` — register
- `tests/unit/test_two_stage_bidder.py` — tests

## Outcome

### Track B: Two-Stage OLS — H16 PARTIAL

**PR:** _pending_

**Training results:**
- P(make) AUC = 0.9363 (gate PASS)
- Composite suit R² = 0.5894 (vs OLS 0.565, vs GBT 0.594)
- High R² = 0.5328, Low R² = 0.5143, Pass R² = 0.0456

**H2H results (QUICK, 2K paired deals, seed 42):**

| Matchup | Symmetrized delta |
|---------|-------------------|
| Two-Stage vs OLS | **+0.124** |
| Two-Stage vs R0 | **+0.191** |
| Two-Stage vs GBT | **-0.750** |
| GBT vs R0 | **+1.075** |

**Verdict:** H16 PARTIAL — make/set decomposition helps (+0.124 vs OLS) but
closes only 11.5% of the GBT gap. Model capacity dominates decomposition strategy.

**Report:** `docs/04_reports/arc_d_v1/r1_5/11_two_stage_evaluation.md`

### Track A: GBT FULL — _not started (separate PR)_
