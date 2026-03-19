# Model-Eval Chart Regeneration + DS-3 Closure

**Date:** 2026-03-19
**Branch:** `fix/model-eval-chart-regen-and-ds3`
**Predecessor:** PR #980 (merged) — regenerated R0-R2/FULL model-eval CSVs with GBT rows

## Goal

Re-render the reader-facing model-eval PNGs (Charts 16-18 + dashboard_model_eval)
for R0-R2/FULL so they reflect the GBT evidence now present in the underlying
CSVs. Fix the governing-plan `#TBD` placeholder. Confirm Charts 21/22 remain
data-blocked. Produce a clean single PR.

## State Assessment

| Item | Current State | Target State |
|------|--------------|-------------|
| R0-R2/FULL model-eval CSVs | ✅ Include `gbt_av` (5 models total) via PR #980 | No change needed |
| R0-R2/FULL model-eval PNGs | ❌ STALE — rendered from pre-GBT CSVs (PR #881) | Regenerate from updated CSVs |
| DS-3 governing plan text | Says `(PR #TBD)` | Fix to `(PR #980)` |
| R0-R2/FULL manifests | Reflect CSV sizes from #980 | Update PNG sizes after regen |
| Charts 21/22 (DS-2) | Data-blocked — no `action_value.parquet` exists | Confirm still blocked, no action |
| DS-1 (QUICK synthetic) | Accepted policy | No change |
| DS-4 (R3/FULL parity) | Resolved (PR #972) | No change |

## Scope

### In scope

1. Regenerate 4 model-eval PNGs × 3 rungs (R0-R2/FULL):
   - `full_chart_suite/pred_vs_actual.png`
   - `full_chart_suite/residual_distribution.png`
   - `full_chart_suite/calibration_curve.png`
   - `dashboard_model_eval.png`
2. Update `00_manifest.md` with new PNG byte sizes (3 rungs)
3. Update `evidence_manifest.json` with new PNG byte sizes (3 rungs)
4. Fix `#TBD` → `#980` in governing plan DS-3 section
5. Confirm Charts 21/22 remain data-blocked (no implementation)

### Out of scope

- Regenerating non-model-eval charts (no CSV changes for those)
- Charts 21/22 implementation (no parquet data available)
- QUICK mode changes
- R3/FULL changes (already at parity)
- Full bundle regeneration
- Report narrative rewrites

## Approach: Targeted Chart Regeneration

The `generate_rung_charts.py` CLI generates ALL charts in one pass. To avoid
unnecessary churn in unrelated PNGs (matplotlib version differences could cause
pixel-level changes), use a targeted Python script that calls only the 4
model-eval chart functions.

Each function reads from `chart_data/` CSVs and writes to `charts/`:
- `generate_predictions_scatter(chart_data_dir, suite_dir)`
- `generate_residuals_chart(chart_data_dir, suite_dir)`
- `generate_calibration_curve(chart_data_dir, suite_dir)`
- `generate_dashboard_model_eval(tables_dir, charts_dir, chart_data_dir)`

Input directories per rung:
- `tables_dir`: `docs/04_reports/arc_d_v2/<rung>/full/tables/`
- `chart_data_dir`: `docs/04_reports/arc_d_v2/<rung>/full/chart_data/`
- `suite_dir`: `docs/04_reports/arc_d_v2/<rung>/full/charts/full_chart_suite/`
- `charts_dir`: `docs/04_reports/arc_d_v2/<rung>/full/charts/`

## Charts 21/22 Feasibility Assessment

**Result: DATA-BLOCKED — no action.**

- `.joblib` models exist: ✅ (`gbt_{high,low,pass,suit}.joblib` for R0-R2)
- `action_value.parquet` exists: ❌ (not present for any rung)
- `generate_interpretability.py` requires both `.joblib` AND `action_value.parquet`
- Parquet files live in `data/runs/` (gitignored, large runtime artifacts)
- DS-2 remains accurately described as data-blocked

## Validation Plan

### Artifact checks
- Verify regenerated PNGs differ from pre-regen versions (new models visible)
- Verify manifest byte sizes match actual file sizes
- Verify evidence_manifest.json matches

### Automated tests
- `uv run python -m pytest -q tests/unit/test_rung_charts.py`
- `uv run python -m pytest -q tests/unit/test_rung_report.py`
- `uv run python -m pytest -q tests/unit/test_bundle_hygiene.py`
- `make check-quiet`

## Outcome

**PR:** #TBD

### What shipped
- 12 model-eval PNGs regenerated (Charts 16-18 + dashboard_model_eval × 3 rungs)
- All PNGs now include GBT model alongside 4 OLS-family models (5 total)
- 3 `00_manifest.md` + 3 `evidence_manifest.json` updated with accurate byte sizes
- DS-3 `#TBD` → `#980` fix + removed "Remaining gap" about un-rendered PNGs
- R0/R1 `dashboard_model_eval.png` pre-existing size discrepancy fixed

### Items 1-4 assessment
1. ✅ #980 verified on main, DS-3 truthfulness pass done
2. ✅ Model-eval surfaces regenerated for R0-R2/FULL
3. ✅ DS-3 fully resolved — no remaining gaps
4. ❌ Charts 21/22 deferred — `action_value.parquet` does not exist for any rung (DS-2 unchanged)

### Remaining degraded states
- **DS-1:** QUICK synthetic outcome distributions (accepted policy — unchanged)
- **DS-2:** Charts 21/22 data-blocked (no `action_value.parquet`) — unchanged

### Validation
- test_rung_charts: 56 passed
- test_rung_report: 36 passed
- test_bundle_hygiene: 30 passed, 4 skipped
- `make check-quiet`: all passed
- All 12 manifest + 12 evidence_manifest size entries verified vs actual files
