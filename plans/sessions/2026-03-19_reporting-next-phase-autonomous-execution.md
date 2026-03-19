# Reporting Next Phase Autonomous Execution
**Date:** 2026-03-19
**Goal:** Move Arc D v2 reporting from “complete with degraded states” to the strongest practical post-refactor state by removing the remaining degraded modes, regenerating stale bundles, and shifting from infrastructure work to analytical/report-quality work.

## Executive State

The reporting refactor is structurally complete, but the next meaningful work is still substantive:

- Charts 21/22 are still absent and remain the largest analytical blind spot.
- `r3/full` is still stale relative to `r0-r2/full`.
- GBT model-eval extraction remains incomplete.
- QUICK outcome distributions are still synthetic by policy.
- The next improvements should optimize for decision-maker usefulness, not more chart-suite churn.

This plan treats those five items as one coordinated execution slice.

## Primary Sources Of Truth

- `plans/arc_d_v2/reporting_refactor_full_plan.md`
- `plans/arc_d_v2/reporting_pr_scope_full_chart_suite.md`
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/`

## Scope

### In scope

1. Finish decision-analysis chart production for Charts 21/22 if artifacts permit.
2. Bring `r3/full` into parity with the current FULL reporting contract.
3. Fix or document GBT model-eval loading.
4. Revisit the long-term QUICK synthetic-distribution policy.
5. Improve report quality and decision usefulness without expanding the surface area.

### Out of scope

- Reopening the 23-chart registry contract.
- Adding new top-level report families.
- Reintroducing `canonical/` as a maintained surface.
- Notebook-driven reporting as the primary path.

## Autonomous Execution Requirements

Before writing code, the executing agent must:

1. Read the governing plan sections relevant to:
   - accepted degraded states
   - Charts 21/22
   - FULL model-eval chart requirements
   - QUICK/FULL mode policy
2. Draft a concrete session plan for the execution slice.
3. Create a bounded task list.
4. Assess safe parallelism and spawn at least one plan-review sub-agent.
5. Incorporate plan-review feedback before implementation.

Do not start implementation until the plan, task list, and plan-review step are complete.

## Workstreams

### Workstream A — Charts 21/22 Decision Analysis

**Objective:** Produce `decision_comparison.csv`, `disagreement_outcomes.csv`, `decision_agreement.png`, and `disagreement_outcomes.png` if the required `.joblib` + parquet inputs exist.

**Tasks**

- Verify artifact availability for each rung:
  - trained `.joblib` models
  - eval parquet with the schema needed by `generate_interpretability.py`
- If artifacts exist:
  - run interpretability generation
  - render Charts 21/22
  - regenerate affected manifests and results reports
- If artifacts do not exist:
  - leave canonical ownership as-is
  - explicitly preserve DS-2 as data-blocked
  - update the PR summary and plan/status docs to say the gap is evidence-blocked, not code-blocked

**Success condition**

- Either Charts 21/22 ship in at least the eligible FULL bundles, or the repo has a fully verified, explicit “data-blocked” closeout note with no ambiguity.

### Workstream B — R3/FULL Parity

**Objective:** Eliminate DS-4 if the current artifacts support regeneration.

**Tasks**

- Audit `r3/full` against `r0-r2/full` for:
  - rendered Charts 10 and 16-18
  - model roster class metadata
  - results/report sections that still understate on-disk data
- If current inputs are sufficient:
  - regenerate `r3/full`
  - update manifest, evidence manifest, and results report
- If inputs are still insufficient:
  - keep DS-4 explicit and narrow
  - ensure the governing plan says exactly why parity is not possible

**Success condition**

- `r3/full` either matches the current FULL contract or is the only explicitly documented stale exception with concrete cause.

### Workstream C — GBT Model-Eval Loading

**Objective:** Remove or narrow DS-3 by fixing GBT artifact discovery if practical.

**Tasks**

- Trace how OLS-family training artifacts are discovered for prediction/residual/calibration extraction.
- Compare that path to GBT artifact layout.
- Fix the joblib-path mismatch if it is a local pipeline problem.
- If GBT loading cannot be fixed without artifact changes:
  - document the exact blocker
  - preserve DS-3 with tighter wording

**Success condition**

- GBT model-eval rows either appear in generated CSVs/charts or the repo contains a precise, verified reason they cannot.

### Workstream D — QUICK Distribution Policy

**Objective:** Decide whether QUICK synthetic distributions remain an accepted product decision or should be retired.

**Tasks**

- Re-check whether any practical QUICK parquet-backed path now exists.
- If not:
  - keep DS-1
  - make sure QUICK reports clearly label synthetic/degraded distribution evidence
- If yes:
  - estimate the runtime/complexity cost of upgrading QUICK
  - only implement if it does not collapse QUICK into FULL

**Success condition**

- QUICK distribution policy is explicit, stable, and honest in plan/report language.

### Workstream E — Report Quality

**Objective:** Improve report usefulness after infrastructure fixes, without adding new surfaces.

**Tasks**

- Review `01_results.md` and `02_decision.md` after any regeneration for:
  - placeholder text that should now be removed
  - weak narrative around failure modes
  - missing explanation of degraded states
- Prioritize improvements that help a human decision-maker:
  - what is missing
  - what is trustworthy
  - what changed materially by rung
- Keep the surface fixed to:
  - `00_manifest.md`
  - `01_results.md`
  - `02_decision.md`

**Success condition**

- Regenerated reports read as decision artifacts, not just chart inventories.

## Bounded Task List

1. Verify current artifact availability for interpretability and GBT eval.
2. Draft execution plan and get one plan-review sub-agent response.
3. Split work into at least two non-overlapping write scopes if parallelism is useful.
4. Attempt Charts 21/22 generation.
5. Attempt `r3/full` regeneration.
6. Attempt GBT artifact loading fix.
7. Revalidate QUICK synthetic policy.
8. Refresh manifests/results/decision reports.
9. Run targeted tests.
10. Run bundle-audit checks.
11. Update governing docs/status language if any degraded state is removed or narrowed.
12. Prepare PR with validation evidence.

## Parallelism Guidance

The executing agent should assess safe parallelism before editing.

Good disjoint splits:

- **Agent A:** Artifact audit and generation feasibility for Charts 21/22 and GBT eval.
- **Agent B:** Report-quality pass and post-regeneration text cleanup in `01_results.md` / `02_decision.md`.
- **Agent C:** Validation harness and bundle-audit command preparation.

Keep these owned by the main agent:

- final regeneration choices
- final plan/status edits
- integration of generated artifacts
- PR body and validation evidence

Do not allow multiple agents to edit the same plan file or the same generated bundle paths.

## Recommended Execution Order

1. Draft session plan and task list.
2. Run plan review with at least one sub-agent.
3. Audit interpretability + GBT artifact availability.
4. Implement the highest-value unblock first:
   - Charts 21/22 if artifacts exist
   - otherwise GBT loading or `r3/full` regeneration
5. Regenerate affected FULL bundles.
6. Reassess QUICK synthetic policy.
7. Improve report narrative in regenerated bundles.
8. Run validation.
9. Open PR with full evidence.

## Validation Requirements

Minimum automated validation:

- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_tables.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_charts.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_report.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_bundle_hygiene.py`
- `make check-quiet`

