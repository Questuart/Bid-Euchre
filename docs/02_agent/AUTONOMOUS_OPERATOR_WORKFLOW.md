# Autonomous Operator Workflow

## Overview

This document defines the operating model for autonomous multi-agent work in
the Bid Euchre repository. It covers the canonical lane identity model, the
deployed steward layout, the legacy three-role compatibility layer, and the
runtime metadata contracts that connect them.

### Design Principles

1. **Main is read-only.** The main checkout is the control plane for
   bootstrapping, auditing, and orchestrating. Existing hooks
   (`worktree-guard.sh`, `worktree-reminder.sh`) enforce this.
2. **One writer per worktree.** Each worktree has at most one active agent
   session writing to it at any time.
3. **Lanes are explicit.** Every agent session declares its lane identity at
   startup. The lane determines capabilities, branch conventions, and default
   behavior.
4. **State is repo-local.** Session, task, and worktree metadata live in
   gitignored runtime directories under `.claude/runtime/`. No external
   databases or services.
5. **Planning precedes execution.** Non-trivial tasks start with a planning
   phase that produces a bounded task list before any code is written.

---

## Identity Model

### Evolution

The identity model has evolved through three stages:

| Stage | Model | Bootstrap | Identity Field |
|-------|-------|-----------|----------------|
| **v1 -- Three-role** | `author`, `review`, `ops` | `start-role-worktree.sh` + `start-agent-role.sh` | `role` |
| **v2 -- Steward** | 7 named lanes in tmux/cmux | `steward-session.sh` | `lane_id` |
| **v3 -- Extensible** | Dynamic lane creation (future) | Orchestrator-managed | `lane_id` |

PR-1 documents v1 to v2 and locks the identity contract for v3.

### Canonical Lane Identity

**`lane_id`** is the canonical machine identity for any lane. It is an opaque
string, unique within a session, stable across restarts.

The deployed steward layout defines these canonical lane IDs:

| Lane ID | Lane Class | Worktree | Branch | Purpose |
|---------|-----------|----------|--------|---------|
| `ops` | `ops` | Main checkout | -- | Monitoring, orchestration |
| `review` | `review` | `...-steward-review` | detached | Independent review |
| `author-a` | `author` | `...-steward-author` | `codex/steward-author` | Primary implementation |
| `author-b` | `author` | `...-steward-author-b` | `codex/steward-author-b` | Parallel implementation |
| `author-c` | `author` | `...-steward-author-c` | `codex/steward-author-c` | Overflow implementation |
| `author-d` | `author` | `...-steward-author-d` | `codex/steward-author-d` | Overflow implementation |
| `author-scratch` | `scratch` | `...-steward-author-scratch` | `codex/steward-author-scratch` | Exploratory, non-production |

Future generated worker IDs such as `author-001` are supported by the model
but are not required to land in the current launcher.

### Lane Classes

Lane classes group lanes by functional role:

| Class | Purpose | Capabilities |
|-------|---------|-------------|
| `ops` | Operator and monitor | Status checks, orchestration, health monitoring |
| `review` | Independent reviewer | Read diffs, run validation, review plans/code |
| `author` | Implementation agent | Write code, run tests, create branches, open PRs |
| `scratch` | Exploratory work | Planning, comparisons, drafts, non-production reasoning |

Lane classes are conventions, not hard permission boundaries. Claude Code
does not support per-worktree permission tiers.

### Legacy Role Compatibility

The original three-role model (`author`, `review`, `ops`) remains available
through the legacy bootstrap scripts (`start-role-worktree.sh`,
`start-agent-role.sh`). These scripts are **compatibility-only** entrypoints
-- they are not the canonical bootstrap path.

**Mapping from legacy roles to canonical lane IDs:**

| Legacy Role | Maps To | Notes |
|-------------|---------|-------|
| `author` | `author-a` (default) | Legacy `author` is a single-lane alias for the worker class |
| `review` | `review` | Direct mapping |
| `ops` | `ops` | Direct mapping |

