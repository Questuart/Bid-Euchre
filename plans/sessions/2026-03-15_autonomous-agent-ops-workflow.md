# Autonomous Agent Ops Workflow
**Date:** 2026-03-15
**Goal:** Move to a fully autonomous multi-agent operating model where agents execute work end-to-end in isolated worktrees and persistent terminal sessions, while the user audits progress, diffs, artifacts, and status primarily through VS Code.

> **Scope note:** This plan has governing-initiative scale (5 PRs, new `src/` package, new CLI) but is filed as a session plan because it is infrastructure/tooling work that does not require the checkpoint/sub-plan governance designed for research lineages. If scope grows beyond 5 PRs, promote to a governed initiative under `plans/agent_ops/`.

## Plan
- PR-1: Establish the steward lane model, bootstrap scripts, and documentation for lane/worktree identity using the existing Claude worktree hook system as the foundation.
- PR-2: Add a repo-owned steward session launcher and VS Code audit workspace so autonomous sessions can be started consistently and audited from a stable editor surface, while shifting review inspection from local loop state to GitHub/CI outcomes.
- PR-3: Add a lightweight operator CLI (`ops.py`) that summarizes worktree health, GitHub/CI review outcomes, local plan-review status, rung state, heartbeats, watchdog status for long-running processes, and latest artifacts from one command.
- PR-4: Add a two-layer memory system: small curated memory for stable operator facts plus a local audit index over execution logs, CI/review outcomes, checkpoints, and manifests for searchable history.
- PR-5: Roll out the autonomous workflow in stages, validate online-first PR review plus local `/review-plan`, add a canonical lane-activity / current-work surface, add skill-promotion, issue-triage, and context-safety workflows, and retire ad hoc “multiple terminals in one checkout” usage.

## Current State

As of 2026-03-19, future agents should treat the following as ground truth:

- The canonical execution identity is the **steward lane model** (`lane_id`), not the older three-role-only model.
- The default steward baseline is a multi-lane tmux session with persistent lanes `author-a` through `author-d`, `review`, `ops`, and `scratch`.
- `author`, `review`, and `ops` remain useful **role classes**, but the concrete execution units are lanes/worktrees.
- PR-1 through PR-4 have established the core substrate: steward bootstrap, audit workspace, `ops.py`, watchdogs/recovery, online-first PR review surfaces, local `/review-plan`, audit index, curated memory, and session compaction.
- PR-5 is now primarily a rollout, adoption, and operational-proof phase rather than a large architecture-definition phase.
- The current operator substrate still needs a canonical operator-facing answer to: "which lane is working on which problem right now?"
- Local PR review-loop and plan-review loop state under `.claude/runtime/review_loops/**` and `.claude/runtime/plan_reviews/**` is transitional/legacy unless explicitly called out otherwise.
- If issue automation is adopted, it starts as scheduled/event-driven triage with dedupe and thresholds; it is not a default always-on autonomous fixer.

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
- **PR-1:** Steward lane/worktree contract, identity conventions, session/task metadata
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

### Review Architecture Migration (2026-03-18)

**Decision:** PR review becomes online-first; plan review remains local/in-session; existing local PR/plan review loops are transitional, not strategic.

- GitHub is the source of truth for PR review state.
- Deterministic prechecks should move to GitHub Actions as a normal PR check.
- Local PR review-loop state under `.claude/runtime/review_loops/**` and local plan-review loop state under `.claude/runtime/plan_reviews/**` should not become new first-class dependencies of the ops layer.
- `/review-plan` remains the user-facing plan review command, but its backend should be simplified to a local Claude-first in-session flow rather than a Codex CLI subprocess loop.
- Existing local PR/plan review loop code may be kept functioning during migration, but it should not be expanded further unless strictly required for transition safety.

**Dated repo fact (2026-03-18):**
- Branch protection on `main` currently requires `tests` and `governance`.
- `reviewing-changes` is advisory, not required.

**Implementation constraint:**
- `scripts/internal/deterministic_prechecks.py` uses `git diff origin/main...HEAD`, so any GitHub workflow that runs it must fetch history deeply enough for the merge base to exist.

### Issue Triage Architecture (2026-03-19)

**Decision:** Add issue automation as a triage/backlog layer first, not as a permanently autonomous fix-everything worker.

- The system may create or update GitHub issues from qualified operational findings, but issue creation must be thresholded, deduplicated, and source-backed.
- `ops` remains the detector and evidence producer. An optional `issues` agent or scheduled triage workflow may convert durable findings into GitHub issues and project items.
- The recommended initial operating mode is scheduled or event-driven triage, not a permanently running autonomous fixer lane.
- Autonomous code execution must remain gated behind explicit issue readiness markers such as assignment, `agent-ready`, or equivalent project state. Finding an issue is not by itself permission to start coding.
- Repeated transient failures, advisory-only findings, and duplicate incidents should update an existing issue or project item instead of creating new backlog noise.
- Dedupe keys, issue budgets, and escalation thresholds should be repo-owned policy, not improvised by whichever agent happens to be running.

**Why:**
- The new event log, watchdogs, retry/reroute policy, and audit index now produce the evidence needed for durable backlog capture.
- A triage layer reduces “noticed but not tracked” failures without creating an unbounded autonomous issue/PR loop.

### Lane Activity / Current Work Surface (2026-03-19)

**Decision:** Add a canonical lane-activity view as part of PR-5 continuation, starting by extending `ops.py status` or a tightly related operator surface rather than introducing a separate dashboard framework first.

