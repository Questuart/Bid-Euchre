# Reporting Residuals Post-#972 Handoff
**Date:** 2026-03-19
**Goal:** Finish the highest-value remaining reporting work after PR `#972`, ideally in one PR, by realizing the GBT model-eval fix in shipped FULL bundles and tightening the governing-plan/report truthfulness that follows from it.

## Primary References

- `plans/arc_d_v2/reporting_refactor_full_plan.md`
- `plans/sessions/2026-03-19_reporting-next-phase-autonomous-execution.md`
- PR `#972` branch / merge state

## Current State

Assuming `#972` is merged or ready to merge:

- DS-4 is resolved or pending resolution via `r3/full` chart parity.
- DS-3 is narrowed in code, but not yet fully realized in shipped bundles.
- The highest-value remaining reporting work is:
  - regenerate `r0-r2/full` model-eval CSVs with GBT rows
  - refresh manifests/results to reflect the new rows
  - re-audit degraded states after the regeneration

Still accepted unless this slice proves otherwise:

- DS-1: QUICK synthetic outcome distributions
- DS-2: Charts 21/22 data-blocked

## Scope For One PR

This should fit in one PR **if** the artifacts needed for FULL regeneration are present and stable.

### In scope

1. Verify `#972` state on `main` or stack cleanly on top of it.
2. Regenerate `r0-r2/full` model-eval CSVs so GBT rows actually ship.
3. Refresh affected FULL manifests and results reports.
4. Re-audit DS-3 after regeneration.
5. If cheap and directly adjacent, improve `01_results.md` / `02_decision.md` wording where the new model-eval evidence changes the interpretation.

### Out of scope

- Charts 21/22 unless artifact availability turns out to be trivial after audit.
- QUICK-mode redesign.
- New top-level reporting surfaces.
- Notebook-driven reporting.

## Mandatory Execution Sequence

Before implementation:

1. Read the governing plan sections for:
   - DS-1 through DS-4
   - FULL model-eval chart-data expectations
   - acceptance criteria status
2. Read `plans/sessions/2026-03-19_reporting-next-phase-autonomous-execution.md`.
3. Draft a concrete session plan for this residual slice.
4. Create a bounded task list.
5. Assess safe parallelism.
6. Spawn at least one agent to review the plan before major edits.
7. Incorporate plan-review feedback.

Do not start implementation until the plan, task list, and plan review are complete.

## Main Objective

Turn DS-3 from “code fix shipped, regeneration deferred” into shipped reporting evidence.

That means:

- `predictions.csv`
- `residuals.csv`
- `calibration_bins.csv`

for `r0-r2/full` should include GBT rows if the fixed discovery path in `tables.py` now works against the real artifacts.

## Concrete Task List

1. Verify merge/base state.
   - If `#972` is merged, branch from `main`.
   - If not, stack on `#972` cleanly and state that explicitly in the PR.

2. Audit artifact availability for `r0-r2/full`.
   - confirm `training_artifact_gbt_av.json`
   - confirm `.joblib` files under `data/artifacts/arc_d_v2/<rung>/`
   - confirm FULL eval parquet paths

3. Draft the execution plan and get one plan-review agent response.

4. Regenerate `r0-r2/full` model-eval chart-data.
   - validate that GBT rows appear in:
     - `predictions.csv`
     - `residuals.csv`
     - `calibration_bins.csv`

5. Refresh bundle surfaces impacted by the regenerated CSVs.
   - `00_manifest.md`
   - `evidence_manifest.json`
   - `01_results.md`
   - any affected charts/dashboards if regeneration changes them materially

6. Re-evaluate DS-3.
   - If GBT rows now ship in `r0-r2/full`, narrow or remove DS-3 accordingly.
   - If regeneration still fails, document the exact blocker rather than leaving generic wording.

7. Optional adjacent pass:
   - tighten `01_results.md` or `02_decision.md` narrative only where the new GBT evidence materially changes interpretation.

8. Run validation.

9. Open PR with explicit before/after evidence.

## Safe Parallelism

Use parallelism only if write scopes are disjoint.

Good splits:

- **Agent A:** artifact audit and regeneration feasibility for `r0-r2/full`
- **Agent B:** report-quality wording audit for affected FULL bundles
- **Agent C:** validation command preparation / bundle-audit checks

Keep these with the main agent:

- final regeneration commands
- integration of regenerated artifacts
- governing-plan degraded-state edits
- final PR body and evidence summary

Do not have multiple agents edit the same generated bundle directories or the same plan file.

## Validation Requirements

Minimum:

- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_tables.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_charts.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_report.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_bundle_hygiene.py`
- `make check-quiet`

Required artifact checks:

- GBT rows actually appear in regenerated `r0-r2/full` model-eval CSVs
- manifests/evidence manifests inventory the regenerated CSVs accurately
- `01_results.md` no longer understates the available model-eval evidence
- DS-3 wording in the governing plan matches the shipped bundle state

Suggested audit commands:

```bash
for p in docs/04_reports/arc_d_v2/r{0,1,2}/full/chart_data/{predictions,residuals,calibration_bins}.csv; do
  echo "== $p =="
  sed -n '1,8p' "$p"
done
```

```bash
for p in docs/04_reports/arc_d_v2/r{0,1,2}/full/00_manifest.md; do
  echo "== $p =="
  rg -n "Predicted vs Actual|Residual Distribution|Calibration Curve" "$p"
done
```

```bash
git show origin/main:plans/arc_d_v2/reporting_refactor_full_plan.md | sed -n '1098,1122p'
```

## PR Guidance

This can be one PR if the regeneration works.

Recommended PR framing:

- primary change: realize GBT model-eval support in shipped FULL bundles
- secondary change: narrow or resolve DS-3 in plan docs
- optional tertiary change: small report-quality wording updates tied directly to the new evidence

Do not expand scope to Charts 21/22 unless the artifact path is unexpectedly trivial.

## Deliverables

1. Code/docs/artifacts committed on branch.
2. PR opened.
3. PR body includes:
   - base/stacking state relative to `#972`
   - artifact availability findings
   - regeneration commands
   - tests run
   - before/after DS-3 status
   - any remaining blockers
4. Short handoff summary stating:
   - what shipped
   - whether DS-3 is now realized or still deferred
   - whether any adjacent report-quality cleanup landed
   - PR number/link

## Success Condition

This slice is successful if one PR can move reporting forward from:

- “GBT fix exists in code”

to:

- “GBT-backed model-eval evidence actually ships in the FULL bundles that can support it”

and the governing plan truthfully reflects that new state.
