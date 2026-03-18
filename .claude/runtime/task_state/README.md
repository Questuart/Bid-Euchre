# Task State

Runtime metadata for delegated tasks. JSON files in this directory are
gitignored; only this README is committed.

## Schema (v2)

Each delegated task writes a JSON file named `<task_id>.json`.

### v2 Example

```json
{
  "schema_version": 2,
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "owner_lane": "author-a",
  "subject": "Extract chart_data CSVs",
  "goal": "Extract chart_data CSV files from R0-R3 JSON artifacts for the reporting suite",
  "status": "in_progress",
  "plan_link": "plans/arc_d_v2/reporting_suite_compaction_plan.md",
  "in_scope": [
    "Parse R0-R3 JSON artifacts",
    "Generate chart CSV files",
    "Validate output against existing baselines"
  ],
  "out_of_scope": [
    "Chart rendering",
    "Report generation",
    "Schema changes to source artifacts"
  ],
  "items": [
    {"id": 1, "description": "Parse R0 JSON artifacts", "status": "completed"},
    {"id": 2, "description": "Generate R0 chart CSV", "status": "in_progress"},
    {"id": 3, "description": "Validate R0 output", "status": "pending"}
  ],
  "blocked_by": [],
  "validation_steps": ["make lint", "uv run pytest tests/unit/test_foo.py"],
  "completion_criteria": "All 9 CSVs extracted and validated",
  "escalation_triggers": [
    "Touched files outside src/bid_euchre/arc_d_v2/",
    "Validation fails 3+ times on same step",
    "Blocked for more than 30 minutes"
  ],
  "completion_note": null
}
```

### Fields

| Field | Type | Required | Since | Description |
|-------|------|----------|-------|-------------|
| `schema_version` | int | yes | v1 | Schema version (`2` for this version) |
| `task_id` | string | yes | v1 | UUID v4 identifying this task |
| `owner_lane` | string | yes | v2 | Canonical `lane_id` of the lane that owns this task |
| `subject` | string | yes | v1 | Short description of the task (imperative form) |
| `goal` | string | yes | v2 | One-sentence goal statement for the task |
| `status` | string | yes | v1 | One of `pending`, `in_progress`, `blocked`, `completed`, `abandoned` |
| `plan_link` | string | no | v1 | Relative path to the plan authorizing this task |
| `in_scope` | array | yes | v2 | List of strings defining what this task covers |
| `out_of_scope` | array | yes | v2 | List of strings defining what this task must not do |
| `items` | array | yes | v1 | Ordered checklist of sub-items (see below) |
| `blocked_by` | array | no | v1 | List of blocker descriptions |
| `validation_steps` | array | no | v1 | Commands to run for validation |
| `completion_criteria` | string | no | v1 | What "done" means for this task |
| `escalation_triggers` | array | no | v2 | Conditions under which the lane must escalate rather than continue |
| `completion_note` | string/null | no | v2 | Short summary written at task completion or handoff |

### Field Semantics

**`owner_lane`** is the canonical `lane_id` of the lane that owns this task.
One lane should own one primary task at a time. If a lane discovers work
outside its scope, it should create a follow-up, hand off to another lane,
or escalate to `ops`.

**`in_scope`** and **`out_of_scope`** define the task's boundaries. A lane is
considered drifting if its changed files, validations, or reported progress
no longer match the declared scope.

**`escalation_triggers`** define when the lane must stop and escalate rather
than continuing autonomously. Escalation is required, not optional, when
any trigger condition is met.

**`completion_note`** is written at task completion or abandonment. It provides
a short summary of what was done, what was left undone, and any follow-ups.
This replaces implicit handoff information that would otherwise exist only
in chat history.

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

1. A bounded scope (`in_scope`, `out_of_scope`)
2. An ordered checklist of items (the "what")
3. Validation steps (the "how to verify")
4. Completion criteria (the "definition of done")
5. Escalation triggers (the "when to stop and ask")

Execution may revise the plan only through explicit updates to the task
record. Ad hoc scope expansion without updating the task state is an
anti-pattern.

### Completion

A task is `completed` only when:
1. All items are `completed` or explicitly `skipped`
2. All validation steps pass
3. Completion criteria are met
4. A `completion_note` is written summarizing outcome and any follow-ups

The agent must set `status: "completed"` explicitly -- it is never inferred.

### v1 Compatibility

v1 task files are accepted by v2 readers. Missing v2 fields are inferred:

| v2 Field | Inferred Value from v1 |
|----------|----------------------|
| `owner_lane` | Inferred from session metadata if available, otherwise `"unknown"` |
| `goal` | Same as `subject` |
| `in_scope` | `[]` (unbounded -- legacy behavior) |
| `out_of_scope` | `[]` (unbounded -- legacy behavior) |
| `escalation_triggers` | `[]` (no automatic escalation -- legacy behavior) |
| `completion_note` | null |

Writers should produce v2 entries. v1 entries remain readable.

## v1 Schema (Deprecated)

The v1 schema did not include `owner_lane`, `goal`, `in_scope`,
`out_of_scope`, `escalation_triggers`, or `completion_note`. See git
history for the full v1 specification.
