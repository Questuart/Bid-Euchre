# Fix Retry Chronology Bug and Document Unwired Review Emission

**Date:** 2026-03-20
**Origin:** Post-merge review of PR #1098 (ops: close PR-5 follow-through gaps)

## Context

Post-merge review of PR #1098 identified two findings:

- **P1 (correctness):** `get_pending_retries()` builds a global `resolved_task_ids`
  set from *any* historical resolution event, then suppresses *all* `task_failed`
  events for that task. A newer failure after an older retry is silently hidden.
- **P2 (documentation):** `emit_review_event()` exists and is tested but is never
  called from any production path (scheduler, ops CLI, review polling).

## Implementation Plan

### 1. Fix chronology bug in `get_pending_retries()` (P1)

**File:** `src/bid_euchre/ops/retries.py`

Replace the global `resolved_task_ids` set with a per-task latest-resolution
timestamp approach:

1. **Phase 1:** Scan all events to find the latest resolution timestamp per task_id.
2. **Phase 2:** Scan `task_failed` events and only consider a failure resolved if
   its timestamp is ≤ the latest resolution timestamp for that task.

This means a failure occurring *after* a retry/completion/reroute/escalation is
correctly identified as unresolved.

`get_retry_summary()` calls `get_pending_retries()` internally, so the fix
flows through to `dropped_count` automatically. The summary's cumulative counts
(`retried_tasks`, `resolved_tasks`, etc.) remain historical — that's the correct
semantic for aggregate reporting.

### 2. Add regression tests (P1)

**File:** `tests/unit/test_ops_retries.py`

Add tests for:
- Failure after retry → still pending
- Failure after completion → still pending
- Multiple cycles: fail → retry → fail → complete → all resolved
- Failure at same timestamp as resolution → resolved (tie = resolved)

### 3. Document unwired `emit_review_event()` (P2)

**File:** `src/bid_euchre/ops/reviews.py`

Add a `.. note::` to the docstring clarifying that this function is not yet
wired into any production polling path. Callers must invoke it explicitly.
This is a documentation-only change — production wiring is a separate scope.

## Out of Scope

- Wiring `emit_review_event()` into production paths (separate PR)
- Changes to `get_retry_summary()` cumulative counts (correct as-is)
- Changes to ops CLI, scheduler, or other modules

## Parallelism Assessment

All three tasks touch disjoint files. Tasks 1 and 2 are tightly coupled
(implementation + tests). Task 3 is independent. Sequential execution is
appropriate given the small scope.

## Done When

- [ ] `get_pending_retries()` uses per-task chronological resolution
- [ ] Regression tests cover failure-after-resolution scenarios
- [ ] `emit_review_event()` docstring documents production wiring status
- [ ] `uv run python -m pytest tests/unit/test_ops_retries.py tests/unit/test_ops_reviews.py` passes
- [ ] `make check-quiet` passes

## Outcome

*To be filled after implementation.*
