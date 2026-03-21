# Post-Merge Review Fixes (Batch 5)

**Date:** 2026-03-20
**Branch:** `fix/post-merge-batch-5`
**Scope:** Fix validated findings from 20-PR post-merge review (#982–#1013)

## Context

A comprehensive review of the last 20 merged PRs produced 22 findings.
Validation against the codebase confirmed 14 as actionable, dismissed 3 as
false positives, and found 3 already resolved. This plan addresses all
confirmed actionable findings in a single focused PR.

## Findings to Fix

### HIGH (2 confirmed)

| # | File | Issue | Fix |
|---|------|-------|-----|
| F1 | `src/bid_euchre/ops/memory.py` | `_locked_update()` saves unconditionally even for no-op mutations, polluting `last_updated` timestamps | Add snapshot comparison: hash `store.to_dict()` before yield, skip `save_memory()` if unchanged |
| F2 | `src/bid_euchre/ops/scheduler.py` | `daemon()` consecutive error counter conflates `tick_result.errors` (warnings) with exceptions. 3 watchdog warnings shutdown daemon identically to 3 crashes | Only increment `consecutive_errors` on actual exceptions (the `except Exception` path). Treat `tick_result.errors` as non-fatal — log them but don't count toward consecutive shutdown threshold |

### MEDIUM (4 actionable)

| # | File | Issue | Fix |
|---|------|-------|-----|
| F10 | `src/bid_euchre/ops/memory.py` | Concurrent corruption backup produces misleading "Failed to backup" log when second process finds file already renamed | Improve log message to distinguish "file already renamed (concurrent recovery)" from "genuine backup failure" |
| F17 | `tests/unit/test_ops_index.py` | Direct `_STALENESS_TTL_SECONDS` assignment (line 1038, 1082) instead of `monkeypatch` — no cleanup on test failure | Replace with `monkeypatch.setattr()` |
| F19 | `tests/unit/test_ops_status.py` | No direct test for `_is_newer_session(malformed_candidate, valid_existing)` branch | Add test covering the malformed-candidate + valid-existing case (line 345-346 of status.py) |
| F22 | `tests/unit/test_ops_memory.py` | Inconsistent mock patch path: `patch("os.replace", ...)` (line 200) vs `patch("bid_euchre.ops.memory.os.replace", ...)` (line 230) | Normalize to qualified path `bid_euchre.ops.memory.os.replace` |

### LOW (deferred to follow-up issues)

These are confirmed but not worth fixing in this PR to maintain scope discipline:

- **F14**: `agent_ops/` forward reference in CLAUDE.md — intentional, tracked by governing plan
- **F16**: `_check_staleness` default `index_dir=None` bypasses cache — intentional design
- **F20**: `bid_behavior_panel` regeneration without documented rationale — cosmetic

### Not fixed (false positives / resolved)

- **F4**: Manifest-to-disk 2.5× mismatch — FALSE POSITIVE (sizes match)
- **F11**: `TYPE_CHECKING` guard on `RetryPolicy` — FALSE POSITIVE (no such guard)
- **F18**: Fragile `Path.write_text` patch — FALSE POSITIVE (not found in codebase)
- **F15**: Nested symlinks in archive dirs — RESOLVED in PR #959
- **F21**: Stale `arc_d/` path in skill — RESOLVED (already `arc_d_v2/`)

## Implementation Details

### F1: `_locked_update()` dirty-check

**File:** `src/bid_euchre/ops/memory.py`, lines 225-251

**Approach:** Snapshot the store's serializable state before yielding. After
yield, compare. Only call `save_memory()` if the store changed. Use
`json.dumps(store.to_dict(), sort_keys=True)` for stable comparison.

```python
@contextmanager
def _locked_update(memory_dir: Path) -> Generator[MemoryStore, None, None]:
    memory_dir.mkdir(parents=True, exist_ok=True)
    lock_path = memory_dir / LOCK_FILE
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            store = load_memory(memory_dir)
            snapshot = json.dumps(store.to_dict(), sort_keys=True)
            yield store
            if json.dumps(store.to_dict(), sort_keys=True) != snapshot:
                save_memory(store, memory_dir)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
```

**Tests to add:**
- `test_locked_update_no_op_skips_save`: verify `save_memory` is not called
  when no mutations occur
- `test_locked_update_mutation_saves`: verify `save_memory` IS called when
  store is modified (regression guard)
- `test_remove_nonexistent_no_timestamp_change`: verify `last_updated` is
  unchanged after removing a nonexistent entry

### F2: Scheduler error conflation fix

**File:** `src/bid_euchre/ops/scheduler.py`, lines 358-362

**Current:**
```python
if tick_result.errors:
    result.errors.extend(tick_result.errors)
    consecutive_errors += 1
else:
    consecutive_errors = 0
```

**Fixed:** Move `consecutive_errors = 0` to always execute on successful tick
(i.e., no exception), regardless of whether `tick_result.errors` has warnings.

```python
# Successful tick — reset consecutive error counter
consecutive_errors = 0
if tick_result.errors:
    result.errors.extend(tick_result.errors)
```

**Tests to add:**
- `test_daemon_warnings_do_not_trigger_shutdown`: 5 consecutive ticks each
  returning `tick_result.errors=["watchdog warning"]` must NOT trigger
  shutdown. Assert `result.stopped_reason == "max_iterations"` and
  `result.ticks_completed == 5`.

### F10: Concurrent corruption log message

**File:** `src/bid_euchre/ops/memory.py`, lines 174-178

**Current:**
```python
except OSError as rename_err:
    logger.warning(
        "Failed to backup corrupt memory file (%s): %s",
        rename_err,
        e,
    )
```

**Fixed:** Check if source file is already gone (concurrent recovery) vs
genuine failure:

```python
except OSError as rename_err:
    if not memory_path.exists():
        logger.info(
            "Corrupt memory file already recovered by another process: %s",
            e,
        )
    else:
        logger.warning(
            "Failed to backup corrupt memory file (%s): %s",
            rename_err,
            e,
        )
```

### F17: Monkeypatch for `_STALENESS_TTL_SECONDS`

**File:** `tests/unit/test_ops_index.py`, lines 1038 and 1082

Replace:
```python
idx_mod._STALENESS_TTL_SECONDS = 3600.0
# ... test body ...
idx_mod._STALENESS_TTL_SECONDS = 30.0
```

With monkeypatch (need to add `monkeypatch` fixture parameter):
```python
monkeypatch.setattr(idx_mod, "_STALENESS_TTL_SECONDS", 3600.0)
```

### F19: `_is_newer_session` malformed candidate test

**File:** `tests/unit/test_ops_status.py`

Add test near existing `test_session_selection_malformed_vs_valid`:
```python
def test_is_newer_session_malformed_candidate(self) -> None:
    """Malformed candidate loses to valid existing session."""
    from bid_euchre.ops.status import _is_newer_session

    malformed = {"started_at": "not-a-date"}
    valid = {"started_at": "2026-03-18T12:00:00+00:00"}
    assert not _is_newer_session(malformed, valid)
```

### F22: Normalize mock patch path

**File:** `tests/unit/test_ops_memory.py`, line 200

Change both unqualified patches in the same `with` block:
```python
patch("os.replace", side_effect=OSError("disk full")),
patch("os.close", side_effect=tracking_close),
```
To:
```python
patch("bid_euchre.ops.memory.os.replace", side_effect=OSError("disk full")),
patch("bid_euchre.ops.memory.os.close", side_effect=tracking_close),
```

## Files Changed

| File | Type | Changes |
|------|------|---------|
| `src/bid_euchre/ops/memory.py` | Fix | F1 (dirty-check), F10 (log message) |
| `src/bid_euchre/ops/scheduler.py` | Fix | F2 (error conflation) |
| `tests/unit/test_ops_memory.py` | Test | F1 tests, F22 (patch path) |
| `tests/unit/test_ops_scheduler.py` | Test | F2 test |
| `tests/unit/test_ops_index.py` | Test | F17 (monkeypatch) |
| `tests/unit/test_ops_status.py` | Test | F19 (malformed candidate test) |

## Validation

- Tier 1: `uv run python -m pytest tests/unit/test_ops_memory.py tests/unit/test_ops_scheduler.py tests/unit/test_ops_index.py tests/unit/test_ops_status.py -v`
- Tier 2: `make check-quiet` before PR

## Parallelism Assessment

All fixes are in disjoint files/areas:
- **Group A** (memory.py): F1, F10, F22 — same file cluster, must be sequential
- **Group B** (scheduler.py): F2 — independent
- **Group C** (test_ops_index.py): F17 — independent
- **Group D** (test_ops_status.py): F19 — independent

Groups A, B, C, D are independent write scopes. However, since this is
one bounded PR from a single author lane, sequential execution is simpler
and avoids merge conflicts. Total changes are small (~60 lines across 6
files) — parallelism overhead exceeds benefit.

**Decision:** Execute sequentially within this lane.

## Outcome

_To be filled after implementation._
