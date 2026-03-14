# PR #411 Review Fixes

Fixes 4 confirmed findings from the post-merge review of PR #411 (R0 reporting upgrade).

**Single PR, single branch:** `fix/pr411-review-fixes`

---

## Finding 1 (P0): Drift Detection Attribute Mismatch

**Root cause:** `compare_first_last_batch()` returns `BatchComparisonResult` with
fields `mannwhitney_stat` and `mannwhitney_pvalue` (`stats.py:24-25`), but the
notebook reads `.statistic` and `.p_value` which don't exist on that dataclass.

**File:** `notebooks/arc_d/02_r0_baseline.py` (lines 704-707)

**Fix:**
```python
# Before (broken):
f"Drift detection: statistic={batch_result.statistic:.4f}, "
f"p_value={batch_result.p_value:.4f}"
if batch_result.p_value < 0.05:

# After (fixed):
f"Drift detection: statistic={batch_result.mannwhitney_stat:.4f}, "
f"p_value={batch_result.mannwhitney_pvalue:.4f}"
if batch_result.mannwhitney_pvalue is not None and batch_result.mannwhitney_pvalue < 0.05:
```

Note: `mannwhitney_pvalue` is `Optional[float]`, so add a `not None` guard.

**Test:** Add `test_r0_notebook_drift_detection_attributes` — parse notebook source,
verify it references `mannwhitney_stat` and `mannwhitney_pvalue` (not `.statistic`
or `.p_value`) in the drift detection section.

---

## Finding 2 (P0): Comparator Battery Schema Mismatch

Two sub-issues:

### 2a: Bundle stores path string, not inline dict

**Root cause:** `rung_bundle_r0.json:57` has
`"comparator_battery": "data/artifacts/arc_d/r0/comparator_battery_r0.json"` —
a string path. Report code at `arc_d_report.py:352-353` does
`isinstance(comparator_battery, dict)` which is `False` for a string.

**Fix in `arc_d_report.py`:** When `comparator_battery` is a string, treat it
as a path relative to the bundle's parent directory and load the JSON file:

```python
comparator_battery = bundle.get("comparator_battery")
if isinstance(comparator_battery, str):
    # Bundle stores a path to the comparator battery JSON
    cb_path = Path(bundle_path).parent / Path(comparator_battery).name
    if not cb_path.exists():
        # Try repo-root-relative (bundle paths are repo-root-relative)
        cb_path = Path(comparator_battery)
    if cb_path.exists():
        import json as json_mod
        comparator_battery = json_mod.loads(cb_path.read_text())
```

**Fix in `02_r0_baseline.py`:** The notebook already has a fallback (lines 936-940)
that loads the standalone file. But the first path (line 933, reading from bundle)
needs the same path-resolution logic. Simpler fix: when the bundle value is a
string, resolve it and load:

```python
_comparator_data = _rung_bundle.get("comparator_battery")
if isinstance(_comparator_data, str):
    # Bundle stores a path reference — resolve and load
    _cb_path = Path(_comparator_data)
    if not _cb_path.exists() and ARTIFACT_DIR:
        _cb_path = Path(ARTIFACT_DIR) / Path(_comparator_data).name
    if _cb_path.exists():
        with open(_cb_path) as _f:
            _comparator_data = json.load(_f)
```

### 2b: JSON nests bidder metrics under `"bidders"` key

**Root cause:** `comparator_battery_r0.json` schema is:
```json
{"schema": "arc_d_comparator_v1", "seed": 42, "gate_status": "PASS",
 "bidders": {"fiveheadfred": {"net_eppd": -3.52}, ...}}
```

Both notebook (line 945) and report (line 358) iterate root keys, hitting
`schema`, `seed`, `gate_status`, `bidders`. Only `bidders` passes the
`isinstance(metrics, dict)` guard, producing one row with key "bidders".

**Fix:** In both notebook and report, after loading the JSON dict, drill into
`["bidders"]` if that key exists:

```python
if isinstance(comparator_battery, dict) and "bidders" in comparator_battery:
    comparator_battery = comparator_battery["bidders"]
```

This is backward-compatible: if the dict doesn't have a `"bidders"` key
(e.g., the test's inline format), it works as before.

---

## Finding 3 (P1): Matchup ID Parsing in Report

**Root cause:** `arc_d_report.py:390` uses `stem.split("_", 1)` which splits
on the first underscore. But log filenames are
`{run_id}_{matchup_id}.jsonl` where `run_id` itself contains many underscores
(e.g., `arc_d_r0_head_to_head_42_20260223_120000`).

**Correct pattern:** The matchup notebook (`03_r0_matchups.py:80-84`) already
does this correctly — it strips the run directory name prefix since the run_id
matches the directory name.

**Fix in `arc_d_report.py`:** Replace `split("_", 1)` with the directory-name
stripping pattern:

```python
run_dir_name = matchup_run_dir.name
# ...
stem = lf_path.stem
if stem.startswith(run_dir_name + "_"):
    mid = stem[len(run_dir_name) + 1:]
else:
    mid = stem
```

---

## Finding 4 (P2): Test Coverage Gaps

### 4a: Comparator battery test uses wrong schema

**Current:** `test_report_with_comparator_battery` (line 776) puts an inline dict
directly at `comparator_battery` key — doesn't test path-string resolution or
`bidders` nesting.

**Fix:** Add two new test variants:

1. `test_report_with_comparator_battery_path_string` — bundle has
   `"comparator_battery": "comparator_battery_r0.json"` (string path),
   actual JSON file written to `tmp_path` with `{"bidders": {...}}` schema.
   Verify report includes "## Comparator Battery" and actual bidder names.

2. `test_report_with_comparator_battery_nested_bidders` — bundle has
   inline dict with `{"schema": "...", "bidders": {...}}` schema.
   Verify report includes actual bidder names, not "bidders" as a row.

Keep existing test as-is (tests the backward-compatible inline format).

### 4b: Drift detection attribute test

**New:** `test_r0_notebook_drift_detection_attributes` — source inspection test
(same pattern as existing `test_r0_notebook_imports_diagnostics`).

### 4c: Matchup ID parsing test

**New:** `test_report_h2h_matchup_id_extraction` — write JSONL logs with
realistic filenames (`{run_id}_{matchup_id}.jsonl`) into a fake run directory
named `{run_id}`. Call `generate_arc_d_rung_report()` with `matchup_run_dir`.
Verify the report table contains the correct matchup_id labels (not corrupted
prefixes).

---

## Files Modified

| File | Change |
|------|--------|
| `notebooks/arc_d/02_r0_baseline.py` | Fix drift detection attrs (§7.7), fix comparator loading (§11) |
| `notebooks/arc_d/02_r0_baseline.ipynb` | Jupytext sync |
| `src/bid_euchre/reporting/arc_d_report.py` | Fix comparator path+schema, fix matchup ID parsing |
| `tests/unit/test_notebook_template_contract.py` | 1 new test (drift detection attrs) |
| `tests/unit/test_arc_d_reporting.py` | 3 new tests (comparator path, nested bidders, matchup ID) |

---

## Execution Order

1. Create worktree `fix/pr411-review-fixes`
2. Fix §7.7 drift detection attributes in notebook (Finding 1)
3. Fix comparator battery path resolution + `bidders` nesting in both
   `arc_d_report.py` and `02_r0_baseline.py` (Finding 2)
4. Fix matchup ID parsing in `arc_d_report.py` (Finding 3)
5. Add new tests (Finding 4)
6. Jupytext sync notebook
7. `make check`
8. Commit, push, create PR, merge

---

## Verification

```bash
# Full suite
make check

# Targeted test run
uv run python -m pytest tests/unit/test_arc_d_reporting.py -v -k "comparator or matchup"
uv run python -m pytest tests/unit/test_notebook_template_contract.py -v -k "drift"
```
