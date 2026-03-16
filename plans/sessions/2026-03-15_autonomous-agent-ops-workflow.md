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
> **Context:** Arc D v2 R0-R2 QUICK complete, R3 engine in progress, FULL backfill running. Browser-game initiative ACTIVE but not yet started.

This plan is a **staged enabling track**, not a monolithic blocker. It should not pause Arc D and should not be deferred until after everything else. The thin slice lands right after R3 QUICK; the heavier infrastructure lands as browser-game creates real multi-agent coordination pressure.

### Immediate (now, during Arc D sprint)

Adopt **user-side workflow changes only** — no repo PRs required:
- Ghostty (or equivalent) as primary terminal host
- `tmux` for persistent sessions
- Role-based worktrees (informal adoption of `author`/`review`/`ops` convention)
- VS Code as audit surface for diffs, plans, and runtime artifacts
- **Permission model redesign:** Switch from allowlist (`Bash(command:*)` per command) to denylist (`Bash(*)` + targeted deny). Add interim `rm -rf ../:*` and `rm -rf ../*:*` deny rules to protect worktree directories until lifecycle tooling lands.

These reduce operational pain immediately and require no shared-repo changes.

### After R3 QUICK first stable pass → PRs 1-2

Land the **lightweight workflow scaffolding**:
- **PR-1:** Worktree/bootstrap contract, role conventions, session/task metadata
- **PR-2:** tmux launcher, VS Code audit workspace and tasks

These are low-risk (mostly tooling/docs) but change shared repo behavior, so they should not land in the middle of the active research loop.

### Before browser-game backend/frontend parallelism → PRs 3-4

Land the **operator CLI and memory/index layer**:
- **PR-3:** `ops.py` CLI, health checks, watchdogs, recovery templates
- **PR-4:** Curated memory, audit index, session compaction/archive

These are cross-cutting and will be easier to design once Arc D runtime artifacts and operational pain points are stable. The browser-game initiative is exactly the kind of work that benefits most — it involves parallel tracks (domain engine, backend API, frontend product, replay/export, deployment) that create real multi-agent coordination pressure.

### Before hosted-play becomes externally exposed → PR-5

Land the **higher-autonomy safeguards**:
- **PR-5:** Rollout validation, agent profiles, context safety, shadow snapshots

This must be in place before the hosted product is operationally important or externally exposed.

### Summary Sequence

| Step | Trigger | Deliverables |
|------|---------|-------------|
| 1 | Now | User-side workflow (Ghostty, tmux, role worktrees, VS Code, permission denylist redesign) |
| 2 | R3 QUICK stable pass | PRs 1-2 (scaffold) |
| 3 | Browser-game Phase 0/1/2 starts | Browser-game benefits from improved agent workflow |
| 4 | Browser-game enters backend/frontend parallelism | PRs 3-4 (operator CLI, memory/index) |
| 5 | Before hosted-play external exposure | PR-5 (rollout, safety, recovery) |

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
- Terminal control surface: Ghostty + tmux for persistent autonomous sessions.
- Editor audit surface: VS Code multi-root workspace spanning main checkout plus role worktrees.
- Repo control surface: repo-owned scripts and tasks for bootstrap, status, resume, and cleanup.

### State Model
- Worktree state: branch, path, dirty/clean status, last activity.
- Worktree registry state: role/class (`persistent` or `ephemeral`), task/plan/PR linkage, TTL, cleanup status, and active session ownership.
- Session state: active role, current task, governing/session plan link, last checkpoint, and restart metadata.
- Task state: canonical todo list, current `in_progress` item, blocked reasons, validation status, and explicit completion marker.
- Review state: `.claude/runtime/review_loops/**`, sidecars, PR metadata.
- Plan-review state: `.claude/runtime/plan_reviews/**`.
- Rung/orchestration state: `plans/**/state.json`, `execution_log.jsonl`, heartbeat files, checkpoints.
- Artifact/report state: manifests, latest report dirs, evidence outputs.

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

### PR-2: Persistent Session Manager And VS Code Audit Surface

**Depends on:** PR-1 (role worktree conventions and bootstrap scripts).
**Produces:** tmux session layout, VS Code workspace. Required by PR-5 (rollout).

#### Objectives
- Replace fragile ad hoc terminal tabs with a deterministic, resumable session layout.
- Make VS Code the stable audit surface across all active worktrees.

