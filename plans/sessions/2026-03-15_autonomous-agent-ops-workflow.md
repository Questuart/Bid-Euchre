# Autonomous Agent Ops Workflow
**Date:** 2026-03-15
**Goal:** Move to a fully autonomous multi-agent operating model where agents execute work end-to-end in isolated worktrees and persistent terminal sessions, while the user audits progress, diffs, artifacts, and status primarily through VS Code.

> **Scope note:** This plan has governing-initiative scale (5 PRs, new `src/` package, new CLI) but is filed as a session plan because it is infrastructure/tooling work that does not require the checkpoint/sub-plan governance designed for research lineages. If scope grows beyond 5 PRs, promote to a governed initiative under `plans/agent_ops/`.

## Plan
- PR-1: Establish the operating model, bootstrap scripts, and documentation for role-based worktrees (`author`, `review`, `ops`) using the existing Claude worktree hook system as the foundation.
- PR-2: Add a repo-owned tmux launcher and VS Code audit workspace so autonomous sessions can be started consistently and audited from a stable editor surface.
- PR-3: Add a lightweight operator CLI (`ops.py`) that summarizes worktree health, review-loop state, rung state, heartbeats, watchdog status for long-running processes, scheduled health checks, and latest artifacts from one command.
- PR-4: Add a two-layer memory system: small curated memory for stable operator facts plus a local audit index over execution logs, review artifacts, checkpoints, and manifests for searchable history.
- PR-5: Roll out the autonomous workflow in stages, validate that it works for real tasks, add skill-promotion and context-safety workflows, and retire ad hoc “multiple terminals in one checkout” usage.

## Sequencing — Roadmap Position

> **Decision date:** 2026-03-15
> **Revised:** 2026-03-16 (post-review: CI remediation, consistency cleanup, resolved design decisions)
> **Context:** Arc D v2 QUICK ladder complete (R0-R3, 9/9 PASS on R3). FULL backfill running (R0-R2 × 3 seeds, sequential orchestrator). Browser-game initiative ACTIVE but not yet started.

This plan is a **staged enabling track**, not a monolithic blocker. It should not pause Arc D and should not be deferred until after everything else. The thin slice lands after the next Arc D closeout slice (Phase 4a); the heavier infrastructure lands as browser-game creates real multi-agent coordination pressure.

### Compatibility with Running FULL Backfill

PRs 1-2 are **low-risk** during the FULL backfill. They are almost entirely additive (new files, new packages, new docs) and do not touch any modules the orchestrator imports. PRs 3-5 involve hooks, permission changes, and cleanup/watchdog flows that could affect active agent sessions and operator behavior — these should be staged per the triggers below, not bundled with 1-2.

> **Note:** "Low-risk" is not "zero-risk." The orchestrator runs from the main checkout and each `uv run python` invocation reads code from disk. Verify that any PR merged to main during FULL compute does not touch orchestrator-imported modules.

### Immediate (now, during Arc D sprint) — DONE (2026-03-16)

Adopt **user-side workflow changes only** — no repo PRs required:
- ~~Ghostty (or equivalent) as primary terminal host~~ ✅ Installed
- ~~`tmux` for persistent sessions~~ ✅ Already installed (3.6a)
- Role-based worktrees (informal adoption of `author`/`review`/`ops` convention)
- VS Code as audit surface for diffs, plans, and runtime artifacts
- ~~**Permission model:**~~ ✅ Already configured — `Bash(*)` allow, `defaultMode: bypassPermissions`, interim `rm -rf ../:*` and `rm -rf ../*:*` deny rules in place.
- ~~Worktree sprawl cleanup~~ ✅ Cleaned 37 stale worktrees (2026-03-16)

> **Permission model note:** The broader permission redesign (replacing interim deny rules with hook-based lifecycle tooling) is **tracked work for PR-3**, not an ad-hoc mid-sprint change. The interim deny rules are sufficient until then.

### After Phase 4a (QUICK charts reporting sweep) → PRs 1-2

Land the **lightweight workflow scaffolding**:
- **PR-1:** Worktree/bootstrap contract, role conventions, session/task metadata
- **PR-2:** tmux launcher, VS Code audit workspace and tasks

These are low-risk (mostly tooling/docs) and additive. Sequencing them after Phase 4a keeps Arc D v2 closeout on the critical path while slotting infrastructure into the natural gap while FULL compute continues.

### Before browser-game backend/frontend parallelism → PRs 3-4

Land the **operator CLI and memory/index layer**:
- **PR-3:** `ops.py` CLI, health checks, watchdogs, recovery templates, CI remediation, permission migration
- **PR-4:** Curated memory, audit index, session compaction/archive

These are cross-cutting and will be easier to design once Arc D runtime artifacts and operational pain points are stable. The browser-game initiative is exactly the kind of work that benefits most — it involves parallel tracks (domain engine, backend API, frontend product, replay/export, deployment) that create real multi-agent coordination pressure.

### Before hosted-play becomes externally exposed → PR-5

Land the **higher-autonomy safeguards**:
- **PR-5:** Rollout validation, agent profiles, context safety, shadow snapshots

This must be in place before the hosted product is operationally important or externally exposed.

### Summary Sequence

| Step | Trigger | Deliverables |
|------|---------|-------------|
| 0 | Now | ~~User-side workflow~~ ✅ DONE (Ghostty, tmux, permissions, worktree cleanup) |
| 1 | After Phase 4a (QUICK charts) | PRs 1-2 (scaffold) |
| 2 | Browser-game Phase 0/1/2 starts | Browser-game benefits from improved agent workflow |
| 3 | Browser-game enters backend/frontend parallelism | PRs 3-4 (operator CLI, memory/index, CI remediation) |
| 4 | Before hosted-play external exposure | PR-5 (rollout, safety, recovery) |

## Resolved Design Decisions (2026-03-16)

