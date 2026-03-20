# Batch 4 — CI Classifier Input Mismatch

**Date:** 2026-03-20
**Goal:** Align `classify_review_mode()` file detection patterns with CI workflow's `dorny/paths-filter` to prevent review mode misclassification (#934).

## Problem

The review driver's `classify_review_mode()` determines review mode (STANDARD
vs REPORT_AUDIT vs PLAN_AUDIT) by checking if changed files end with `.py` and
start with `src/`, `scripts/`, or `tests/`.

The CI workflow's `dorny/paths-filter` uses broader patterns for "code":
- `src/**`, `scripts/**`, `tests/**`, `experiments/**`
- `Makefile`, `pyproject.toml`, `.github/workflows/ci.yml`

**Mismatch:** A PR that changes only `pyproject.toml` + `docs/04_reports/`
would be classified as REPORT_AUDIT by the review driver, but CI runs full
tests because paths-filter treats `pyproject.toml` as "code". The review
mode determines which prechecks and Codex prompts are used, so a mismatch
could cause insufficient review for infrastructure-affecting changes.

## Fix

Align `classify_review_mode()` with CI's paths-filter patterns:

```python
# Before:
has_code = any(
    f.endswith(".py")
    and (f.startswith("src/") or f.startswith("scripts/") or f.startswith("tests/"))
    for f in changed_files
)

# After — aligned with CI paths-filter (see .github/workflows/ci.yml):
_CODE_PREFIXES = ("src/", "scripts/", "tests/", "experiments/", ".github/workflows/")
_CODE_EXACT = ("Makefile", "pyproject.toml")

has_code = any(
    any(f.startswith(p) for p in _CODE_PREFIXES) or f in _CODE_EXACT
    for f in changed_files
)
```

Also add a comment cross-referencing the CI workflow for future maintenance.

## Files Changed

| File | Change |
|------|--------|
| `scripts/internal/review_driver.py` | Broaden `classify_review_mode()` patterns |
| `tests/unit/test_review_driver.py` | Add tests for non-.py code detection |

## Test Plan

1. `test_classify_review_mode_pyproject` — `pyproject.toml` triggers STANDARD
2. `test_classify_review_mode_makefile` — `Makefile` triggers STANDARD
3. `test_classify_review_mode_experiments` — `experiments/configs/foo.yaml` triggers STANDARD
4. Existing tests continue to pass

## Scope Boundary

- Only `review_driver.py` and its tests
- No CI workflow changes
- No `ci.py` changes (that module classifies failures, not file types)

## Outcome
<!-- Filled after implementation -->
