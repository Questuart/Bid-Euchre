# Agent Ops Post-Sprint Brainstorm

**Date:** 2026-03-19
**Status:** Exploratory / non-binding
**Context:** Possible branch-out directions after the active `agent_ops`
governed initiative reaches a stable closeout point.
**Canonical active roadmap:** [governing_plan.md](governing_plan.md)

This document is intentionally separate from the governed roadmap. Nothing here
is committed, scheduled, or implied by the existence of this file alone.

## Purpose

Capture promising infrastructure directions that become attractive **after** the
current orchestration sprint is complete, so the team can revisit them without
polluting the active `Platform-*` roadmap.

## How To Use This Document

- Treat this as a parking lot for worthwhile follow-on bets.
- Do not pull items into active execution unless they are promoted into:
  - the governed plan,
  - a future governed initiative, or
  - a clearly scoped session/sub-plan.
- Prefer ideas that:
  - reuse the new orchestration core,
  - improve reliability or leverage across repos,
  - accelerate real product/research work in this repo.

## Highest-Value Branch-Out Ideas

### 1. Reliability Lab And Replay Harness

Build a first-class integration/replay environment for the full orchestration
stack.

Potential work:

- replay a full multi-lane task lifecycle from durable events/messages
- simulate lane failure, stalled workers, dead-letter messages, and remote
  notification failures
- run soak tests for supervisor loops, issue triage, and second-model lanes
- generate operator postmortems automatically from replay artifacts

Why it is worth exploring:

- this directly addresses the repo's historic "works in review, flaky in use"
  failure mode
- it gives confidence before enabling higher-autonomy features by default
- it becomes reusable across any repo that adopts the orchestration core

Best timing:

- after the communication bus, worker pool, and remote channel are stable

### 2. Repo Adapter SDK / Extraction Kit

Turn the orchestration core into something that can be adopted by another repo
with low friction.

Potential work:

- package the core-vs-adapter boundary as a small reusable library/template
- add a project bootstrap command for new repos
- add adapter validation checks:
  - required CI checks configured
  - prompt/profile overrides present
  - review/test commands wired correctly
- add example adapters for:
  - a research repo
  - an application repo

Why it is worth exploring:

- this is the clearest proof that the portability work is real
- it reduces the cost of reusing the infrastructure for browser-game work or a
  second data-science/coding repo

Best timing:

- after `Platform-10` through `Platform-13`

### 3. Operator Console / Audit UI

Build a richer human-facing surface on top of the dashboard/status model.

Potential work:

- terminal UI or lightweight web UI for:
  - active lanes
  - task inboxes
  - blocked items
  - PR/CI/review state
  - issue triage output
  - remote notification history
- replay view for a task thread or lane timeline
- one-click drill-down into worker lanes or linked artifacts

Why it is worth exploring:

- once the system is actually being used every day, operator ergonomics matter
- this lowers the cognitive cost of supervising many background lanes
- it makes the system easier to demo, debug, and port

Best timing:

- after the dashboard/status model has settled and the message contracts are
  stable

#### UI / UX Buckets Worth Exploring

These are the main UI/UX directions that seem worth considering once the core
platform contracts are stable.

##### A. Core Supervision Surfaces

Purpose:

- help the operator answer "what needs attention right now?" quickly

Ideas:

- **Operator dashboard**
  - active lanes
  - blocked items
  - worker-pool summary
  - PR/CI/review health
  - degraded-lane warnings
- **Attention queue**
  - one place for `needs_human` items
  - sorted by urgency, age, and lane
  - links back to the exact task/thread/lane

Why this bucket matters:

- this is the highest-leverage UX improvement for day-to-day operation

##### B. Investigation And Drill-Down Surfaces

Purpose:

- help the operator understand why something is stuck or what happened

Ideas:

- **Task/thread timeline view**
  - intake -> delegation -> review -> PR -> merge / failure timeline
  - messages, events, retries, handoffs, alerts in one place
- **Lane drill-down / resume UI**
  - inspect `author-b` or `review` directly
  - show task, branch, PR, last activity, blockers, health
  - resume or attach by lane name rather than tmux hunting

Why this bucket matters:

- it makes the system debuggable without falling back to raw logs and panes

##### C. Review And Delivery Surfaces

Purpose:

- make PR, review, and issue-management workflows easier to supervise

Ideas:

- **PR / review cockpit**
  - active PRs
  - required vs advisory checks
  - pending review work
  - follow-up queue
