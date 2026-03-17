# Arc D v2 Reporting Suite Compaction Plan

<!-- review-tier: medium -->

**Date:** 2026-03-16
**Status:** PROPOSED
**Scope:** Strengthen Arc D v2 reporting for model evaluation, outcome distributions, and one-page storytelling by expanding canonical `chart_data`, introducing dashboard-style chart pages, and compacting the markdown surface to the existing 3-report contract.
**Supersedes:** None

---

## 1. Decision

Implement a compact but richer canonical reporting layer for `arc_d_v2` that keeps the existing markdown surface of `00_manifest.md`, `01_results.md`, and `02_decision.md`, while adding first-class `chart_data` extraction and three dashboard-style chart pages per rung. Do not add notebooks. Do not add new top-level companion reports. Restore the missing analytical coverage by upgrading tables, `chart_data`, and chart generation so another agent can regenerate the full rung package from existing artifacts without rerunning expensive experiments.

## 2. Goals

1. Make model evaluation materially more informative than the current `R^2` and `MAE` only view.
2. Restore clear visibility into outcome distributions and health diagnostics that existed in v1/phase0.
3. Reduce visual and narrative sprawl by consolidating many small charts into three dashboard pages.
4. Preserve the canonical 3-report contract and avoid notebook dependencies.
5. Keep the reporting pipeline fully auditable from CSV and JSON artifacts.

## 3. Non-Goals

1. Do not add new notebooks under `notebooks/`.
2. Do not create new top-level canonical reports beyond `00_manifest.md`, `01_results.md`, and `02_decision.md`.
3. Do not rerun QUICK or FULL evaluation batteries as part of the implementation PR unless a later regeneration pass requires it and the artifacts are missing.
4. Do not redesign rung hypotheses, rung advancement logic, or the model roster.

## 4. Current Gaps

### 4.1 Model Evaluation

- Current committed rung bundles expose only `model_performance.csv` plus `r2_by_contract.png` and `mae_by_contract.png`.
- `01_results.md` has placeholder sections for offline diagnostics, interpretability, and cross-model decision analysis.
- The pipeline does not currently surface prediction diagnostics, calibration, selection paths, or disagreement analysis into the canonical rung package.

### 4.2 Outcome and Health Visibility

- Current committed rung bundles have no populated `chart_data/` CSVs.
- Planned health charts such as outcome distributions and seat balance are absent from committed rung packages.
- Existing behavioral tables do not carry enough context to explain why a model wins or loses.

### 4.3 Sprawl and Readability

- Raw tables, especially H2H matrices, are more exhaustive than readable.
- Several current standalone charts are too narrow to support a one-page review of a rung.
- The current chart set does not provide a concise storytelling surface for humans or agents.

### 4.4 Pipeline Wiring Defects

- Step `3b` in `src/bid_euchre/arc_d_v2/orchestration.py` writes interpretability outputs to the wrong report subdirectory.
- Step `7` does not invoke `scripts/internal/generate_interpretability_charts.py`.
- `src/bid_euchre/arc_d_v2/report.py` expects chart names that do not fully match the broader v2 contract.
- `generate_hypothesis_outcomes()` currently emits a stub CSV with no population path into committed artifacts.

## 5. Target Reporting Contract

### 5.1 Canonical Per-Rung Surface

Keep exactly these top-level deliverables per rung:

- `00_manifest.md`
- `01_results.md`
- `02_decision.md`
- `charts/dashboard_model_eval.png`
- `charts/dashboard_health.png`
- `charts/dashboard_competitive.png`

Additional standalone charts are allowed only as supporting assets when reused inside the dashboards or report sections. They are not the primary review surface.

### 5.2 Dashboard Responsibilities

`dashboard_model_eval.png`
- Offline fit by model and contract
- Predicted vs actual
- Residual distribution
- Calibration curve
- Feature selection path or feature importance
- Cross-model decision agreement and disagreement outcomes

`dashboard_health.png`
- Outcome distributions by contract
- CDF or tail behavior panel
- Seat balance
- Contract mix
- Bid rate, pass rate, average bid, make rate
- Bid-level distribution
- Bid-type breakdown when present

`dashboard_competitive.png`
- Comparator ranking bars with CIs
- Tail risk
- H2H delta vs anchor by contract
- H2H heatmap
- Cross-rung progression summary

### 5.3 Markdown Report Role

`01_results.md`
- Embed the three dashboard pages prominently.
- Retain compact table excerpts for source-of-truth inspection.
- Avoid dumping the full H2H matrix inline unless truncated or summarized.

`02_decision.md`
- Summarize hypothesis outcomes.
- Cite only the key values needed for decisions.
- Point to dashboards and CSV tables instead of reproducing large raw tables.

## 6. Data Contract Changes

### 6.1 Table Schema Upgrades

Expand canonical behavioral reporting in `src/bid_euchre/arc_d_v2/tables.py`.