- The operator should have one repo-owned place to answer: "which lane is working on which problem right now?"
- The first implementation should prefer extending existing operator surfaces (`ops.py status`, and optionally `ops.py health`) rather than adding a separate web/TUI dashboard.
- The lane-activity view should synthesize current work from existing repo-local state where possible:
  - `.claude/runtime/task_state/**`
  - `.claude/runtime/session_metadata/**`
  - `.claude/runtime/worktree_registry/**`
  - durable events
  - PR / CI linkage already surfaced through `ops.py reviews` and `ops.py ci`
- Only introduce a dedicated `lane_activity` registry if deriving a trustworthy current-work summary from existing state proves too ambiguous.
- The surface should highlight at least:
  - `lane_id`
  - current task id or short title
  - current step or progress note
  - state (`active`, `blocked`, `waiting_review`, `waiting_ci`, `idle`)
  - linked PR if present
  - last progress timestamp
  - attention flag when stale or blocked
- The primary goal is operator clarity, not polished UI. A richer dashboard can come later if the current-work contract proves useful.
- The implementation must degrade gracefully when some fields are missing.

## Decisions

### Target Workflow
- VS Code remains the primary audit and editing UI.
- Ghostty or another native terminal becomes the primary terminal host.
- tmux becomes the session manager for long-lived autonomous agents.
- Each active autonomous lane gets its own git worktree.
- The main checkout becomes a control plane and audit root, not a write surface.

### Role Classes
- `author`: implementation role class; in practice the steward baseline may host multiple author lanes (`author-a` through `author-d`) in parallel.
- `review`: advisory/manual reviewer role class; triages online PR review outcomes, performs bounded local plan/report/code reviews, and runs follow-up validation when online review or CI flags issues.
- `ops`: monitoring and orchestration role class; watches rung status, GitHub/CI review outcomes, heartbeats, failures, and artifact publication.
- `issues`: optional triage/backlog role class; turns qualified, deduplicated operational findings into GitHub issues or project items and routes them for later work. It is not the default autonomous fixer.
- `scratch`: optional utility lane for bounded exploratory or support work; not a primary ownership lane.

### Worktree Lifecycle Policy
- The default steward session maintains persistent lanes `author-a`, `author-b`, `author-c`, `author-d`, `review`, `ops`, and `scratch`.
- These lanes map back to role classes (`author`, `review`, `ops`, optional `issues`), but `lane_id` is the canonical machine identity.
- Specialized lanes such as `issues` may be added later if they prove useful, but they are not part of the default persistent baseline and should start as scheduled/event-driven workflows before becoming long-lived worktrees.
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

### Task Discipline And Lane Governance
- Every active execution lane must have one canonical repo-local task record while work is in progress.
- The task record is the lane's execution contract. It must define:
  - `task_id`
  - `owner_lane`
  - `goal`
  - `in_scope`
  - `out_of_scope`
  - ordered checklist items
  - validation steps
  - completion criteria
  - escalation triggers
- One lane should own one primary task at a time. Newly discovered work should become:
  - a follow-up item
  - a handoff to another lane
  - or an escalation to `ops`
- Agents must keep the repo-local task record aligned with the in-session task list they are actually following.
- A lane is considered drifting if its changed files, validations, or reported progress no longer match its declared task scope.
- Each lane must have an explicit charter that states:
  - what it owns
  - what it must not touch
  - when it must escalate
  - what counts as done
- Escalation is required, not optional, when:
  - requested work exceeds declared scope
  - touched files move outside allowed ownership without explicit reassignment
  - validation fails repeatedly beyond the configured threshold
  - the lane is blocked beyond the configured threshold
  - destructive or risky recovery action is needed
  - the plan/requirements become materially ambiguous
- Task completion requires:
  - updating task state
  - recording validation outcome
  - writing a short completion note or handoff summary
  - emitting follow-ups or blockers explicitly instead of leaving them implicit in chat history

### Role Capability Policy
- `author` may edit repo files, run targeted tests, run bounded validation, create branches/worktrees, and prepare or open PRs.
- `review` defaults to read, diff, review, and targeted validation only; write access is limited to review artifacts or explicitly delegated fix-up work.
- `ops` may inspect runtime state, refresh indexes, run status commands, poll GitHub/CI review outcomes, and perform bounded orchestration/recovery actions; code edits are off by default unless explicitly delegated.
- `issues` may read runtime state, query the audit index, check existing GitHub issues/project state, and create or update bounded backlog items when repo policy thresholds are met; code edits and PR creation are off by default unless a separate execution flow is explicitly triggered.
- Destructive or recovery actions remain approval-gated regardless of role.

### Issue Triage Policy
- Issue automation exists to preserve durable backlog and routing, not to create a free-running autonomous fixer loop.
- New GitHub issues should be created only from qualified findings such as:
  - retry cap exhaustion
  - repeated CI failures of the same class
  - repeated watchdog findings on the same task, lane, PR, or worktree
  - repeated manual intervention on the same operational failure mode
  - migration/legacy dependencies that continue to block the target workflow
- One-off transient failures, advisory-only findings, and duplicate incidents should update or comment on an existing issue rather than create a new one.
- Issue creation must use repo-owned dedupe keys, thresholds, labels, and project-field conventions.
- The first rollout should prefer scheduled or event-driven triage.
- A permanently running `issues` lane is optional and should be adopted only after the triage policy proves low-noise in real use.
- Autonomous implementation from issues must remain gated by explicit human/project intent:
  - issue assigned for agent execution
  - `agent-ready` or equivalent label/state
  - bounded scope and validation plan

### User Role
- The user does not manage day-to-day execution once a task is delegated.
- The user audits diffs, plans, runtime state, and reports in VS Code as needed.
- The user remains the approval boundary for tool adoption outside the repo, terminal preferences, and any destructive recovery actions.