- **Issue triage board**
  - deduped operational findings
  - issue creation/update history
  - what got promoted to backlog and why

Why this bucket matters:

- these are some of the highest-friction operational loops today

##### D. Remote And Notification Surfaces

Purpose:

- make away-from-keyboard supervision reliable and transparent

Ideas:

- **Remote notification center**
  - what was sent to Telegram/Discord
  - dedupe/backoff history
  - ack status
  - failed or missed delivery visibility

Why this bucket matters:

- remote supervision should be inspectable, not a black box

##### E. Control And Intervention Surfaces

Purpose:

- give the operator safe, fast ways to intervene

Ideas:

- **Safe-mode / policy controls**
  - pause delegation
  - pause issue creation
  - disable remote commands
  - cap worker scaling
- **Command palette / quick actions**
  - reroute task
  - send to review
  - pause retries
  - summarize active lanes
  - inspect blocker thread

Why this bucket matters:

- the system should be easy to steer without opening five different panes

##### F. Analytics And Evaluation Surfaces

Purpose:

- help decide whether the platform is actually improving work

Ideas:

- **Operator scorecards**
  - intervention load
  - blocker detection latency
  - false alert rate
  - worker utilization
  - review usefulness

Why this bucket matters:

- it converts "this feels better" into measurable platform evidence

#### Suggested UI / UX Order

If this branch-out area gets promoted later, the likely best order is:

1. **Core supervision surfaces**
2. **Investigation and drill-down surfaces**
3. **Review and delivery surfaces**
4. **Control and intervention surfaces**
5. **Remote and notification surfaces**
6. **Analytics and evaluation surfaces**

This keeps the focus on:

- clarity first
- debuggability second
- operational leverage third
- polish and instrumentation after the core operator experience is solid

### 4. Browser-Game Development Accelerator

Use the orchestration platform to directly speed up this repo's browser-game
work once the core is reliable.

Potential work:

- browser-game-specific adapter and prompts
- dedicated flows for:
  - frontend slices
  - backend/API slices
  - replay export / human game capture
  - UI test and deploy validation
- review/ops automation tuned for application development rather than research
  only

Why it is worth exploring:

- this repo is one of the first real consumers of the infrastructure
- it pressure-tests whether the core works outside pure infra/research slices
- it creates a direct payoff: faster app development on top of the same system

Best timing:

- as soon as the early governed batches are stable enough to help real browser
  game work

### 5. Cross-Model Service Mesh

Go beyond one extra reviewer lane and treat multiple models as bounded service
roles under the same orchestration contract.

Potential work:

- Codex as background reviewer/maintainer
- another model as issue triage or report-audit specialist
- model routing by task type, cost, or reliability profile
- consensus/escalation patterns when model findings disagree

Why it is worth exploring:

- it gives real defense-in-depth without collapsing back into fragile hooks
- it lets the platform use different models for different roles while keeping
  one coordination bus

Best timing:

- after the Codex service-lane experiment has reliability data

### 6. Policy And Approval Engine

Make the orchestration platform more explicit about what actions are allowed and
which ones require approval.

Potential work:

- machine-readable action policy
- approval classes for:
  - write actions
  - merges
  - issue creation
  - remote commands
  - dynamic worker creation
- budget and notification policies by role and repo

Why it is worth exploring:

- it makes autonomy safer as the system becomes more capable
- it helps portability by making repo policy declarative instead of implicit

Best timing:

- once the current safe-mode, rate-limit, and remote-command rules have proven
  useful but feel too hard-coded

### 7. Continuous Evaluation And Scorecards

Evaluate the orchestration platform like a product, not just a pile of tools.

Potential work:

- automated scorecards for:
  - review precision
  - blocker detection latency
  - task handoff quality
  - retry/reroute usefulness
  - remote alert quality
- regression suites for orchestration behavior
- before/after metrics for developer throughput and intervention load

Why it is worth exploring:

- this helps decide whether the platform is actually simplifying work
- it turns subjective "this feels better" into measurable evidence

Best timing:

- after enough real task volume exists to make the metrics meaningful

## Interesting But Lower-Priority Ideas

### 8. Knowledge Layer And Retrieval Assistant

Build a higher-level assistant on top of the audit index, message bus, and plan
artifacts.

Potential work:

- answer questions such as:
  - what usually fixes this class of failure?
  - which lanes were involved in the last similar incident?
  - what changed between the last successful and failed runs?
- repo-specific retrieval over plans, findings, issues, and task threads

