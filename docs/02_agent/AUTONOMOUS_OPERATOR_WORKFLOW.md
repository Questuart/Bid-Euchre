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
  +-- ../<repo>-steward-orchestrator/         # orchestrator lane (target)
  +-- ../<repo>-steward-author/               # author-a lane
  +-- ../<repo>-steward-author-b/             # author-b lane
  +-- ../<repo>-steward-author-c/             # author-c lane
  +-- ../<repo>-steward-author-d/             # author-d lane
  +-- ../<repo>-steward-author-scratch/       # author-scratch lane
  +-- ../<repo>-steward-review/               # review lane
```

The `ops` lane runs from the main checkout itself. It does not have a
dedicated worktree because it is read-only -- it inspects state, checks
health, and supervises but does not write code.

The target steady-state model adds a distinct `orchestrator` lane as the
single normal user entrypoint for new work. `author-*` lanes become a
background/resumable worker pool that the orchestrator delegates into.

---

## Persistent Session Manager (tmux)

The tmux session provides a persistent multi-lane terminal environment that
survives disconnections and allows switching between lane contexts instantly.

### Starting the Steward Session (Canonical)

From the main checkout:

```bash
.claude/tmux/steward-session.sh
```

This creates (or attaches to) a tmux session named `steward`.

Current shipped baseline:

| Window | Name | Panes | Purpose |
|--------|------|-------|---------|
| 0 | `dashboard` | 4 (author-a, author-b, review, ops) | Mission-control view |
| 1 | `author-c` | 1 | Overflow author lane |
| 2 | `author-d` | 1 | Overflow author lane |
| 3 | `author-scratch` | 1 | Exploratory lane |

Target dashboard-first layout (governed follow-on target):

| Window | Name | Panes | Purpose |
|--------|------|-------|---------|
| 0 | `dashboard` | summary surface | High-signal current work and alerts |
| 1 | `orchestrator` | 1 | Single human-facing intake/delegation lane |
| 2 | `ops` | 1 | Supervisor / health / recovery lane |
| 3 | `review` | 1 | Review / validation lane |
| 4 | `issues` | 1 (optional) | Scheduled triage lane |

`author-*` lanes remain available as background workers and should be
resumable/inspectable by lane name rather than requiring them all to stay
foreground panes at all times.

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
all steward lane worktrees: `author-a` through `author-d`, `review`, and
`scratch`. The `ops` lane runs from the main checkout and does not need a
separate folder.

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
| **Review loop state (legacy)** | Local review loop state.json files (transitional -- prefer GitHub PR checks) |
| **Heartbeat check** | Agent heartbeat files in plans/ |
| **Worktree list** | All git worktrees |
| **Git status (all worktrees)** | Short status for every worktree |
| **Orchestrator log (tail)** | Last 30 lines of overnight orchestrator |
| **Session metadata** | Active session metadata JSON files |
| **Worktree registry** | Registered worktree metadata |

#### GitHub and CI Tasks

| Task | What it shows |
|------|---------------|
| **GitHub PR checks (current branch)** | CI check status for the current branch's PR |
| **GitHub PR checks (specific)** | CI check status for a specific PR number |
| **Deterministic prechecks** | Local deterministic prechecks output |
| **Plan review artifacts** | Contents of plan review artifact directories |

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

## Host-Level Recovery (macOS)

The steward session is designed to be persistent, but tmux sessions can be
lost due to host reboots, terminal crashes, or system updates. A macOS
`launchd` agent template is provided to automatically re-establish the
steward session on login.

### How It Works

The `launchd` agent runs a simple check:
1. If the `steward` tmux session exists, exit successfully (no action).
2. If the session is missing, run `steward-session.sh` in detached mode to
   recreate all lane windows and worktrees.

The agent uses `KeepAlive/SuccessfulExit=false` so `launchd` only restarts
the check if the script exits with an error. A 120-second throttle interval
prevents rapid restart loops.

### Installation

```bash
# Preview what will be installed (dry run)
.claude/launchd/install-launchd.sh --dry-run

# Install the agent
.claude/launchd/install-launchd.sh

