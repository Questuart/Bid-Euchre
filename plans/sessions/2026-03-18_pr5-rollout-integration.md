# PR-5: Rollout, Integration, and Operational Proof

**Date:** 2026-03-18
**Branch:** `codex/steward-author-c`
**Parent plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`
**Closes issues:** #928, #929, #930

## Goal

Make the autonomous operator stack operationally credible by:
1. Wiring deferred watchdog producers so all 6 watchdogs function against real data
2. Adding event emission to the retry/reroute CLI command
3. Adding a CLI `scope` subcommand to manage task scope fields
4. Updating the operator workflow doc to reflect the complete shipped surface
5. Running operational smoke and failure-injection validation

## Scope

### In Scope

| Area | Files | Change |
|------|-------|--------|
| CI event producers | `scripts/internal/ci_poller.sh` | Emit `ci_failure`/`ci_success` events on CI outcome |
| Scope field API | `src/bid_euchre/ops/status.py` | Add `update_task_scope()` helper |
| Scope CLI | `scripts/internal/ops.py` | Add `ops.py scope` subcommand |
| Retry event emission | `scripts/internal/ops.py` | Emit events in `cmd_retry()` |
| Tests | `tests/unit/test_ops_*.py` | New tests for producers, scope API, retry events |
| Docs | `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | Update "Future Work" → shipped, add operator CLI reference |

### Out of Scope

- Fully automated scope tracking via hooks (complex, needs separate design)
- New hook scripts (scope tracking in hooks deferred)
- Changes to other ops modules beyond what's listed
- Reopening PR-1 through PR-4 architecture

## Design

### 1. CI Event Producers (Issue #928)

The `ci_poller.sh` script already determines pass/fail status for PRs. Wire it to emit
events to the durable event log:

- On CI pass: emit `ci_success` with `{pr_number: N}` payload
- On CI failure: emit `ci_failure` with `{pr_number: N, failure_class: "..."}` payload
- Use `uv run python -c "from bid_euchre.ops.events import append_event; ..."` pattern
  (same as `post-task-event.sh`)

This makes `check_ci_stuck()` watchdog functional against real CI data.

### 2. Task Scope Management (Issue #929)

Add a Python API + CLI for managing scope fields on task state:

**Python API** (`src/bid_euchre/ops/status.py`):
```python
def update_task_scope(
    task_id: str,
    *,
    declared_files: list[str] | None = None,
    touched_files: list[str] | None = None,
    append_touched: bool = False,
    runtime_dir: Path | None = None,
) -> dict:
    """Update scope fields on a task state file."""
```

**CLI** (`ops.py scope`):
```
ops.py scope set --task TASK_ID --declared 'src/bid_euchre/ops/*.py' 'tests/unit/test_ops_*.py'
ops.py scope touch --task TASK_ID --file src/bid_euchre/ops/watchdogs.py
ops.py scope show --task TASK_ID
```

This makes `check_scope_drift()` watchdog functional — agents or operators call
`ops.py scope set` at task start and `ops.py scope touch` during execution.

### 3. Retry/Reroute Event Emission (Issue #930)

Modify `cmd_retry()` in `ops.py` to emit events after policy evaluation:
- If action is "retry": emit `retry_attempted` event
- If action is "reroute": emit `task_rerouted` event
- If action is "escalate": emit `escalation` event
- Add `--emit` flag (default: off) to control event emission (advisory by default)

### 4. Docs Update

Update `AUTONOMOUS_OPERATOR_WORKFLOW.md`:
- Move items from "Future Work" to shipped status
- Add Operator CLI reference table with all commands
- Add rollback/disable instructions
- Mark local review loop as transitional

## Implementation Order

1. Wire CI event producers in `ci_poller.sh`
2. Add `update_task_scope()` to `status.py`
3. Add `ops.py scope` CLI subcommand
4. Add event emission to `cmd_retry()`
5. Write tests for all new code
6. Update docs
7. Run `make check-quiet`
8. Run operational smoke + failure injection
9. Commit and open PR

## Parallelism Assessment

| Work | Owner | Files |
|------|-------|-------|
| CI poller + scope API + retry events | main agent | `ci_poller.sh`, `status.py`, `ops.py` |
| Docs update | can be parallel agent | `AUTONOMOUS_OPERATOR_WORKFLOW.md` |
| Tests | main agent (after implementation) | `test_ops_*.py` |

The docs update has no file overlap with implementation — safe for parallel agent.
Tests must follow implementation (sequential).

## Validation Plan

### Automated Tests
- `test_ops_status.py`: test `update_task_scope()` API
- `test_ops_cli.py`: test `ops.py scope` subcommand
- `test_ops_recovery.py`: test retry event emission
- `test_ops_watchdogs.py`: verify watchdog + producer integration
- Full `make check-quiet` before PR

### Manual Smoke
- Run `ops.py watchdogs` in steward environment — verify no false positives
- Run `ops.py health` — verify coherent text + JSON output
- Run `ops.py scope show --task ...` — verify scope display
- Run `ops.py retry --task ...` — verify policy + event emission

### Failure Injection
- Inject `ci_failure` event → verify `check_ci_stuck()` detects it after threshold
- Inject `ci_success` event → verify `check_ci_stuck()` clears the stuck state
- Create task with out-of-scope files → verify `check_scope_drift()` detects drift
- Run retry at cap → verify `task_rerouted` event emitted
- Remove all events → verify watchdogs degrade gracefully (no crash, no false positives)

### Rollback Path
- CI event emission is fire-and-forget in `ci_poller.sh` — removing the lines restores old behavior
- Scope API is opt-in — no existing behavior changes if unused
- Retry event emission is behind `--emit` flag — default off
- Docs changes are additive

## Outcome

_To be filled after implementation._

## Known Gaps (Deferred)

- Fully automated scope tracking via file-write hooks (would need per-task context in hooks)
- Automated retry execution (currently advisory only)
- CI event emission from GitHub Actions (currently only from local CI poller)
