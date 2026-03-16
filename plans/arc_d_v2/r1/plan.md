# Arc D v2 — R1 Rung Plan

**Status:** PROPOSED
**Lineage:** arc_d_v2
**Rung:** r1 (partner + position context)

## 1. Objective

Add partner context and auction position features to the action-value framework.
Test whether partner information improves bidding decisions beyond hand-only (R0).

## 2. Model Roster

Same as R0 — see `plans/arc_d_v2/roster.json`. All 8 models (5 trainable + 3
heuristic/legacy) retrained with R1 context features.

## 3. Context Bundle

R1 context: hand + partner + position.
- 39 hand features (frozen, same as R0)
- 6 partner features (v2 suit-relative channels):
  `partner_level_same_suit`, `partner_level_same_color`,
  `partner_level_off_color`, `partner_level_high`,
  `partner_level_low`, `partner_passed`
- 2 position features (Amendment LA-1):
  `auction_position`, `is_dealer`
- Total: 47 state features (excluding 10 positional/legality dummies)

## 4. Hypotheses

See `plans/arc_d_v2/r1/hypotheses.json` for the machine-readable hypothesis set.

## 5. Execution

Managed by `scripts/internal/run_rung.py --rung r1`.

Per Amendment LA-3 (Hybrid Path), R1 runs at QUICK scale only.
FULL deferred until R0-R2 QUICK results are reviewed.

## 6. Implementation Notes

Partner features v2 replace the legacy v7 partner features (3 features →
6 features). The v2 features use suit-relative channels that encode the
relationship between the partner's bid suit and the observer's best suit:
- same_suit: shared right bower (strongest coordination signal)
- same_color: left bower overlap
- off_color: no bower connection
- high/low: no-trump bids (different strategic meaning)

Position features provide auction order information that disambiguates
"partner hasn't bid yet" from "partner passed."

## Outcome

_To be filled after execution._
