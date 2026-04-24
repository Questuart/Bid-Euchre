---
name: read-ops-brief
description: Orchestrator-lane skill that consumes the deterministic ops signal bridge (`ops.py orchestrator brief`), routes each finding to its action handler, and acks supervisor_alert messages AFTER routing. Replaces ad-hoc `gh pr list` / `ops.py task list` / `ops.py inbox` scans in orchestrator cron fires.
---

# /read-ops-brief — Deterministic Ops Signal Bridge

> **Invoked by:** the orchestrator lane at the start of every cron fire.
> **Replaces:** ad-hoc `gh pr list` / `ops.py task list` / `ops.py inbox` scans.
> **Authoritative contract:** `docs/01_core/orchestrator_brief_schema.md`.

## Purpose

Before #2806, orchestrator cron fires reinvented subsets of the ops monitor's
work via shell: `gh pr list`, `ops.py task list`, `ops.py inbox`. Neither the
ops monitor's `supervisor_alert` findings nor the cron's ad-hoc scans were
authoritative — and coarse `ack-all` on the orchestrator side dropped the
monitor's findings wholesale.

This skill consumes `ops.py orchestrator brief --json` — a single, stable,
deterministic JSON document covering every observation the orchestrator cron
needs, including the **expanded `findings[]` arrays** from recent unacked
`supervisor_alert` messages — and routes each finding to a specific action
handler.

## When to Use

- **At the start of every orchestrator cron fire** (mandated by
  `.claude/rules/prompt_policy/orchestrator.md`).
- When the operator invokes `/read-ops-brief` manually to surface recent
  ops signal without tripping a full monitor cycle.
- As the first step in any orchestrator-lane skill that depends on current
  fleet state (open PRs, dispatched packets, pending inbox).

## Arguments

- `--recent N` (optional) — Expand the most recent N unacked
  `supervisor_alert` messages. Default: `5`.
- `--no-ack` (optional) — Route findings but do not ack alerts. Useful when
  the operator wants to inspect the brief without advancing state.

## Workflow

### Step 1 — Invoke the brief

```bash
uv run python scripts/internal/ops.py --json orchestrator brief --recent 5
```

> **Note the flag order:** `--json` is a top-level parser flag and must come
> **before** the `orchestrator brief` subcommand.

Capture stdout as the brief JSON. Exit non-zero means the CLI itself is
broken — surface a blocker to the operator; do **not** fall back to shell
scans (that reintroduces the bug this skill exists to fix).

### Step 2 — Validate schema version

```python
assert brief["schema_version"] == 1, "schema bumped — update this skill"
```

If the schema version has bumped, stop and surface to the operator: the
skill ships in the same PR as the bump per the schema doc's versioning
rules.

### Step 3 — Route each finding

For each `alert` in `brief["recent_ops_alerts"]`, for each `finding` in
`alert["findings"]`, dispatch to the handler named in the routing table
below. The table is **authoritative** — the schema doc's Finding category
→ action handler table is the source of truth; this skill stays in sync.

| `category` | Handler |
|---|---|
| `pr_merged` | Look up dispatched packet whose `pr_number` metadata matches `details.pr`. If found, complete packet (post-merge hook normally handles this; reconciliation is a no-op). Surface merge to narration. |
| `pr_ready` | Verify CI green + review verdict; if merge preconditions met, route to operator for merge decision. Do **not** auto-merge. |
| `pr_status` | If `severity == "high"` and summary mentions conflicts: message the owning lane as `blocker` with conflict details. Else: include in narration. |
| `ci_status` | Dispatch a recovery message to the owning lane; flag for manual retry if no owner can be inferred. |
| `stale_dispatch` | Send reminder to `details.lane_id`. If `age > 60 minutes`, file a `blocker` against the lane. |
| `lane_idle` | Consider auto-dispatch from approved packets (already handled by `check_auto_dispatch`; brief just surfaces the signal). |
| `lane_health` | For `severity == "high"` (dead pane, critical health): surface to operator via `supervisor_alert`-tagged inbox message. Do **not** auto-recover without operator confirmation. |
| `fleet_idle` | Before acting on `details.should_shutoff == true`, cross-check `brief["dispatched_packets"]` and `brief["tui_task_status"]["in_progress"]`. If either is non-zero, mark **false positive** and file a bug against the ops classifier. |
| `approval_stall` | Trigger the approval-stall recovery flow (Escape + nudge); escalate to operator if stall persists past the next cycle. |
| `stall_detection` | Cross-reference with `dispatched_packets` age and lane activity. If the lane still has forward progress, treat as false positive. Otherwise schedule a recovery pass next cycle. |
| `stall_recovery` | Narrate the recovery attempt; no additional action (the monitor has already acted). If recovery cycles repeat on the same lane, escalate to operator. |
| `merged_dispatch` | Reconcile with `dispatched_packets`: the packet whose PR number matches should now be `completed`. If still `dispatched`, flag a reconciliation gap. |
| `auto_dispatch` | Narrate: the monitor auto-dispatched a packet to an idle lane. No action beyond logging. |
| `escalation` | Re-surface the escalation alert as its own `supervisor_alert` routing pass; do **not** ack until the underlying alert is handled. |
| (other) | LLM-judgment fallback. Append the unknown category as a single JSON line to `.claude/runtime/orchestrator_brief_unknown_categories.jsonl` so the archivist can flag new categories that need handlers. |

