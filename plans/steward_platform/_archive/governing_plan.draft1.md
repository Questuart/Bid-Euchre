# Steward Platform — Governing Plan

**Date:** 2026-04-22
**Status:** PROPOSED
**Scope:** Evolve the current single-repo steward control plane into a Claude Code-native, multi-project desktop platform with per-project steward cells, a meta orchestrator, `cmux` operator UX, Phoenix-backed observability, durable learning, and shared planning / prompt / knowledge contracts across repos.
**Supersedes:** [Agentic Orchestration Platform — Governing Plan](../agent_ops/governing_plan.md) for future steward-platform direction. The prior `agent_ops` plan remains the historical source for shipped Phase 0-4 platform work and partial Phase 5 portability/learning work.

---

## 1. Decision

Build the next steward initiative as a Claude Code-native platform shell,
coordination layer, and learning layer rather than as a new general-purpose
agent runtime. The platform should use Claude Code, tmux, and repo-local state
as the execution substrate; `cmux` as a first-class operator UI and control
surface; Phoenix as the phase-one observability and evaluation sidecar; and
repo-local plus meta-level knowledge bases, archivists, and prompt-policy
layers to improve orchestration quality over time. The platform must support
multiple selected project repos concurrently, keep each project cell
operationally isolated, and standardize planning, prompts, tracing, and
knowledge structures across `Bid-Euchre`, `Fund`, and `RIN SnD`.

## 2. Goals

1. Build a meta steward layer that can select, launch, supervise, and steer multiple project steward cells concurrently.
2. Standardize a reusable project-cell contract with always-on `orchestrator`, `ops`, and `review` lanes plus off-by-default `author-*` and `analyst-*` specialist lanes.
3. Finish the core-vs-adapter split so steward can run against additional repos without editing core ops code.
4. Make `cmux` a first-class operator shell from phase one without making it the source of operational truth.
5. Add durable learning loops through project archivists, a meta-archivist, Phoenix traces, incident/playbook ledgers, and startup briefings.
6. Establish project and meta knowledge bases with a shared skeleton, repo-specific content, and explicit promotion rules for cross-project lessons.
7. Standardize prompt-policy layering, shared planning artifacts, and role boundaries across repos so agentic development compounds instead of drifting.
8. Keep model/effort routing advisory until proven, while capturing the evidence needed to improve token efficiency over time.

## 3. Key Definitions

- **Claude Code-native platform**: a platform that assumes Claude Code sessions, hooks, memory, channels, prompt layering, and subagents as the primary local runtime primitives.
- **Meta steward / meta orchestrator**: the user-level supervisor that selects projects, boots project cells, loads cross-project memory and prompt-policy guidance, routes attention, and surfaces operator decisions.
- **Project steward cell**: one repo-local control domain with its own tmux session namespace, runtime state, adapters, hooks, inboxes, and knowledge assets.
- **Platform contract**: the shared runtime, planning, prompt, trace, and knowledge skeleton that every steward-enabled repo must implement.
- **Project archivist**: the repo-local learning lane that turns session evidence into incidents, lessons, playbooks, archives, and candidate workflow improvements.
- **Meta-archivist**: the cross-project learning lane that reads project outputs plus Phoenix traces and promotes generalized lessons, operator briefings, and platform policy candidates into the meta layer.
- **Analyst lane**: a shaping and investigation lane whose primary outputs are findings, issue packages, plans, diagnostics, comparisons, or recommendations; it does not own merge-oriented implementation work by default.
- **Author lane**: an implementation lane whose primary outputs are merge-oriented code/doc changes, validation evidence, and PR-ready artifacts; it does not own broad investigative work by default.
- **Promotion flow**: the explicit lifecycle from raw evidence to candidate lesson to confirmed project knowledge to cross-project knowledge or policy candidate.
- **Knowledge base (KB)**: the versioned markdown-first corpus of repo-local or cross-project facts, incidents, lessons, playbooks, indexes, and curated archives maintained agentically over time.
- **Actionable surface**: an operator briefing, issue queue, incident page, playbook, policy candidate, or other artifact that changes future steering; traces and logs without such a surface are insufficient.

