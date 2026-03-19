# Reporting Quality: GBT Model-Eval Fix + R3/FULL Parity

**Date:** 2026-03-19
**Goal:** Narrow DS-3 (GBT model-eval) and DS-4 (R3/FULL stale) degraded states, confirm DS-1/DS-2 status, improve report quality.
**Branch:** fix/reporting-gbt-r3-parity
**Parent plan:** `plans/arc_d_v2/reporting_refactor_full_plan.md` (§16.6)

## Audit Findings

### Artifact Availability

| Artifact | R0 | R1 | R2 | R3 | Notes |
|----------|----|----|----|----|-------|
| GBT `.joblib` (FULL) | ✅ 4 files | ✅ 4 files | ✅ 4 files | ❌ | R3 FULL has no dedicated GBT run dir |
| GBT `.joblib` (artifacts/) | ✅ | ✅ | ✅ | ✅ | All at `data/artifacts/arc_d_v2/<rung>/gbt_*.joblib` |
| `training_artifact_gbt_av.json` | ✅ | ✅ | ✅ | ✅ | Schema `action_value_gbt_v1`, 4 contracts |
| Eval parquet (FULL) | ✅ | ✅ | ✅ | ✅ | `data/runs/arc_d_v2/base_datasets/pre_<rung>/full/` |
| `decision_comparison.csv` | ❌ | ❌ | ❌ | ❌ | Not produced anywhere |
| `disagreement_outcomes.csv` | ❌ | ❌ | ❌ | ❌ | Not produced anywhere |

### R3/FULL vs R0-R2/FULL Chart Parity

R3/FULL is missing 4 charts that R0-R2/FULL have:
- Chart 10: `seat_balance.png` — data present (`seat_balance.csv` 332 bytes)
- Chart 16: `pred_vs_actual.png` — data present (`predictions.csv` 540KB)
- Chart 17: `residual_distribution.png` — data present (`residuals.csv` 2.7KB)
- Chart 18: `calibration_curve.png` — data present (`calibration_bins.csv` 1.7KB)

**Root cause:** Charts were not regenerated after chart_data CSVs were added to R3/FULL.

### GBT Model-Eval Path Mismatch (DS-3)

`generate_model_eval_csvs()` in `tables.py` (line 1892) looks for GBT joblib files
relative to the eval parquet path:

```python
candidate_dirs = [
    eval_parquet_path.parent.parent / "artifacts",  # datasets/artifacts/ — wrong
    eval_parquet_path.parent,                         # action_value/ dir — wrong
]
```

Actual joblib location: `data/artifacts/arc_d_v2/<rung>/gbt_<contract>.joblib`

Neither candidate resolves to the actual path. The function does not receive `rung_dir`.

**Fix:** Add `rung_dir` parameter to `generate_model_eval_csvs()` and include it
in `candidate_dirs`.

### Charts 21/22 (DS-2) — Still Data-Blocked

The interpretability pipeline (`generate_interpretability.py`) needs eval parquet with
`bid_decision` and `model` columns. Current eval parquets are raw action-value datasets
without these columns. No practical path exists without a separate model inference run.

**Decision:** DS-2 remains data-blocked. No code change.

### QUICK Synthetic (DS-1) — Confirmed Stable

No QUICK parquet exists. QUICK bundles correctly label `source=synthetic`.
No changes needed.

## Execution Plan

### Phase 1: Code Fix — GBT Model-Eval Discovery

**Files:** `src/bid_euchre/arc_d_v2/tables.py`

1. Add `rung_dir: Path | None = None` parameter to `generate_model_eval_csvs()`
2. Add `rung_dir` to `candidate_dirs` list (before existing candidates)
3. Update call site in `generate_all_tables()` (line 2680) to pass `rung_dir`
4. Add test for GBT joblib discovery

### Phase 2: R3/FULL Chart Regeneration

1. Run `generate_rung_charts.py` on R3/FULL existing tables + chart_data
2. Verify Charts 10, 16-18 are now present
3. Regenerate R3/FULL dashboards (they embed model-eval panels)

### Phase 3: R3/FULL Manifest + Report Update

1. Regenerate `00_manifest.md` — charts 10, 16-18 flip from absent to present
2. Update `01_results.md` — improve model-eval section wording
3. Update `evidence_manifest.json`

### Phase 4: Report Quality Pass

1. Review all 8 `01_results.md` for placeholder/weak narrative
2. Review all 8 `02_decision.md` for decision usefulness
3. Focus on: what's trustworthy, what's missing, what changed

### Phase 5: Governing Plan Update

1. Narrow DS-3 description (code fix shipped, R0-R2 regeneration deferred)
2. Remove DS-4 if R3/FULL reaches parity
3. Confirm DS-1, DS-2 stable

### Phase 6: Validation + PR

1. Run targeted tests
2. Run `make check-quiet`
3. Bundle audit
4. Open PR with validation evidence

## Scope Boundaries

**In scope:**
- GBT joblib discovery fix in tables.py
- R3/FULL chart regeneration (Charts 10, 16-18)
- R3/FULL manifest/report update
- Report quality improvements (all bundles)
- Governing plan §16.6 updates
- Test for GBT path discovery

**Out of scope (follow-up):**
- Regenerating R0-R2/FULL chart_data with GBT predictions (needs separate regeneration)
- Charts 21/22 (data-blocked, no practical path)
- QUICK mode changes
- Manifest model class metadata fix

## Parallelism Assessment

**Main agent owns:** code fix, chart regeneration, manifest/report updates, PR
**Plan-review agent:** review this plan before implementation
**No additional parallel agents needed** — write scopes overlap too much for safe split

## Risk

| Risk | Mitigation |
|------|-----------|
| Chart generator fails on R3/FULL data | Data verified present; R0/FULL same data format works |
| GBT fix requires API change propagation | Only one call site; backward compatible default |
| Report changes create noisy diff | Focus on factual accuracy, not cosmetic changes |

## Outcome

_To be filled after implementation._
