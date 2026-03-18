# HALT+SKIP test and ADVANCE recommendation text
**Date:** 2026-03-18
**Goal:** Address two post-merge review findings from PR #796: add missing HALT+SKIP test and fix ADVANCE text when hypotheses are skipped.

## Plan
- Add `test_halt_when_fail_plus_skips` test with statuses `["PASS", "FAIL", "SKIP"]` asserting `**HALT**` in output — locks behavior that SKIP does not mask a real FAIL
- Fix `generate_decision_report` (lines 574-578) to count SKIPs and emit "All evaluated hypothesis checks passed (N skipped)" when skips > 0
- Update existing `test_advance_when_passes_plus_skips` assertion to verify recommendation mentions skipped count

## Files
- `tests/unit/test_rung_report.py` — add `test_halt_when_fail_plus_skips`, update `test_advance_when_passes_plus_skips` assertion
- `src/bid_euchre/arc_d_v2/report.py` — fix ADVANCE recommendation text in `generate_decision_report`

## Outcome
<!-- Filled after implementation -->
- PR: pending
- Notes: issue #797