## 4. Execution Structure

### 4.1 Phases / Milestones

| Phase | Directory | Description | Depends On |
|-------|-----------|-------------|------------|
| 0 | `0_contract_and_baseline` | Define the steward-platform contract, migration baseline, canonical schemas, and proving targets | Existing `agent_ops` platform assets |
| 1 | `1_reference_cell` | Normalize `Bid-Euchre` into the reference project cell, including prompts, KB scaffold, archivist flow, and Phoenix export | Phase 0 |
| 2 | `2_meta_supervisor_and_cmux` | Add the meta steward home, project registry, project selection, `cmux` workspaces/surfaces, and operator-facing control surfaces | Phase 1 |
| 3 | `3_learning_and_actionability` | Add project archivists, meta-archivist, startup briefings, issue surfacing, periodic audits, and workflow-improvement loops | Phases 1-2 |
| 4 | `4_cross_repo_rollout` | Port the contract into `Fund` and `RIN SnD`, prove repo isolation, and validate shared planning/prompt/KB structures | Phases 0-3 |
| 5 | `5_specialist_activation_and_routing` | Add on-demand `author-*` / `analyst-*` activation, bounded parking/retirement, and evidence-backed advisory model/effort routing | Phases 1-4 |
| 6 | `6_closeout_and_hardening` | Close portability debt, harden operator UX, finalize migration docs, and resolve remaining rollout gaps | Phases 1-5 |

### 4.2 Step Template (per phase)

Each phase follows this standard sequence:

1. **Scope lock**
   - **Commands:** read root `CLAUDE.md`, this governing plan, the active phase plan/checkpoints, relevant ADRs, and any active sub-plans.
   - **Validates:** the slice boundary, repo-specific overlay, and acceptance criteria are explicit before implementation starts.
   - **Error recovery:** if the slice needs new architecture decisions, create an ADR or record an open item before widening scope.
   - **Outputs:** scope lock note, updated checkpoint target, and any new sub-plan/ADR registration.
2. **Contract check**
   - **Commands:** inspect the platform contract, prompt-policy registry, KB skeleton spec, trace schema, and repo adapter contract.
   - **Validates:** the slice conforms to the shared skeleton instead of inventing repo-local structure.
   - **Error recovery:** if the contract is insufficient, amend the contract first or leave a blocking open item.
   - **Outputs:** contract references in the phase log and any required contract deltas.
3. **Implementation**
   - **Commands:** targeted edits, focused tests, Phoenix smoke wiring where relevant, and repo-local runtime/config changes defined by the slice.
   - **Validates:** the work stays inside the declared write scope and preserves repo isolation plus the steward-native event model.
   - **Error recovery:** record blockers or follow-on work rather than silently expanding the slice.
   - **Outputs:** code, docs, prompt/rule/skill assets, KB scaffolding, or runtime wiring for the slice.
4. **Verification**
   - **Commands:** targeted automated tests, manual steward smoke checks, at least one unhappy-path check, and phase-specific validation commands.
   - **Validates:** the slice meets its done-when criteria, produces actionable operator surfaces, and preserves rollback/disable paths.
   - **Error recovery:** tighten the slice, add missing tests, or leave the step `BLOCKED` with a precise next action.
   - **Outputs:** validation evidence recorded in checkpoints, PR notes, or sub-plan outcomes.
5. **Learning / handoff**
   - **Commands:** update checkpoints, KB or archive artifacts if promoted, prompt-policy candidates if warranted, and any issue/improvement backlog items.
   - **Validates:** future agents can resume from durable state rather than reconstructing intent from transcripts.
   - **Error recovery:** if promotion quality is unclear, leave the artifact at `candidate` rather than forcing promotion.
   - **Outputs:** durable handoff state, archivist inputs, and updated learning surfaces.