These decisions were resolved during the 2026-03-16 review session.

### ops/ Package Location

**Decision:** Hybrid — CLI entrypoint in `scripts/internal/ops.py`, reusable logic in `src/bid_euchre/ops/`.

- `scripts/internal/ops.py` is the operator-facing entrypoint (consistent with existing `run_rung.py`, `run_suite.py` pattern).
- `src/bid_euchre/ops/` makes parsing, classification, and tests much cleaner.
- `src/bid_euchre/ops/` is a nested package under the existing library tree, **not** a new repo-top-level directory.
- **Constraint:** Treat `src/bid_euchre/ops/` as internal tooling. Do not re-export it broadly or add it to the public engine API surface.

### ops/ Coupling to Arc D Internals

**Decision:** Prefer direct state-file reading. Narrow imports only for very stable helpers.

- Parse JSON/JSONL/heartbeat files directly.
- Import stable path/time helpers only where that avoids duplicated path logic.
- **Do not** import orchestration, domain, or schema internals just to answer status questions.
- **Why:** Keeps ops loosely coupled to active research code. Arc D v2 refactors should not break operator tooling.
- **Tradeoff:** Duplicates a bit of schema knowledge, but the ops layer becomes more robust to research-code churn.

### Worktree Cleanup Tooling

**Decision:** The existing `scripts/internal/clean_worktrees.sh` is useful for inventory but does not solve worktree sprawl.

- `clean_worktrees.sh` only targets branches whose upstream is marked `[gone]`. It does **not** handle: stale local task worktrees, `.claude/worktrees/*`, detached worktrees, or TTL-expired worktrees.
- Real cleanup requires the lifecycle classification and prune flows designed in PR-3 (`ops.py worktrees prune`).
- Until PR-3 lands, worktree cleanup is manual (`git worktree remove`) guided by `git worktree list` inspection.
- **2026-03-16:** Manually cleaned 37 stale worktrees (27 timestamp, 7 clean agent/feature, 3 dirty-but-superseded). This confirms the sprawl problem is real and motivates the PR-3 lifecycle system.

### Permission Model Evolution

**Decision:** The broader permission redesign is tracked work for PR-3, not an ad-hoc mid-sprint change.

- Interim deny rules (`rm -rf ../:*`, `rm -rf ../*:*`) are already in place and sufficient.
- The full migration (removing deny rules, adding PreToolUse hook redirection to `ops.py worktrees prune`) lands with PR-3.
- **Why:** Permission changes affect every Claude session. They should be deliberate and versioned, not drift in as side tweaks.

## Decisions

### Target Workflow
- VS Code remains the primary audit and editing UI.
- Ghostty or another native terminal becomes the primary terminal host.
- tmux becomes the session manager for long-lived autonomous agents.
- Each active autonomous role gets its own git worktree.
- The main checkout becomes a control plane and audit root, not a write surface.

### Roles
- `author`: primary implementation agent; writes code, runs targeted checks, opens PRs.
- `review`: independent reviewer agent; inspects diffs, runs targeted validation, reviews plan/report/code changes.
- `ops`: monitoring and orchestration agent; watches rung status, review loop state, heartbeats, failures, and artifact publication.

### Worktree Lifecycle Policy
- The system maintains exactly three default persistent role worktrees: `author`, `review`, and `ops`.
- Any additional worktree is ephemeral and must be linked to a bounded task, plan, PR, or experiment.
- Every worktree must have repo-local metadata: path, branch, role/class, created time, last active time, owner/session, dirty status, and cleanup state.
- Ephemeral worktrees must carry a TTL and cleanup policy from creation time.
- Anonymous timestamp worktrees without metadata are not part of the target design.

### Permission Model Alignment
The Claude Code permission model must evolve alongside the worktree lifecycle system. The principle: **the deny list covers catastrophic operations only; domain-specific safety comes from lifecycle tooling and hooks, not permission rules.**

#### Current Permission Model (as of 2026-03-15)
- `Bash(*)` in allow — all bash commands auto-approved by default.
- `defaultMode: "bypassPermissions"` — everything not in deny is auto-approved.
- Deny list covers: `rm -rf /`, `rm -rf ~`, `rm -rf /*`, `sudo`, `mkfs`, `dd`, `diskutil erase`, `shutdown`, `reboot`.
- Git force operations (`push --force`, `reset --hard`, `branch -D`) are **not** denied — Claude's behavioral guardrails (always confirm before destructive git ops) provide the safety layer.
- Interim worktree protection: `rm -rf ../:*` and `rm -rf ../*:*` are denied until the lifecycle system lands.

#### Phased Permission Evolution
| Phase | Worktree Protection | Mechanism |
|-------|--------------------|-----------|
| **Interim** (before PR-3) | `rm -rf ../:*`, `rm -rf ../*:*` hard-denied | User-level deny list |
| **PR-3 lands** | Deny rules removed; PreToolUse hook redirects `rm -rf ../Bid-Euchre*` to `ops.py worktrees prune` | Hook-based guidance (block + suggest) |
| **Mature state** | No worktree-specific deny rules | `ops.py` lifecycle is the guardrail; deny list contains only catastrophic ops |

#### Design Constraints
- The deny list should contain only operations that are dangerous regardless of context (system destruction, privilege escalation, power control).
- Domain-specific safety (worktree cleanup, branch management) should be enforced through hooks and tooling that can educate, suggest alternatives, and be overridden when genuinely needed.
- There is no "prompt" tier in Claude Code permissions — commands are either auto-approved (allow/default) or hard-blocked (deny). Behavioral guardrails (Claude confirming before destructive actions) are the middle tier.

### Planning Contract
- Non-trivial tasks must begin with a planning phase that is logically separate from execution.
- Planning should run as a read-only planner subagent or planner workflow, even if hosted by the `author` role.
- The planner produces a bounded task list, file plan, validation plan, and completion criteria before execution begins.
- Execution may revise the plan only through explicit plan updates recorded in task metadata or plan files.

