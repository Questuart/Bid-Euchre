# Restore Dirty-Worktree Liveness Fallback

**Date:** 2026-03-20
**Author:** author-b
**Branch:** `fix/stale-slice-sequencing`

## Problem

PR #1091 rewrote the fallback liveness probe in `src/bid_euchre/ops/status.py`,
replacing the old `_probe_lane_liveness()` with `_probe_fallback_liveness()`.
The rewrite added 4 data-driven signals (events, task state, session metadata,
registry last_active) but removed the dirty-worktree subprocess check that was
previously signal #2.

**Regression case:** A lane with uncommitted work in its worktree but no active
session_id, no recent events, no in-progress tasks, and no fresh
session/last_active timestamps is now reported as `idle` instead of
`likely_active`. This reopens the trust gap that slice 6 was supposed to close.

## Approach

Restore dirty-worktree probing as the **lowest-priority** signal (#5) in
`_probe_fallback_liveness()`. This preserves the #1091 design (data-driven
signals first, subprocess last) while closing the regression.

## Changes

### 1. `src/bid_euchre/ops/status.py`

#### `_probe_fallback_liveness()` — add signal #5

- Add parameters: `worktree_path: str = ""`, `check_worktree: bool = True`
- After signal #4 (registry last_active) and before the "no evidence" fallback,
  add signal #5:
  ```
  # --- Signal 5: Dirty worktree (subprocess, lowest priority) ---
  if check_worktree and worktree_path:
      try:
          from bid_euchre.ops.worktrees import is_worktree_dirty
          if is_worktree_dirty(worktree_path):
              wt_name = Path(worktree_path).name
              return _LivenessProbe(
                  is_likely_live=True,
                  is_stale=False,
                  source="worktree_dirty",
                  detail=f"uncommitted changes in {wt_name}",
              )
      except Exception:
          pass  # Subprocess failure — degrade gracefully, skip signal
  ```
- Update docstring to document signal #5

#### `synthesize_lane_activity()` — pass worktree_path through

- The `worktree_path` is already available via `lane.get("worktree_path", "")`
  (line 740 in current code). Pass it to `_probe_fallback_liveness()`:
  ```python
  probe = _probe_fallback_liveness(
      lane_id,
      session=session,
      lane_tasks=lane_tasks,
      events=events,
      last_active_ts=last_active_ts,
      worktree_path=lane.get("worktree_path", ""),  # NEW
      now=now,
      stale_minutes=stale_minutes,
  )
  ```

#### `LaneStatus.liveness_source` docstring

- Add `"worktree_dirty"` to the documented set of source values (line 79)

### 2. `tests/unit/test_ops_status.py`

Add tests in two locations:

#### `TestProbeFallbackLiveness` — unit tests for signal #5

- `test_dirty_worktree_returns_likely_live` — mock `is_worktree_dirty` → True,
  verify `is_likely_live=True, source="worktree_dirty"`
- `test_clean_worktree_returns_idle` — mock `is_worktree_dirty` → False,
  verify `is_likely_live=False, source=None`
- `test_worktree_check_failure_degrades_gracefully` — mock raises exception,
  verify returns idle (not crash)
- `test_worktree_check_skipped_when_disabled` — `check_worktree=False`,
  verify `is_worktree_dirty` not called
- `test_worktree_signal_lowest_priority` — fresh event + dirty worktree →
  `source="events"` (not `"worktree_dirty"`)

#### `TestSynthesizeLaneActivityLiveness` — integration test

- `test_likely_active_from_dirty_worktree` — lane with no session, no events,
  no tasks, but dirty worktree → `state="likely_active"`, `liveness_source="worktree_dirty"`

## Validation

- **Tier 1:** `uv run python -m pytest tests/unit/test_ops_status.py -v`
- **Tier 2:** `make check-quiet` before PR

## Out of Scope

- PR #1098 (slice 7) — already in flight, tracked separately
- Platform pre-phase entry — blocked on slice 7, tracked in checkpoints
- Stale docs (P2 finding) — already fixed by c61bc24c

## Outcome

Implemented and validated. PR pending.

- `_probe_fallback_liveness()` now has signal #5 (dirty worktree) as lowest priority
- `synthesize_lane_activity()` passes `worktree_path` through to the probe
- 7 new tests added (6 unit + 1 integration), all passing
- Full `make check-quiet` passes (149/149 status tests, 71/71 CLI tests)
