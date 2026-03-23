---
name: delegate-task
description: Creates a task packet, previews it for approval, and dispatches to an author lane. Use from the orchestrator lane to delegate bounded work.
---

# /delegate-task — Orchestrator Task Delegation

Create a durable task packet, preview it for user approval, and dispatch to
the appropriate author lane. This skill extracts the orchestrator's
intake-to-dispatch flow into a reusable workflow.

## When to Use

- You are the orchestrator and need to delegate a bounded coding task
- The user has submitted a work request that requires author-lane execution
- You need to formalize a task before handing it off

## Workflow

### Phase 1 — Draft Task Packet

1. **Create a TaskPacket** with these required fields:
   - **title:** Short imperative description (e.g., "Fix scoring edge case")
   - **description:** Full task description with acceptance criteria
   - **owner:** Target worker lane. Platform pool: `author-a` through
     `author-d`. Browser-game pool: `brws-author-a` through `brws-author-d`.
     Flex pool: `author-scratch`, `flex-a`, `flex-b`, `flex-c`.
   - **scope_declared:** File patterns that will be touched
   - **validation:** Commands the author must run (e.g., specific test files)
   - **priority:** low / normal / high
   - **domain:** Execution domain for routing — `platform` or `browser-game`.
     Determines which worker pool the task routes to. Omit for flex/unspecified.

2. **Choose the target lane** using the delegation guidelines:

   | Task Type | Preview Required | Suggested Lane | Domain |
   |-----------|-----------------|----------------|--------|
   | Single-file bugfix | No | Any idle author in matching pool | Infer |
   | Multi-file feature | Yes | author-a or author-b | platform |
   | Architectural change | Yes + plan review | author-a | platform |
   | Exploratory analysis | No | author-scratch or flex-* | (flex) |
   | Overflow / parallel work | Yes | author-c, author-d, or flex-* | Match source |
   | Browser-game work | Yes | brws-author-a through brws-author-d | browser-game |

3. **Check lane availability:**
   ```bash
   uv run python scripts/internal/ops.py dashboard --json
   ```
   Prefer idle or least-loaded lanes. Do not assign to a lane that already
   has an active task unless the user explicitly directs it.

### Phase 2 — Preview (non-trivial tasks)

4. For non-trivial tasks (multi-file, cross-module, or architectural):
   - Present the task packet to the user
   - Wait for one of: **approve**, **edit**, **redirect**, or **reject**

5. For trivial tasks (single-file fix, typo, previously approved pattern):
   - Skip preview and proceed directly to dispatch

### Phase 3 — Dispatch

6. **Create the task packet** (if not already created during preview):
   ```bash
   uv run python scripts/internal/ops.py task create \
     --title "<title>" \
     --description "<description with acceptance criteria>" \
     --owner "<lane>" \
     --priority "<priority>" \
     --domain "<platform|browser-game>" \
     --scope "<file pattern>" \
     --validation "<test command>"
   ```

7. **Dispatch to the author lane** using the blessed task dispatch path:
   ```bash
   uv run python scripts/internal/ops.py task dispatch <packet_id> <lane> --approve
   ```

   This single command:
   - Approves the packet (transitions pending/previewing -> approved)
   - Calls `dispatch_to_worker()` to wake the lane and assign the task
   - Writes an inbox message for the author lane
   - Nudges the lane's tmux pane with `/start-task <packet_id>`

   For packets already in `approved` status, omit `--approve`.

8. **Verify dispatch:**
   ```bash
   uv run python scripts/internal/ops.py task show <packet_id>
   uv run python scripts/internal/ops.py task list
   ```

## Gotchas

- Do not bypass preview for non-trivial work — the user must see and approve
  the delegation before it happens
- Do not assign to lanes that don't exist in the worktree registry (see
  `.claude/rules/75_worktree_protection.md` for the canonical list)
- If scope_declared is vague, tighten it before dispatching — authors should
  not have to guess their write boundary
- The orchestrator coordinates; it does not execute implementation work itself
- Check the dashboard for lane state — do not format your own competing
  worker-pool summary
- Always use `task dispatch` for the final dispatch step — do not use
  `workers dispatch` (low-level) or `Agent` (hidden subprocess delegation)

## References

- `.claude/agents/steward-orchestrator.md` — full orchestrator operating rules
- `.claude/CLAUDE.md` § Implementation Handoff Protocol — handoff requirements
- `.claude/rules/25_task_lists.md` — task list conventions
