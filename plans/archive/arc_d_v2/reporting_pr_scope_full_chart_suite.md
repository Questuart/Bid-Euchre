# Arc D v2 Reporting PR Scope: Full Chart Suite

<!-- review-tier: medium -->

> **ARCHIVED:** Superseded by reporting refactor PRs #834–#848. Moved 2026-03-18.

**Date:** 2026-03-16
**Status:** PROPOSED
**Owner:** Reporting follow-up PR
**Depends on:** `plans/arc_d_v2/reporting_suite_compaction_plan.md`

## 1. Objective

Deliver one follow-up PR that completes the missing Arc D v2 chart suite without expanding the report surface beyond:

- `00_manifest.md`
- `01_results.md`
- `02_decision.md`

The PR must:

- finish the missing model-evaluation and health/distribution charts
- fix the current chart-data and path-contract defects
- make chart numbering explicit and stable across all rungs
- add H2H ranking scatter and intelligence-faceted H2H views
- preserve the dashboard-first review surface
- avoid notebooks and new companion reports

## 2. Non-Goals

- Do not add notebooks.
- Do not add new top-level markdown reports.
- Do not rerun expensive experiment batteries unless an artifact is missing and regeneration is unavoidable.
- Do not redesign rung advancement logic or roster composition.

## 3. Scope Summary

This PR is complete only if all four workstreams land together:

1. Path and contract alignment
2. Full `chart_data` completion for the missing model-eval and health views
3. Full canonical chart generation, including numbered charts
4. Report and manifest updates so the numbered chart suite is visible and auditable

The implementation must preserve autonomous generation:

- a single pipeline run must still be able to regenerate `00_manifest.md`, `01_results.md`, `02_decision.md`, `tables/*.csv`, `chart_data/*.csv`, and `charts/*.png` without manual notebook or hand-edited report steps

## 4. Required Outcomes

### 4.1 Path Contract

Unify the canonical rung report location to:

- `docs/04_reports/arc_d_v2/<rung>/quick`

All helpers, orchestration steps, report generation, evidence-manifest generation, and backfill commands must write to and read from that same path.

### 4.2 Full Canonical Chart Suite

Each rung bundle must support the following stable chart registry. Numbering is global within the rung package and must not change based on missing optional artifacts.

| Number | Filename | Title | Required Source |
|---|---|---|---|
| 1 | `dashboard_competitive.png` | Competitive Dashboard | canonical tables |
| 2 | `dashboard_health.png` | Health Dashboard | canonical tables + `chart_data` |
| 3 | `dashboard_model_eval.png` | Model Evaluation Dashboard | canonical tables + `chart_data` |
| 4 | `comparator_ranking_bars.png` | Comparator Ranking Bars | `tables/comparator_rankings.csv` |
| 5 | `tail_risk_panel.png` | Tail Risk Panel | `tables/comparator_rankings.csv` |
| 6 | `delta_bars_by_contract.png` | H2H Delta by Contract | `tables/h2h_delta_matrix.csv` |
| 7 | `h2h_heatmap.png` | H2H Heatmap | `tables/h2h_delta_matrix.csv` |
| 8 | `h2h_ranking_scatter.png` | H2H Ranking Scatter | `tables/comparator_rankings.csv` and `tables/h2h_tier_summary.csv` |
| 9 | `outcome_distributions.png` | Outcome Distributions | `chart_data/outcome_distributions.csv` |
| 10 | `seat_balance.png` | Seat Balance | `chart_data/seat_balance.csv` |
| 11 | `contract_mix_bars.png` | Contract Mix | `chart_data/contract_mix.csv` |
| 12 | `bid_behavior_panel.png` | Bid and Make Rates | `tables/behavior_summary.csv` and `tables/behavior_by_contract.csv` |
| 13 | `bid_level_distribution.png` | Bid Level Distribution | `chart_data/bid_levels.csv` |
| 14 | `r2_by_contract.png` | R-squared by Contract | `tables/model_performance.csv` |
| 15 | `mae_by_contract.png` | MAE by Contract | `tables/model_performance.csv` |
| 16 | `pred_vs_actual.png` | Predicted vs Actual | `chart_data/predictions.csv` |
| 17 | `residual_distribution.png` | Residual Distribution | `chart_data/residuals.csv` |
| 18 | `calibration_curve.png` | Calibration Curve | `chart_data/calibration_bins.csv` |
| 19 | `selection_path.png` | Selection Path | `chart_data/selection_paths.csv` |
| 20 | `feature_importance.png` | Feature Importance | `chart_data/feature_importances.csv` |
| 21 | `decision_agreement.png` | Decision Agreement | `chart_data/decision_comparison.csv` |
| 22 | `disagreement_outcomes.png` | Disagreement Outcomes | `chart_data/disagreement_outcomes.csv` |

