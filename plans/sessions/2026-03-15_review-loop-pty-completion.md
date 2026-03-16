<!-- review-tier: small -->
# Review Loop PTY Completion

**Date:** 2026-03-15
**Goal:** Apply PTY fix to PR review adapter, reduce max iterations 5→3 for both loops, close stale fallback issues.

## Steps

### Step 1: Apply PTY fix to PR review adapter (#730)

In `scripts/internal/codex_review_adapter.py`:
1. Update `invoke_codex_cli()` to use `_run_with_pty()` from `codex_plan_review_adapter.py`
2. Add `codex` marker extraction for PTY output
3. Update 7 tests in `tests/unit/test_codex_review_adapter.py` to mock `_run_with_pty` instead of `subprocess.run`

### Step 2: Reduce max iterations 5→3

- `scripts/internal/plan_review_driver.py` — `run_plan_review_loop()` default `max_iter=5` → `max_iter=3`
- `scripts/internal/review_driver.py` — find `max_iterations` default and change 5→3
- Update any docs/constants that reference the iteration cap

### Step 3: Close stale fallback issues

Close #713, #714, #728 — these were created by the plan review fallback when Codex timed out. Root cause fixed in #722.

### Step 4: Validate

```bash
uv run python -m pytest tests/unit/test_codex_review_adapter.py tests/unit/test_codex_plan_review_adapter.py tests/unit/test_plan_review_driver.py -v
make check-quiet
```

## Files Changed

- `scripts/internal/codex_review_adapter.py` — PTY invocation
- `scripts/internal/plan_review_driver.py` — max_iter 5→3
- `scripts/internal/review_driver.py` — max_iterations 5→3
- `tests/unit/test_codex_review_adapter.py` — mock updates

## Outcome
<!-- Filled after implementation -->
