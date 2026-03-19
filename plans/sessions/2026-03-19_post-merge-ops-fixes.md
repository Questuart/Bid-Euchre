# Session Plan: Post-Merge Ops Fixes

**Date:** 2026-03-19
**Scope:** Fix 4 validated findings from post-merge review of PRs #940, #961, #994
**Branch:** fix/post-merge-ops-findings
**Issues:** #989, #990, #991, #992

## Validation Summary

| # | Issue | Severity | Validated? | Notes |
|---|-------|----------|-----------|-------|
| 1 | #989 — Path traversal in `update_task_scope`/`get_task_scope` | HIGH | **YES** | `task_id` used in `f"{task_id}.json"` (L408, L468) with no validation. `compaction.py:110-115` has `_validate_session_id()` that rejects `..`, `/`, `\` — same pattern should apply here. |
| 2 | #992 — Standalone CLI scripts untested | HIGH | **PARTIAL** | `build_audit_index.py`, `build_curated_memory.py`, `compact_session_context.py` are CLI wrappers in `scripts/internal/`. Their library functions are tested, but `main()` argument parsing, error paths, and output formatting are not. Scope-reduce: test `main()` entrypoints only, not full E2E. |
| 3 | #990 — Missing fsync in `update_task_scope` | MEDIUM | **YES** | Uses `Path.write_text() + Path.rename()` (L441-442). The same package's `compaction.py` uses `os.write + os.fsync + os.replace` pattern (committed one PR earlier). Inconsistent but low-probability data loss. |
| 4 | #991 — CI poller timeout no failure event | MEDIUM | **YES** | `check_ci_stuck()` (watchdogs.py:313-398) only reads `ci_failure` and `ci_success` events (L350). No `ci_timeout` event type exists in `VALID_EVENT_TYPES`. The timeout codepath in CI polling doesn't emit an event the watchdog can detect. |
| 5 | Dead code in lane-activity state derivation | MEDIUM | **YES** | `synthesize_lane_activity()` has `state = "unknown"` as final else-branch, but the conditions `has_active_session` / `not has_active_session` are exhaustive booleans. `LANE_STATES` frozenset includes `"unknown"` but it can never be assigned by this logic. |

## Plan

### Fix 1: Path traversal validation (#989) — `status.py`

**What:** Extract a `_validate_task_id()` function (or reuse pattern from `compaction._validate_session_id`) and call it at the top of both `update_task_scope()` and `get_task_scope()`.

**Files:**
- `src/bid_euchre/ops/status.py` — add validation to L400 and L465
- `tests/unit/test_ops_status.py` — add tests for path traversal rejection

**Implementation:**
```python
def _validate_task_id(task_id: str) -> None:
    """Validate task_id contains no path traversal sequences."""
    if not task_id or ".." in task_id or "/" in task_id or "\\" in task_id:
        raise ValueError(
            f"Invalid task_id {task_id!r}: must not contain path separators or '..'"
        )
```

Call at the top of both `update_task_scope()` and `get_task_scope()`.

### Fix 2: CLI script test coverage (#992) — new test file

**What:** Add `tests/unit/test_ops_cli.py` with tests for each CLI script's `main()` function.

**Wait — `test_ops_cli.py` already exists.** Check what's in it and extend.

**Files:**
- `tests/unit/test_ops_cli.py` — add tests for `build_audit_index.main()`, `build_curated_memory.main()`, `compact_session_context.main()`
- These scripts are in `scripts/internal/` and use `_repo_utils` for repo root.

**Test approach:** Import `main()` from each script, call with `argv=["--help"]` or minimal args to exercise argument parsing and error paths. Use `monkeypatch` to mock the library functions they delegate to.

### Fix 3: Fsync in `update_task_scope` (#990) — `status.py`

**What:** Replace `Path.write_text() + Path.rename()` with `os.open + os.write + os.fsync + os.close + os.replace` pattern, consistent with `compaction.py`.

**Files:**
- `src/bid_euchre/ops/status.py` — update L439-442
- `tests/unit/test_ops_status.py` — existing atomic write test covers this

### Fix 4: Add `ci_timeout` event type (#991) — `events.py` + `watchdogs.py`

**What:**
1. Add `"ci_timeout"` to `VALID_EVENT_TYPES` in `events.py`
2. Update `check_ci_stuck()` in `watchdogs.py` to also check for `ci_timeout` events
3. Add test for timeout event detection

**Files:**
- `src/bid_euchre/ops/events.py` — add to `VALID_EVENT_TYPES` frozenset
- `src/bid_euchre/ops/watchdogs.py` — update L350 filter
- `tests/unit/test_ops_watchdogs.py` — add timeout event test

### Fix 5: Remove dead `"unknown"` state branch (#994) — `status.py`

**What:** Remove the unreachable `else: state = "unknown"` branch. The `LANE_STATES` frozenset should remain (it documents valid states including "unknown" which is the dataclass default), but the derivation logic should not pretend the branch is reachable.

**Files:**
- `src/bid_euchre/ops/status.py` — remove dead else branch (around L338 in diff)
- `tests/unit/test_ops_status.py` — add tests for `synthesize_lane_activity()` state derivation

## Parallelism Assessment

**Fix 1 + Fix 3** touch the same file (`status.py`) and same function area — must be **sequential** (or combined in one pass).

**Fix 2** (CLI tests) is fully **independent** — different files entirely.

**Fix 4** (`events.py` + `watchdogs.py`) is fully **independent** of fixes 1/3/5.

**Fix 5** touches `status.py` — must be **sequenced** with fixes 1/3.

**Execution order:**
1. Fixes 1 + 3 + 5 combined (all in `status.py` + tests)
2. Fix 4 (events + watchdogs) — can run in parallel with #1
3. Fix 2 (CLI tests) — can run in parallel with #1 and #4

Since this is a single-author lane, execute serially: 1→4→2, then run `make check`.

## Acceptance Criteria

- [ ] `_validate_task_id()` rejects `../etc/passwd`, `/tmp/evil`, `..\\windows`
- [ ] `update_task_scope` uses `os.fsync + os.replace` pattern
- [ ] `ci_timeout` is a valid event type
- [ ] `check_ci_stuck()` detects `ci_timeout` events
- [ ] Dead `else: state = "unknown"` branch removed
- [ ] CLI `main()` functions have basic test coverage
- [ ] `make check` passes
- [ ] Tests for `synthesize_lane_activity()` state derivation exist

## Outcome

_To be filled after implementation._