Rules:

- Chart numbers are part of the contract and must appear in `01_results.md` and `00_manifest.md`.
- If a chart is unavailable because source data is legitimately absent, keep the number reserved and emit a numbered placeholder in `01_results.md`.
- Dashboards stay first in the report, but numbered standalone charts remain canonical supporting evidence.
- `02_decision.md` must cite chart numbers where charts drive the decision narrative.

### 4.2.1 Report Flow Requirements

The chart suite must flow into the canonical markdown artifacts as follows.

`00_manifest.md`

- inventory every numbered chart with:
  - chart number
  - filename
  - title
  - byte size
  - presence/absence status
- inventory `chart_data/*.csv` and explanatory tables used by the dashboards

`01_results.md`

- present dashboards first
- present the highest-signal numbered standalone charts in the section where they explain the evidence
- include compact explanatory tables only where they materially aid interpretation
- avoid dumping long raw tables inline when the chart already communicates the point

`02_decision.md`

- reference the numbered charts and only the minimum supporting tables needed for the rung decision
- pull in the smallest useful excerpt of hypothesis outcomes, comparator ranking, and H2H evidence
- prefer chart references plus concise summary tables over large markdown dumps

### 4.2.2 Long Table Handling

Long lists and large raw tables are allowed as canonical CSV artifacts, but not all of them should be rendered inline in markdown.

Rules:

- If a table exceeds approximately 12-15 rows in the rendered report, prefer a summary or top/bottom excerpt.
- If a matrix is visually explained by a chart, do not also dump the full matrix inline.
- For large H2H tables, render:
  - a short explanatory summary table
  - the relevant chart(s)
  - a note that the full canonical CSV is available under `tables/`
- The report should explicitly mark long omitted tables with wording such as:
  - `Full table omitted from markdown; see tables/<name>.csv`

### 4.3 Dashboard Composition Requirements

`dashboard_competitive.png`

- comparator ranking bars
- tail risk
- H2H delta by contract
- H2H heatmap
- H2H ranking scatter
- H2H intelligence-faceted summary
- cross-rung progression summary

`dashboard_health.png`

- bid rate, pass rate, make rate
- contract mix
- outcome distributions
- seat balance or bid-level distribution

`dashboard_model_eval.png`

- `R^2` by contract
- `MAE` by contract
- predicted vs actual
- residual distribution
- calibration curve
- selection path or feature importance
- decision agreement or disagreement outcomes

If the full set does not fit on one page, use a 3x2 layout for `dashboard_model_eval.png`, `dashboard_health.png`, and `dashboard_competitive.png`. The dashboards should summarize, not replace, the numbered standalone charts.

## 5. Source Data Requirements

The PR must ensure the following canonical `chart_data` files are emitted under `chart_data/` when the underlying artifacts exist:

- `predictions.csv`
- `residuals.csv`
- `calibration_bins.csv`
- `selection_paths.csv`
- `feature_importances.csv`
- `decision_comparison.csv`
- `disagreement_outcomes.csv`
- `outcome_distributions.csv`
- `seat_balance.csv`
- `bid_levels.csv`
- `contract_mix.csv`
- `cross_rung_progression.csv`

The PR must also ensure the following canonical H2H summary table is present and used:

- `tables/h2h_tier_summary.csv`

### 5.1 Data Semantics

The implementation must satisfy these semantics:

- `outcome_distributions.csv` must contain actual distribution rows suitable for histogram or CDF rendering. It must not be a summary-metric table disguised as a distribution table.
- `contract_mix.csv` must be the source of truth for contract mix charts.
- `behavior_by_contract.csv` must actually drive contract-faceted behavior views.
- `decision_comparison.csv` and `disagreement_outcomes.csv` must feed the model-evaluation suite whenever interpretability outputs exist.
- `h2h_tier_summary.csv` must be treated as the source of truth for intelligence-faceted H2H reporting, using the existing tier taxonomy (`smart`, `anchor`, `heuristic`) unless the roster contract is explicitly expanded in the same PR.
- H2H reporting must preserve both contract faceting (`suit`, `high`, `low`, `pooled`) and intelligence faceting. Intelligence faceting is not optional.
- H2H report-facing tables and chart labels must use repo-convention naming that clearly identifies sides as `team0` and `team1`.

## 6. Required Code Changes

The following files are expected to change.

### 6.1 Path and Orchestration

- `src/bid_euchre/arc_d_v2/paths.py`
- `src/bid_euchre/arc_d_v2/orchestration.py`

Required changes:

- Make `rung_report_dir()` resolve to `docs/04_reports/arc_d_v2/<rung>/quick`.
- Update Step `3b` and Step `7` to use the same helper path instead of hard-coded subdirectories.
- Ensure interpretability outputs and chart generation land in `chart_data/` and `charts/` under the canonical quick bundle.

### 6.2 Table and Chart-Data Extraction

- `src/bid_euchre/arc_d_v2/tables.py`
- `scripts/internal/generate_interpretability.py`

Required changes:

- Expand behavior tables to include:
  - `pass_rate`
  - `avg_bid`
  - `bid_std`
  - `bid_min`
  - `bid_max`
  - `mix_suit`
  - `mix_high`
  - `mix_low`
- Replace the current outcome-summary-as-distribution extraction with true outcome-distribution rows.
- Emit `seat_balance.csv`, `bid_levels.csv`, `predictions.csv`, `residuals.csv`, `calibration_bins.csv`, `feature_importances.csv`, `decision_comparison.csv`, and `disagreement_outcomes.csv` where source artifacts exist.
- Keep extraction logic notebook-free and driven by existing artifacts.
- If needed, widen `h2h_tier_summary.csv` so it can support a ranking scatter and intelligence-faceted H2H dashboard panel with:
  - model rank or pooled rank
  - intelligence tier
  - mean delta
  - mean win rate
  - opponent count
- Add report-facing H2H summary tables or aliases that label matchup sides as `team0` and `team1`, even if internal computation still uses `model_a` and `model_b`.

### 6.3 Chart Generation

- `scripts/internal/generate_rung_charts.py`
- `scripts/internal/generate_interpretability_charts.py`

Required changes:

- Generate all standalone charts listed in Section 4.2.
- Fix `bid_behavior_panel.png` so it reflects actual contract-faceted behavior rather than taking the first row per model.
- Make `contract_mix_bars.png` read from `chart_data/contract_mix.csv`.
- Add new chart builders for:
  - `h2h_ranking_scatter.png`
  - `outcome_distributions.png`
  - `seat_balance.png`
  - `bid_level_distribution.png`
  - `pred_vs_actual.png`
  - `residual_distribution.png`
  - `calibration_curve.png`
  - `feature_importance.png`
  - `decision_agreement.png`
  - `disagreement_outcomes.png`
- Add an H2H ranking scatter that shows every model's standing, with labels, and that can be faceted or color-coded by model intelligence.
- Ensure H2H charts incorporate intelligence faceting:
  - contract-faceted charts remain driven by `facet`
  - intelligence-faceted H2H views are driven by `h2h_tier_summary.csv`
  - the competitive dashboard must surface both perspectives
- Ensure H2H chart legends, labels, and captions use `team0` and `team1` terminology where sides are shown explicitly.
- Update dashboard assembly so the dashboard panels are composed from the same canonical source files as the standalone charts.

### 6.4 Report and Manifest Rendering

- `src/bid_euchre/arc_d_v2/report.py`
- `src/bid_euchre/arc_d_v2/manifest.py`
- `scripts/internal/generate_evidence_manifest.py`

Required changes:

- Add a stable chart registry structure with:
  - chart number
  - filename
  - display title
  - optional/required flag
- Render chart headings in `01_results.md` as `### Chart <n>. <Title>`.
- Render dashboard headings in `01_results.md` as `### Chart <n>. <Title>`.
- Emit numbered placeholders for missing optional charts.
- Include chart number and title in the chart inventory rendered into `00_manifest.md`.
- Update `01_results.md` generation so large low-signal tables are summarized instead of dumped inline.
- Update `02_decision.md` generation or synthesis inputs so it references chart numbers and concise supporting tables.
- Ensure report-rendered H2H tables and captions label sides as `team0` and `team1`.

