# Orchestrator Brief — JSON Schema

> Stable schema for `scripts/internal/ops.py orchestrator brief`. This
> document is the **contract** between the ops cron (producer of
> `supervisor_alert` payloads) and the orchestrator cron (consumer via
> `/read-ops-brief`).

## Purpose

Before #2806, two parallel monitor loops duplicated work: the ops lane
emitted rich structured `supervisor_alert` payloads to the orchestrator
inbox, and the orchestrator separately ran `gh pr list`, `ops.py task
list`, `ops.py inbox` via ad-hoc shell. Neither was authoritative; ops's
findings were dropped wholesale by coarse `ack-all` on the orchestrator
side.

`ops.py orchestrator brief` is the deterministic bridge. It produces a
single JSON document covering every observation the orchestrator cron
needs — including the **expanded `findings[]` arrays from recent
unacked `supervisor_alert` messages**. The orchestrator consumes this
via `/read-ops-brief` rather than reinventing subsets via bash.

## CLI

```bash
uv run python scripts/internal/ops.py orchestrator brief [--recent N] [--mark-read] [--json]
```

- `--recent N` — Expand the most recent N unacked `supervisor_alert`
  messages. Default: `5`.
- `--mark-read` — After printing, persist the current timestamp to
  `.claude/runtime/orchestrator_brief_state.json` so the next call's
  `merged_prs_since_last_read` window advances.
- `--json` — Emit JSON (the default; non-JSON mode is a brief
  human-readable summary for debugging).

Output is written to stdout. Exit code `0` on success, non-zero only on
CLI argument errors.

## Schema

```json
{
  "schema_version": 1,
  "generated_at": "2026-04-24T18:00:00Z",
  "last_read_at": "2026-04-24T17:30:00Z",
  "recent_ops_alerts": [
    {
      "message_id": "...",
      "created_at": "2026-04-24T17:45:00Z",
      "age_minutes": 15,
      "severity": "high",
      "priority": "high",
      "status": "pending",
      "summary": "Monitor: 1 HIGH, 2 warn, 3 info findings",
      "high_count": 1,
      "warn_count": 2,
      "info_count": 3,
      "findings": [
        {
          "category": "pr_merged",
          "severity": "info",
          "summary": "PR #2800 merged: ... (branch-name)",
          "details": {"pr": 2800, "title": "...", "branch": "...", "merged_at": "..."}
        }
      ]
    }
  ],
  "open_prs": [
    {
      "number": 2797,
      "title": "...",
      "branch": "...",
      "mergeable": "CONFLICTING",
      "ci_state": "blocked",
      "failing_checks": ["tests"]
    }
  ],
  "merged_prs_since_last_read": [
    {"number": 2800, "title": "...", "branch": "...", "merged_at": "..."}
  ],
  "pending_inbox_by_type": {
    "supervisor_alert": 3,
    "blocker": 0,
    "ack": 12,
    "completion": 2,
    "escalation": 1
  },
  "dispatched_packets": [
    {
      "packet_id": "...",
      "owner": "author-a",
      "title": "...",
      "priority": "high",
      "age_minutes": 42
    }
  ],
  "tui_task_status": {
    "in_progress": 5,
    "pending": 3,
    "blocked": 1,
    "completed": 12,
    "abandoned": 0,
    "total": 21
  }
}
```

### Field semantics

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | Bumped on breaking schema changes. Consumers must check. |
| `generated_at` | ISO-8601 UTC | `Z` suffix. |
| `last_read_at` | ISO-8601 UTC or `null` | Timestamp persisted by a prior `--mark-read` call; `null` on first-ever read. |
| `recent_ops_alerts[]` | list | Up to `--recent N` unacked `supervisor_alert` messages for the `orchestrator` lane, newest first. |
| `recent_ops_alerts[].findings[]` | list | **Expanded** `MonitorFinding` dicts from the alert's payload — this is the data the prior design was dropping via `ack-all`. |
| `open_prs[]` | list | Result of `gh pr list --state open --limit 20`. `ci_state` is one of `green`, `blocked`, `pending`, `unknown`. |
| `merged_prs_since_last_read[]` | list | Result of `gh pr list --state merged --limit 20` filtered by `mergedAt > last_read_at`. When `last_read_at` is null, returns the most recent 10 merges. |
| `pending_inbox_by_type` | object | Counts of `pending`+`delivered` messages in the `orchestrator` inbox, grouped by `message_type`. |
| `dispatched_packets[]` | list | All task packets with `status == "dispatched"`, sorted by `created_at` ascending. |
| `tui_task_status` | object | Aggregate counts from `.claude/runtime/task_state/*.json` (durable task records). `total` is the sum of all status buckets. |

### Severity mapping for `recent_ops_alerts[].severity`

The alert's payload stores only `priority` on the message envelope. The
brief derives a `severity` field for convenience:

| Message `priority` | Derived `severity` |
|---|---|
| `urgent`, `high` | `high` |
| `normal` | `warn` |
| `low` | `info` |

Individual findings inside `findings[]` keep their own `severity` from
the ops monitor (`high`, `warn`, `info`).

### CI state derivation for `open_prs[].ci_state`

