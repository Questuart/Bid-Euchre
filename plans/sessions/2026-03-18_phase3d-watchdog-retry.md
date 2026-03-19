# Phase 3D: Watchdog Extensions + Retry/Reroute Policy

**Date:** 2026-03-18
**Author lane:** author-c
**Governing plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` § PR-3
**Implementation plan:** `plans/sessions/2026-03-18_pr3-operator-cli.md` § Phase 3D

## Goal

Extend watchdog coverage and add retry/reroute policy so `ops` can detect:
- CI stuck beyond threshold
- Repeated sub-agent/task failures
- Scope drift outside declared task scope
- No forward progress (already exists, may extend)

And respond with bounded retry/reroute policy:
- Bounded retries only (no infinite loops)
- Reroute durable work to persistent lanes after repeated failure
- Escalate after retry cap

## Files Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/bid_euchre/ops/watchdogs.py` | Extend | `check_ci_stuck()`, `check_subagent_failures()`, `check_scope_drift()` |
| `src/bid_euchre/ops/recovery.py` | Extend | `RetryPolicy`, `evaluate_retry_policy()` |
| `src/bid_euchre/ops/scheduler.py` | Extend | `daemon()` mode with bounded loop |
| `src/bid_euchre/ops/events.py` | Extend | Add new event types: `retry_attempted`, `task_rerouted` |
| `scripts/internal/ops.py` | Extend | Wire `daemon` subcommand |
| `tests/unit/test_ops_watchdogs.py` | Extend | Tests for new watchdog rules |
| `tests/unit/test_ops_recovery.py` | Extend | Tests for retry/reroute policy |
| `tests/unit/test_ops_cli.py` | Extend | Tests for daemon CLI |
| `tests/unit/test_ops_scheduler.py` | Extend | Tests for daemon mode |

## Design Decisions

### check_ci_stuck()
- Reads event log for `ci_failure` and `ci_success` events
- Groups by PR number from payload, keeping only the most recent event per PR
- Resolves `ci_failure` against subsequent `ci_success` — a PR with a newer
  `ci_success` is not flagged as stuck
- Flags PRs where the most recent CI event is `ci_failure` and it's older than `stuck_minutes`

### check_subagent_failures()
- Reads event log for `task_failed` events
- Groups by `(lane_id, task_id_from_payload)` combination
- Flags when failure count >= `max_failures` threshold
- Recommends reroute to persistent lane

### check_scope_drift()
- Reads `task_state/*.json` for in-progress tasks with `scope.declared_files` field
- Compares against `scope.touched_files` (populated by hooks/agents)
- Flags when touched_files includes patterns not in declared_files
- Pure JSON comparison — no subprocess calls

### evaluate_retry_policy()
- Pure function: takes task_id and event list
- Counts `task_failed` events for the task
- Default max retries: 3
- Action: retry (< max), reroute (== max), escalate (> max)
- Returns RetryPolicy with action and reroute target

### daemon() mode
- Bounded loop: max_iterations parameter (default 100)
- Configurable interval_seconds (default 300 = 5 min)
- Calls tick() each iteration
- Logs findings and emits events
- Returns DaemonResult with summary

## Implementation Order

1. Write plan file (this document)
2. Extend `events.py` VALID_EVENT_TYPES
3. Add watchdog extensions to `watchdogs.py`
4. Add retry/reroute policy to `recovery.py`
5. Add daemon mode to `scheduler.py`
6. Wire CLI subcommand in `ops.py`
7. Add tests for all new functionality
8. Run `make check-quiet`
9. Commit and open PR

## Outcome

_To be filled after implementation._
