# Worktree Registry

Runtime metadata for tracked worktrees. JSON files in this directory are
gitignored; only this README is committed.

This is the **single canonical registry** for live lane/worktree identity.
Do not create parallel registries (e.g., `lane_registry/`).

## Schema (v2)

Each registered worktree has a JSON file named `<lane_id>.json` (for steward
lanes) or `<role>.json` (for legacy role worktrees, backward compatible).

### v2 Example (Steward Lane)

```json
{
  "schema_version": 2,
  "lane_id": "author-a",
  "lane_class": "author",
  "worktree_path": "../Bid-Euchre-steward-author",
  "branch": "codex/steward-author",
  "class": "persistent",
  "created_at": "2026-03-18T10:00:00Z",
  "last_active": "2026-03-18T10:00:00Z",
  "session_id": null,
  "ttl_hours": null,
  "display_name": "Author A",
  "tmux_session": "steward",
  "tmux_window": "dashboard",
  "tmux_pane": "1",
  "cmux_workspace_ref": null,
  "cmux_surface_ref": null,
  "legacy_role": null,
  "session_handle": "steward:author-a",
  "visibility": "foreground"
}
```

### v2 Example (Legacy Role, Compatibility)

```json
{
  "schema_version": 2,
  "lane_id": "author-a",
  "lane_class": "author",
  "worktree_path": "../Bid-Euchre-author",
  "branch": "role/author",
  "class": "persistent",
  "created_at": "2026-03-16T22:00:00Z",
  "last_active": "2026-03-16T22:00:00Z",
  "session_id": null,
  "ttl_hours": null,
  "display_name": null,
  "tmux_session": null,
  "tmux_window": null,
  "tmux_pane": null,
  "cmux_workspace_ref": null,
  "cmux_surface_ref": null,
  "legacy_role": "author",
  "session_handle": "role:author-a",
  "visibility": null
}
```

### Fields

| Field | Type | Required | Since | Description |
|-------|------|----------|-------|-------------|
| `schema_version` | int | yes | v1 | Schema version (`2` for this version) |
| `lane_id` | string | yes | v2 | Canonical machine identity for this lane (e.g., `author-a`, `ops`) |
| `lane_class` | string | yes | v2 | Functional class: `ops`, `review`, `author`, `scratch` |
| `worktree_path` | string | yes | v1 | Path to the worktree directory (relative to main checkout parent) |
| `branch` | string | yes | v1 | Git branch name used by this worktree |
| `class` | string | yes | v1 | Lifecycle class: `persistent` or `ephemeral` |
| `created_at` | string | yes | v1 | ISO 8601 timestamp of worktree creation |
| `last_active` | string | yes | v1 | ISO 8601 timestamp of last activity |
| `session_id` | string/null | no | v1 | UUID of the active session using this worktree, or null |
| `ttl_hours` | number/null | no | v1 | Hours until ephemeral worktree becomes stale. Null for persistent. |
| `display_name` | string/null | no | v2 | Human-facing label (e.g., `Author A`). Not used for routing. |
| `tmux_session` | string/null | no | v2 | tmux session name (e.g., `steward`) |
| `tmux_window` | string/null | no | v2 | tmux window name (e.g., `dashboard`, `author-c`) |
| `tmux_pane` | string/null | no | v2 | tmux pane index within the window (e.g., `1`) |
| `cmux_workspace_ref` | string/null | no | v2 | cmux workspace reference (future use) |
| `cmux_surface_ref` | string/null | no | v2 | cmux surface reference (future use) |
| `legacy_role` | string/null | no | v2 | Legacy role name (`author`, `review`, `ops`) if created by legacy scripts. Null for steward lanes. |
| `session_handle` | string/null | no | v2 | Resume-targeting handle (e.g., `steward:author-a`, `role:author-a`). Null for ephemeral or legacy entries without a stable handle. |
| `visibility` | string/null | no | v2 | Worker visibility class: `foreground` (dashboard panes), `background` (off-dashboard windows), or null (unknown/legacy). |

### Field Semantics

**`lane_id`** is the canonical machine identity. It is the sole routing key
used for metadata lookup, coordination, and addressing. It must be unique
within a registry.

**`lane_class`** is the functional class, determining what capabilities and
conventions apply to the lane. Values: `ops`, `review`, `author`, `scratch`.

**`class`** is the lifecycle class from v1 and is **not renamed**. It
determines cleanup behavior: `persistent` lanes are never auto-pruned;
`ephemeral` lanes are subject to TTL and cleanup policy.

**`display_name`** is presentation-only. It must never be used as a routing
key, metadata lookup key, or coordination identifier.

**Transport fields** (`tmux_session`, `tmux_window`, `tmux_pane`,
`cmux_workspace_ref`, `cmux_surface_ref`) capture the terminal session
targeting for the lane. These are informational and may be used to send
commands or navigate to a lane, but are not primary identity.

**`legacy_role`** records the v1 role name when a worktree was created by
the legacy `start-role-worktree.sh` script. It enables backward compatibility
during the transition period. Null for worktrees created by the steward
launcher.

**`session_handle`** is a stable resume-targeting key. Format is
`<transport>:<lane_id>` (e.g., `steward:author-a` for steward lanes,
`role:author-a` for legacy role worktrees). Null for ephemeral worktrees or
entries written before this field was introduced. Used by follow-on
resume-by-name tooling.

**`visibility`** is the worker visibility class, written by the launcher based
on tmux layout. Values: `foreground` (dashboard panes visible in the main
tmux window), `background` (off-dashboard windows like author-c, author-d,
author-scratch). Null for legacy entries or entries written before this field
was introduced. Not used for routing or scheduling — purely informational for
operator tooling.

### Lifecycle Class Values

- **`persistent`** -- Lane worktrees that are never auto-pruned. All steward
  lanes and legacy role worktrees are persistent. Updated on reuse but never
  removed by cleanup flows.
- **`ephemeral`** -- Task-specific worktrees with bounded lifetime. Created for
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

**Steward lanes (v2):**
- `author-a.json` -- Primary author lane
- `author-b.json` -- Parallel author lane
- `author-c.json` -- Overflow author lane
- `author-d.json` -- Overflow author lane
- `author-scratch.json` -- Exploratory lane
- `review.json` -- Review lane
- `ops.json` -- Ops lane

**Legacy roles (v1 compatibility):**
- `author.json` -- Author role worktree (v1 naming, maps to `author-a`)
- `review.json` -- Review role worktree
- `ops.json` -- Ops role worktree

**Ephemeral:**
- `task-<slug>.json` -- Ephemeral task worktree (slug derived from branch name)

### v1 to v2 Migration

v1 entries are accepted by v2 readers. Missing v2 fields are inferred:

| v2 Field | Inferred Value from v1 |
|----------|----------------------|
| `lane_id` | Same as `role` (e.g., `author` becomes `author-a`) |
| `lane_class` | Same as `role` for `review` and `ops`; `author` for role `author` |
| `display_name` | null |
| `tmux_*` | null |
| `cmux_*` | null |
| `legacy_role` | Same as `role` |
| `session_handle` | null |
| `visibility` | null |

Writers should produce v2 entries. v1 entries will not be actively migrated
but remain readable. Older v2 entries written before `session_handle` and
`visibility` were introduced are also accepted — readers default both to null.

## v1 Schema (Deprecated)

The v1 schema used `role` as the primary identity field and did not include
`lane_id`, `lane_class`, or transport fields. See git history for the full
v1 specification.

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

v1 files are still valid and readable. The `role` field maps to `lane_id`
and `lane_class` as described in the migration table above.
