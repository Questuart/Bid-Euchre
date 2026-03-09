# R1.5 Step 1: Counterfactual Dataset Generator

> **Implementation history.** This is a step-level implementation record, not a
> decision document. For the canonical rung summary, see
> [rung_closeout.md](rung_closeout.md).

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-07
**PRs:** #564 (generator), #565 (engine alignment fixes)
**Gate:** X1 (dataset sanity)

## Summary

Built the counterfactual action-value dataset generator that produces training
labels for the `ActionValueBidder`. For each (deal, focal_seat), the generator
enumerates all legal bidding actions, forces each one, completes the auction
with a continuation policy, plays out tricks, and records `net_points`.

## Script

`scripts/internal/generate_action_value_dataset.py`

### CLI

```bash
uv run python scripts/internal/generate_action_value_dataset.py \
    --seed 42 --mode QUICK \
    --output-dir data/runs/action_value_quick_42/datasets
```

### Modes

| Mode | Deals | Est. Rows | Purpose |
|------|-------|-----------|---------|
| SMOKE | 30 | ~5k | CI/test validation |
| QUICK | 2,500 | ~470k | Rapid iteration |
| FULL | 50,000 | ~9.4M | Production training |

## Gate X1: Dataset Sanity

**Status:** PASS (SMOKE validated during PR, QUICK validated at Step 2)

| Check | SMOKE Result | QUICK Result |
|-------|-------------|--------------|
| Row count | ~4,800 (30 deals x 4 seats x ~40 actions) | ~473,440 |
| Contract families | All 4 present (suit, high, low, pass) | All 4 present |
| net_points range | [-17, +11] | [-17, +11] |
| Pass coverage | 1 per (deal, focal_seat) | 1 per (deal, focal_seat) |
| NaN check | None | None |

## Key Design Details

1. **Single rollout per action:** Each (deal, focal_seat, action) gets ONE
   continuation rollout. The design spec assumed averaged rollouts but the
   implementation produces one. This creates oracle noise — see Gate X3 report
   (`01_offline_gate_x3_report.md`) for analysis.

2. **Continuation policy:** Uses `HybridOLSaBidder` (R0 full artifact) for
   remaining auction seats after the forced action. Play policy is
   `GluttonStrategy` for all seats.

3. **Engine alignment fixes (PR #565):** Fixed dealer rotation and auction
   lifecycle to match the canonical game engine. 26 unit tests added.

## Provenance

| Item | Value |
|------|-------|
| gate_status | PASSED (Gate X1 — dataset sanity) |
| PRs | #564, #565 |
| Merged | 2026-03-07 |
| Continuation artifact | `data/artifacts/arc_d/r0/hybrid_r0_full.json` |
