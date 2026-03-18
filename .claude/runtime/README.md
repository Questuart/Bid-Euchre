# Runtime State

Gitignored runtime directories for session, lane, and task metadata.
Only README files in each subdirectory are committed; all JSON data
files are gitignored.

## Directories

| Directory | Schema | Purpose |
|-----------|--------|---------|
| `worktree_registry/` | v2 | Canonical lane/worktree identity and metadata |
| `session_metadata/` | v2 | Active and recent session state for resume and audit |
| `task_state/` | v1 | Delegated task items, progress, and validation contracts |
| `review_loops/` | -- | Review loop state (managed by `review_driver.py`) |
| `plan_reviews/` | -- | Plan review state (managed by review skill) |

## Schema Documentation

Each subdirectory has a `README.md` documenting its schema, field
semantics, lifecycle, and migration notes.

- `worktree_registry/README.md` -- v2 schema with `lane_id`, `lane_class`, transport fields
- `session_metadata/README.md` -- v2 schema with canonical `lane_id`, optional `role` compat
- `task_state/README.md` -- v1 schema for delegated task tracking

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
| `review_driver.py` | `review_loops/` | Review loop execution |
