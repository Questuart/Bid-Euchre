# Medium Fixture Plan

<!-- review-tier: medium -->

**Date:** 2026-03-17
**Status:** FIXTURE
**Scope:** Test fixture for review infrastructure QUICK/FULL tests

---

## Problem

The frobnication pipeline has three known issues:

1. **Timeout handling:** The widget processor times out after 30s but the
   retry logic uses `time.sleep(60)` which exceeds the timeout window.
2. **Missing validation:** Input data is not validated before processing,
   leading to silent corruption of output files.
3. **Hardcoded paths:** Several file paths are hardcoded to `/tmp/data/`
   which fails on CI environments.

## Steps

### PR 1: Fix timeout handling
- Update `src/bid_euchre/strategy/frobnicate.py` to use 15s sleep
- Add retry counter with max 3 attempts
- Add unit test for timeout scenario

### PR 2: Add input validation
- Add schema validation in `src/bid_euchre/core/validate.py`
- Wire validation into the pipeline entry point
- Add property tests for schema edge cases

### PR 3: Remove hardcoded paths
- Replace `/tmp/data/` with `pathlib.Path` from config
- Update all 5 call sites
- Add integration test with temp directory

## Files
- `src/bid_euchre/strategy/frobnicate.py`
- `src/bid_euchre/core/validate.py`
- `src/bid_euchre/core/pipeline.py`
- `tests/unit/test_frobnicate.py`
- `tests/unit/test_validate.py`
- `tests/integration/test_pipeline.py`

## Validation

```bash
uv run python -m pytest tests/unit/test_frobnicate.py -v
uv run python -m pytest tests/ -k pipeline
make check-quiet
```

## Outcome
<!-- Filled after implementation -->
- PR: (fixture — not implemented)
