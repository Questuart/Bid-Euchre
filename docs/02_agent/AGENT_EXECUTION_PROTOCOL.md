# Agent Execution Protocol

This document defines how autonomous agents discover, execute, and hand off
work within governed initiatives. For the plan hierarchy itself (governing
plans, sub-plans, registries, checkpoints), see `docs/02_agent/AGENTS.md`
section 12.

## Discovery Order

When an agent starts a session:

1. **Read `CLAUDE.md`** — find the "Active Governing Plans" table
2. **Read the governing plan** — understand scope, current phase, step sequence
3. **Read the active phase's `checkpoints.md`** — find the current step and status
4. **Read the phase's `plan.md`** (if it exists) — for phase-specific details
5. **Read `sub_plan_registry.md`** — check for in-progress or blocked sub-plans
6. **Resume from the last recorded state**

If no governing plan is active, fall back to `MEMORY.md` for context recovery.

**`checkpoints.md` vs `state.json`:** For governed initiatives with an
orchestrator (e.g., Arc D v2), `state.json` is the machine-readable execution
state used by the orchestrator for automatic step selection and resume.
`checkpoints.md` remains the human-readable progress log updated by agents at
session boundaries. Both are maintained; `state.json` is authoritative for
orchestrator decisions, `checkpoints.md` is authoritative for human-readable
session handoff.

## Determining the Next Runnable Unit of Work

An agent determines what to do next by reading the checkpoint file:

1. Find the first step with status `PENDING` or `IN_PROGRESS`.
2. If the step is `IN_PROGRESS`, read the session log for where it left off.
3. If the step is `BLOCKED`, check whether the blocker has been resolved.
   If resolved, update status to `IN_PROGRESS` and proceed. If not, skip
   to the next non-blocked step or escalate.
4. If all steps are `COMPLETE`, the phase is done. Check the governing plan
   for the next phase.

**What blocks progression:**
- A step's `Validates` conditions fail
- A required sub-plan is `blocked`
- A predecessor step is not `COMPLETE`
- A hard dependency declared in the governing plan is unmet

## Escalating Blockers

When an agent encounters a blocker it cannot resolve:

1. Mark the step `BLOCKED` in `checkpoints.md` with a clear description
2. Log the issue in the phase's `qa_log.md` (if one exists) as status `open`
3. Record the blocker in the session log entry in `checkpoints.md`
4. Attempt to proceed with the next non-dependent step, if any
5. If all remaining steps depend on the blocker, end the session with a
   clear handoff note

**Do not silently work around blockers.** If validation fails, do not
hand-edit outputs. If a script produces unexpected results, do not
improvise a replacement. Log and escalate.

## Recording Completion

When an agent completes a step:

1. Update `checkpoints.md`: set step status to `COMPLETE`, record date and session
2. If a sub-plan was involved, update its status in the sub-plan registry
3. Verify the step's `Validates` conditions are met
4. Proceed to the next step per the governing plan sequence

When an agent completes a phase:

1. Update all steps to `COMPLETE` in `checkpoints.md`
2. Update the governing plan's checkpoint or progress tracking
3. Check the governing plan for the next phase's prerequisites
4. If the next phase has no unmet dependencies, begin it
5. Update `MEMORY.md` with a summary

## Session Handoff Requirements

Before ending a session, an agent MUST:

1. **Update `checkpoints.md`** with current step status
2. **Record partial progress** if mid-step (e.g., "3/5 models trained")
3. **Verify open issues** are logged in `qa_log.md` (if applicable)
4. **Update `MEMORY.md`** with a one-line session summary
5. **Note uncommitted artifacts** — either commit or record their location
   in `checkpoints.md`

The next agent reads `checkpoints.md` and resumes from the recorded state.
No conversation history is required.

**Timeout detection:** Long-running orchestrator agents write a heartbeat
file every 60 seconds. Check with `run_rung.py --rung <rung> --check-alive`.
If stale (>5 min), the agent has died and should be respawned -- `state.json`
enables idempotent resume.

**Agent reliability:** Spawned agents silently die when they exhaust their
context window (~15 min or ~700KB output). Keep agent tasks small and focused
(one concept per agent). Never combine fix + validation in one agent. See
`.claude/rules/70_agent_reliability.md` for constraints.

## When to Create a Sub-Plan

Create a sub-plan when a governing plan step requires significant
implementation work. See `docs/02_agent/AGENTS.md` section 12.3 for the
full contract. Quick reference:

- >3 files changed
- New code (not just running existing scripts)
- Design choices not specified in the governing plan

Do NOT create a sub-plan for:
- Running a command from the governing plan
- Filling in a checkpoint or table
- Minor adjustments within a single file

## Plan Templates

| Template | Location | Use For |
|----------|----------|---------|
| Governing plan | `plans/_templates/governing_plan.md` | New major initiatives |
| Sub-plan | `plans/_templates/sub_plan.md` | Bounded implementation work |
| Checkpoints | `plans/_templates/checkpoints.md` | Phase/rung progress tracking |
| Sub-plan registry | `plans/_templates/sub_plan_registry.md` | Index of all sub-plans |
| Session plan | `plans/sessions/TEMPLATE.md` | Standalone one-off work |