`behavior_summary.csv` must include at minimum:
- `model`
- `source`
- `net_eppd`
- `eppd`
- `bid_rate`
- `pass_rate`
- `make_rate`
- `avg_bid`
- `bid_std`
- `bid_min`
- `bid_max`
- `mix_suit`
- `mix_high`
- `mix_low`
- `cvar_5`
- `net_cvar_5`
- `redeal_rate`

`behavior_by_contract.csv` must include at minimum:
- `model`
- `contract`
- `source`
- `net_eppd`
- `bid_rate`
- `pass_rate`
- `make_rate`
- `avg_bid`
- `bid_std`
- `bid_min`
- `bid_max`

`behavior_by_bid_type.csv` remains canonical and must be surfaced into charts when bid-type data exists.

`hypothesis_outcomes.csv`
- Stop emitting a permanently empty stub.
- Populate from advance-check outputs or explicitly mark `PENDING` only when `02_decision.md` has not yet been synthesized.

### 6.2 New Canonical `chart_data` CSVs

Create and inventory these CSVs under `docs/04_reports/arc_d_v2/<rung>/<tier>/chart_data/`:

- `predictions.csv`
- `residuals.csv`
- `calibration_bins.csv`
- `selection_paths.csv`
- `decision_comparison.csv`
- `disagreement_outcomes.csv`
- `outcome_distributions.csv`
- `seat_balance.csv`
- `bid_levels.csv`
- `contract_mix.csv`
- `cross_rung_progression.csv`

All dashboard visualizations must render from these CSVs or from canonical `tables/*.csv`. No dashboard should read raw JSONL, parquet, or model artifacts directly.

## 7. Execution Structure

### 7.1 Phase 0: Contract Alignment

Purpose: correct the contract mismatch between the lineage plan and the actual pipeline before adding new visual surfaces.

Files changed:
- `plans/arc_d_v2/lineage_plan.md`
- `src/bid_euchre/arc_d_v2/report.py`
- `src/bid_euchre/arc_d_v2/manifest.py`

Actions:
- Reconcile chart naming between report generation and the v2 chart contract.
- Define the dashboard pages in the lineage plan as the canonical visual review surface.
- Specify the required `chart_data` inventory and expected report behavior when optional model-specific charts are absent.

Validates:
- Report/chart naming is internally consistent.
- The plan no longer claims charts or sections that the code cannot produce.

### 7.2 Phase 1: Table and `chart_data` Expansion

Purpose: upgrade source-of-truth tables and generate auditable `chart_data`.

Files changed:
- `src/bid_euchre/arc_d_v2/tables.py`
- `scripts/internal/generate_rung_tables.py`
- `scripts/internal/generate_rung_charts.py`
- `scripts/internal/generate_interpretability.py`

Actions:
- Expand behavior table schemas with pass rate, bid-level, and contract-mix fields.
- Add extraction logic for `chart_data` CSVs from existing artifacts and tables.
- Ensure `generate_interpretability.py` writes to the rung report `chart_data/` directory, not `tables/`.
- Ensure no new `chart_data` extractor depends on notebooks.

Validates:
- Fixture-driven table generation still passes.
- New `chart_data` CSVs are emitted in the smoke pipeline.
- Missing optional sources degrade gracefully.

### 7.3 Phase 2: Dashboard Chart Generation

Purpose: replace fragmented visual review with three dashboard pages.

Files changed:
- `scripts/internal/generate_rung_charts.py`
- `scripts/internal/generate_interpretability_charts.py`
- `src/bid_euchre/arc_d_v2/report.py`

Actions:
- Add dashboard composition functions:
  - `dashboard_model_eval.png`
  - `dashboard_health.png`
  - `dashboard_competitive.png`
- Reuse existing chart builders where possible instead of duplicating logic.
- Keep supporting standalone charts only when they are reused in report sections or assist debugging.
- Update report generation to embed dashboards first, then supporting compact tables.

Validates:
- Dashboards render on fixture data.
- Layout remains readable with 8-model rosters.
- Dashboard generation succeeds even when some optional model-specific CSVs are absent.

### 7.4 Phase 3: Pipeline Wiring and Decision Report Completion

Purpose: make the orchestrator produce the intended canonical package end-to-end.

Files changed:
- `src/bid_euchre/arc_d_v2/orchestration.py`
- `scripts/internal/generate_rung_report.py`
- `scripts/internal/generate_evidence_manifest.py`
- `src/bid_euchre/arc_d_v2/advance_check.py`

Actions:
- Fix Step `3b` output paths.
- Add interpretability chart generation to Step `7`.
- Ensure `chart_data` inventory is recorded in the evidence manifest.
- Define how `hypothesis_outcomes.csv` is populated from advance-check output and/or `02_decision.md`.
- Ensure `02_decision.md` remains the only narrative file and is regenerated from current tables.

Validates:
- Smoke pipeline produces `chart_data`, dashboards, manifest, `01_results.md`, and a populated hypothesis CSV.
- No new top-level report files are created.

### 7.5 Phase 4: Backfill Existing Canonical Bundles