# Uninstall the agent
.claude/launchd/install-launchd.sh --uninstall
```

The installer:
1. Substitutes `__REPO_PATH__` in the plist template with the actual repo path.
2. Validates the rendered plist with `plutil -lint`.
3. Copies it to `~/Library/LaunchAgents/com.bid-euchre.steward-session.plist`.
4. Loads the agent with `launchctl load`.

### Detached Mode

The `steward-session.sh` script supports a `STEWARD_DETACHED=1` environment
variable. When set, the script creates the tmux session but does not attach
to it (no `exec tmux attach`). This is required for non-interactive contexts
like `launchd` agents.

### Verifying the Agent

```bash
# Check if the agent is loaded
launchctl list | grep bid-euchre

# Check the agent log
cat /tmp/bid-euchre-steward-session.log

# Check for errors
cat /tmp/bid-euchre-steward-session.err

# Manually trigger the agent
launchctl start com.bid-euchre.steward-session
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent not running after login | Not loaded | Run `install-launchd.sh` |
| `claude` not found at launch | PATH changed since install | Re-run `install-launchd.sh` to re-resolve paths |
| Rapid restarts in log | Script failing immediately | Check `.err` log for syntax/path errors |
| Session exists but empty panes | tmux created but Claude exited | Manually check `tmux list-panes -t steward` |

### Path Resolution

The installer resolves paths **at install time**, not at runtime:

- **`__CLAUDE_BIN__`** -- absolute path to `claude` from `command -v claude`
- **`__LAUNCHD_PATH__`** -- the installer's shell `$PATH` plus essential system dirs
- **`__REPO_PATH__`** -- absolute path to the main checkout

If you install `claude` in a new location (e.g., move from Homebrew to cargo),
re-run `install-launchd.sh` to update the rendered plist.

The `steward-session.sh` script also accepts a `CLAUDE_BIN` env var override,
which the rendered plist sets explicitly so the session is not dependent on
launchd's limited default PATH.

### Files

| File | Purpose |
|------|---------|
| `.claude/launchd/ensure-steward-session.plist` | Template plist with `__REPO_PATH__`, `__CLAUDE_BIN__`, `__LAUNCHD_PATH__` placeholders |
| `.claude/launchd/install-launchd.sh` | Installer/uninstaller script |
| `~/Library/LaunchAgents/com.bid-euchre.steward-session.plist` | Installed (rendered) plist |
| `/tmp/bid-euchre-steward-session.log` | Agent stdout log |
| `/tmp/bid-euchre-steward-session.err` | Agent stderr log |

### Non-macOS Hosts

The `launchd` agent is macOS-specific. On Linux, equivalent recovery can be
achieved with a systemd user unit or a cron `@reboot` job that runs
`steward-session.sh` in detached mode. Templates for other platforms may be
added in future PRs.

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

Every active execution lane should own one primary task at a time. When a
task record is warranted (see "When to Create a Task Record" below), it is
recorded in `.claude/runtime/task_state/<task_id>.json` using the v2
schema (see `.claude/runtime/task_state/README.md`). Simple work that does
not meet the task-record creation criteria (single-file edits, running
commands, filling in checkpoints) does not require a formal task record but
still follows the one-task-at-a-time discipline.

Newly discovered work during execution should become:
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

