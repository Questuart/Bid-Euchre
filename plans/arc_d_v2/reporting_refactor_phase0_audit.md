# Phase 0: Reporting Pipeline Audit — Reconciliation Note

**Date:** 2026-03-18
**Author:** author-b
**Status:** COMPLETE

## Context

This audit examines the 9 chart_data extraction items referenced in the
reporting refactor plan: whether extraction functions exist, whether they
work with current artifact schemas, and whether they are wired into the
orchestration pipeline (steps 6/7).

---

## Item-by-Item Reconciliation

### 1. predictions.csv

| Property | Status |
|----------|--------|
| Extraction function | ✅ `generate_model_eval_csvs()` at `tables.py:1673` |
| Called by orchestration? | ✅ Via `generate_all_tables()` at line 2491 (step 6) |
| Data source | Loads joblib model files + eval parquet, runs predictions live |
| Training artifacts contain raw predictions? | **NO** — only summary metrics (R², MAE, n_train, n_val, feature_importances) |

**⚠️ COLUMN MISMATCH GAP:** The function looks for `actual` column in
parquet (`actual_col = "actual" if "actual" in family_df.columns else None`),
but `action_value.parquet` uses `tricks_won` (not `actual`). The function
silently skips when `actual` is absent. The fixture parquet confirms:
`['hand_id', 'deal_id', 'focal_seat', 'action_type', 'contract_family',
'bid_n', 'trump_suit', 'net_points', 'tricks_won', ...]` — no `actual`
column.

**Fix required:** Add fallback: `actual_col = "actual" if "actual" in
df.columns else ("tricks_won" if "tricks_won" in df.columns else None)`.

### 2. residuals.csv

Same function and same gap as predictions.csv (`generate_model_eval_csvs()`).
Residuals are computed as `preds - actuals` from the same live prediction path.

**Fix:** Same column mapping fix as predictions.csv.

### 3. calibration_bins.csv

Same function and same gap as predictions.csv. Calibration bins use
prediction deciles from the same live predictions.

**Fix:** Same column mapping fix as predictions.csv.

### 4. seat_balance.csv

| Property | Status |
|----------|--------|
| Extraction function | ✅ `generate_seat_balance_csv()` at `tables.py:1595` |
| Called by orchestration? | ✅ Via `generate_all_tables()` at line 2485 (step 6) |
| Data source | Reads action_value.parquet, groups by seat × contract_family |
| Parquet available? | ✅ Discovered at `rung_dir/seed_<s>/datasets/action_value.parquet` |

**⚠️ COLUMN MISMATCH GAP:** Function checks `seat_col = "seat" if "seat"
in df.columns else None`. The fixture parquet uses `focal_seat`, not `seat`.
The function returns `None` when `seat_col is None`, so it silently skips.

**Fix required:** Add fallback: check for `focal_seat` as an alternative
column name. The function already has flexible column detection for
`contract_family`/`contract_type` and `tricks_won`/`actual`, but misses
the `seat`/`focal_seat` variant.

### 5. bid_levels.csv

| Property | Status |
|----------|--------|
| Extraction function | ✅ `_extract_bid_levels()` at `tables.py:1133` |
| Called by orchestration? | ✅ Via `generate_chart_data()` at line 1035 (step 6) |
| Data source | Comparator CIs JSON — aggregate bid_rate, make_rate, pass_rate |
| Per-bid-level counts available? | **NO** |

**Known limitation (documented in code):** "Per-bid-level distributions are
not available in battery JSONs" (tables.py:1136). The function extracts
aggregate metrics only (bid_rate, make_rate, pass_rate per model). For true
bid-level distributions (e.g., count of 6H vs 7H vs 8H bids), the
comparator and H2H battery JSONs do not store per-level breakdowns.

**No fix needed for Phase 1** — this is a data availability constraint, not
a code bug. A future enhancement could add per-level tracking to the
comparator battery pipeline.

### 6. decision_comparison.csv

**Two independent extraction paths exist:**

| Path | Location | Wired? | Productive on current schema? |
|------|----------|--------|------------------------------|
| A: `_extract_decision_comparison()` | `tables.py:1461` | ✅ via `generate_chart_data()` (step 6) | ❌ Non-productive |
| B: `generate_decision_comparison()` | `generate_interpretability.py:424` | ✅ via step 3b | ✅ Productive |

**Path A (tables.py):** Wired through `generate_chart_data()` at line 1071,
which is called by `generate_all_tables()` (step 6). However, it requires
parquet with `bid_decision` + `model` + `deal_id` columns. The current
`action_value.parquet` schema has none of these — it stores raw features
and outcomes, not per-model bid decisions. The `_load_and_merge_pairwise()`
helper checks for these columns and logs an info message when absent, but
produces no output. **Currently non-productive on the available parquet
schema**, unless a future pipeline produces per-model-labeled parquet files.

