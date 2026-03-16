# Worktree Registry

Runtime metadata for tracked worktrees. JSON files in this directory are
gitignored; only this README is committed.

## Schema (v1)

Each registered worktree has a JSON file named `<role>.json` (for persistent
role worktrees) or `<task-slug>.json` (for ephemeral task worktrees).

```json
{
  "schema_version": 1,
  "role": "author",
  "worktree_path": "../Bid-Euchre-author",
  "branch": "role/author",
  "class": "persistent",
  "created_at": "2026-03-16T22:00:00Z",
  "last_active": "2026-03-16T22:00:00Z",
  "session_id": null,
  "ttl_hours": null
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | int | yes | Always `1` for this version |
| `role` | string | yes | One of `author`, `review`, `ops`, or a task-specific name |
| `worktree_path` | string | yes | Path to the worktree directory (relative to main checkout parent) |
| `branch` | string | yes | Git branch name used by this worktree |
| `class` | string | yes | `persistent` (role worktrees) or `ephemeral` (task worktrees) |
| `created_at` | string | yes | ISO 8601 timestamp of worktree creation |
| `last_active` | string | yes | ISO 8601 timestamp of last activity |
| `session_id` | string/null | no | UUID of the active session using this worktree, or null |
| `ttl_hours` | number/null | no | Hours until ephemeral worktree becomes stale. Null for persistent. |

### Class Values

- **`persistent`** — Role worktrees (`author`, `review`, `ops`). Never auto-pruned.
  Updated to latest main on reuse but never removed by cleanup flows.
- **`ephemeral`** — Task-specific worktrees with bounded lifetime. Created for
  a specific PR, experiment, or investigation. Subject to TTL and cleanup policy.

### Cleanup States (Ephemeral Only)

Ephemeral worktrees progress through lifecycle states:

| State | Meaning |
|-------|---------|
| `active` | In use by a session or task |
| `idle` | No active session, TTL not expired |
| `stale` | TTL expired, no active session |
| `quarantined` | Has uncommitted changes, needs manual review |
| `ready_to_remove` | Clean, stale, safe to prune |
| `archived` | Metadata preserved, worktree directory removed |

### File Naming

- `author.json` — Author role worktree
- `review.json` — Review role worktree
- `ops.json` — Ops role worktree
- `task-<slug>.json` — Ephemeral task worktree (slug derived from branch name)