When completing a task that has a formal task record (see "When to Create
a Task Record" below for criteria), a lane must:
1. Update `status` to `completed` in the task record
2. Record the validation outcome
3. Write a `completion_note` summarizing what was done and any follow-ups
4. Emit follow-ups or blockers explicitly rather than leaving them implicit
   in chat history

Work that does not warrant a task record (single-file edits, running
commands) should still follow general completion discipline: verify the
result and record any follow-ups in the appropriate persistent system
(checkpoints, MEMORY.md, or GitHub issues).

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

## Shadow Snapshots

Shadow snapshots provide lightweight, git-native point-in-time captures of
worktree state. They enable auditable rollback when an autonomous agent
produces a bad edit sequence.

### What a Shadow Snapshot Captures

| Field | Source | Purpose |
|-------|--------|---------|
| `head_sha` | `git rev-parse HEAD` | Commit to restore via `git reset --hard` |
| `branch` | `git rev-parse --abbrev-ref HEAD` | Branch context |
| `stash_sha` | `git stash create` | Uncommitted changes (staged + unstaged) |
| `files_changed` | `git diff --stat HEAD` | Change magnitude |
| `lane_id` / `task_id` | Caller-provided | Attribution |
| `reason` | Caller-provided | Human-readable context |
| `timestamp` | UTC ISO 8601 | Ordering and age-based pruning |

**Storage:** `.claude/runtime/snapshots/<snapshot_id>.json` (gitignored).

### When to Create Snapshots

- Before a risky autonomous refactor or multi-file edit sequence
- Before running an auto-fix agent that modifies committed code
- Before any destructive git operation in a worktree (rebase, reset)
- At agent session boundaries for progress checkpointing

### Creating a Snapshot

```bash
# Via CLI
uv run python scripts/internal/ops.py snapshot create \
  --worktree /path/to/worktree \
  --reason "before risky refactor" \
  --lane author-a \
  --task task-123

# Programmatic (from Python)
from bid_euchre.ops.snapshots import create_snapshot
record = create_snapshot(
    worktree_path="/path/to/worktree",
    reason="before risky refactor",
    snapshots_dir=Path(".claude/runtime/snapshots"),
    lane_id="author-a",
    task_id="task-123",
    events_dir=Path(".claude/runtime/events"),
)
```

### Listing Snapshots

```bash
# All snapshots (most recent first)
uv run python scripts/internal/ops.py snapshot list

# Filter by worktree
uv run python scripts/internal/ops.py snapshot list --worktree /path/to/worktree

# JSON output
uv run python scripts/internal/ops.py snapshot list --json
```

### Rolling Back

```bash
# Roll back to a specific snapshot
uv run python scripts/internal/ops.py snapshot rollback snap-abc123def456

# Check result
uv run python scripts/internal/ops.py snapshot rollback snap-abc123def456 --json
```

**Rollback is destructive.** It runs `git reset --hard` to the snapshot's
HEAD, then attempts `git stash apply` if uncommitted changes were captured.
If the stash apply fails (e.g., due to conflicts), the rollback still
succeeds for the HEAD reset and reports a warning with the stash SHA for
manual recovery.

### Retention and Pruning

Snapshots are bounded by two retention rules:

| Rule | Default | Purpose |
|------|---------|---------|
| Per-worktree cap | 20 | Prevent unbounded growth |
| Age cap | 168 hours (7 days) | Remove stale snapshots |

```bash
# Prune with defaults
uv run python scripts/internal/ops.py snapshot prune

# Custom retention
uv run python scripts/internal/ops.py snapshot prune \
  --max-per-worktree 10 --max-age-hours 48
```

### Interaction with Worktrees and Git

- Snapshots are **per-worktree**: each snapshot records and targets a
  specific worktree path. Rolling back snapshot A in worktree X does not
  affect worktree Y.
- `git stash create` produces a commit object without modifying the stash
  list or working tree, so snapshot creation has **no side effects** on the
  working state.
- Snapshot metadata is stored in `.claude/runtime/snapshots/` (gitignored),
  not in the worktree itself.
- Worktree cleanup (prune/archive) does not automatically remove snapshots.
  Run `snapshot prune` separately.
- The stash commit SHA referenced by a snapshot may be garbage-collected by
  `git gc` if the snapshot is very old. Prune snapshots before their stash
  objects expire (the 7-day default is well within git's default GC window).

### Event Integration

Snapshot operations emit durable events to the ops event log:

| Event Type | When |
|------------|------|
| `snapshot_created` | After successful snapshot creation |
| `snapshot_rolled_back` | After successful rollback |

These events appear in `ops.py events` output and are indexed by the
audit index for searchable history.

### Bypassing Snapshots

If the snapshot system causes issues:

1. **Skip snapshot creation**: Simply don't call `snapshot create` — it's
   always opt-in.
2. **Ignore stale snapshots**: Run `snapshot prune --max-per-worktree 0` to
   clear all snapshot metadata.
3. **Manual recovery**: Use standard `git reflog` and `git stash list` for
   recovery without the snapshot layer.

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

## Operator CLI Reference

The operator CLI (`scripts/internal/ops.py`) provides a single entrypoint for
workspace health monitoring, event inspection, and operational management.

### Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `status` | Lane/session/task health summary | `ops.py status --json` |
| `health` | Aggregated health (status + watchdogs) | `ops.py health` |
| `watchdogs` | Run all watchdog checks | `ops.py watchdogs --json` |
| `tick` | Run one scheduler cycle | `ops.py tick` |
| `daemon` | Run bounded repeating tick loop | `ops.py daemon --interval 300 --max-ticks 50` |
| `events` | Show recent events | `ops.py events --type ci_failure --limit 10` |
| `events drain` | Archive all events | `ops.py events drain` |
| `reviews` | PR review/check outcomes from GitHub | `ops.py reviews --pr 927` |
| `ci` | CI status and failure classification | `ops.py ci --pr 940` |
| `recover` | Recovery guidance for active failures | `ops.py recover` |
| `retry` | Evaluate retry/reroute policy | `ops.py retry --task t1 --emit` |
| `worktrees` | Worktree registry and reconciliation | `ops.py worktrees --json` |
| `worktrees prune` | Prune stale worktrees (dry-run default) | `ops.py worktrees prune --execute` |
| `worktrees quarantine` | Quarantine a dirty worktree | `ops.py worktrees quarantine /path` |
| `worktrees archive` | Archive (remove) a worktree | `ops.py worktrees archive /path` |
| `scope show` | Show task scope fields | `ops.py scope show --task t1` |
| `scope set` | Set declared_files for a task | `ops.py scope set --task t1 --declared 'src/*.py'` |
| `scope touch` | Record touched files for a task | `ops.py scope touch --task t1 --file src/a.py` |
| `index` | Build or show audit index | `ops.py index --rebuild` |
| `query` | Query the audit index | `ops.py query --text "ci_failure" --limit 5` |
| `memory` | Show curated memory entries | `ops.py memory --category workflow` |
| `compact` | List archived sessions | `ops.py compact` |
| `snapshot create` | Create a shadow snapshot | `ops.py snapshot create --worktree /path --reason "text"` |
| `snapshot list` | List shadow snapshots | `ops.py snapshot list --worktree /path` |
| `snapshot rollback` | Roll back to a snapshot | `ops.py snapshot rollback snap-abc123` |
| `snapshot prune` | Prune old snapshots | `ops.py snapshot prune --max-per-worktree 10` |

All commands support `--json` for machine-readable output. Use
`--runtime-dir` and `--plans-dir` to override default paths.

### Watchdog Checks

Six watchdog checks run automatically via `ops.py tick` or `ops.py watchdogs`:

| Check | What it detects | Input source |
|-------|----------------|-------------|
| `heartbeats` | Stale/missing heartbeat files | `plans/**/heartbeat` files |
| `task_progress` | Stalled in-progress tasks | `task_state/*.json` progress fields |
| `worktree_health` | Unregistered/missing worktrees | Git worktree list vs registry |
| `ci_stuck` | CI failing beyond threshold | `ci_failure`/`ci_success` events |
| `subagent_failures` | Repeated task failures | `task_failed` events |
| `scope_drift` | Files changed outside declared scope | `task_state/*.json` scope fields |

### Event Producers

Events are emitted to the durable event log (runtime events JSONL) by:

| Producer | Event types | Trigger |
|----------|------------|---------|
| `ci_poller.sh` | `ci_failure`, `ci_success` | CI pass/fail on PR checks |
| `post-task-event.sh` | `task_completed` | `gh pr merge` via PostToolUse hook |
| `ops.py tick` | `watchdog_finding`, `scheduler_tick` | Scheduler tick cycle |
| `ops.py retry --emit` | `retry_attempted`, `task_rerouted`, `escalation` | Retry policy evaluation |

### Task Scope Management

Task scope enables the `scope_drift` watchdog to detect when an agent modifies
files outside its declared scope. Scope is managed via the CLI:

```bash
# At task start: declare the intended file scope
ops.py scope set --task t1 --declared 'src/bid_euchre/ops/*.py' 'tests/unit/test_ops_*.py'

# During execution: record files as they are modified
ops.py scope touch --task t1 --file src/bid_euchre/ops/watchdogs.py

# Inspect current scope
ops.py scope show --task t1
```

The scope API can also be called programmatically:

```python
from bid_euchre.ops.status import update_task_scope, get_task_scope

update_task_scope("t1", declared_files=["src/bid_euchre/ops/*.py"])
update_task_scope("t1", touched_files=["src/bid_euchre/ops/watchdogs.py"], append_touched=True)
scope = get_task_scope("t1")
```

### Rollback and Disable

All operator stack features are designed to be independently disablable:

| Feature | Disable method |
|---------|---------------|
| CI event emission | Remove `emit_ci_event` calls from `ci_poller.sh` |
| Scope tracking | Stop calling `ops.py scope set/touch` — watchdog degrades gracefully |
| Retry event emission | Omit `--emit` flag (default: off) |
| Watchdog checks | Pass `checks={"heartbeats"}` to run only specific checks |
| Scheduler daemon | Do not run `ops.py daemon` — all checks are on-demand via `ops.py tick` |
| Full stack | Remove `.claude/hooks/post-task-event.sh` and stop running `ops.py` |

No feature alters core simulation, strategy, or experiment behavior.

---

## Shipped Work (Implementation History)

The following capabilities were delivered across the autonomous agent ops
workflow (`plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`):

| PR | Scope | Status |
|----|-------|--------|
| PR-1 | Operating model, worktree bootstrap, documentation | Shipped |
| PR-2 | Steward session launcher, VS Code audit workspace, launchd recovery | Shipped |
| PR-3 | Operator CLI (`ops.py`), reviews/CI surfaces, scheduler, watchdogs, retry/reroute | Shipped |
| PR-4 | Audit index, curated memory, session compaction | Shipped |
| PR-5 (slice 1) | CI event producers, scope management, retry events | Shipped (#961) |
| PR-5 (slice 2) | Issue-triage workflow, agent profile, conventions | Shipped |
| PR-5 (slices 3-7) | Context safety, shadow snapshots, skill promotion, lane-activity, scope/retry/CI closeout | Shipped (#1024, #1016, #1054, #1068, #1091, #1098, #1104, #1112) |

> **Note:** PR-5 is now **closed** (2026-03-20). All slices have shipped. The
> remaining pre-Platform-1 work is the post-PR-5 bridge (filesystem boundary
> + PR comment ingestion). See `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`
> for the full entry gate. The larger single-entry orchestrator /
> dashboard-first / remote-channel / exportable-platform architecture is
> tracked in the governed follow-on plan
> `plans/agent_ops/governing_plan.md`.
> Issue-triage details:
> `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`.

### Remaining Pre-Platform-1 Work (Post-PR-5 Bridge)

- Repo-bounded filesystem access as default in repo-owned entrypoints
- PR comment ingestion for trusted-bot operational signals (Codex Cloud)
- Bounded trusted command handling (conditional — only if still needed)

See `plans/sessions/2026-03-20_post-pr5-bridge-controls-and-review-surfaces.md`
for the bridge implementation plan.

### Follow-On Governed Initiative

- Agent-native orchestration layer: canonical lane prompts, named skills,
  supervisor routines, and automatic state updates so daily work is
  prompt-first rather than command-first
- Single-entry `orchestrator` lane and dashboard-first steward session, with
  `author-*` lanes acting as resumable background workers
- Remote operator channel integration (Telegram and/or Discord via official
  Claude Code plugin flows) for out-of-band summaries, alerts, bounded
  supervision, and 5-minute idle-attention notifications
- Background worker-pool management, resume-by-name, communication logging,
  and exportability to other coding projects
- Reviewed self-improving skill loop for repeated successful workflows
- Bounded second-model reviewer/maintainer service lanes (for example Codex as
  background reviewer/maintainer while Claude remains the primary executor)

See
`plans/agent_ops/governing_plan.md`
for the governed follow-on architecture plan, detailed `Platform-*` PR
roadmap, dependency batches, portability boundary, and development footguns.

See `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` for the
full implementation sequence and design decisions.

---

## Context Safety

### Overview

Content entering the curated memory store and the skill-promotion
workflow is scanned before persistence.  Every piece of content is
classified as:

| Outcome | Effect |
|---------|--------|
| **allow** | Content accepted without restriction |
| **warn** | Content persisted, but tagged `_safety_warnings` and logged |
| **reject** | Content blocked — not persisted, ValueError raised |

### What Is Scanned

| Rule | Severity | Detects |
|------|----------|---------|
| `secret_pattern` | reject | API keys, tokens, passwords, private keys |
| `shell_injection` | reject | Backtick execution, `$()` subshells, pipe-to-shell |
| `path_traversal` | reject | `../../` traversal, sensitive system paths |
| `missing_provenance` | reject | Missing `source_file` or `added_by` metadata |
| `oversized_content` | warn | Content exceeding 10 KB (configurable) |
| `binary_content` | reject | Null bytes / non-text data |

### When Scanning Happens

- **`add_entry()`** — enabled by default (`safety_scan=True`).  All curated
  memory entries are scanned before persistence.
- **CLI dry-run** — the `scan` subcommand lets an operator preview the scan
  result without persisting:

  ```bash
  # Scan inline text
  uv run python scripts/internal/build_curated_memory.py scan --text "content..."

  # Scan a file
  uv run python scripts/internal/build_curated_memory.py scan --file path/to/content

  # Include provenance for full check
  uv run python scripts/internal/build_curated_memory.py scan \
    --text "content" --source CLAUDE.md --by author-a
  ```

### Disabling the Scan

Pass `safety_scan=False` to `add_entry()` or use the existing `add` CLI
subcommand (which does not expose a `--no-scan` flag — bypassing requires
programmatic access, keeping the default safe).

### Audit Trail

Every scan result includes a SHA-256 `content_hash` for traceability.
Warned entries carry the `_safety_warnings` tag, making them filterable:

```bash
uv run python scripts/internal/build_curated_memory.py list --tag _safety_warnings
```

### Implementation

- Scanner module: `src/bid_euchre/ops/context_safety.py`
- Integration: `src/bid_euchre/ops/memory.py` (`add_entry()`), `src/bid_euchre/ops/skill_promotion.py`
- CLI surface: `scripts/internal/build_curated_memory.py` (`scan` subcommand)
- Tests: `tests/unit/test_ops_context_safety.py`, `tests/unit/test_ops_memory.py`

---

## Skill Promotion

### Overview

Repeated successful multi-step workflows can be proposed as skill candidates,
reviewed by an operator, scanned for context safety, and promoted into the
`.claude/skills/` directory with full provenance.  This is the PR-5
rollout/safety skill-promotion workflow — not the governed Platform-11
skill-learning loop.

### Lifecycle

```
propose → review (approve/reject) → promote → [disable]
```

1. **Propose** — create a candidate with name, description, content, and
   provenance.  Context-safety scanning runs immediately.  Even if the scan
   rejects the content, the candidate is persisted so the operator can inspect
   the reason and revise.
2. **Review** — an operator inspects the candidate and approves or rejects it.
   Only pending candidates can be reviewed.
3. **Promote** — write the skill to `.claude/skills/<name>/SKILL.md`.  Only
   allowed if the candidate is approved AND a re-scan at promotion time does
   not reject the content.
4. **Disable** — rename `SKILL.md` to `SKILL.md.disabled`.  The candidate
   record is retained for provenance.

### Storage

| Artifact | Location | Git status |
|----------|----------|------------|
| Candidates (pending review) | `.claude/runtime/skill_candidates/<id>.json` | gitignored |
| Promoted skills | `.claude/skills/<name>/SKILL.md` | committed |

### Context-Safety Integration

- Scanning is mandatory at **proposal** and **promotion** time.
- A `reject` outcome blocks promotion until the content is revised.
- A `warn` outcome allows promotion; warnings are recorded in the candidate
  metadata.
- There is no bypass path — even programmatic access runs the scan.

### CLI Commands

```bash
# List all candidates (or filter by status)
uv run python scripts/internal/ops.py skills [--status pending|approved|rejected|promoted] [--json]

# Propose a new skill
uv run python scripts/internal/ops.py skills propose \
  --name my-skill \
  --description "One-line description" \
  --content-file path/to/content.md \
  --source-workflow "Repeated PR review workflow" \
  --proposed-by author-b

# Review a candidate
uv run python scripts/internal/ops.py skills review <candidate-id> \
  --approve --reviewed-by operator --notes "Looks good"

# Promote an approved candidate
uv run python scripts/internal/ops.py skills promote <candidate-id>

# Disable a promoted skill
uv run python scripts/internal/ops.py skills disable my-skill --reason "Discovered issue"
```

### Rollback

Disabling a skill renames `SKILL.md` to `SKILL.md.disabled` in the skill
directory.  The candidate record under `.claude/runtime/skill_candidates/`
is retained for provenance.  To fully remove a disabled skill, delete the
directory manually.

### Implementation

- Promotion module: `src/bid_euchre/ops/skill_promotion.py`
- CLI surface: `scripts/internal/ops.py` (`skills` subcommand)
- Tests: `tests/unit/test_ops_skill_promotion.py`