Purpose: regenerate committed `arc_d_v2` rung bundles from existing artifacts only.

Targets:
- `docs/04_reports/arc_d_v2/r0/quick/`
- `docs/04_reports/arc_d_v2/r1/quick/`
- `docs/04_reports/arc_d_v2/r2/quick/`
- `docs/04_reports/arc_d_v2/r3/canonical/`

Actions:
- Run table generation from existing rung artifacts.
- Run dashboard and supporting chart generation.
- Regenerate manifests and results reports.
- Synthesize or restore missing `02_decision.md` where appropriate.

Validates:
- Existing rung artifacts are sufficient to regenerate the richer report package.
- `r3/canonical` contains the same top-level contract as earlier rungs.

## 8. File-Level Change List

### 8.1 Required Code Paths

- `src/bid_euchre/arc_d_v2/tables.py`
- `src/bid_euchre/arc_d_v2/report.py`
- `src/bid_euchre/arc_d_v2/manifest.py`
- `src/bid_euchre/arc_d_v2/orchestration.py`
- `scripts/internal/generate_rung_tables.py`
- `scripts/internal/generate_rung_charts.py`
- `scripts/internal/generate_interpretability.py`
- `scripts/internal/generate_interpretability_charts.py`
- `scripts/internal/generate_rung_report.py`
- `scripts/internal/generate_evidence_manifest.py`

### 8.2 Required Tests

- `tests/unit/test_rung_tables.py`
- `tests/unit/test_rung_report.py`
- `tests/unit/test_reporting_pipeline_smoke.py`
- `tests/unit/test_rung_orchestrator.py`

Potential new tests if needed:
- `tests/unit/test_rung_dashboards.py`
- `tests/unit/test_chart_data_contract.py`

## 9. Validation Plan

### 9.1 Unit and Integration

- `PYTHONPATH=src uv run pytest -q tests/unit/test_rung_tables.py`
- `PYTHONPATH=src uv run pytest -q tests/unit/test_rung_report.py`
- `PYTHONPATH=src uv run pytest -q tests/unit/test_reporting_pipeline_smoke.py`
- `PYTHONPATH=src uv run pytest -q tests/unit/test_rung_orchestrator.py -k 'advance_check or step_3b or step_7'`

### 9.2 Artifact Validation

- Smoke-generate a temporary rung report from `data/fixtures/arc_d_v2`.
- Verify manifest records non-empty `chart_data`.
- Verify dashboards exist and are referenced in `01_results.md`.
- Verify no notebooks are created or modified.
- Verify no new top-level report types are introduced.

### 9.3 Backfill Validation

For each committed rung package:
- `chart_data/` exists and contains the required CSVs or a documented subset when optional data is unavailable.
- `charts/` contains the three dashboard pages.
- `01_results.md` embeds the dashboards and no longer shows offline-diagnostics placeholders for data that is now produced.
- `02_decision.md` exists for every committed canonical rung package.

## 10. Dependency Chain

- Existing rung artifacts under `data/artifacts/arc_d_v2/<rung>/` must be present for backfill.
- Existing interpretability extraction code in `scripts/internal/generate_interpretability.py` is the basis for model-evaluation `chart_data`.
- Existing diagnostic chart helpers in `src/bid_euchre/diagnostics/` may be reused for dashboard panels, but no notebook workflow may be introduced.

## 11. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Dashboard pages become unreadable with many panels | Keep only three dashboard pages and cap panel count per page; split by function, not by every raw metric |
| Existing artifacts lack enough information for some `chart_data` CSVs | Degrade gracefully, emit partial dashboards, and document unavailable panels in the report rather than inventing data |
| Behavior schema expansion breaks fixture tests | Update fixture expectations first, then chart generation, then report rendering |
| Rung pipeline paths remain inconsistent | Fix Step `3b` and Step `7` wiring before backfill |
| Regeneration accidentally implies new experiment runs | Restrict implementation validation to fixture data and existing artifacts; do not rerun QUICK/FULL batteries |

## 12. Rollback and Failure Containment

- If schema expansion breaks report generation, revert to the last passing table schema and land pipeline wiring separately.
- If dashboard composition is too brittle, land `chart_data` extraction first and keep the old standalone charts temporarily.
- If backfill for a rung is blocked by missing artifacts, leave the code changes merged and defer that rung’s regenerated committed bundle.
- Do not hand-edit markdown or CSV values to patch failures; fix generators and rerun.

## 13. Success Criteria

1. Every committed `arc_d_v2` rung bundle contains non-empty `chart_data` inventory in the evidence manifest.
2. Every committed `arc_d_v2` rung bundle contains the three dashboard pages.
3. `01_results.md` provides materially richer model-evaluation and outcome-distribution coverage without adding new top-level reports.
4. No notebooks are added or modified.
5. Another agent can regenerate the rung package end-to-end from this plan plus the referenced scripts without repository archaeology.

## Outcome

_To be filled after implementation._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN
- Notes: deviations from plan
