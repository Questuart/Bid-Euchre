# Events

Durable event log for operational signals. JSONL files in this directory
are gitignored; only this README is committed.

## Schema

Each event is a single JSON line in `events.jsonl`:

```json
{
  "timestamp": "2026-03-18T10:00:00+00:00",
  "event_type": "ci_failure",
  "source": "ops.tick",
  "lane_id": "author-a",
  "payload": {
    "pr_number": 866,
    "failure_class": "lint",
    "details": "ruff check found 2 issues"
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | yes | ISO 8601 timestamp of the event |
| `event_type` | string | yes | One of the valid event types (see below) |
| `source` | string | yes | Identifier for the producer |
| `lane_id` | string | yes | Canonical lane identity |
| `payload` | object | yes | Arbitrary structured payload |

### Valid Event Types

| Event Type | Source | Meaning |
|-----------|--------|---------|
| `task_completed` | Agent/hook | A task reached completion |
| `task_failed` | Agent/hook | A task failed |
| `task_blocked` | Agent/hook | A task became blocked |
| `ci_failure` | ops.tick / hook | CI check failed on a PR |
| `ci_success` | ops.tick / hook | CI check passed on a PR |
| `heartbeat_stale` | ops.tick | Heartbeat exceeded staleness threshold |
| `heartbeat_ok` | ops.tick | Heartbeat is fresh |
| `review_outcome` | ops.tick / hook | PR review result received |
| `plan_review_outcome` | review session | Plan review completed |
| `worktree_created` | launcher | New worktree created |
| `worktree_removed` | ops.prune | Worktree removed |
| `worktree_quarantined` | ops.quarantine | Dirty worktree quarantined |
| `worktree_archived` | ops.archive | Worktree metadata archived |
| `escalation` | Agent | Work escalated to another lane |
| `recovery_action` | ops | Recovery step taken |
| `watchdog_finding` | ops.tick | Watchdog detected an issue |
| `scheduler_tick` | ops.tick | Scheduler completed one cycle |
| `session_started` | launcher | New session started |
| `session_ended` | Agent/hook | Session ended |

## Files

| File | Purpose | Lifecycle |
|------|---------|-----------|
| `events.jsonl` | Active event log (append-only) | Grows until drained |
| `events.archive.jsonl` | Drained events archive | Grows over time |

## Operations

- **Append:** `ops/events.py::append_event()` — thread-safe single-line append
- **Read:** `ops/events.py::read_events()` — filter by type, lane, time
- **Drain:** `ops/events.py::drain_events()` — move processed events to archive
- **Count:** `ops/events.py::count_events()` — count events by type
