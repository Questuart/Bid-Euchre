---
name: session-end
description: Walks the orchestrator through a clean end-of-session shutdown — park non-orchestrator lanes, verify zero active cron jobs fleet-wide, append the session handoff to MEMORY.md, then park the orchestrator's own crons last. Use from the orchestrator lane when ending a session.
---

# /session-end — Orchestrated Shutdown and Handoff

Guides the orchestrator through the Session-End Shutdown sequence that was
previously documented prose-only in the orchestrator's system prompt. The
goal is a deterministic, auditable shutdown: every non-orchestrator lane
parked, zero orphaned cron jobs fleet-wide, a written handoff in MEMORY.md,
and then — last — the orchestrator parks its own crons and exits.

## Problem

Ending a session by `/clear`-ing each pane is unsafe: cron jobs persist
across `/clear` and continue burning tokens and sending alerts to an
orchestrator that has stopped reading them. The orchestrator's system
prompt documents the correct sequence ("Session-End Shutdown (Orchestrator
Exit)" in `.claude/agents/steward-orchestrator.md`), but it is a six-step
prose checklist — easy to miss a step, no tooling to verify completion.

This skill is the executable form of that checklist. It enumerates the
lanes, parks them in the correct order, verifies cleanup, writes the
handoff, and only then parks the orchestrator itself.

## When to Use

- You are the orchestrator and the operator has signaled end of session
  (e.g., "wrap up", "park the fleet", "good night")
- You have finished dispatching and monitoring for the day and want a
  clean, auditable handoff for the next session
- A long autonomous run is ending and the fleet needs to drain before
  the orchestrator exits

Do **not** use this skill mid-session to park a single lane — use `/park`
sent to that lane's pane. This skill shuts down the whole fleet.

## Pre-conditions

Before starting, confirm:

- No task packets are mid-flight that require immediate attention (check
  `ops.py task list` — any lane currently implementing or opening a PR
  should finish or be explicitly reassigned before its pane is parked)
- No urgent unread messages in the orchestrator inbox that require a
  response (Phase 3 re-verifies this, but catching it early avoids a
  retry loop)
- The operator is aware the fleet is shutting down (if in doubt, ask)

If any pre-condition fails, abort and address the gap before restarting
the skill.

## Workflow

### Phase 1 — Enumerate Active Non-Orchestrator Lanes

List every lane that is currently holding a session besides the
orchestrator. Two complementary signals:

```bash
# Primary: dashboard-first view of foreground + background lanes
uv run python scripts/internal/ops.py dashboard

# Cross-check: per-lane heartbeat files (writer lands per PR #2686).
# Each file in this directory corresponds to a lane that has recently
# run a tool — recency is `updated_at` in the JSON payload.
ls -la .claude/runtime/lane_status/
```

The canonical lane list (see `.claude/rules/75_worktree_protection.md`):

- **Control plane:** `ops`, `review`
- **Author pool:** `author-a`, `author-b`, `author-c`, `author-d`
- **Browser-game pool:** `brws-author-a`, `brws-author-b`, `brws-author-c`,
  `brws-author-d`
- **Analyst pool:** `analyst-a` (aka `analyst`), `analyst-b`, `analyst-c`,
  `analyst-d`
- **Flex pool:** `flex-a`, `flex-b`, `flex-c`, `flex-d`

Build a working list of the lanes that **actually have an active session**
— not every protected worktree is live. A lane is active if any of:

- It appears in `dashboard` under foreground or background with non-zero
  tokens or recent activity
- It has a heartbeat file under `.claude/runtime/lane_status/<lane>.json`
  with `updated_at` newer than ~30 minutes
- `ops.py task list` shows a `dispatched` packet owned by that lane

Lanes with no heartbeat and no dispatched packet are already idle at the
session level — they do not need `/park`.

### Phase 2 — Park Lanes in Order

Park lanes from least-critical to most-critical so a failure early in the
sequence still leaves the control plane alive to help diagnose:

1. **Idle author/flex/browser-game/analyst lanes** — any pool lane with no
   active task packet
2. **Author/browser-game/analyst lanes holding dispatched packets** — these
   should ideally finish and auto-close via the post-merge hook before
   `/session-end`; if they cannot finish, reassign or complete their packet
   first, then park
3. **Review lane** — runs post-PR review crons; parking this cuts off the
   review queue reader
4. **Ops lane** — runs monitoring crons; park this last among the
   non-orchestrator lanes so it can surface problems during the shutdown

For each lane, send `/park` to its tmux pane using the three-step pattern
(Escape-to-cancel, send text, delay, send Enter). The naked two-step
form (`'/park' Enter` in one call) is swallowed by bracketed paste mode
— see `.claude/skills/start-task/SKILL.md` § "Tmux Paste Bracketing Caveat"
and issues #1834 and #2352 for the underlying bug.

