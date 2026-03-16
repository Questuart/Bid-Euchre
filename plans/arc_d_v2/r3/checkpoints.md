# R3 Checkpoints

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Phase/Rung:** R3 (moon/loner action space expansion)
**Last updated:** 2026-03-16 by report suite session

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Plan & Hypothesize | COMPLETE | 2026-03-15 | Plan creation | 9 hypotheses |
| Step 1: Generate Training Data | COMPLETE | 2026-03-16 | Orchestrator | `--include-moon-loner` flag, seed 42 |
| Step 2: Train All Roster Models | COMPLETE | 2026-03-16 | Orchestrator | 59 state + 4 action features |
| Step 3: Offline Evaluation + Data Sanity | COMPLETE | 2026-03-16 | Orchestrator | 23/23 sanity checks pass |
| Step 3b: Model Interpretability | COMPLETE | 2026-03-16 | Orchestrator | SHAP analysis completed |
| Step 4: H2H Battery | COMPLETE | 2026-03-16 | Orchestrator | All cross-matchups |
| Step 5: Comparator Battery | COMPLETE | 2026-03-16 | Orchestrator | 8 bidders ranked |
| Step 6: Sanity Bounds Check | COMPLETE | 2026-03-16 | Orchestrator | All bounds pass |
| Step 7: Generate Reports | COMPLETE | 2026-03-16 | Orchestrator + PR | Tables + h2h_tier_summary |
| Step 8: Advance Decision + Narrative | COMPLETE | 2026-03-16 | Orchestrator | PROCEED, 9/9 pass, 1 canary warning |
| Step 9: Archive & Advance | PENDING | | | Awaiting FULL backfill |

## Prerequisites

- [x] R0 QUICK canonical -- 8/9 PASS
- [x] R1 QUICK canonical -- 7/9 PASS (H2 FAIL, H7 SURPRISE)
- [x] R2 QUICK canonical -- 8/9 PASS (H2 FAIL, non-blocking)
- [x] R3 Phase A engine expansion -- 6 PRs merged
- [x] R3 inference fix -- PR #739 merged

## Blockers

_None._

## R3 QUICK Results Summary

- **Advance decision:** PROCEED (all 9 hypotheses pass)
- **GBT H2H delta vs anchor:** +1.2156 (pooled), +0.8639 (suit)
- **GBT comparator net_eppd:** 2.3048 (rank 1/8)
- **GBT suit R-squared:** 0.8986
- **GBT win rate vs anchor:** 54.48%
- **GBT vs smart models:** +1.5884 delta, 62.25% win rate
- **Canary warning:** C3 (magnitude >5.0 on rankthetank matchups)
- **Rerun note:** Results from post-inference-fix rerun (PR #739)

## Session Log

### 2026-03-15 -- Plan creation

- R2 baselines: GBT +1.302 H2H, 0.603 suit R-squared, 2.255 comparator, 57.2% win rate
- R3 is unique: action space expansion, not feature addition
- 9 hypotheses focused on: action space doesn't hurt (H1-H4, H7), models remain sane (H6, H8), model ordering preserved (H5, H9)
- Key R3 research questions from lineage plan section 6.4.6: do models learn moon vs loner selectivity, does GBT exploit card exchange better than OLS, dealer takeover risk
- Moon/loner-specific metrics (bid rates by action type, make rates by action type) not yet in canonical CSV schema -- will need game log analysis or table schema extension

### 2026-03-16 -- QUICK rerun + report suite

- R3 QUICK rerun completed after inference fix (PR #739)
- All 9 hypotheses pass, 1 canary warning (C3, non-blocking)
- Reports re-homed from canonical/ to quick/ per R0-R2 pattern
- Added h2h_tier_summary.csv to table pipeline
- Updated cross_rung_deltas.csv with R3 row + gbt_vs_smart columns
