# Review Batch Fixes — Post-Merge Review Findings

**Date:** 2026-03-18
**Goal:** Address remaining open findings from steward-review of PRs #878, #892, #888, #875 in a single scoped follow-up PR.

## Triage Summary

### Already Resolved
| Finding | Fixed By | Status |
|---------|----------|--------|
| #878 H2 (no file locking) | PR #902 (merged) | ✅ |
| #878 M3 (dead code `count_events`) | PR #902 (merged) | ✅ |
| #878 M5 (v1 role map fallback) | PR #902 (merged) | ✅ |
| #892 F1 (shell interpolation) | PR #902 (merged) | ✅ |
| #892 F5 (concurrent events) | PR #902 (shared with H2) | ✅ |
| #875 all findings | PRs #880, #901 | ✅ |
| #892 quarantine untracked + archive registry | PR #905 (open) | ⏳ |

### Accepted / Deferred
| Finding | Severity | Reason |
|---------|----------|--------|
| #878 H1 (drain crash duplication) | HIGH | Already documented in `drain_events()` docstring (PR #902). Accept as known limitation. |
| #878 M2 (read_events loads all) | MEDIUM | Optimization, not a defect. Would require API change. Log as follow-up. |
| #878 M7 (drain concurrent append) | MEDIUM | Related to H1 design. Same accept rationale. |
| #892 F6 (get_active_failures no resolution correlation) | LOW | Feature request, not a defect. Log as follow-up. |
| #892 F7 (TOCTOU registry race) | LOW | Low probability, internal tooling only. |

### Fixes in This PR

| # | Finding | Source | Severity | File(s) | Change |
|---|---------|--------|----------|---------|--------|
| 1 | H3: `is_worktree_dirty()` no path validation | #878 | HIGH | `worktrees.py` | Add existence + directory check before subprocess |
| 2 | F3: steward-ops missing from protected list | #892 | MEDIUM | `worktrees.py` | Add `Bid-Euchre-steward-ops` to `PROTECTED_WORKTREE_NAMES` |
| 3 | F4: quarantine path no error handling in prune | #892 | MEDIUM | `worktrees.py` | Add try/except matching the removal path pattern |
| 4 | F2: quarantine diff filename overwrites | #892 | MEDIUM | `worktrees.py` | Add timestamp suffix to diff filename |
| 5 | F8: archive_worktree missing dir confusing error | #892 | LOW→MED | `worktrees.py` | Improve error message when path doesn't exist |
| 6 | M1: reconcile() symlink false mismatch | #878 | MEDIUM | `worktrees.py` | Use `Path.resolve()` consistently (already done — verify) |
| 7 | 888-M: `active_sessions` misleading field name | #888 | MEDIUM | `status.py` | Rename to `recent_sessions` |
| 8 | 888-L1: No test for `events drain --json` | #888 | LOW | `test_ops_cli.py` | Add test for `--json` output |

## Implementation Details

### Fix 1: `is_worktree_dirty()` path validation (H3)

**File:** `src/bid_euchre/ops/worktrees.py`, line ~203

**Current:** Passes `worktree_path` directly to `git -C <path> status` without checking if path exists or is a directory. Missing path causes git failure → returns `True` (has changes) which is misleading.

**Change:**
```python
def is_worktree_dirty(worktree_path: str) -> bool:
    path = Path(worktree_path)
    if not path.is_dir():
        raise FileNotFoundError(
            f"Worktree path does not exist or is not a directory: {worktree_path}"
        )
    # ... existing subprocess call
```

**Test:** Add `test_is_worktree_dirty_missing_path` asserting `FileNotFoundError`.

### Fix 2: Add steward-ops to protection list (F3)

**File:** `src/bid_euchre/ops/worktrees.py`, line ~24

**Change:** Add `"Bid-Euchre-steward-ops"` to `PROTECTED_WORKTREE_NAMES` frozenset.

**Test:** Add assertion in existing `test_is_protected` test.

### Fix 3: Quarantine error handling in prune (F4)

**File:** `src/bid_euchre/ops/worktrees.py`, `prune_worktrees()`, line ~533

**Current:** `quarantine_worktree()` call is unguarded. If it fails, the entire prune loop aborts.

