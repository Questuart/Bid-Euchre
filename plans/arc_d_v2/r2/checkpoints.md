# R2 Checkpoints

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Phase/Rung:** R2 (opponent context)
**Last updated:** 2026-03-15 — initial creation

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Plan & Hypothesize | COMPLETE | 2026-03-15 | Plan creation | 9 hypotheses |
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

## Prerequisites

- [x] R0 QUICK canonical — 8/9 PASS
- [x] R1 QUICK canonical — 7/9 PASS (H2 FAIL, H7 SURPRISE)
- [ ] R2 opponent features implemented

## Blockers

- [ ] R2 features not yet implemented — blocks Steps 1-9

## Session Log

### 2026-03-15 — Plan creation

- R0 baselines: GBT +1.061 H2H, 0.588 suit R², 2.201 comparator, 53.2% win rate
- R1 baselines: GBT +0.490 H2H, 0.621 suit R², 2.114 comparator, 44.0% win rate
- R1 finding: partner features improve R² but reduce H2H vs hand-only anchor
