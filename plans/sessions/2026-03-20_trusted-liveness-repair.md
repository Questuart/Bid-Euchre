# Trusted Liveness Repair — Slice 6

**Date:** 2026-03-20
**Goal:** Repair trusted lane liveness so `ops.py status` is an authoritative
operator surface, not a best-effort hint.

## Problem

`synthesize_lane_activity()` derives lane state from a single liveness signal:
`lane.get("session_id") is not None` from the worktree registry. When this field
is null (session not registered, registration cleared, or never wired), the lane
is reported as "idle" even when a live Claude process is actively working in that
worktree.

This creates a trust gap: the operator cannot rely on `ops.py status` output to
know whether a lane is genuinely idle vs. actively running with stale metadata.

## Approach

### 1. Add fallback liveness probe

A new `_probe_fallback_liveness()` function checks repo-local evidence beyond
the registry `session_id`:

| Signal | Source | Interpretation |
|--------|--------|----------------|
| Recent events | Event log for this lane_id | Activity within staleness window |
| In-progress tasks | Task state for this lane | Active work assigned |
| Session metadata freshness | Session `started_at` timestamp | Recent session start |
| Last active timestamp | Registry `last_active` field | Recent registry update |

Returns: `(is_likely_live: bool, is_stale: bool, source: str, detail: str)`

### 2. New lane states

Expand `LANE_STATES` to include uncertainty states:

| State | Meaning | When |
|-------|---------|------|
| `active` | Confirmed active | Registry `session_id` present |
| `likely_active` | No session_id, but fallback evidence is fresh | Fallback probe finds recent evidence |
| `stale` | Evidence exists but is aging / uncertain | Evidence older than staleness threshold but present |
| `blocked` | Primary task is blocked | (unchanged) |
| `idle` | No evidence of activity | No session_id AND no fallback evidence |
| `unknown` | Cannot determine | (reserved, not currently used) |

### 3. Add `liveness_source` to LaneStatus

New field tracking where the state determination came from:
- `"registry"` — session_id was present
- `"events"` — recent event log entry
- `"task_state"` — in-progress task with recent progress
- `"session_metadata"` — fresh session metadata
- `None` — no evidence (idle)

### 4. Update state derivation

In `synthesize_lane_activity()`, change the else-idle branch to:

```python
if primary_task and primary_task.get("status") == "blocked":
    state = "blocked"
elif has_active_session:
    state = "active"
    liveness_source = "registry"
else:
    # Fallback liveness probe
    probe = _probe_fallback_liveness(...)
    if probe.is_likely_live:
        state = "likely_active"
    elif probe.is_stale:
        state = "stale"
    else:
        state = "idle"
```

### 5. Update formatting

- Text: `[likely_active]` and `[stale]` badges, with source annotation
- JSON: `liveness_source` field in lane objects
- Attention: `stale` gets attention flag; `likely_active` does not
- Persistent idle lanes keep their existing attention flag

### 6. Tests

Cover all paths:
- Heartbeat/session present and fresh → `active`
- No session_id, recent event → `likely_active`
- No session_id, recent in-progress task → `likely_active`
- No session_id, stale evidence → `stale`
- No session_id, no evidence → `idle`
- Formatting for new states

## Files Changed

| File | Change |
|------|--------|
| `src/bid_euchre/ops/status.py` | Add probe, states, LaneStatus field, synthesis update, formatting |
| `tests/unit/test_ops_status.py` | New test class for fallback liveness |

## Out of Scope

- tmux process detection (subprocess calls to tmux)
- orchestrator / dashboard
- message bus / remote channels
- Platform-1+

## Outcome

(filled after implementation)
