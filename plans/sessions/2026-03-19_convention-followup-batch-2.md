# Session Plan: Convention Follow-up Batch 2

**Date:** 2026-03-19
**Author:** author-b
**Branch:** fix/convention-followup-batch-2
**Closes:** #924, #922, #920, #908, #907, #900, #898, #895

## Goal

Address 8 deferred review findings across ops/, arc_d_v2/, CI workflow, and
docs in a single batch PR. Follows the same pattern as PR #918 (batch 1).

## Scope

| Issue | File | Finding | Change |
|-------|------|---------|--------|
| #922 | `src/bid_euchre/ops/recovery.py:175` | Match worktree resolution events by worktree path | Prefer `payload.worktree_path` as fallback target for worktree events |
| #920 | `src/bid_euchre/ops/reviews.py:53` | Preserve timeout state | Log timeout at ERROR level, distinct from generic gh failure |
| #920 | `src/bid_euchre/ops/reviews.py:155` | Aggregate multiple review contexts | Collect all matching checks and aggregate instead of first-match-wins |
| #908 | `src/bid_euchre/ops/worktrees.py:764` | Preserve v1 lane_id inference when archiving | Apply v1 role→lane_id map before falling back to "ops" |
| #907 | `src/bid_euchre/ops/status.py:103` | Unique lane IDs for unmapped legacy roles | Use role name as fallback lane_id instead of "unknown" |
| #900 | `src/bid_euchre/ops/worktrees.py:608` | Handle registry write failures separately | Separate read/parse errors from write errors, log write failures explicitly |
| #898 | `docs/04_reports/arc_d_v2/r0/canonical/02_decision.md:69` | WARNING checks reported as fully passed | Qualify language to reflect WARNING-level sanity checks |
| #895 | `src/bid_euchre/arc_d_v2/tables.py:726` | Derive repo-relative paths from Git root | Add `_find_repo_root()` with lru_cache, fall back to `/data/` heuristic |

## Out of Scope

- #921, #890, #925 — hypothesis_outcomes.csv data regeneration (separate effort)
- #829, #830 — review driver architectural changes (larger scope)

## Detailed Changes

### F1: `recovery.py` — Worktree path resolution target (#922)

**Current:** `_resolution_target()` uses `payload.target`, falling back to `lane_id`.

**Problem:** Worktree events (`worktree_quarantined`, `worktree_archived`) should
match by worktree path, not lane_id, since a single lane can have multiple
worktrees. Without this, a resolution event for one worktree could incorrectly
resolve a failure for a different worktree on the same lane.

**Fix:** Add `payload.worktree_path` as intermediate fallback:

```python
def _resolution_target(event: dict[str, Any]) -> str:
    payload = event.get("payload", {})
    target = payload.get("target")
    if target is not None:
        return str(target)
    # Worktree events: prefer worktree_path as matching key
    wt_path = payload.get("worktree_path")
    if wt_path:
        return str(wt_path)
    return str(event.get("lane_id", "unknown"))
```

**Test:** Add test case for worktree resolution by path.

### F2: `reviews.py` — Timeout observability (#920a)

**Current:** `_run_gh()` catches `TimeoutExpired` and returns a synthetic failure
with `stderr="Timed out after Ns"`. Callers log generic "Failed to list open PRs."

**Fix:** In `_get_open_prs()` and `get_pr_review_detail()`, detect timeout in
stderr and log at ERROR level (vs WARNING for other failures). This preserves
graceful degradation while improving observability.

### F3: `reviews.py` — Aggregate review contexts (#920b)

**Current:** `_get_review_status()` returns the state of the first matching check.
If multiple review contexts exist (e.g., both `reviewing-changes` and a future
`codex-review`), only the first is considered.

**Fix:** Collect all matching review checks and aggregate:
- Any FAILURE → "failure"
- Any PENDING/IN_PROGRESS → "pending"
- All SUCCESS → "success"
- Otherwise → "unknown"

Same logic as `_classify_ci_status()` for consistency.

**Test:** Add test for multiple review contexts with different states.

### F4: `worktrees.py` — V1 lane_id inference in archive (#908)

**Current:** `archive_worktree()` reads `lane_id` from registry with `"ops"` default.
V1 entries without `lane_id` always get "ops" even if their `role` field indicates
otherwise.

**Fix:** Apply the standard v1 role→lane_id map:

```python
lane_id = reg_data.get("lane_id")
if not lane_id and reg_data.get("schema_version", 1) < 2:
    role = reg_data.get("role", "ops")
    _v1_map = {"author": "author-a", "review": "review", "ops": "ops"}
    lane_id = _v1_map.get(role, role)
lane_id = lane_id or "ops"
```

### F5: `status.py` — Unique unmapped lane IDs (#907)

**Current:** V1 sessions with unrecognized role get `lane_id="unknown"`,
collapsing distinct roles into a single identity.

**Fix:** Use the role name as the fallback lane_id:

```python
data.setdefault("lane_id", lane_id_map.get(role, role))
```

**Test:** Update `test_v1_unknown_role_maps_to_unknown` to expect the role
name instead of "unknown".

### F6: `worktrees.py` — Separate write errors (#900)

**Current:** `_update_registry_cleanup_state()` catches `(json.JSONDecodeError,
OSError)` around both read and write operations. A write failure is silently
skipped and the loop continues — but no subsequent file will match, so the
failure is permanently silent.

**Fix:** Narrow the exception handling: catch `JSONDecodeError` on parse only,
and catch `OSError` on write separately with explicit logging and `return False`.

### F7: `02_decision.md` — WARNING language (#898)

**Current:** "Data sanity: all checks passed"

**Fix:** "Data sanity: all checks passed (some with WARNINGs — see caveats below)"

### F8: `tables.py` — Repo-relative paths via Git root (#895)

**Current:** `_make_repo_relative()` searches for `/data/` marker in the path
string. Fragile if path contains `/data/` elsewhere.

**Fix:** Add `_find_repo_root()` with `@lru_cache(maxsize=1)` that walks up
from `__file__` looking for `.git`. Use `Path.relative_to(root)` when root
is found, fall back to `/data/` heuristic.

**Test:** Test with explicit root parameter or mock.

## Files Changed

| File | Type |
|------|------|
| `src/bid_euchre/ops/recovery.py` | Code fix |
| `src/bid_euchre/ops/reviews.py` | Code fix |
| `src/bid_euchre/ops/worktrees.py` | Code fix |
| `src/bid_euchre/ops/status.py` | Code fix |
| `src/bid_euchre/arc_d_v2/tables.py` | Code fix |
| `.github/workflows/dashboard.yml` | CI fix |
| `docs/04_reports/arc_d_v2/r0/canonical/02_decision.md` | Docs fix |
| `tests/unit/test_ops_recovery.py` | Test updates |
| `tests/unit/test_ops_reviews.py` | Test updates |
| `tests/unit/test_ops_status.py` | Test updates |
| `tests/unit/test_ops_worktrees.py` | Test updates |

## Validation

- Tier 1: Run impacted test files after each code change
- Tier 2: `make check-quiet` before PR

## Outcome

_To be filled after implementation._
