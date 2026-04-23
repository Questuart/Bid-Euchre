# Steward Platform — Governing Plan (Draft 2)

**Date:** 2026-04-22
**Status:** PROPOSED — revision of `governing_plan.md` following reviewer and operator feedback
**Scope:** Mature the existing Bid-Euchre steward control plane into a full-ambition single-repo platform (self-improving, auditable, durably remembered, token-efficient, actively triaging), prove it on a complete research run, and only then decide what to port and whether a meta-layer earns its slot.
**Supersedes:** `plans/steward_platform/governing_plan.md` (draft 1) and `plans/agent_ops/governing_plan.md` for future steward-platform direction. The prior `agent_ops` plan remains historical record for shipped Phase 0-4 work and in-flight Phase 5 work absorbed into Phase 0 below.
**Revision drivers:**
- Reviewer feedback flagged that draft 1 deferred its own falsification test to Phase 4 and committed to ~12 new primitives before validating any of them.
- Operator reframed the core test from "does the contract port to Fund and RIN-SnD?" to "does this platform produce research value on the repo where we have the most signal?"
- Operator clarified that vertical ambition (capability depth per repo) must be preserved; what sequences later is horizontal ambition (number of repos served).

---

## 1. Decision

Build the steward platform out to its full vertical ambition inside the
Bid-Euchre repo first, prove it by executing an end-to-end research program
through it (e.g., GBT retrain informed by human-gameplay capture), and use
the proving run's outcomes to decide portability scope and meta-layer shape.

Do not port to additional repos until the Bid-Euchre platform demonstrably
produces research outcomes, durable memory, compounding skill improvement,
and active (not stale) monitoring. Do not build a meta-orchestrator or
cross-project layer until there is at least one proving run's worth of
evidence about what cross-project state is actually useful.

The core bet: **a platform that produces demonstrable research value on one
repo is worth porting; one that does not produce value is not worth
porting, no matter how portable it is.**

---

## 2. Goals — The Full Vertical Stack

The platform must satisfy all of the following inside Bid-Euchre by the end
of Phase 0, with evidence generated during Phase 1:

1. **Self-improving** — skill promotion, prompt-policy evolution, and adaptive dispatch feed back into future task execution.
2. **Auditable and traceable** — every task, message, event, and decision is reconstructable from durable artifacts without transcript archaeology.
3. **Durable memory over time** — lessons from session N observably influence session N+K; MEMORY.md and KB compound rather than decay.
4. **Intent-aware delegation** — the platform chooses *shape / delegate / author* correctly for each task type, with the analyst-vs-author boundary enforced.
5. **Token-efficient** — tokens per successful merge, per proving-run decision, and per research insight are measured and trend flat or down.
6. **Adaptive lane and model selection** — lanes turn on and off under bounded rules; model/effort selection matches task complexity.
7. **Well-engineered prompts** — prompts sent to lanes are authored under a versioned prompt-policy contract, not ad-hoc per invocation.
8. **Active issue triage** — issues are flagged, logged, and triaged by event-driven signals, not operator discovery after the fact.
9. **Durable near-instantaneous messaging** — the message bus preserves lane-to-lane communication with low p95 latency and zero loss.
10. **Event-driven monitoring** — attention is driven by events as they occur, not polling loops that catch conditions after they've gone stale.
11. **Chat archiving and evaluation** — session chats are archived, mined for lessons, and feed back into skill and prompt-policy improvement.
12. **Knowledge-base system** — repo-local KB with clear structure, auto-indexed, earned-by-content growth.
13. **Rollback / disable paths** — every platform change (skill promotion, prompt-policy version, adaptive-dispatch shift, KB restructure) is reversible in one step without losing previously accumulated state.
14. **ADR-style architecture decision capture** — decisions about contracts, lane topology, model choices, promotions, and kill signals are recorded in a structured, auditable form distinct from lessons, playbooks, and incidents.
15. **Reliability lab / replay / failure-injection** — the platform can replay multi-lane task lifecycles from durable events, simulate lane stalls and dead-letter messages, and generate postmortems automatically. Used both as a regression test and as a future portability-validation harness.
16. **Any further improvements** the governing plan later identifies — this list is a floor, not a ceiling.

Deferred until Phase 2 decision gate (post-proving-run):

- Horizontal scope expansion (Fund, RIN-SnD adoption)
- `cmux`-based operator UX for multi-project supervision
- Dedicated meta-steward home / cross-project state directory
- Meta-orchestrator lane or pattern
- Cross-project promotion flow
- Planning skeleton mirror/sync mechanism

These remain *eventual* platform targets. They do not ship until the proving
run establishes what cross-project state is worth federating and what
cross-project decisions are worth centralizing.

