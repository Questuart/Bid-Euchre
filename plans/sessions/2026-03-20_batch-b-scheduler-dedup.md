# Batch B: Scheduler Dedup Fixes

**Date:** 2026-03-20
**Author:** author-c
**Scope:** `src/bid_euchre/ops/scheduler.py`, `tests/unit/test_ops_scheduler.py`
**Issues:** #1042 (dead else branch), #1045 (missing escalation in dedup set)

## Problem

Two bugs in `_evaluate_retries_for_findings()` (scheduler.py lines 154-165):

1. **Dead else branch (#1042):** `read_events()` returns `list[dict[str, Any]]` (confirmed
   in `events.py:125`). The `else` branch with `getattr()` is unreachable dead code that
   obscures the fact that events are always dicts.

2. **Missing escalation dedup (#1045):** The dedup guard checks `("retry_attempted",
   "task_rerouted")` but not `"escalation"`. Per `_RETRY_EVENT_MAP` in `recovery.py:490-494`,
   the `"escalate"` action emits an `"escalation"` event. Without including it, escalated
   tasks can be re-processed on every tick.

## Fix

Replace the dedup loop (lines 154-165) with a simplified version that:
- Removes the dead `isinstance` / `else` branch -- always use `.get()` on dicts
- Adds `"escalation"` to the dedup event set alongside `"retry_attempted"` and `"task_rerouted"`

### Before
```python
already_retried: set[str] = set()
for evt in events:
    if isinstance(evt, dict):
        etype = evt.get("event_type", "")
        payload = evt.get("payload", {})
    else:
        etype = getattr(evt, "event_type", "")
        payload = getattr(evt, "payload", {})
    if etype in ("retry_attempted", "task_rerouted"):
        tid = payload.get("task_id") if isinstance(payload, dict) else None
        if tid:
            already_retried.add(tid)
```

### After
```python
already_retried: set[str] = set()
for evt in events:
    etype = evt.get("event_type", "")
    payload = evt.get("payload", {})
    if etype in ("retry_attempted", "task_rerouted", "escalation"):
        tid = payload.get("task_id") if isinstance(payload, dict) else None
        if tid:
            already_retried.add(tid)
```

## Tests

Add two tests to `TestEvaluateRetriesForFindings` in `test_ops_scheduler.py`:

1. **`test_dedup_skips_already_escalated_tasks`** -- Pre-populate event log with an
   `escalation` event for task `t1`, then create a subagent_failure finding for `t1`.
   Verify `_evaluate_retries_for_findings` returns 0 (skipped).

2. **`test_events_are_always_dicts`** -- Verify that events from `read_events()` are
   always dicts, validating the removal of the else branch.

## Validation

```bash
uv run python -m pytest tests/unit/test_ops_scheduler.py -v
make check-quiet
```

## Outcome
<!-- Filled after implementation -->