### Role Capability Policy
- `author` may edit repo files, run targeted tests, run bounded validation, create branches/worktrees, and prepare or open PRs.
- `review` defaults to read, diff, review, and targeted validation only; write access is limited to review artifacts or explicitly delegated fix-up work.
- `ops` may inspect runtime state, refresh indexes, run status commands, and perform bounded orchestration/recovery actions; code edits are off by default unless explicitly delegated.
- Destructive or recovery actions remain approval-gated regardless of role.

### User Role
- The user does not manage day-to-day execution once a task is delegated.
- The user audits diffs, plans, runtime state, and reports in VS Code as needed.
- The user remains the approval boundary for tool adoption outside the repo, terminal preferences, and any destructive recovery actions.

## Existing Assets To Reuse
- `.claude/scripts/claude-worktree.sh` already creates a worktree and starts Claude.
- `.claude/hooks/worktree-guard.sh` and `.claude/hooks/worktree-reminder.sh` already enforce “no edits from main checkout”.
- `scripts/internal/clean_worktrees.sh` already handles stale worktree cleanup.
- `scripts/internal/run_rung.py`, `src/bid_euchre/arc_d_v2/orchestration.py`, and review-loop scripts already expose most of the runtime state the operator surface needs.

## Scope

### In Scope
- Role-based worktree conventions and branch naming.
- tmux-based autonomous session bootstrap.
- VS Code audit workspace and tasks.
- Repo-local status/audit CLI.
- Local audit index for repo runtime artifacts.
- Documentation and rollout procedure.

### Out Of Scope
- Replacing VS Code with a terminal-only workflow.
- Introducing Airflow, Dagster, Prefect, or other heavyweight orchestrators.
- Introducing fully dynamic self-modifying agent behavior.
- Replacing the existing review loop or rung orchestrator state machines.

## Architecture

### Control Surfaces
- Terminal control surface: cmux as the default outer terminal host, with Ghostty as an acceptable fallback host, and tmux as the persistent inner session manager.
- Editor audit surface: VS Code multi-root workspace spanning main checkout plus role worktrees.
- Repo control surface: repo-owned scripts and tasks for bootstrap, status, resume, routing, notification, and cleanup.

### Coordination Model
- Repo-local task and routing metadata remain the system of record.
- cmux provides the default outer workspace host, notifications, and top-level surface targeting.
- In the initial implementation, all active lanes live inside one tmux session hosted by one cmux surface. Per-lane routing therefore targets tmux panes/windows first; cmux is the notification and outer-host layer.
- Human-facing labels such as tmux pane titles may be used for notifications, but canonical routing must not rely on display labels alone.

### State Model
- Worktree state: branch, path, dirty/clean status, last activity.
- Worktree registry state: role/class (`persistent` or `ephemeral`), task/plan/PR linkage, TTL, cleanup status, and active session ownership.
- Session state: active role, current task, governing/session plan link, last checkpoint, and restart metadata.
- Task state: canonical todo list, current `in_progress` item, blocked reasons, validation status, and explicit completion marker.
- Event state: durable event log for review requests, CI failures, heartbeat anomalies, task completions, and other hook-produced operational signals.
- Review queue state: queued review requests, claim status, owner, source lane/task/PR, and completion status.
- Scheduler state: last tick time, last successful health pass, next due checks, and host-level recovery metadata.
- Review state: `.claude/runtime/review_loops/**`, sidecars, PR metadata.
- Plan-review state: `.claude/runtime/plan_reviews/**`.
- Rung/orchestration state: `plans/**/state.json`, `execution_log.jsonl`, heartbeat files, checkpoints.
- Artifact/report state: manifests, latest report dirs, evidence outputs.
- CI state: per-PR check status (pending/pass/fail), failure class, retry count, last push SHA, remediation history.

### Audit Model
- VS Code shows all checkouts and generated audit artifacts.
- `ops.py status` provides a single summary for humans and agents.
- Curated memory stores stable facts, preferences, and workflow invariants that should survive across sessions.
- Local audit index supports query-style retrieval over runtime artifacts and recent operational history.
- Non-lossy context compaction archives older session detail to disk while retaining an artifact index and summary for restart/resume.

### Safety And Recoverability Model
- Autonomous edits and shell operations should be traceable through an operation log.
- Long-running autonomous work should create bounded shadow snapshots so bad edits can be audited and rolled back without relying on fragile terminal history.
- Long-running autonomous processes should be covered by repo-owned watchdogs that detect stalls, exceeded wall-time, and lack of task progress before they become silent failures.
- Every growing runtime structure must have explicit bounds: retries, reminders, snapshots, task list size, and retained archives.
- Session-local cron helpers are not a persistence primitive. Durable monitoring must be driven by repo-owned state plus host-level recovery, not by Claude-session-only timers.

### Scheduling And Monitoring Model
- `ops` is the active scheduler/orchestrator role. It owns periodic health checks, event draining, review-queue maintenance, and escalation.
- `review` is queue-driven with light polling. It should react to durable review requests rather than free-running full-repo scans.
- Hooks produce durable events on disk; they do not themselves become the long-lived scheduler.
- Host-level persistence is provided by OS-level startup/recovery (macOS `launchd` in the first implementation), whose job is to ensure the steward session and `ops` lane are re-established after terminal/session loss.
- Claude-session-only cron facilities may be used as convenience inside a running session, but they must not be the authoritative persistence or scheduling mechanism.

### Context Safety Model
- Agent-loaded context sources are explicitly classified as trusted, generated, or untrusted.
- Generated context, session summaries, and imported notes must pass lightweight prompt-injection or instruction-conflict scanning before being promoted into memory or loaded automatically.
- Skills and curated memory entries require explicit provenance back to repo files or validated operator input.

## Implementation Sequence

