---
name: start-task
description: Receives a task packet from the orchestrator and bootstraps author lane work — scope lock, branch setup, and implementation kickoff. Use when an author lane begins a new delegated task.
---

# /start-task — Author Task Bootstrap

Receive a delegated task packet and bootstrap work in this author lane. This
skill covers the receipt-to-implementation-start phase — not multi-unit plan
decomposition (use `/executing-plans` for that).

## When to Use

- You are an author lane (author-a/b/c/d) and the orchestrator has assigned
  you a task packet
- You are starting a new bounded coding task from a plan step or handoff
- You need to set up a fresh branch and scope lock before implementation

## Workflow

### Phase 1 — Receive and Acknowledge

1. **Read the task packet** (title, description, scope_declared, validation):
   ```bash
   uv run python scripts/internal/ops.py task list
   ```

2. **Verify scope is clear:**
   - Are the file patterns in `scope_declared` specific enough?
   - Is the validation command runnable?
   - Is there a plan or sub-plan reference to read?

3. If scope is ambiguous, ask the orchestrator for clarification before
   proceeding. Do not guess at scope boundaries.

### Phase 2 — Branch Setup

4. **Ensure you are in your dedicated author worktree** (not the main checkout).
   Then create a fresh branch from main:
   ```bash
   git fetch origin main
   git checkout -b <branch-name> origin/main
   ```
   If you are on `main` in the shared checkout, create a worktree first — see
   `/managing-worktrees`. Branch naming: use the pattern from the task packet
   or governing plan (e.g., `ops/platform5-canonical-prompts`,
   `fix/scoring-edge-case`).

5. If the task references a plan or sub-plan, **read it now**:
   ```bash
   cat plans/agent_ops/<phase>/sub/<sub-plan>.md
   ```

### Phase 3 — Scope Lock

6. **Confirm file scope** matches the task packet's `scope_declared`:
   - List the files you expect to touch
   - Verify no overlap with other active author lanes
   - If you discover the task requires files outside declared scope, report
     the scope pressure to the orchestrator before proceeding

7. **Confirm validation commands** from the task packet are runnable.

### Phase 4 — Begin Implementation

8. Start coding within the declared scope. Follow the standard author
   lifecycle: implement → validate (Tier 1) → PR → handoff.

## Gotchas

- This skill is for single-task bootstrap, not multi-unit plan decomposition —
  use `/executing-plans` for multi-PR plan execution
- Do not skip scope lock — it prevents scope drift and cross-lane conflicts
- If the task packet has no `scope_declared`, treat this as a blocker and ask
  the orchestrator to fill it in
- Author lanes are background in the dashboard — the operator sees your status
  automatically; focus on the task, not on reporting visibility

## References

- `.claude/skills/executing-plans/WORK_UNIT_TEMPLATE.md` — work unit format
- `.claude/CLAUDE.md` § Implementation Handoff Protocol — handoff sequence
- `.claude/rules/15_testing_tiers.md` — validation tiers
