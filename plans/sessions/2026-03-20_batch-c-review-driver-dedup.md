# Batch C: Review Driver Dedup Hardening

**Date:** 2026-03-20
**Issue:** #1043
**Branch:** `fix/review-driver-dedup-hardening`

## Problem

In `scripts/internal/review_driver.py`, the `_create_follow_up_issues()` function
has a dedup guard (lines 159-190) with two defects:

1. **Broad exception catch:** `except (json.JSONDecodeError, Exception) as e:` --
   `Exception` subsumes `json.JSONDecodeError`, making the tuple redundant. More
   critically, catching all exceptions silently swallows transient `gh` failures
   (network timeout, auth issues), proceeding to issue creation and potentially
   creating duplicates.

2. **Quiet logging:** `logger.debug(...)` is too quiet for a dedup failure --
   should be `logger.warning(...)` so operators see it.

## Fix

### review_driver.py (line 189-190)

Replace:
```python
except (json.JSONDecodeError, Exception) as e:
    logger.debug("Dedup check failed, proceeding with creation: %s", e)
```

With:
```python
except (json.JSONDecodeError, subprocess.CalledProcessError, OSError) as e:
    logger.warning("Dedup check failed, proceeding with creation: %s", e)
```

Rationale:
- `json.JSONDecodeError` -- malformed `gh` output
- `subprocess.CalledProcessError` -- `gh` exits non-zero (already imported)
- `OSError` -- file/network-level failures (e.g., `gh` not found)
- Unexpected errors (TypeError, KeyError, etc.) will now propagate, surfacing bugs

### Tests (new file: `tests/unit/test_review_driver_dedup.py`)

1. **test_dedup_catches_subprocess_error** -- Mock `subprocess.run` to raise
   `CalledProcessError` on the `gh issue list` call. Verify it catches gracefully
   and proceeds to issue creation.

2. **test_dedup_catches_json_error** -- Mock `subprocess.run` to return garbage
   stdout. Verify `json.JSONDecodeError` is caught and proceeds.

3. **test_dedup_does_not_catch_unexpected_error** -- Mock `subprocess.run` to raise
   `TypeError`. Verify the exception propagates (is NOT caught).

## Validation

```bash
uv run python -m pytest tests/unit/test_review_driver_dedup.py -v
make check-quiet
```

## Outcome

- PR: (to be filled)
- Closes: #1043