```bash
PANE=steward:<window>.<lane-pane>

tmux send-keys -t "$PANE" Escape
sleep 0.1
tmux send-keys -t "$PANE" '/park'
sleep 1
tmux send-keys -t "$PANE" Enter
```

After dispatching `/park`, **wait for the lane to confirm**. Read the pane
contents and look for the final line of the `/park` skill output, which
reports the number of cron jobs deleted and that `CronList` is now empty.
Use the `/capture-pane` skill (or the underlying `tmux capture-pane`
invocation it wraps):

```bash
tmux capture-pane -t steward:<window>.<pane> -p -S -50
```

The lane is safely parked when the pane shows:

- "Killed N orphaned process(es)" (Step 1 of `/park`)
- "CronList" returning an empty list after all deletes (Step 4 of `/park`)
- A terminal "The lane is safe to `/clear`" confirmation line

If the confirmation does not appear within ~60 seconds, re-inspect the
pane — the lane may be mid-validation or waiting on a permission prompt.
Do **not** send a second `/park` on top; nudge only after resolving the
stall.

**Do not run `/clear` on the parked lane.** `/park` intentionally stops
at cron cleanup so the operator can inspect the pane state. The next
session-start sequence will `/clear` or restart the lane.

### Phase 3 — Verify Zero Active Cron Jobs Fleet-Wide

Spot-check that nothing escaped Phase 2:

- For each parked lane, confirm its `/park` final confirmation is visible
  in the pane transcript
- For the orchestrator, do **not** run `CronList` yet — the orchestrator's
  own crons (e.g., `/loop 8m /fleet-check`) are still running and will
  be parked in Phase 5

Also re-check the orchestrator inbox for any P0/P1 messages that arrived
during the shutdown:

```bash
uv run python scripts/internal/ops.py inbox \
  --lane orchestrator \
  --status pending \
  --type supervisor_alert,escalation,blocker \
  --prioritized
```

If urgent messages are present:

- **Supervisor alerts from ops:** triage and ack; if the finding is
  actionable and the relevant lane is already parked, file a follow-up
  issue rather than un-parking
- **Escalations:** address before proceeding — the shutdown is not
  yet safe to finalize

Ack each processed message:

```bash
uv run python scripts/internal/ops.py inbox ack <MSG_ID> --lane orchestrator
```

A clean inbox at this point is the signal that Phase 4 can proceed.

### Phase 4 — Write the Session Handoff to MEMORY.md

Draft a handoff entry and append it to `MEMORY.md`. The entry should be
structured so the next session's `/recovering-context` can resume
deterministically. Minimum content:

- **Date and wall-clock wrap time** (UTC or local — be explicit)
- **Session goal / theme** (one sentence)
- **PRs merged this session** — table of `#N | title | status`
- **Lanes parked** — list of lane ids that held sessions and were
  `/park`ed during Phase 2
- **Open PRs and their states** — anything left in CI or in review
- **Outstanding task packets** — anything still `dispatched` or
  `approved` in the queue, plus the planned next owner
- **Immediate next steps** — what the next orchestrator session should
  pick up first
- **Known hazards** — CI anomalies, flaky tests, stuck reviews, etc.

Keep the entry concise — target ~20-40 lines of markdown. If the session
produced a large PR log, link to a session detail file under
`plans/sessions/YYYY-MM-DD_<slug>.md` rather than embedding everything
in MEMORY.md.

Commit the MEMORY.md change on a dedicated worktree/branch, open a PR,
and let post-merge review catch any handoff gaps. **Do not skip the PR
step** — MEMORY.md is project-wide context; direct commits on main are
blocked by the worktree-only policy.

See `.claude/skills/summarizing-sessions/SKILL.md` for a complementary
PR-focused session summary template.

**Critical rule (from `steward-orchestrator.md`):** Do not write the
handoff while ops or review lanes still have active cron jobs. The
handoff signals "session ended" — but orphaned crons mean the session
is still consuming resources. Phase 2 must complete before Phase 4
begins.

### Phase 4.5 — Feed Archivist Candidate Queue

Immediately after the MEMORY.md handoff commit is authored (but before
pushing), invoke the archivist postmortem mode:

```
uv run python scripts/internal/archivist_candidates.py --mode postmortem --session-id <id>
```

This appends a postmortem-derived section to
`knowledge/_candidates/<date>_lessons.md` covering this session's
incidents, token outliers, and explicit `lesson-learned` annotations.
The appended candidate file ships in the same MEMORY.md commit so the
handoff and the candidate-queue entry arrive together.

The archivist is best-effort: if the invocation fails, **do not** block
shutdown — log the failure to the pane transcript and proceed to Phase
5. Failed postmortems are caught by the next nightly archivist run.