**Change:**
```python
try:
    quarantine_worktree(...)
    results.append(PruneResult(..., action="quarantined", ...))
except (OSError, subprocess.SubprocessError) as e:
    results.append(PruneResult(..., action="skipped", reason=f"Quarantine failed: {e}", ...))
```

Matches the existing removal path's try/except pattern.

**Test:** Add `test_prune_continues_after_quarantine_failure` using monkeypatch.

### Fix 4: Quarantine diff timestamp (F2)

**File:** `src/bid_euchre/ops/worktrees.py`, `quarantine_worktree()`, line ~630

**Current:** `diff_file = quarantine_dir / f"{slug}.diff"` — overwrites on repeat quarantine.

**Change:** `diff_file = quarantine_dir / f"{slug}_{timestamp}.diff"` where timestamp is `%Y%m%dT%H%M%S`.

**Note:** PR #905 also touches `quarantine_worktree()` (adds untracked files capture). The timestamp fix is on a different line (filename generation vs. diff content). Minimal conflict expected — resolve at rebase if needed.

**Test:** Verify two sequential quarantines produce different diff files.

### Fix 5: archive_worktree missing dir error (F8)

**File:** `src/bid_euchre/ops/worktrees.py`, `archive_worktree()`, line ~704

**Current:** `is_worktree_dirty()` returns `True` for missing paths → error says "has uncommitted changes" instead of "not found".

**Change:** After Fix 1, `is_worktree_dirty()` raises `FileNotFoundError` for missing paths. `archive_worktree()` already calls `is_worktree_dirty()` when `not force`, so the error will now be accurate. Add an explicit early check:
```python
resolved = str(Path(worktree_path).resolve())
if not Path(resolved).is_dir():
    raise FileNotFoundError(f"Worktree directory not found: {worktree_path}")
```

**Test:** Add `test_archive_missing_dir_error`.

### Fix 6: Verify reconcile() uses resolve() (M1)

**File:** `src/bid_euchre/ops/worktrees.py`, `reconcile()`, line ~246

**Current code already uses `Path(...).resolve()`** on both registry and git paths. The M1 concern was about string equality on symlinks — but since both sides resolve, this is already handled. Verify and close as non-issue.

If symlinks are a concern, note that `Path.resolve()` follows symlinks. No code change needed.

### Fix 7: Rename `active_sessions` → `recent_sessions` (888-M)

**File:** `src/bid_euchre/ops/status.py`

Two changes:
1. Line 47: `active_sessions` → `recent_sessions` in dataclass field
2. Line 244: `report.active_sessions` → `report.recent_sessions`

No other references in src/ or tests/ (verified by grep). The `format_status_json()` function doesn't serialize this field.

### Fix 8: Add drain --json test (888-L1)

**File:** `tests/unit/test_ops_cli.py`

Add `test_events_drain_json_subcommand` that passes `--json` flag and verifies output is valid JSON with expected structure.

## Files Changed

| File | Changes |
|------|---------|
| `src/bid_euchre/ops/worktrees.py` | Fixes 1-5 (path validation, protected list, prune error handling, timestamp diff, archive error) |
| `src/bid_euchre/ops/status.py` | Fix 7 (rename field) |
| `tests/unit/test_ops_worktrees.py` | Tests for fixes 1-5 |
| `tests/unit/test_ops_cli.py` | Fix 8 (drain --json test) |
| `tests/unit/test_ops_status.py` | Test for fix 7 (if needed) |

## PR #905 Conflict Assessment

PR #905 touches `worktrees.py` (quarantine untracked + archive registry cleanup) and `test_ops_worktrees.py`. Our changes touch:
- Different functions in most cases (H3=`is_worktree_dirty`, F3=`PROTECTED_WORKTREE_NAMES`, F4=`prune_worktrees`)
- Same function for F2 (`quarantine_worktree`) but different lines (filename vs content)
- Same function for F5 (`archive_worktree`) but additive early check

**Strategy:** Rebase on main after PR #905 merges. If PR #905 hasn't merged when we're ready, create PR against main and note potential conflict in description.

## Validation

1. Tier 1: `uv run python -m pytest tests/unit/test_ops_worktrees.py tests/unit/test_ops_status.py tests/unit/test_ops_cli.py -v`
2. Tier 2: `make check-quiet` before PR

## Outcome

_To be filled after implementation._
