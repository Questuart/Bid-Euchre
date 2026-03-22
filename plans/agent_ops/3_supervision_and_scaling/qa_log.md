# Phase 3 QA Log

**Phase:** 3_supervision_and_scaling
**Last updated:** 2026-03-22

## Findings

| ID | Severity | Source | Status | Description |
|----|----------|--------|--------|-------------|
| BD-001 | WARN | Batch D proving run | open | `_classify_pool_status()` in worker_pool.py:279 treats `likely_active` + no-task as "active", blocking dispatch to idle lanes. Should return "idle" when has_task=False. |
| BD-002 | WARN | Batch D proving run | open | Dashboard `active_tasks` and `current_task_id` read from `task_state/` directory, not `task_queue/` (orchestrator packets). Dispatched task packets don't appear in dashboard lane status. |
| BD-003 | INFO | Batch D proving run | open | `workers dispatch` CLI requires packet in "approved" status but no CLI subcommand exists for approval. Workaround: call `transition_status()` Python API directly. |
