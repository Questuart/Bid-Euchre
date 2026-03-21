# Ops Lane — Repo Status Monitoring Handoff

**Lane Direction:** Use the `ops` lane for continuous repo-health monitoring through the committed operator CLI. This is an operational supervision task. Do not make code changes from this lane unless a specific blocking defect is identified and reassigned.

**Date:** 2026-03-21
**Goal:** Have `ops` monitor lane health, queue state, review state, and watchdog findings using the repo’s built-in tools so regressions are caught early while other lanes work.

## Mission

Keep a live picture of:

- lane/session health
- review queue state
- PR review outcomes
- watchdog/health degradations
- notable event-stream failures

Use the repo tools as the source of truth, not pane archaeology.

## Primary Tools

Use:

- `uv run python scripts/internal/ops.py status`
- `uv run python scripts/internal/ops.py health`
- `uv run python scripts/internal/ops.py watchdogs`
- `uv run python scripts/internal/ops.py queue`
- `uv run python scripts/internal/ops.py reviews`
- `uv run python scripts/internal/ops.py events --limit 20`

Use JSON output when you need to capture or compare state:

- `... --json`

## Monitoring Cadence

Recommended rhythm while the repo is active:

- `status`: every 10-15 minutes
- `queue`: every 10-15 minutes, and after PR create / merge events
- `reviews`: every 15-30 minutes, and after notable PR transitions
- `health` / `watchdogs`: every 30-60 minutes, or immediately after suspicious behavior
- `events`: when something looks wrong, or at least once per monitoring block

If the repo is quiet, reduce frequency rather than inventing work.

## Standard Check Loop

For each monitoring pass:

1. Run `ops.py status`
   - confirm lane/session/task state looks sane
2. Run `ops.py queue`
   - check for stuck requests, stale verdicts, missing verdicts, or failed verdicts
3. Run `ops.py reviews`
   - confirm recent PR review/check outcomes match expectations
4. Run `ops.py health`
   - look for critical watchdog findings
5. If something is off, inspect:
   - `ops.py watchdogs`
   - `ops.py events --limit 20`

## What To Watch For

Prioritize:

- requests with no progress
- verdicts stuck in `running` or other non-terminal states
- stale SHA mismatches
- repeated review failures on the same PR
- watchdog findings marked critical
- CI/review mismatches that imply the merge path is regressing
- lane/session health problems that strand active work

Secondary:

- advisory review noise
- isolated transient event spikes that self-resolve

## Escalation Rules

Escalate when:

- merge safety looks weakened
- multiple PRs are getting stuck in the same part of the review flow
- watchdogs report critical findings
- queue state and review state disagree in a way that affects mergeability

Escalation output should include:

- the concrete symptom
- the affected PR(s) or lane(s)
- the command output or state surface that showed the problem
- whether a bounded fix PR is recommended

## Reporting Style

For normal passes, keep updates brief:

- healthy / no action
- one or two items to watch

For degraded passes, include:

- exact affected PR or lane
- likely root cause
- whether this is blocking or advisory

## Out Of Scope

Do not:

- manually edit queue/verdict files unless explicitly directed
- bypass the merge guard
- turn advisory signals into fixes from the `ops` lane without reassignment

## Exit Criteria

- `ops` is using repo-native tools, not ad hoc shell inspection, as the main monitoring surface
- queue/review/watchdog problems are detected early
- escalations are concise, evidence-based, and routed to the right author lane
