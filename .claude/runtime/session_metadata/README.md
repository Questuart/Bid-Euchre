# Session Metadata

Runtime metadata for active and recent sessions. JSON files in this directory
are gitignored; only this README is committed.

## Schema (v2)

Each session writes a JSON file named `<session_id>.json`.

### v2 Example

```json
{
  "schema_version": 2,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "lane_id": "author-a",
  "role": "author",
  "started_at": "2026-03-18T10:00:00Z",
  "task": "Implement chart_data extraction",
  "plan_link": "plans/sessions/2026-03-16_chart-data.md",
  "last_checkpoint": "Step 3 complete",
  "worktree_path": "../Bid-Euchre-steward-author"
}
```

### Fields

| Field | Type | Required | Since | Description |
|-------|------|----------|-------|-------------|
| `schema_version` | int | yes | v1 | Schema version (`2` for this version) |
| `session_id` | string | yes | v1 | UUID v4 identifying this session |
| `lane_id` | string | yes | v2 | Canonical lane identity (e.g., `author-a`, `review`, `ops`) |
| `role` | string | no | v1 | Legacy role compatibility field. Optional in v2; will be removed in a future version. |
| `started_at` | string | yes | v1 | ISO 8601 timestamp of session start |
| `task` | string | no | v1 | Short description of the current task |
| `plan_link` | string | no | v1 | Relative path to the governing or session plan file |
| `last_checkpoint` | string | no | v1 | Free-text description of the last completed checkpoint |
| `worktree_path` | string | yes | v1 | Path to the worktree this session operates in |

### Field Semantics

**`lane_id`** is the canonical machine identity, matching the `lane_id` in
the worktree registry entry for this session's worktree. New code should
use `lane_id` exclusively for routing and lookup.

**`role`** is retained as an optional compatibility field during the
transition from the three-role model. It maps legacy role names to the
session so older tooling can still find sessions by role. It will be
removed in a future version once all consumers read `lane_id`.

### Lifecycle

1. **Created** when a launcher starts a session (`steward-session.sh` or
   legacy `start-agent-role.sh`).
2. **Updated** as the session progresses (`task`, `last_checkpoint`).
3. **Preserved** after session ends for resume and audit.
4. **Archived** during session compaction (future scope).

### Resume

To resume a session, read the most recent session file for the desired lane
(filter by `lane_id`), check its `last_checkpoint` and `plan_link`, and
continue from the recorded state. No conversation history is required --
the checkpoint and plan provide sufficient context.

### v1 Compatibility

v1 session files use `role` as the primary identity and do not include
`lane_id`. v2 readers should infer `lane_id` from `role` using the same
mapping as the worktree registry:

| v1 `role` | Inferred `lane_id` |
|-----------|-------------------|
| `author` | `author-a` |
| `review` | `review` |
| `ops` | `ops` |

Writers should produce v2 entries. v1 entries remain readable.