### 4.3 Phase 0 Dependencies

Before Phase 0 starts:

- Existing `agent_ops` Phase 0-4 assets remain usable and should be treated as implementation substrate, not discarded work.
- The paused `agent_ops` portability/learning work is the baseline for portability and token-routing debt, not a closed problem.
- The current `ops.py` CLI, task queue, message bus, attention broker, worker pool, role prompts, and tmux bootstrap scripts are available for adaptation.
- `Bid-Euchre` remains the reference repo and initial proving ground.
- The dedicated meta steward home/repo exists or is created as part of Phase 0.

## 5. Sub-Plan Governance

Sub-plans are required for implementation-heavy work, multi-file contract
changes, repo-rollout slices, or any step where this governing plan leaves
material design choices open.

### 5.1 Sub-Plan Registry

Maintained in: `plans/steward_platform/sub_plan_registry.md`

Each sub-plan entry tracks:

| Field | Description |
|-------|-------------|
| `id` | Stable identifier: `SP-<phase>-<seq>` |
| `parent` | Parent plan section or phase reference |
| `status` | `proposed`, `in_progress`, `blocked`, `completed`, `abandoned`, `superseded` |
| `owner` | Agent session ID or human owner |
| `repo_scope` | `meta`, `bid-euchre`, `fund`, `rin-snd`, or multi-repo |
| `file` | Path to the sub-plan document |

### 5.2 When to Create a Sub-Plan

- The step changes more than three files
- The step introduces or changes runtime behavior
- The step changes the shared contract or repo adapter boundary
- The step changes prompts, skills, rules, or KB structure in a way that affects future agent behavior
- The step spans multiple repos or requires migration sequencing

### 5.3 Sub-Plan Lifecycle

`proposed -> in_progress -> completed`

`in_progress -> blocked -> in_progress`

`any -> abandoned | superseded`

## 6. Checkpoint Contract

Each phase maintains a checkpoint file at:
`plans/steward_platform/<phase>/checkpoints.md`

Checkpoint entries must capture:

- active slice and next action
- validation performed
- current blockers and open items
- promotion state for any lessons or policies affected by the slice
- rollout state across `Bid-Euchre`, `Fund`, and `RIN SnD` when relevant

## 7. Evidence / Output Contract

Every phase must produce:

- code/docs/runtime changes scoped to one slice
- targeted automated tests for new logic
- manual steward smoke checks
- at least one unhappy-path / failure-injection check where meaningful
- operator-facing evidence that the slice yields an actionable surface
- rollback/disable path
- known gaps and follow-on work

The platform must favor evidence that is durable and inspectable:

- repo-local ledgers or JSON artifacts for steward-native truth
- Phoenix traces for span inspection, prompt inspection, and evaluation loops
- KB / incident / playbook artifacts for promoted learning
- checkpoints and ADRs for planning and governance state

## 8. Existing Platform Baseline And Adaptation Path

The current steward platform is not a greenfield starting point. The new
initiative should explicitly reuse and adapt the existing shipped pieces below.

### 8.1 Existing assets to reuse

- **Steward tmux bootstrap and lane layout**
  - `.claude/tmux/steward-session.sh`
  - current `orchestrator`, `ops`, `review`, `analyst-*`, `author-*`, browser, and flex lane concepts
- **Operator CLI and runtime surfaces**
  - `scripts/internal/ops.py`
  - status, dashboard, workers, task queue, inbox, memory, skills, supervisor, attention, and usage commands
- **Core-vs-adapter foundation**
  - `src/bid_euchre/ops/core/provider.py`
  - `src/bid_euchre/ops/core/interfaces.py`
  - `src/bid_euchre/ops/adapters/`