Why it is interesting:

- it can make the platform easier to operate and debug
- it is a more appropriate future use of agent frameworks than the core control
  plane

Why it is not top priority:

- it is leverage on top of the platform, not the platform itself

### 9. Team / Shared-Supervision Mode

Extend the single-user operator model into something friendlier for multiple
humans.

Potential work:

- shared Discord-room supervision
- operator roles and acknowledgements
- handoff and on-call style workflows
- per-user notification routing

Why it is interesting:

- it would make the platform more useful beyond a single primary operator

Why it is not top priority:

- the current target is still a single-user, single-repo operational model

### 10. Hosted / Always-On Runtime

Move the orchestration platform from one workstation to a more persistent
service environment.

Potential work:

- deploy the supervisor stack on a stable host
- separate compute workers from the operator UI
- persistent remote-control endpoint

Why it is interesting:

- it improves uptime and reduces dependence on one machine

Why it is not top priority:

- it raises the operational and security bar significantly
- the local repo-first model should prove itself first

## Additional Tooling Worth Evaluating

These are not part of the committed core stack today. They are candidates worth
evaluating later if the orchestration platform reaches the point where the
additional leverage outweighs the extra surface area.

### A. Near-Term Evaluation Candidates

These seem like the most plausible next tools to evaluate once the current
platform contracts are stable.

#### 1. `Textual`

Why evaluate it:

- strong fit for a richer terminal-native operator console
- supports more ambitious dashboard UX than plain terminal output
- includes worker/concurrency patterns that may fit a live control surface

Likely use:

- dashboard-first operator console
- attention queue
- lane drill-down
- timeline / replay views

When to evaluate:

- after the registry, message bus, and supervisor outputs have stabilized

#### 2. `Rich`

Why evaluate it:

- immediate upgrade path for terminal ergonomics even before a full TUI
- useful for trees, progress views, tables, logs, and better tracebacks

Likely use:

- `ops.py` output improvements
- inbox / blocker summaries
- richer CLI-oriented review and status surfaces

When to evaluate:

- anytime; lower-risk than a full TUI shift

#### 3. `Typer`

Why evaluate it:

- natural fit for a more structured operator/orchestrator CLI surface
- works well with Python type hints and larger multi-command CLIs

Likely use:

- if `ops.py` grows into a larger command surface
- if the orchestration core is later extracted into a reusable toolkit

When to evaluate:

- after the command surface is stable enough that a CLI framework migration
  would reduce friction instead of causing churn

#### 4. `FastAPI` + `htmx`

Why evaluate it:

- gives a lightweight path to a local web operator console without jumping
  straight to a heavy frontend stack
- `htmx` is especially attractive if you want HTML-first, low-JS UI for an
  operator dashboard

Likely use:

- browser-based dashboard
- operator actions / control panel
- replay and audit views
- remote-safe human review surfaces

When to evaluate:

- after the terminal-first operating model is proven and you want a browser UI
  with low frontend overhead

### B. Data And Contract Tooling

These are interesting if the platform becomes more schema-heavy and more
portable.

#### 5. `datamodel-code-generator`

Why evaluate it:

- could reduce hand-written schema boilerplate once the message bus and
  adapter contracts stabilize

Likely use:

- generate Pydantic models from JSON Schema / OpenAPI / shared contracts

When to evaluate:

- only after schemas are stable enough that generation helps more than it hides

#### 6. SQLite JSON / JSONB features

Why evaluate them:

- the platform already leans on SQLite, and the built-in JSON support is strong
- JSONB may become useful for denser or faster state storage if query patterns
  justify it

Likely use:

- message payload storage
- snapshot diffs
- richer query surfaces over runtime state

When to evaluate:

- after the current SQLite-backed surfaces show real query or storage pressure

#### 7. `Datasette` / `sqlite-utils`

Why evaluate them:

- attractive for quickly exploring SQLite-backed runtime state without building
  a bespoke UI first
- could provide a fast path for audit, inspection, and admin views

Likely use:

- interactive exploration of the message bus, checkpoints, alerts, and audit
  data
- fast temporary console for internal operator analysis

When to evaluate:

- after the SQLite schema settles and there is enough real operational data to
  inspect

### C. Observability Tooling

These are interesting if the platform needs stronger health and tracing than
repo-local status checks provide.

#### 8. `OpenTelemetry`

Why evaluate it:

- gives a standard observability layer for traces, metrics, and logs
- could make it easier to understand supervisor latency, message flow, retry
  churn, and remote notification delivery