Legacy scripts write runtime metadata with both `role` (compatibility) and
`lane_id` (canonical) fields. New code should consume `lane_id` exclusively;
`role` will be removed in a future version.

### Machine vs. Display Identity

| Layer | Field | Purpose | Example |
|-------|-------|---------|---------|
| Machine identity | `lane_id` | Routing, coordination, metadata lookup | `author-a` |
| Transport identity | `tmux_session`, `tmux_window`, `tmux_pane` | Terminal session targeting | `steward`, `dashboard`, `1` |
| Display identity | `display_name` (optional) | Human-facing labels | `Author A` |
| Compatibility | `role` (optional, transitional) | Legacy script interop | `author` |

Machine identity (`lane_id`) is the sole routing key. Display names and
tmux targets are presentation metadata and must never be used as primary
identifiers for coordination or metadata lookup.

---

## Target Architecture

```
Main checkout (control plane, read-only for agents)
  |
  +-- .claude/tmux/steward-session.sh         # Canonical bootstrap
  +-- .claude/scripts/start-role-worktree.sh  # Legacy compatibility
  +-- .claude/scripts/start-agent-role.sh     # Legacy compatibility
  +-- .claude/runtime/                        # Gitignored state
  |     +-- worktree_registry/                # Lane/worktree metadata (v2)
  |     +-- session_metadata/                 # Session state (v2)
  |     +-- task_state/                       # Delegated task state (v1)
  |     +-- review_loops/                     # Review loop state (existing)
  |     +-- plan_reviews/                     # Plan review state (existing)
  |
  +-- ../<repo>-steward-author/               # author-a lane
  +-- ../<repo>-steward-author-b/             # author-b lane
  +-- ../<repo>-steward-author-c/             # author-c lane
  +-- ../<repo>-steward-author-d/             # author-d lane
  +-- ../<repo>-steward-author-scratch/       # author-scratch lane
  +-- ../<repo>-steward-review/               # review lane
```

The `ops` lane runs from the main checkout itself. It does not have a
dedicated worktree because it is read-only -- it inspects state, checks
health, and orchestrates but does not write code.

---

## Persistent Session Manager (tmux)

The tmux session provides a persistent multi-lane terminal environment that
survives disconnections and allows switching between lane contexts instantly.

### Starting the Steward Session (Canonical)

From the main checkout:

```bash
.claude/tmux/steward-session.sh
```

This creates (or attaches to) a tmux session named `steward` with:

| Window | Name | Panes | Purpose |
|--------|------|-------|---------|
| 0 | `dashboard` | 4 (author-a, author-b, review, ops) | Mission-control view |
| 1 | `author-c` | 1 | Overflow author lane |
| 2 | `author-d` | 1 | Overflow author lane |
| 3 | `author-scratch` | 1 | Exploratory lane |

Custom session name:

```bash
.claude/tmux/steward-session.sh my-session
```

### Idempotent Behavior

The script is safe to rerun:
- If the session already exists, it attaches to it
- If a lane worktree does not exist, it creates it automatically

### Metadata at Bootstrap

When `steward-session.sh` creates the session, it writes a v2 worktree
registry entry for each launched lane. This ensures all lanes are registered
with canonical `lane_id`, `lane_class`, and tmux transport fields from the
moment they start.

### Legacy tmux Session

The legacy `agent-ops-session.sh` script created a 4-window layout (author,
review, ops, scratch) matching the three-role model. It remains in the repo
for reference but is not the canonical path. Use `steward-session.sh` for
new sessions.

---

## VS Code Audit Surface

The VS Code workspace provides a unified view across all lane worktrees for
auditing diffs, runtime state, and test results.

### Opening the Workspace

```bash
code Bid-Euchre-agent-audit.code-workspace
```

This opens a multi-root workspace with folders for the main checkout and
all lane worktrees.

### File Exclusions

The workspace hides noisy directories from the file tree and search:
- `.venv`, `__pycache__`, `*.pyc`
- `data/runs`, `data/artifacts`, `data/models`, `data/reports`, `data/training`
- `.claude/worktrees` (ephemeral agent worktrees)

### VS Code Tasks

