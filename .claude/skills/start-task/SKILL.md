---
name: start-task
description: Receives a task packet from the orchestrator and bootstraps author lane work — scope lock, branch setup, and implementation kickoff. Use when an author lane begins a new delegated task. Accepts an optional packet_id argument for direct dispatch.
---

# /start-task — Author Task Bootstrap

Receive a delegated task packet and bootstrap work in this author lane. This
skill covers the receipt-to-implementation-start phase — not multi-unit plan
decomposition (use `/executing-plans` for that).

## Arguments

- `packet_id` (optional) — If provided, load that specific task packet from
  the task queue. If omitted, scan the queue for dispatched packets owned by
  this lane.

## When to Use

- You are an author lane (author-a/b/c/d) and the orchestrator has assigned
  you a task packet
- A pane nudge sent `/start-task <packet_id>` into your session
- You are starting a new bounded coding task from a plan step or handoff
- You need to set up a fresh branch and scope lock before implementation

## Workflow

### Phase 1 — Receive and Acknowledge

1. **Read the task packet** (title, description, scope_declared, validation).
   If a `packet_id` argument was provided, load that specific packet:
   ```bash
   uv run python scripts/internal/ops.py task show <packet_id>
   ```
   Otherwise, list dispatched packets for this lane:
   ```bash
   uv run python scripts/internal/ops.py task list
   ```

2. **Accept the task** — a single command that performs three steps in
   sequence: acks the inbox message, sends a task-received ack to the
   orchestrator, and emits a `task_started` event:
   ```bash
   uv run python scripts/internal/ops.py task accept <PACKET_ID> --lane <LANE>
   ```
   This is idempotent — safe to run multiple times if the nudge fires twice
   or you re-invoke `/start-task` manually.

3. **Verify scope is clear:**
   - Are the file patterns in `scope_declared` specific enough?
   - Is the validation command runnable?
   - Is there a plan or sub-plan reference to read?

4. If scope is ambiguous, ask the orchestrator for clarification before
   proceeding. Do not guess at scope boundaries.

### Phase 2 — Branch Setup

5. **Ensure you are in your dedicated author worktree** (not the main checkout).
   Then create a fresh branch from main:
   ```bash
   git fetch origin main
   git checkout -b <branch-name> origin/main
   ```
   If you are on `main` in the shared checkout, create a worktree first — see
   `/managing-worktrees`. Branch naming: use the pattern from the task packet
   or governing plan (e.g., `ops/platform5-canonical-prompts`,
   `fix/scoring-edge-case`).

6. If the task references a plan or sub-plan, **read it now**:
   ```bash
   cat plans/agent_ops/<phase>/sub/<sub-plan>.md
   ```

### Phase 3 — Scope Lock

7. **Confirm file scope** matches the task packet's `scope_declared`:
   - List the files you expect to touch
   - Verify no overlap with other active author lanes
   - If you discover the task requires files outside declared scope, report
     the scope pressure to the orchestrator before proceeding

8. **Confirm validation commands** from the task packet are runnable.

### Phase 4 — Begin Implementation

9. Start coding within the declared scope. Follow the standard author
   lifecycle: implement -> validate (Tier 1) -> PR -> handoff.

## Nudge-Based Dispatch

When the orchestrator dispatches a task via `dispatch_to_worker()`, the
following happens automatically:

1. The task packet is transitioned to `dispatched` status with you as owner
2. An inbox message is written to your message bus inbox
3. A `tmux send-keys` nudge injects `/start-task <packet_id>` into your pane
4. This skill activates and loads the specific packet

The nudge is best-effort — if it fails, the task remains in durable state
and you can pick it up manually via `task list`.

## Auto-Completion on Merge

When you merge a PR via `gh pr merge`, the `post-merge-notify.sh` hook
automatically closes the task lifecycle:

1. Finds the active dispatched task packet owned by your lane
2. Transitions the packet from `dispatched` → `completed`
3. Sends a `completion` message to the orchestrator via message bus

This means **you do not need to manually complete your task packet** after
merging. The hook handles it. If the hook fails (best-effort), the
orchestrator can complete the packet manually.

The hook identifies your lane via `CLAUDE_AGENT_NAME` env var, falling
back to `CLAUDE_PROJECT_DIR` directory name parsing.

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
- `src/bid_euchre/ops/worker_pool.py` — dispatch_to_worker, nudge_pane
- `src/bid_euchre/ops/message_bus.py` — inbox messages, ack_message
- `.claude/hooks/post-merge-notify.sh` — auto-completion hook (dispatched → completed)