### Step 4 — Ack supervisor_alert messages AFTER routing

Once **every** finding across **every** alert has been routed, ack each
`supervisor_alert`:

```bash
uv run python scripts/internal/ops.py inbox ack <MSG_ID> --lane orchestrator
```

> **Ack ordering is critical.** Ack-after-routing ensures that if the
> orchestrator crashes mid-cycle, the next cycle still sees the alert and
> re-runs routing (idempotent handlers tolerate this). Never ack before
> routing; never use `--bulk` to ack a batch that contains unrouted
> alerts.

If invoked with `--no-ack`, skip this step.

### Step 5 — Surface a structured summary for narration

Emit a concise narration block for the orchestrator to act on:

```
Ops brief (generated <brief.generated_at>, last read <brief.last_read_at>):
- <K> recent supervisor_alerts routed (<N> findings across <M> categories)
- <P> open PRs (<Q> green, <R> blocked, <S> pending)
- <T> merged PRs since last read
- <U> dispatched packets ({author-a: 1, author-b: 2, ...})
- Pending inbox: {supervisor_alert: <v>, blocker: <w>, ...}
- TUI task status: <in_progress>/<pending>/<blocked>/<completed> (total <n>)

Routing outcomes:
- <handler-name> → <action-taken>
- ...
```

### Step 6 — Advance last-read watermark

After routing and acking succeed, advance the watermark so the next cycle's
`merged_prs_since_last_read` window does not re-emit the same merges:

```bash
uv run python scripts/internal/ops.py --json orchestrator brief --mark-read > /dev/null
```

(A second call is intentional — the first call is the authoritative read;
the second call's only purpose is to persist the timestamp. An
optimization could merge them, but the two-call pattern keeps the
skill trivial to reason about.)

## Example

```bash
# Full cron-fire usage:
uv run python scripts/internal/ops.py --json orchestrator brief --recent 5 > /tmp/brief.json

# Inspect findings without advancing state:
uv run python scripts/internal/ops.py --json orchestrator brief --recent 10
```

## Gotchas

- **Do NOT fall back to `gh pr list` / `ops.py task list` / `ops.py inbox`
  on brief failure.** If the CLI is broken, surface the blocker. The whole
  point of this skill is to route through a single, deterministic bridge.
- **Do NOT ack alerts before routing their findings.** Ack-after-routing is
  the idempotency contract. Breaking it reintroduces the #2806 bug.
- **Unknown categories are a soft signal, not a hard failure.** Log them to
  the JSONL sink and continue. The archivist reviews the sink and proposes
  new routing-table rows.
- **The brief is schema-stable under empty fleet** — every top-level key is
  always present. Empty arrays are `[]`, not missing. `last_read_at` is
  `null` on first-ever read, never missing. Treat "empty" as "no signal,"
  not as "nothing to see."
- **Partial failure within the brief is handled by the CLI, not this
  skill.** If a data source raises, the CLI sets that key to its
  empty-state value and logs the failure. The skill treats empty values as
  "signal unavailable, fall back to LLM judgment," not as "nothing to see."
- **False-positive guard for `fleet_idle`.** The ops classifier emits
  `fleet_idle` with `should_shutoff=true` when it sees zero active panes.
  But if `dispatched_packets` or `tui_task_status.in_progress` is non-zero,
  that is a classifier bug — file it, do not shut off.

## References

- `docs/01_core/orchestrator_brief_schema.md` — authoritative contract
- `src/bid_euchre/ops/orchestrator_brief.py` — brief builder (producer side)
- `scripts/internal/ops.py orchestrator brief` — CLI entry point
- `.claude/rules/prompt_policy/orchestrator.md` — mandate to begin every
  cron fire with this skill
- `src/bid_euchre/ops/monitor.py` — producer of `MonitorFinding` dataclasses
- Issue #2806 — problem analysis and design rationale
- Issue #2805 — superseded by #2806