The workspace includes pre-configured tasks (`.vscode/tasks.json`) accessible
via **Terminal > Run Task** or `Ctrl+Shift+P > Tasks: Run Task`.

#### Testing Tasks

| Task | Command | Notes |
|------|---------|-------|
| **Run targeted pytest** | `uv run python -m pytest <path> -x -q` | Prompts for test path |
| **Run targeted pytest (verbose)** | `uv run python -m pytest <path> -x -v` | Verbose output |
| **Make check-quiet** | `make check-quiet` | Full pre-PR validation (default test task) |
| **Make check (full output)** | `make check` | Full validation with verbose output |
| **Ruff lint** | `uv run ruff check src/ tests/ ...` | Lint only |
| **Ruff format check** | `uv run ruff format --check ...` | Format check only |

#### Status Inspection Tasks

| Task | What it shows |
|------|---------------|
| **Rung status** | State of all rungs (r0-r3) |
| **Rung status (single)** | State of a selected rung (pick list) |
| **Review loop state** | Active review loop state.json files |
| **Heartbeat check** | Agent heartbeat files in plans/ |
| **Worktree list** | All git worktrees |
| **Git status (all worktrees)** | Short status for every worktree |
| **Orchestrator log (tail)** | Last 30 lines of overnight orchestrator |
| **Session metadata** | Active session metadata JSON files |
| **Worktree registry** | Registered worktree metadata |

### Recommended Extensions

The workspace recommends:
- **Ruff** (`charliermarsh.ruff`) -- Linting and formatting
- **Python** (`ms-python.python`) -- Language support
- **GitLens** (`eamodio.gitlens`) -- Git history and blame

---

## Bootstrap Workflows

### Canonical Bootstrap (Steward)

The steward session is the primary bootstrap path:

```bash
cd /path/to/Bid-Euchre                          # Main checkout
.claude/tmux/steward-session.sh                  # Start all lanes
code Bid-Euchre-agent-audit.code-workspace       # Open VS Code audit surface
```

For resuming after a restart:

```bash
cd /path/to/Bid-Euchre
.claude/tmux/steward-session.sh                  # Reattach to existing session
```

### Legacy Bootstrap (Three-Role)

The legacy scripts remain for backward compatibility with the three-role model:

```bash
# Create role worktrees (legacy -- creates author, review, ops)
.claude/scripts/start-role-worktree.sh

# Start Claude in a role (legacy -- launches in role worktree)
.claude/scripts/start-agent-role.sh author
```

These scripts are **compatibility-only**. They write runtime metadata with
both legacy `role` and canonical `lane_id` fields. New workflows should use
`steward-session.sh`.

---

## Lane Capability Matrix

| Capability | author | scratch | review | ops |
|------------|--------|---------|--------|-----|
| Edit repo files | Yes | Yes (non-production) | Limited (review artifacts) | Limited (orchestration config) |
| Run targeted tests (Tier 1) | Yes | Yes | Yes | No |
| Run full validation (`make check`) | Yes (pre-PR) | No | Yes (review validation) | No |
| Create branches/worktrees | Yes | No | No | No |
| Open/update PRs | Yes | No | No | No |
| Review PRs | No | No | Yes | No |
| Inspect runtime state | Yes (own work) | Yes | Yes (review targets) | Yes (primary duty) |
| Run experiments | Yes | Yes (exploratory) | No | No |
| Run health checks | No | No | No | Yes |
| Run orchestration commands | No | No | No | Yes |
| Destructive/recovery actions | Approval-gated | No | No | Approval-gated |

### User Role

The user does not manage day-to-day execution once a task is delegated. The
user:
- Audits diffs, plans, runtime state, and reports in VS Code
- Approves destructive or recovery actions when escalated
- Makes tool adoption, terminal preference, and workflow policy decisions
- Remains the authority for scope changes and initiative-level decisions

---

## Task Discipline and Lane Governance

### One Task Per Lane

Every active execution lane must own one primary task at a time. The task
is recorded in `.claude/runtime/task_state/<task_id>.json` using the v2
schema (see `.claude/runtime/task_state/README.md`).

