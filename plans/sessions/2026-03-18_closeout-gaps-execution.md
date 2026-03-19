# Closeout Gaps Execution Plan
**Date:** 2026-03-18
**Goal:** Execute the 5 remaining gaps from the reporting refactor post-#904/#909 closeout.

## Gaps Addressed

### Gap 1: Guard dormant extractors ✅
Removed steps 9-10 (`_extract_decision_comparison()` / `_extract_disagreement_outcomes()`)
from `generate_chart_data()` call path in `tables.py`. Functions retained as library code
but no longer called during normal chart-data generation. Prevents silent shadowing of
canonical producer (`generate_interpretability.py`).

### Gap 2: Regeneration prerequisites doc ✅
Added §17 to `plans/arc_d_v2/reporting_refactor_full_plan.md` with:
- §17.1: CSV → artifact dependency table (11 CSVs documented)
- §17.2: Degraded mode descriptions
- §17.3: JSONL re-extraction command template
- §17.4: Chart rendering dependency notes
- §17.5: Post-regeneration audit table

### Gap 3: Regenerate QUICK bundles ⚠️ Blocked
Existing comparator_cis JSONs lack `bidders_by_contract`. JSONL game logs exist for
re-extraction (`data/runs/arc_d_v2_*_comparator_*/logs/*.jsonl`). Blocked on PR #909
merge — the per-contract extraction code is on #909's branch.

### Gap 4: Chart rendering verification ✅
Verified against R0/full bundle:
- Charts 10, 16, 17, 18: ✅ All render (seat_balance, pred_vs_actual, residual_distribution, calibration_curve)
- Charts 21, 22: ❌ Absent — source CSVs (decision_comparison, disagreement_outcomes) require `generate_interpretability.py` run, not `generate_chart_data()`

### Gap 5: Post-regeneration audit ✅
Written inline in §17.5 of the governing plan. Categorizes all acceptance criteria as:
- Fixed in code (6 items)
- Fixed in bundles (4 items)
- Data-blocked (2 items)

## Outcome
- PR: #912 (guard dormant extractors + regen prerequisites doc + chart verification + audit)
- Remaining: Gap 3 (QUICK bundle regeneration) blocked on #909 merge + JSONL re-extraction
