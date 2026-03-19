# Runtime State

Gitignored runtime directories for session, lane, and task metadata.
Only README files in each subdirectory are committed; all JSON data
files are gitignored.

## Directories

| Directory | Schema | Status | Purpose |
|-----------|--------|--------|---------|
| `worktree_registry/` | v2 | Canonical | Lane/worktree identity and metadata |
| `session_metadata/` | v2 | Canonical | Active and recent session state for resume and audit |
| `task_state/` | v2 | Canonical | Delegated task items, scope, and validation contracts |
| `events/` | v1 | Canonical | Durable event log for operational signals (JSONL append-only) |
| `scheduler/` | v1 | Canonical | Scheduler tick state for ops periodic monitoring |
| `review_loops/` | -- | Transitional | Local review loop state (managed by `review_driver.py`). PR review is migrating to online-first (GitHub). Do not build new dependencies on this directory. |
| `plan_reviews/` | -- | Transitional | Local plan review state (managed by review skill). Will be simplified to in-session flow. Do not build new dependencies on this directory. |

## Schema Documentation

Each subdirectory has a `README.md` documenting its schema, field
semantics, lifecycle, and migration notes.

- `worktree_registry/README.md` -- v2 schema with `lane_id`, `lane_class`, transport fields
- `session_metadata/README.md` -- v2 schema with canonical `lane_id`, optional `role` compat
- `task_state/README.md` -- v2 schema with `owner_lane`, `in_scope`, `out_of_scope`, escalation triggers
- `events/README.md` -- v1 schema with JSONL event log, event types, and drain/archive flow
- `scheduler/README.md` -- v1 schema with tick state and health pass tracking

## Identity Contract

The `lane_id` field in `worktree_registry` and `session_metadata` is the
canonical machine identity for a lane. It is the sole routing key for
metadata lookup and coordination. See
`docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` for the full identity model.

## Writers

| Writer | Directories | When |
|--------|------------|------|
| `steward-session.sh` | `worktree_registry/` | Session bootstrap (v2 entries) |
| `start-role-worktree.sh` | `worktree_registry/` | Legacy role bootstrap (v2 entries with `legacy_role`) |
| `start-agent-role.sh` | (sets env vars only) | Legacy role launch |
| Agent sessions | `session_metadata/`, `task_state/` | During execution |
| `ops.py` (scheduler) | `events/`, `scheduler/` | Tick loop, watchdog findings |
| `ops/events.py` | `events/` | Durable event append from hooks/agents |
| `review_driver.py` | `review_loops/` | Review loop execution |