## Existing Assets To Reuse
- `.claude/scripts/claude-worktree.sh` already creates a worktree and starts Claude.
- `.claude/hooks/worktree-guard.sh` and `.claude/hooks/worktree-reminder.sh` already enforce “no edits from main checkout”.
- `scripts/internal/clean_worktrees.sh` already handles stale worktree cleanup.
- `scripts/internal/run_rung.py` and `src/bid_euchre/arc_d_v2/orchestration.py` already expose most of the runtime/orchestration state the operator surface needs.
- `scripts/internal/deterministic_prechecks.py` should be reused as the basis for a GitHub-hosted deterministic prechecks job.
- Existing local review-loop scripts and adapters are transitional references only; they should not be expanded into long-term operator dependencies.

## Scope

### In Scope
- Role-based worktree conventions and branch naming.
- tmux-based autonomous session bootstrap.
- VS Code audit workspace and tasks.
- Repo-local status/audit CLI.
- Local audit index for repo runtime artifacts.
- GitHub-hosted deterministic prechecks and provider-neutral PR review outcome monitoring.
- Simplified local `/review-plan` flow for plan review.
- Documentation and rollout procedure.

### Out Of Scope
- Replacing VS Code with a terminal-only workflow.
- Introducing Airflow, Dagster, Prefect, or other heavyweight orchestrators.
- Introducing fully dynamic self-modifying agent behavior.
- Replacing the existing rung orchestrator state machines.
- Preserving the current local PR/plan review loops as canonical long-term architecture.

## Architecture

### Control Surfaces
- Terminal control surface: Ghostty + tmux for persistent autonomous sessions.
- Editor audit surface: VS Code multi-root workspace spanning main checkout plus steward lane worktrees.
- Repo control surface: repo-owned scripts and tasks for bootstrap, status, resume, and cleanup.

### State Model
- Worktree state: branch, path, dirty/clean status, last activity.
- Worktree registry state: role/class (`persistent` or `ephemeral`), task/plan/PR linkage, TTL, cleanup status, and active session ownership.
- Session state: active role, current task, governing/session plan link, last checkpoint, and restart metadata.
- Task state: canonical todo list, current `in_progress` item, blocked reasons, validation status, and explicit completion marker.
- Progress state: last completed checklist item, last meaningful artifact touched, last validation run, current blocker, and last forward-progress timestamp.
- Event state: durable event log for CI failures, heartbeat anomalies, task completions, local review requests, and other hook-produced operational signals.
- Scheduler state: last tick time, last successful health pass, next due checks, and host-level recovery metadata.
- PR review state: provider-neutral review outcomes including GitHub PR checks, deterministic prechecks CI status, and visible online review artifacts/comments.
- Plan-review state: local `/review-plan` outputs and summaries; `.claude/runtime/plan_reviews/**` is transitional/legacy unless retained as a simplified local artifact store.
- Rung/orchestration state: `plans/**/state.json`, `execution_log.jsonl`, heartbeat files, checkpoints.
- Artifact/report state: manifests, latest report dirs, evidence outputs.
- CI state: per-PR check status (pending/pass/fail), failure class, retry count, last push SHA, remediation history.

### Audit Model
- VS Code shows all checkouts and generated audit artifacts.
- `ops.py status` provides a single summary for humans and agents, centered on provider-neutral review outcomes rather than local review-loop internals.
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
- `ops` is the active scheduler/orchestrator role. It owns periodic health checks, event draining, GitHub/CI review outcome polling, and escalation.
- `review` is an advisory/manual reviewer role for local plan/report/code review and follow-up validation. It is not a durable autonomous review-loop daemon.
- Hooks produce durable events on disk; they do not themselves become the long-lived scheduler.
- Host-level persistence is provided by OS-level startup/recovery (macOS `launchd` in the first implementation), whose job is to ensure the steward session and `ops` lane are re-established after terminal/session loss.
- Claude-session-only cron facilities may be used as convenience inside a running session, but they must not be the authoritative persistence or scheduling mechanism.
- `ops` should monitor not just liveness but task adherence:
  - whether the lane heartbeat is fresh
  - whether progress is being recorded
  - whether changed files remain inside declared scope
  - whether validation is advancing toward completion
- Heartbeats should distinguish:
  - process alive
  - task progressing
  - task blocked
  - task drifting
- The monitoring model should support lane inbox/outbox artifacts or equivalent message records so handoffs are durable and auditable rather than hidden in chat state.

### Context Safety Model
- Agent-loaded context sources are explicitly classified as trusted, generated, or untrusted.
- Generated context, session summaries, and imported notes must pass lightweight prompt-injection or instruction-conflict scanning before being promoted into memory or loaded automatically.
- Skills and curated memory entries require explicit provenance back to repo files or validated operator input.

## Implementation Sequence

### PR-1: Workflow Contract And Bootstrap — COMPLETE

**Depends on:** None (first PR in the chain).
**Produces:** Lane identity model, steward bootstrap, session/task/worktree metadata schemas, workflow docs. Required by all later PRs.
**Delivered:** #835 (role-model → steward-model), #839 (task discipline + lane governance), #841 (progress-state + one-task-per-lane)

> **Note:** The original plan described a three-role model (`author`, `review`, `ops`).
> Implementation evolved to a 7-lane steward model with `lane_id` as the canonical
> identity. Legacy three-role scripts are retained for compatibility. See
> `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` for the delivered identity model.