- **Durable tasking and routing metadata**
  - `src/bid_euchre/ops/task_queue.py`
  - existing `task_type`, `complexity_estimate`, `model_hint`, and `effort_hint` metadata contract
- **Messaging / attention improvements already landed**
  - `message_bus.py`, `attention.py`, `control_plane.py`, `events.py`
- **Existing role prompts and operating docs**
  - `.claude/agents/steward-*.md`
  - `plans/sessions/2026-03-24_steward-analyst-implementation-handoff.md`
- **Current memory, indexing, and audit trail primitives**
  - `memory.py`, `index.py`, `audit_trail.py`, `snapshots.py`, `skill_promotion.py`

### 8.2 Known gaps to close

- **Portability is not complete**
  - `docs/02_agent/PORTABILITY_MANIFEST.md` still records substantial hard-block and soft-coupling debt, led by `ops/worktrees.py` and `ops/token_economy.py`.
- **Token economy is not complete**
  - current routing metadata and fixed low-risk defaults exist, but the outcomes/advisor/evaluation loop is not yet closed.
- **Messaging is materially stronger but not fully proven**
  - the code and tests are strong, but the repo still records live proving and some closeout debt as incomplete.
- **Current lane layout is repo-specific and too large for the target model**
  - browser-domain and flex-domain worktree assumptions must be replaced by repo adapters and a standardized project-cell contract.
- **Current prompts and memory are useful but not standardized across repos**
  - the next platform must formalize a shared skeleton rather than carrying one repo’s conventions implicitly.

### 8.3 Adaptation rule

Default to adaptation before replacement. Existing ops surfaces, prompts, ledgers,
and launchers should be generalized, slimmed, or re-homed where necessary.
Replacement is justified only when an existing piece materially blocks the new
platform contract.

## 9. Target Architecture

### 9.1 Platform shape

The target platform has three persistent surfaces:

1. **Meta steward surface**
   - user-level supervisor
   - project selection and launch
   - cross-project attention routing
   - operator briefing and improvement backlog
2. **Project steward cells**
   - one per selected repo
   - separate tmux session per project
   - repo-local runtime truth
3. **Knowledge and learning surfaces**
   - per-project KB instances
   - meta-level KB
   - incidents, playbooks, lessons, archives, and prompt-policy candidates

### 9.2 Execution layers

1. **Execution substrate**
   - Claude Code sessions, hooks, channels, subagents, memory, and headless entrypoints
   - tmux as the durable process/session substrate
2. **Operator UX**
   - `cmux` from phase one
   - one workspace per project cell
   - metadata, notifications, browser surfaces, and operator-triggered actions
3. **Project cell**
   - repo-local tmux session namespace
   - always-on `orchestrator`, `ops`, `review`
   - on-demand `author-*`, `analyst-*`
   - repo-local adapters, queues, inboxes, ledgers, health surfaces, and KB
4. **Meta layer**
   - project registry
   - operator briefing
   - cross-project issue surfacing
   - prompt-policy loading
   - project-cell lifecycle control
5. **Learning layer**
   - project archivists
   - meta-archivist
   - Phoenix exporter and trace analysis
   - incidents, lessons, playbooks, routing outcomes, and workflow-improvement backlog

### 9.3 Truth model

- Repo-local runtime state = operational truth for a project cell
- Phoenix = primary observability and eval UI, not the canonical internal state model
- `cmux` = operator UI and action surface, not the canonical state store
- KB artifacts = promoted knowledge and steering surfaces, not raw evidence
- GitHub = PR / review / CI truth
- Meta steward home = canonical home for cross-project policy, planning skeleton, meta KB, and shared skills

### 9.4 Lane policy

- **Always on**
  - `orchestrator`
  - `ops`
  - `review`
- **Off by default**
  - `author-*`
  - `analyst-*`
- **Activation**
  - project orchestrator may activate specialist lanes under bounded rules with clear operator visibility
- **Retirement**
  - unused specialist lanes are parked or retired after idle thresholds
