# Session: Upstream Model-Eval bid_n_sq Fix
**Date:** 2026-03-19
**Goal:** Remove the `contract=pass` limitation in model-eval CSVs by computing the missing `bid_n_sq` derived feature, then regenerate R0-R3/FULL bundles and narrow DS-2 to its exact blocker.

## Root Cause Analysis

### Goal 1: Contract-faceted model-eval (contract=pass only)

**Root cause confirmed:** `generate_model_eval_csvs()` in `tables.py` checks whether all features in a model's `feature_names` list exist as columns in the eval parquet. The `bid_n_sq` feature is a derived feature computed on-the-fly during training (see `train_action_value.py` line 409: `bid_n ** 2`), but is NOT stored in the parquet. It IS listed in every model's feature_names for suit/high/low contracts.

**Evidence:**
- All 5 models × 4 rungs × 3 non-pass contracts: `bid_n_sq` is the ONLY missing feature
- FULL parquet has `is_moon`, `is_loner`, `bid_n`, and all 69-73 other features
- Pass models don't need `bid_n_sq` (69 features vs 73 for suit) → pass rows work
- Suit/high/low: `len(available) != len(feature_names)` → `continue` → skipped

**Fix:** Compute `bid_n_sq = bid_n ** 2` in `generate_model_eval_csvs()` before the feature check, matching the pattern in `train_action_value.py`.

### Goal 2: Charts 21/22 (decision_comparison, disagreement_outcomes)

**Blockers identified (2):**

1. **Path mismatch:** `generate_interpretability.py` `_discover_artifacts()` looks in `rung_dir / "artifacts"` but actual artifact layout is `data/artifacts/arc_d_v2/<rung>/*.json` (no `artifacts/` subdir). Similarly, `_find_eval_dataset()` expects `rung_dir / "datasets"` but eval data is at `data/runs/arc_d_v2/base_datasets/...`.

2. **Single GBT model:** Decision comparison requires ≥2 GBT artifacts (line 716: `if len(gbt_infos) >= 2`), but only 1 GBT model exists per rung (`training_artifact_gbt_av.json` → `gbt_{suit,high,low,pass}.joblib`). This is a structural data limitation from the experiment pipeline, not a code bug.

**Conclusion:** DS-2 remains data-blocked. The correct action is to narrow the blocker description to "single-GBT-per-rung structural limitation." Path mismatch is a secondary issue that doesn't unblock Charts 21/22.

### Goal 3: R3/FULL parity

**Already resolved:** DS-4 was fixed by PR #972. R3/FULL now has Charts 1-20, 23 present (matching R0-R2/FULL). Confirmed in governing plan §16.

### Goal 4: Downstream regeneration

After the `bid_n_sq` fix:
- Regenerate predictions.csv, residuals.csv, calibration_bins.csv for R0-R3/FULL
- Update manifests to reflect new CSV sizes/content
- Narrow degraded-state language for DS-2 (cannot remove, but can make precise)
- Charts 16-18 (pred_vs_actual, residual_distribution, calibration_curve) will render richer data with suit/high/low facets

## Implementation Plan

### Step 1: Fix `generate_model_eval_csvs()` in `tables.py`
- Add `bid_n_sq` computation from `bid_n` before the per-model loop
- Pattern: `eval_df["bid_n_sq"] = eval_df["bid_n"] ** 2` (matching `train_action_value.py`)
- Location: after the `eval_df = pd.read_parquet(...)` line, before the model iteration

### Step 2: Add targeted test
- Test that `generate_model_eval_csvs()` produces suit/high/low rows given a parquet with `bid_n` but not `bid_n_sq`
- Use existing test fixture parquet or create minimal fixture

### Step 3: Regenerate R0-R3/FULL model-eval CSVs
- Use `generate_rung_tables.py` with `--dataset-dir` pointing to FULL parquet
- Verify CSVs now contain suit/high/low contract rows

### Step 4: Regenerate Charts 16-18 PNGs from richer data
- Use `generate_rung_charts.py` to render from updated chart_data

### Step 5: Update manifests and evidence manifests
- Update `00_manifest.md` with new CSV sizes
- Update `evidence_manifest.json` with file hashes

### Step 6: Narrow DS-2 wording
- Update governing plan DS-2 description to state exact blocker
- Keep DS-2 status as data-blocked but with precise cause

### Step 7: Validate
- Run targeted tests
- Run `make check-quiet`
- Verify CSVs have non-pass rows
- Verify charts render

## One PR Assessment

All changes share one conceptual boundary: "compute the missing derived feature and regenerate downstream." This fits cleanly in one PR:
- 1 code fix in `tables.py`
- 1 test addition
- Regenerated CSVs and charts (generated artifacts, not separate concepts)
- Narrowed plan language (bookkeeping)

## Parallelism Assessment

**Disjoint write scopes:**
- Main agent: `tables.py` fix, test, regeneration, manifest updates, PR
- Plan review agent: read-only review of this plan

**No parallel implementation agents needed** — the fix is 3 lines of code. The bulk of work is regeneration (automated) and validation.

## Outcome

**PR #TBD** — fix: compute bid_n_sq derived feature in model-eval, regenerate R0-R3/FULL

**What shipped:**
- `generate_model_eval_csvs()` now computes `bid_n_sq = bid_n ** 2` before model iteration
- Regression test `test_bid_n_sq_derived_enables_contract_facets` verifying all 4 contracts
- R0-R3/FULL model-eval CSVs regenerated: 95K rows × 4 contracts × 5 models each
- Charts 16-18 + dashboard_model_eval regenerated from richer contract-faceted data
- Evidence manifests and 00_manifest.md regenerated for all 4 FULL bundles
- DS-2 narrowed to exact blocker: single-GBT-per-rung structural limitation
- DS-3 `contract=pass` known limitation struck through and marked RESOLVED

**Degraded states after this PR:**
- DS-1 (QUICK synthetic distributions): retained — accepted intentional policy
- DS-2 (Charts 21/22 absent): retained but narrowed — single GBT model per rung
- DS-3 (GBT model-eval skipped): RESOLVED (PR #972 + PR #980 + this PR)
- DS-4 (R3/full stale): RESOLVED (PR #972)

**Fit in one PR:** Yes — single conceptual fix + automated downstream regeneration.

**Remaining blockers:** Charts 21/22 require ≥2 GBT models per rung. This is a structural experiment-pipeline limitation, not a code or parquet issue.
