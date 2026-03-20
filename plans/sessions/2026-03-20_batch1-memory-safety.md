# Batch 1 — memory.py Data Safety

**Date:** 2026-03-20
**Goal:** Close remaining data safety gaps in `memory.py` (#950 residual, #1002). #951 is already fully fixed.

## Current State

| Issue | Status | Evidence |
|-------|--------|----------|
| #950 | **Partially fixed** | `MemoryStore.from_dict()` skips bad entries (line 106-116, test at line 88). BUT `load_memory()` still returns empty store on `json.JSONDecodeError` (line 162), and the next `save_memory()` would persist that empty store, permanently losing data. |
| #951 | **Fully fixed** | `save_memory()` uses tempfile+fsync+replace (line 179-194). 3 tests cover it (lines 143-235). |
| #1002 | **Not fixed** | No `flock()` anywhere in memory.py. `add_entry()` and `remove_entry()` do load→modify→save without locking. |

## Plan

### Fix 1: Backup corrupt file before returning empty (#950 residual)

**File:** `src/bid_euchre/ops/memory.py`, `load_memory()` (line 159-164)

**Change:** When `json.JSONDecodeError` is caught, rename the corrupt file to
`memory.json.corrupt.<ISO-timestamp>` before returning an empty store. This
preserves the corrupt data for manual recovery and prevents the next write
from silently overwriting it.

```python
# Before (current):
except (json.JSONDecodeError, KeyError, TypeError) as e:
    logger.warning("Failed to load curated memory: %s", e)
    return MemoryStore()

# After:
except json.JSONDecodeError as e:
    # Preserve corrupt file for recovery before returning empty store
    backup = memory_path.with_suffix(
        f".corrupt.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    try:
        memory_path.rename(backup)
        logger.warning(
            "Corrupt memory file backed up to %s: %s", backup.name, e
        )
    except OSError as rename_err:
        logger.warning(
            "Failed to backup corrupt memory (%s): %s", rename_err, e
        )
    return MemoryStore()
except (KeyError, TypeError) as e:
    logger.warning("Failed to load curated memory: %s", e)
    return MemoryStore()
```

### Fix 2: Add flock around read-modify-write cycle (#1002)

**File:** `src/bid_euchre/ops/memory.py`

**Design:** Add a `_locked_update()` context manager that:
1. Opens/creates a `.lock` file in memory_dir
2. Acquires `fcntl.flock(LOCK_EX)` on it
3. Yields the loaded `MemoryStore`
4. On context exit, saves the store and releases the lock

**Why a separate lock file?** The main `memory.json` file is replaced
atomically via `os.replace()` — can't hold a flock on a file that gets
replaced. A dedicated `.lock` file persists across writes.

**Functions to update:**
- `add_entry()` — use `_locked_update()` instead of load→modify→save
- `remove_entry()` — use `_locked_update()` instead of load→modify→save

**Read-only functions (no lock needed):**
- `load_memory()` — reads are safe with atomic writes (either old or new content)
- `get_entry()`, `list_entries()`, `search_entries()` — all call `load_memory()`

```python
import fcntl
from contextlib import contextmanager
from typing import Generator

LOCK_FILE = ".memory.lock"

@contextmanager
def _locked_update(memory_dir: Path) -> Generator[MemoryStore, None, None]:
    """Context manager for exclusive read-modify-write on the memory store."""
    memory_dir.mkdir(parents=True, exist_ok=True)
    lock_path = memory_dir / LOCK_FILE
    with open(lock_path, "w") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            store = load_memory(memory_dir)
            yield store
            save_memory(store, memory_dir)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
```

### Tests to Add

1. **test_load_backs_up_corrupt_file** — Write invalid JSON, call `load_memory()`,
   verify `.corrupt.*` file exists and contains the original bytes.
2. **test_load_corrupt_backup_failure** — Corrupt file + readonly dir,
   verify warning logged but no crash.
3. **test_locked_update_basic** — Verify `_locked_update()` loads, modifies, saves.
4. **test_locked_update_creates_lock_file** — Verify `.memory.lock` file is created.
5. **test_concurrent_add_entry** — Use threading to verify two concurrent `add_entry()`
   calls don't lose writes.

## Files Changed

- `src/bid_euchre/ops/memory.py` — 2 fixes, ~40 lines added
- `tests/unit/test_ops_memory.py` — 5 new tests, ~80 lines

## Scope Boundary

- Only `memory.py` and its tests
- Compaction bugs (#954, #959) are Batch 3 — not touched here
- Events flock race (#938) is Batch 3 — not touched here

## Outcome
<!-- Filled after implementation -->
- PR: pending
- Notes: pending
