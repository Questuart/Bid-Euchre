# Fix #967 + #959: ops bugs — force flag and symlink containment

## Context

Two remaining bugs from triage Batch 3. Issues #954 and #938 were already fixed
(closed). These are the two that still need code changes.

## Issue #967 — archive_worktree --force not passed to git

**File:** `src/bid_euchre/ops/worktrees.py`, line 801
**Current:** `["git", "worktree", "remove", worktree_path]`
**Problem:** `force=True` parameter is accepted but never passed to the git command.

### Fix

```python
cmd = ["git", "worktree", "remove", worktree_path]
if force:
    cmd.append("--force")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
```

### Test

Add `test_archive_passes_force_flag` to `TestArchiveWorktree` — mock
`subprocess.run`, call with `force=True`, verify `--force` is in the command.

**Note:** Can't test with a real dirty worktree in unit tests (requires git
repo setup). Mocking `subprocess.run` is the practical approach, matching
existing test patterns in the file.

## Issue #959 — delete_archive follows symlinks without containment check

**File:** `src/bid_euchre/ops/compaction.py`, line 338
**Current:** `shutil.rmtree(session_dir)` without checking resolved path.
**Problem:** A symlink inside the archive dir could point outside, and rmtree
would follow it and delete the target.

### Fix

Add resolve check before rmtree:

```python
session_dir = archive_dir / session_id
if not session_dir.exists():
    return False

# Defence-in-depth: verify resolved path stays inside archive_dir (#959)
if not session_dir.resolve().is_relative_to(archive_dir.resolve()):
    logger.warning(
        "Refusing to delete %s: resolved path escapes archive directory",
        session_dir,
    )
    return False
```

### Test

Add `test_delete_archive_rejects_symlink_escape` to `TestPathTraversal` —
create a symlink inside archive_dir pointing to a target outside, verify
`delete_archive()` returns False and the target is NOT deleted.

## Files changed

| File | Change |
|------|--------|
| `src/bid_euchre/ops/worktrees.py` | Add `--force` to git command when `force=True` |
| `src/bid_euchre/ops/compaction.py` | Add resolve containment check in `delete_archive()` |
| `tests/unit/test_ops_worktrees.py` | Add `test_archive_passes_force_flag` |
| `tests/unit/test_ops_compaction.py` | Add `test_delete_archive_rejects_symlink_escape` |

## Validation

- `uv run python -m pytest tests/unit/test_ops_worktrees.py tests/unit/test_ops_compaction.py -v` (Tier 1)
- `make check-quiet` (Tier 2, before PR)

## Outcome

_(To be filled after implementation)_
