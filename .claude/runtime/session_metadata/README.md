# Session Metadata

Runtime metadata for active and recent sessions. JSON files in this directory
are gitignored; only this README is committed.

## Schema (v1)

Each session writes a JSON file named `<session_id>.json`.

```json
{
  "schema_version": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "author",
  "started_at": "2026-03-16T22:00:00Z",
  "task": "Implement chart_data extraction",
  "plan_link": "plans/sessions/2026-03-16_chart-data.md",
  "last_checkpoint": "Step 3 complete",
  "worktree_path": "../Bid-Euchre-author"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | int | yes | Always `1` for this version |
| `session_id` | string | yes | UUID v4 identifying this session |
| `role` | string | yes | Role assumed by this session (`author`, `review`, `ops`) |
| `started_at` | string | yes | ISO 8601 timestamp of session start |
| `task` | string | no | Short description of the current task |
| `plan_link` | string | no | Relative path to the governing or session plan file |
| `last_checkpoint` | string | no | Free-text description of the last completed checkpoint |
| `worktree_path` | string | yes | Path to the worktree this session operates in |

### Lifecycle

1. **Created** when `start-agent-role.sh` launches a session.
2. **Updated** as the session progresses (task, last_checkpoint).
3. **Preserved** after session ends for resume and audit.
4. **Archived** during session compaction (future PR-4 scope).

### Resume

To resume a session, read the most recent session file for the desired role,
check its `last_checkpoint` and `plan_link`, and continue from the recorded
state. No conversation history is required — the checkpoint and plan provide
sufficient context.