### PR-1: Workflow Contract And Bootstrap

**Depends on:** None (first PR in the chain).
**Produces:** Role conventions, bootstrap scripts, session/task metadata schemas, workflow docs. Required by all later PRs.

#### Objectives
- Make the operating model explicit and repo-owned.
- Standardize role names, branch names, worktree locations, and lifecycle rules.
- Provide a single bootstrap command for agent worktree creation.

#### Deliverables
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- `.claude/scripts/start-role-worktree.sh`
- `.claude/scripts/start-agent-role.sh`
- `.claude/runtime/session_metadata/` contract and schema docs
- `.claude/runtime/task_state/` contract and schema docs
- `.claude/runtime/worktree_registry/` contract and schema docs
- `scripts/internal/clean_worktrees.sh` updates if needed for role-named worktrees
- optional `Makefile` targets for bootstrap and cleanup

#### Requirements
- Support fixed role names: `author`, `review`, `ops`.
- Default worktree paths outside the main checkout, sibling to the repo root.
- Role bootstrap must be idempotent: reuse an existing role worktree if present.
- Startup output must tell the agent which role it is assuming and which commands are expected in that role.
- Bootstrap must write role/session metadata so sessions can be resumed cleanly after restart.
- Bootstrap or role startup must initialize task-state tracking for delegated work.
- Bootstrap must classify worktrees as persistent role worktrees or ephemeral task worktrees and write registry metadata immediately.
- The workflow doc must define the capability matrix and approval boundaries for each role.
- The workflow doc must define the planner/executor split for non-trivial tasks.
- The workflow doc must define cleanup states, TTL defaults, and the quarantine/archive flow for stale worktrees.
- The workflow doc must define how gitignored local config or tool state is copied/shared into role worktrees.
- Main checkout remains blocked for editing by existing hooks.

#### Acceptance Criteria
- From the main checkout, one command creates or reuses the three role worktrees.
- A role-specific command can enter a single role worktree and start Claude.
- Each role session can be identified and resumed from repo-local metadata without relying on terminal history.
- Non-trivial delegated tasks create an explicit task record with plan, todo state, validation steps, and completion criteria.
- Ephemeral worktrees are created with explicit metadata and are discoverable as cleanup candidates later.
- Documentation clearly states the role responsibilities and the “one writer per worktree” rule.

### PR-2: Persistent Session Manager, cmux Host, And VS Code Audit Surface

**Depends on:** PR-1 (role worktree conventions and bootstrap scripts).
**Produces:** tmux session layout, cmux host wrapper, VS Code workspace. Required by PR-5 (rollout).

#### Objectives
- Replace fragile ad hoc terminal tabs with a deterministic, resumable session layout.
- Make VS Code the stable audit surface across all active worktrees.
- Establish cmux as the default outer coordination host while preserving tmux as the resumable runtime layer.
- Ensure the steward session, especially the `ops` lane, can be re-established automatically after host/session loss.

#### Deliverables
- `.claude/tmux/agent-ops-session.sh`
- `.claude/tmux/agent-ops-layout.conf` or equivalent repo-owned layout file
- `.claude/cmux/agent-ops-session.sh` or equivalent wrapper around the tmux session
- `.claude/launchd/ensure-steward-session.plist` template or generator script for macOS host-level recovery
- `Bid-Euchre-agent-audit.code-workspace`
- `.vscode/tasks.json`
- docs updates in `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`

#### Requirements
- tmux layout must create windows for `author`, `review`, `ops`, and optional `scratch`.
- Each tmux window must start in the correct worktree.
- The cmux wrapper must start or attach the steward tmux session cleanly and expose stable workspace/surface targets for notifications.
- The initial cmux integration does not require one native cmux surface per lane; per-lane routing may continue to use tmux pane/window targets in the first implementation.
- The repo must provide a documented host-level recovery path that re-establishes the steward session and `ops` lane after process loss or reboot.
- VS Code workspace must include:
  - main checkout
  - author worktree
  - review worktree
  - ops worktree
- VS Code tasks must include:
  - targeted pytest
  - `make check-quiet`
  - `scripts/internal/run_rung.py --status`
  - review-loop state inspection
  - heartbeat inspection

#### Acceptance Criteria
- One repo-owned command starts the tmux session with all role windows and works cleanly when launched from cmux.
- On macOS, one repo-owned launchd template or setup step can re-establish the steward session without manual recreation after host/session loss.
- One repo-owned workspace file opens the audit layout in VS Code.
- The user can inspect all active role worktrees and runtime artifacts from VS Code without moving agent sessions into the VS Code terminal.

### PR-3: Operator CLI

**Depends on:** PR-1 (role conventions, session/task metadata schemas).
**Produces:** `ops.py` CLI, `src/bid_euchre/ops/` package. Required by PR-5 (rollout).

#### Objectives
- Provide a single operator entrypoint for current repo health.
- Reduce manual `rg`, `cat`, and path-hunting for common status questions.
- Provide deterministic recovery guidance when autonomous work hits common failure modes.
- Detect and surface long-running process failures early through lightweight watchdogs rather than manual polling.
- Enable autonomous post-push CI remediation: `ops` polls CI status, classifies failures, and `author` applies bounded safe fixes without human intervention.
- Make lane-aware notifications and routing a first-class behavior: notifications should include a human-facing lane label, but routing and persistence must remain keyed to canonical metadata.
- Make `ops` the scheduler brain for persistent monitoring and make `review` operate from a durable review queue rather than session-only timers.