Artifact and report validation:

- verify whether Charts 21/22 are present or still explicitly absent
- verify whether `r3/full` manifests/charts/results match on-disk chart data
- verify whether GBT model-eval rows appear where expected
- verify QUICK distribution labeling remains explicit
- verify no deprecated decision artifacts reappear

Suggested audit commands:

```bash
git fetch origin main
for p in docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/00_manifest.md; do
  echo "== $p =="
  rg -n "decision_agreement|disagreement_outcomes|seat_balance|pred_vs_actual|residual_distribution|calibration_curve" "$p"
done
```

```bash
for p in docs/04_reports/arc_d_v2/r{0,1,2,3}/quick/chart_data/outcome_distributions.csv; do
  echo "== $p =="
  sed -n '1,6p' "$p"
done
```

```bash
git show origin/main:docs/04_reports/arc_d_v2/r3/full/00_manifest.md | sed -n '10,110p'
```

## Deliverables

1. Code/docs/artifacts committed on branch.
2. PR opened.
3. PR body includes:
   - plan summary
   - artifact availability findings
   - tests run
   - bundle-audit evidence
   - final degraded states removed, narrowed, or retained
4. Short closeout note stating whether reporting is now:
   - fully complete
   - complete with fewer degraded states
   - still complete with the same degraded states

## Definition Of Done

This slice is successful if:

- the highest-value remaining analytical gap is reduced
- any remaining degraded states are narrower and better justified
- `r3/full` is either regenerated or explicitly proven blocked
- report quality improves without expanding the reporting surface
- the next person can tell, from the PR alone, exactly what reporting still cannot do and why
