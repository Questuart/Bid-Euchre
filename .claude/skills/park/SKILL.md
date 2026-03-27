---
name: park
description: Shuts down a lane cleanly by deleting all active cron jobs and clearing conversation context. Use when the orchestrator needs to park a lane or before /clear to prevent orphaned cron jobs.
---

# /park — Lane Shutdown with Cron Cleanup

Cleanly shut down the current lane by deleting all active cron jobs before
clearing conversation context. This prevents orphaned cron jobs from
continuing to fire on a lane that the orchestrator considers parked.

## Problem

`/clear` resets conversation context but does **not** kill cron jobs. Cron
jobs persist in the Claude session runtime independently of conversation
history. A "cleared" lane can still have active cron jobs burning tokens
and sending alerts to an orchestrator that has stopped reading them.

## When to Use

- The orchestrator is parking this lane (no more work to assign)
- You are about to `/clear` and want a clean shutdown
- You notice orphaned cron jobs running after a previous `/clear`
- The orchestrator sends `/park` to this lane's tmux pane

## Workflow

### Step 1 — Kill Orphaned Build/Test Processes

Before cleaning up cron jobs, kill any orphaned pytest, make, or uv processes
that were spawned from this lane's worktree. These accumulate during fleet runs
and exhaust system memory if not cleaned up.

```bash
uv run python -c "
from bid_euchre.ops.worker_pool import cleanup_lane_processes
killed = cleanup_lane_processes('<lane_id>')
print(f'Killed {len(killed)} orphaned process(es)')
"
```

Replace `<lane_id>` with the lane identity (e.g., `author-a`, `brws-author-b`).
This is safe to run even if no orphaned processes exist (returns empty list).

**Note:** `park_worker()` also calls this automatically when invoked
programmatically, so this step is primarily for manual `/park` usage.

### Step 2 — List Active Cron Jobs

Use `CronList` to see all active cron jobs in this session.

If no cron jobs are listed, skip to Step 4.

### Step 3 — Delete Each Cron Job

For **every** cron job returned by CronList, call `CronDelete` with its ID
to stop it. Do not skip any — even jobs that look harmless will continue
firing after `/clear`.

Example sequence:
```
CronList
# Shows: job_id_1 (every 3m), job_id_2 (every 15m)

CronDelete job_id_1
CronDelete job_id_2
```

### Step 4 — Verify Cleanup

Call `CronList` again to confirm the list is empty. If any jobs remain,
repeat Step 3 for the stragglers.

### Step 5 — Confirm Parked

Report the shutdown result:
- How many orphaned processes were killed (Step 1)
- How many cron jobs were deleted
- Confirmation that CronList is now empty
- The lane is safe to `/clear`

Do **not** automatically run `/clear` — let the operator or orchestrator
decide when to clear context. The park skill's job is process + cron cleanup.

## Orchestrator Usage

The orchestrator can park a lane by sending this to its tmux pane:

```bash
tmux send-keys -t <pane> '/park' Enter
```

Or for a full shutdown sequence:

```bash
tmux send-keys -t <pane> '/park' Enter
# Wait for confirmation, then:
tmux send-keys -t <pane> '/clear' Enter
```

## Gotchas

- `/clear` alone does NOT stop cron jobs — always `/park` first
- CronDelete requires the exact job ID from CronList output
- A lane with 0 cron jobs can still be `/park`ed safely (no-op)
- This skill does not remove the lane from the worker pool or modify
  task queue state — it only cleans up session-level cron jobs

## Related

- #1580 — `/clear` does not kill cron jobs (this skill is the fix)
- #1572 — idle auto-shutoff (should include cron cleanup)
- `/start-task` — the inverse: bootstraps a lane for new work

## Closes

Closes #1580 by providing an explicit lane shutdown procedure that cleans
up cron jobs before `/clear`. The operator must use `/park` (not bare
`/clear`) when shutting down a lane to prevent orphaned cron jobs.
