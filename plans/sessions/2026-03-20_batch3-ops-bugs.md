# Batch 3 — Ops Bugs

**Date:** 2026-03-20
**Goal:** Fix 3 remaining ops bugs: worktree --force passthrough (#967), symlink containment in compaction (#959), and flock/rename race in event draining (#938). #954 already fixed — closed.

## Current State

| Issue | Status | File |
|-------|--------|------|
| #967 | Not fixed | `src/bid_euchre/ops/worktrees.py` |
| #959 | Not fixed | `src/bid_euchre/ops/compaction.py` |
| #938 | Not fixed | `src/bid_euchre/ops/events.py` |
| #954 | ~~Already fixed~~ | Closed — cleanup logic + test on main |

## Plan

### Fix 1: Pass --force to git worktree remove (#967)

**File:** `src/bid_euchre/ops/worktrees.py`, `archive_worktree()` (~line 800)

**Problem:** `force=True` only bypasses the dirty check at line 771, but the
`git worktree remove` command at line 800 never includes `--force`. Git itself
rejects removal of dirty worktrees without `--force`.

**Change:**
```python
# Before:
cmd = ["git", "worktree", "remove", worktree_path]

# After:
cmd = ["git", "worktree", "remove"]
if force:
    cmd.append("--force")
cmd.append(worktree_path)
```

**Test:** `test_archive_worktree_passes_force_flag` — mock subprocess.run,
verify `--force` is in the command when `force=True` and absent when `False`.

---

### Fix 2: Symlink containment in delete_archive (#959)

**File:** `src/bid_euchre/ops/compaction.py`, `delete_archive()` (~line 323)

**Problem:** `_validate_session_id()` prevents `..` traversal in the string,
but a symlink inside `archive_dir` with a valid session_id name could point
outside. `shutil.rmtree()` follows the symlink and deletes the target.

**Change:** After resolving `session_dir`, verify it is still inside
`archive_dir`:
```python
def delete_archive(session_id: str, archive_dir: Path | None = None) -> bool:
    _validate_session_id(session_id)
    if archive_dir is None:
        archive_dir = DEFAULT_ARCHIVE_DIR
    session_dir = archive_dir / session_id

    # Symlink containment: resolved path must be inside archive_dir
    resolved = session_dir.resolve()
    if not str(resolved).startswith(str(archive_dir.resolve()) + "/"):
        logger.warning("Refusing to delete %s: resolves outside archive dir", session_dir)
        return False

    if not session_dir.exists():
        return False
    ...
```

**Test:** `test_delete_archive_rejects_symlink_escape` — create a symlink
inside archive_dir pointing outside, verify delete_archive returns False.

---

### Fix 3: Separate lock file for events (#938)

**File:** `src/bid_euchre/ops/events.py`

**Problem:** `append_event()` locks the events file itself. `drain_events()`
also locks the events file, then renames it. A concurrent `append_event`
that opened the file before the rename blocks on the old inode; when drain
releases, append writes to the old (now unlinked) inode — data loss.

**Root cause:** Both sides lock the data file, but rename replaces the inode,
making the locks on separate objects after the rename.

**Change:** Add a dedicated `LOCK_FILE = ".events.lock"` (same pattern as
memory.py Batch 1). Both `append_event` and `drain_events` lock this file
instead of the data file.

```python
LOCK_FILE = ".events.lock"

def append_event(...):
    ...
    events_dir.mkdir(parents=True, exist_ok=True)
    lock_path = events_dir / LOCK_FILE
    events_file = events_dir / EVENTS_FILE
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(events_file, "a") as f:
                f.write(json.dumps(event, sort_keys=True) + "\n")
                f.flush()
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
    ...

def drain_events(...):
    ...
    lock_path = events_dir / LOCK_FILE
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            # read, filter, write tmp, rename, archive — all under same lock
            ...
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
```

**Test:** Existing `test_drain_serializes_with_concurrent_append` should
continue to pass. Add `test_append_after_drain_rename_not_lost` — verify
that an event appended after drain's rename is not lost.

---

## Files Changed

| File | Change |
|------|--------|
| `src/bid_euchre/ops/worktrees.py` | --force passthrough |
| `src/bid_euchre/ops/compaction.py` | symlink containment check |
| `src/bid_euchre/ops/events.py` | separate lock file |
| `tests/unit/test_ops_worktrees.py` | 1 new test (or test_ops_cli.py) |
| `tests/unit/test_ops_compaction.py` | 1 new test |
| `tests/unit/test_ops_events.py` | 1 new test |

## Scope Boundary

- Only worktrees.py, compaction.py, events.py and their tests
- No index.py changes (Batch 2, author-b)
- No memory.py changes (Batch 1, PR #1005)

## Outcome
<!-- Filled after implementation -->
- PR: pending
- Notes: pending