Newly discovered work during execution must become:
- A follow-up item on the current task (if in scope)
- A new task handed off to another lane
- An escalation to `ops`

It must **not** silently expand the current task's scope.

### Task Record as Execution Contract

The task record defines the lane's execution boundaries:
- **`in_scope`** -- what this task covers
- **`out_of_scope`** -- what this task must not do
- **`escalation_triggers`** -- when to stop and ask rather than continue

A lane is considered drifting if its changed files, validations, or reported
progress no longer match the declared task scope.

### Lane Charters

Each lane class has an implicit charter derived from the capability matrix
above. In summary:

| Lane Class | Owns | Must Not Touch | Escalates When |
|------------|------|----------------|----------------|
| `author` | Implementation in its worktree | Other lanes' worktrees, main checkout | Scope exceeds task, validation fails repeatedly, blocked, destructive action needed |
| `scratch` | Exploratory work, drafts | Production code, other lanes' work | Work becomes production-ready (hand off to author) |
| `review` | Review artifacts, validation | Implementation code (except delegated fixes) | Blocking findings that need implementation |
| `ops` | Status, orchestration, health | Implementation code | Recovery action needs approval |

### Escalation Requirements

Escalation is required, not optional, when:
- Requested work exceeds the declared `in_scope`
- Touched files move outside the lane's allowed ownership
- Validation fails repeatedly (3+ times on the same step)
- The lane is blocked beyond a reasonable threshold
- Destructive or risky recovery action is needed
- The plan or requirements become materially ambiguous

### Task Completion Requirements

When completing a task, a lane must:
1. Update `status` to `completed` in the task record
2. Record the validation outcome
3. Write a `completion_note` summarizing what was done and any follow-ups
4. Emit follow-ups or blockers explicitly rather than leaving them implicit
   in chat history

### Progress Visibility

Lanes must keep their repo-local task record aligned with the in-session
task list they are actually following. The task record in
`.claude/runtime/task_state/` is the durable progress signal; the in-session
TUI task list (see `.claude/rules/25_task_lists.md`) is the ephemeral
intra-session complement.

The v2 task schema includes a `progress` object with concrete fields for
durable progress tracking:

- **`last_completed_item`** -- ID of the last completed checklist item
- **`last_artifact`** -- path to the last meaningful file touched
- **`last_validation`** -- last validation command and outcome
- **`current_blocker`** -- current blocker description, or null
- **`last_forward_progress_at`** -- ISO 8601 timestamp of last forward progress

Agents should update `progress` whenever they complete a checklist item,
run a validation step, or encounter/clear a blocker. This enables `ops` to
distinguish "alive and progressing" from "alive but drifting/blocked"
without reading terminal history.

---

## Session Metadata

Each active session writes metadata to
`.claude/runtime/session_metadata/<session_id>.json`. This enables:

- **Resume:** Read the latest session file for a lane to recover context
  without conversation history.
- **Audit:** See which sessions are active, what they are working on, and
  where they left off.
- **Coordination:** Prevent two sessions from claiming the same worktree.

### Schema

See `.claude/runtime/session_metadata/README.md` for the full v2 schema.

Key fields:
- `session_id` -- UUID identifying this session
- `lane_id` -- Canonical lane identity (e.g., `author-a`, `review`, `ops`)
- `role` -- Optional compatibility field (transitional, maps to legacy role)
- `task` -- Short description of current work
- `plan_link` -- Path to the governing or session plan
- `last_checkpoint` -- Free-text progress marker

### Session Resume

To resume work after a session ends or crashes:

1. Read the session metadata for the desired lane
2. Check `last_checkpoint` for where the session left off
3. Read the linked `plan_link` for the full task context
4. Continue from the recorded state

This complements the Agent Execution Protocol in `CLAUDE.md`, which defines
discovery and handoff for governed initiatives.

---

## Task State

Delegated tasks are tracked in `.claude/runtime/task_state/<task_id>.json`.
See `.claude/runtime/task_state/README.md` for the full v2 schema.

Task state provides:

- **Bounded scope:** `in_scope` and `out_of_scope` define task boundaries
- **Progress tracking:** Ordered checklist items with status
- **Validation contract:** Commands to run and completion criteria
- **Escalation contract:** Conditions that require stopping and escalating
- **Auditability:** The user can inspect task state from VS Code at any time

### When to Create a Task Record

Create a task record when:
- The work involves more than 3 files
- The work involves new code (not just running existing scripts)
- The work involves design choices not specified in the governing plan
- The work is delegated from one lane to another

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

---

## Cleanup Policy

### Persistent Worktrees

Persistent lane worktrees (all steward lanes) are never auto-pruned.
They may become stale if unused, but they remain available for the next
session. The bootstrap script updates them on reuse.

See `.claude/rules/75_worktree_protection.md` for the protected worktree list
and cleanup safety rules.

### Ephemeral Worktrees

Ephemeral worktrees (created by `claude-worktree.sh` or spawned agents) have
a default TTL of 72 hours. After expiration:

- **Clean worktrees** (no uncommitted changes) become `ready_to_remove`
  and can be pruned automatically.
- **Dirty worktrees** (uncommitted changes) are `quarantined` and require
  manual review before removal.

### Current Cleanup Mechanism

Until the lifecycle-aware `ops.py worktrees prune` lands (future scope),
cleanup is manual:

```bash
# List all worktrees
git worktree list

# Remove a specific ephemeral worktree (after safety checks)
git worktree remove ../Bid-Euchre-<name>
```

**Never remove steward worktrees.** See `.claude/rules/75_worktree_protection.md`.

---

## Relationship to Existing Systems

### Agent Execution Protocol (CLAUDE.md)

The Agent Execution Protocol in `CLAUDE.md` defines how agents discover,
execute, and hand off work within governed initiatives. This workflow document
complements it by defining:
- The physical infrastructure (worktrees, sessions, lanes)
- The task state tracking for standalone work
- The bootstrap and cleanup procedures

The two systems are compatible: an agent following the Agent Execution Protocol
operates within a lane worktree bootstrapped by this workflow.

### Autonomous Review Loop (AUTONOMOUS_REVIEW_LOOP.md)

The local review loop runs from the main checkout (not from lane worktrees).
It is triggered by PR creation hooks and operates independently. The `review`
lane worktree is for manual or agent-driven review work, not for the
automated review loop.

**Transitional status:** The local review loop infrastructure
(`.claude/runtime/review_loops/`, `.claude/runtime/plan_reviews/`) is
transitional. PR review is migrating to an online-first model where GitHub
is the source of truth for review state and deterministic prechecks run as
GitHub Actions. Do not build new first-class dependencies on the local
review loop directories. See
`plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` for the
review architecture migration plan.

### Existing Worktree Scripts

- `claude-worktree.sh` -- Creates ephemeral worktrees for branch-per-PR work.
  Still valid and useful. Not replaced by lane worktree scripts.
- `worktree-guard.sh` -- Blocks edits from main checkout. Still active.
- `worktree-reminder.sh` -- Reminds about worktree convention. Still active.
- `clean_worktrees.sh` -- Cleans worktrees with deleted remote branches.
  Complements (does not replace) the lifecycle cleanup in this workflow.

---

## Future Work

The following capabilities are planned for subsequent PRs and are documented
here for context. They are not yet implemented.

### Operator CLI (ops.py)

- Single-command status summary
- Worktree lifecycle management (`prune`, `quarantine`, `archive`)
- Health checks and watchdogs
- CI failure classification and bounded remediation
- Recovery templates for common failure modes

### Scheduler and Event System

- Durable event production/consumption
- Queue-driven review execution
- Scheduled health checks and remediation
- `launchd` recovery for persistent sessions

### Audit Index and Memory

- SQLite-based searchable index over runtime artifacts
- Curated memory for stable operator facts
- Session compaction and archive

### Rollout and Safety

- Context safety scanning for auto-loaded content
- Shadow snapshots for rollback
- Skill promotion workflow
- End-to-end validation pilots

See `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` for the
full implementation sequence and design decisions.