---

## 3. Key Definitions

- **Vertical ambition:** the capability depth of the platform inside a single repo.
- **Horizontal ambition:** the number of repos the platform concurrently serves.
- **Proving run:** a complete end-to-end research program executed through the platform, used to validate that the platform produces observable research value. The first proving run is the GBT retrain informed by human-gameplay data captured through the browser-game hosting infrastructure.
- **Hardening gate:** a closed list of existing-debt items and new-primitive deliverables that must be complete before any Phase 1 proving work begins.
- **Decision gate (Phase 2):** a planning phase, not a build phase, whose output is a subsequent governing plan or scoped sub-plan based on proving-run findings.
- **Prompt-policy:** the versioned contract describing how prompts are constructed for each lane type and task type, including operator preferences, repo rules, and role-specific guidance. A prompt-policy edit is auditable and reversible.
- **Archivist:** a scheduled workflow (not a persistent lane) that reads events, messages, task outcomes, and review results, producing candidate lessons, incidents, and KB promotions for operator review.
- **Event-driven monitoring:** attention routing in which events (CI failure, inbox urgency, stall detection, threshold breach) produce operator or lane signals within a target latency, rather than being discovered by a polling cron that finds them minutes or hours stale.
- **Analyst lane:** shapes, investigates, diagnoses, recommends. Findings-oriented.
- **Author lane:** implements, tests, ships PRs. Merge-oriented.

---

## 4. Execution Structure

### 4.1 Phases

| Phase | Directory | Description | Depends On |
|-------|-----------|-------------|------------|
| 0 | `0_hardening` | Close existing debt and build out the full vertical stack (7 primitives) inside Bid-Euchre | Existing `agent_ops` Phase 0-4 assets |
| 1 | `1_proving_run` | Execute a complete research program through the platform; measure against Goal #1-#13 criteria | Phase 0 done-when met |
| 2 | `2_decision_gate` | Evaluate proving-run evidence; decide portability scope, meta-layer shape, and next-wave ambitions; produce Phase 3 scope as sub-plan or successor governing plan | Phase 1 complete |
| 3 | _(reserved)_ | Shape TBD by Phase 2 decision — e.g., second-repo port, meta-layer build, or further single-repo iteration | Phase 2 |
| 4 | _(reserved)_ | Shape TBD | Phase 3 |

Phases 3 and beyond are intentionally reserved. The revision's whole point
is that what comes after Phase 2 should be driven by evidence, not by a
roadmap committed in April.

### 4.2 Parallel low-cost work during Phase 0

One analyst-shift effort, running concurrent with Phase 0, not competing for primary attention:

- **Fund + RIN-SnD shape audit.** One-page inventory per repo: CI shape, branch conventions, test framework, existing `.claude/` presence, hosted-service dependencies, tooling conventions. Output lives at `plans/steward_platform/0_hardening/target_repo_audit.md`. Purpose: de-risk the eventual port if Phase 2 decides to pursue it. Not gating on Phase 1.

### 4.3 Step Template

Each phase follows this sequence (unchanged from draft 1):

1. **Scope lock** — read governing plan, phase plan, active sub-plans; establish slice boundary.
2. **Contract check** — inspect platform contract, prompt-policy registry, KB skeleton, trace schema, adapter contract; amend contract before implementation if insufficient.
3. **Implementation** — targeted edits inside declared write scope; preserve repo isolation and the steward-native event model.
4. **Verification** — targeted tests, manual steward smoke, at least one unhappy-path check, phase-specific validation.
5. **Learning / handoff** — update checkpoints, KB artifacts, prompt-policy candidates, improvement backlog, and write at least one entry to `decision_inputs.md` summarizing any finding from the slice that should bear on Phase 2 (see §15).

### 4.4 Phase 0 Dependencies

Before Phase 0 starts:
- Existing `agent_ops` Phase 0-4 assets remain in place and are treated as substrate, not discarded work.
- Paused `agent_ops` Phase 5 sub-efforts (`5_extraction`, `5_cross_model`, `5_skill_learning`, `5_portability_and_learning`) are explicitly retired or absorbed (see §7 debt closure).
- `Bid-Euchre` remains the only active target repo until Phase 2 decision gate.

---

## 5. Workstreams — The 8 Primitives

Each primitive maps to one or more of the 16 goals and is budgeted as a
workstream for Phase 0. No speculative additions; every primitive ties
directly to a named goal. Primitive H (Reliability Lab) doubles as a
portability de-risking surface in Phase 2.

### Primitive A — Unified Trace and Observability Layer

