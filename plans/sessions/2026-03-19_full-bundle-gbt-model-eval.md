# Session Plan: Realize GBT Model-Eval in Shipped FULL Bundles

**Date:** 2026-03-19
**Branch:** `fix/full-bundle-gbt-model-eval`
**Base:** `origin/main` (after PR #972 merge at `84ca863`)

## Goal

Turn DS-3 from "GBT fix shipped in code" to "GBT-backed model-eval evidence
ships in the FULL bundles that can support it." One PR.

## Context

PR #972 added `rung_dir` to `generate_model_eval_csvs()` so GBT `.joblib`
files at `data/artifacts/arc_d_v2/r{0,1,2}/` are discoverable. But the
committed FULL bundle CSVs were not regenerated — they still contain only
OLS-family (`constrained_ols_av`) rows.

## Artifact Audit (Pre-Implementation)

| Artifact | R0 | R1 | R2 | Path Pattern |
|----------|----|----|----|----|
| `training_artifact_gbt_av.json` | ✅ | ✅ | ✅ | `data/artifacts/arc_d_v2/r{0,1,2}/` |
| GBT `.joblib` (4 per rung) | ✅ | ✅ | ✅ | `data/artifacts/arc_d_v2/r{0,1,2}/gbt_{high,low,pass,suit}.joblib` |
| FULL eval parquet (10 seeds) | ✅ | ✅ | ✅ | `data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_{1001..1010}/datasets/action_value/part_*.parquet` |
| OLS training artifacts (4 per rung) | ✅ | ✅ | ✅ | `data/artifacts/arc_d_v2/r{0,1,2}/training_artifact_{constrained,full,selected}_ols_av.json` + `selected_two_stage_av` |

**Conclusion:** All inputs needed for GBT model-eval regeneration are present.
The parquet files use chunked format (`part_000000_004999.parquet`), which
`generate_all_tables()` handles via `av_dir.glob("*.parquet")` fallback.

## Plan

### Step 1: Regenerate model-eval CSVs for r0-r2/full

Run `generate_rung_tables.py` for each rung with correct `--dataset-dir` paths.
This regenerates all tables + chart_data CSVs. The model-eval CSVs
(`predictions.csv`, `residuals.csv`, `calibration_bins.csv`) should now include
GBT rows thanks to the #972 `rung_dir` fix.

```bash
for rung in r0 r1 r2; do
  PYTHONPATH=src uv run python scripts/internal/generate_rung_tables.py \
    --rung-dir data/artifacts/arc_d_v2/$rung \
    --output-dir docs/04_reports/arc_d_v2/$rung/full/tables \
    --mode full \
    --seed 1001,1002,1003,1004,1005,1006,1007,1008,1009,1010 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1001 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1002 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1003 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1004 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1005 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1006 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1007 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1008 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1009 \
    --dataset-dir data/runs/arc_d_v2/base_datasets/pre_r3/full/seed_1010 \
    -v
done
```

### Step 2: Verify GBT rows in regenerated CSVs

```bash
for rung in r0 r1 r2; do
  echo "== $rung predictions.csv =="
  cut -d, -f1 docs/04_reports/arc_d_v2/$rung/full/chart_data/predictions.csv | sort -u
  echo "== $rung residuals.csv =="
  cut -d, -f1 docs/04_reports/arc_d_v2/$rung/full/chart_data/residuals.csv | sort -u
  echo "== $rung calibration_bins.csv =="
  cut -d, -f1 docs/04_reports/arc_d_v2/$rung/full/chart_data/calibration_bins.csv | sort -u
done
```

Expected: `gbt_av` rows appear alongside existing OLS-family rows.

### Step 3: Refresh affected manifests

For each rung, update CSV size metadata:
- `00_manifest.md` — update `calibration_bins.csv`, `predictions.csv`, `residuals.csv` sizes
- `evidence_manifest.json` — update `size_bytes` for the same 3 CSVs

Note: `01_results.md` and dashboard PNGs (Charts 16-18) were **not** refreshed
in this PR. The GBT data ships in the CSVs but is not yet surfaced in the
chart/report reading experience. This is documented in the governing plan DS-3.

### Step 4: Update DS-3 in governing plan

In `plans/arc_d_v2/reporting_refactor_full_plan.md`, narrow or remove DS-3.
The new wording should reflect that GBT model-eval CSVs now ship in r0-r2/full
bundles.

### Step 5: Run validation

- Targeted tests: `test_rung_tables.py`, `test_rung_charts.py`, `test_rung_report.py`, `test_bundle_hygiene.py`
- Full: `make check-quiet`

### Step 6: Open PR with validation evidence

## Files Modified

| File | Change |
|------|--------|
| `docs/04_reports/arc_d_v2/r{0,1,2}/full/chart_data/predictions.csv` | Add GBT rows |
| `docs/04_reports/arc_d_v2/r{0,1,2}/full/chart_data/residuals.csv` | Add GBT rows |
| `docs/04_reports/arc_d_v2/r{0,1,2}/full/chart_data/calibration_bins.csv` | Add GBT rows |
| `docs/04_reports/arc_d_v2/r{0,1,2}/full/00_manifest.md` | Updated CSV sizes |
| `docs/04_reports/arc_d_v2/r{0,1,2}/full/evidence_manifest.json` | Updated CSV size_bytes |
| `plans/arc_d_v2/reporting_refactor_full_plan.md` | DS-3 status update |

## Out of Scope

- Charts 21/22 (DS-2, data-blocked)
- QUICK synthetic distributions (DS-1, accepted policy)
- R3 bundles (already regenerated in #972)
- New reporting surfaces
- Notebook-driven reporting

## Risk

- Regeneration may change non-model-eval CSVs if `tables.py` logic changed since
  last bundle generation. Mitigation: diff review before commit.
- Parquet chunked format may not be handled correctly by the `dataset_dirs`
  discovery path. Mitigation: verified that `av_dir.glob("*.parquet")` handles
  chunked format at line 2646 of `tables.py`.

## Outcome

**Status:** COMPLETE (with documented remaining gaps)

Regenerated model-eval CSVs for R0-R2/FULL bundles with GBT rows.

- All 3 CSVs × 3 rungs now contain 5 models: `constrained_ols_av`, `full_ols_av`,
  `gbt_av`, `selected_ols_av`, `selected_two_stage_av`
- Before: 20,000 rows (4 OLS-family models × 5,000 each)
- After: 25,000 rows (5 models × 5,000 each)
- Manifests and evidence manifests updated with new sizes
- DS-3 in governing plan marked RESOLVED (PR #972 code fix + PR #980 regeneration)
- DS-4 PR reference updated to #972

**Not shipped (documented in DS-3):**
- `01_results.md` unchanged — no narrative update for GBT model-eval
- Dashboard PNGs (Charts 16-18) not re-rendered from updated CSVs
- All model-eval CSVs contain only `contract=pass` rows (pre-existing limitation:
  `bid_n_sq` derived feature missing from eval parquet)

**PR:** [#980](https://github.com/Questuart/Bid-Euchre/pull/980)
