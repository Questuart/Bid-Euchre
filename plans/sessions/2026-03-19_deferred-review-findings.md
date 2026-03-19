# Deferred Review Findings — Ops Package Hardening

**Date:** 2026-03-19
**Goal:** Address the 5 deferred findings from the steward review batch (PRs #878, #892) that were triaged out of PR #910.
**Branch:** `fix/deferred-review-findings` from `origin/main`
**PR:** One PR for all 5 fixes (same review batch, all ops-internal)

## Context

PR #910 fixed 7 findings. These 5 were deferred with rationale. This session re-evaluates and addresses all of them.

## Execution Groups

- **Group A (events.py):** H1 + M7 → M2. Sequential — same file, H1+M7 coupled.
- **Group B (recovery.py):** F6. Independent, parallel-ready.
- **Group C (worktrees.py):** F7. Independent, parallel-ready.

## Refined Findings

### H1+M7: `drain_events()` crash safety + concurrent locking

**File:** `src/bid_euchre/ops/events.py`, lines 170-243
**Function:** `drain_events(events_dir, *, up_to)`

**Current code flow (lines 205-240):**
1. L205-224: Open events_file, read all lines, sort into `to_drain`/`to_keep` — NO LOCK
2. L230-232: Append `to_drain` to `archive_file` — NO LOCK
3. L236-240: Write `to_keep` to temp file, `rename()` over events_file — NO LOCK

**H1 problem:** If crash between L232 (archive append) and L240 (rename), drained events exist in BOTH archive and active log. Next drain re-archives them → duplicates.

**H1 fix:** Reorder to rename-before-archive-append:
1. Write temp with `to_keep` events
2. `rename()` temp over active log (atomic — drained events removed)
3. Append `to_drain` to archive
Crash between steps 2 and 3 → drained events removed from active but missing from archive (acceptable — archive is best-effort historical, events are advisory).

**M7 problem:** Between L205 read and L240 rename, a concurrent `append_event()` (which holds flock only for its own write at L99-105) can write a new event to the old active file. The rename replaces it → new event lost.

**M7 fix:** Hold `fcntl.flock(LOCK_EX)` on events_file for the entire drain cycle (read → filter → write temp → rename → archive append). This serializes drain with concurrent appends since `append_event()` already acquires `LOCK_EX`.

**Combined implementation:**
```python
def drain_events(events_dir, *, up_to=None):
    # ... setup ...
    with open(events_file, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            # Read and classify
            for line in f: ...

            if not to_drain: return 0

            # 1. Write remaining to temp (while holding lock)
            tmp_file = events_file.with_suffix(".tmp")
            with open(tmp_file, "w") as tmp:
                for line in to_keep: tmp.write(line + "\n")

            # 2. Atomic rename (removes drained from active)
            tmp_file.rename(events_file)

            # 3. Append drained to archive (best-effort)
            with open(archive_file, "a") as af:
                for line in to_drain: af.write(line + "\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

**Edge cases:**
- Empty log: returns 0 early (before lock acquisition via exists() check)
- File exists but empty: flock succeeds, no lines → returns 0
- `up_to` partial drain: only matching events drained, rest kept
- Archive file doesn't exist: `open("a")` creates it

**Tests:**
- `test_drain_atomic_rename_before_archive`: Verify drain order by checking archive has events after rename
- `test_drain_holds_lock_during_operation`: Use thread to try concurrent append during drain

### M2: `read_events()` memory optimization

**File:** `src/bid_euchre/ops/events.py`, lines 111-167
**Function:** `read_events(events_dir, *, since, event_type, lane_id, limit)`

**Current code (lines 138-167):**
```python
events: list[dict] = []
with open(events_file) as f:
    for line in f:
        # ... parse and filter ...
        events.append(event)
events.reverse()
return events[:limit]
```
Loads ALL matching events, reverses, then slices. O(N) memory for N total matching events.

**Fix:** Use `collections.deque(maxlen=limit)` to keep only the last `limit` matching events during iteration. Then reverse the deque for most-recent-first output. O(limit) memory.

```python
from collections import deque

matched: deque[dict] = deque(maxlen=limit)
with open(events_file) as f:
    for line in f:
        # ... parse and filter ...
        matched.append(event)
result = list(matched)
result.reverse()
return result
```

**Behavioral change:** None. Same output, less memory. Existing tests pass unchanged.

**Tests:**
- Existing `test_limit` already validates the behavior. No new test needed — purely an optimization.

### F6: `get_active_failures()` resolution correlation

**File:** `src/bid_euchre/ops/recovery.py`, lines 165-193
**Function:** `get_active_failures(events_dir, *, limit)`

**Current code (lines 187-192):**
```python
for event in events:
    event_type = event.get("event_type", "")
    if event_type in _FAILURE_EVENT_TYPES:
        failures.append(classify_failure(event))
```
No resolution check — ALL failure events returned as "active."

**Fix:** Define resolution map and walk events newest-first:

```python
# New module-level constant
_RESOLUTION_MAP: dict[str, frozenset[str]] = {
    "ci_success": frozenset({"ci_failure"}),
    "task_completed": frozenset({"task_failed", "task_blocked"}),
    "heartbeat_ok": frozenset({"heartbeat_stale"}),
    "worktree_archived": frozenset({"worktree_quarantined"}),
    "recovery_action": frozenset({"escalation"}),
}

def _resolution_target(event: dict) -> str:
    payload = event.get("payload", {})
    return str(payload.get("target", event.get("lane_id", "unknown")))
```

Algorithm (events are newest-first from `read_events`):
1. See resolution event → mark `(failure_type, target)` as resolved
2. See failure event → only include if `(event_type, target)` NOT resolved

**Tests:**
- `test_resolved_failure_excluded`: ci_failure + ci_success for same target → 0 active
- `test_newer_failure_after_resolution_still_active`: ci_success + ci_failure (newer) → 1 active
- `test_different_target_not_resolved`: ci_failure(PR#1) + ci_success(PR#2) → 1 active
- `test_multiple_resolution_types`: task_failed + task_completed → resolved

### F7: `_update_registry_cleanup_state()` TOCTOU race

**File:** `src/bid_euchre/ops/worktrees.py`, lines 584-620
**Function:** `_update_registry_cleanup_state(registry_dir, worktree_path, cleanup_state)`

**Current code (lines 607-616):**
```python
for f in sorted(registry_dir.glob("*.json")):
    try:
        data = json.loads(f.read_text())  # READ
    except ...: continue
    if ...:
        data["cleanup_state"] = cleanup_state
        f.write_text(json.dumps(data, indent=2))  # WRITE
```
Read and write are separate operations with no lock. Concurrent writes can overwrite each other.

**Fix:** Use `open("r+")` with `fcntl.flock()`:
```python
import fcntl

for json_path in sorted(registry_dir.glob("*.json")):
    try:
        with open(json_path, "r+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                data = json.loads(fh.read())
                if match:
                    data["cleanup_state"] = cleanup_state
                    fh.seek(0)
                    fh.truncate()
                    fh.write(json.dumps(data, indent=2))
                    return True
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
    except ...: continue
```

**Tests:**
- Existing `test_quarantine_persists_cleanup_state` validates the behavior end-to-end
- New: `test_update_registry_cleanup_state_writes_atomically`: Verify file is valid JSON after update

## Outcome

**PR:** #918 — fix: address 5 deferred review findings in ops package
**Status:** MERGED (2026-03-19)

All 5 deferred findings addressed: H1+M7 crash-safe event drain with
`fcntl.flock`, F6 worktree path resolution fallback, M2 timeout
observability in reviews, V1 lane_id inference in worktree archive.
