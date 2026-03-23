# Phase 3 QA Log

**Phase:** 3_supervision_and_scaling
**Last updated:** 2026-03-22

## Findings

| ID | Severity | Source | Status | Description | Fix PR |
|----|----------|--------|--------|-------------|--------|
| BD-001 | WARN | Batch D proving run | closed | `_classify_pool_status()` in worker_pool.py:279 treats `likely_active` + no-task as "active", blocking dispatch to idle lanes. Should return "idle" when has_task=False. | #1261 |
| BD-002 | WARN | Batch D proving run | closed | Dashboard `active_tasks` count (via `status.py` `load_tasks()`) reads from `task_state/` directory, not `task_queue/`. Per-lane `current_task_id` is a `WorkerState` field in the workers CLI, not a dashboard field. | #1261 |
| BD-003 | INFO | Batch D proving run | closed | `workers dispatch` CLI requires packet in "approved" status but no CLI subcommand exists for approval. Workaround: call `transition_status()` Python API directly. | #1261 |
| BD-004 | WARN | Batch D proving run | closed | Dispatch flow does not deliver tasks into live tmux pane sessions end-to-end. Execution via Agent subprocesses, not pane message delivery. Phase 3 exit gate. Tracked as #1259. | #1263 |
| BD-005 | INFO | Batch D proving run | open | Task packets don't auto-transition to `completed` when executing agent finishes. No completion callback from agent to task queue. | -- |
