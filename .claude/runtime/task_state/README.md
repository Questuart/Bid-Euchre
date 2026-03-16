# Task State

Runtime metadata for delegated tasks. JSON files in this directory are
gitignored; only this README is committed.

## Schema (v1)

Each delegated task writes a JSON file named `<task_id>.json`.

```json
{
  "schema_version": 1,
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "subject": "Extract chart_data CSVs",
  "status": "in_progress",
  "plan_link": "plans/arc_d_v2/reporting_suite_compaction_plan.md",
  "items": [
    {"id": 1, "description": "Parse R0 JSON artifacts", "status": "completed"},
    {"id": 2, "description": "Generate R0 chart CSV", "status": "in_progress"},
    {"id": 3, "description": "Validate R0 output", "status": "pending"}
  ],
  "blocked_by": [],
  "validation_steps": ["make lint", "uv run pytest tests/unit/test_foo.py"],
  "completion_criteria": "All 9 CSVs extracted and validated"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | int | yes | Always `1` for this version |
| `task_id` | string | yes | UUID v4 identifying this task |
| `subject` | string | yes | Short description of the task |
| `status` | string | yes | One of `pending`, `in_progress`, `blocked`, `completed`, `abandoned` |
| `plan_link` | string | no | Relative path to the plan authorizing this task |
| `items` | array | yes | Ordered list of sub-items (see below) |
| `blocked_by` | array | no | List of blocker descriptions |
| `validation_steps` | array | no | Commands to run for validation |
| `completion_criteria` | string | no | What "done" means for this task |

### Item Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | int | yes | Sequential item number |
| `description` | string | yes | What this item does |
| `status` | string | yes | One of `pending`, `in_progress`, `completed`, `skipped` |

### Status Values

| Status | Meaning |
|--------|---------|
| `pending` | Task created but not started |
| `in_progress` | Active work underway |
| `blocked` | Cannot proceed (see `blocked_by`) |
| `completed` | All items done, completion criteria met |
| `abandoned` | Task cancelled or superseded |

### Planning Contract

Non-trivial tasks (>3 files, new code, design choices) must create a task
record before execution begins. The task record captures:

1. A bounded list of items (the "what")
2. Validation steps (the "how to verify")
3. Completion criteria (the "definition of done")

Execution may revise the plan only through explicit updates to the task
record. Ad hoc scope expansion without updating the task state is an
anti-pattern.

### Completion

A task is `completed` only when:
1. All items are `completed` or explicitly `skipped`
2. All validation steps pass
3. Completion criteria are met

The agent must set `status: "completed"` explicitly — it is never inferred.