#### Delivered Outcomes
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — comprehensive workflow doc with steward identity model, lane capability matrix, task discipline contract, and progress-state schema.
- `.claude/tmux/steward-session.sh` — canonical steward launcher creating 7 lanes (author-a through author-d, review, ops, scratch) with v2 worktree registry metadata.
- `.claude/scripts/start-role-worktree.sh`, `.claude/scripts/start-agent-role.sh` — legacy compatibility bootstrap.
- `.claude/runtime/session_metadata/`, `.claude/runtime/task_state/`, `.claude/runtime/worktree_registry/` — v2 schemas with README docs.
- Lane governance: one-task-per-lane rule, escalation triggers, progress visibility contract.

#### Acceptance Criteria (all met)
- From the main checkout, `steward-session.sh` creates or reuses all 7 lane worktrees.
- Each lane session is identified via `lane_id` and resumable from repo-local metadata.
- Non-trivial delegated tasks create explicit task records with plan, scope, validation, and completion criteria.
- Documentation defines lane responsibilities, capability matrix, and the “one writer per worktree” rule.

### PR-2: Persistent Session Manager And VS Code Audit Surface — COMPLETE

**Depends on:** PR-1 (lane identity model and bootstrap scripts).
**Produces:** tmux session layout, VS Code workspace, host-level recovery. Required by PR-5 (rollout).
**Delivered:** #858

> **Note:** The steward tmux launcher was delivered in PR-1. PR-2 completed the
> remaining deliverables: steward-lane VS Code workspace, missing CI/review tasks,
> macOS launchd recovery, and `STEWARD_DETACHED` mode for non-interactive startup.

#### Delivered Outcomes
- `Bid-Euchre-agent-audit.code-workspace` — multi-root workspace with all steward lanes (author-a through author-d, review, scratch).
- `.vscode/tasks.json` — 19 tasks covering testing, status inspection, GitHub PR checks, deterministic prechecks, and plan review artifacts.
- `.claude/launchd/ensure-steward-session.plist` — macOS launchd template with `__REPO_PATH__`, `__CLAUDE_BIN__`, and `__LAUNCHD_PATH__` placeholders resolved at install time.
- `.claude/launchd/install-launchd.sh` — installer that resolves `claude` path and shell `PATH` at install time, validates plist, and loads via modern `launchctl bootstrap` with fallback.
- `STEWARD_DETACHED=1` env var in `steward-session.sh` for non-interactive contexts.
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — host-level recovery section, new task tables.
- `tests/unit/test_steward_session.py` — 21+ regression tests.

#### Acceptance Criteria (all met)
- One repo-owned command (`steward-session.sh`) starts the tmux session with all lane windows.
- On macOS, `install-launchd.sh` installs a launchd agent that re-establishes the steward session after host/session loss, with the `claude` binary path resolved at install time.
- One repo-owned workspace file opens the audit layout in VS Code with all steward lanes.
- The user can inspect all active lane worktrees and runtime artifacts from VS Code via 19 pre-configured tasks.

### PR-3: Operator CLI

**Depends on:** PR-1 (role conventions, session/task metadata schemas).
**Produces:** `ops.py` CLI, `src/bid_euchre/ops/` package. Required by PR-5 (rollout).

#### Objectives
- Provide a single operator entrypoint for current repo health.
- Reduce manual `rg`, `cat`, and path-hunting for common status questions.
- Provide deterministic recovery guidance when autonomous work hits common failure modes.
- Detect and surface long-running process failures early through lightweight watchdogs rather than manual polling.
- Enable autonomous post-push CI remediation: `ops` polls CI status, classifies failures, and `author` applies bounded safe fixes without human intervention.
- Make `ops` the scheduler brain for persistent monitoring while treating PR review as an online-first GitHub/CI concern and local plan review as a bounded in-session concern.

#### Deliverables
- `scripts/internal/ops.py`
- supporting module(s) under `src/bid_euchre/ops/`
- `src/bid_euchre/ops/worktrees.py`
- `src/bid_euchre/ops/watchdogs.py`
- `src/bid_euchre/ops/events.py`
- `src/bid_euchre/ops/reviews.py`
- `src/bid_euchre/ops/scheduler.py`
- recovery-template data or helpers under `src/bid_euchre/ops/recovery.py`
- `.claude/hooks/post-task-event.sh` — hook that appends durable operational events
- `.claude/hooks/pre-worktree-cleanup.sh` — PreToolUse hook that detects direct `rm -rf` on worktree directories and redirects to `ops.py worktrees prune`
- `.github/workflows/deterministic-prechecks.yml` — GitHub-hosted deterministic prechecks for PRs
- `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` — migrate to hybrid review architecture and mark local PR loop state transitional
- `docs/02_agent/CODEX_GITHUB_REVIEW.md` — document the online PR review path and pilot assumptions
- `.claude/skills/review-plan/SKILL.md` — simplify to a Claude-only in-session plan review flow
- `.claude/skills/reviewing-plans/SKILL.md` — align rubric usage with the simplified `/review-plan` path
- unit tests under `tests/unit/`
- optional `Makefile` targets like `make ops-status`
- **Permission migration:** Remove interim `rm -rf ../:*` deny rules from user settings once the PreToolUse hook and `ops.py worktrees prune` are validated
- `src/bid_euchre/ops/ci.py` — CI status polling, failure classification, and remediation policy
- `tests/unit/test_ops_ci.py` — CI failure classification and remediation policy tests
- `tests/unit/test_ops_events.py` — durable event append/drain tests
- `tests/unit/test_ops_reviews.py` — provider-neutral review outcome aggregation tests
- `tests/unit/test_ops_scheduler.py` — scheduler tick, due-check, and recovery tests