## 7. Implementation Notes

Use these implementation constraints:

- Do not renumber charts dynamically based on availability.
- Do not make dashboards the only place a chart appears; keep standalone evidence charts.
- Prefer a single shared chart registry constant used by report rendering, manifest rendering, and tests.
- If an interpretability artifact is absent for a rung, preserve the chart number and emit a placeholder rather than dropping the section.
- Preserve backward-compatible filenames listed in Section 4.2.
- Use the existing H2H tier taxonomy already present in `src/bid_euchre/arc_d_v2/tables.py` unless the PR also formalizes a broader roster-level intelligence field and updates all downstream contracts.
- Keep raw canonical CSV schemas stable where practical, but add report-facing aliases or rendering transforms when repo-facing language should use `team0` and `team1`.

## 8. Acceptance Criteria

The PR is ready only when all of the following are true:

1. `docs/04_reports/arc_d_v2/r0/quick` through `r3/quick` can be regenerated without writing to any `canonical/` sibling directory.
2. `01_results.md` for each rung embeds numbered dashboards and numbered standalone charts.
3. `00_manifest.md` inventories numbered charts and the expanded `chart_data` set.
4. `02_decision.md` cites numbered charts where those charts support the advancement decision.
5. Long low-signal tables are not dumped inline in markdown when a chart already carries the information.
6. H2H markdown tables and chart labels use `team0` and `team1` naming when matchup sides are shown.
7. `pred_vs_actual.png`, `residual_distribution.png`, and `calibration_curve.png` are generated whenever the required model-eval inputs exist.
8. `outcome_distributions.png` is backed by true distribution rows, not summary metrics.
9. `contract_mix_bars.png` is backed by `chart_data/contract_mix.csv`.
10. `bid_behavior_panel.png` uses actual contract-faceted data.
11. `h2h_ranking_scatter.png` is present and shows the ranking/standing of each model from canonical H2H inputs.
12. The competitive suite includes intelligence-faceted H2H analysis using `h2h_tier_summary.csv`.
13. `dashboard_model_eval.png` contains more than `R^2`, `MAE`, and selection-path panels; it must include prediction diagnostics and decision-analysis content when present.
14. No notebooks are added.
15. No new top-level report markdown files are added.

## 9. Testing Requirements

At minimum, add or update tests in:

- `tests/unit/test_rung_tables.py`
- `tests/unit/test_rung_report.py`
- `tests/unit/test_reporting_pipeline_smoke.py`
- `tests/unit/test_rung_orchestrator.py`

Required test coverage:

- chart registry numbering is stable and rendered correctly
- report placeholders preserve chart numbers for missing optional charts
- path helpers and orchestrator steps write to `quick`
- `00_manifest.md`, `01_results.md`, and `02_decision.md` all reflect the numbered chart contract
- long markdown tables are truncated or summarized according to policy
- `contract_mix_bars.png` uses `contract_mix.csv`
- `outcome_distributions.csv` and `outcome_distributions.png` use distribution-shaped data
- `h2h_ranking_scatter.png` renders from canonical H2H summary inputs
- intelligence-faceted H2H views use `h2h_tier_summary.csv`
- contract-faceted H2H views remain intact alongside intelligence-faceted views
- H2H report/table labels use `team0` and `team1`
- dashboard model-eval rendering degrades gracefully when some optional CSVs are missing
- evidence manifest inventories `chart_data` and charts with numbering metadata

## 10. Suggested PR Description

Title:

- `fix: complete arc_d_v2 full chart suite and add stable chart numbering`

Summary bullets:

- align `arc_d_v2` report paths on `docs/04_reports/arc_d_v2/<rung>/quick`
- generate missing model-eval and health/distribution charts from canonical `chart_data`
- add H2H ranking scatter and intelligence-faceted H2H reporting
- fix miswired contract-mix and behavior panels
- add stable chart numbering across reports and manifests
- improve report readability by summarizing long low-signal tables and using `team0`/`team1` H2H labels
- backfill rung bundles without adding notebooks or report sprawl
