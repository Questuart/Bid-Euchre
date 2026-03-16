# R3 Checkpoints

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Phase/Rung:** R3 (moon/loner action space expansion)
**Last updated:** 2026-03-15 by plan creation session

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Plan & Hypothesize | COMPLETE | 2026-03-15 | Plan creation | 9 hypotheses |
| Step 1: Generate Training Data | PENDING | | | `--include-moon-loner` flag required |
| Step 2: Train All Roster Models | PENDING | | | 59 state + 4 action features |
| Step 3: Offline Evaluation + Data Sanity | PENDING | | | |
| Step 3b: Model Interpretability | PENDING | | | SHAP analysis of is_moon, is_loner features |
| Step 4: H2H Battery | PENDING | | | |
| Step 5: Comparator Battery | PENDING | | | |
| Step 6: Sanity Bounds Check | PENDING | | | |
| Step 7: Generate Reports | PENDING | | | |
| Step 8: Advance Decision + Narrative | PENDING | | | |
| Step 9: Archive & Advance | PENDING | | | |

## Prerequisites

- [x] R0 QUICK canonical -- 8/9 PASS
- [x] R1 QUICK canonical -- 7/9 PASS (H2 FAIL, H7 SURPRISE)
- [x] R2 QUICK canonical -- 8/9 PASS (H2 FAIL, non-blocking)
- [x] R3 Phase A engine expansion -- 6 PRs merged

## Blockers

_None._

## Session Log

### 2026-03-15 -- Plan creation

- R2 baselines: GBT +1.302 H2H, 0.603 suit R-squared, 2.255 comparator, 57.2% win rate
- R3 is unique: action space expansion, not feature addition
- 9 hypotheses focused on: action space doesn't hurt (H1-H4, H7), models remain sane (H6, H8), model ordering preserved (H5, H9)
- Key R3 research questions from lineage plan section 6.4.6: do models learn moon vs loner selectivity, does GBT exploit card exchange better than OLS, dealer takeover risk
- Moon/loner-specific metrics (bid rates by action type, make rates by action type) not yet in canonical CSV schema -- will need game log analysis or table schema extension
