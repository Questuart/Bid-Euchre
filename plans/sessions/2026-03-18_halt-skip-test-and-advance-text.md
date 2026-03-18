# Session Plan: HALT+SKIP test and ADVANCE recommendation text

**Date:** 2026-03-18
**Issue:** #797
**Scope:** 2 files, 2 changes — small bounded fix

## Goal

Address two post-merge review findings from PR #796:
1. Add a missing test for HALT decision when FAILs coexist with SKIPs
2. Fix misleading ADVANCE recommendation text when hypotheses are skipped

## Changes

### 1. Add `test_halt_when_fail_plus_skips` test

**File:** `tests/unit/test_rung_report.py`
**Class:** `TestDecisionReport`

Add test with statuses `["PASS", "FAIL", "SKIP"]` → asserts `**HALT**` in output.
This locks the behavior that SKIP does not mask a real FAIL.

The logic is already correct in `_extract_advancement_decision` (line 383 filters
out SKIP, line 390 checks `n_fail > 0`), but no test exercises this specific
combination.

### 2. Fix ADVANCE recommendation text to account for skips

**File:** `src/bid_euchre/arc_d_v2/report.py`
**Function:** `generate_decision_report` (lines 574-578)

Current text (always):
> "All hypothesis checks passed. Evidence supports advancing to the next rung."

Fix: count SKIPs from `hypothesis_outcomes` DataFrame. When skips > 0:
> "All evaluated hypothesis checks passed (N skipped). Evidence supports advancing to the next rung."

When no skips, keep existing text unchanged.

### 3. Update existing test assertion

**File:** `tests/unit/test_rung_report.py`
**Test:** `test_advance_when_passes_plus_skips` (line 231)

Currently only checks `**ADVANCE**` is present. Add assertion that the
recommendation mentions skipped hypotheses (e.g., `"2 skipped"` for the
`["PASS", "PASS", "SKIP", "PASS", "SKIP"]` fixture).

## Validation

- `uv run python -m pytest tests/unit/test_rung_report.py -x -q`
- `make check-quiet` before PR

## Outcome

_To be filled after implementation._