#### Commands
- `ops.py status`
- `ops.py events`
- `ops.py events drain`
- `ops.py tick`
- `ops.py daemon`
- `ops.py worktrees`
- `ops.py worktrees prune`
- `ops.py worktrees quarantine`
- `ops.py worktrees archive`
- `ops.py reviews`
- `ops.py health`
- `ops.py recover`
- `ops.py watchdogs`
- `ops.py retry --task <TASK_ID>`
- `ops.py ci` — poll CI status for a PR, classify failures, suggest remediation
- `ops.py ci --pr <N>` — check specific PR

> **Note:** The commands above are the delivered PR-3 operator surface. Later PRs add
> memory/index commands (`index`, `query`, `memory`, `compact`) on top of this base.
> Older exploratory command ideas such as `rungs`, `failures`, `artifacts`,
> `resume --role`, `schedule`, and `ci --remediate` are not part of the current
> shipped CLI and should be treated as deferred unless reintroduced explicitly.

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
- `.claude/runtime/scheduler/**`
- GitHub PR checks and review metadata (`gh pr checks`, `gh pr view`, or equivalent provider APIs)
- deterministic prechecks workflow results
- `.claude/runtime/plan_reviews/**` local artifacts only where retained for simplified `/review-plan`
- `.claude/runtime/review_loops/**` transitional/legacy only while migration is incomplete
- `.claude/runtime/task_state/**`
- `plans/**/state.json`
- `plans/**/execution_log.jsonl`
- heartbeat files
- evidence/report manifests
- process metadata and watchdog threshold configuration

#### Watchdog Coverage
- rung orchestrators with stale or missing heartbeats
- long-running commands that exceed configured wall-time bounds
- task sessions that remain `in_progress` without evidence of forward progress
- abandoned dirty worktrees associated with inactive sessions
- worktree count/age drift beyond configured limits
- detached or metadata-missing worktrees that cannot be safely classified
- PRs stuck in CI pending or failure state beyond configured thresholds
- PRs missing expected online review or deterministic prechecks outcomes beyond configured thresholds
- CI remediation loops that exceed retry caps without resolution

#### Watchdog Behavior
- Default behavior is detect, classify, log, and recommend a bounded recovery step.
- Auto-remediation is opt-in and limited to explicitly safe actions.
- Watchdogs must not silently kill or mutate important processes by default.
- Worktree cleanup defaults to dry-run reporting first; removal requires clean-state or explicit quarantine/archive handling.
- `ops` periodic monitoring should be implemented as a durable scheduler loop (`tick`/`daemon`) backed by repo-local state, not by session-only cron.
- `review` work should be triggered by explicit local tasks or follow-up validation requests, not by a durable autonomous loop.

#### Worktree Cleanup Policy
- Persistent steward lane worktrees are never auto-pruned.
- Ephemeral worktrees may be `idle`, `stale`, `quarantined`, `ready_to_remove`, or `archived`.
- Clean ephemeral worktrees with no active session and expired TTL may be removed automatically only in explicitly enabled cleanup mode.
- Dirty or detached worktrees must go through quarantine or archive flow before removal.
- Cleanup output must always include the reason a worktree qualified for prune/quarantine/archive.

#### Output Requirements
- Human-readable summary by default.
- JSON output mode for agent consumption.
- Non-zero exit when requested checks find blocking failures or stale runtime state.
- Health output must cover stale heartbeats, abandoned dirty worktrees, missing review outcomes, and missing or stale indexes.
- Health and scheduler output must show whether the event queue, GitHub/CI polling, local plan-review path, and host-level recovery path are healthy.
- Watchdog output must identify which process or session is unhealthy, why it tripped, which threshold fired, and the next bounded recovery action.
- Recovery output must classify common failures and recommend the next bounded action instead of generic retry loops.
- Worktree output must distinguish persistent steward lane worktrees from ephemeral task worktrees and show cleanup candidacy clearly.

#### Acceptance Criteria
- `ops.py status` answers “what is running, what is blocked, what failed, and what needs attention next?” in one command.
- `ops.py status` or equivalent operator surfaces should be able to identify lanes that are alive-but-drifting, alive-but-blocked, or complete-but-unclosed.
- The CLI works from the main checkout and any worktree.
- Agents can use JSON mode without custom parsing hacks.
- Scheduled health checks can run unattended and produce actionable summaries without human triage first.
- `ops` can recover its own periodic monitoring after session restart by reading scheduler state rather than relying on re-entered cron commands.
- GitHub is the source of truth for PR review outcomes surfaced by `ops.py`.
- Deterministic prechecks run as a visible GitHub PR check with workflow fetch depth sufficient for `origin/main...HEAD`.
- `/review-plan` remains available as a local in-session review flow without depending on a Codex CLI subprocess loop.
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
- Minimize repeated full-file rereads of plans, logs, reports, CI outputs, and sidecars.
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
- Audit index: searchable operational history over runtime artifacts, GitHub/CI review outcomes, local plan review outputs, checkpoints, and reports.
- Session archive: non-lossy compaction target containing older observations, operation summaries, and touched-artifact indexes for restart/resume.

#### Indexed Sources
- durable event log
- GitHub PR check snapshots / exported status summaries
- online review artifacts or exported review summaries
- local `/review-plan` artifacts and summaries
- review-loop and plan-review sidecars only as transitional/legacy sources during migration
- rung `state.json`
- `execution_log.jsonl`
- `checkpoints.md`
- evidence manifests
- latest report metadata

#### Query Use Cases
- “What failed in the last rung run?”
- “Which worktree owns the active implementation branch?”
- “Which PRs have failing or pending checks?”
- “Which PRs are missing deterministic prechecks or visible online review outcomes?”
- “Which local plan reviews are pending or completed?”
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
**Produces:** Validated end-to-end workflow, canonical current-work visibility, promoted skills, issue-triage workflow, context-safety validation.

