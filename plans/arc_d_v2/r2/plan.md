# Arc D v2 — R2 Rung Plan

**Status:** PROPOSED
**Lineage:** arc_d_v2
**Rung:** r2 (opponent context)

## 1. Objective

Add opponent context features (left + right) to the action-value framework.
Test whether knowing what opponents bid improves bidding decisions beyond
partner-only context (R1).

## 2. Model Roster

Same as R0/R1 — see `plans/arc_d_v2/roster.json`.

## 3. Context Bundle

R2 context: hand + partner + position + opponent.
- 39 hand features (frozen)
- 6 partner features (v2 suit-relative, from R1)
- 2 position features (LA-1: auction_position, is_dealer)
- 12 opponent features (6 left + 6 right, same template as partner)
- Total: 59 state features

## 4. Hypotheses

See `plans/arc_d_v2/r2/hypotheses.json`.

## 5. Execution

Managed by `scripts/internal/run_rung.py --rung r2`.
Per Amendment LA-3, R2 runs at QUICK scale only.

## 6. Implementation Notes

Opponent features use the same 6-feature template as partner features
(3 suit-relative channels + 2 contract-type channels + 1 pass signal),
applied independently to left opponent (seat+1) and right opponent (seat-1).

The extract_state_features() order is:
hand (39) + partner (6) + position (2) + opponent_left (6) + opponent_right (6) + positional (10)

## Outcome

_To be filled after execution._
