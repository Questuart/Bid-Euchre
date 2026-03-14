# Arc D v2 — R0 Rung Plan

**Status:** DRAFT
**Lineage:** arc_d_v2
**Rung:** r0 (baseline regeneration)

## 1. Objective

Regenerate the R0 baseline under the new canonical lineage contract.
All models in the roster receive the same hand-only context bundle
and are evaluated with identical methodology.

## 2. Model Roster

See `plans/arc_d_v2/roster.json` for the canonical roster.

## 3. Context Bundle

R0 context: hand-only (39 hand features + 13 bid/state features = 52 state features).
No partner or opponent context at R0.

## 4. Hypotheses

See `plans/arc_d_v2/r0/hypotheses.json` for the machine-readable hypothesis set.

## 5. Execution

Managed by `scripts/internal/run_rung.py --rung r0`.

## Outcome

_To be filled after execution._
