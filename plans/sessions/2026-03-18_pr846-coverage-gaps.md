<!-- review-tier: small -->
# Session Plan: PR #846 Post-Merge Coverage Gaps

**Date:** 2026-03-18
**Trigger:** Post-merge review of PR #846 (`fix: resolve 3 follow-up issues (#830, #833, #840)`)
**Lane:** TBD (author-a or author-b)
**PR Strategy:** Single PR — test-only, no production code changes

## Post-Merge Review Summary

PR #846 merged cleanly. Architecture and correctness reviews passed clean.
Coverage review found 2 WARN-level gaps and 2 INFO-level edge cases.

## Confirmed Findings

### WARN-1: Flat-schema `elif` branch untested in `run()`

**File:** `scripts/internal/generate_interpretability_charts.py` (lines 359–369)
**Confirmed:** ✅ Real gap

PR #846 added a new `elif` branch in `run()` that handles `feature_importances.csv`
with the flat schema (`model, contract, feature_name, importance` — no `rank` column).
This branch synthesizes rank via `groupby().rank(ascending=False, method="first")`.

Existing tests exercise:
- SHAP summary path (`test_run_charts_from_csvs`)
- Ranked importance via `selection_paths.csv` (`test_run_dispatches_importance_schema`)
- Ranked importance via `feature_importances.csv` (`test_run_prefers_feature_importances_csv`)
- Selection path schema (`test_run_dispatches_selection_path_schema`)

**None write a flat-schema CSV** (no `rank` column) to `feature_importances.csv` and
verify `run()` still produces `feature_importance.png` via the rank-synthesis path.

### WARN-2: Step 6 dual-write (both CSVs) not asserted together

**File:** `src/bid_euchre/arc_d_v2/tables.py` (step 6, ~line 1053)
**Confirmed:** ✅ Real gap

Step 6 now writes both `feature_importances.csv` AND `selection_paths.csv` in a single
call for backward compatibility. Two existing tests each check one file:
- `test_chart_data_includes_feature_importances` → asserts `feature_importances.csv` + ranked schema
- `test_selection_paths_from_training_artifacts` → asserts `selection_paths.csv`

**No test asserts both files are produced in the same call.** A regression that drops
one write while keeping the other would go undetected.

### INFO-1: Docstring "Pass 1.5" label is misleading (cosmetic)

**File:** `tests/unit/test_codex_plan_review_adapter.py` line 239
**Confirmed:** ✅ Cosmetic only

The `TestParsePlanFindingsReversedFormat` class docstring references "Pass 1.5"
as a label, but no code path is labeled "Pass 1.5" — the reversed format is handled
by `_FINDING_LINE_RE.search()`. The behavior works; the explanation is just imprecise.

### INFO-2: No reversed-format test without line number

**File:** `tests/unit/test_codex_plan_review_adapter.py`
**Confirmed:** ✅ Real edge case gap, low risk

All 4 reversed-format tests include line numbers (`:42`, `:90-95`, `:10`, `:25`).
No test covers the variant `— src/foo.py` (without `:N` suffix). The underlying
regex in `_FINDING_LINE_RE` handles this case, but it's not exercised.

## Fix Plan

### Fix 1: Test flat-schema branch in `run()`

**File:** `tests/unit/test_interpretability.py`
**Class:** `TestChartGeneration`
**New test:** `test_run_dispatches_flat_importance_schema`

Write a `feature_importances.csv` with flat schema (no `rank` column) to
`chart_data_dir`, invoke `run()`, and assert:
1. `"feature_importance.png" in generated`
2. Output file exists
3. No crash from rank synthesis

This covers WARN-1 and implicitly exercises the rank synthesis edge cases
(INFO-3 from original review).

### Fix 2: Assert dual-write in step 6

**File:** `tests/unit/test_rung_tables.py`
**Class:** `TestExtractFeatureImportancesFlat`
**Modify:** `test_chart_data_includes_feature_importances`

After the existing assertions, additionally assert:
1. `"selection_paths.csv" in generated` (backward compat write)
2. Both files have identical content (same DataFrame)

This covers WARN-2.

### Fix 3: Add no-line-number reversed-format test

**File:** `tests/unit/test_codex_plan_review_adapter.py`
**Class:** `TestParsePlanFindingsReversedFormat`
**New test:** `test_reversed_format_no_line_number`

Input: `- [P1] Missing docs — src/bid_euchre/foo.py\n`
Assert: finding parsed, `line` is None or 0, file is `src/bid_euchre/foo.py`.

This covers INFO-2.

### Fix 4: Fix "Pass 1.5" docstring (cosmetic)

**File:** `tests/unit/test_codex_plan_review_adapter.py`
**Change:** Update class docstring to say "which handles reversed format via
`_FINDING_LINE_RE`" instead of referencing "Pass 1.5".

This covers INFO-1.

## Files Changed

| File | Change Type |
|------|-------------|
| `tests/unit/test_interpretability.py` | Add 1 new test |
| `tests/unit/test_rung_tables.py` | Extend 1 existing test |
| `tests/unit/test_codex_plan_review_adapter.py` | Add 1 new test + fix docstring |

## Validation

- Tier 1: `uv run python -m pytest tests/unit/test_interpretability.py tests/unit/test_rung_tables.py tests/unit/test_codex_plan_review_adapter.py -x -q`
- Tier 2: `make check-quiet` before PR

## Outcome

_To be filled after implementation._
