# Reporting Refactor Alignment Closeout
**Date:** 2026-03-18
**Goal:** Close the remaining gaps between the shipped `arc_d_v2` report bundles and the governing reporting refactor plan. The focus is not new charting ideas; it is finishing the missing chart-data, bundle regeneration, and report-surface cleanup needed so the delivered `quick` and `full` bundles actually match the intended contract.

## Plan
- Step 1: Reconcile the governing plan status with reality before further execution.
  - Update `plans/arc_d_v2/reporting_refactor_full_plan.md` so its status and acceptance section reflect the current shipped state, not a completed-state claim.
  - Add a short pointer from the governing plan to this session plan as the active remediation runbook.
- Step 2: Lock canonical ownership for the remaining missing chart-data family.
  - Make `scripts/internal/generate_interpretability.py` the explicit canonical producer for `decision_comparison.csv` and `disagreement_outcomes.csv`.
  - Treat the dormant parquet extractors in `src/bid_euchre/arc_d_v2/tables.py` as fallback-only and document that they are not expected to produce output on the current parquet schema.
  - Decide whether `cross_rung_progression.csv` stays canonical. If yes, wire it; if no, remove it from the target contract and manifests.
- Step 3: Finish the missing chart-data production path for shipped bundles.
  - Ensure regeneration can emit, when source artifacts exist:
    - `seat_balance.csv`
    - `predictions.csv`
    - `residuals.csv`
    - `calibration_bins.csv`
    - `decision_comparison.csv`
    - `disagreement_outcomes.csv`
    - optionally `cross_rung_progression.csv` per Step 2
  - Add explicit degraded-state files or manifest notes when those artifacts are unavailable because models/parquet are missing.
- Step 4: Fix the remaining semantic contract mismatches in canonical tables.
  - Replace pooled-only `behavior_by_contract.csv` output with real contract-faceted rows for `suit`, `high`, and `low`.
  - Remove aggregate-only fallback from shipped `bid_levels.csv` bundles unless explicitly marked degraded.
  - Stop shipping `outcome_summary.csv` in regenerated `quick/full` bundles; if it remains for debugging, keep it outside canonical committed outputs.
- Step 5: Enforce chart/report generation from the completed chart-data contract.
  - Regenerate Chart 10, 16, 17, 18, 21, and 22 whenever their source CSVs exist.
  - Ensure `01_results.md` stops rendering placeholder text for sections where source data is now present.
  - Keep explicit placeholders only when a source CSV is absent and the manifest marks the bundle incomplete for that reason.
- Step 6: Bring the health and model-eval dashboards into alignment with the shipped evidence.
  - Health dashboard:
    - keep current violin/CDF layout
    - replace degraded synthetic panels only when real row-level distributions exist
    - ensure seat-balance panel is present when `seat_balance.csv` exists
  - Model-eval dashboard:
    - require actual `predictions.csv`, `residuals.csv`, and `calibration_bins.csv` before claiming the dashboard is complete
    - if those CSVs are absent, mark the bundle incomplete rather than treating the dashboard as done
- Step 7: Collapse decision-report sprawl back into the canonical surface.
  - Fold the still-useful narrative content from `04_rung_decision.md` into `02_decision.md`.
  - Remove `04_rung_decision.md` from regenerated `full` bundles, or explicitly deprecate it and stop maintaining it.
  - Keep `02_decision.md` as the single canonical decision artifact for both `quick` and `full`.
- Step 8: Regenerate all canonical bundles from the corrected pipeline.
  - Regenerate `r0-r3/quick`.
  - Regenerate `r0-r3/full` where source artifacts exist.
  - Do not touch `canonical/` bundles in this run unless doing a separate legacy-cleanup PR.
- Step 9: Add acceptance checks that enforce shipped-bundle alignment, not just infrastructure behavior.
  - Assert no `quick/full` canonical bundle contains `outcome_summary.csv`.
  - Assert `behavior_by_contract.csv` has non-pooled contract rows.
  - Assert `02_decision.md` is never `PENDING` in `quick`.
  - Assert the manifest and results report agree on chart presence/absence.
  - Assert bundles are distinct across rungs.

