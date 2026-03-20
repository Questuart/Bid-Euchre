# Wire Watchdog Event Producers (#928, #929, #930)

**Date:** 2026-03-20
**Author:** author-a
**Issues:** #928, #929, #930
**Branch:** `fix/ops-bugs` (current working branch)

## Goal

Wire the event producers and scope tracking needed by three existing operator
watchdogs that currently have no data to consume. All three are LOW-priority
follow-up enhancements from Phase 3D of the agent ops governing plan.

## Current State Analysis

### #928 -- CI event producers for `check_ci_stuck()`

**Consumer:** `watchdogs.py:check_ci_stuck()` reads `ci_failure`, `ci_success`,
and `ci_timeout` events from the event log, looking for PRs where CI has been
stuck failing beyond a threshold.

**Existing producer:** `scripts/internal/ci_poller.sh` already emits all three
event types (`ci_failure`, `ci_success`, `ci_timeout`) via shell wrapper around
`append_event()`. This covers the "real steward session" acceptance criterion.

**Gap:** There is no Python-level convenience function in `ops/ci.py` for
emitting CI events. The `poll_ci_status()` function polls checks but does not
emit events. Adding `emit_ci_events()` to `ci.py` would allow the scheduler
tick, CLI, or any Python caller to emit CI events after polling -- making the
producer accessible from Python, not just shell.

### #929 -- Scope fields for `check_scope_drift()`

**Consumer:** `watchdogs.py:check_scope_drift()` reads `scope.declared_files`
and `scope.touched_files` from `task_state/*.json` files.

**Existing infrastructure (already implemented):**
- `status.py:update_task_scope()` writes both fields.
- `status.py:set_declared_scope()` convenience wrapper exists.
- `status.py:record_touched_files()` convenience wrapper exists.
- `ops.py scope set/touch/show` CLI commands exist.
- Tests exist for all of the above in `test_ops_status.py`.

**Gap:** No automated mechanism snapshots actual git changes into touched_files.
An `emit_scope_snapshot()` helper that reads `git diff --name-only` and feeds
the result to `record_touched_files()` would close this gap, enabling hooks
to auto-track what files an agent has actually modified.

### #930 -- retry_attempted and task_rerouted event emission

**Existing infrastructure (already implemented):**
- `recovery.py:emit_retry_event()` maps policy actions to event types.
- `ops.py retry --emit` CLI flag calls `emit_retry_event()`.
- Full test coverage exists in `test_ops_recovery.py`.

**Gap:** The scheduler tick does not automatically evaluate retry policy for
tasks with repeated failures. When `check_subagent_failures()` detects
repeated task failures, the scheduler should call `evaluate_retry_policy()` +
`emit_retry_event()` to produce durable retry/reroute/escalation events.

## Implementation Plan

### Task 1: Add `emit_ci_events()` to `ops/ci.py` (#928)

**Files:** `src/bid_euchre/ops/ci.py`, `tests/unit/test_ops_ci.py`

**Function signature:**
```python
def emit_ci_events(
    report: CIStatusReport,
    lane_id: str,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
```

**Logic:**
- `report.overall == "failure"` -> emit `ci_failure` with payload
  `{pr_number, failure_class}` (join classification failure_classes).
- `report.overall == "success"` -> emit `ci_success` with payload
  `{pr_number}`.
- Otherwise (pending/unknown) -> return None.

**Tests (4):**
- `test_emit_ci_events_failure` -- emits ci_failure with payload
- `test_emit_ci_events_success` -- emits ci_success with payload
- `test_emit_ci_events_pending_noop` -- returns None
- `test_emit_ci_events_persisted` -- event readable from JSONL

### Task 2: Wire scheduler to emit retry events (#930)

**Files:** `src/bid_euchre/ops/scheduler.py`, `tests/unit/test_ops_scheduler.py`

**What:** After running watchdogs in `tick()`, evaluate retry policy for each
task flagged by `check_subagent_failures()` and emit the appropriate event.

**Integration in `tick()`:** Add step 3.5 after existing step 3:
```python
_evaluate_retries_for_findings(findings, events_dir)
```

**Helper `_evaluate_retries_for_findings()`:**
1. Filter findings to `watchdog_name == "subagent_failure_check"`.
2. Parse `finding.target` (format "lane_id:task_id").
3. Read recent events from events_dir.
4. Call `evaluate_retry_policy(task_id, events, current_lane=lane_id)`.
5. Call `emit_retry_event(policy, lane_id, events_dir)`.
6. Increment `result.events_emitted` for each emitted event.

**Tests (2):**
- `test_tick_emits_retry_for_subagent_failures` -- scheduler tick with
  repeated failures triggers retry event emission
- `test_tick_no_retry_without_subagent_failures` -- no extra events when
  subagent_failures watchdog is clean

### Task 3: Add `emit_scope_snapshot()` to `ops/status.py` (#929)

**Files:** `src/bid_euchre/ops/status.py`, `tests/unit/test_ops_status.py`

**Function signature:**
```python
def emit_scope_snapshot(
    task_id: str,
    repo_root: Path | None = None,
    runtime_dir: Path | None = None,
) -> dict[str, Any] | None:
```

**Logic:**
1. Run `git diff --name-only HEAD` from `repo_root`.
2. Also run `git diff --name-only` (unstaged) and union the results.
3. If no changed files, return None.
4. Call `record_touched_files(task_id, files, runtime_dir)`.
5. Return the updated task state dict.

**Tests (3):**
- `test_emit_scope_snapshot_with_changes` -- mock subprocess, verify touched
  files recorded
- `test_emit_scope_snapshot_no_changes` -- mock subprocess returns empty,
  returns None
- `test_emit_scope_snapshot_nonexistent_task` -- raises FileNotFoundError

### Task 4: Lint, format, full validation

```bash
ruff check --fix <changed files>
ruff format <changed files>
make check-quiet
```

### Task 5: Commit and open PR

Single commit referencing all three issues. PR uses the repository template.

## Dependency Graph

```
Task 1 (ci.py)         Task 2 (scheduler.py)   Task 3 (status.py)
     \                       |                      /
      \                      |                     /
       v                     v                    v
                    Task 4 (validate)
                          |
                          v
                    Task 5 (PR)
```

Tasks 1, 2, 3 have disjoint write scopes and can be implemented independently.

## Scope Boundaries

**In scope:**
- `src/bid_euchre/ops/ci.py` -- new `emit_ci_events()`
- `src/bid_euchre/ops/scheduler.py` -- wire retry evaluation in `tick()`
- `src/bid_euchre/ops/status.py` -- new `emit_scope_snapshot()`
- `tests/unit/test_ops_ci.py` -- tests for emit_ci_events
- `tests/unit/test_ops_scheduler.py` -- tests for retry in tick
- `tests/unit/test_ops_status.py` -- tests for emit_scope_snapshot

**Out of scope:**
- Modifying `ci_poller.sh` (already works)
- Modifying `recovery.py` or `emit_retry_event()` (already complete)
- Adding PostToolUse hooks (hook registration is separate concern)
- Game logic, strategy code, experiment infrastructure
- Modifying the review loop or review driver

## Outcome

<!-- Fill after implementation -->
