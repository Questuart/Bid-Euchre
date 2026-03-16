# Autonomous Operator Workflow

## Overview

This document defines the target operating model for autonomous multi-agent
work in the Bid Euchre repository. The model uses three persistent role
worktrees, the main checkout as a control plane, VS Code as an audit surface,
and tmux for persistent sessions.

### Design Principles

1. **Main is read-only.** The main checkout is the control plane for
   bootstrapping, auditing, and orchestrating. Existing hooks
   (`worktree-guard.sh`, `worktree-reminder.sh`) enforce this.
2. **One writer per worktree.** Each worktree has at most one active agent
   session writing to it at any time.
3. **Roles are explicit.** Every agent session declares its role at startup.
   The role determines capabilities, branch conventions, and default behavior.
4. **State is repo-local.** Session, task, and worktree metadata live in
   gitignored runtime directories under `.claude/runtime/`. No external
   databases or services.
5. **Planning precedes execution.** Non-trivial tasks start with a planning
   phase that produces a bounded task list before any code is written.

### Target Architecture

```
Main checkout (control plane, read-only for agents)
  |
  +-- .claude/scripts/start-role-worktree.sh   # Bootstrap
  +-- .claude/scripts/start-agent-role.sh       # Launch
  +-- .claude/runtime/                          # Gitignored state
  |     +-- worktree_registry/                  # Worktree metadata
  |     +-- session_metadata/                   # Session state
  |     +-- task_state/                         # Delegated task state
  |     +-- review_loops/                       # Review loop state (existing)
  |     +-- plan_reviews/                       # Plan review state (existing)
  |
  +-- ../Bid-Euchre-author/                     # Author role worktree
  +-- ../Bid-Euchre-review/                     # Review role worktree
  +-- ../Bid-Euchre-ops/                        # Ops role worktree
```

---

## Roles

The operating model defines three persistent roles. Each role has a dedicated
worktree, branch, and capability set. Roles are conventions enforced through
documentation and bootstrap scripts, not through hard permission boundaries
(Claude Code does not support per-worktree permission tiers).

### Role Definitions

| Role | Purpose | Primary Activities |
|------|---------|--------------------|
| **author** | Implementation agent | Write code, run targeted tests, create branches, open PRs |
| **review** | Independent reviewer | Read diffs, run validation, review plans/reports/code |
| **ops** | Operator and monitor | Check status, run health checks, orchestrate, recover |

### Capability Matrix

| Capability | author | review | ops |
|------------|--------|--------|-----|
| Edit repo files | Yes | Limited (review artifacts, delegated fixes) | Limited (orchestration config) |
| Run targeted tests (Tier 1) | Yes | Yes | No |
| Run full validation (`make check`) | Yes (pre-PR) | Yes (review validation) | No |
| Create branches/worktrees | Yes | No | No |
| Open/update PRs | Yes | No | No |
| Review PRs | No | Yes | No |
| Inspect runtime state | Yes (own work) | Yes (review targets) | Yes (primary duty) |
| Run experiments | Yes | No | No |
| Run health checks | No | No | Yes |
| Run orchestration commands | No | No | Yes |
| Destructive/recovery actions | Approval-gated | No | Approval-gated |

### Branch Conventions

| Role | Branch | Worktree Path |
|------|--------|---------------|
| author | `role/author` | `../Bid-Euchre-author` |
| review | `role/review` | `../Bid-Euchre-review` |
| ops | `role/ops` | `../Bid-Euchre-ops` |

Role branches exist as persistent tracking branches. The author creates
feature branches from `role/author` for actual PR work (following the
existing worktree-per-PR convention from `AGENTS.md` section 2).

### User Role

The user does not manage day-to-day execution once a task is delegated. The
user:
- Audits diffs, plans, runtime state, and reports in VS Code
- Approves destructive or recovery actions when escalated
- Makes tool adoption, terminal preference, and workflow policy decisions
- Remains the authority for scope changes and initiative-level decisions

---