**Path B (interpretability):** Loads joblib GBT models from artifacts,
runs live predictions on eval data to determine each model's "best action",
then compares pairwise. Requires ≥2 GBT artifacts. This is wired via
step 3b (interpretability) and writes to `chart_data/`. This is currently
the **only productive path** for decision_comparison.csv.

**Note:** Path A is not dead code in the strict sense — it is wired and
would activate if the parquet schema were extended with `bid_decision` and
`model` columns. It is better characterized as *dormant*: correctly wired
but non-productive under the current data contract.

### 7. disagreement_outcomes.csv

Same dual-path situation as decision_comparison.csv:

| Path | Location | Wired? | Productive on current schema? |
|------|----------|--------|------------------------------|
| A: `_extract_disagreement_outcomes()` | `tables.py:1492` | ✅ via `generate_chart_data()` (step 6) | ❌ Non-productive |
| B: Part of `generate_decision_comparison()` | `generate_interpretability.py:424` | ✅ via step 3b | ✅ Productive |

**Path A** is wired at line 1079 via `generate_chart_data()`, but requires
`bid_decision` + `model` + `tricks_won` columns in parquet — currently
non-productive (same dormant status as decision_comparison Path A).
**Path B** produces disagreement_outcomes from live model predictions.
Only Path B is currently productive.

### 8. cross_rung_progression.csv

| Property | Status |
|----------|--------|
| Extraction function | ✅ `generate_cross_rung_progression()` at `tables.py:1558` |
| Called by orchestration? | **❌ NOT wired** |
| Data source | Dict of rung_label → comparator CIs JSON (multi-rung) |

**GAP:** This function exists but is never called by `generate_all_tables()`
or any orchestration step. It requires comparator CIs from multiple rungs,
which means it's a cross-rung aggregation that belongs in a post-pipeline
step (after all rungs complete). No current script calls it.

**Fix required:** Wire this into the final lineage report generation or add
a cross-rung step to the orchestration pipeline.

### 9. outcome_distributions.csv

| Property | Status |
|----------|--------|
| Extraction function | ✅ `_extract_outcome_distributions()` at `tables.py:1210` |
| Called by orchestration? | ✅ Via `generate_chart_data()` at line 1055 (step 6) |
| Data source | Primary: parquet (true histogram), Fallback: H2H battery (summary) |

**Partially working:** When `parquet_paths` are available, the function
reads `tricks_won` histograms grouped by contract_family — the parquet
path should work correctly since `tricks_won` and `contract_family`
columns are present in `action_value.parquet`. When parquet is absent,
it falls back to H2H battery summary data (which is per-matchup summary,
not per-deal distribution).

**⚠️ UNVERIFIED AT BUNDLE LEVEL:** While the code path is correct for the
available parquet schema, we have not yet verified that regenerated bundles
(QUICK or FULL) actually exercise the parquet-backed real-data path vs.
falling back to the H2H summary path. The existing QUICK bundles we've
reviewed may still contain synthetic/summary data. This needs verification
during Phase 1 by inspecting a regenerated bundle's `outcome_distributions.csv`
to confirm it contains per-deal histogram bins (many rows per contract) rather
than one-row-per-contract summary metrics.

---

## Summary: Working vs Broken chart_data Items

| CSV | Extraction exists? | Wired? | Actually produces data? | Fix needed? |
|-----|-------------------|--------|------------------------|-------------|
| predictions.csv | ✅ | ✅ | ❌ `actual` column mismatch | Column fallback |
| residuals.csv | ✅ | ✅ | ❌ Same mismatch | Column fallback |
| calibration_bins.csv | ✅ | ✅ | ❌ Same mismatch | Column fallback |
| seat_balance.csv | ✅ | ✅ | ❌ `seat`/`focal_seat` mismatch | Column fallback |
| bid_levels.csv | ✅ | ✅ | ✅ Aggregate only | None (data limitation) |
| decision_comparison.csv | ✅ (2 paths) | ✅ | ✅ Via interpretability only (tables.py path dormant) | Decide: remove dormant path or extend parquet schema |
| disagreement_outcomes.csv | ✅ (2 paths) | ✅ | ✅ Via interpretability only (tables.py path dormant) | Same as above |
| cross_rung_progression.csv | ✅ | ❌ | ❌ Never called | Wire into pipeline |
| outcome_distributions.csv | ✅ | ✅ | ⚠️ Unverified at bundle level | Verify parquet path is hit in regenerated bundles |

## Key Answers to Phase 0 Questions

### Q1: Do training artifacts store raw predictions?
**No.** Training artifacts (`training_artifact_*.json`) contain:
- Top-level: `schema_version`, `target`, `risk_mode`, `models`, `metadata`
- Per-model: `model_file` (joblib path), `feature_names`, `r_squared`, `mae`,
  `n_train`, `n_val`, `feature_importances`