## Files
- `plans/arc_d_v2/reporting_refactor_full_plan.md` — correct status, acceptance text, and pointer to the active remediation plan
- `src/bid_euchre/arc_d_v2/tables.py` — finish chart-data ownership, contract faceting, seat/model-eval generation, and remove canonical `outcome_summary` output
- `scripts/internal/generate_interpretability.py` — become the explicit canonical writer for decision-comparison chart-data
- `scripts/internal/generate_rung_charts.py` — ensure dashboards/standalone charts reflect actual chart-data availability and do not overclaim completeness
- `src/bid_euchre/arc_d_v2/report.py` — remove placeholder sections once source data exists and collapse extra decision-report value into `02_decision.md`
- `src/bid_euchre/arc_d_v2/manifest.py` — manifest incompleteness states must reflect actual missing/degraded chart-data
- `tests/unit/test_rung_tables.py` — add contract-row, missing-artifact, and no-`outcome_summary` assertions
- `tests/unit/test_rung_charts.py` — add chart presence/absence contract tests for the newly completed chart-data family
- `tests/unit/test_rung_report.py` — add `02_decision.md` and `01_results.md` assertions tied to the completed chart-data/report flow
- `tests/unit/test_reporting_pipeline_smoke.py` — enforce bundle-level alignment checks
- `docs/04_reports/arc_d_v2/r0/quick/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r1/quick/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r2/quick/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r3/quick/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r0/full/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r1/full/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r2/full/**` — regenerated canonical bundle
- `docs/04_reports/arc_d_v2/r3/full/**` — regenerated canonical bundle

## Implementation Sequence
- PR 1: Governing-plan correction + ownership lock
  - update governing-plan status
  - lock `decision_comparison.csv` / `disagreement_outcomes.csv` ownership
  - decide `cross_rung_progression.csv` disposition
- PR 2: Chart-data contract completion
  - fix `behavior_by_contract.csv`
  - remove canonical `outcome_summary.csv`
  - complete seat/model-eval/decision chart-data generation where source artifacts exist
- PR 3: Report and chart enforcement
  - remove stale placeholders when data exists
  - ensure manifests/results reflect actual presence
  - fold `04_rung_decision.md` value into `02_decision.md`
- PR 4: Bundle regeneration + acceptance checks
  - regenerate `quick/full`
  - add bundle-level tests
  - verify rung distinctness and canonical surface completeness

## Acceptance Criteria
- `quick` and `full` bundles no longer ship `outcome_summary.csv` as canonical chart-data.
- `behavior_by_contract.csv` contains real `suit`/`high`/`low` rows in regenerated bundles.
- `seat_balance.csv` is present whenever parquet data exists, and Chart 10 renders from it.
- Charts 16, 17, 18, 21, and 22 are present whenever their source CSVs are present; otherwise the manifest explicitly marks the mode incomplete.
- `01_results.md` no longer contains placeholder text for diagnostics/decision-analysis sections when the source chart-data exists.
- `02_decision.md` is the sole maintained decision artifact for regenerated bundles.
- The manifest, results report, and actual filesystem contents agree on chart presence.
- The regenerated bundles are materially closer to the governing plan than the current shipped state:
  - no synthetic distributions presented as healthy
  - no pooled-only contract faceting in canonical support tables
  - no decision-report placeholders in `quick`

## Validation
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_rung_tables.py tests/unit/test_rung_charts.py tests/unit/test_rung_report.py tests/unit/test_reporting_pipeline_smoke.py`
- `rg -n "outcome_summary.csv" docs/04_reports/arc_d_v2/*/{quick,full}`
- `python3 - <<'PY'\nfrom pathlib import Path\nfor rung in ['r0','r1','r2','r3']:\n    for mode in ['quick','full']:\n        p = Path(f'docs/04_reports/arc_d_v2/{rung}/{mode}/tables/behavior_by_contract.csv')\n        if p.exists():\n            txt = p.read_text().splitlines()[1:6]\n            print(rung, mode, txt)\nPY`
- `python3 - <<'PY'\nfrom pathlib import Path\nfor rung in ['r0','r1','r2','r3']:\n    p = Path(f'docs/04_reports/arc_d_v2/{rung}/quick/02_decision.md')\n    if p.exists():\n        print(rung, p.read_text().splitlines()[4])\nPY`

## Outcome
- PR: pending (branch: fix/reporting-refactor-status-correction)
- **Completed (3 of 9 steps):**
  - Step 1: Governing plan status corrected (COMPLETE → PARTIALLY COMPLETE, §16 added)
  - Step 2: Chart-data ownership locked (§16.5 table)
  - Partial Step 4: outcome_summary.csv removed from 9 committed locations
  - Step 7: 04_rung_decision.md deprecated (notices added to all 4 full bundles)
  - Step 9: 34 bundle hygiene tests added
- **Blocked (6 of 9 steps):**
  - Step 3 (chart-data completion): No source artifacts on disk (data/artifacts/ empty)
  - Step 4 (behavior_by_contract): Requires upstream pipeline change to extract_comparator_cis.py — source data lacks `bidders_by_contract`
  - Step 5 (chart enforcement): Depends on Steps 3-4
  - Step 6 (dashboard alignment): Depends on Steps 3-4
  - Step 8 (bundle regeneration): No source artifacts on disk
  - Partial Step 9 (manifest agreement checks): Depends on regenerated bundles
- Notes: The blocked items require either: (a) source data on disk (JSONL game logs, parquet, training artifacts), or (b) upstream pipeline changes. The completed items establish the correct contract and enforcement tests.
