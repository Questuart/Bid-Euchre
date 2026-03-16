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
  +-- .claude/tmux/agent-ops-session.sh         # Persistent tmux session
  +-- .claude/tmux/agent-ops-layout.conf        # tmux layout config
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

## Persistent Session Manager (tmux)

The tmux session provides a persistent multi-role terminal environment that
survives disconnections and allows switching between role contexts instantly.

### Starting the tmux Session

From anywhere inside the repository:

```bash
.claude/tmux/agent-ops-session.sh
```

This creates (or attaches to) a tmux session named `bid-euchre-ops` with
four windows:

| Window | Name | Directory | Purpose |
|--------|------|-----------|---------|
| 0 | `author` | `../Bid-Euchre-author` | Implementation work |
| 1 | `review` | `../Bid-Euchre-review` | Code review and validation |
| 2 | `ops` | `../Bid-Euchre-ops` | Monitoring and orchestration |
| 3 | `scratch` | Main checkout | Ad-hoc inspection, control plane |

Custom session name:

```bash
.claude/tmux/agent-ops-session.sh my-session
```

### Idempotent Behavior

The script is safe to rerun:
- If the session already exists, it attaches to it
- If a role worktree does not exist, the window opens in the main checkout
  with a message suggesting `start-role-worktree.sh`

### tmux Key Bindings

The layout configuration (`.claude/tmux/agent-ops-layout.conf`) provides:

| Key | Action |
|-----|--------|
| `Alt+1` | Switch to author window |
| `Alt+2` | Switch to review window |
| `Alt+3` | Switch to ops window |
| `Alt+4` | Switch to scratch window |
| Mouse scroll | Scroll through output history |

Standard tmux prefix (`Ctrl+b`) bindings also work.

### Layout Configuration

The layout file at `.claude/tmux/agent-ops-layout.conf` sets:
- 50,000-line scrollback buffer
- Mouse support enabled
- 256-color terminal
- Status bar showing session name and active window

To reload after editing:

```bash
tmux source-file .claude/tmux/agent-ops-layout.conf
```

### Prerequisites

- `tmux` must be installed (`brew install tmux` on macOS)
- Role worktrees should be created first via `start-role-worktree.sh`
  (the session script works without them but windows will fall back to main)

---

## VS Code Audit Surface

The VS Code workspace provides a unified view across all role worktrees for
auditing diffs, runtime state, and test results.

### Opening the Workspace

```bash
code Bid-Euchre-agent-audit.code-workspace
```

This opens a multi-root workspace with four folders:

| Folder | Path | Purpose |
|--------|------|---------|
| `main` | `.` (repo root) | Control plane, runtime state |
| `author` | `../Bid-Euchre-author` | Author worktree code |
| `review` | `../Bid-Euchre-review` | Review worktree artifacts |
| `ops` | `../Bid-Euchre-ops` | Ops worktree state |

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
- **Ruff** (`charliermarsh.ruff`) — Linting and formatting
- **Python** (`ms-python.python`) — Language support
- **GitLens** (`eamodio.gitlens`) — Git history and blame

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

### Full Bootstrap Sequence

For a fresh setup (recommended order):

```bash
cd /path/to/Bid-Euchre                          # Main checkout
.claude/scripts/start-role-worktree.sh           # Create all 3 worktrees
.claude/tmux/agent-ops-session.sh                # Start persistent tmux session
code Bid-Euchre-agent-audit.code-workspace       # Open VS Code audit surface
```

For resuming after a restart:

```bash
cd /path/to/Bid-Euchre
.claude/scripts/start-role-worktree.sh author    # Update to latest main
.claude/tmux/agent-ops-session.sh                # Reattach to existing session
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
- `session_id` -- UUID identifying this session
- `role` -- Which role this session assumes
- `task` -- Short description of current work
- `plan_link` -- Path to the governing or session plan
- `last_checkpoint` -- Free-text progress marker

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

### Autonomous Review Loop (AUTONOMOUS_REVIEW_LOOP.md)

The review loop runs from the main checkout (not from role worktrees). It
is triggered by PR creation hooks and operates independently. The `review`
role worktree is for manual or agent-driven review work, not for the
automated review loop.

### Existing Worktree Scripts

- `claude-worktree.sh` -- Creates ephemeral worktrees for branch-per-PR work.
  Still valid and useful. Not replaced by role worktree scripts.
- `worktree-guard.sh` -- Blocks edits from main checkout. Still active.
- `worktree-reminder.sh` -- Reminds about worktree convention. Still active.
- `clean_worktrees.sh` -- Cleans worktrees with deleted remote branches.
  Complements (does not replace) the lifecycle cleanup in this workflow.

---

## Future Work

The following capabilities are planned for subsequent PRs and are documented
here for context. They are not yet implemented.

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
