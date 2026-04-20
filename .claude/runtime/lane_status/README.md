# lane_status/

Per-lane heartbeat snapshots emitted after every tool call by
`.claude/hooks/lane-heartbeat-post-tool.sh`.  Each file is an ephemeral
liveness indicator — **not a source of truth**.

This directory is gitignored except for this README.  Files are recreated
automatically whenever a lane runs a tool; they are safe to delete at any
time.

## Schema (v1)

One file per lane, named `<lane_id>.json`:

```json
{
  "schema_version": 1,
  "lane_id": "author-a",
  "pid": 12345,
  "session_id": "s-abc...",
  "updated_at": "2026-04-20T23:05:49Z",
  "last_tool": "Bash",
  "phase": "implementing",
  "extras": {"cwd": "/path/to/worktree"}
}
```

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | Current version: `1`.  Bump on breaking changes. |
| `lane_id` | string | Canonical lane identity (`author-a`, `analyst-b`, ...). |
| `pid` | int | Process id of the writing Claude session. |
| `session_id` | string \| null | Best-effort session identifier from `CLAUDE_SESSION_ID`. |
| `updated_at` | ISO-8601 | UTC timestamp with `Z` suffix. |
| `last_tool` | string \| null | Name of the last tool invocation (`Bash`, `Edit`, ...). |
| `phase` | string \| null | Free-form label.  Documented values: `implementing`, `validating`, `waiting`, `idle`.  Consumers must tolerate unknown phases. |
| `extras` | object | Caller-provided metadata.  Optional. |

## Writers

| Writer | When |
|--------|------|
| `.claude/hooks/lane-heartbeat-post-tool.sh` | PostToolUse (every tool call) |
| `bid_euchre.ops.lane_heartbeat.write_heartbeat` | Library entry point |

## Readers

There are no consumers in PR 1.  Readers ship in later PRs:

- **PR 2 (planned):** `status.py` signal 0 plus a lane status CLI read
  these files to classify live vs. stale lanes.
- **PR 3 (planned):** the dashboard labeling path consumes the classifier
  output to fix the F1 failure mode where active pytest/make runs are
  mislabeled `[stale!]`.

Design: see issue #2415 and analyst-b's 3-PR plan.
