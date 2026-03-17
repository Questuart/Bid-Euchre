<!-- review-tier: small -->
# Fix #799: Plan Review Parser — Unparseable Output Bug

**Date:** 2026-03-17
**Issue:** [#799](https://github.com/Questuart/Bid-Euchre/issues/799)

## Problem

Plan review loop returns `NOT_READY` with "Unparseable output" when Codex CLI
produces valid but unrecognized response format. Codex completed successfully
(56.5s, exit 0, 218 chars) but output didn't match `_CLEAN_REVIEW_PATTERNS`.

## Root Causes

1. **`_CLEAN_REVIEW_PATTERNS` too narrow** — Missing common clean-review phrasings
2. **Raw output not persisted** — Sidecar and state don't include raw Codex output,
   making failed parses impossible to debug
3. **`output_dir` not passed** — `run_plan_review_loop` passes `base_dir` (which is
   often `None`) as `output_dir`, so `_save_raw_output` is a no-op

## Changes

### 1. Expand `_CLEAN_REVIEW_PATTERNS` (`codex_review_adapter.py`)
Add patterns:
- "no significant issues", "no blockers", "no major issues", "no critical issues"
- "everything looks/checks out", "I found no issues", "I don't see any issues"
- "no violations", "good to go", "ready to merge", "no action needed"
- "passes all checks", "the code/plan/changes is/are correct"
- "satisfactory", "nothing stands out", "no problems detected"
- "well-structured" / "well-organized" as standalone positive assessment

### 2. Persist raw output in sidecar (`plan_review_driver.py`)
- Pass `plan_review_state_dir(key, base_dir)` as `output_dir`
- Track last raw_output through the loop
- Add `## Raw Output` section to sidecar review file

### 3. Tests
- New clean-review pattern tests in `test_codex_review_adapter.py`
- Test raw output in sidecar in `test_plan_review_driver.py`
- Test output_dir passed correctly

## Outcome

_(filled after implementation)_
