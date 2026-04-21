---
name: fleet-check
description: Consolidated orchestrator cron — polls inbox, checks CPU load, detects task completions, dispatches new work, and runs a full check-in cycle. Use via durable cron (/loop 8m /fleet-check).
---

# /fleet-check -- Orchestrator Consolidated Cron

Single consolidated skill for the orchestrator's periodic duties. Replaces
the previous pattern of three separate cron jobs (CPU check, analyst completion
check, and `/check-in`). Designed for durable cron invocation
(`/loop 8m /fleet-check`) that survives `/clear`.

## When to Use

- You are the orchestrator and need a single durable cron for fleet management
- After a `/clear`, the orchestrator needs to resume periodic duties
- You want to consolidate scattered monitoring into one invocation

## Arguments

None. Runs all sub-checks in sequence.

## Workflow

This skill runs the following checks in order. Each step is independent --
a failure in one step does not block subsequent steps.

### Step 1 -- Inbox Poll (MANDATORY FIRST)

**Always poll the inbox first.** This is the only channel through which ops,
authors, and the review lane can escalate to the orchestrator.

```bash
uv run python scripts/internal/ops.py inbox --lane orchestrator --status pending --include-native --prioritized
```

Process messages by priority tier:
- **P0** (`supervisor_alert`, `recovery`): Handle immediately
- **P1** (`completion`, `escalation`, `blocker`): Process and ack
- **P2** (`ack`, `progress`): Note and ack

Ack all processed messages:
```bash
uv run python scripts/internal/ops.py inbox ack <MSG_ID> --lane orchestrator
```

### Step 2 -- CPU Load Check

Check system CPU load and park lanes if overloaded:

```bash
# Check load average
sysctl -n vm.loadavg 2>/dev/null || uptime

# If load > threshold (e.g., > 8 on 10-core), consider parking a lane:
# uv run python scripts/internal/ops.py lane park <lane-id>
```

### Step 3 -- Task Completion Check

Check for completed tasks and dispatch new work:

```bash
# Check task queue for completed items
uv run python scripts/internal/ops.py task list

# Check per-lane state to find idle lanes (heartbeat-aware, post-#2415)
uv run python scripts/internal/ops.py --json lane status --all | \
  jq -r '.[] | select(.phase == "idle" or .phase == "stale") | .lane_id'
```

For each completed task:
1. Verify the PR was merged (or note if still open)
2. Update any governing plan checkpoints
3. Identify the next dispatchable task

For each idle lane (from `lane status` output above, not `dashboard`):
1. Check if there are approved task packets in the queue
2. Dispatch if scope is clear and lane is healthy

> **Do not use `dashboard`'s `[stale!]` flag to infer idle-ness.** The
> dashboard classifier relies on a 30-minute `last_active` registry
> heuristic, which mis-classifies working lanes as stale during long
> validation runs (#2415 F1). `lane status --all` uses the Signal 0
> heartbeat + process-tree reconciler and gets it right.

### Step 4 -- Full Check-In

Run the standard check-in cycle for situational awareness:

```bash
# Per-lane health via the heartbeat-aware classifier (preferred for
# per-lane liveness classification — see #2415, PR #2695)
uv run python scripts/internal/ops.py lane status --all

# Aggregate dashboard — still the right tool for token economy,
# attention items, task-queue totals, and warnings. Do NOT read per-lane
# liveness from here; it uses the older 30-minute `last_active` heuristic.
uv run python scripts/internal/ops.py dashboard

# Open PRs status
gh pr list --state open --json number,title,headRefName --limit 20

# Any stuck lanes
# (Use /capture-pane --stuck if needed)
```

> **Known limitation — pre-#2686 sessions.** The heartbeat writer
> (`.claude/runtime/lane_status/<lane>.json`) shipped in PR #2686 on
> 2026-04-21. Sessions that launched **before** that restart do not write
> heartbeats. For those lanes, `lane status` falls back to stale registry
> evidence and may show `stale!` even though the pane is alive. This
> primarily affects the control-plane lanes (orchestrator, ops, review)
> until each one restarts. Cross-check with `capture-pane` when a
> long-running lane unexpectedly reports stale.

### Step 5 -- Remote Status Update (Optional)

If operator away-mode is active and Telegram is configured, push a status
summary:

```bash
uv run python scripts/internal/ops.py away --check
```

If away, the monitor cycle (run by ops lane) handles Telegram push. The
orchestrator only needs to ensure the ops lane is running.

## Durable Cron Setup

The orchestrator should run this skill on a repeating schedule:

```
/loop 8m /fleet-check
```

This replaces the previous three-cron pattern:
- ~~`/loop 12m` CPU-aware fleet check~~ -> Step 2
- ~~`/loop 6m` analyst completion check~~ -> Step 3
- ~~`/loop 8m /check-in`~~ -> Steps 1 + 4

## Gotchas

- **Inbox first, always.** The 2026-03-24 overnight run proved that skipping
  the inbox causes 25+ HIGH alerts to go unread for hours.
- This skill is for the **orchestrator only**. Ops uses `/monitor`, review
  uses `/check-reviews`.
- If CPU load is high, park flex lanes first (they are lowest priority).
- Task dispatch should respect scope isolation -- never dispatch two tasks
  that touch overlapping file patterns to different lanes.
- Keep the check cycle under 2 minutes to avoid overlapping with the next
  cron invocation.

## References

- `.claude/skills/check-in/SKILL.md` -- the original check-in skill (now
  subsumed by Step 1 + Step 4 of this skill)
- `.claude/skills/monitor/SKILL.md` -- ops lane monitoring (complementary)
- `.claude/skills/delegate-task/SKILL.md` -- task dispatch workflow
- `.claude/skills/lane-status/SKILL.md` -- lane health assessment
- Issue #2415 + PR #2686 (heartbeat writer) + PR #2695 (`lane status`
  consumer CLI) -- the Signal 0 heartbeat infrastructure that replaces
  the old registry-based stale classification