#### Deliverables
- `scripts/internal/ops.py`
- supporting module(s) under `src/bid_euchre/ops/`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/watchdogs.py`
- `src/bid_euchre/ops/messages.py`
- `src/bid_euchre/ops/notifications.py`
- `src/bid_euchre/ops/events.py`
- `src/bid_euchre/ops/review_queue.py`
- `src/bid_euchre/ops/scheduler.py`
- recovery-template data or helpers under `src/bid_euchre/ops/recovery.py`
- `.claude/hooks/post-task-event.sh` — hook that appends durable operational events
- `.claude/hooks/post-review-request.sh` or equivalent hook/helper that queues review requests durably
- `.claude/hooks/pre-worktree-cleanup.sh` — PreToolUse hook that detects direct `rm -rf` on worktree directories and redirects to `ops.py worktrees prune`
- unit tests under `tests/unit/`
- optional `Makefile` targets like `make ops-status`
- **Permission migration:** Remove interim `rm -rf ../:*` deny rules from user settings once the PreToolUse hook and `ops.py worktrees prune` are validated
- `src/bid_euchre/ops/ci.py` — CI status polling, failure classification, and remediation policy
- `tests/unit/test_ops_ci.py` — CI failure classification and remediation policy tests
- `tests/unit/test_ops_messages.py` — routing and message transport tests
- `tests/unit/test_ops_notifications.py` — lane-aware notification formatting tests
- `tests/unit/test_ops_events.py` — durable event append/drain tests
- `tests/unit/test_ops_review_queue.py` — review queue enqueue/claim/complete tests
- `tests/unit/test_ops_scheduler.py` — scheduler tick, due-check, and recovery tests

#### Commands
- `ops.py status`
- `ops.py message --to <role>`
- `ops.py notify --to <role>`
- `ops.py events`
- `ops.py events drain`
- `ops.py review-queue`
- `ops.py review-queue enqueue`
- `ops.py review-queue claim`
- `ops.py tick`
- `ops.py daemon`
- `ops.py worktrees`
- `ops.py worktrees prune`
- `ops.py worktrees quarantine`
- `ops.py worktrees archive`
- `ops.py reviews`
- `ops.py rungs`
- `ops.py failures`
- `ops.py artifacts`
- `ops.py resume --role <role>`
- `ops.py health`
- `ops.py schedule`
- `ops.py recover`
- `ops.py watchdogs`
- `ops.py ci` — poll CI status for a PR, classify failures, suggest remediation
- `ops.py ci --pr <N>` — check specific PR
- `ops.py ci --remediate` — apply bounded safe fixes (lint/format only by default)

#### CI Failure Classes

| Class | Auto-remediable? | Action |
|-------|-----------------|--------|
| **lint/format** | Yes | `ruff check --fix && ruff format`, re-push |
| **deterministic test** | Yes (bounded) | Author reads failure, applies targeted fix, runs Tier 1 validation, re-pushes |
| **missing config/artifact** | Yes (bounded) | Author adds missing file or config, validates, re-pushes |
| **flaky/external** | No | Retry once; if still failing, escalate to human |
| **infra/auth/tooling** | No | Log and escalate — not a code problem |
| **risky/destructive** | No | Never auto-remediate; always escalate |

#### Bounded CI Remediation Policy

- `ops` polls `gh pr checks` after each push and classifies failures.
- For auto-remediable failures (lint/format, deterministic test, missing config):
  - `author` applies only the minimal fix in the PR worktree.
  - `author` runs targeted validation (Tier 1) before re-pushing.
  - Maximum 3 remediation attempts per PR. After 3, escalate.
- For non-remediable failures (flaky, infra, risky):
  - Log the failure class and details.
  - Escalate immediately — do not retry or attempt workarounds.
- Re-push must not include unrelated changes. Fix scope = failure scope.
- All remediation actions are logged in CI state for auditability.

#### Data Sources
- `git worktree list`
- `.claude/runtime/worktree_registry/**`
- `.claude/runtime/events/**`
- `.claude/runtime/review_queue/**`
- `.claude/runtime/scheduler/**`
- `.claude/runtime/review_loops/**/state.json`
- `.claude/runtime/plan_reviews/**/state.json`
- `.claude/runtime/task_state/**`
- `plans/**/state.json`
- `plans/**/execution_log.jsonl`
- heartbeat files
- evidence/report manifests
- process metadata and watchdog threshold configuration
- tmux pane/window targets and cmux workspace/surface metadata when available

#### Watchdog Coverage
- rung orchestrators with stale or missing heartbeats
- review loops that stop changing state for too long
- review-queue items that remain unclaimed or unresolved too long
- long-running commands that exceed configured wall-time bounds
- task sessions that remain `in_progress` without evidence of forward progress
- abandoned dirty worktrees associated with inactive sessions
- worktree count/age drift beyond configured limits
- detached or metadata-missing worktrees that cannot be safely classified
- PRs stuck in CI pending or failure state beyond configured thresholds
- CI remediation loops that exceed retry caps without resolution

#### Watchdog Behavior
- Default behavior is detect, classify, log, and recommend a bounded recovery step.
- Auto-remediation is opt-in and limited to explicitly safe actions.
- Watchdogs must not silently kill or mutate important processes by default.
- Worktree cleanup defaults to dry-run reporting first; removal requires clean-state or explicit quarantine/archive handling.
- Notification and transport helpers must distinguish canonical role/worktree identity from human-facing display labels such as tmux pane titles.
- `ops` periodic monitoring should be implemented as a durable scheduler loop (`tick`/`daemon`) backed by repo-local state, not by session-only cron.
- `review` periodic behavior should be queue-driven with bounded polling rather than continuous broad scans.

#### Worktree Cleanup Policy
- Persistent role worktrees are never auto-pruned.
- Ephemeral worktrees may be `idle`, `stale`, `quarantined`, `ready_to_remove`, or `archived`.
- Clean ephemeral worktrees with no active session and expired TTL may be removed automatically only in explicitly enabled cleanup mode.
- Dirty or detached worktrees must go through quarantine or archive flow before removal.
- Cleanup output must always include the reason a worktree qualified for prune/quarantine/archive.

#### Output Requirements
- Human-readable summary by default.
- JSON output mode for agent consumption.
- Non-zero exit when requested checks find blocking failures or stale runtime state.
- Health output must cover stale heartbeats, stuck review loops, abandoned dirty worktrees, and missing or stale indexes.
- Health and scheduler output must show whether the event queue, review queue, and host-level recovery path are healthy.
- Watchdog output must identify which process or session is unhealthy, why it tripped, which threshold fired, and the next bounded recovery action.
- Recovery output must classify common failures and recommend the next bounded action instead of generic retry loops.
- Worktree output must distinguish persistent role worktrees from ephemeral task worktrees and show cleanup candidacy clearly.
- Notification output must include a human-facing lane label without treating that label as the canonical routing identity.

#### Acceptance Criteria
- `ops.py status` answers “what is running, what is blocked, what failed, and what needs attention next?” in one command.
- The CLI works from the main checkout and any worktree.
- Agents can use JSON mode without custom parsing hacks.
- Scheduled health checks can run unattended and produce actionable summaries without human triage first.
- `ops` can recover its own periodic monitoring after session restart by reading scheduler state rather than relying on re-entered cron commands.
- `review` can resume from a durable review queue without rescanning the entire repo manually.
- Common failure classes have deterministic recovery paths surfaced through the operator CLI.
- Watchdogs reliably detect stalled or overlong autonomous processes without introducing unsafe default auto-kill behavior.
- Worktree sprawl is bounded through explicit lifecycle states, safe prune flows, and visibility into stale/abandoned worktrees.
- Routing and notification events are recorded in repo-local state rather than existing only in terminal transport.
- Direct `rm -rf` on worktree directories is intercepted by PreToolUse hook and redirected to `ops.py worktrees prune`.
- Interim `rm -rf ../:*` deny rules can be safely removed from user permission settings after hook validation.

### PR-4: Local Audit Index

**Depends on:** PR-3 (`src/bid_euchre/ops/` package and status aggregation).
**Produces:** Curated memory, audit index, session compaction. Required by PR-5 (rollout).

#### Objectives
- Give agents and the user fast retrieval over operational state and history.
- Minimize repeated full-file rereads of plans, logs, reports, and sidecars.
- Separate durable small-memory facts from large searchable operational history.
- Preserve old session detail without forcing it to remain in the live prompt/context window.

#### Deliverables
- `scripts/internal/build_curated_memory.py`
- `scripts/internal/build_audit_index.py`
- `scripts/internal/compact_session_context.py`
- module(s) under `src/bid_euchre/ops/memory.py`
- module(s) under `src/bid_euchre/ops/index.py`
- module(s) under `src/bid_euchre/ops/compaction.py`
- curated memory storage under `.claude/runtime/curated_memory/`
- index storage under `.claude/runtime/audit_index/`
- archived session context under `.claude/runtime/session_archive/`
- query entrypoint, either in `ops.py` or as a companion command
- tests for indexing and query behavior

#### Memory Layers
- Curated memory: stable repo facts, user preferences, workflow invariants, role instructions, and approved operational shortcuts.
- Audit index: searchable operational history over runtime artifacts, review outputs, checkpoints, and reports.
- Session archive: non-lossy compaction target containing older observations, operation summaries, and touched-artifact indexes for restart/resume.

#### Indexed Sources
- durable event log
- review queue artifacts
- review-loop sidecars and states
- plan-review sidecars and states
- rung `state.json`
- `execution_log.jsonl`
- `checkpoints.md`
- evidence manifests
- latest report metadata

#### Query Use Cases
- “What failed in the last rung run?”
- “Which worktree owns the active implementation branch?”
- “What review findings are still open?”
- “Which review requests are queued or stale?”
- “What events did ops process in the last hour?”
- “Which rung is blocked and why?”
- “What artifacts were produced most recently?”

#### Technology Choice
- SQLite with FTS is preferred.
- DuckDB is acceptable only if there is a clear need for analytical queries not served by SQLite.

#### Acceptance Criteria
- Index rebuild is fast and idempotent.
- Curated memory updates are explicit, provenance-backed, and separate from bulk indexing.
- Session compaction preserves a path back to archived detail and a touched-artifact index, rather than replacing old context with an opaque summary.
- Queries return source-backed answers with file references.
- Agents can answer routine operational questions without re-reading large trees.

### PR-5: Rollout, Agent Profiles, And Validation

**Depends on:** PR-1 through PR-4 (all infrastructure must be in place before rollout).
**Produces:** Validated end-to-end workflow, promoted skills, context-safety validation.

#### Objectives
- Move from partial manual adoption to the default operating model.
- Validate the end-to-end flow using real repo tasks.
- Capture repeated successful workflows as reusable skills instead of rediscovering them.
- Ensure auto-loaded context is safe to consume at high autonomy.

#### Deliverables
- rollout guide in `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- optional role-specific startup prompts or agent docs under `.claude/agents/`
- context-safety scan script for memory/summary/skill promotion
- skill-promotion workflow doc or helper script under `.claude/skills/` or `scripts/internal/`
- shadow snapshot/rollback workflow docs and helper script
- validation notes in a follow-up session plan or report

