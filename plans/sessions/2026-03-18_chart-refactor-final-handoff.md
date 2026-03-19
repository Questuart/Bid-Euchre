# Chart Refactor Final Handoff
**Date:** 2026-03-18
**Goal:** Hand off the remaining work needed to move the Arc D v2 reporting/charting refactor from “mostly landed” to “actually complete against the original plan.”

## Executive State

The refactor is **not fully complete** against the original reporting plan.

As of the latest audited state:
- `#919` closed the chart-data ownership guard in code.
- `#942` appears to correctly land the missing `#919` follow-up work:
  - regenerated `behavior_by_contract.csv` bundles with `suit/high/low/pooled`
  - corrected stale plan bullets
  - added ownership-guard regression tests

If `#942` merges cleanly, that should close the specific `#919` follow-up gaps.

But even after that, the **original plan is still not fully done**. The largest remaining gaps are:
- QUICK bundles still use synthetic outcome distributions
- Charts 21 and 22 are still absent from shipped bundles
- `04_rung_decision.md` still ships in full bundles, even though deprecated

## What The Next Agent Should Assume

- Do **not** assume the governing plan in `main` is perfectly up to date until `#942` is merged and verified on `main`.
- Do **not** treat “closeout” language from `#919` or `#942` as proof that the original refactor plan is complete.
- Treat `#942` as the likely last cleanup PR for the `#919` review findings, not as proof that the broader chart/report contract is fully satisfied.

## Immediate Verification Step

Before doing any new work, verify whether `#942` merged and actually landed on `main`.

Check:
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/tables/behavior_by_contract.csv`
- `plans/arc_d_v2/reporting_refactor_full_plan.md`
- `tests/unit/test_rung_tables.py`

Expected post-merge state:
- all 8 `behavior_by_contract.csv` files contain `suit`, `high`, `low`, and `pooled`
- governing plan §2.2 no longer describes `Rung ?`, `PENDING`, `Mode: QUICK`, or `Seeds: []` as current truth
- tests include:
  - `test_decision_comparison_not_in_canonical_path`
  - `test_disagreement_outcomes_not_in_canonical_path`

## Remaining Work After #942

### Workstream 1 — Decide what “complete” means for QUICK distributions

Current state:
- QUICK bundles still ship synthetic `outcome_distributions.csv`
- this is explicitly labeled with `source=synthetic`
- the original plan wanted “real health/distribution analysis”

Decision needed:
- Option A: accept synthetic QUICK distributions as an intentional degraded mode and update the governing plan to say the refactor is complete with that degraded policy
- Option B: do not call the refactor complete until QUICK has real row-level distribution data too

Recommendation:
- take **Option A** unless there is a practical path to generate QUICK parquet-backed distributions without turning QUICK into FULL

Tradeoff:
- Option A preserves QUICK speed/readability but accepts a degraded health surface

Why:
- the current design already distinguishes QUICK vs FULL and explicitly supports degraded states when raw artifacts are unavailable

Files to update if Option A is chosen:
- `plans/arc_d_v2/reporting_refactor_full_plan.md`
- potentially `00_manifest.md` / `01_results.md` wording if needed

### Workstream 2 — Finish Charts 21 and 22 or explicitly remove them from “completion”

Current state:
- `decision_agreement.png` and `disagreement_outcomes.png` are still absent across shipped bundles
- canonical data source is `generate_interpretability.py`, not `generate_chart_data()`

Needed work:
- run the interpretability pipeline with trained `.joblib` models and eval parquet
- generate:
  - `decision_comparison.csv`
  - `disagreement_outcomes.csv`
  - Chart 21
  - Chart 22
- regenerate affected bundles and results reports

If artifacts do not exist:
- keep the ownership guard as-is
- update the governing plan so “complete” no longer implies these charts are present

Recommendation:
- first verify whether the required `.joblib` models and eval parquet actually exist for any rung/mode

Tradeoff:
- pushing this to “optional/deferred” makes the suite more honest, but it means the original 23-chart aspiration was not fully realized

Why:
- the current repo state still cannot honestly claim those charts are delivered

Files likely involved:
- `scripts/internal/generate_interpretability.py`
- `scripts/internal/generate_interpretability_charts.py`
- `docs/04_reports/arc_d_v2/r*/{quick,full}/**`
- `plans/arc_d_v2/reporting_refactor_full_plan.md`

### Workstream 3 — Remove the remaining decision-report sprawl

Current state:
- `04_rung_decision.md` is deprecated but still shipped in all FULL bundles

Needed work:
- decide whether to:
  - remove `04_rung_decision.md` from full bundles entirely, or
  - keep it indefinitely as a historical artifact and explicitly exclude it from completion criteria

Recommendation:
- remove it from regenerated FULL bundles once any useful narrative has been folded into `02_decision.md`

Tradeoff:
- removal is cleaner but requires confidence that `02_decision.md` now carries the necessary decision narrative

Why:
- the original plan explicitly tried to constrain the suite to the canonical `00/01/02` surface

Files likely involved:
- `src/bid_euchre/arc_d_v2/report.py`
- `docs/04_reports/arc_d_v2/r*/full/02_decision.md`
- `docs/04_reports/arc_d_v2/r*/full/04_rung_decision.md`

## Suggested Execution Order

1. Verify `#942` on `main`
2. Make the QUICK synthetic-distribution policy explicit
3. Audit whether Charts 21/22 are practically generatable with current artifacts
4. Either generate Charts 21/22 or formally move them out of completion scope
5. Remove `04_rung_decision.md` from regenerated full bundles or formalize it as legacy-only
6. Re-run a final bundle audit against the governing plan
7. Only then change the governing plan status from `PARTIALLY COMPLETE`

## Final Acceptance Checklist

The next agent should only call the refactor “complete” if all of the following are true:

- `#942` is merged and verified on `main`
- the governing plan matches actual shipped bundle state
- the QUICK synthetic distribution policy is explicit and accepted
- Charts 21/22 are either shipped or explicitly removed from completion claims
- `04_rung_decision.md` is no longer part of the maintained reporting surface
- a final audit says the original plan is either:
  - fully complete, or
  - intentionally complete-with-degraded-quick-and-no-21/22

## Useful Verification Commands

```bash
git fetch origin main
git show origin/main:docs/04_reports/arc_d_v2/r2/quick/tables/behavior_by_contract.csv | sed -n '1,12p'
git show origin/main:plans/arc_d_v2/reporting_refactor_full_plan.md | sed -n '33,80p'
git show origin/main:tests/unit/test_rung_tables.py | rg "not_in_canonical"
```

```bash
PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_tables.py -k 'not_in_canonical or BehaviorByContractExpanded'
PYTHONPATH=. uv run python -m pytest -q tests/unit/test_bundle_hygiene.py
```

```bash
for p in docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/00_manifest.md; do
  echo "== $p =="
  rg -n "decision_agreement.png|disagreement_outcomes.png" "$p"
done
```

## Bottom Line

The likely post-`#942` state is:
- **specific closeout fixes:** done
- **original chart refactor plan:** still needs one final decision-and-audit pass before it can honestly be called complete