## Worktree Lifecycle

### Persistent vs Ephemeral

The system distinguishes two worktree classes:

| Class | Examples | TTL | Auto-prune |
|-------|----------|-----|------------|
| **Persistent** | `author`, `review`, `ops` | None | Never |
| **Ephemeral** | Task worktrees, experiment worktrees | Default 72h | Yes (when clean + stale) |

Persistent role worktrees are created once and reused across sessions. They
are updated to latest main on each bootstrap but never removed by cleanup
flows.

Ephemeral worktrees are created for bounded tasks (a specific PR, experiment,
or investigation) and carry a TTL from creation. Once expired and clean, they
become candidates for automated cleanup.

### Cleanup States (Ephemeral)

Ephemeral worktrees progress through lifecycle states:

```
active --> idle --> stale --> ready_to_remove --> (removed)
                      |
                      +--> quarantined --> (manual review) --> archived
```

| State | Condition | Action |
|-------|-----------|--------|
| `active` | Session is using this worktree | Protected from cleanup |
| `idle` | No active session, TTL not expired | No action needed |
| `stale` | TTL expired, no active session | Candidate for cleanup |
| `quarantined` | Has uncommitted changes | Needs manual review before removal |
| `ready_to_remove` | Clean, stale, no blockers | Safe to prune |
| `archived` | Metadata preserved, directory removed | Terminal state |

### One Writer Per Worktree

Each worktree may have at most one active agent session writing to it. This
prevents merge conflicts, race conditions, and confused state. The
`session_id` field in the worktree registry tracks the owning session.

If an agent needs to operate on a worktree that already has an active session,
it must either:
1. Wait for the existing session to complete
2. Use a different worktree
3. Escalate for manual resolution

### Creating Ephemeral Worktrees

Ephemeral worktrees follow the existing `claude-worktree.sh` pattern for
branch-per-PR work. The key addition is metadata: every ephemeral worktree
should have a registry entry with `class: "ephemeral"` and a TTL.

Future tooling (PR-3 scope) will provide `ops.py worktrees prune` for
lifecycle-aware cleanup. Until then, cleanup is manual via
`git worktree remove`.

---

## Bootstrap Workflow

### Creating Role Worktrees

From the main checkout:

```bash
# Create all three role worktrees
.claude/scripts/start-role-worktree.sh

# Create a single role worktree
.claude/scripts/start-role-worktree.sh author
```

The script is idempotent. If a role worktree already exists, it updates it
to latest main and refreshes the registry metadata.

### Starting a Role Session

```bash
# Start Claude in the author role
.claude/scripts/start-agent-role.sh author
```

This:
1. Verifies the role worktree exists
2. Sets `CLAUDE_ROLE` environment variable (readable by hooks)
3. Changes to the worktree directory
4. Execs `claude`

### Bootstrap Sequence

For a fresh setup:

```bash
cd /path/to/Bid-Euchre                          # Main checkout
.claude/scripts/start-role-worktree.sh           # Create all 3 worktrees
.claude/scripts/start-agent-role.sh author       # Start author session
```

For an existing setup (e.g., after restart):

```bash
cd /path/to/Bid-Euchre
.claude/scripts/start-role-worktree.sh author    # Update to latest main
.claude/scripts/start-agent-role.sh author       # Resume
```

---

## Session Metadata

Each active session writes metadata to
`.claude/runtime/session_metadata/<session_id>.json`. This enables:

- **Resume:** Read the latest session file for a role to recover context
  without conversation history.
- **Audit:** See which sessions are active, what they are working on, and
  where they left off.
- **Coordination:** Prevent two sessions from claiming the same worktree.

### Schema

See `.claude/runtime/session_metadata/README.md` for the full schema.

Key fields:
- `session_id` — UUID identifying this session
- `role` — Which role this session assumes
- `task` — Short description of current work
- `plan_link` — Path to the governing or session plan
- `last_checkpoint` — Free-text progress marker

### Session Resume