#### Rollout Steps
- Pilot on one bounded implementation task.
- Pilot on one plan review or report review task.
- Pilot on one rung-monitoring task.
- Validate handoff behavior across restarts and across multiple active worktrees.
- Promote at least one repeated multi-step workflow into a reusable skill.
- Validate that generated summaries or notes are scanned before auto-loading or memory promotion.
- Validate that shadow snapshots and operation logs are sufficient to audit and recover from a bad autonomous edit sequence.
- Make the workflow the documented default once all pilots pass.

#### Acceptance Criteria
- The user can delegate a task, open VS Code, and audit progress without sharing a checkout with the autonomous agent.
- An agent can start, continue, review, and monitor work autonomously from dedicated role worktrees.
- Repeated successful workflows are captured as skills or documented operator procedures.
- High-autonomy context loading has a defined safety boundary and validation path.
- Autonomous work is reversible through documented snapshot/recovery mechanisms.
- Cleanup and recovery are documented and tested.

## Detailed File Plan
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — canonical workflow doc for the new operating model.
- `.claude/scripts/start-role-worktree.sh` — role-aware worktree bootstrap and reuse logic.
- `.claude/scripts/start-agent-role.sh` — starts Claude in the correct role worktree with expected instructions.
- `.claude/tmux/agent-ops-session.sh` — tmux bootstrap for persistent multi-role sessions.
- `.claude/tmux/agent-ops-layout.conf` — stable tmux window and pane layout.
- `.claude/launchd/ensure-steward-session.plist` — macOS host-level recovery template for steward session bootstrap.
- `Bid-Euchre-agent-audit.code-workspace` — multi-root audit workspace for VS Code.
- `.vscode/tasks.json` — audit/status/validation tasks.
- `scripts/internal/ops.py` — top-level operator CLI.
- `src/bid_euchre/ops/__init__.py` — package root for operator helpers.
- `src/bid_euchre/ops/status.py` — status aggregation logic.
- `src/bid_euchre/ops/worktrees.py` — worktree registry, classification, TTL, and cleanup policy helpers.
- `src/bid_euchre/ops/events.py` — durable event append/drain helpers.
- `src/bid_euchre/ops/review_queue.py` — review queue state and claim logic.
- `src/bid_euchre/ops/scheduler.py` — periodic scheduler loop and due-check logic.
- `src/bid_euchre/ops/memory.py` — curated memory ingestion, validation, and query helpers.
- `.claude/hooks/post-task-event.sh` — durable event producer hook for task completions/failures.
- `.claude/hooks/post-review-request.sh` — durable review-request enqueue hook/helper.
- `.claude/hooks/pre-worktree-cleanup.sh` — PreToolUse hook redirecting direct `rm -rf` on worktree dirs to `ops.py worktrees prune`.
- `src/bid_euchre/ops/watchdogs.py` — watchdog rules for long-running process health and stall detection.
- `src/bid_euchre/ops/ci.py` — CI status polling, failure classification, remediation policy, and retry tracking.
- `src/bid_euchre/ops/recovery.py` — failure classification and bounded recovery templates.
- `src/bid_euchre/ops/compaction.py` — session compaction and archive metadata helpers.
- `src/bid_euchre/ops/index.py` — audit index build/query logic.
- `tests/unit/test_ops_status.py` — CLI/status tests.
- `tests/unit/test_ops_worktrees.py` — worktree lifecycle, prune, quarantine, and archive tests.
- `tests/unit/test_ops_events.py` — durable event log tests.
- `tests/unit/test_ops_review_queue.py` — review queue tests.
- `tests/unit/test_ops_scheduler.py` — scheduler/due-check/recovery tests.
- `tests/unit/test_ops_memory.py` — curated memory tests.
- `tests/unit/test_ops_watchdogs.py` — watchdog threshold and stall-detection tests.
- `tests/unit/test_ops_ci.py` — CI failure classification, remediation policy, and retry cap tests.
- `tests/unit/test_ops_recovery.py` — recovery template tests.
- `tests/unit/test_ops_compaction.py` — compaction/archive tests.
- `tests/unit/test_ops_index.py` — audit index tests.

