# Agentic Orchestration Platform — Governing Plan

**Date:** 2026-03-19
**Status:** ACTIVE
**Scope:** Build the prompt-first orchestration platform that sits on top of the current steward control plane: single-entry orchestration, dashboard-first supervision, durable communication, remote operator reachability, bounded second-model reviewer/maintainer lanes, and portability to other coding repos.
**Supersedes:** [Post-PR-5 Follow-On Roadmap](../post_pr5_follow_on_roadmap.md) for committed orchestration-platform scope; seeded from [2026-03-19_agentic-orchestration-platform.md](2026-03-19_agentic-orchestration-platform.md)
**Parent context:** [Autonomous Agent Ops Workflow](../sessions/2026-03-15_autonomous-agent-ops-workflow.md)

## 1. Decision

Build the agentic orchestration platform as a governed follow-on initiative on
top of the current steward control plane. This initiative exists because the
repo has outgrown a pure session-plan rollout: it now needs a durable
orchestrator, dashboard-first supervision, message-backed coordination, remote
operator reachability, bounded second-model review/maintenance, and a portable
core that can later be reused outside Bid-Euchre. The platform should land in
consumable batches that accelerate current repo work and browser-game work as
they ship, rather than forming one monolithic prerequisite wall.

## 2. Goals

1. Add a single user-facing `orchestrator` lane for normal task intake and delegation.
2. Move the visible steward experience toward dashboard-first supervision with resumable background workers.
3. Add durable lane-to-lane communication, remote operator reachability, and high-signal idle escalation.
4. Add bounded self-improving skill promotion and bounded second-model reviewer/maintainer service lanes.
5. Preserve a clean core-vs-adapter boundary so the orchestration layer can later be reused in another coding or research repo.

## 3. Key Definitions

- **`orchestrator`**: the single normal ingress for user-submitted work; it creates task packets, delegates, and reports outcomes.
- **Worker pool**: the background `author-*` lanes that execute bounded delegated tasks and can be reused or scaled within repo-owned limits.
- **Communication bus**: the durable message/event/summarization layer used for coordination between lanes.
- **Remote operator channel**: the Telegram and/or Discord path used for bounded remote supervision and 5-minute idle-attention alerts; it is not the source of truth.
- **Repo adapter**: the repo-specific policy layer for CI, branch policy, validation commands, labels, and workflow conventions.
- **Second-model service lane**: an advisory reviewer or maintainer lane, such as Codex, operating through durable task packets rather than a hook-coupled local review loop.

## 4. Execution Structure

### 4.1 Phases / Milestones

| Phase | Directory | Description | Depends On |
|-------|-----------|-------------|------------|
| 0 | `0_bootstrap` | Governed-plan scaffolding, discovery wiring, and Platform-1 entry gating | PR-5 closed; bridge gate satisfied (2026-03-21) |
| 1 | `1_coordination_core` | `Platform-1` through `Platform-3`: lane registry, intake contract, communication substrate, and primary PR review architecture | Phase 0 |
| 2 | `2_visible_operating_model` | `Platform-4` through `Platform-5`: dashboard-first stewardship, canonical prompts, first skills | Phase 1 |
| 3 | `3_supervision_and_scaling` | `Platform-6` through `Platform-7`: supervisor routines and worker-pool manager | Phase 2 |
| 4 | `4_remote_channel` | `Platform-8` through `Platform-9`: Telegram/Discord integration and idle-attention flow | Phase 3 |
| 5 | `5_portability_and_learning` | `Platform-10` through `Platform-11`: core-vs-adapter split and skill learning loop | Phase 3 |
| 6 | `6_second_model_and_validation` | `Platform-12` through `Platform-13`: cross-model service lanes and second-project validation | Phase 5 |
| 7 | `7_closeout` | `Platform-14`: hardening, migration docs, residual closeout | Phases 1-6 |

### 4.2 Step Template (per phase)

Each phase follows this standard sequence:

1. **Scope lock**
   - **Commands:** read `CLAUDE.md`, this governing plan, the active phase `checkpoints.md`, and any active sub-plans.
   - **Validates:** the next step is unambiguous and the phase boundary still matches the roadmap.
   - **Error recovery:** if the work needs new design choices or touches more than three files, create a sub-plan before implementation.
   - **Outputs:** updated checkpoint target and, when needed, a registered sub-plan.
2. **Implementation**
   - **Commands:** targeted edits, focused tests, and phase-specific commands defined by the sub-plan or slice.
   - **Validates:** the implementation stays within the declared slice boundary and preserves core-vs-adapter separation.
   - **Error recovery:** record blockers or required amendments rather than silently widening scope.
   - **Outputs:** code/docs/runtime-contract changes for the slice.
3. **Verification**
   - **Commands:** targeted automated tests, manual steward smoke checks, and at least one unhappy-path / failure-injection check.
   - **Validates:** the slice meets its "done when" criteria and has a rollback/disable path.
   - **Error recovery:** add missing tests or tighten the slice before proceeding.
   - **Outputs:** validation evidence recorded in checkpoints, PR body, or sub-plan outcome.
4. **Handoff**
   - **Commands:** update phase checkpoints, the sub-plan registry, and any relevant sub-plan outcome sections.
   - **Validates:** a future agent can resume from durable state rather than reconstructing intent from chat history.
   - **Error recovery:** if incomplete, mark the step `BLOCKED` or leave it `IN_PROGRESS` with a precise next action.
   - **Outputs:** durable handoff state.

### 4.3 Phase 0 Dependencies

Before `Platform-1` implementation begins:

- [x] PR-5 slices 3-7 complete (2026-03-20)
- [x] `ops.py status` is trustworthy enough to support dashboard-first work
- [x] worktree/session registry behavior is stable enough to extend
- [x] post-PR-5 bridge gate satisfied (2026-03-21) — filesystem boundary (#1115), PR comment ingestion (#1122), review coordinator reset (#1123), repair lane (#1138), precheck hardening (#1126, #1132). Trusted command handling deferred to Platform-1. See `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`.

## 5. Sub-Plan Governance

Sub-plans are required for implementation-heavy slices, multi-file design work,
or any step where the governing plan leaves material design choices open.

- Registry location: `plans/agent_ops/sub_plan_registry.md`
- File location: `plans/agent_ops/<phase>/sub/YYYY-MM-DD_<slug>.md`
- Required statuses: `proposed`, `in_progress`, `blocked`, `completed`, `abandoned`, `superseded`
- Every implementation-heavy Platform slice should trace to either the
  governing plan step or a registered sub-plan

## 6. Checkpoint Contract

Each active phase maintains a checkpoint file at:
`plans/agent_ops/<phase>/checkpoints.md`

Current active phase:

- `plans/agent_ops/0_bootstrap/checkpoints.md`

Agents should treat checkpoints as the human-readable source of current step
status, blockers, and session handoff state.

## 7. Evidence / Output Contract

Each Platform slice should produce:

- code/docs/runtime state changes scoped to one slice
- automated tests for new runtime/state logic
- manual steward-environment smoke checks
- at least one unhappy-path / failure-injection check
- rollback/disable path
- known gaps

The exploratory operator/orchestration ideas in
[post_pr5_follow_on_roadmap.md](../post_pr5_follow_on_roadmap.md) remain
non-binding background context. This governed plan supersedes that roadmap for
committed orchestration-platform scope.

Additional non-binding post-sprint branch-out ideas for the `agent_ops`
initiative are tracked in
[post_sprint_brainstorm.md](post_sprint_brainstorm.md).

## Desired End State

### Human-facing surfaces

The user normally interacts with only:

- `dashboard`
- `orchestrator`
- `ops`
- `review`
- `issues`
- a remote operator channel (Telegram and/or Discord)

### Background execution

The system manages a worker pool of:

- `author-a`
- `author-b`
- `author-c`
- `author-d`
- `author-scratch`
- additional bounded `author-*` lanes when parallelism justifies it

### Truth model

- repo runtime state = operational truth
- GitHub = PR/review/CI truth
- communication bus = coordination truth
- Telegram/Discord = notification and bounded remote control, not source of truth

## Core Principles

1. **Single ingress:** Normal new work enters through `orchestrator`.
2. **Delegation alignment:** For non-trivial tasks, `orchestrator` shows the
   proposed author-lane prompt/task packet to the user before dispatch.
3. **Background workers:** Authors are execution workers, not primary human-facing interfaces.
4. **Clear role boundaries:** `orchestrator`, `ops`, `review`, `issues`, and `author-*` retain distinct responsibilities.
5. **Prompt-first:** The primary interface is prompts, skills, and workflows, not raw CLI choreography.
6. **Durable coordination:** Important messages and decisions must be logged in repo-owned state.
7. **High-signal notifications:** Remote alerts are summarized, deduplicated, and bounded.
8. **Exportable core:** Generic orchestration logic should be separable from repo-specific policy.
9. **Remote reachability is required:** The user must be reachable through Telegram and/or Discord when away from the steward session.
10. **Learning loop is explicit:** Repeated successful workflows should be turned into reviewed, reusable skills over time.

## Non-Goals

- Replacing GitHub as the source of truth for PR status
- Replacing repo/runtime state with chat transcripts
- Creating a free-roaming autonomous issue fixer
- Letting author workers self-assign work from backlog by default
- Building a heavyweight external orchestrator (Airflow, Dagster, Prefect, Celery, etc.)
- Allowing remote channels to bypass repo-owned review, audit, or safety boundaries

## Preferred Implementation Tooling

The platform should prefer a small, explicit tooling stack over a large agent
framework.

### Recommended tools

- **Pydantic**
  - for lane/session/message/task schemas and validation
- **watchdog**
  - for file-system driven automatic state updates and touched-file tracking
- **APScheduler**
  - for recurring in-process supervisor, issues, and idle-attention jobs
- **libtmux**
  - for tmux-aware introspection, session checks, and safer lane/session handling
- **SQLite + JSONL**
  - SQLite for queryable current state, inboxes, dashboards, and indexes
  - JSONL for append-only immutable audit trails

### Optional later tools

- **Textual**
  - only if/when the dashboard graduates from `ops.py status` plus summaries to
    a richer terminal UI

### Avoid for now

- **LangChain or similar frameworks for core orchestration**
  - possible later for retrieval/Q&A layers, but not for the control plane
- **Redis / Postgres / external queues as required infrastructure**
  - do not make the first version depend on a separate always-on data service
- **Heavy workflow/orchestration systems**
  - Airflow, Dagster, Prefect, Celery, Temporal, etc.

### Tooling principle

The first version should remain:

- repo-local
- explicit
- schema-driven
- easy to audit
- easy to port

If a tool makes the control plane harder to reason about, it is the wrong tool
for the first version.

## Target Architecture

### Lanes

- **`orchestrator`**
  - single user-facing intake point
  - decomposes work
  - drafts delegation prompts / task packets for author lanes
  - shows non-trivial delegation prompts to the user for approval or editing
    before dispatch
  - spawns plan review
  - assesses safe parallelism
  - delegates to author workers
  - tracks dependencies and user-facing state

- **`ops`**
  - supervisor lane
  - watches health, watchdogs, review/CI state, worker utilization
  - emits delta summaries and recovery recommendations

- **`review`**
  - bounded review and validation lane
  - handles `/review-plan`, PR/code review, local repro, and validation

- **`issues`**
  - scheduled triage lane
  - runs every 30-60 minutes
  - dedupes and updates issues
  - never implements fixes directly

- **`author-*`**
  - background worker pool
  - executes bounded delegated tasks
  - resumes by lane name/session identity
  - may scale up or down within repo-owned limits

### Session model

The visible steward session should become dashboard-first:

- `dashboard`
- `orchestrator`
- `ops`
- `review`
- optional `issues`

Author workers should be hidden or closed by default in the visible steward
layout and opened or resumed on demand when the orchestrator delegates work or
the user explicitly drills down. Ordinary supervision should not require
keeping all worker panes foregrounded.

### Registry model

The platform needs a durable lane/session registry with at least:

- `lane_id`
- `role_class`
- `session_handle`
- `worktree_path`
- `branch`
- `current_task_id`
- `linked_pr`
- `state`
- `last_active_at`
- `last_user_attention_at`
- `visibility` (`foreground`, `background`, `hidden`)

This registry must support:

- resume-by-name
- worker-pool summaries
- dashboard rendering
- stale/idle detection

## Communication Layer

### Communication types

Keep these distinct:

- **events**
  - immutable low-level facts
  - example: `task_started`, `ci_failed`, `issue_updated`

- **messages**
  - lane-to-lane actionable coordination
  - example: `orchestrator -> author-a` assignment

- **summaries**
  - human-facing digests
  - example: “author-b blocked on governance failure”

### Message contract

Each message should carry:

- `message_id`
- `thread_id`
- `task_id`
- `from_lane`
- `to_lane`
- `message_type`
- `priority`
- `status`
- `created_at`
- `acked_at`
- `resolved_at`
- `requires_human`
- `summary`
- `payload`
- `source_transport`
- `parent_message_id`

### Storage

- append-only JSONL for immutable audit trail
- SQLite for current inboxes, unresolved items, dashboard views, and queryability

### Delivery semantics

The communication layer must define:

- acknowledgement semantics
- retry semantics
- duplicate suppression
- expiry / TTL
- dead-letter handling

The platform must not rely on best-effort message passing between lanes.

### Message flows

- `orchestrator -> author-*`
  - assignment packets
- `author-* -> orchestrator`
  - ack, progress, blocker, completion
- `ops -> orchestrator`
  - supervisor alerts, retry/reroute recommendations
- `review -> orchestrator`
  - plan review outcome, PR findings, validation status
- `issues -> orchestrator`
  - issue created/updated, threshold crossed
- remote channel -> `orchestrator` / `ops`
  - bounded user replies, acknowledgements, reroute/inspect requests

## Prompt And Skill Layer

### Canonical prompts

The platform should define reusable lane prompts for:

- `orchestrator`
- `ops`
- `review`
- `author-*`
- `issues`

### Named skills / workflow wrappers

Initial skill set:

- `start-task`
- `delegate-task`
- `monitor-pr`
- `prepare-review`
- `recover-stalled-lane`
- `triage-qualified-issue`
- `summarize-worker-pool`
- `notify-remote-operator`

The prompts should call these routines rather than forcing the user to think in raw `uv run ...` commands.

## Self-Improving Skill Loop

The platform should support a bounded skill-generation and skill-improvement
loop for repeated successful workflows.

### Purpose

- capture repeated multi-step workflows without rediscovering them
- improve prompt-first operation over time
- make successful orchestrator/review/ops/author routines portable to other repos

### Constraints

- no autonomous skill activation without review
- provenance must link back to successful real executions
- context-safety scanning must apply before skill promotion
- promotion remains gated through repo-owned validation and approval policy

### First target

Start with:

- skill suggestion generation from repeated successful runs
- explicit proposed skill artifacts
- human/review approval before activation

Only later should the system attempt bounded self-improvement of already approved skills.

## Cross-Model Reviewer And Maintainer Lanes

> **Architecture note:** The primary PR review architecture (durable review
> request/verdict state and merge-safety gate) belongs to `Platform-3`, not
> here. This section defines second-model service lanes that operate as
> advisory participants on top of that substrate. `SendMessage`-style
> lane-to-lane delivery is a later convenience layer on the durable review
> bus — it is not the source of review truth.

The platform should later support bounded second-model service lanes so Claude
can remain the primary executor while another model such as Codex handles
background review and maintenance work.

### Intended roles

- **`codex-review`**
  - advisory reviewer lane
  - receives bounded review tasks from `orchestrator`, `ops`, or `review`
  - emits findings into the durable communication bus
  - does not share authorship responsibility with the executing Claude lane

- **`codex-maint`**
  - bounded maintenance lane
  - handles explicitly assigned maintenance tasks such as doc drift checks,
    plan consistency checks, follow-up issue drafting, or small corrective
    follow-up branches
  - does not self-assign new product work

### Guardrails

- Do **not** revive the old hook-coupled local review loop as the primary model.
- Keep reviewer and fixer separate; do not return to the same-loop
  review -> auto-fix -> re-review cycle as the normal path.
- Route all work through durable task packets and the communication bus rather
  than raw terminal history or ad hoc subprocess stdout parsing.
- Start advisory-first; do not make the second-model lane merge-blocking until
  its reliability is measured on real traffic.
- Require structured terminal states such as `clean`, `findings`, `blocked`,
  and `failed` instead of relying on fragile free-form parsing alone.
- Add circuit breakers: retry caps, cooldowns, degraded-lane state, and
  escalation back to `review`/`ops`.
- Restrict triggers to explicit assignment, PR review requests, CI-follow-up
  investigation, or scheduled maintenance sweeps.

### What success looks like

- Claude remains the primary implementation agent.
- Codex (or another second model) can review or maintain in the background
  without becoming a flaky hidden blocker.
- Failures in the second-model lane degrade gracefully into advisory warnings or
  explicit `degraded` service-lane state, not silent pipeline stalls.

## Automatic State Updates

Automate where safe:

- file-touch / scope updates from hooks
- PR linkage back to task/lane state
- lane activity from task/session/events
- progress timestamps from durable events
- worker idle/busy state
- idle-attention timers for user-facing lanes

Agents should not be required to act as shell clerks for routine state mutation.

## Security, Safety, And Platform Controls

### Security / credential model

The platform must define:

- where bot and remote-channel credentials live
- which lanes can access which credentials
- which remote commands are allowed
- which remote commands require explicit confirmation
- how destructive actions remain gated even when triggered remotely
- how filesystem access is bounded so agents default to repo-owned paths rather
  than wandering into arbitrary host files

### Filesystem access boundary

The platform should make repo-bounded filesystem access the default:

- agents may read and write inside the repo root by default
- repo-owned runtime areas remain allowed (for example `.claude/runtime/**`)
- any temp/artifact exception should be narrow, explicit, and auditable
- reads outside the repo are sensitive too; not just writes
- outside-repo access should require explicit operator approval or a narrowly
  managed allowlist, not just prompt wording

This is both a safety control and an extensibility control: it keeps future
multi-agent and second-model behavior bounded to the repo unless the operator
chooses otherwise.

### Pause / safe-mode / kill switch

The platform must support a repo-owned safe-mode that can:

- pause remote command intake
- pause background delegation
- pause issue creation
- pause dynamic worker creation
- optionally keep read-only monitoring active

### Schema versioning and migrations

The following runtime contracts need explicit versioning and migration rules:

- lane/session registry
- task packets
- messages/inboxes/outboxes
- remote notification state
- worker-pool metadata

### Budgeting and rate limits

The platform must define repo-owned caps for:

- max active author workers
- max issue creation per period
- max remote notifications per period
- supervisor polling cadence
- retry/reroute churn

### Platform observability

The platform must expose its own health signals, including:

- orchestrator liveness
- ops supervisor liveness
- message backlog size
- worker-pool utilization
- remote adapter health
- idle-alert delivery success/failure
- registry/message mismatch counts

## Remote Operator Channels

The platform should support an official Claude Code plugin path for:

- Telegram
- Discord

Recommended pilot:

- Telegram first for personal DM-based supervision
- Discord later if shared/team-room workflows become important

### Allowed remote behaviors

- summaries
- alerts
- acknowledgements
- bounded commands such as:
  - inspect
  - reroute
  - pause retries
  - summarize active lanes
  - send review to PR N

At least one of Telegram or Discord must be adopted as part of the platform.
Telegram is the recommended first path, but the remote operator channel is not
optional in the target end state.

If an official Claude Code plugin path is unavailable, unstable, or lacks the
required bounded-command surface when `Platform-8` begins, that slice should
use a minimal repo-owned adapter with the same command and audit contract
instead of blocking the roadmap on that external dependency.

### Idle-attention policy

If a user-facing lane or conversation is awaiting user attention and remains
idle for more than **5 minutes**, the system should send a high-signal remote
summary. This must be:

- deduplicated
- summarized
- rate-limited / backoff-controlled
- routed through `ops` or `orchestrator`, not emitted independently by every author lane

## Exportability To Other Coding Repos

The system should separate into:

### Reusable core

- lane/session registry
- worker-pool manager
- communication layer
- supervisor engine
- remote-channel adapters
- dashboard/status model
- retry/reroute scaffolding

### Repo adapter

Each project should provide:

- branch/PR policy
- required CI checks
- validation/test commands
- plan/review doc locations
- issue labels and routing policy
- scope conventions
- prompt/profile overrides

The long-term shape should allow this repo to remain the first production user
while the orchestration core can later be extracted or templated for reuse.

### First intended consumers

The architecture should be designed from the start to serve at least three
consumers:

1. **This repo's infrastructure work**
   - the current steward / ops / review / issues workflow
2. **This repo's browser-game application work**
   - same orchestration core, but with repo-specific browser-game task and CI
     policy in the adapter layer
3. **A second coding or research repo**
   - proving the orchestration core is actually portable

## Core Versus Adapter Boundary

This boundary must be enforced from the start.

### Core platform

Belongs in the reusable orchestration layer:

- lane/session registry
- worker-pool manager
- communication/message bus
- supervisor routines
- remote-channel adapters
- dashboard/status model
- prompt/skill contracts
- retry/reroute scaffolding
- idle-notification and acknowledgement flow

### Repo adapter

Belongs in repo-specific policy:

- required CI checks
- branch/merge policy
- validation commands
- review-plan locations
- issue labels/project routing
- scope conventions
- prompt/profile overrides
- any Bid-Euchre / Arc D / browser-game specific logic

### Guardrail

Anything tied to Arc D, notebook/report lineage, browser-game implementation
details, or Bid Euchre domain specifics must remain in the adapter layer. The
core must not import those assumptions directly.

## PR Roadmap

The roadmap below is the rough slice guide after PR-5 closeout. It is designed
to make future handoff generation easy: each PR has a stable name, scope, and
dependency boundary.

### Entry criteria

Treat the following as prerequisites before Platform-1 begins.
The full checklist is at `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`.

- [x] **PR-5 closed** (2026-03-20) — all slices complete: #1054, #1068,
  #1091, #1098, #1104, #1112
- [x] `ops.py status` is trustworthy enough to support dashboard-first work
- [x] worktree/session registry behavior is stable enough to extend rather
  than re-litigate
- [x] **review surfaces dialed in** — Platform-1 must not begin on top of
  unstable PR-review plumbing:
  - [x] `reviewing-changes` remains the merge-relevant gate
  - [x] `claude-review` remains visible without poisoning CI
  - [x] Codex Cloud proving-run behavior is recorded accurately
  - [x] PR comment ingestion bridge lands so Codex Cloud comments are
    operationally visible (not speculative check/status plumbing) — shipped
    in #1122
- [x] **repo-bounded filesystem access** is the default, with only narrow
  managed exceptions and explicit operator approval for outside-repo access
  — shipped in #1115 (`src/bid_euchre/ops/fs_boundary.py`)

> **Bridge gate satisfied (2026-03-21).** All items resolved. See
> `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md` for the full entry checklist.
> Platform-1 (Step 3) is now open.

### Sequencing principle

This initiative must preserve the original non-blocking rule:

- browser-game and other product/application work should be able to **benefit
  from** early platform slices as they land
- they should not be forced to wait for Platform-1 through Platform-14 to be
  fully complete before meaningful implementation can proceed

The orchestrator platform is an enabling layer, not a prerequisite wall.

### Early-consumer mapping

| Batch | Primary consumer value |
|------|-------------------------|
| Batch A (`Platform-1`) | Better lane identity and resume semantics for current infra work; low direct browser-game value by itself |
| Batch B (`Platform-2` + `Platform-3`) | Browser-game and other in-repo implementation can start benefiting from orchestrated intake, durable handoff, clearer delegation, and the primary PR review substrate (review requests, verdicts, merge-safety state) |
| Batch C (`Platform-4` + `Platform-5`) | Browser-game Phase 0-3 style work can use dashboard-first supervision and prompt-first author/review flows daily |
| Batch D (`Platform-6` + `Platform-7`) | Sustained multi-lane application work benefits from automatic supervision, worker reuse, and bounded scaling |
| Batch E (`Platform-8` + `Platform-9`) | Remote supervision helps longer-running game/app sprints but is not a prerequisite for starting browser-game work |
| Batch F (`Platform-10` + `Platform-11`) | Portability and learning-loop value mainly benefits future repos and later-stage reuse |
| Batch G (`Platform-12` + `Platform-13`) | Cross-model review/maintenance (extending Platform-3's review substrate with second-model service lanes) plus second-project validation strengthen long-run confidence and portability |
| Batch H (`Platform-14`) | Hardening and closeout consolidate the platform after the major capabilities have landed |

### Platform PRs

| PR | Goal | Depends on | Can parallelize with |
|----|------|------------|----------------------|
| `Platform-1` | Lane/session registry foundation | PR-5 closeout or near-closeout | none |
| `Platform-2` | `orchestrator` lane and task-intake contract | Platform-1 | partial overlap with Platform-3 docs only |
| `Platform-3` | Communication bus v1, structured work packets, and primary PR review substrate (review request/verdict state, merge-safety gate) | Platform-1 | partial overlap with Platform-2 prompt/docs work |
| `Platform-4` | Dashboard-first steward session | Platform-1, Platform-2 | partial overlap with Platform-5 prompt authoring |
| `Platform-5` | Canonical lane prompts and first skill set | Platform-2, Platform-3 | partial overlap with Platform-4 |
| `Platform-6` | `ops` supervisor routines and delta summaries | Platform-3, Platform-4 | partial overlap with Platform-7 if write scopes are split |
| `Platform-7` | Background worker-pool management and bounded dynamic author scaling | Platform-1, Platform-2, Platform-3 | partial overlap with Platform-6 |
| `Platform-8` | Remote operator channel v1 (Telegram-first, Discord-compatible) | Platform-3, Platform-6 | none |
| `Platform-9` | Idle-attention notifications and bounded remote reply handling | Platform-8 | none |
| `Platform-10` | Portability layer: core vs repo adapter split | Platform-3 through Platform-7 reasonably stable | none |
| `Platform-11` | Skill learning loop: suggestion, review, and bounded refinement | Platform-5, Platform-10 preferred | none |
| `Platform-12` | Cross-model review and maintenance service lanes | Platform-3, Platform-5, Platform-6 | none |
| `Platform-13` | Second-project validation / extraction proof | Platform-10 through Platform-12 reasonably stable | none |
| `Platform-14` | Hardening, cleanup, migration docs, and residual closeout | Platform-1 through Platform-13 | none |

### Recommended dependency batches

#### Batch A: foundation

- `Platform-1`

#### Batch B: orchestration substrate

- `Platform-2`
- `Platform-3`

These can overlap a little in docs/contracts, but avoid overlapping writes to
the same registry/message modules.

#### Batch C: visible operating model

- `Platform-4`
- `Platform-5`

These define what the human and lane prompts actually experience.

### Roadmap reassessment gate

After Batch C lands, review actual delivered PR count, corrective follow-up
rate, and browser-game adoption value before continuing unchanged into Batches D
through G. If the roadmap is materially behind or the boundaries are proving
wrong, split or rescope the remaining initiative instead of letting it expand
silently.

#### Batch D: autonomy and supervision

- `Platform-6`
- `Platform-7`

These should land only after the message and prompt contracts are real.

#### Batch E: remote channel

- `Platform-8`
- `Platform-9`

Do Telegram first unless a shared-team Discord requirement appears earlier.

#### Batch F: portability and learning loop

- `Platform-10`
- `Platform-11`

#### Batch G: second-model service lanes and second-project validation

- `Platform-12`
- `Platform-13`

#### Batch H: hardening

- `Platform-14`

### Batch Pass Gates

Each batch should clear a concrete pass gate before the plan treats the next UX
shift or larger autonomy step as trustworthy.

#### Batch A pass gate

- lane/session identity survives restart without lane collisions
- resume-by-name works in a live steward smoke check
- `ops` can summarize worker visibility from registry state without pane
  guesswork

#### Batch B pass gate

- `orchestrator` can take one real task, preview the proposed delegation prompt
  or task packet, receive approval/edit/redirect, and dispatch it successfully
- one real task thread can be replayed end to end from durable state rather
  than reconstructed from terminal history
- one real author-lane completion is acknowledged back into durable
  coordination state
- one real PR review request is stored durably as a `ReviewRequest`, receives
  a `ReviewVerdict`, and drives merge-safety state without relying on
  hook-coupled subprocess parsing

#### Batch C pass gate

- the dashboard-first steward layout is usable for daily supervision
- one real PR goes through the new prompt-first orchestrator/review flow
  successfully
- the user can supervise ordinary work without keeping all author panes
  foregrounded

#### Batch D pass gate

- `ops` delta summaries are reliable enough to drive intervention decisions
- worker reuse/open-on-demand behavior works in a live multi-lane proving run
- stale/blocked/degraded lane handling is auditable and does not require pane
  archaeology

#### Batch E pass gate

- one real away-from-keyboard idle-attention flow reaches Telegram/Discord (or
  the approved fallback adapter) successfully
- acknowledgements and bounded replies are recorded durably
- dedupe/backoff prevents noisy alert spam in a proving run

#### Batch F pass gate

- at least one repo adapter boundary is exercised outside the initial infra
  path
- bounded skill learning can propose a reusable workflow without bypassing
  review, context-safety, or rollback controls

#### Batch G pass gate

- second-model service lanes operate advisory-first without becoming flaky
  hidden blockers
- one second-project or second-subproject validation run proves the
  core-vs-adapter split is real

#### Batch H pass gate

- migration docs reflect the actual working operator model
- no remaining critical plan or runtime-contract gaps block normal use of the
  platform
- the platform can be handed off without relying on chat-history-only context

### Practical delivery expectation

At current shipping rates:

- **PR-5 closeout** is the part that can plausibly be pushed through in about
  one to two focused days if review churn stays low.
- **This governed platform plan** is a larger follow-on stack. Even with low
  churn, it is a multi-day / multi-batch effort and should not be treated as a
  single rapid push.

### Adoption expectation

Do not wait for final closeout before using the platform. The expected rollout
pattern is:

- land a batch
- let browser-game or other in-repo development consume the new capability
- observe friction and tighten the core/adapter split
- continue with the next batch

## Real-World Proving Runs

The platform should not advance only on unit tests and design review. Each
major batch should be exercised through live steward usage that proves the
workflow actually works under realistic conditions.

### Core proving runs

- **Single-task proving run**
  - one real task enters through `orchestrator`, is delegated, executed, and
    closed out with durable state
- **Parallel two-author proving run**
  - two real tasks run at once with distinct ownership and visible supervision
- **PR / review / CI proving run**
  - one real PR moves through author -> review -> CI -> resolution using the
    new operating model and Platform-3 review substrate (durable review
    request/verdict state, merge-safety gate)
- **Restart / resume proving run**
  - an interrupted lane or session is resumed from durable state rather than
    reconstructed manually
- **Blocked / stale / recovery proving run**
  - one deliberately stalled or blocked scenario exercises supervisor
    detection, recommendation, and recovery handling
- **Remote-away-from-keyboard proving run**
  - one real idle-attention notification and acknowledgement path succeeds
    through the remote operator channel

### Later proving runs

- **Skill-learning proving run**
  - one repeated workflow becomes a reviewed reusable skill without bypassing
    safety checks
- **Second-model advisory proving run**
  - one Codex-or-equivalent reviewer/maintainer task succeeds without becoming
    a hidden blocker
- **Second-project portability proving run**
  - one non-Bid-Euchre consumer uses the orchestration core through an adapter

### Proving-run evidence

Each proving run should leave:

- a concise written outcome
- validation commands run
- unhappy-path coverage exercised
- known gaps / follow-ups
- enough durable state that another agent can inspect what happened later

## User Migration Checkpoints

This section defines **when you should change your own UX/workflow**, rather
than only what the agents should build.

### Current state (before Platform-1)

You should continue to use the current steward baseline:

- visible author lanes are normal
- no `orchestrator`-first intake yet
- remote Telegram/Discord supervision is not yet part of daily workflow
- direct inspection of author panes is still expected
- do not change normal UX on the basis of target architecture alone; wait for
  the relevant proving runs and pass gates

### After `Platform-1` to `Platform-3`

Expected user change:

- still use the existing steward layout for normal work
- begin trusting lane/session identity and resume-by-name semantics
- start treating lane communication and coordination as durable repo state, not
  just pane history
- expect `orchestrator` to preview non-trivial delegation prompts before
  sending them to author lanes

Not yet expected:

- switching fully to `orchestrator` as the only intake
- hiding author lanes by default
- relying on Telegram/Discord as part of normal supervision

Gate:

- do not treat this as the default workflow until Batch B proving runs pass

### After `Platform-4` and `Platform-5`

This is the first major UX shift.

Expected user change:

- use the dashboard-first steward session as the default visible layout
- submit normal new work to `orchestrator`
- review and approve or edit non-trivial author delegation prompts before
  dispatch
- treat `author-*` as worker lanes you inspect only when needed
- begin relying on canonical prompts/skills rather than direct command
  choreography

At this point, the normal visible lanes should be:

- `dashboard`
- `orchestrator`
- `ops`
- `review`
- optional `issues`

Gate:

- do not make dashboard-first / orchestrator-first the default until Batch C
  proving runs pass

### After `Platform-6` and `Platform-7`

Expected user change:

- rely on `ops` for delta summaries and attention routing rather than frequent
  manual polling
- let the orchestrator assign and reuse author workers automatically
- expect author panes to open or resume on demand when work is delegated, then
  return to background or hidden state when no drill-down is needed
- inspect authors mainly for drill-down, intervention, or debugging

Gate:

- do not hide author panes by default until Batch D proving runs pass

### After `Platform-8` and `Platform-9`

This is the second major UX shift.

Expected user change:

- adopt Telegram and/or Discord as a normal part of supervision
- expect 5-minute idle-attention notifications when away from the machine
- use bounded remote replies/commands for acknowledgement and lightweight
  direction

At this point, remote supervision is part of the intended default workflow,
not an experiment.

Gate:

- do not treat remote supervision as a normal required workflow until Batch E
  proving runs pass

### After `Platform-10` to `Platform-14`

Expected user change:

- little day-to-day UX change inside this repo
- the main shift is architectural: the system should now be portable enough to
  reuse elsewhere
- browser-game and future repos should be able to consume the same core model
  with different adapters

## Handoff-Friendly Slice Definitions

These are the short names future handoffs should use.

### `Platform-1` — Lane Registry Foundation

- strengthen lane/session registry
- add resume-by-name
- add worker visibility summary fields
- no remote channel or worker scaling yet
- done when:
  - lane metadata persists durably enough to support resume-by-name smoke checks
  - `ops` can summarize worker visibility from registry state without tmux
    guesswork

### `Platform-2` — Orchestrator Intake

- add `orchestrator` lane/profile
- define task intake and task packet contract
- add prompt-preview / approval flow for non-trivial author delegation
- delegate to existing author lanes
- no message bus yet beyond minimal durable handoff contract
- done when:
  - a user request can be converted into a durable task packet with owner,
    scope, and validation requirements
  - `orchestrator` can show the proposed author-lane prompt/task packet to the
    user and capture approve/edit/redirect before dispatch for non-trivial work
  - `orchestrator` can assign that packet to an existing author lane and record
    acknowledgment/completion without manual pane inspection

### `Platform-3` — Communication Bus V1 And Primary PR Review Substrate

- define message schema
- add inbox/outbox storage
- add durable lane-to-lane message logging
- add query surface for unresolved items
- **primary PR review architecture:**
  - durable review request / verdict state (extends the `ReviewRequest` /
    `ReviewVerdict` models introduced in the review queue substrate, #1176)
  - merge-safety gate driven by verdict state, not hook-coupled subprocess
    parsing
  - review status as a first-class communication bus participant
  - `SendMessage`-style lane delivery is **not** required here — it is a
    later convenience layer on top of the durable review bus, not the source
    of review truth
- expected shape:
  - likely `Platform-3a` schema/logging
  - `Platform-3b` inbox/query surface
  - `Platform-3c` delivery semantics and hardening
  - `Platform-3d` review request/verdict state and merge-safety gate
- done when:
  - durable messages can be stored, queried, and replayed locally without
    relying on transient pane history
  - acknowledgement, retry, TTL, and dead-letter behavior are defined and
    covered by at least one unhappy-path test each
  - review requests and verdicts are stored durably and drive the merge-safety
    gate without relying on hook-coupled subprocess parsing or transient
    terminal output

### `Platform-4` — Dashboard-First Steward

- rework visible steward layout
- foreground `dashboard`, `orchestrator`, `ops`, `review`, optional `issues`
- background authors summarized rather than foregrounded
- done when:
  - the default visible steward layout no longer requires author panes to stay
    foregrounded for ordinary supervision
  - hidden-by-default author lanes remain easy to inspect or resume by name
  - the dashboard surface can answer who owns what and what needs attention

### `Platform-5` — Canonical Prompts And Skills

- lane prompts for `orchestrator`, `ops`, `review`, `author`, `issues`
- first named workflow skills
- prompt-first user interaction docs
- done when:
  - each lane has one canonical prompt/profile with bounded responsibilities
  - at least one repeated workflow per major lane class is captured as a named
    skill or prompt wrapper

### `Platform-6` — Supervisor Routines

- `ops` delta summaries
- escalation/recovery recommendations
- attention routing into orchestrator/human surfaces
- done when:
  - `ops` can emit delta-only summaries over repo state and PR/CI state
  - retry/reroute/escalation recommendations are durable and auditable

### `Platform-7` — Worker Pool Manager

- idle worker reuse
- bounded dynamic author creation
- worker parking/retirement
- worker-pool dashboard state
- open/resume author panes on delegation and return them to background/hidden
  state when idle
- note:
  - if scaling and retirement logic do not fit cleanly, this slice may land as
    two PRs under the same parent label
- done when:
  - `orchestrator` can reuse idle authors before creating new workers
  - a delegated task can cause the needed author lane to open or resume on
    demand without requiring all author panes to be pre-opened
  - dynamic worker creation and retirement obey repo-owned concurrency and
    cleanup limits

### `Platform-8` — Remote Operator Channel

- Telegram-first plugin path
- Discord-compatible contract
- notifications and bounded remote commands
- done when:
  - one remote channel can deliver summarized alerts and accept bounded replies
  - the implementation path is validated against either an official plugin or a
    documented repo-owned fallback adapter

### `Platform-9` — Idle Attention Flow

- 5-minute idle threshold
- dedupe/backoff
- acknowledgement handling
- reply-to-message -> bounded inbound command mapping
- done when:
  - idle-attention alerts are deduplicated and rate-limited
  - an acknowledgement or bounded reply can be recorded back into the durable
    coordination state

### `Platform-10` — Portability Layer

- define reusable core vs repo adapter
- move repo-specific assumptions behind config/contracts
- document adapter surface
- done when:
  - new orchestration code depends on adapter contracts rather than
    Bid-Euchre-specific paths or docs
  - the refactor scope for existing `src/bid_euchre/ops/` assumptions is
    documented and materially reduced

### `Platform-11` — Skill Learning Loop

- add bounded skill suggestion/promotion pipeline
- capture repeated successful workflows
- support reviewed skill refinement
- done when:
  - repeated successful workflows can produce skill suggestions with provenance
  - promotion/refinement cannot bypass review, context-safety, and rollback
    gates

### `Platform-12` — Cross-Model Review And Maintenance

> **Relationship to Platform-3:** Platform-3 owns the primary PR review
> architecture — durable review request/verdict state and the merge-safety
> gate. Platform-12 extends that substrate by adding second-model service
> lanes (Codex or equivalent) that operate as advisory participants on top
> of the same durable review bus. Platform-12 does not redefine the review
> truth model; it adds cross-model execution as a consumer of it.

- add bounded `codex-review` service lane
- add optional `codex-maint` bounded maintenance lane
- route work through task packets and durable messages, not hook-coupled local
  subprocess loops
- keep second-model execution advisory-first with circuit breakers and degraded
  service-lane states
- done when:
  - a second-model reviewer can consume assigned review work and emit durable
    findings without becoming a hidden blocking loop
  - second-model findings are recorded as verdicts in the Platform-3 review
    substrate, not as a separate review truth model
  - second-model failures degrade into explicit service-lane health signals
    rather than silent stalls

> **Interim Codex overlay path (2026-03-20):** Codex may still be used before
> `Platform-12`, but the proving run showed Codex Cloud currently landing as PR
> issue comments from `chatgpt-codex-connector[bot]`, not as checks, statuses,
> or PR review objects. That means the near-term path is a small
> comment-ingestion / trusted-command bridge after PR-5 if needed, not a
> speculative advisory-check integration. The following constraints apply:
>
> 1. It must be **advisory-only** — not merge-blocking.
> 2. It must **not** revive the old local Codex subprocess review loop as the
>    primary review architecture.
> 3. If the repo wants Codex surfaced operationally before `Platform-12`, use
>    explicit comment ingestion for trusted bot comments rather than pretending
>    they are checks or PR review objects.
> 4. Any interim Codex overlay should later be migrated into or aligned with the
>    durable service-lane contract defined by `Platform-12`.

### `Platform-13` — Second-Project Validation

- validate against another coding repo or clearly separate subproject mode
- prove the adapter boundary is real
- done when:
  - a second project can adopt the core orchestration model without copying the
    entire Bid-Euchre control plane
  - at least one adapter seam is validated against a real non-Bid-Euchre use

### `Platform-14` — Hardening And Closeout

- cleanup, docs consolidation, migration notes
- remaining residual fixes
- done when:
  - known residual gaps are either closed or explicitly deferred with owner and
    rationale
  - the migration guidance is good enough for another agent to operate the
    platform without reconstructing intent from chat history

## Instrumentation Ownership

The metrics in "Things To Track While Building" should be introduced in slices
that naturally produce them rather than deferred to a vague future dashboard:

- `Platform-1`
  - lane/session registry mismatch count
  - worker resume success rate
- `Platform-3`
  - message backlog size
  - unresolved blocker count
  - review request → verdict latency
  - merge-safety gate accuracy (false blocks, missed blocks)
- `Platform-6`
  - manual interventions per PR
  - stale-lane false positive rate
  - median blocker age
- `Platform-8` and `Platform-9`
  - duplicate/ignored remote notifications
  - time-to-acknowledgement for human-needed decisions
- `Platform-11`
  - skill suggestion volume
  - promoted skill acceptance rate
  - post-promotion rollback rate
- `Platform-12`
  - second-model invocation success rate
  - structured-output / parse success rate
  - duplicate-finding rate versus deterministic prechecks or primary review
  - circuit-breaker trip count

## 8. Risks

These are the highest-risk failure modes during implementation.

1. **Orchestrator overload**
   - Risk: `orchestrator` becomes both dispatcher and executor.
   - Mitigation: keep execution in `author-*`; orchestrator coordinates only.

2. **Chat becomes source of truth**
   - Risk: Telegram/Discord or lane transcripts drift from repo/runtime state.
   - Mitigation: messages are transport; repo state and GitHub remain canonical.

3. **Worker-pool sprawl**
   - Risk: dynamic author lanes recreate untracked worktree chaos.
   - Mitigation: hard concurrency caps, TTLs, registry enforcement, cleanup policy.

4. **Hidden background activity**
   - Risk: too much off-screen behavior makes the system hard to trust.
   - Mitigation: durable message logs, dashboard summaries, audit queries, disable paths.

5. **Notification spam**
   - Risk: idle alerts and remote summaries become noisy and ignored.
   - Mitigation: high-signal summaries only, dedupe, backoff, severity thresholds.

6. **Weak portability boundary**
   - Risk: the "core" quietly imports Bid-Euchre-specific policy and becomes unportable.
   - Mitigation: explicit core-vs-adapter code ownership and contract tests.

7. **Resume-by-name ambiguity**
   - Risk: stale or duplicate session identities route work to the wrong lane.
   - Mitigation: durable session handles, unique lane ids, restart-safe registry semantics.

8. **Prompt drift**
   - Risk: lane prompts evolve inconsistently and stop matching runtime expectations.
   - Mitigation: canonical prompt files, validation checks, and prompt/skill docs under review.

9. **Message schema drift**
   - Risk: lanes produce incompatible coordination messages over time.
   - Mitigation: explicit message schema, backward-compat tests, and storage contract tests.

10. **Remote command overreach**
    - Risk: Telegram/Discord replies become an unsafe backdoor for destructive actions.
    - Mitigation: bounded command set, explicit authn/authz, confirmation policy, and audit logging.

11. **Unreviewed self-improvement**
    - Risk: autonomous skill generation drifts into unsafe or low-quality default behavior.
    - Mitigation: suggestion-first flow, provenance requirements, review gates, and staged activation.

12. **Credential sprawl**
    - Risk: bot tokens, repo tokens, and model/provider credentials are scattered across lanes and hosts.
    - Mitigation: explicit credential ownership model, least-privilege access, and documented secret locations.

13. **Reviewer/fixer recoupling**
    - Risk: a second-model reviewer is reintroduced through a tight local
      review -> auto-fix -> re-review subprocess loop and recreates the old
      flakiness.
    - Mitigation: advisory-first service lanes, durable task packets, explicit
      circuit breakers, and separation between reviewer and maintainer roles.

## Things To Track While Building

Track these as leading indicators that the system is simplifying the workflow
rather than just adding machinery.

- number of active author workers
- idle vs busy worker utilization
- unresolved blocker count
- median blocker age
- time-to-acknowledgement for human-needed decisions
- number of manual interventions per PR
- number of corrective follow-up PRs
- duplicate/ignored remote notifications
- skill suggestion volume
- promoted skill acceptance rate
- post-promotion rollback rate
- second-model invocation success rate
- second-model parse / structured-output success rate
- duplicate finding rate from second-model review
- second-model circuit-breaker trip count
- stale-lane false positive rate
- worker resume success rate
- lane/session registry mismatch count
- issue triage dedupe rate
- how often users bypass `orchestrator` and talk directly to authors

## Suggested Implementation Sequence

Build in this order:

1. close PR-5 rollout work
2. `Platform-1`
3. `Platform-2` + `Platform-3`
4. `Platform-4` + `Platform-5`
5. `Platform-6` + `Platform-7`
6. `Platform-8` + `Platform-9`
7. `Platform-10` + `Platform-11`
8. `Platform-12` + `Platform-13`
9. `Platform-14`

## Validation Requirements

Each slice should include:

- automated tests for new runtime/state logic
- manual steward-environment smoke checks
- at least one unhappy-path / failure-injection check
- rollback/disable path
- known gaps

Additional platform-specific validation:

- resume-by-name smoke checks
- idle-notification dedupe tests
- remote channel acknowledgement tests
- worker-pool scaling safety checks
- communication log replay / audit checks
- applicable real-world proving runs for the current batch

## 9. Success Criteria

- The user gives normal work only to `orchestrator`.
- `author-*` lanes run as a background worker pool.
- `ops` reports deltas and attention, not raw command output.
- `review` and `issues` act as service lanes, not user-facing intake points.
- Telegram/Discord can notify the user after 5 minutes of unattended required attention.
- The remote operator channel is a normal part of the workflow rather than an optional side path.
- Important lane-to-lane communication is durable and queryable.
- Repeated successful workflows can be turned into reviewed, reusable skills without bypassing safety gates.
- A second-model reviewer/maintainer lane can operate in the background without
  recreating the old flaky hook-coupled review loop.
- The system can later be adapted to another coding repo without cloning the entire Bid-Euchre-specific control plane.

## Outcome

_To be filled after implementation._

- Result: ACTIVE
- PRs: --
- Notes:
  - Governing-plan scaffold created on 2026-03-19.
  - PR-5 closed on 2026-03-20; all slices complete.
  - Post-PR-5 bridge gate satisfied (2026-03-21): filesystem boundary
    (#1115), PR comment ingestion (#1122), and related hardening all landed.
    Platform-1 is now open.
  - Entry checklist published at `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`.
