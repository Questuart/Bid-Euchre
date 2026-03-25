---
name: run-fleet
description: Run the steward fleet autonomously — maximize safe, mergeable throughput across all tracks by continuously dispatching, monitoring, triaging, and recovering lanes.
---

# /run-fleet — Autonomous Fleet Orchestration

Run the steward fleet continuously and autonomously, maximizing safe
mergeable throughput across all defined tracks.

## When to Use

- User says "run", "go", "run fleet", "keep going", or similar
- Starting a new autonomous orchestration session after a handoff
- Resuming orchestration after a break

## Startup Checklist

Before entering the main dispatch loop:

1. Recover context (`/recovering-context` or read MEMORY.md)
2. **Set up inbox polling cron** — ensures inbox is read even if the
   orchestrator gets absorbed in a long task and skips check-in cycles.
   **Deduplicate first:** list existing crons and delete any stale
   inbox-poll cron before creating a new one (prevents duplicates when
   `/run-fleet` is re-invoked or the session is resumed):
   ```
   CronList  → scan for any cron whose command contains "ops.py inbox"
   CronDelete <id>  → remove each matching cron

   CronCreate: every 2 minutes, run:
     uv run python scripts/internal/ops.py inbox --lane orchestrator --status pending
     If P0 messages found, surface them immediately.
   ```
   This is the backup mechanism. The primary mechanism is step 0 of every
   dispatch cycle (see Dispatch Discipline below).
3. Check dashboard health: `uv run python scripts/internal/ops.py dashboard --json`
4. Bulk-refresh idle lanes:
   ```bash
   uv run python scripts/internal/ops.py lane refresh --all-idle
   ```
5. Triage inbox and open issues; route ambiguous or multi-PR shaping work to
   `steward-analyst`
6. Define Wave 1 candidates

## Primary Goal

Maximize safe, mergeable throughput across all defined tracks.

## Secondary Goals

- Keep as many lanes productively busy as possible
- Maintain full operator observability through the steward layout
- Minimize token waste, rework, and manual babysitting
- Leave behind a clear next-wave plan, not just partial work

## Execution Model

- Run continuously and autonomously
- Treat waves as planning buckets, not hard synchronization barriers
- Do not wait for an entire wave to finish if part of the next wave is
  already unblocked
- Always keep a 2-wave lookahead:
  - while Wave N is executing, define Wave N+1
  - before Wave N completes, sketch Wave N+2
- Prefer steady pipeline flow over batch pauses

## Source of Truth

- The handoff (session context, MEMORY.md, checkpoints) defines the active
  tracks, lane pools, governing plans, sub-plans, constraints, and initial
  dispatch candidates
- If the handoff and repo state disagree, verify the repo state and adapt
  without breaking the governing plan

## Dispatch Discipline

Before each dispatch cycle:

0. **MANDATORY: Poll inbox for P0/P1 messages**
   ```bash
   uv run python scripts/internal/ops.py inbox --lane orchestrator --status pending
   ```
   Scan pending messages and classify by priority:
   - **P0 (urgent):** `supervisor_alert`, `recovery` — **STOP. Process these
     before dispatching any new work.** These represent active incidents that
     may invalidate planned dispatches.
   - **P1 (high):** `completion`, `escalation`, `blocker` — process completions
     (to free lanes) and escalations (to unblock lanes) before evaluating new
     dispatch candidates.
   - **P2 (normal/low):** `ack`, `progress` — note and continue.

   If you skip this step, you risk dispatching into broken lanes, missing
   merge-conflict alerts, or duplicating work that another lane already
   completed. The overnight run of 2026-03-24 proved this: 25+ HIGH alerts
   went unread for 7 hours because the orchestrator never polled its inbox.

1. Check lane health, dirty worktrees, stale packets, inbox backlog, open
   PRs, newly opened or updated GitHub issues, current task lists, and
   current blockers
2. Verify the candidate task is still valid, unblocked, and within scope
3. Confirm file-scope isolation
4. Dispatch to the best-fit idle lane

At session start, run a bulk lane refresh to reset all stale worktrees
before the first dispatch cycle:
```bash
uv run python scripts/internal/ops.py lane refresh --all-idle
```

> **Note:** `task dispatch` auto-refreshes the target lane, so per-dispatch
> refresh is not needed. The bulk refresh at startup is still recommended for
> observability — it surfaces dirty worktrees and stale state before work
> begins.

Rules:
- Prefer small, mergeable PRs over large speculative changes
- Only dispatch work with clear file-scope ownership
- One active writer per overlapping file set

## Analyst Routing

Use `steward-analyst` when work needs deeper shaping before execution:

- new sub-plans or major plan refreshes
- unclear implementation seams
- tests, gates, or smoke boundaries that are not obvious
- complex issue bundles that need richer evidence and PR decomposition
- restart or end-of-run handoffs
- plan/checkpoint/task-list drift relative to repo state

Expected analyst outputs:

- sub-plan or execution brief
- validation commands and gates
- risks and smoke-test boundaries
- issue package or issue update draft
- PR roadmap / safe-parallelism guidance
- restart-ready handoff

## Lane Discipline