## User-Owned Tasks
- Install cmux and use it as the default steward host (Ghostty remains an acceptable fallback).
- Install and adopt tmux.
- Decide whether to keep the current shell profile or add aliases/launchers.
- Confirm that `cmux ping`, `cmux notify`, and the Claude notification hook work from inside tmux.
- Install or enable the repo-provided `launchd` recovery job if host-level persistence is desired on macOS.

## Agent-Owned Tasks
- Implement all repo-local scripts, workspace files, tasks, docs, and CLI surfaces.
- Reuse existing worktree hooks instead of replacing them.
- Add tests for all new repo-local behavior.
- Implement scheduled health checks, curated memory, and safety scanning as repo-owned capabilities.
- Implement durable event production, review queueing, and scheduler state as repo-owned capabilities.
- Implement task-state tracking, compaction, recovery templates, shadow snapshot helpers, and watchdogs as repo-owned capabilities.
- Implement worktree lifecycle tracking, TTL policy, and safe cleanup as repo-owned capabilities.
- Validate the workflow through bounded pilots before making it default.

## Execution Risks

The following capabilities have no prior repo precedent and carry higher implementation risk:

- **Context safety scanning (PR-5):** Prompt-injection and instruction-conflict detection for auto-loaded content. No existing scanner to build on; start with a minimal keyword/pattern scanner and iterate.
- **Shadow snapshots (PR-5):** Filesystem snapshots for rollback of autonomous edits. Must not conflict with git state or worktree lifecycle. Consider lightweight git stash/branch-based approach before building custom snapshot tooling.
- **Curated memory system (PR-4):** Provenance-tracked memory distinct from MEMORY.md. Risk of duplicating or conflicting with the existing auto-memory system. Must define clear boundary: curated memory stores operator-validated facts; auto-memory remains the conversation-scoped system.
- **SQLite audit index (PR-4):** Introduces a database dependency for operational state. Must remain optional — the workflow should degrade gracefully if the index is stale or absent.
- **CI remediation loop (PR-3):** Autonomous CI fix-and-repush could introduce scope creep or unbounded retries. Mitigated by strict failure classification, retry caps (max 3), and escalation for non-remediable classes. The `risky/destructive` class is never auto-remediated.
- **Host-level persistence (PR-2/PR-3):** `launchd` recovery plus scheduler state must not create duplicate steward sessions or duplicate monitor loops. Idempotent bootstrap and lock/state checks are required.

## Risks And Mitigations
- Role drift between worktrees.
  - Mitigation: role-aware bootstrap, docs, and visible role banners in startup scripts.
