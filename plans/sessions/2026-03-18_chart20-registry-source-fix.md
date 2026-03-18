# Chart 20 Registry Source Fix

**Date:** 2026-03-18
**Status:** IN_PROGRESS
**Branch:** `codex/steward-author-d`

## Context

A Codex review of charting infrastructure produced 5 WARNING findings.
Validation against actual source code revealed **4 of 5 were invalid**
(the code already handles the described scenarios via fallbacks). Only
one finding is confirmed valid.

### Validated Findings

| # | Finding | Verdict | Evidence |
|---|---------|---------|----------|
| 1 | `generate_model_eval_csvs()` requires `actual` column | INVALID | Lines 1948-1952: already falls back `actual` → `tricks_won` |
| 2 | `generate_seat_balance_csv()` only accepts `seat` | INVALID | Lines 1753-1757: already falls back `seat` → `focal_seat` |
| 3 | `_extract_bid_levels()` only produces aggregate rates | INVALID | Lines 1151-1246: `_extract_bid_levels_from_parquet()` produces real bid-level frequency rows; aggregate is fallback only |
| 4 | Chart 20 registered against `selection_paths.csv` | **VALID** | Line 191: registry says `selection_paths.csv`, plan spec §7.10 says `feature_importances.csv` |
| 5 | Outcome distributions still uses grouped bars | INVALID | Lines 887-918: already uses violin+box for real data; bars only for synthetic/sparse fallback |

## Problem

Chart 20 (`feature_importance.png`) is registered in `chart_registry.py`
with `csv_source="chart_data/selection_paths.csv"`. The reporting refactor
plan §7.10 (line 520) and chart spec (line 301) both specify that Chart 20
should use `chart_data/feature_importances.csv`.

The chart *generator* code already prefers `feature_importances.csv` at
runtime (with fallback to `selection_paths.csv`), so charts render correctly.
But the registry metadata is wrong, which means:

- `00_manifest.md` inventory links Chart 20 to the wrong source
- Any tooling that uses registry metadata for validation/audit is misled
- The contract is internally inconsistent

## Fix

### Step 1: Fix chart_registry.py (1 line)

File: `src/bid_euchre/arc_d_v2/chart_registry.py`, line 191

```python
# Before
"chart_data/selection_paths.csv",

# After
"chart_data/feature_importances.csv",
```

### Step 2: Add registry contract test

File: `tests/unit/test_rung_charts.py`

Add a test verifying Chart 20's `csv_source` is `feature_importances.csv`.

### Step 3: Validate

- Tier 1: `test_rung_charts.py`, `test_rung_tables.py`, `test_rung_report.py`
- Tier 2: `make check-quiet`

## Risk

- **Low risk:** This is a metadata-only fix. The chart generator already
  prefers `feature_importances.csv` at runtime, so no behavioral change.
- **No regeneration needed:** Bundle regeneration is not required because
  this only affects the registry metadata used by manifest generation.

## Outcome

_To be filled after implementation._
