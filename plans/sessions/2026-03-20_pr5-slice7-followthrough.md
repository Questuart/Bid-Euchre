# PR-5 Slice 7: Follow-Through Automation and Closeout

**Date:** 2026-03-20
**Goal:** Close PR-5 follow-through gaps for scope drift detection, retry follow-through, and CI/review event emission consistency.

## Context

- PR-5 slices 1–5 shipped; slice 6 (liveness/heartbeat truth) in progress on another lane.
- Slice 7 is bounded follow-through automation — not orchestrator or platform work.
- This is the final closeout slice for the PR-5 session plan.

## Strict Ownership Boundary

**Do NOT edit** (slice-6 write scope):
- `src/bid_euchre/ops/status.py`
- `src/bid_euchre/ops/watchdogs.py`
- `src/bid_euchre/ops/worktrees.py`
- `tests/unit/test_ops_status.py`
- `tests/unit/test_ops_watchdogs.py`
- `tests/unit/test_ops_worktrees.py`

## Implementation Plan

### 1. `scope.py` — Scope Drift Detection (NEW FILE)

**File:** `src/bid_euchre/ops/scope.py`

Automates comparison of declared vs touched files for a task, flagging scope drift.

- `ScopeDriftReport` dataclass — drift findings (out_of_scope files, stats)
- `check_scope_drift(task_id, runtime_dir)` — reads scope from `status.get_task_scope()`, matches touched files against declared patterns via `fnmatch`
- `emit_scope_drift_event(report, lane_id, events_dir)` — emits `watchdog_finding` event when drift is detected
- `format_scope_drift_text(report)` / `format_scope_drift_json(report)` — formatters

### 2. `retries.py` — Retry Follow-Through Helpers (NEW FILE)

**File:** `src/bid_euchre/ops/retries.py`

Proactive scanning for failed tasks that haven't been retried, ensuring failed work doesn't silently disappear.

- `PendingRetry` dataclass — task with unresolved failure
- `RetrySummary` dataclass — aggregate retry state
- `get_pending_retries(events, max_age_hours)` — finds `task_failed` events without subsequent `retry_attempted`/`task_completed`/`task_rerouted` for the same task
- `get_retry_summary(events)` — counts retries/reroutes/escalations per task, flags dropped tasks

### 3. `reviews.py` — Review Event Emission (EDIT)

**File:** `src/bid_euchre/ops/reviews.py`

Add `emit_review_event(outcome, lane_id, events_dir)` analogous to `emit_ci_events()` in `ci.py`. Emits `review_outcome` events when review status is determined. Makes CI and review event emission patterns consistent.

### 4. CLI Wiring (EDIT)

**File:** `scripts/internal/ops.py`

- `ops.py scope check --task TASK_ID` — check scope drift for a task
- `ops.py retry summary` — show retry follow-through summary

### 5. Tests

- `tests/unit/test_ops_scope.py` — full coverage for scope drift detection
- `tests/unit/test_ops_retries.py` — full coverage for retry follow-through
- Additional tests in `tests/unit/test_ops_reviews.py` for `emit_review_event`

## Out of Scope

- Slice-6 liveness/heartbeat truth work
- Orchestrator / platform architecture
- Dashboard-first UI
- Remote channels / worker-pool management
- Codex Cloud comment ingestion
- Broad workflow-engine refactors

## Done When

- [x] Scope drift detection automation with test coverage
- [x] Retry follow-through scanning with test coverage
- [x] Review event emission consistent with CI pattern
- [x] CLI wiring for scope check and retry summary
- [x] `make check-quiet` passes
- [x] PR created

## Outcome

PR: (to be filled after PR creation)
