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

- [ ] R1 features not yet implemented — blocks Steps 1-9

## Session Log

### 2026-03-15 — Plan creation

- Created R1 plan, hypotheses, checkpoints
- R0 QUICK results provide baseline for comparison:
  - GBT pooled H2H: +1.061, suit: +0.876, high: +1.868, low: +1.337
  - GBT suit R²: 0.588
  - GBT comparator: 2.201
  - Best comparator: full_ols_av 2.236