- Respect the lane/track affinity defined in the handoff
- Use tmux-pane delivery only
- Do not use hidden subprocess agents or isolated temp worktrees unless the
  handoff explicitly authorizes them
- If a lane becomes stale or risky, use the platform's reset/recovery path
  instead of forcing more work through bad context

## Autonomy Rules

Proceed without asking for confirmation unless one of these occurs:
- Credentials, secrets, plugins, or external setup are required
- Two high-priority tasks need the same file set
- Governing plans conflict or are ambiguous
- Tests suggest a likely regression outside assigned scope
- A destructive recovery action would be required
- A user smoke test or proving step is required on the critical path

If one track is blocked, keep the others moving. If a user smoke test is
needed for only one slice, isolate that slice, mark it pending, and
continue other work.

## User Smoke-Test Rule

If a task reaches a point where user smoke testing or proving is required:

1. Stop dependent follow-on work on that specific slice
2. Do not keep extending that slice past the smoke-test boundary
3. Record the state durably:
   - Add a concise session note
   - Update the relevant plan/checkpoint with `USER SMOKE TEST PENDING`
   - File or update an issue tracking the pending smoke test
4. Provide a compact smoke-test handoff:
   - What changed
   - Exactly what the user should test
   - Expected outcome
   - What remains blocked on the result
5. Continue all other unblocked tracks and lanes

Only pause autonomous execution if:
- The smoke test is required before any other safe work can proceed
- The result determines which implementation branch is correct
- Proceeding further would risk invalidating the test or building on an
  unverified assumption

## Parallelism Rules

- Maximize parallelism subject to file-scope isolation and review capacity
- Keep idle lanes low, but do not fill them with low-value churn
- If no safe implementation task is ready for a lane, use that lane for
  planning, validation, review support, or issue cleanup

## Token-Efficiency Rules

- Optimize for throughput per token, not just visible activity
- Avoid repeated long restatements of context already in the handoff
- Avoid redundant repo rereads unless state has materially changed
- Reuse lane context when helpful, but clear/reset when stale context
  would cause drift
- Prefer direct execution over extended meta-discussion

## Reprioritization

Reprioritize dynamically based on:
- Merged PRs
- Blocked tasks
- Failing validations
- Review backlog
- Lane health
- File-scope conflicts
- Newly opened or newly unblocked work

## Issue Intake and Triage

Regularly triage newly opened and recently updated GitHub issues:
- At startup
- At the start of each new wave
- After meaningful merge batches
- Whenever active work is blocked and idle capacity appears

For each issue, classify quickly:
- Critical blocker to active work
- High-value next-wave candidate
- Backlog / defer
- Out of current scope

If actionable, in scope, and file-scope isolated: create or route work
without waiting for user confirmation. If it changes platform scope or
governance, route it through `steward-analyst` before dispatching.

## Task-List Maintenance

Update task lists at minimum:
- At startup after repo-state review
- Before each new wave is dispatched
- After each meaningful merge batch
- Whenever priority order changes
- Whenever a slice becomes blocked, deferred, or user-test-pending

Keep entries concise, current, and action-oriented. Remove stale entries.
If task lists and repo state diverge, reconcile promptly.

## Recovery Behavior

- If a lane stalls, use the bounded recovery path defined by the platform
- If recovery fails, escalate or reassign rather than letting work sit
- If a task proves over-scoped, narrow it and ship the useful subset

## Reporting

Maintain concise session notes. Explicitly track:
- User smoke tests pending and which lanes/tracks are blocked on them
- Which tracks remain active
- Newly triaged GitHub issues
- Which issues were dispatched vs deferred and why
- Whether `steward-analyst` left a restart-ready handoff for the next session

Periodically use `/check-in` to summarize current state.

At the end of the run, produce a compact handoff:
- What shipped
- What is in flight
- What is blocked
- Recommended next wave

## Shutdown Sequence

Before ending the fleet run, park all lanes with active sessions to prevent
orphaned cron jobs. `/clear` alone does **not** stop cron jobs — always
`/park` first.

1. **Park central lanes** — ops and review run persistent monitoring crons
   that must be stopped before the orchestrator exits:
   ```bash
   tmux send-keys -t steward:ops '/park' Enter
   # Wait for "0 cron jobs" confirmation
   tmux send-keys -t steward:review '/park' Enter
   # Wait for confirmation
   ```

2. **Park idle author lanes** — any author lane with an active session but
   no dispatched work:
   ```bash
   tmux send-keys -t steward:author-a '/park' Enter
   # ... repeat for each idle lane with an active session
   ```

3. **Verify cleanup** — confirm all parked lanes report zero active cron jobs

4. **Write session handoff** — only after all lanes are parked

5. **Park orchestrator** — run `/park` locally to clean up the orchestrator's
   own cron jobs (e.g., the inbox-polling cron from the Startup Checklist)

**Critical rule:** Do not write the session handoff while ops or review lanes
still have active cron jobs. Orphaned crons burn tokens and send alerts to
an orchestrator that has stopped reading them.

## Success Condition

- Maximize safe, observable, mergeable progress across all active tracks
- Keep idle capacity low
- Keep drift, hidden work, and unnecessary token burn low
- Stop cleanly at true user-validation boundaries
- Leave the system in a better operational state than it started
