# Session Plan: Post-Merge Test Hardening (PRs #843–#845)

**Date:** 2026-03-18
**Lane:** author-d
**Branch:** `fix/post-merge-chart-test-hardening`

## Context

Post-merge review of PRs #843, #844, #845 produced 18 findings across 9
review agents. After cross-referencing every finding against the actual
codebase on `origin/main` (post-rebase), **11 of 18 are false positives**
(referencing functions that don't exist, stale checkouts, or misidentified
code paths). The remaining 7 are genuine gaps — 2 correctness issues and 5
missing test paths.

## Finding Triage

### False positives (NO action)

| # | Original Finding | Why False |
|---|-----------------|-----------|
| 844-#1 | PRELIMINARY triage `data_sanity FAIL` path | `_build_preliminary_triage` does not exist in codebase |
| 844-#2 | Tests don't pass explicit `mode=` | Tests at `test_rung_report.py:167,292` already pass `mode="QUICK"` and `mode="FULL"` |
| 844-#3 | `_to_repo_relative` returncode | Function does not exist in codebase |
| 844-#5 | Unknown mode value untested | `mode` is a display string; no validation logic to test |
| 844-#6 | `_build_preliminary_triage` no-facet-column | Function does not exist |
| 844-#7 | `_to_repo_relative` error handling | Function does not exist |
| 843-#2 | All non-bid action_type empty fallback | `_extract_outcome_distributions_from_parquet` does not filter by `action_type`; filtering happens upstream in `generate_all_tables` |
| 843-#3 | `.status` sidecar dead artifact | `lifecycle.py:_write_status` writes `status.json` which IS consumed by `list_runs`, `_get_lifecycle_status`, and `manifest.py:_get_lifecycle_status` |
| 843-#4 | No test .status NOT written for clean runs | `.status` is lifecycle management, not parquet-related |
| 843-#5 | Parquet without action_type column | Extraction function doesn't use `action_type` |
| 844-#4 | Stale absolute paths in evidence_manifest.json | Machine paths in committed JSON are cosmetic; `_inventory_dir` uses Path objects for local ops |

### Genuine findings — correctness fixes (2)

| ID | Severity | File | Description |
|----|----------|------|-------------|
| C1 | MEDIUM | `generate_rung_charts.py:863,877` | "synthetic data" annotation fires on real-but-sparse data (≤2 unique `tricks_won`, no `source` column). Label should be "sparse data" unless `source=="synthetic"`. |
| C2 | MEDIUM | `generate_rung_charts.py:898-920` | Standalone Chart 9: when `raw_data` is empty (all counts=0 in violin path), axes get xlabel="Model" and ylabel="Tricks Won" with nothing drawn. Should call equivalent of `_unavailable_panel`. |

### Genuine findings — test coverage gaps (5)

| ID | Severity | Target Function | Missing Path |
|----|----------|----------------|--------------|
| T1 | HIGH | `generate_dashboard_health` Panel 4 (line 1742) | No test provides `bid_level+count` schema to dashboard health |
| T2 | HIGH | `generate_dashboard_health` Panel 3 (line 1714) | No test exercises `raw_data` empty-dict → `_unavailable_panel` fallback |
| T3 | HIGH | `_extract_outcome_distributions_from_parquet` (line 1343) | No test for parquet with `tricks_won` but no contract column → returns `[]` |
| T4 | MEDIUM | `generate_dashboard_health` Panel 3 (line 1676) | No test provides `source="synthetic"` data to dashboard Panel 3 |
| T5 | MEDIUM | `_extract_outcome_distributions_from_parquet` (line 1367) | Fraction sum-to-1 invariant not asserted in existing parquet tests |

## Implementation Plan

### Step 1: Correctness fix — sparse annotation label (C1)

**File:** `scripts/internal/generate_rung_charts.py`
**Lines:** 863, 876-877

Change the annotation text from `"synthetic data"` to `"sparse data"` when
the trigger is `tricks_won.nunique() <= 2` but `is_synthetic` is False.
Keep `"synthetic data"` when `is_synthetic` is True.