- No raw prediction arrays. Predictions must be computed on-the-fly from
  loaded joblib models + eval parquet.

### Q2: Are parquet sources available for seat_balance?
**Yes.** The `action_value.parquet` files exist at
`rung_dir/seed_<s>/datasets/action_value.parquet` and contain `tricks_won`
and `contract_family` columns. But the `seat` column is named `focal_seat`
in the parquet schema, causing a silent skip.

### Q3: Do H2H/comparator artifacts contain per-bid-level counts?
**No.** Comparator CIs contain aggregate `bid_rate` and `make_rate` per model,
not per-bid-level (e.g., 6H vs 7H vs 8H) breakdowns.

### Q4: Does the interpretability pipeline produce decision_comparison and disagreement_outcomes?
**Yes.** `generate_interpretability.py` step 3b produces both CSVs from live
model predictions. This is the **only currently productive path**. The parallel
extraction in `tables.py` (`_extract_decision_comparison`,
`_extract_disagreement_outcomes`) is wired through `generate_chart_data()` but
is dormant — non-productive on the current parquet schema (which lacks
`bid_decision` and `model` columns). These functions would activate if the
parquet schema were extended.

### Q5: Which chart_data files have extraction functions not wired into orchestration?
**One:** `generate_cross_rung_progression()` exists but is never called by
any orchestration step or script.

### Q6: Can QUICK advance checks be produced during regeneration?
**Yes.** Step 8 (`execute_step_8`) calls `generate_advance_check.py` with
`--mode` and `--tables-dir` pointing to the correct mode-specific directory.
The advance check reads `hypotheses.json` + tables CSVs to produce
`advance_check.json`. This is fully wired and works for both QUICK and FULL
modes identically.

---

## Prioritized Fix List for Phase 1

1. **Column naming mismatches (3 functions, ~10 lines each):**
   - `generate_model_eval_csvs()`: `actual` → fallback to `tricks_won`
   - `generate_seat_balance_csv()`: `seat` → fallback to `focal_seat`
   - Enables predictions.csv, residuals.csv, calibration_bins.csv, seat_balance.csv

2. **Wire `generate_cross_rung_progression()`:** Either add to
   `generate_all_tables()` or create a post-pipeline aggregation script.

3. **Verify outcome_distributions at bundle level:** Confirm that a
   regenerated bundle's `outcome_distributions.csv` exercises the
   parquet-backed path (many-row histogram) rather than falling back to
   the H2H summary path (one-row-per-contract).

4. **Dormant extractor decision:** The `_extract_decision_comparison()` and
   `_extract_disagreement_outcomes()` functions in tables.py are wired but
   dormant (non-productive on the current parquet schema). Options:
   - Leave dormant (no harm — they degrade gracefully with an info log)
   - Remove to reduce maintenance surface
   - Extend parquet schema with `bid_decision` + `model` to activate them

---

## Outcome

Phase 0 audit is complete. Phase 1 implementation produced 3 PRs:

| PR | Title | Status | Fixes |
|----|-------|--------|-------|
| [#834](https://github.com/Questuart/Bid-Euchre/pull/834) | fix: add column fallbacks for chart_data CSV generation | Open | Items 1-4 (predictions, residuals, calibration, seat_balance column mismatches) |
| [#837](https://github.com/Questuart/Bid-Euchre/pull/837) | fix: wire dataset paths for parquet-backed chart_data generation | Open | Item 9 root cause (parquet discovery path mismatch) + enables parquet-backed outcome_distributions |
| [#838](https://github.com/Questuart/Bid-Euchre/pull/838) | fix: wire cross_rung_progression CLI + annotate dormant extractors | Open | Item 8 (cross_rung unwired) + Items 6-7 (dormant extractor docstrings) |

### Root cause discovery (Phase 1 finding)

During Phase 1, investigation of outcome_distributions revealed a deeper
issue than initially diagnosed. The Phase 0 audit flagged it as "unverified
at bundle level." Investigation confirmed ALL bundles use `source=synthetic`
because of a **parquet discovery path mismatch**:

- **Step 1** generates datasets at `data/runs/arc_d_v2/base_datasets/pre_r3/<mode>/seed_<ds_seed>/`
- **Step 6** looked for parquet at `data/artifacts/arc_d_v2/<rung>/seed_<s>/datasets/`
- Training artifacts (JSON + joblib) are copied to the artifacts dir (step 3), but **parquet files are never copied**
- Additionally, dataset seeds (1001+) differ from training seeds (42, 123, 456)

PR #837 fixes this by passing actual dataset directory paths from step 6
to `generate_all_tables()` via a new `dataset_dirs` parameter.