**Operator review prompt:** "Handoff written and candidates queued"
should resolve to YES once Phase 4.5 completes — i.e., the MEMORY.md
handoff block exists AND `knowledge/_candidates/<date>_lessons.md`
contains a `## Postmortem — session <id>` section for this session.

See `plans/steward_platform/4_primitive_D/shaping.md` §4.4 for the
Primitive D.2 postmortem design.

### Phase 5 — Park the Orchestrator's Own Crons

With the fleet parked and the handoff written, shut down the orchestrator
itself by running `/park` locally:

```
/park
```

This follows the same Step 1-5 sequence documented in
`.claude/skills/park/SKILL.md`:

1. Kill orphaned build/test processes (rare on orchestrator, but harmless)
2. `CronList` — expect to see the orchestrator's durable crons
   (typically `/loop 8m /fleet-check`)
3. `CronDelete` each returned id
4. `CronList` again — confirm the list is empty
5. Report cron cleanup complete; the lane is safe to `/clear`

Only after the orchestrator's own `CronList` returns empty is the session
truly ended. At that point the operator (or a session-end script) can
`/clear` the orchestrator pane or close the tmux window.

## Dry-Walk Checklist

Before invoking this skill for real, mentally walk the sequence:

- [ ] Phase 1 produces a concrete list of live non-orchestrator lanes
      from `dashboard` + heartbeat + task queue, not from imagination
- [ ] Phase 2 parks lanes in the order idle-pool → busy-pool → review →
      ops, using the three-step tmux pattern, and waits for each
      `/park` confirmation before moving on
- [ ] Phase 3 confirms no urgent inbox messages and every parked lane
      reported zero active cron jobs
- [ ] Phase 4 writes a MEMORY.md handoff with goal, PRs, parked lanes,
      open PRs, outstanding packets, next steps, and hazards — and ships
      it via a PR rather than a direct-to-main commit
- [ ] Phase 4.5 invokes
      `scripts/internal/archivist_candidates.py --mode postmortem --session-id <id>`
      and the `_candidates/<date>_lessons.md` file gains a
      `## Postmortem — session <id>` section — or the failure is logged
      and shutdown proceeds
- [ ] Phase 5 parks the orchestrator's own crons last, only after
      Phase 4 is committed

If any step would be a guess rather than a concrete observation, stop
and collect the missing data first.

## Gotchas

- **Order matters.** Parking ops first blinds the fleet to new stalls;
  parking the orchestrator first orphans every other lane's alerts. The
  Phase 2 order (idle pool → busy pool → review → ops) keeps the control
  plane alive the longest.
- **`/park` does not `/clear`.** This is intentional — the operator may
  want to inspect pane transcripts before clearing. Do not follow `/park`
  with an automatic `/clear` inside this skill.
- **Bracketed paste.** Always use the three-step `Escape / text / sleep /
  Enter` tmux pattern. The naked `tmux send-keys -t <pane> '/park' Enter`
  form corrupts input on many terminals and is the leading cause of
  stuck lanes during shutdown.
- **Auto-merge races.** If a PR merges during Phase 2, the post-merge
  review hook fires a background Explore agent. That is fine — the
  post-merge review is advisory and does not require the orchestrator
  to be live. Do not delay shutdown waiting for post-merge review.
- **This is docs only.** The skill is a procedural checklist with
  concrete commands; it does not introduce new hooks, CLI commands, or
  automation. Behavior changes (auto-triggering on idle, one-shot
  `ops.py session-end`) are future work — file a fresh issue rather
  than expanding this skill.

## References

- `.claude/skills/park/SKILL.md` — the per-lane shutdown primitive used
  in Phase 2 and Phase 5
- `.claude/skills/fleet-check/SKILL.md` — enumerate-lanes pattern
  (`ops.py dashboard` + inbox poll) reused in Phase 1 and Phase 3
- `.claude/skills/start-task/SKILL.md` § Tmux Paste Bracketing Caveat —
  three-step `Escape / text / Enter` tmux pattern required in Phase 2
- `.claude/skills/capture-pane/SKILL.md` — read pane content to verify
  `/park` confirmations in Phase 2
- `.claude/skills/summarizing-sessions/SKILL.md` — complementary
  PR-focused summary template for Phase 4
- `.claude/agents/steward-orchestrator.md` § "Session-End Shutdown
  (Orchestrator Exit)" — authoritative prose version of this sequence;
  this skill is the executable complement
- `.claude/rules/75_worktree_protection.md` — canonical lane list
  referenced in Phase 1
- Issue #2403 — scope and acceptance criteria for this skill
- Issue #2686 — lane-heartbeat writer referenced in Phase 1
- Issues #1834, #2352 — tmux paste-bracketing bugs that justify the
  three-step `Escape / text / Enter` pattern

## Closes

Closes #2403 by providing an executable session-end checklist that
codifies the orchestrator's prose "Session-End Shutdown (Orchestrator
Exit)" sequence into a discoverable skill.