- **Routing principle**
  - analyst owns findings, diagnosis, plans, recommendations, issue shaping, and workflow-improvement suggestions
  - author owns implementation, tests/docs required for merge, and PR-ready changes

### 9.5 Knowledge architecture

Each repo has its own KB instance with a shared skeleton:

- `knowledge/wiki/`
- `knowledge/playbooks/`
- `knowledge/incidents/`
- `knowledge/lessons/`
- `knowledge/archives/`
- `knowledge/index/`
- `knowledge/raw/` for intentionally curated source material only

The meta steward home carries:

- `meta_knowledge/projects/`
- `meta_knowledge/cross_project_patterns/`
- `meta_knowledge/prompt_policy/`
- `meta_knowledge/operator_briefs/`
- `meta_knowledge/platform_incidents/`
- `meta_knowledge/playbooks/`
- `meta_knowledge/archives/`

Shared skeleton, separate instances, explicit promotion.

### 9.6 Prompt / rule / skill layering

- user-level meta `CLAUDE.md` for stable global steering
- user-level skills for reusable workflows such as archivist, planning, ADR, and execution-plan generation
- project `CLAUDE.md` for concise repo-wide constants only
- project rules for path/topic-specific behavior
- project skills for repo-local workflows and KB maintenance
- generated briefings for current incidents, lessons, and steering notes

`CLAUDE.md` files should stay concise; large or volatile guidance belongs in
rules, skills, or generated briefing artifacts.

### 9.7 Event and trace model

Steward keeps its own modular internal event model and exports it to Phoenix.
The canonical execution hierarchy is:

`project_cell -> session -> task -> lane_activity -> tool_call`

First-class IDs should include:

- `project_id`
- `cell_id`
- `session_id`
- `task_id`
- `lane_id`
- `trace_id`
- `incident_fingerprint`
- `prompt_policy_version`

### 9.8 Planning framework

The planning framework should have:

- one canonical source of truth in the dedicated steward platform home/repo
- mirrored copies in each project repo
- one shared section skeleton
- repo-specific rubric overlays

Shared artifacts include:

- governing plan template
- ADR template
- sub-plan template
- execution plan template
- checkpoint/completion template
- promotion/rollback template
- review rubric contract

## 10. Workstreams

1. **Platform contract**
   - runtime layout
   - lane taxonomy
   - adapter interface
   - event schema
   - KB skeleton
   - prompt-policy registry
   - planning skeleton
2. **Portability closeout**
   - remove remaining hard-block coupling
   - move lane/worktree/project naming into adapters
   - make the core reusable across repos without source edits
3. **Meta steward home**
   - dedicated repo/home for cross-project assets
   - project registry
   - shared skills/prompts/planning artifacts
4. **cmux-first operator UX**
   - workspace/surface contract
   - operator metadata, notifications, browser surfaces, and action bindings
5. **Project cell standardization**
   - always-on control lanes
   - off-by-default specialist lanes
   - repo adapter compliance
6. **Phoenix observability**
   - exporter from steward-native event model
   - trace/span inspection
   - prompt inspection
   - evaluation loops
7. **Archivist and actionable learning**
   - project archivists
   - meta-archivist
   - periodic system audits
   - issue/improvement backlog generation
8. **Prompt and policy system**
   - layered prompts/rules/skills
   - anti-pattern library
   - prompt-policy candidates and promotion
9. **Knowledge base system**
   - per-repo KB scaffold
   - meta KB
   - ingest/compile/query/update loop
10. **Specialist activation and token routing**
   - bounded specialist activation
   - parking/retirement
   - evidence-backed advisory model/effort routing

## 11. Risks