**Goals served:** #2 (auditable/traceable), #10 (real-time monitoring), #11 (archiving/evaluation, in part).

**Work:**
- Finalize event schema around first-class IDs: `project_id`, `cell_id`, `session_id`, `task_id`, `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`.
- Ensure every lane, hook, and command emits into the unified schema. Close any hook coverage gaps.
- Deploy **Phoenix** as a local observability sidecar (single Docker container). Named workflows: trace inspection for reproducibility audits (#2); session-archive evaluation for lesson extraction (#11).
- Replace polling-based attention with event-driven monitoring. Inbox urgency, CI failure, stall detection, and threshold breaches produce near-real-time signals into operator/ops lanes.
- Retention policy: raw events kept runtime-only; promoted artifacts committed.

**Done-when:** full experiment reproducible from trace corpus alone; event-to-operator latency has a published p95; Phoenix has a sustained hit count from two named workflows.

### Primitive B — Adaptive Dispatch, Skill Improvement, and Prompt-Policy

**Goals served:** #1 (self-improving), #4 (intent-aware delegation), #6 (lane/model selection), #7 (well-engineered prompts).

**Work:**
- Close SP-5-02 adaptive dispatch: advisor wired end-to-end, shadow mode → operator-visible recommendations → operator-approved promotion to active routing.
- Skill promotion loop: tie skill promotions/edits to observed task outcomes (via Primitive A events). A skill's "earning its keep" is measurable, not asserted.
- **Prompt-policy registry** — new. Versioned contract per lane type and task type. Captures operator preferences, repo rules, role-specific guidance. Edits produce diffable policy versions tagged in traces via `prompt_policy_version`.
- Policy candidates follow a candidate → confirmed lifecycle; promotion requires operator or analyst review.
- Analyst-vs-author routing rules encoded as policy, not convention.

**Done-when:** at least one skill has been measurably promoted or edited based on outcome feedback; prompt-policy version appears in ≥90% of trace records; adaptive dispatch has either been promoted to active or explicitly retained in advisory with an evaluation finding documented.

### Primitive C — Durable Memory and Knowledge Base

**Goals served:** #3 (durable memory), #12 (KB system), #14 (ADR capture).

**Work:**
- KB skeleton in `knowledge/` — 4 promoted-artifact classes plus two structured supplements:
  - `NOTES.md` — curated lessons, append-only, operator-edited prose.
  - `PLAYBOOKS.md` — runbooks. Procedural, "when X, do Y."
  - `anti_patterns.md` — actively consulted "do not do X" entries, structured as `trigger → harm → preferred alternative`. Distinct from NOTES because it is consulted during implementation and review, not just referenced post-hoc.
  - `incidents/<fingerprint>.md` — one file per incident, machine-fingerprinted, operator-annotated.
  - `adr/<NNN>-<slug>.md` — ADR-style architecture decisions (context, decision, consequences, alternatives considered, status).
  - `INDEX.md` — auto-generated from all of the above.
- MEMORY.md continues as the cross-session rolling index; tightened integration with KB (MEMORY.md entries link to NOTES / PLAYBOOKS / incidents / ADRs, not just recap).
- Retention and compaction policy for MEMORY.md, raw session logs, and raw trace exports.
- Commit policy: only promoted artifacts are committed; raw events and transcripts are runtime-only.
- **Planning templates** (goal #16 subsumes, previously in draft 1 §9.8): `plans/_templates/` carries governing-plan, sub-plan, execution-plan, checkpoint, promotion/rollback, and review-rubric templates. Template conformance enforced by `/create-plan` and `/create-adr` skills.

**Done-when:** KB contains ≥10 lessons; ≥3 of those lessons are cited downstream during Phase 1; `anti_patterns.md` has ≥5 entries each tied to an observed failure mode; at least 2 ADRs recorded for Phase 0 design choices; INDEX auto-regenerates; MEMORY.md no longer grows without bound.

### Primitive D — Archivist Script and Session Postmortem

**Goals served:** #11 (archiving/evaluation).

**Work:**
- `scripts/internal/archivist.py` — scheduled (nightly + end-of-session) script. Reads events (Primitive A), inbox, PR outcomes, task completions. Produces `knowledge/_candidates/<date>.md` with templated sections: repeated patterns, token-efficiency outliers, incident candidates, lesson candidates.
- Operator or analyst reviews candidates and promotes into NOTES / PLAYBOOKS / incidents.
- Session postmortem: end-of-session trigger writes a per-session handoff into MEMORY.md + feeds candidates into the archivist queue.
- Not a lane. Invokable as a skill from any lane if real-time curation is needed on demand.

**Done-when:** archivist runs nightly; candidate-to-promoted ratio is tracked; at least one promoted lesson has observable downstream use within the proving run.

### Primitive E — Messaging and Active Triage Closeout

**Goals served:** #8 (active triage), #9 (durable near-instantaneous messaging).

**Work:**
- Close message bus proving debt. The 4 keystone PRs merged this session hardened the bus; the remaining work is proving-under-load and follow-up cleanup (e.g., #2689 heartbeat pure-shell, #2690 lane-id dedup, #2691 hook JSON escape) — absorbing those into Phase 0 explicitly.
- Publish message-bus latency metrics (p50, p95) and throughput to dashboard.
- Active issue triage: event-driven signals (CI red, review blocked, stalled lane, orphan worktree, token anomaly) auto-create GitHub issues with the right labels, not waiting for operator discovery.
- Issue triage workflow (`triaging-issues` skill) integrated with event-driven inputs.

**Done-when:** bus p95 message-delivery latency measured and within a stated target; active triage has created at least N issues (target set at phase start) without operator intervention; zero lost-message incidents observed during the proving run.

### Primitive F — Token Economy Closeout

**Goals served:** #5 (token-efficient), supports #1 and #6.

**Work:**
- Execute token-economy Slice F evaluation protocol (already drafted as #2716). 1-2 week observation window after Slice B telemetry merged.
- Decision gate: adopt adaptive dispatch as active routing, retain as advisory indefinitely, or kill.
- Lane × model × effort rollups surfaced in dashboard (already shipped via #2725) and integrated into the archivist's periodic briefings.
- Token-per-successful-merge metric wired into trace records and surfaced in Primitive A.

**Done-when:** Slice F decision recorded in MEMORY.md + committed evaluation artifact; tokens-per-merge and tokens-per-proving-run-insight metrics published.

### Primitive H — Reliability Lab and Replay Harness

**Goals served:** #15 (reliability / replay / failure-injection), supports #1, #2, #11.

**Work:**
- `tests/reliability/replay.py` — harness that reconstructs a task lifecycle from the event corpus (Primitive A) and asserts expected intermediate + final states.
- Failure-injection scenarios: lane stall, dead-letter message, stuck worktree, orphan cron, review-coordinator crash, Telegram outage. Initially asserting the platform's existing recovery paths; later used to identify missing ones.
- Automated postmortem generator: given a replay artifact, produce a draft incident file with fingerprint, timeline, events, and proposed lessons.
- Rollback validation: for each reversible change (skill version, prompt-policy version, adaptive-dispatch policy), the harness exercises forward and backward transitions. This is how goal #13 (rollback/disable paths) is verified end-to-end.
- Usable as a *portability dry-run* in Phase 2: once a shape audit is available for Fund or RIN-SnD, the same harness can be pointed at an adapter stub to flag hidden coupling before any port work begins.

**Done-when:** ≥3 task-lifecycle replay scenarios pass; ≥5 failure-injection scenarios exercised; automated postmortem generator produces at least one end-to-end incident draft; rollback paths validated for every primitive that introduces a reversible change.

### Primitive G — Existing-Debt Closeout

**Goals served:** non-capability primitive; gates all others.

**Work:**
- Portability manifest: zero hard-blocks in `ops/worktrees.py` (44 occurrences) and `ops/token_economy.py` (22 occurrences). Soft-coupling may remain.
  - _Note:_ We are not porting yet, but unblocking these reduces accidental coupling and pays immediate dividends for any future extraction; the cost is modest and the code gets hygienically cleaner.
- Retire fragmented `agent_ops/5_extraction`, `agent_ops/5_cross_model`, `agent_ops/5_skill_learning`, `agent_ops/5_portability_and_learning` subtrees with explicit status (superseded / absorbed / abandoned) and outcome entries.
- Resolve remaining messaging-bus proving items (overlaps Primitive E).
- Platform-11 adaptive-dispatch partial reactivation (SP-5-02) either closes inside Primitive B or is explicitly superseded.

**Done-when:** `PORTABILITY_MANIFEST` shows zero hard-blocks in the two named files; `agent_ops/5_*` subtrees each have an explicit resolution note; old plan fragmentation is gone.

---

## 6. Phase 1 — Proving Run

### 6.1 Proving run selection

The first proving run is a complete research program end-to-end executed
through the platform. Primary candidate: **GBT retrain informed by
human-gameplay data captured through the browser-game hosting
infrastructure.**

Why this candidate:
- Exercises the full research workflow: capture → analyze → hypothesize → design → implement → execute → evaluate → decide.
- Requires cross-lane coordination (analyst for shaping, author for implementation, ops for orchestration, review for quality, measurement for promotion gates).
- Has ground truth: the retrained strategy either measurably outperforms the baseline or it does not.
- Exercises the rigor apparatus already documented in `.claude/rules/deferred/05_rigor.md`.
- Produces research value regardless of platform-test outcome — even if the platform proves weak, the retrain itself is useful research.

Alternative candidates (if GBT retrain is not the right shape for Phase 1):
- A new strategy addition (e.g., a counter-GBT or a hybrid heuristic-ML bot) executed end-to-end through the platform.
- A measurement methodology overhaul (new rigor regime applied across existing strategies).

### 6.2 Platform-level success criteria

The proving run measures the platform against the 13 goals. Each gets a
concrete metric:

| # | Capability | Measured by |
|---|---|---|
| 1 | Self-improving | Number of skill edits/promotions during the run driven by observed outcomes |
| 2 | Auditable/traceable | Full run reconstructable from trace corpus without transcript archaeology |
| 3 | Durable memory | Count of lessons from week 1 observably cited in week ≥3 tasks |
| 4 | Intent-aware delegation | Analyst-vs-author routing errors per 100 tasks (target: ≤1) |
| 5 | Token-efficient | Tokens per successful merge trending flat or down over the run |
| 6 | Lane/model selection | Adaptive dispatch decisions that operator would approve if audited (target: ≥80%) |
| 7 | Well-engineered prompts | Prompt-policy version cited in ≥90% of traces; policy deltas tied to outcome changes |
| 8 | Active triage | Share of issues created by event-driven triage vs. operator discovery (target: ≥50%) |
| 9 | Durable messaging | Zero lost messages; p95 message-delivery latency within stated target |
| 10 | Event-driven monitoring | Event-to-operator-signal latency p95 within target; zero stale-catch incidents |
| 11 | Archiving/evaluation | Archivist candidate-to-promotion rate measurable; promoted lessons with downstream use |
| 12 | KB system | KB grows during the run; promoted lessons are findable via INDEX |
| 13 | Rollback/disable paths | At least one forward + backward transition exercised per reversible primitive; zero state-loss incidents |
| 14 | ADR capture | ≥2 ADRs recorded for decisions made during the proving run; every kill-criterion trigger produces an ADR |
| 15 | Reliability lab / replay | Replay harness reconstructs ≥1 proving-run task lifecycle end-to-end with no drift from live events |
| 16 | Other | Any capability exposed by the run not captured above; documented in the proving-run report |

### 6.3 Separation of platform test from research test

The proving run has two separate evaluations that must not be conflated:

1. **Research evaluation** — does the GBT retrain actually beat the baseline at a statistically defensible level? Answered by the experiment's own rigor apparatus.
2. **Platform evaluation** — did the platform enable that experiment to execute efficiently, reproducibly, with compounding learning? Answered by the criteria above.

A research failure is not a platform failure. A research success that
required operator heroics is not a platform success.

### 6.4 Proving-run report

At end of Phase 1, the operator and analyst lanes produce
`plans/steward_platform/1_proving_run/report.md` containing:

- Research outcome (promoted / retained / killed).
- Per-capability evidence against §6.2 criteria.
- Identified platform gaps by severity.
- Proposed Phase 2 decision inputs (portability worth pursuing? meta-layer worth pursuing? further single-repo iteration?).
- **Ledger synthesis:** each of the 16 capability rows resolves into one or more entries in `decision_inputs.md` (§15), tagged per the taxonomy there. The report itself reads from the ledger rather than duplicating its contents.

---

## 7. Phase 2 — Decision Gate

Phase 2 is a planning phase, not a build phase. Its output is either a
successor governing plan or a scoped sub-plan that drives Phase 3+.

### 7.1 Inputs

- Phase 1 proving-run report.
- Fund + RIN-SnD shape audits (from §4.2 parallel work).
- Any deferred workstreams from draft 1 not absorbed into the 7 primitives.

### 7.2 Decisions to make

1. **Portability.** Does the proving run establish that the platform
   produces value worth porting? If yes, target: Fund first or RIN-SnD
   first? If no, what specific weaknesses need further single-repo
   hardening?
2. **Meta-layer.** What cross-project state is actually useful? Daily
   brief? Shared KB patterns? A dedicated meta-steward home? A
   meta-orchestrator lane, or a skill family invokable from each project?
   Answered by what the proving run revealed about operator pain, not by
   architectural preference.
3. **cmux adoption.** Only relevant if portability goes forward. Shape:
   workspace-per-project, notification bindings, browser surfaces,
   operator action bindings.
4. **Next proving run.** Should there be a Phase 3 proving run in Fund
   or RIN-SnD (the portability falsification test) before committing to
   a full port? Default: yes.

### 7.3 Kill signals

Phase 2 may also surface kill signals — platform capabilities that did not
earn their keep during the proving run. Each of the 7 primitives has
kill criteria (§11). Kill decisions are first-class Phase 2 output
alongside scope-expansion decisions.

---

## 8. Existing Platform Baseline and Adaptation Path

Unchanged from draft 1 §8. Summary:

- Reuse `steward-session.sh`, `ops.py`, `src/bid_euchre/ops/core/`, task queue, message bus, attention broker, worker pool, role prompts.
- Adapt before replace. Replacement justified only when an existing piece materially blocks a new capability.
- Known gaps (portability debt, token-economy incomplete, messaging proving incomplete, lane layout over-sized) are addressed by Primitives B/E/F/G above rather than left as background debt.

---

## 9. Target Architecture

Preserved from draft 1 §9 where still applicable; items deferred to Phase 2
are marked.

### 9.1 Platform shape (Phase 0 target)

Single Bid-Euchre steward cell with:
- Always-on: `orchestrator`, `ops`, `review`.
- Off-by-default, bounded-activation: `analyst-*`, `author-*`, `brws-author-*`, `flex-*`.
- No meta-surface in Phase 0. Deferred to Phase 2 decision.

### 9.2 Truth model

- Repo-local runtime state = operational truth.
- Phoenix = observability/eval UI, not canonical state.
- KB artifacts = promoted knowledge, not raw evidence.
- GitHub = PR/review/CI truth.
- Meta-level truth: not applicable in Phase 0 (no meta-surface).

### 9.3 Lane policy (Phase 0 target)

Reduced from current 19-lane fleet:
- Always-on: orchestrator + ops + review (3).
- Specialist activation under bounded rules with operator-visible triggers.
- Retirement: unused specialists parked after idle thresholds.
- Routing principle: analyst owns shaping/findings/diagnostics; author owns merge-oriented implementation.

### 9.4 Event and trace model

As in draft 1 §9.7. First-class IDs (project_id, cell_id, session_id,
task_id, lane_id, trace_id, incident_fingerprint, prompt_policy_version)
are canonical. Steward keeps a native event model; Phoenix is a consumer,
not a source.

### 9.5 Knowledge architecture (Phase 0)

Per-repo KB with 4-item skeleton (§5 Primitive C). Meta-KB deferred to
Phase 2.

### 9.6 Prompt / rule / skill layering

- User-level meta `CLAUDE.md` for stable global steering.
- User-level skills for reusable workflows (archivist, planning, ADR).
- Project `CLAUDE.md` for concise repo constants.
- Project rules for path/topic-specific behavior.
- Project skills for repo-local workflows.
- **Prompt-policy registry** (new Phase 0 primitive) sits alongside these layers, providing versioned per-lane/per-task guidance.
- Generated briefings for current incidents, lessons, steering notes.

### 9.7 Deferred cross-project architecture

Everything in draft 1 §9 that described meta-surfaces, cross-project
federation, planning-skeleton mirroring, or cross-repo promotion flow is
deferred to Phase 2 decision gate. It is not abandoned; it is evidence-
gated.

---

## 10. Sub-Plan Governance

Unchanged from draft 1 §5. Registry at
`plans/steward_platform/sub_plan_registry.md`. Required for multi-file
contract changes, runtime-behavior changes, or slices with material
open design choices.

---

## 11. Kill Criteria

Per-primitive kill criteria. If a primitive fails its criterion during
Phase 0 or Phase 1, Phase 2 evaluates whether to rework, downgrade, or
retire it.

| Primitive | Kill criterion |
|---|---|
| A — Trace/observability | Phoenix has <5 operator opens across 4 weeks after deployment → demote to JSONL + notebook only |
| B — Adaptive dispatch + skill + prompt-policy | Skill promotions/edits driven by outcome feedback = 0 across the proving run → revert to manual skill curation |
| C — KB | <3 promoted lessons observably cited during the proving run → collapse to single NOTES.md per repo |
| D — Archivist | Candidate-to-promotion rate <10% across the proving run → rewrite template or retire script |
| E — Messaging/triage | Active triage produces <20% of issues created → revert to operator-discovery model |
| F — Token economy | Slice F cannot produce a defensible promote/retain/kill decision → freeze adaptive dispatch in advisory indefinitely |
| G — Debt closeout | Not kill-able; blocks all other primitives |
| H — Reliability lab | <2 replay scenarios pass or <3 failure-injection scenarios exercised by end of Phase 0 → demote to a simpler event-diff assertion set; postmortem generator deferred |

---

## 12. Risks

| Risk | Mitigation |
|------|------------|
| Phase 0 hardening scope creep | Time-box Phase 0 at 6-8 weeks; 7 primitives are a closed list; new gaps are filed, not absorbed |
| Research stall conflated with platform stall in proving run | §6.3 enforces separation of research and platform evaluations |
| Phoenix becomes unused infrastructure | Kill criterion §11-A; two named workflows at deploy time |
| Archivist produces noise, not signal | Kill criterion §11-D; candidate-to-promotion rate measured weekly |
| Prompt-policy pollution degrades steering | Candidate → confirmed lifecycle; operator-visible policy versions; rollback path via policy version pinning |
| Platform-11/13 repeat-postponement pattern | Phase 0 is narrower than draft 1's Phase 0-4; operator confirmed constraints that paused earlier attempts no longer apply |
| Portability option decays because we defer it | §4.2 parallel shape-audit work keeps the option warm at low cost |
| Event-driven monitoring adds attention noise | Signal thresholds tuned by archivist feedback; event classes can be muted via policy |
| KB grows without compaction | §5-C retention policy; INDEX highlights stale content |
| Lane reduction causes bottleneck on active lanes | Specialist activation thresholds tunable; retirement only if idle, not if contention |

---

## 13. Success Criteria

1. All 8 primitives reach Phase 0 done-when criteria.
2. Proving run executes end-to-end through the platform with measurable attention compression relative to baseline.
3. Proving-run platform evaluation produces a per-capability scorecard against all 16 goals.
4. Decision gate (Phase 2) produces a scoped successor plan (portability, meta-layer, further iteration, or combination) based on proving-run evidence *read from the decision-inputs ledger* (§15), not reconstructed from transcripts.
5. At least 3 KB lessons have observable downstream use during the proving run.
6. Tokens per successful merge during the proving run are flat or declining.
7. Messaging bus has zero lost-message incidents and published p95 latency.
8. Adaptive dispatch either ships as active routing or is documented as retained-advisory with evaluation evidence.
9. At least one skill and one prompt-policy have been promoted or edited with outcome-feedback evidence.
10. Reliability-lab replay harness reconstructs ≥1 proving-run task lifecycle without drift.
11. Rollback paths validated for every reversible change introduced in Phase 0.
12. `decision_inputs.md` contains ≥20 tagged entries by end of Phase 1, with at least one entry per capability in §2.

---

## 14. Open Items

1. **Proving-run scope.** GBT retrain is primary candidate; alternates listed in §6.1. Operator confirms selection before Phase 1.
2. **Phase 0 time-box.** Target 6-8 weeks; exact budget set at Phase 0 kickoff based on primitive-by-primitive estimates.
3. **Prompt-policy schema.** Registry structure, versioning semantics, and lifecycle state machine to be detailed in a sub-plan under Primitive B.
4. **Event-driven monitoring latency targets.** p95 target numbers set in a sub-plan under Primitive A once baseline measurements exist.
5. **Archivist template structure.** Candidate-file sections, promotion criteria, and review cadence specified in a sub-plan under Primitive D.
6. **KB INDEX generation.** Tooling choice (Python script, skill, cron) and schema specified in a sub-plan under Primitive C.
7. **Phoenix local deployment details.** Docker-compose shape, retention, exporter path specified under Primitive A. (Single-container target; no multi-service stack.)
8. **Specialist activation thresholds.** Exact idle-to-parked and task-arrival-to-active thresholds specified in a sub-plan.
9. **Target-repo shape-audit output format.** Standardized one-page template for Fund and RIN-SnD audits.
10. **Phase 2 decision template.** Decision-gate rubric and output format specified at end of Phase 0 to avoid recency bias from the proving run.

---

## 15. Decision-Inputs Ledger

A persistent ledger at `plans/steward_platform/decision_inputs.md` captures
every finding during Phases 0 and 1 that should bear on the Phase 2
decision gate. Purpose: prevent Phase 2 from being an archaeological
exercise over commit logs and session transcripts. Every primitive, the
proving run, the archivist script, and the parallel shape audits feed
entries into this ledger.

### Entry format

```
## [YYYY-MM-DD] <short title>

**Source:** primitive-X | proving-run | shape-audit-<repo> | archivist | ad-hoc
**Tags:** <comma-separated from taxonomy below>
**Severity:** high | medium | low
**Evidence:** <link to commit / trace / incident / artifact>

### Finding
<what we observed>

### Implication for Phase 2
<what this suggests about portability, meta-layer, further iteration, or kill signals>
```

### Tag taxonomy

- `portability-signal` — evidence the contract will or will not port cleanly.
- `meta-layer-signal` — evidence a cross-project mechanism would or would not earn its slot.
- `capability-gap` — a goal from §2 that the Phase 0 build did not deliver well enough.
- `capability-win` — a goal that over-delivered and could support broader ambition.
- `kill-signal` — evidence a primitive should be retired or downgraded (see §11).
- `surprise-finding` — something the plan did not anticipate at all.
- `target-repo-shape` — findings from Fund / RIN-SnD shape audits.
- `cost-signal` — operator-time, token, or complexity cost exceeding expectation.
- `adr-trigger` — a finding that warrants a formal ADR under Primitive C.

### Write expectations

- Every primitive's done-when verification produces at least one ledger entry summarizing the capability's state (win or gap), tagged accordingly.
- Every kill-criterion trigger (§11) produces a ledger entry with the `kill-signal` tag and spawns an ADR.
- The archivist script's nightly output includes a section proposing new ledger entries; operator reviews and accepts or rejects each.
- The proving-run report (§6.4) is structured so that each of the 16 capability rows resolves into one or more ledger entries.
- The parallel target-repo shape audits (§4.2) produce entries under `target-repo-shape` and `portability-signal`.
- Ledger entries are additive only; corrections append a new entry referencing the earlier one rather than editing the original.

### Phase 2 use

The Phase 2 decision gate begins by reading the ledger filtered by tag.
Each decision in §7.2 has a tag filter and a summarization pass:

- Portability decision: `portability-signal` + `target-repo-shape` + `cost-signal`.
- Meta-layer decision: `meta-layer-signal` + `surprise-finding` + `cost-signal`.
- Kill decisions: `kill-signal` with supporting `capability-gap` entries.
- Next-wave ambition: `capability-win` entries.

If the ledger has high-severity entries Phase 0 or Phase 1 did not
resolve, they become mandatory Phase 2 inputs rather than optional
considerations.

---

## 16. Delta From Draft 1

Recording what changed, why, so future readers can reconstruct the revision:

- **Horizontal scope reduced, vertical scope preserved.** Draft 1 proposed 3 repos + full vertical stack simultaneously. Draft 2 proposes 1 repo + full vertical stack, with horizontal expansion evidence-gated.
- **Falsification test moved from portability to research value.** Draft 1's falsification came at Phase 4 (cross-repo adoption). Draft 2's comes at Phase 1 (proving run), upstream of any port decision.
- **Primitive count disciplined.** Draft 1 introduced ~12 new subsystems. Draft 2 specifies 7 primitives mapped 1:1 to operator-named capabilities (§2), with explicit kill criteria.
- **Meta-layer deferred, not abandoned.** Draft 1 committed to meta-steward home, meta-orchestrator, cmux adoption, cross-project promotion in Phase 0-2. Draft 2 defers all of that to Phase 2 decision based on proving-run evidence.
- **KB taxonomy simplified.** Draft 1 proposed 7 top-level KB directories per repo × 3 repos + 7-dir meta-KB. Draft 2 uses a 4-item skeleton (NOTES, PLAYBOOKS, incidents/, INDEX) for Bid-Euchre only.
- **Archivist is a script, not a lane.** Draft 1 proposed persistent archivist and meta-archivist lanes. Draft 2 specifies a scheduled script + end-of-session hook.
- **Phoenix retained but constrained.** Draft 1 made Phoenix a phase-one pillar. Draft 2 ships Phoenix in Phase 0 with two named workflows as its justification and a kill criterion if those workflows don't earn sustained use.
- **Debt closeout is a primitive.** Draft 1 listed gaps in §8 but did not scope their resolution. Draft 2 makes existing-debt closeout Primitive G with explicit done-when criteria.
- **Phase 2 is a decision phase.** Draft 1's Phase 2 was a build phase (meta-supervisor + cmux). Draft 2's Phase 2 is an evaluation phase with sub-plan or successor-plan output.
- **Goals expanded from 12 to 16 to capture draft 1 vertical ambitions the original 12-list did not surface.** Added rollback/disable paths (#13), ADR-style decision capture (#14), and reliability-lab/replay/failure-injection (#15, sourced from `post_sprint_brainstorm.md`). Primitive count rose from 7 to 8 (Reliability Lab added).
- **Decision-inputs ledger (§15) introduced.** Draft 1 had no persistent surface for tracking findings that should bear on later decisions. Draft 2 requires every primitive, the proving run, the archivist script, and the shape audits to write tagged entries into a single ledger that Phase 2 reads from directly.

---

## Outcome

_To be filled after implementation._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN, #NNN
- Notes: deviations from plan, proving-run outcomes, Phase 2 decisions.