```python
# Line 863: condition stays the same
if is_synthetic or cdf["tricks_won"].nunique() <= 2:
    # ...existing bar code...
    annotation = "synthetic data" if is_synthetic else "sparse data"
    ax.annotate(annotation, ...)
```

### Step 2: Correctness fix — empty raw_data fallback (C2)

**File:** `scripts/internal/generate_rung_charts.py`
**Lines:** 898-920

Add an `else` clause after `if raw_data:` to render a fallback. In the
standalone chart, use `ax.text()` centered message (matching
`_unavailable_panel` pattern, but standalone chart functions don't call
the dashboard helper).

```python
if raw_data:
    # ...existing violin+box code...
else:
    ax.text(0.5, 0.5, "Insufficient data", ...)
    ax.set_xticks([])
    ax.set_yticks([])
```

### Step 3: Test — dashboard health Panel 4 with bid_level+count schema (T1)

**File:** `tests/unit/test_rung_charts.py`
**Class:** `TestDashboardHealthOutcomeDistributions` (add new test)

Create `chart_data/bid_levels.csv` with `model, contract, bid_level, count`
schema. Verify `generate_dashboard_health` returns True and produces PNG.

### Step 4: Test — dashboard health Panel 3 empty raw_data fallback (T2)

**File:** `tests/unit/test_rung_charts.py`
**Class:** `TestDashboardHealthOutcomeDistributions` (add new test)

Provide `outcome_distributions.csv` with all `count=0` (real/parquet source,
many tricks_won). Verify `generate_dashboard_health` still returns True
(degrades gracefully via `_unavailable_panel`).

### Step 5: Test — parquet extraction missing contract column (T3)

**File:** `tests/unit/test_rung_tables.py`
**Class:** New `TestExtractOutcomeDistributionsFromParquet`

Create parquet with `tricks_won` and `model` but NO contract column
(`contract_family`, `contract_type`, `contract` all absent). Verify function
returns `[]`.

### Step 6: Test — dashboard health Panel 3 synthetic path (T4)

**File:** `tests/unit/test_rung_charts.py`
**Class:** `TestDashboardHealthOutcomeDistributions` (add new test)

Provide `outcome_distributions.csv` with `source="synthetic"` and few
tricks_won bins. Verify `generate_dashboard_health` returns True and the
chart renders the synthetic bar path (title includes "synthetic").

### Step 7: Test — parquet extraction fraction invariant (T5)

**File:** `tests/unit/test_rung_tables.py`
**Class:** New `TestExtractOutcomeDistributionsFromParquet` (same as Step 5)

Assert that within each `(model, contract)` group the `fraction` values sum
to 1.0 (within float tolerance).

### Step 8: Test — standalone Chart 9 sparse annotation label (C1 test)

**File:** `tests/unit/test_rung_charts.py`
**Class:** `TestOutcomeDistributionsViolin` (add new test)

Provide data with ≤2 unique tricks_won but NO `source` column. Verify the
chart renders successfully (bar path). This tests the corrected annotation
doesn't crash and the sparse-but-not-synthetic path works.

### Step 9: Validation

```bash
uv run python -m pytest tests/unit/test_rung_charts.py tests/unit/test_rung_tables.py -v
make check-quiet
```

## Files Changed

| File | Change Type |
|------|-------------|
| `scripts/internal/generate_rung_charts.py` | Fix (sparse annotation, empty raw_data) |
| `tests/unit/test_rung_charts.py` | New tests (T1, T2, T4, C1-test) |
| `tests/unit/test_rung_tables.py` | New tests (T3, T5) |

## Scope Boundary

- **In scope:** 2 correctness fixes + 6 new tests covering the 7 genuine findings
- **Out of scope:** Chart 20 registry doc update (WARNING finding — separate PR if pursued)
- **Out of scope:** Stale paths in committed evidence_manifest.json (cosmetic)
- **Out of scope:** All 11 false-positive findings

## Outcome

_To be filled after implementation._