#### Deliverables
- `.claude/tmux/agent-ops-session.sh`
- `.claude/tmux/agent-ops-layout.conf` or equivalent repo-owned layout file
- `Bid-Euchre-agent-audit.code-workspace`
- `.vscode/tasks.json`
- docs updates in `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`

#### Requirements
- tmux layout must create windows for `author`, `review`, `ops`, and optional `scratch`.
- Each tmux window must start in the correct worktree.
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
- One repo-owned command starts the tmux session with all role windows.
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

#### Deliverables
- `scripts/internal/ops.py`
- supporting module(s) under `src/bid_euchre/ops/`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/watchdogs.py`
- recovery-template data or helpers under `src/bid_euchre/ops/recovery.py`
- `.claude/hooks/pre-worktree-cleanup.sh` — PreToolUse hook that detects direct `rm -rf` on worktree directories and redirects to `ops.py worktrees prune`
- unit tests under `tests/unit/`
- optional `Makefile` targets like `make ops-status`
- **Permission migration:** Remove interim `rm -rf ../:*` deny rules from user settings once the PreToolUse hook and `ops.py worktrees prune` are validated

#### Commands
- `ops.py status`
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

#### Data Sources
- `git worktree list`
- `.claude/runtime/worktree_registry/**`
- `.claude/runtime/review_loops/**/state.json`
- `.claude/runtime/plan_reviews/**/state.json`
- `.claude/runtime/task_state/**`
- `plans/**/state.json`
- `plans/**/execution_log.jsonl`
- heartbeat files
- evidence/report manifests
- process metadata and watchdog threshold configuration

#### Watchdog Coverage
- rung orchestrators with stale or missing heartbeats
- review loops that stop changing state for too long
- long-running commands that exceed configured wall-time bounds
- task sessions that remain `in_progress` without evidence of forward progress
- abandoned dirty worktrees associated with inactive sessions
- worktree count/age drift beyond configured limits
- detached or metadata-missing worktrees that cannot be safely classified

#### Watchdog Behavior
- Default behavior is detect, classify, log, and recommend a bounded recovery step.
- Auto-remediation is opt-in and limited to explicitly safe actions.
- Watchdogs must not silently kill or mutate important processes by default.
- Worktree cleanup defaults to dry-run reporting first; removal requires clean-state or explicit quarantine/archive handling.

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
- Watchdog output must identify which process or session is unhealthy, why it tripped, which threshold fired, and the next bounded recovery action.
- Recovery output must classify common failures and recommend the next bounded action instead of generic retry loops.
- Worktree output must distinguish persistent role worktrees from ephemeral task worktrees and show cleanup candidacy clearly.

#### Acceptance Criteria
- `ops.py status` answers “what is running, what is blocked, what failed, and what needs attention next?” in one command.
- The CLI works from the main checkout and any worktree.
- Agents can use JSON mode without custom parsing hacks.
- Scheduled health checks can run unattended and produce actionable summaries without human triage first.
- Common failure classes have deterministic recovery paths surfaced through the operator CLI.
- Watchdogs reliably detect stalled or overlong autonomous processes without introducing unsafe default auto-kill behavior.
- Worktree sprawl is bounded through explicit lifecycle states, safe prune flows, and visibility into stale/abandoned worktrees.
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
- `Bid-Euchre-agent-audit.code-workspace` — multi-root audit workspace for VS Code.
- `.vscode/tasks.json` — audit/status/validation tasks.
- `scripts/internal/ops.py` — top-level operator CLI.
- `src/bid_euchre/ops/__init__.py` — package root for operator helpers.
- `src/bid_euchre/ops/status.py` — status aggregation logic.
- `src/bid_euchre/ops/worktrees.py` — worktree registry, classification, TTL, and cleanup policy helpers.
- `src/bid_euchre/ops/memory.py` — curated memory ingestion, validation, and query helpers.
- `.claude/hooks/pre-worktree-cleanup.sh` — PreToolUse hook redirecting direct `rm -rf` on worktree dirs to `ops.py worktrees prune`.
- `src/bid_euchre/ops/watchdogs.py` — watchdog rules for long-running process health and stall detection.
- `src/bid_euchre/ops/recovery.py` — failure classification and bounded recovery templates.
- `src/bid_euchre/ops/compaction.py` — session compaction and archive metadata helpers.
- `src/bid_euchre/ops/index.py` — audit index build/query logic.
- `tests/unit/test_ops_status.py` — CLI/status tests.
- `tests/unit/test_ops_worktrees.py` — worktree lifecycle, prune, quarantine, and archive tests.
- `tests/unit/test_ops_memory.py` — curated memory tests.
- `tests/unit/test_ops_watchdogs.py` — watchdog threshold and stall-detection tests.
- `tests/unit/test_ops_recovery.py` — recovery template tests.
- `tests/unit/test_ops_compaction.py` — compaction/archive tests.
- `tests/unit/test_ops_index.py` — audit index tests.

## User-Owned Tasks
- Install Ghostty or confirm another terminal host.
- Install and adopt tmux.
- Decide whether to keep the current shell profile or add aliases/launchers.
- Decide whether Ghostty becomes the default terminal or only the autonomous-agent terminal.

## Agent-Owned Tasks
- Implement all repo-local scripts, workspace files, tasks, docs, and CLI surfaces.
- Reuse existing worktree hooks instead of replacing them.
- Add tests for all new repo-local behavior.
- Implement scheduled health checks, curated memory, and safety scanning as repo-owned capabilities.
- Implement task-state tracking, compaction, recovery templates, shadow snapshot helpers, and watchdogs as repo-owned capabilities.
- Implement worktree lifecycle tracking, TTL policy, and safe cleanup as repo-owned capabilities.
- Validate the workflow through bounded pilots before making it default.

## Execution Risks

The following capabilities have no prior repo precedent and carry higher implementation risk:

- **Context safety scanning (PR-5):** Prompt-injection and instruction-conflict detection for auto-loaded content. No existing scanner to build on; start with a minimal keyword/pattern scanner and iterate.
- **Shadow snapshots (PR-5):** Filesystem snapshots for rollback of autonomous edits. Must not conflict with git state or worktree lifecycle. Consider lightweight git stash/branch-based approach before building custom snapshot tooling.
- **Curated memory system (PR-4):** Provenance-tracked memory distinct from MEMORY.md. Risk of duplicating or conflicting with the existing auto-memory system. Must define clear boundary: curated memory stores operator-validated facts; auto-memory remains the conversation-scoped system.
- **SQLite audit index (PR-4):** Introduces a database dependency for operational state. Must remain optional — the workflow should degrade gracefully if the index is stale or absent.

## Risks And Mitigations
- Role drift between worktrees.
  - Mitigation: role-aware bootstrap, docs, and visible role banners in startup scripts.
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
- Cleanup accidentally removing valuable in-progress worktrees.
  - Mitigation: persistent vs ephemeral classification, dry-run-first cleanup, quarantine for dirty worktrees, and no default deletion of role worktrees.
- Added tooling without operational adoption.
  - Mitigation: staged rollout with acceptance checks after each PR.

## Verification Strategy
- Unit tests for `ops.py` parsing and state aggregation.
- Unit tests for role metadata and recovery logic.
- Unit tests for worktree registry classification, TTL handling, prune eligibility, and quarantine behavior.
- Unit tests for curated memory validation and promotion.
- Unit tests for audit index build/query behavior.
- Unit tests for watchdog thresholds, stale-heartbeat detection, and no-progress detection.
- Unit tests for task-state progression and explicit completion handling.
- Unit tests for non-lossy compaction and archive lookup.
- Manual smoke test of role bootstrap and tmux session creation.
- Manual smoke test of worktree prune dry-run, quarantine, and archive flows.
- Manual smoke test of VS Code workspace opening all intended roots.
- Manual smoke test of scheduled health checks and stuck-session detection.
- Manual smoke test of long-running process watchdogs against intentionally stalled sessions.
- Manual smoke test of snapshot-based rollback and recovery after an intentionally bad edit sequence.
- Pilot tasks that exercise:
  - implementation flow
  - review flow
  - rung monitoring flow

## Success Criteria
- The default path for autonomous work is: bootstrap role worktrees -> start tmux session -> delegate tasks to agents -> audit in VS Code.
- No autonomous writing occurs from the main checkout.
- The user no longer needs to manage multiple ad hoc terminals in a shared checkout.
- A single repo-owned status surface answers the operational questions that currently require manual inspection.
- Autonomous work is resumable, explicitly tracked, and recoverable without relying on implicit terminal context.

## Outcome
<!-- Filled after implementation -->
- PR: deferred
- Notes: Planning-only session. Existing Claude worktree hooks and helper scripts should be treated as implementation inputs, not replaced blindly.