#### Objectives
- Move from partial manual adoption to the default operating model.
- Validate the end-to-end flow using real repo tasks.
- Give the user and `ops` one place to see which lane is working on which problem without reading raw task files or inferring from diffs.
- Capture repeated successful workflows as reusable skills instead of rediscovering them.
- Capture qualified repeated operational failures as durable backlog without creating issue spam or autonomous issue/PR loops.
- Ensure auto-loaded context is safe to consume at high autonomy.

#### Deliverables
- rollout guide in `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- optional role-specific startup prompts or agent docs under `.claude/agents/`
- lane-activity / current-work surface in `ops.py status` or a tightly related operator surface showing current task and state per lane
- context-safety scan script for memory/summary/skill promotion
- skill-promotion workflow doc or helper script under `.claude/skills/` or `scripts/internal/`
- issue-triage workflow doc and issue/project conventions for qualified operational findings
- optional `issues` agent prompt/profile or scheduled triage helper, if adopted after pilot
- shadow snapshot/rollback workflow docs and helper script
- validation notes in a follow-up session plan or report

#### Rollout Steps
- Pilot on one bounded implementation task.
- Pilot the lane-activity surface against multiple active steward lanes and confirm it can answer "x agent is working on y problem" from one command.
- Pilot one online PR review path with exactly one reviewer enabled.
- Pilot one local `/review-plan` or report-review task.
- Pilot on one rung-monitoring task.
- Pilot one issue-triage flow from a qualified repeated finding into a deduplicated GitHub issue or project item.
- Validate handoff behavior across restarts and across multiple active worktrees.
- Promote at least one repeated multi-step workflow into a reusable skill.
- Validate that generated summaries or notes are scanned before auto-loading or memory promotion.
- Validate that shadow snapshots and operation logs are sufficient to audit and recover from a bad autonomous edit sequence.
- Make the workflow the documented default once all pilots pass.

#### Acceptance Criteria
- The user can delegate a task, open VS Code, and audit progress without sharing a checkout with the autonomous agent.
- The user can see which steward lane is working on which task, current step, and blocker state from one operator surface without reading raw task JSON.
- An agent can start, continue, review, and monitor work autonomously from dedicated steward lane worktrees.
- PR review runs online-first with visible GitHub/CI outcomes and without depending on local review-loop orchestration.
- Local plan review works in-session through `/review-plan` without PTY/parser fragility from a Codex subprocess loop.
- Repeated successful workflows are captured as skills or documented operator procedures.
- Qualified repeated operational findings can be captured as deduplicated GitHub issues or project items without flooding the backlog.
- Autonomous code execution from the issue backlog remains explicitly gated rather than implied by issue existence alone.
- High-autonomy context loading has a defined safety boundary and validation path.
- Autonomous work is reversible through documented snapshot/recovery mechanisms.
- Cleanup and recovery are documented and tested.

## Detailed File Plan
- `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` — canonical workflow doc for the new operating model.
- `.claude/scripts/start-role-worktree.sh` — role-aware worktree bootstrap and reuse logic.
- `.claude/scripts/start-agent-role.sh` — starts Claude in the correct role worktree with expected instructions.
- `.claude/tmux/steward-session.sh` — canonical tmux bootstrap for the steward session baseline.
- `.claude/tmux/agent-ops-layout.conf` — stable tmux window and pane layout.
- `.claude/launchd/ensure-steward-session.plist` — macOS host-level recovery template for steward session bootstrap.
- `Bid-Euchre-agent-audit.code-workspace` — multi-root audit workspace for VS Code.
- `.vscode/tasks.json` — audit/status/validation tasks.
- `scripts/internal/ops.py` — top-level operator CLI.
- `src/bid_euchre/ops/__init__.py` — package root for operator helpers.
- `src/bid_euchre/ops/status.py` — status aggregation logic and synthesized lane current-work view.
- `src/bid_euchre/ops/worktrees.py` — worktree registry, classification, TTL, and cleanup policy helpers.
- `src/bid_euchre/ops/events.py` — durable event append/drain helpers.
- `src/bid_euchre/ops/reviews.py` — provider-neutral PR review outcome aggregation and local plan review status helpers.
- `src/bid_euchre/ops/scheduler.py` — periodic scheduler loop and due-check logic.
- `src/bid_euchre/ops/memory.py` — curated memory ingestion, validation, and query helpers.
- `.claude/hooks/post-task-event.sh` — durable event producer hook for task completions/failures.
- `.claude/hooks/pre-worktree-cleanup.sh` — PreToolUse hook redirecting direct `rm -rf` on worktree dirs to `ops.py worktrees prune`.
- `src/bid_euchre/ops/watchdogs.py` — watchdog rules for long-running process health and stall detection.
- `src/bid_euchre/ops/ci.py` — CI status polling, failure classification, remediation policy, and retry tracking.
- `.github/workflows/deterministic-prechecks.yml` — GitHub-hosted deterministic prechecks workflow.
- `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` — migrated review architecture doc, marking local loop state transitional.
- `docs/02_agent/CODEX_GITHUB_REVIEW.md` — online review path and pilot guidance.
- `docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md` — qualified issue intake, dedupe, labels, and execution gates.
- `.claude/skills/review-plan/SKILL.md` — Claude-only in-session plan review flow.
- `.claude/skills/reviewing-plans/SKILL.md` — rubric support for `/review-plan`.
- `.claude/agents/issues.md` or equivalent optional profile — bounded issue-triage guidance if the `issues` agent is adopted.
- `src/bid_euchre/ops/recovery.py` — failure classification and bounded recovery templates.
- `src/bid_euchre/ops/compaction.py` — session compaction and archive metadata helpers.
- `src/bid_euchre/ops/index.py` — audit index build/query logic.
- `tests/unit/test_ops_status.py` — CLI/status/current-work synthesis tests.
- `tests/unit/test_ops_worktrees.py` — worktree lifecycle, prune, quarantine, and archive tests.
- `tests/unit/test_ops_events.py` — durable event log tests.
- `tests/unit/test_ops_reviews.py` — review outcome aggregation and local plan review status tests.
- `tests/unit/test_ops_scheduler.py` — scheduler/due-check/recovery tests.
- `tests/unit/test_ops_memory.py` — curated memory tests.
- `tests/unit/test_ops_watchdogs.py` — watchdog threshold and stall-detection tests.
- `tests/unit/test_ops_ci.py` — CI failure classification, remediation policy, and retry cap tests.
- `tests/unit/test_ops_recovery.py` — recovery template tests.
- `tests/unit/test_ops_compaction.py` — compaction/archive tests.
- `tests/unit/test_ops_index.py` — audit index tests.

## User-Owned Tasks
- Install Ghostty or confirm another terminal host.
- Install and adopt tmux.
- Decide whether to keep the current shell profile or add aliases/launchers.
- Decide whether Ghostty becomes the default terminal or only the autonomous-agent terminal.
- Install or enable the repo-provided `launchd` recovery job if host-level persistence is desired on macOS.

## Agent-Owned Tasks
- Implement all repo-local scripts, workspace files, tasks, docs, and CLI surfaces.
- Reuse existing worktree hooks instead of replacing them.
- Add tests for all new repo-local behavior.
- Implement scheduled health checks, curated memory, and safety scanning as repo-owned capabilities.
- Implement durable event production, provider-neutral review outcome monitoring, and scheduler state as repo-owned capabilities.
- Implement task-state tracking, compaction, recovery templates, shadow snapshot helpers, and watchdogs as repo-owned capabilities.
- Implement worktree lifecycle tracking, TTL policy, and safe cleanup as repo-owned capabilities.
- Implement issue-triage policy, dedupe rules, and GitHub issue/project routing as repo-owned capabilities if PR-5 adopts issue automation.
- Attach explicit validation evidence to each infrastructure PR: tests run, dry-run checks, manual smoke checks, failure-injection checks, rollback path, and known gaps.
- Validate the workflow through bounded pilots before making it default.

## Operational Validation Gate

Infrastructure PRs in this overhaul must be validated as operational changes, not
just as code changes.

- Every implementation PR must include a `Validation Performed` section in the PR
  body before merge.
- The validation record must include:
  - automated tests run (`pytest`, `make check-quiet`, workflow checks, or equivalent)
  - dry-run validation for destructive or stateful paths
  - manual smoke checks in the real steward environment
  - at least one failure-injection or unhappy-path check for the new capability
  - explicit rollback or disable path
  - known gaps or untested areas
- New automation should launch in observe-only, report-only, or dry-run mode
  before enforcement whenever that is technically feasible.
- Do not remove the previous manual fallback path on first landing. Keep it until
  the new path passes smoke validation and survives real use.
- Treat infrastructure changes as "landed but not yet trusted" until they have
  passed a short soak period in normal steward use without incident.
- Merge readiness for infrastructure PRs requires more than green CI:
  operator-facing workflows must be shown to work in the intended environment.

## Execution Risks

The following capabilities have no prior repo precedent and carry higher implementation risk:

- **Context safety scanning (PR-5):** Prompt-injection and instruction-conflict detection for auto-loaded content. No existing scanner to build on; start with a minimal keyword/pattern scanner and iterate.
- **Shadow snapshots (PR-5):** Filesystem snapshots for rollback of autonomous edits. Must not conflict with git state or worktree lifecycle. Consider lightweight git stash/branch-based approach before building custom snapshot tooling.
- **Issue triage automation (PR-5):** Automatic backlog creation can easily create duplicates or noise if thresholds, dedupe keys, and labels are weak. Start with triage-only authority and scheduled/event-driven pilots before considering a persistent `issues` lane.
- **Curated memory system (PR-4):** Provenance-tracked memory distinct from MEMORY.md. Risk of duplicating or conflicting with the existing auto-memory system. Must define clear boundary: curated memory stores operator-validated facts; auto-memory remains the conversation-scoped system.
- **SQLite audit index (PR-4):** Introduces a database dependency for operational state. Must remain optional — the workflow should degrade gracefully if the index is stale or absent.
- **CI remediation loop (PR-3):** Autonomous CI fix-and-repush could introduce scope creep or unbounded retries. Mitigated by strict failure classification, retry caps (max 3), and escalation for non-remediable classes. The `risky/destructive` class is never auto-remediated.
- **Host-level persistence (PR-2/PR-3):** `launchd` recovery plus scheduler state must not create duplicate steward sessions or duplicate monitor loops. Idempotent bootstrap and lock/state checks are required.
- **Online review provider drift (PR-3/PR-5):** GitHub-hosted reviewer behavior, branch protection settings, or API surfaces may change. Keep provider usage documented as of a dated review and avoid hard-coding assumptions deeper than necessary.
- **Duplicate reviewer noise (PR-3/PR-5):** Running multiple online reviewers simultaneously could create low-signal PR noise. Pilot exactly one reviewer path first and avoid dual automatic reviewers during migration.

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
  - Mitigation: persistent vs ephemeral classification, dry-run-first cleanup, quarantine for dirty worktrees, and no default deletion of steward lane worktrees.
- CI remediation introducing unrelated changes or scope creep.
  - Mitigation: fix scope = failure scope; re-push must not include unrelated changes; Tier 1 validation before each re-push.
- CI remediation becoming an unbounded retry loop.
  - Mitigation: max 3 attempts per PR; non-remediable classes escalate immediately; all actions logged.
- Local review-loop code lingering as a hidden dependency.
  - Mitigation: mark `.claude/runtime/review_loops/**` and `.claude/runtime/plan_reviews/**` transitional/legacy, and do not build new ops dependencies on them.
- Added tooling without operational adoption.
  - Mitigation: staged rollout with acceptance checks after each PR.
- Issue automation flooding the backlog with transient failures or duplicates.
  - Mitigation: repo-owned dedupe keys, thresholds, issue budgets, and update-existing behavior before opening new issues.
- Issue discovery automatically turning into autonomous code churn.
  - Mitigation: triage and execution are separate flows; only explicitly `agent-ready` or assigned issues may enter an autonomous coding lane.

## Verification Strategy
- Per-PR validation must include targeted automated tests plus operational smoke
  tests for the specific capability being introduced.
- Per-PR validation must include at least one failure-injection check for the new
  path, not just the happy path.
- For new enforcement or automation surfaces, validate detect/report behavior
  first and enable mutation or enforcement only after shadow-mode confidence is
  established.
- After merge, keep new infrastructure on a short soak period before removing
  manual fallbacks or older workflow paths.
- Unit tests for `ops.py` parsing and state aggregation.
- Unit tests for role metadata and recovery logic.
- Unit tests for durable event append/drain, review outcome aggregation, and scheduler tick/recovery behavior.
- Unit tests for task-state progression, WIP-limit enforcement, escalation trigger handling, and drift detection.
- Unit tests for worktree registry classification, TTL handling, prune eligibility, and quarantine behavior.
- Unit tests for curated memory validation and promotion.
- Unit tests for audit index build/query behavior.
- Unit tests for watchdog thresholds, stale-heartbeat detection, and no-progress detection.
- Unit tests for task-state progression and explicit completion handling.
- Unit tests for CI failure classification across all 6 failure classes.
- Unit tests for remediation policy (retry caps, escalation triggers, scope constraints).
- Unit tests for non-lossy compaction and archive lookup.
- Manual smoke test of role bootstrap and tmux session creation.
- Manual smoke test that `launchd` or equivalent host-level recovery re-establishes the steward session and `ops` lane after process loss.
- Manual smoke test of worktree prune dry-run, quarantine, and archive flows.
- Manual smoke test of VS Code workspace opening all intended roots.
- Manual smoke test of scheduled health checks and stuck-session detection.
- Manual smoke test that deterministic prechecks appear as a visible GitHub PR check with sufficient fetch depth.
- Manual smoke test that one online reviewer path is visible on PRs without duplicate automated reviewer noise.
- Manual smoke test that `/review-plan` runs locally in-session without Codex subprocess orchestration.
- Manual smoke test of long-running process watchdogs against intentionally stalled sessions.
- Manual smoke test that a lane with stale progress or out-of-scope edits is surfaced as drifting rather than merely alive.
- Manual smoke test that blocked lanes escalate according to the documented triggers instead of silently retrying forever.
- Manual smoke test that a qualified repeated failure creates or updates a deduplicated GitHub issue/project item rather than spamming duplicates.
- Manual smoke test of snapshot-based rollback and recovery after an intentionally bad edit sequence.
- Manual smoke test of CI remediation: introduce a lint failure, push, verify `ops.py ci` classifies it correctly and `author` auto-fixes within retry cap.
- Pilot tasks that exercise:
  - implementation flow
  - online PR review flow
  - local `/review-plan` flow
  - rung monitoring flow

## Success Criteria
- The default path for autonomous work is: bootstrap steward lane worktrees -> start tmux session -> delegate tasks to agents -> audit in VS Code.
- No autonomous writing occurs from the main checkout.
- The user no longer needs to manage multiple ad hoc terminals in a shared checkout.
- A single repo-owned status surface answers the operational questions that currently require manual inspection.
- Autonomous work is resumable, explicitly tracked, and recoverable without relying on implicit terminal context.
- `ops` monitoring survives session loss through host-level recovery plus repo-local scheduler state, PR review state comes from GitHub/CI outcomes, and local plan review remains an in-session flow rather than a local subprocess loop.
- Each active lane stays bounded by an explicit task contract, surfaces progress durably, and can be identified as on-track, blocked, or drifting without reading raw terminal history.
- Qualified repeated incidents can be captured in GitHub issues/project state with low noise, while autonomous implementation from backlog remains explicitly gated.

## Outcome
<!-- Filled after implementation -->
- PR: deferred (PRs 1-2 sequenced after Phase 4a; PRs 3-5 per original triggers)
- Notes:
  - Planning-only session (2026-03-15). Existing Claude worktree hooks and helper scripts should be treated as implementation inputs, not replaced blindly.
  - Review session (2026-03-16): Compatibility analysis confirmed PRs 1-2 low-risk during FULL backfill. User-side setup completed (Ghostty, tmux, permissions verified, 37 stale worktrees cleaned). Four design decisions resolved. Sequencing revised: Phase 4a first, then PR-1, then PR-2. CI remediation loop added to PR-3 scope.
  - Scheduling refinement (2026-03-18): Session-only cron helpers are not treated as durable persistence. The plan now assumes hook-produced durable events, `ops`-owned scheduler state, provider-neutral review outcome monitoring, and host-level recovery (`launchd` on macOS) for monitoring persistence.
  - Review architecture refinement (2026-03-18): PR review is now online-first with GitHub-hosted deterministic prechecks and provider-neutral outcome monitoring. Local PR/plan review loops are transitional only. `/review-plan` remains the local plan-review entrypoint but should be simplified to an in-session Claude-first flow.