| Risk | Mitigation |
|------|------------|
| Existing portability debt causes the new platform to inherit repo-specific assumptions | Treat portability closeout as an explicit workstream and gate multi-repo rollout on adapter-owned naming/worktree/session behavior |
| `cmux` becomes an accidental source of truth | Keep all canonical state in steward/tmux/runtime ledgers; require UI rebind behavior after `cmux` restart |
| Phoenix integration leaks observability-tool assumptions into core state | Keep a steward-native event model and export to Phoenix rather than hard-coding Phoenix semantics internally |
| Memory or prompt-policy pollution causes worse steering over time | Use explicit promotion states, archivist roles, candidate-first policy changes, and operator-visible briefings |
| Repos diverge in planning or prompt structure | Keep the planning skeleton and prompt-policy contract canonical in the meta steward home and mirror into repos with version markers |
| More knowledge in git creates heavy repos and noisy diffs | Keep raw transcripts, raw trace exports, caches, embeddings, and scratch artifacts runtime-only; version promoted and navigable knowledge only |
| Specialist lanes overlap or thrash | Keep analyst vs author boundaries explicit, start specialist activation semi-automatic, and require operator-visible activation in early phases |
| Token-routing work overreaches before evidence exists | Keep routing advisory until measurements show improvement and continue to treat current token-economy work as incomplete |
| Platform generates passive logs without actionable surfaces | Require each trace/log/memory stream to map to an operator briefing, issue queue, incident page, playbook, or policy candidate |

## 12. Success Criteria

1. `Bid-Euchre`, `Fund`, and `RIN SnD` can all adopt the same steward-platform skeleton with repo-specific behavior isolated to adapters and overlays.
2. The operator can launch, inspect, and steer selected projects through `cmux` without relying on raw pane hunting for normal use.
3. Each project cell runs in its own tmux session with repo-local runtime truth and no cross-project contamination.
4. Project archivists and the meta-archivist produce actionable incidents, lessons, playbooks, operator briefings, and improvement items rather than passive trace archives.
5. The platform maintains repo-local and meta-level KBs with a shared skeleton, useful indexes, and promoted lessons that future agents can leverage.
6. Prompt-policy guidance is layered, concise, auditable, and effective at reducing repeated anti-patterns.
7. Phoenix traces provide useful span, prompt, and evaluation visibility without becoming the internal source of truth.
8. Specialist lane activation works under bounded policies and is visibly steerable by the operator.
9. The platform shows evidence that past lessons and surfaced improvements reduce repeated failures, wasted routing, or avoidable operator interventions.

## 13. Open Items

The following items are directionally resolved but not yet scoped tightly
enough to treat as closed implementation decisions:

1. **Meta steward home implementation**
   - Dedicated repo/home is selected, but the exact repository name, bootstrap method, and relationship to user-level `~/.claude/` assets still need to be specified.
2. **Phoenix deployment details**
   - Phoenix is in scope from phase one, but exact local deployment mode, retention policy, and trace export packaging are not yet defined.
3. **Planning skeleton sync mechanism**
   - Canonical planning assets should live in the steward platform home and be mirrored into project repos, but the sync/update mechanism and drift-reporting workflow are still open.
4. **Periodic audit cadence and ownership**
   - The system should use hooks/channels for ingestion plus scheduled audits for synthesis, but the default cadence and exact split between meta audits and project audits remain open.
5. **Knowledge-base compile pipeline**
   - The KB skeleton is defined, but the exact compiler workflow, review thresholds, and treatment of bulky raw artifacts still need to be specified.
6. **Cross-project promotion guardrails**
   - Promotion states are chosen conceptually, but the exact criteria and approval path for `cross_project_candidate` and `policy_candidate` artifacts remain to be formalized.
7. **Specialist activation thresholds**
   - Semi-automatic specialist activation is selected, but the initial thresholds and operator override semantics should be defined in a dedicated sub-plan.
8. **Durability escalation path**
   - The platform is intentionally session-centric in its first form; the threshold for introducing a deeper workflow durability engine later is still an explicit future decision.

## Outcome

_To be filled after implementation._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN, #NNN
- Notes: deviations from plan
