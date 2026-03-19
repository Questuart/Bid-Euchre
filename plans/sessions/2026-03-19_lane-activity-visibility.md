# Lane-Activity / Current-Work Visibility

**Date:** 2026-03-19
**Parent:** PR-5 slice 3 of `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`
**Goal:** Give operators a single command to see which lane is working on what, their state, linked PRs, staleness, and attention needs.

## Context

`ops.py status` currently shows lanes with basic session info (active/idle, session task name) and a flat task list. It does NOT answer:
- What specific task each lane is on (task_id, subject, step)
- Whether a lane is blocked, waiting on review/CI, or stale
- Which PR is linked to a lane's current work
- When each lane last made meaningful progress
- Which lanes need operator attention

## Design

### State Derivation (no new persistent registry)

Synthesize lane activity from existing state:

1. **Worktree registry** (`worktree_registry/*.json`) → lane identity, branch, lifecycle_class, session_id, last_active
2. **Session metadata** (`session_metadata/*.json`) → session task, started_at, last_checkpoint
3. **Task state** (`task_state/*.json`) → task_id, subject, status, progress, items, owner_lane, blocked_by
4. **Events** (`events/events.jsonl`) → last event timestamp per lane for progress tracking
5. **PR linkage** → derived from task metadata `pr_number` field, or from recent events with pr_number payload

### State Model

Each lane gets a derived `state` from this priority chain:

| State | Condition |
|-------|-----------|
| `blocked` | Lane's active task has `status=blocked` or non-empty `blocked_by` |
| `active` | Lane has `session_id` set AND an in_progress task |
| `idle` | Lane has no `session_id` (or no in_progress task) |
| `unknown` | Insufficient data to classify |

Note: `waiting_review` and `waiting_ci` require live GitHub API calls. These are deferred to avoid coupling this slice to network availability. The existing `ops.py reviews` and `ops.py ci` surfaces already provide that data separately.

### Staleness Detection

A lane is flagged as `attention_needed` when:
- State is `active` but `last_progress` timestamp is older than `STALE_MINUTES` (default: 30)
- State is `blocked` (always needs attention)
- Lane is persistent but has no task and no session (idle with no work)

### PR Linkage

Derive from (in priority order):
1. Task state `pr_number` field (if present)
2. Most recent event for the lane with `pr_number` in payload
3. Fallback: None

### Output Fields Per Lane

```json
{
  "lane_id": "author-a",
  "lane_class": "author",
  "state": "active",
  "current_task_id": "task-uuid-1",
  "current_task_title": "Implement lane-activity visibility",
  "current_step": "Step 3/5: Write tests",
  "linked_pr": 985,
  "last_progress": "2026-03-19T14:30:00Z",
  "last_active": "2026-03-19T14:35:00Z",
  "attention_needed": false,
  "attention_reason": null,
  "branch": "codex/steward-author",
  "lifecycle_class": "persistent"
}
```

### Text Output Format

```
=== Steward Status ===

Lane Activity:
  author-a    [active]  Implement lane-activity visibility (step 3/5)  PR #985  14:35
  author-b    [idle]    —
  author-c    [active]  Fix CI regression  PR #982  14:20
  author-d    [idle]    —
  review      [idle]    —
  ops         [active]  Monitoring health  14:30
  scratch     [idle]    —

⚠ Attention:
  author-b: persistent lane idle with no task
  author-d: persistent lane idle with no task

Tasks: 2 active, 0 blocked, 3 completed
...
```

## File Plan

| File | Action | Description |
|------|--------|-------------|
| `src/bid_euchre/ops/status.py` | Edit | Extend `LaneStatus` dataclass, add `synthesize_lane_activity()`, update formatters |
| `scripts/internal/ops.py` | No change | Already delegates to status module formatters |
| `tests/unit/test_ops_status.py` | Edit | Add tests for lane activity synthesis |
| `tests/unit/test_ops_cli.py` | Edit | Add CLI integration test for lane-activity output |

## Implementation Steps

1. Extend `LaneStatus` dataclass with new fields
2. Add `synthesize_lane_activity()` helper that combines registry, session, task, and event data
3. Update `aggregate_status()` to call the synthesis helper
4. Update `format_status_text()` for the new lane-activity display
5. Update `format_status_json()` to include new fields
6. Add unit tests for:
   - Active lane with task and PR
   - Blocked lane
   - Idle lane (no session)
   - Missing/ambiguous state → unknown
   - Stale lane (active but no recent progress)
   - PR linkage from task metadata
   - PR linkage from events
   - Attention flag behavior
7. Add CLI integration test for text and JSON output
8. Run `make check-quiet`

## Parallelism Assessment

**Single-agent work.** All changes are in `status.py` and its test files — a single tightly coupled write scope. No disjoint work to parallelize.

## Validation Plan

- Tier 1: `uv run python -m pytest tests/unit/test_ops_status.py tests/unit/test_ops_cli.py -v`
- Tier 2: `make check-quiet`
- Manual smoke: Inspect `ops.py status` output on steward environment (from main checkout)
- Failure injection: Missing task state, stale heartbeat, ambiguous state

## Outcome

_To be filled after implementation._
