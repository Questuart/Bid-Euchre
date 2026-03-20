# Batch D — Unify CI Classifiers

## Issue

#1036: Two CI classification systems answer "is this check name a real CI check?" with opposite defaults:

1. **`CI_CHECK_NAMES`** in `github_pr_state.py` — fail-closed allowlist. New CI jobs not in the set are invisible to the review loop.
2. **`classify_check()`** in `ops/__init__.py` — fail-open denylist. New CI jobs default to "ci".

Risk: a new CI workflow job not added to `CI_CHECK_NAMES` is invisible to the review loop, which could merge PRs while the new check is failing.

## Fix

**Option 1 (chosen):** Make `github_pr_state.py` use `classify_check()` — the fail-open denylist becomes the single source of truth.

### Changes

**`scripts/internal/github_pr_state.py`:**
- Remove the `CI_CHECK_NAMES` import and fallback definition (lines 146-152)
- Import `classify_check` from `bid_euchre.ops` instead
- Change `get_ci_status()` to use `classify_check()`:
  ```python
  # Before:
  ci_checks = [c for c in checks if c.get("name") in _CI_CHECK_NAMES]

  # After:
  ci_checks = [c for c in checks if classify_check(c.get("name", "")) == "ci"]
  ```
- Update the fallback for import failure to inline the logic

**`src/bid_euchre/ops/__init__.py`:**
- Keep `CI_CHECK_NAMES` but add a deprecation docstring comment
- No behavioral change — it's still exported for backward compat

**`tests/unit/test_check_classifier.py`:**
- Update `TestConsistencyWithGithubPrState` to verify `github_pr_state` uses `classify_check()` instead of `CI_CHECK_NAMES`
- Add a drift-detection test: assert every name in `CI_CHECK_NAMES` classifies as "ci"

**`tests/unit/test_github_pr_state.py`:**
- Add test verifying new CI jobs (unknown check names) are included by default
- Add test verifying advisory/review-gate checks are excluded

## Files
- `scripts/internal/github_pr_state.py` — CI status polling
- `src/bid_euchre/ops/__init__.py` — classify_check, CI_CHECK_NAMES
- `tests/unit/test_check_classifier.py` — classifier tests
- `tests/unit/test_github_pr_state.py` — PR state tests (if exists, else create)

## Validation
```bash
uv run python -m pytest tests/unit/test_check_classifier.py tests/unit/test_github_pr_state.py -v
make check-quiet
```

## Outcome
<!-- Filled after implementation -->
