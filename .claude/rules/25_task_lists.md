# TUI Task List Conventions

> The Claude Code task system (`TaskCreate`, `TaskUpdate`, `TaskList`) is a first-class
> workflow tool. These conventions prevent task list drift in long sessions.

## When to Create Tasks

Create a TUI task list when:
- Work involves 3+ distinct steps
- Executing a governed plan step that decomposes into sub-steps
- User provides multiple requests in one message
- Working in plan mode

Do NOT create tasks for: single-step work, pure Q&A, trivial edits.

## Naming

- **`subject`:** Imperative form, specific outcome ("Wire bid_type to logger", not "Work on logging")
- **`activeForm`:** Present continuous matching subject ("Wiring bid_type to logger")
- **`description`:** Include acceptance criteria and file paths when known

## Dependencies and Parallelism

Wire dependencies at creation time so the task list is a readable execution graph.

- **Sequential:** Use `addBlockedBy` when tasks must run in order.
  Example: "Write implementation" → "Run unit tests" → "Run make check"
- **Parallel:** Tasks with no `blockedBy` edges are implicitly parallel. Omit
  dependency edges between independent tasks — their independence is the signal.
- **Fan-out / fan-in:** Wire the downstream task with `addBlockedBy` listing all
  upstream IDs. Example: Tasks 1,2,3 are independent; Task 4 "Compare results"
  has `addBlockedBy: [1,2,3]`.
- **Task selection:** When multiple unblocked tasks are available, prefer lowest
  ID first. Exception: agents assigned via `owner` work their own tasks.
- **Sub-agent delegation:** Assign each spawned agent as `owner` of its task.
  Parent monitors via `TaskList` to check completions and newly-unblocked work.

## Status Protocol

- Set `in_progress` **before** starting work (drives spinner UX)
- Set `completed` only when fully done (tests pass, files written)
- Use `deleted` for superseded or irrelevant tasks — never leave stale pendings
- Never mark `completed` if blocked, errored, or partial

## Hygiene — Keeping the List Current

In long sessions, agents get absorbed in implementation and stop updating tasks.
The list drifts and loses its value as a progress signal. Prevent this:

- **Transition before action:** Always `TaskUpdate` status *before* starting and
  *after* finishing. If agents skip transitions, the list becomes fiction.
- **Scope changes → task changes:** When an approach is abandoned, immediately
  `deleted` obsolete tasks and create replacements. No zombie pendings.
- **Periodic audit:** After completing any task, call `TaskList` to review the
  full list. Delete or update anything stale. One tool call prevents compounding drift.
- **Cap at ~10 active tasks:** If the list grows larger, consolidate or split into
  phases — create later-phase tasks only after earlier phases complete.
- **Session-end sweep:** Before ending a session, call `TaskList` and ensure:
  - No tasks left `in_progress` (complete or revert to `pending`)
  - No stale `pending` tasks (delete or note in `checkpoints.md` / `MEMORY.md`)
  - Unfinished work captured in the persistent system, not just the ephemeral list

### Anti-Patterns

- Creating 15+ tasks upfront and never revisiting the list
- Leaving tasks `in_progress` across long tangents without updating
- Completing work without marking the task — the spinner lies to the user
- Treating the task list as write-only (create but never read/audit)

## Governed Initiative Integration

- When executing a checkpoint step, create TUI tasks for sub-steps
- Reference the checkpoint step ID in subjects (e.g., "R2.3: Generate behavior tables")
- On completion, update both the TUI task AND `checkpoints.md`

## Implementation Handoff Requirement

If you are writing a handoff prompt for another implementation agent, the
handoff must explicitly require the recipient to:
- refresh or draft the implementation plan first
- have a spawned reviewer agent review that plan before major edits
- create and maintain a task list for execution and validation
- assess the work for safe parallelism before delegating
- execute the work end to end autonomously through PR creation

This rule exists so handoffs do not skip directly from goal statement to
implementation without planning, review, task discipline, and bounded
parallelism.

## Relationship to Other Systems

| System | Scope | Persists? | Use for |
|--------|-------|-----------|---------|
| TUI Tasks | Current session | No | Step-by-step execution, spinner UX |
| `checkpoints.md` | Governed phase | Yes (git) | Cross-session progress |
| `MEMORY.md` | Project-wide | Yes (file) | High-level status |
| GitHub Issues | External | Yes | Follow-ups, bugs |

TUI tasks are the intra-session complement to checkpoints (inter-session).
They do not replace any existing system.
