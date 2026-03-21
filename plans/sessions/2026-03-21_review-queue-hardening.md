# Review Queue Hardening — Follow-up from PR #1181

**Date:** 2026-03-21
**Branch:** `fix/review-queue-hardening`
**Issues:** #1182 (H1), #1183 (H2), #1184 (H3)

## Summary

Fix three hardening issues discovered during PR4 (atomic cutover) review:

1. **#1182 H1: Atomic verdict writes** — `write_verdict()` and `write_request()` use
   `path.write_text()` which is not crash-safe. `read_verdict()` / `read_request()`
   lack `JSONDecodeError` handling.

2. **#1183 H2: Stuck `running` verdicts** — Runner crash after writing `running` verdict
   leaves PR unprocessable. Need staleness timeout for re-claiming.

3. **#1184 H3: Dual verdict writers** — Both `review_driver.py` and `review_lane_runner.py`
   write to the same `verdict.json`. Use `lane_id` discrimination so the merge guard
   and operator tooling can tell who wrote the verdict.

## Design

### H1: Atomic writes

Pattern from `memory.py` (PR #951): `tempfile.mkstemp` → `os.write` → `os.fsync` →
`os.replace`. Add `_atomic_write_json(path, data)` helper in `review_queue.py`.

For reads: wrap `json.loads()` in `try/except (json.JSONDecodeError, ValueError)`
returning `None`.

### H2: Stuck running verdicts

In `find_pending_requests()`, treat `running` verdicts older than 15 minutes as
re-claimable. Use the verdict's `created_at` ISO timestamp for age calculation.

### H3: Dual writer discrimination

The `write_verdict()` already accepts `lane_id`. The `ReviewVerdict` dataclass
doesn't carry a `writer` field though. Add a `writer` field to `ReviewVerdict`
(optional, defaults to empty string for backward compat). Both `review_driver.py`
and `review_lane_runner.py` already pass `lane_id` — thread it through to the
verdict data.

## Files

- `src/bid_euchre/ops/review_queue.py` — atomic writes, read error handling, writer field
- `scripts/internal/review_lane_runner.py` — stuck-running re-claim logic
- `tests/unit/test_review_queue.py` — tests for atomic writes, corrupt reads, stuck running
- `tests/unit/test_review_lane_runner.py` — test re-claim logic

## Validation

- [ ] Corrupt verdict JSON → `read_verdict()` returns None (not crash)
- [ ] `write_verdict()` uses temp+fsync+replace
- [ ] `running` verdict older than 15min is re-claimable
- [ ] `ReviewVerdict` carries `writer` field from `lane_id`
- [ ] `make check` passes

## Outcome

<!-- Filled after implementation -->