- cmux transport diverging from repo task state.
  - Mitigation: treat cmux as transport and notification only; record assignments, handoffs, and escalations in repo-local metadata/logs.
- tmux pane titles disappearing or becoming stale.
  - Mitigation: use pane titles only for display; route by canonical role/worktree metadata and tmux targets.
- Too much duplication with existing hooks/scripts.
  - Mitigation: wrap and extend current `.claude/scripts/claude-worktree.sh` instead of replacing it.
- tmux or VS Code workflow becoming mandatory for all contributors.
  - Mitigation: document it as the recommended autonomous-agent workflow, not a universal contributor requirement.
- Audit index going stale.
  - Mitigation: idempotent rebuild command plus optional refresh on `ops.py status`.
- Curated memory accumulating bad or injected instructions.
  - Mitigation: provenance-backed updates, explicit promotion path, and context-safety scanning before auto-load.
- Autonomous sessions becoming too permissive.
  - Mitigation: role capability matrix plus approval gates for destructive or recovery actions.
- Long-running autonomous sessions losing critical detail through over-compaction.
  - Mitigation: non-lossy compaction with archived context paths and touched-artifact indexes.
- Recovery logic becoming an unbounded retry loop.
  - Mitigation: classify failures, cap retries, and surface explicit next-step guidance.
- Watchdogs producing noisy false positives.
  - Mitigation: per-process thresholds, observe-only rollout first, and bounded actions that default to notify rather than mutate.
- Review queue becoming a dumping ground without ownership.
  - Mitigation: claim/owner model, stale-item watchdogs, and explicit completion or escalation states.
- Cleanup accidentally removing valuable in-progress worktrees.
  - Mitigation: persistent vs ephemeral classification, dry-run-first cleanup, quarantine for dirty worktrees, and no default deletion of role worktrees.
- CI remediation introducing unrelated changes or scope creep.
  - Mitigation: fix scope = failure scope; re-push must not include unrelated changes; Tier 1 validation before each re-push.
- CI remediation becoming an unbounded retry loop.
  - Mitigation: max 3 attempts per PR; non-remediable classes escalate immediately; all actions logged.
- Added tooling without operational adoption.
  - Mitigation: staged rollout with acceptance checks after each PR.

## Verification Strategy
- Unit tests for `ops.py` parsing and state aggregation.
- Unit tests for role metadata and recovery logic.
- Unit tests for routing and lane-aware notification formatting.
- Unit tests for durable event append/drain, review queue claim/complete, and scheduler tick/recovery behavior.
- Unit tests for worktree registry classification, TTL handling, prune eligibility, and quarantine behavior.
- Unit tests for curated memory validation and promotion.
- Unit tests for audit index build/query behavior.
- Unit tests for watchdog thresholds, stale-heartbeat detection, and no-progress detection.
- Unit tests for task-state progression and explicit completion handling.
- Unit tests for CI failure classification across all 6 failure classes.
- Unit tests for remediation policy (retry caps, escalation triggers, scope constraints).
- Unit tests for non-lossy compaction and archive lookup.
- Manual smoke test of role bootstrap, cmux host startup, and tmux session creation.
- Manual smoke test that notifications can be triggered from inside tmux under cmux.
- Manual smoke test that `launchd` or equivalent host-level recovery re-establishes the steward session and `ops` lane after process loss.
- Manual smoke test of worktree prune dry-run, quarantine, and archive flows.
- Manual smoke test of VS Code workspace opening all intended roots.
- Manual smoke test of scheduled health checks and stuck-session detection.
- Manual smoke test that a queued review request survives session restart and is claimed by `review`.
- Manual smoke test of long-running process watchdogs against intentionally stalled sessions.
- Manual smoke test of snapshot-based rollback and recovery after an intentionally bad edit sequence.
- Manual smoke test of CI remediation: introduce a lint failure, push, verify `ops.py ci` classifies it correctly and `author` auto-fixes within retry cap.
- Pilot tasks that exercise:
  - implementation flow
  - review flow
  - rung monitoring flow

## Success Criteria
- The default path for autonomous work is: bootstrap role worktrees -> start tmux session inside cmux -> delegate tasks to agents -> audit in VS Code.
- No autonomous writing occurs from the main checkout.
- The user no longer needs to manage multiple ad hoc terminals in a shared checkout or manually relay routine notifications between agents.
- A single repo-owned status surface answers the operational questions that currently require manual inspection.
- Autonomous work is resumable, explicitly tracked, and recoverable without relying on implicit terminal context.
- `ops` monitoring survives session loss through host-level recovery plus repo-local scheduler state, and `review` resumes from a durable queue rather than a session-only timer.

## Outcome
<!-- Filled after implementation -->
- PR: deferred (PRs 1-2 sequenced after Phase 4a; PRs 3-5 per original triggers)
- Notes:
  - Planning-only session (2026-03-15). Existing Claude worktree hooks and helper scripts should be treated as implementation inputs, not replaced blindly.
  - Review session (2026-03-16): Compatibility analysis confirmed PRs 1-2 low-risk during FULL backfill. User-side setup completed (Ghostty, tmux, permissions verified, 37 stale worktrees cleaned). Four design decisions resolved. Sequencing revised: Phase 4a first, then PR-1, then PR-2. CI remediation loop added to PR-3 scope.
  - Setup refinement (2026-03-17): cmux is now treated as the default outer coordination host and tmux as the persistence layer. Live setup confirmed the initial topology is one cmux surface hosting one tmux session, so per-lane routing remains tmux-targeted while notifications use human-facing display labels such as pane titles.
  - Scheduling refinement (2026-03-18): Session-only cron helpers are not treated as durable persistence. The plan now assumes hook-produced durable events, queue-driven review, `ops`-owned scheduler state, and host-level recovery (`launchd` on macOS) for monitoring persistence.
