# Scheduler

Scheduler state for the ops tick loop. JSON files in this directory
are gitignored; only this README is committed.

## Schema

`state.json` persists scheduler state across session restarts:

```json
{
  "last_tick": "2026-03-18T12:00:00+00:00",
  "last_health_pass": "2026-03-18T11:55:00+00:00",
  "tick_count": 42,
  "due_checks": ["heartbeats", "task_progress", "worktree_health"],
  "last_error": null
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `last_tick` | string/null | no | ISO 8601 timestamp of the last tick |
| `last_health_pass` | string/null | no | ISO 8601 timestamp of last tick with no critical findings |
| `tick_count` | int | yes | Total number of ticks run |
| `due_checks` | array | yes | Names of checks to run each tick |
| `last_error` | string/null | no | Description of the last error, or null |

### Default Checks

| Check | Watchdog | Description |
|-------|----------|-------------|
| `heartbeats` | `check_heartbeats()` | Scans `plans/**/heartbeat` for staleness |
| `task_progress` | `check_task_progress()` | Checks `task_state/*.json` for stalled tasks |
| `worktree_health` | `check_worktree_health()` | Reconciles registry vs git worktrees |

## Operations

- **Tick:** `ops/scheduler.py::tick()` — run one scheduler cycle
- **Load:** `ops/scheduler.py::load_scheduler_state()` — read persisted state
- **Save:** `ops/scheduler.py::save_scheduler_state()` — write state to disk

## Resume

After session restart, the scheduler resumes from `state.json`. No
conversation history is needed — `tick_count` and `last_tick` provide
continuity.
