# Reporting Upstream Artifact Production
**Date:** 2026-03-19
**Goal:** Remove the remaining reporting degraded states by producing the missing upstream runtime artifacts rather than continuing report-layer cleanup.

## Executive State

The Arc D v2 reporting refactor is no longer blocked by chart/report infrastructure.
The remaining gaps are now upstream-data gaps:

- model-eval CSVs only support `contract=pass` because eval parquet lacks the
  derived features needed for suit/high/low contract evaluation
- Charts 21/22 remain data-blocked because `action_value.parquet` is absent for
  the interpretability pipeline
- `r3/full` cannot fully match `r0-r2/full` until FULL-mode eval parquet exists

This plan shifts the work from reporting regeneration to artifact production.

## Primary Sources Of Truth

- `plans/arc_d_v2/reporting_refactor_full_plan.md`
- `plans/arc_d_v2/reporting_refactor_phase0_audit.md`
- `plans/sessions/2026-03-19_reporting-next-phase-autonomous-execution.md`
- `plans/sessions/2026-03-19_reporting-residuals-post-972-handoff.md`
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/{quick,full}/`

## Desired End State

1. Eval parquet supports contract-faceted model evaluation, not just `pass`.
2. `action_value.parquet` exists where decision-analysis generation requires it.
3. `r3/full` has FULL-mode eval parquet if that mode is still intended to exist.
4. Reporting regeneration can then:
   - refresh model-eval CSVs
   - render Charts 16-18 and dashboard surfaces from richer evidence
   - generate Charts 21/22 where artifacts exist
   - narrow or remove DS-2 / DS-3 residual language honestly

## Scope

### In scope

1. Audit the experiment/runtime pipeline that produces eval parquet and action-value artifacts.
2. Identify the exact upstream producer(s) responsible for:
   - derived eval features such as `bid_n_sq`
   - `action_value.parquet`
   - FULL-mode eval parquet availability for `r3`
3. Implement the smallest safe upstream changes that produce the missing artifacts.
4. Add or tighten tests around those producers.
5. Regenerate only the necessary downstream reporting artifacts once upstream production is working.
6. Update degraded-state language if and only if shipped bundle state changes.

### Out of scope

- reopening the chart registry
- introducing new reporting surfaces
- broad report-narrative rewrites unrelated to new evidence
- regenerating `canonical/`
- treating QUICK as FULL

## Workstreams

### Workstream A — Contract-Faceted Model-Eval Inputs

**Objective:** remove the `contract=pass` limitation by ensuring eval parquet contains
the features needed to evaluate suit/high/low contracts.

**Tasks**

- trace the eval parquet producer for Arc D v2
- identify where `bid_n_sq` and any related derived fields should be computed
- confirm whether the missing feature belongs in:
  - dataset preparation
  - feature engineering
  - model-eval extraction
- implement the upstream change at the earliest correct producer boundary
- regenerate a representative eval parquet shard and verify that suit/high/low
  rows can now be extracted into:
  - `predictions.csv`
  - `residuals.csv`
  - `calibration_bins.csv`

**Success condition**

- at least one regenerated FULL bundle produces model-eval CSVs with non-`pass`
  contract coverage, or the repo contains a precise documented blocker with test-backed proof

### Workstream B — Decision-Analysis Artifact Production

**Objective:** unblock Charts 21/22 by producing `action_value.parquet` for the
interpretability pipeline.

**Tasks**

- trace the producer path that should emit `action_value.parquet`
- confirm whether the file is:
  - never produced
  - produced in another location
  - filtered out from committed/retained runtime outputs
- implement the minimal upstream fix to make it available to
  `generate_interpretability.py`
- validate that `decision_comparison.csv` and `disagreement_outcomes.csv` can be generated

**Success condition**

- `action_value.parquet` exists for at least one eligible rung/mode combination
  and the decision-analysis CSVs generate successfully, or DS-2 is narrowed to an exact blocker

### Workstream C — R3/FULL Artifact Availability

**Objective:** determine whether `r3/full` should have FULL-mode eval artifacts and,
if yes, produce them.

**Tasks**

- audit current run/output conventions for `r3`
- determine whether missing FULL eval parquet is:
  - intentional policy
  - missing experiment execution
  - pipeline gap
- if FULL mode is still intended:
  - produce the required eval parquet
  - rerun downstream model-eval extraction and charts for `r3/full`
- if FULL mode is not intended:
  - update plan/status language to make that explicit

**Success condition**

- `r3/full` is either brought to artifact parity or formally scoped as intentionally partial

### Workstream D — Downstream Reporting Regeneration

**Objective:** once upstream artifacts exist, regenerate only the report-layer outputs
that are now newly supportable.

**Tasks**

- refresh affected chart_data CSVs
- regenerate Charts 16-18 and dashboard_model_eval where richer data now exists
- generate Charts 21/22 if decision-analysis artifacts are available
- update:
  - `00_manifest.md`
  - `evidence_manifest.json`
  - `01_results.md`
  - governing degraded-state language

**Success condition**

- reporting surfaces match the newly produced evidence without unrelated churn

## Bounded Task List

1. Audit current degraded states against actual upstream artifact gaps.
2. Draft an execution plan and get at least one plan-review sub-agent response.
3. Identify exact producer files and responsibilities.
4. Assess safe parallelism with disjoint write scopes.
5. Implement upstream feature/artifact fixes.
6. Add targeted tests for the producers.
7. Generate representative artifacts locally.
8. Regenerate the smallest necessary reporting surfaces.
9. Run validation.
10. Update governing docs only if shipped bundle state actually improves.
11. Open PR with full validation evidence and exact remaining blockers.

## Parallelism Guidance

Good disjoint splits:

- **Agent A:** trace and patch eval parquet feature production
- **Agent B:** trace and patch `action_value.parquet` production / interpretability prerequisites
- **Agent C:** prepare downstream validation and bundle-audit checks

Keep these owned by the main agent:

- final upstream architecture decisions
- final regeneration commands
- final degraded-state wording
- PR body assembly

Do not allow multiple agents to edit the same runtime producer modules or the same generated bundle directories.

## Recommended Execution Order

1. Audit current producers for eval parquet and action-value artifacts.
2. Decide whether one PR can safely cover both:
   - contract-faceted model-eval inputs
   - decision-analysis artifact production
3. If yes, implement both upstream fixes in one bounded PR.
4. If not, prioritize in this order:
   - contract-faceted model-eval inputs
   - action-value artifact production
   - `r3/full` parity
5. Regenerate downstream reporting only after upstream artifacts are proven.
6. Re-audit DS-2 / DS-3 / any `r3/full` residual state.

## Validation Requirements

Minimum automated validation:

- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_tables.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_charts.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_report.py`
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_bundle_hygiene.py`
- any targeted producer tests added for dataset/runtime artifact generation
- `make check-quiet`

Artifact validation:

- verify eval parquet now includes the needed contract-eval features
- verify `action_value.parquet` exists at the documented path pattern
- verify regenerated model-eval CSVs contain non-`pass` contract rows if that fix lands
- verify Charts 21/22 can be produced if the decision-analysis artifact fix lands
- verify any updated manifests/results match on-disk files

## Success Condition

This effort is successful if it moves reporting from “complete with degraded states”
to “limited only by clearly intentional policy,” by solving the actual upstream artifact
gaps instead of continuing report-layer workarounds.

At minimum, the next agent should leave the repo with:

- a verified map of the missing producers
- either merged upstream fixes or exact blockers
- a clear statement of whether the remaining work fits in one PR or needs staged follow-up