| Condition | `ci_state` |
|---|---|
| Any check in (`FAILURE`, `ERROR`, `CANCELLED`) | `blocked` |
| All checks `SUCCESS` or `COMPLETED` | `green` |
| Any check still `PENDING`/`IN_PROGRESS`/`QUEUED` | `pending` |
| No checks reported | `unknown` |

## Finding category → action handler table

The `/read-ops-brief` skill routes each finding in
`recent_ops_alerts[*].findings[]` to a specific handler based on
`category`. This table is the **authoritative routing contract**; the
skill implementation must stay in sync with this list.

| `category` | Handler |
|---|---|
| `pr_merged` | Look up dispatched packet whose `pr_number` metadata matches `details.pr`; if found, complete packet (post-merge hook already handles this, so typically a no-op reconciliation). Surface merge to orchestrator narration. |
| `pr_ready` | Verify CI green + review verdict; if merge preconditions met, route to operator for merge decision. Do not auto-merge. |
| `pr_status` | If `severity == "high"` and summary mentions conflicts: message the owning lane as `blocker` with conflict details. Else: include in narration. |
| `ci_status` | Dispatch a recovery message to the owning lane (or flag for manual retry if no owner can be inferred). |
| `stale_dispatch` | Send a reminder inbox message to `details.lane_id`; if age > 60 minutes, file a blocker against the lane. |
| `lane_idle` | Consider auto-dispatch from approved packets (already handled by `check_auto_dispatch`; brief just surfaces the signal). |
| `lane_health` | For `severity == "high"` (dead pane, critical health): surface to operator via `supervisor_alert`-tagged inbox message; do not auto-recover without operator confirmation. |
| `fleet_idle` | Before acting on `should_shutoff=true`, cross-check against `dispatched_packets` and `tui_task_status.in_progress`. If either is non-zero, mark as **false positive** and file a bug against the ops classifier. |
| `approval_stall` | Trigger the approval-stall recovery flow (Escape + nudge); escalate to operator if the stall persists past the next cycle. |
| `stall_detection` | Cross-reference with `dispatched_packets` age and lane activity; if the lane still has forward progress, treat as false positive. Otherwise schedule a recovery pass next cycle. |
| `stall_recovery` | Narrate the recovery attempt; no additional action (the monitor has already acted). If recovery cycles repeat on the same lane, escalate to operator. |
| `merged_dispatch` | Reconcile with `dispatched_packets`: the packet whose PR number matches should now be `completed`. If still `dispatched`, flag a reconciliation gap. |
| `auto_dispatch` | Narrate: the monitor auto-dispatched a packet to an idle lane. No action beyond logging. |
| `escalation` | Re-surface the escalation alert as its own `supervisor_alert` routing pass; do **not** ack until the underlying alert is handled. |
| (other) | LLM judgment fallback. Log the unknown category to `.claude/runtime/orchestrator_brief_unknown_categories.jsonl` so the archivist can flag new categories that need handlers. |

### Ack ordering

The skill **must** route all findings before acking any
`supervisor_alert` message. Ack-after-routing ensures that if the
orchestrator crashes mid-cycle, the next cycle still sees the alert and
re-runs the routing (idempotent handlers tolerate this).

## State file

`--mark-read` writes to `.claude/runtime/orchestrator_brief_state.json`:

```json
{
  "schema_version": 1,
  "last_read_at": "2026-04-24T18:00:00Z"
}
```

This file is gitignored (all `.claude/runtime/*.json` is) and is
rewritten atomically. Read failure is treated as "no previous read"
(returns `last_read_at = null`).

## Invariants

1. **Schema stability under empty fleet.** Every top-level key is
   always present. Empty arrays are `[]`, not omitted. `last_read_at`
   is `null` on first-ever read, never missing.
2. **No partial failure.** If any data source raises, the brief emits
   `generated_at` and whatever keys succeeded; failed keys are set to
   the empty-state value. The skill treats empty values as "signal
   unavailable, fall back to LLM judgment," not as "nothing to see."
3. **Deterministic.** Given the same filesystem state and same GitHub
   responses, two consecutive calls produce identical JSON (except
   `generated_at` and derived `age_minutes`).
4. **Single shell call.** The brief is one `ops.py orchestrator brief
   --json` invocation. The skill does not call `gh`, `ops.py task list`,
   or `ops.py inbox` separately.

## Versioning

Breaking schema changes bump `schema_version`. Additive changes
(new optional fields, new finding categories in the routing table) do
not bump the version but must preserve all existing keys.

`/read-ops-brief` pins the schema version it tolerates and refuses to
proceed on a mismatch. When the schema bumps, the skill ships in the
same PR as the bump.

## References

- Issue #2806 — problem analysis and design rationale
- Issue #2805 — superseded by #2806 (LLM-level prompt change approach)
- `src/bid_euchre/ops/monitor.py` — producer of `MonitorFinding`
  dataclass consumed here
- `src/bid_euchre/ops/message_bus.py::BusMessage` — envelope format of
  `supervisor_alert` messages
- `src/bid_euchre/ops/task_queue.py::TaskPacket` — dispatched-packet
  shape
- `src/bid_euchre/ops/status.py::load_tasks` — source of
  `tui_task_status`
- `.claude/skills/read-ops-brief/SKILL.md` — consumer-side routing
