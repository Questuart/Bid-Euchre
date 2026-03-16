# R1 Checkpoints

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Phase/Rung:** R1 (partner + position context)
**Last updated:** 2026-03-15 — initial creation

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Plan & Hypothesize | COMPLETE | 2026-03-15 | Plan creation | 9 hypotheses, plan.md, checkpoints.md |
| Step 1: Generate Training Data | PENDING | -- | -- | |
| Step 2: Train All Roster Models | PENDING | -- | -- | |
| Step 3: Offline Evaluation + Data Sanity | PENDING | -- | -- | |
| Step 3b: Model Interpretability | PENDING | -- | -- | |
| Step 4: H2H Battery | PENDING | -- | -- | |
| Step 5: Comparator Battery | PENDING | -- | -- | |
| Step 6: Sanity Bounds Check | PENDING | -- | -- | |
| Step 7: Generate Reports | PENDING | -- | -- | |
| Step 8: Advance Decision + Narrative | PENDING | -- | -- | |
| Step 9: Archive & Advance | PENDING | -- | -- | |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

## Prerequisites

- [x] R0 QUICK canonical — 8/9 hypotheses PASS (H8 FAIL expected)
- [ ] R1 feature implementation — partner v2 features + position features (LA-1)

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|

## Blockers

- [x] R1 features not yet implemented — RESOLVED (PR #694)

## Advance Decision Override

**Decision:** `INVESTIGATE` (H7 surprise: GBT win rate 44.0% vs anchor, below 45% threshold)

**Human override:** PROCEED to R2 (approved 2026-03-15)

**Rationale:** The H7 surprise is explained by the anchor's feature asymmetry, not
a model deficiency. The R0 anchor (`hybrid_r0_full`) uses legacy hand-only features
(39). R1 models trained with partner+position features (47 state) bid differently —
they coordinate with partners and adjust for auction position. But this coordination
provides no competitive advantage against an opponent that doesn't use the same
information. The suit R² improvement (+0.033, from 0.588 to 0.621) confirms partner
features add real predictive signal. The H2H regression is a measurement artifact of
evaluating against a feature-asymmetric opponent, not evidence that partner context hurts.

**Per LA-3 reversal condition:** This does not trigger revert to FULL because the
surprise has a clear causal explanation and is not ambiguous.

## Session Log

### 2026-03-15 — Plan creation

- Created R1 plan, hypotheses, checkpoints
- R0 QUICK results provide baseline for comparison:
  - GBT pooled H2H: +1.061, suit: +0.876, high: +1.868, low: +1.337
  - GBT suit R²: 0.588
  - GBT comparator: 2.201
  - Best comparator: full_ols_av 2.236

### 2026-03-15 — QUICK execution + override

- R1 QUICK completed: 7/9 PASS (H2 FAIL suit delta, H7 SURPRISE 44% win rate)
- GBT: +0.490 H2H, 0.621 suit R² (+0.033 vs R0), 2.114 comparator
- Human override: PROCEED to R2 — H7 surprise explained by anchor feature asymmetry
- R2 results subsequently confirmed the diagnosis: opponent features restored H2H
  to +1.302 and 57.2% win rate, exceeding R0