Likely use:

- tracing orchestrator -> worker -> review -> ops flows
- queue latency measurement
- reliability scorecards and regressions

When to evaluate:

- after the orchestration flows are stable enough that instrumentation targets
  are clear

### D. Workflow And Control-Plane Systems Worth Evaluating

These are heavier systems than the current repo-local stack, but they may be
worth a serious post-sprint evaluation if they could materially improve
durability, supervision, or portability.

#### 9. `Temporal`

Why evaluate it:

- strongest candidate if the platform eventually needs durable long-running
  workflows, resumable human-in-the-loop execution, and hosted/multi-repo
  operation

Likely use:

- durable orchestration for long-lived task flows
- human approval wait states
- retry/recovery semantics for multi-step agent work

Why to stay cautious:

- it is a major runtime-model shift compared with the current repo-local
  approach
- it adds meaningful infrastructure and conceptual weight

#### 10. `Prefect`

Why evaluate it:

- plausible middle ground between the current repo-local model and a heavier
  orchestration platform
- attractive if the system wants richer scheduling, state tracking, and
  operator visibility without going full Temporal immediately

Likely use:

- recurring orchestration jobs
- stateful supervisor flows
- lightweight hosted or semi-hosted automation

Why to stay cautious:

- it still introduces a second orchestration worldview
- may fit scheduled flows better than the lane-centric coding workflow itself

#### 11. `LangGraph`

Why evaluate it:

- most interesting control-plane orchestration candidate if the platform wants a
  stronger stateful agent runtime while keeping human-in-the-loop and durable
  graph/state concepts

Likely use:

- orchestrator state machine
- review/approval branches
- resumable multi-step agent workflows

Why to stay cautious:

- it may abstract exactly the layer this project is trying to make explicit and
  repo-owned
- it should be evaluated as a possible future runtime substrate, not adopted
  casually

#### 12. `Dagster`

Why evaluate it:

- potentially attractive for data/research-heavy workflows, especially if the
  repo eventually wants stronger asset lineage or data-product orchestration on
  top of the coding workflow

Likely use:

- research/data pipelines
- evaluation/report generation flows
- governed automation around artifact production

Why to stay cautious:

- better fit for data orchestration than for the core lane-based coding control
  plane

#### 13. `Airflow`

Why evaluate it:

- mainly worth evaluating as a sanity-check baseline because it is a familiar
  orchestration system with strong scheduling and UI

Likely use:

- scheduled batch automation only

Why to stay cautious:

- weakest fit for the day-to-day lane-based agent workflow
- more likely useful for periodic jobs than for the core interactive control
  plane

### E. Caution / Probably-Not-Yet Tooling

These may become useful eventually, but they are not attractive near-term.

#### 14. Heavy workflow systems as immediate replacement

Examples:

- Airflow
- Dagster
- Prefect
- Celery
- Temporal

Why to stay cautious:

- these add a second orchestration worldview on top of the repo-owned one
- they are likely too heavy for a single-user, repo-first platform at this
  stage

#### 15. Agent frameworks for the control plane

Examples:

- LangChain-style orchestration frameworks

Why to stay cautious:

- they abstract exactly the layer this project is trying to make explicit,
  durable, and auditable
- they may be more appropriate later for retrieval/Q&A than for the core
  orchestration loop

## Tooling Prioritization Heuristic

If post-sprint tooling evaluation becomes active, the most sensible order is
probably:

1. `Rich`
2. `Textual`
3. `FastAPI` + `htmx`
4. `Temporal` / `Prefect` / `LangGraph` evaluation spike
5. `Typer`
6. `Datasette` / `sqlite-utils`
7. `OpenTelemetry`
8. `datamodel-code-generator`
9. deeper SQLite JSONB optimization work

That ordering emphasizes:

- immediate UX wins first
- operator-console leverage second
- serious orchestration-framework evaluation only after the repo-native model is
  concrete enough to compare against
- portability and observability after the platform itself has proven out

## Prioritization Heuristic After Sprint Closeout

If the current initiative lands cleanly, the most sensible next bets are
probably:

1. **Reliability lab and replay harness**
2. **Browser-game development accelerator**
3. **Repo adapter SDK / extraction kit**
4. **Operator console / audit UI**

That ordering keeps the focus on:

- reliability first
- direct leverage on real product work second
- portability third
- ergonomics fourth

## Outcome

Pending. This document is exploratory and has no implementation outcome yet.
