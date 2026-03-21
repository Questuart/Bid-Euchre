# Platform-1 Slice 1 — Additive Field Contract

**Date:** 2026-03-21
**Author:** author-b
**Parent:** `plans/agent_ops/1_coordination_core/sub/2026-03-21_platform1-lane-registry-foundation.md` (SP-1-01)

## Locked Field Contract

### New Registry Fields (additive to v2 schema)

| Field | Type | Default | Writer | Description |
|-------|------|---------|--------|-------------|
| `session_handle` | `string/null` | `null` | Launcher (`steward-session.sh`, `start-role-worktree.sh`) | Resume-targeting handle. For steward lanes, set to `"steward:<lane_id>"` (e.g., `"steward:author-a"`). For legacy role lanes, set to `"role:<role>"`. Null for ephemeral worktrees without a stable handle. |
| `visibility` | `string/null` | `null` | Launcher | Worker visibility class: `"foreground"` (dashboard panes), `"background"` (off-dashboard windows), or `null` (unknown/legacy). Reserved value `"hidden"` is NOT written by any current launcher. |

### Derivation Rules

- **`session_handle`**: Composed from existing launcher data. Format is `"<transport>:<lane_id>"`:
  - Steward launcher → `"steward:<lane_id>"` (e.g., `"steward:author-b"`)
  - Legacy launcher → `"role:<role>"` (e.g., `"role:author"`)
  - Ephemeral/unknown → `null`

- **`visibility`**: Written by launchers based on tmux layout:
  - Dashboard panes (author-a, author-b, review, ops in `dashboard` window) → `"foreground"`
  - Off-dashboard windows (author-c, author-d, author-scratch) → `"background"`
  - Legacy `start-role-worktree.sh` → `null` (no tmux layout info)
  - Missing/unknown → `null` (reader defaults)

### Backward Compatibility Rules

1. **Missing fields default to `null`**: Older registry entries without `session_handle` or `visibility` are valid. Readers must `.setdefault()` both to `null`.
2. **No schema_version bump**: These are additive nullable fields on the existing v2 schema. No version migration needed.
3. **v1 entries**: The existing v1→v2 inference in `list_worktrees_registry()` already defaults missing fields. We add `session_handle` and `visibility` to the same defaulting block.

### Display Name Defaults

The existing `display_name` field is already in the schema but always written as `null`. This slice adds launcher-written defaults:

| lane_id | display_name |
|---------|-------------|
| `author-a` | `"Author A"` |
| `author-b` | `"Author B"` |
| `author-c` | `"Author C"` |
| `author-d` | `"Author D"` |
| `author-scratch` | `"Scratch"` |
| `review` | `"Review"` |
| `ops` | `"Ops"` |
| Legacy role lanes | `null` (no change) |

### Operator Surface Changes

#### `ops.py worktrees --json` (matched entries)

Add `visibility` and `session_handle` to each matched entry dict:

```json
{
  "path": "...",
  "branch": "...",
  "lane_id": "author-a",
  "class": "persistent",
  "visibility": "foreground",
  "session_handle": "steward:author-a"
}
```

#### `ops.py status --json` (lanes array)

Add `visibility` and `session_handle` to each lane dict:

```json
{
  "lane_id": "author-a",
  "visibility": "foreground",
  "session_handle": "steward:author-a",
  ...existing fields...
}
```

#### `ops.py status` (text output)

No layout change to the text status line. The `visibility` field is informational and surfaced only in JSON. The text output already shows enough context via state badges and task info.

#### `ops.py worktrees` (text output)

Append visibility badge after lifecycle class:

```
  author-a        [persistent ] [fg ] codex/steward-author
  author-c        [persistent ] [bg ] codex/steward-author-c
  review          [persistent ] [—  ] detached
```

Where `fg` = foreground, `bg` = background, `—` = null/unknown.

## File-by-File Implementation Plan

### 1. `.claude/tmux/steward-session.sh`

- Add `session_handle` and `visibility` parameters to `write_lane_metadata()` function
- Add `display_name` parameter to `write_lane_metadata()` function
- Update all 7 `write_lane_metadata` call sites with the new args
- Dashboard lanes get `visibility="foreground"`, off-dashboard get `visibility="background"`

### 2. `.claude/scripts/start-role-worktree.sh`

- Add `session_handle`, `visibility`, `display_name` fields to `write_registry()` heredoc
- `session_handle` = `"role:${role}"`, `visibility` = `null`, `display_name` = `null`

### 3. `src/bid_euchre/ops/worktrees.py`

- In `list_worktrees_registry()`, add `.setdefault("session_handle", None)` and `.setdefault("visibility", None)` to the v1→v2 inference block
- Also add defaults in a new block for v2 entries missing the additive fields (backward compat for entries written before this PR)

### 4. `src/bid_euchre/ops/status.py`

- Add `visibility: str | None = None` and `session_handle: str | None = None` fields to `LaneStatus` dataclass
- In `synthesize_lane_activity()`, read these from lane data and pass to `LaneStatus` constructor
- In `format_status_json()`, include `visibility` and `session_handle` in lane dicts
- No change to `format_status_text()` (visibility only in JSON)

### 5. `scripts/internal/ops.py`

- In `cmd_worktrees()`, add `visibility` and `session_handle` to matched JSON output
- In `cmd_worktrees()` text output, add visibility badge after class column

### 6. `.claude/runtime/worktree_registry/README.md`

- Add `session_handle` and `visibility` to the fields table
- Add to v2 examples
- Add to v1→v2 migration table

### 7. `.claude/runtime/session_metadata/README.md`

- No changes needed (session_handle lives in registry, not session metadata)

### 8. Tests

- `test_ops_worktrees.py`: Test normalization defaults for entries missing `session_handle`/`visibility`
- `test_ops_status.py`: Test that `LaneStatus` carries `visibility`/`session_handle` from registry
- `test_ops_cli.py`: Test JSON output includes the new fields
- `test_steward_session.py`: Test that bash syntax still validates (already covered by `bash -n`)

## Outcome

_Filled after implementation._