To resume work after a session ends or crashes:

1. Read the session metadata for the desired role
2. Check `last_checkpoint` for where the session left off
3. Read the linked `plan_link` for the full task context
4. Continue from the recorded state

This complements the Agent Execution Protocol in `CLAUDE.md`, which defines
discovery and handoff for governed initiatives.

---

## Task State

Delegated tasks are tracked in `.claude/runtime/task_state/<task_id>.json`.
Task state provides:

- **Bounded scope:** A finite list of items to complete
- **Progress tracking:** Which items are done, in progress, or blocked
- **Validation contract:** What commands to run and what "done" means
- **Auditability:** The user can inspect task state from VS Code at any time

### Schema

See `.claude/runtime/task_state/README.md` for the full schema.

### When to Create a Task Record

Create a task record when:
- The work involves more than 3 files
- The work involves new code (not just running existing scripts)
- The work involves design choices not specified in the governing plan
- The work is delegated from one role to another

Do not create a task record for:
- Running a command from the governing plan
- Filling in a checkpoint or table
- Minor adjustments within a single file

This mirrors the sub-plan creation criteria from `AGENTS.md` section 12.3.

### Task Lifecycle

```
pending --> in_progress --> completed
                |
                +--> blocked --> (unblocked) --> in_progress
                |
                +--> abandoned
```

1. **Create:** Agent creates the task record with items, validation steps,
   and completion criteria before starting work.
2. **Execute:** Agent works through items sequentially, updating status as
   each completes.
3. **Validate:** Agent runs all validation steps.
4. **Complete:** Agent sets status to `completed` only when all criteria are
   met.

### Blocked Tasks

When a task cannot proceed:
1. Set status to `blocked`
2. Record the blocker in `blocked_by`
3. Attempt the next non-dependent item if possible
4. Escalate if all items depend on the blocker

This aligns with the escalation protocol in `CLAUDE.md` "Escalating Blockers."

---

## Planning Contract

Non-trivial tasks must begin with a planning phase that is logically separate
from execution. This is a firm convention, not a suggestion.

### What Constitutes "Non-Trivial"

- More than 3 files changed
- New code (not just running existing scripts)
- Design choices not specified in the governing plan
- Cross-module changes
- Changes to contracts (rules, logging, metrics, scoring)

### Planning Phase

The planner (which may be the same agent in planning mode) produces:

1. **File plan** — Which files will be created, modified, or deleted
2. **Task list** — Bounded, ordered list of items
3. **Validation plan** — Which tests and checks to run
4. **Completion criteria** — What "done" looks like

The plan is recorded as either:
- A session plan file in `plans/sessions/` (for standalone work)
- A sub-plan under the governing plan (for initiative work)
- A task state record in `.claude/runtime/task_state/`

### Execution Phase

During execution, the agent:
- Works through the task list in order
- Updates task state as items complete
- May revise the plan, but only through explicit updates to the plan file
  or task state (not ad hoc scope expansion)
- Runs validation at checkpoints, not just at the end

### Relationship to Governing Plans

For work within a governed initiative (see `AGENTS.md` section 12), the
planning contract is already enforced through the governing plan, checkpoints,
and sub-plan registry. The task state system provides the same structure for
standalone work that does not belong to a governed initiative.

---

## Cleanup Policy

### Persistent Worktrees

Persistent role worktrees (`author`, `review`, `ops`) are never auto-pruned.
They may become stale if unused, but they remain available for the next
session. The bootstrap script updates them to latest main on reuse.

### Ephemeral Worktrees

Ephemeral worktrees have a default TTL of 72 hours. After expiration:

- **Clean worktrees** (no uncommitted changes) become `ready_to_remove`
  and can be pruned automatically.
- **Dirty worktrees** (uncommitted changes) are `quarantined` and require
  manual review before removal.

### Current Cleanup Mechanism

Until the lifecycle-aware `ops.py worktrees prune` lands (PR-3 scope),
cleanup is manual:

```bash
# List all worktrees
git worktree list

# Remove a specific worktree
git worktree remove ../Bid-Euchre-<name>

# Prune stale worktree references
git worktree prune
```

### What Not To Do

- Do not `rm -rf` worktree directories directly (interim deny rules block
  this; future hooks will redirect to proper cleanup).
- Do not remove persistent role worktrees.
- Do not remove worktrees with active sessions.

---

## Gitignored State Sharing

Worktrees created by `git worktree add` share the same `.git` directory as
the main checkout. This means:

- **Shared:** Git config, hooks, branches, remotes, refs
- **Shared:** `.claude/` directory contents at the repo root (because
  worktrees see the same working tree files at their own paths)
- **Not shared:** Working tree files (each worktree has its own copy)
- **Not shared:** Unstaged changes, stashes (per-worktree)

### Runtime State

The `.claude/runtime/` directory is gitignored and exists only in the main
checkout's working tree. Worktrees that need to read runtime state should
reference the main checkout path, which is discoverable from the registry
metadata.

However, because worktrees share the same `.git` directory, scripts running
in any worktree can locate the main checkout:

```bash
# From any worktree, find the main checkout
MAIN_DIR="$(git worktree list | head -1 | awk '{print $1}')"
```

### CLAUDE.md and Rules

The `CLAUDE.md` file and `.claude/rules/` directory are committed files, so
they are available in every worktree automatically. Changes to these files
in one worktree are visible in others after commit and checkout/rebase.

---

## Relationship to Existing Systems

### Agent Execution Protocol (CLAUDE.md)

The Agent Execution Protocol in `CLAUDE.md` defines how agents discover,
execute, and hand off work within governed initiatives. This workflow document
complements it by defining:
- The physical infrastructure (worktrees, sessions, roles)
- The task state tracking for standalone work
- The bootstrap and cleanup procedures

The two systems are compatible: an agent following the Agent Execution Protocol
operates within a role worktree bootstrapped by this workflow.

### Governing Plan Framework (AGENTS.md section 12)

The governing plan framework defines the plan hierarchy for major initiatives.
This workflow document does not replace or duplicate it. Instead:
- Governed initiative work uses the governing plan for scope and sequencing
- This workflow provides the session/task infrastructure underneath
- The `plan_link` field in session and task metadata connects to governing
  plan steps

### Autonomous Review Loop (AUTONOMOUS_REVIEW_LOOP.md)

The review loop runs from the main checkout (not from role worktrees). It
is triggered by PR creation hooks and operates independently. The `review`
role worktree is for manual or agent-driven review work, not for the
automated review loop.

### Existing Worktree Scripts

- `claude-worktree.sh` — Creates ephemeral worktrees for branch-per-PR work.
  Still valid and useful. Not replaced by role worktree scripts.
- `worktree-guard.sh` — Blocks edits from main checkout. Still active.
- `worktree-reminder.sh` — Reminds about worktree convention. Still active.
- `clean_worktrees.sh` — Cleans worktrees with deleted remote branches.
  Complements (does not replace) the lifecycle cleanup in this workflow.

---

## Future Work

The following capabilities are planned for subsequent PRs and are documented
here for context. They are not yet implemented.

### PR-2: Persistent Sessions (tmux)

- tmux session layout with windows per role
- VS Code audit workspace spanning all worktrees
- Deterministic session startup and resume

### PR-3: Operator CLI (ops.py)

- Single-command status summary
- Worktree lifecycle management (`prune`, `quarantine`, `archive`)
- Health checks and watchdogs
- CI failure classification and bounded remediation
- Recovery templates for common failure modes

### PR-4: Audit Index and Memory

- SQLite-based searchable index over runtime artifacts
- Curated memory for stable operator facts
- Session compaction and archive

### PR-5: Rollout and Safety

- Context safety scanning for auto-loaded content
- Shadow snapshots for rollback
- Skill promotion workflow
- End-to-end validation pilots

See `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` for the
full implementation sequence and design decisions.
