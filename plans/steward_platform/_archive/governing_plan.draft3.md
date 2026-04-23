# Steward Platform — Governing Plan (Draft 3)

**Date:** 2026-04-22
**Status:** PROPOSED — revision of `governing_plan.draft2.md` incorporating analyst-a's structural review
**Scope:** Mature the existing Bid-Euchre steward control plane into a full-ambition single-repo platform (self-improving, auditable, durably remembered, token-efficient, actively triaging, replay-testable), prove it on a complete research run, and only then decide what to port and whether a meta-layer earns its slot.
**Supersedes:** `governing_plan.draft2.md` and `governing_plan.md`. The prior `agent_ops` governing plan remains historical record for shipped Phase 0-4 work and in-flight Phase 5 work absorbed into Phase 0 below.
**Revision drivers (draft 2 → draft 3):**
- Analyst-a flagged a Phase 0 / Phase 1 dependency bug (Phase 0 done-when criteria required Phase 1 evidence — impossible boundary).
- Analyst-a flagged that the full research proving run doubles as platform judgment and research delivery, creating schedule risk if the platform is fundamentally flawed; a cheaper fail-fast preflight is needed.
- Analyst-a flagged internal consistency errors (stale "7 primitives" and "#1-#13" references after Primitive H and goals 13-15 were added).
- Analyst-a flagged that the decision-inputs ledger needs operational fields (decision axis, owner, review-by, disposition) beyond additive-only tagged entries.
- Analyst-a flagged undefined baselines and undefined target thresholds used as success criteria.
- Operator directed removal of clock-time budgets; sequencing and usage-based thresholds remain.

---

## 1. Decision

Build the steward platform out to its full vertical ambition inside the
Bid-Euchre repo first, prove it by executing an end-to-end research program
through it (e.g., GBT retrain informed by human-gameplay capture), and use
the proving run's outcomes to decide portability scope and meta-layer
shape.

Do not port to additional repos until the Bid-Euchre platform demonstrably
produces research outcomes, durable memory, compounding skill improvement,
and active (not stale) monitoring. Do not build a meta-orchestrator or
cross-project layer until there is at least one proving run's worth of
evidence about what cross-project state is actually useful.

The core bet: **a platform that produces demonstrable research value on
one repo is worth porting; one that does not produce value is not worth
porting, no matter how portable it is.**

---

## 2. Goals — The Full Vertical Stack

The platform must satisfy all of the following inside Bid-Euchre by the
end of Phase 1, with substrate standing up in Phase 0 and outcome-evidence
generated during Phases 1a and 1:

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

These remain *eventual* platform targets. They do not ship until the
proving run establishes what cross-project state is worth federating and
what cross-project decisions are worth centralizing.

---

## 3. Key Definitions

- **Vertical ambition:** the capability depth of the platform inside a single repo.
- **Horizontal ambition:** the number of repos the platform concurrently serves.
- **Phase 0 readiness criteria:** substrate-level conditions that must be true to enter Phase 1a. "The thing exists and passes targeted tests." Does not require proving-run outcome evidence.
- **Phase 1 validation criteria:** outcome-level conditions measured during the proving run. "The thing produces the effect it was built for." Measured against real usage.
- **Platform preflight (Phase 1a):** a bounded end-to-end workflow that exercises every substrate surface (trace, routing, messaging, archivist, rollback, skill loop, prompt-policy) under a short-scoped task. Purpose: fast-fail platform check before committing to the full research proving run. Distinct from the proving run itself.
- **Proving run (Phase 1):** a complete end-to-end research program executed through the platform, used to validate that the platform produces observable research value. Primary candidate: GBT retrain informed by human-gameplay capture.
- **Hardening gate (Phase 0):** a closed list of existing-debt items and new-primitive readiness deliverables that must be complete before any Phase 1a or Phase 1 work begins.
- **Decision gate (Phase 2):** a planning phase, not a build phase, whose output is a subsequent governing plan or scoped sub-plan based on proving-run findings.
- **Prompt-policy:** the versioned contract describing how prompts are constructed for each lane type and task type. A prompt-policy edit is auditable and reversible.
- **Archivist:** a scheduled workflow (not a persistent lane) that reads events, messages, task outcomes, and review results, producing candidate lessons, incidents, and KB promotions for operator review.
- **Event-driven monitoring:** attention routing in which events (CI failure, inbox urgency, stall detection, threshold breach) produce operator or lane signals within a target latency, rather than being discovered by a polling cron that finds them stale.
- **Analyst lane:** shapes, investigates, diagnoses, recommends. Findings-oriented.
- **Author lane:** implements, tests, ships PRs. Merge-oriented.

---

## 4. Execution Structure

### 4.1 Phases

| Phase | Directory | Description | Depends On |
|-------|-----------|-------------|------------|
| 0 | `0_hardening` | Close existing debt and build substrate for all 8 primitives to **readiness**; capture baselines | Existing `agent_ops` Phase 0-4 assets |
| 1a | `1a_preflight` | Short-scoped platform preflight: one bounded end-to-end workflow exercising every substrate surface; go/no-go for Phase 1 | Phase 0 readiness criteria met |
| 1 | `1_proving_run` | Execute a complete research program through the platform; measure against Phase 1 validation criteria | Phase 1a pass |
| 2 | `2_decision_gate` | Evaluate proving-run evidence via the decision-inputs ledger; decide portability scope, meta-layer shape, and next-wave ambitions; produce Phase 3 scope as sub-plan or successor governing plan | Phase 1 complete |
| 3 | _(reserved)_ | Shape TBD by Phase 2 decision | Phase 2 |
| 4 | _(reserved)_ | Shape TBD | Phase 3 |

No clock-time budgets are attached to phases. Sequencing and
readiness/validation gates are the discipline; the work takes the time it
takes.

### 4.2 Parallel low-cost work during Phase 0

Independent of primitive work, running in parallel on an analyst lane:

- **Fund + RIN-SnD shape audit.** One-page inventory per repo: CI shape, branch conventions, test framework, existing `.claude/` presence, hosted-service dependencies, tooling conventions. Output lives at `plans/steward_platform/0_hardening/target_repo_audit.md`. Purpose: de-risk the eventual port if Phase 2 decides to pursue it. Not gating on Phase 1a or Phase 1.

### 4.3 Phase 0 Step 0 — Baseline Capture

Before primitive work begins, capture a one-time baseline snapshot at
`plans/steward_platform/0_hardening/baseline.md`:

- **Attention compression baseline:** operator interventions per task (sampled from the last N completed packets before Phase 0 start).
- **Token-per-successful-merge baseline:** tokens consumed per merged PR, averaged across a representative window of recent merges.
- **Issue-discovery baseline:** share of issues over a recent period that were created by automation vs. operator discovery.
- **Message-bus latency baseline:** current p50 and p95 delivery times, measured via the telemetry merged in PR #2725.
- **Event-to-operator-signal baseline:** current time from event emission to operator awareness, estimated from recent incident fingerprints.

Every Phase 1 validation criterion that references "relative to baseline"
or "trending flat or down" references this artifact.

### 4.4 Step Template (per slice)

1. **Scope lock** — read governing plan, phase plan, active sub-plans; establish slice boundary.
2. **Contract check** — inspect platform contract, prompt-policy registry, KB skeleton, trace schema, adapter contract; amend contract before implementation if insufficient.
3. **Implementation** — targeted edits inside declared write scope; preserve repo isolation and the steward-native event model.
4. **Verification** — targeted tests, manual steward smoke, at least one unhappy-path check, phase-specific validation.
5. **Learning / handoff** — update checkpoints, KB artifacts, prompt-policy candidates, improvement backlog, and write at least one entry to `decision_inputs.md` summarizing any finding from the slice that should bear on Phase 2 (see §15).

### 4.5 Phase 0 Dependencies

Before Phase 0 starts:
- Existing `agent_ops` Phase 0-4 assets remain in place and are treated as substrate, not discarded work.
- Paused `agent_ops` Phase 5 sub-efforts (`5_extraction`, `5_cross_model`, `5_skill_learning`, `5_portability_and_learning`) are explicitly retired or absorbed (see Primitive G).
- `Bid-Euchre` remains the only active target repo until Phase 2 decision gate.

---

## 5. Workstreams — The 8 Primitives

Each primitive maps to one or more of the 16 goals. Per analyst-a's
structural fix, each primitive is specified with three distinct
sections:

- **Work:** what gets built.
- **Phase 0 Readiness:** substrate-level "the thing exists and is wired" conditions, gatable before any Phase 1a or Phase 1 work.
- **Phase 1 Validation:** outcome-level "the thing produces the effect" conditions, measured during the preflight and proving run.

No speculative additions; every primitive ties directly to a named goal.
Primitive H (Reliability Lab) doubles as a portability de-risking surface
in Phase 2.

### Primitive A — Unified Trace and Observability Layer

**Goals served:** #2 (auditable/traceable), #10 (real-time monitoring), #11 (archiving/evaluation, in part).

**Work:**
- Finalize event schema around first-class IDs: `project_id`, `cell_id`, `session_id`, `task_id`, `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`.
- Ensure every lane, hook, and command emits into the unified schema.
- Deploy **Phoenix** as a local observability sidecar (single Docker container). Named workflows: trace inspection for reproducibility audits (#2); session-archive evaluation for lesson extraction (#11).
- Replace polling-based attention with event-driven monitoring for inbox urgency, CI failure, stall detection, and threshold breach.
- Retention policy: raw events kept runtime-only; promoted artifacts committed.
- Publish event-to-operator-signal p95 latency (first-cut target: ≤5 minutes; sub-plan may tighten).
- Publish message-bus p95 delivery latency (first-cut target: ≤30 seconds for durable messages).

**Phase 0 Readiness:**
- Event schema finalized; committed.
- Every lane and hook emits into the schema; hook coverage audit passes.
- Phoenix container deployable via a documented command; first-cut retention policy enforced.
- Event-driven attention routing wired end-to-end (at least one event class routes to operator without polling).
- Baseline latencies captured (§4.3) and latency-measurement surfaces published to dashboard.

**Phase 1 Validation:**
- Proving-run experiment fully reconstructable from trace corpus alone.
- Phoenix has a sustained hit count from the two named workflows across the proving run.
- Event-to-operator-signal p95 meets or beats target; zero stale-catch incidents recorded.
- Message-bus p95 meets or beats target; zero lost messages.

### Primitive B — Adaptive Dispatch, Skill Improvement, and Prompt-Policy

**Goals served:** #1 (self-improving), #4 (intent-aware delegation), #6 (lane/model selection), #7 (well-engineered prompts).

**Work:**
- Close SP-5-02 adaptive dispatch: advisor wired end-to-end, shadow mode → operator-visible recommendations → operator-approved promotion to active routing.
- Skill promotion loop: tie skill promotions/edits to observed task outcomes (via Primitive A events).
- **Prompt-policy registry** — new. Versioned contract per lane type and task type. Edits produce diffable policy versions tagged in traces via `prompt_policy_version`.
- Policy candidates follow candidate → confirmed lifecycle; promotion requires operator or analyst review.
- Analyst-vs-author routing rules encoded as policy, not convention.

**Phase 0 Readiness:**
- Adaptive-dispatch advisor wired end-to-end in shadow mode.
- Prompt-policy registry exists with an initial set of policies for orchestrator, ops, review, analyst-*, and author-* lanes.
- Skill-outcome linkage in place: skill promotions/edits referenceable against observed outcomes.
- Rollback path validated: policy-version pin works; dispatch policy can revert to prior shadow version.

**Phase 1 Validation:**
- At least one skill measurably promoted or edited based on outcome feedback during the proving run.
- Prompt-policy version present in ≥90% of proving-run trace records.
- Adaptive-dispatch decisions over the proving run would be approved by operator if audited (target: ≥80%).
- Analyst-vs-author routing errors ≤1 per 100 tasks during the proving run.

### Primitive C — Durable Memory and Knowledge Base

**Goals served:** #3 (durable memory), #12 (KB system), #14 (ADR capture).

**Work:**
- KB skeleton in `knowledge/` — 4 promoted-artifact classes plus two structured supplements:
  - `NOTES.md` — curated lessons, append-only, operator-edited prose.
  - `PLAYBOOKS.md` — runbooks. Procedural.
  - `anti_patterns.md` — actively consulted "do not do X" entries; `trigger → harm → preferred alternative`.
  - `incidents/<fingerprint>.md` — machine-fingerprinted per-incident files.
  - `adr/<NNN>-<slug>.md` — ADR-style architecture decisions.
  - `INDEX.md` — auto-generated from all of the above.
- MEMORY.md tightened to link into KB entries, not just recap.
- Retention and compaction policy for MEMORY.md, raw session logs, and raw trace exports.
- Commit policy: only promoted artifacts committed.
- **Planning templates** (`plans/_templates/`) with governing-plan, sub-plan, execution-plan, checkpoint, promotion/rollback, and review-rubric templates. Conformance via `/create-plan` and `/create-adr` skills.

**Phase 0 Readiness:**
- KB skeleton files exist, validated by a lint script that enforces structure.
- `INDEX.md` auto-regenerates via a committed script; targeted tests cover the generator.
- `/create-plan` and `/create-adr` skills present; templates conform.
- MEMORY.md compaction script present and smoke-tested.
- At least 2 ADRs recorded for Phase 0 design decisions (e.g., the readiness/validation split, the preflight insertion).

**Phase 1 Validation:**
- KB accumulates ≥10 lessons during preflight + proving run.
- ≥3 of those lessons cited downstream (in a plan, task, skill, or subsequent lesson) within the proving run.
- `anti_patterns.md` has ≥5 entries each tied to an observed failure mode.
- At least 1 additional ADR per major Phase 1 decision (kill signals, primitive changes, preflight outcomes).

### Primitive D — Archivist Script and Session Postmortem

**Goals served:** #11 (archiving/evaluation).

**Work:**
- `scripts/internal/archivist.py` — scheduled (nightly + end-of-session) script. Reads events, inbox, PR outcomes, task completions. Produces `knowledge/_candidates/<date>.md` with templated sections.
- Operator or analyst reviews candidates and promotes into NOTES / PLAYBOOKS / incidents / ADRs.
- Session postmortem: end-of-session trigger writes a per-session handoff into MEMORY.md + feeds candidates into the archivist queue.
- Not a lane. Invokable as a skill from any lane for real-time curation.

**Phase 0 Readiness:**
- Archivist script runs nightly and on end-of-session hook; targeted tests cover the templating and event-reading.
- Candidate file format committed; operator review workflow documented.
- `/run-archivist` skill available for ad-hoc invocation.
- Rollback path: candidate-to-promoted moves tracked; a promotion can be reverted by moving content back into `_candidates/`.

**Phase 1 Validation:**
- At least one promoted lesson observably cited downstream during the proving run.
- Candidate-to-promoted ratio measured weekly; ≥10% is the working floor.
- Session postmortems trigger reliably at end of each proving-run session.

### Primitive E — Messaging and Active Triage Closeout

**Goals served:** #8 (active triage), #9 (durable near-instantaneous messaging).

**Work:**
- Close message-bus proving debt. Absorb #2689 heartbeat pure-shell, #2690 lane-id dedup, #2691 hook JSON escape follow-ups.
- Publish bus p50 and p95 delivery latency to dashboard.
- Active issue triage: event-driven signals (CI red, review blocked, stalled lane, orphan worktree, token anomaly) auto-create GitHub issues with correct labels.
- Integrate `triaging-issues` skill with event-driven inputs.

**Phase 0 Readiness:**
- All three follow-up PRs merged; bus closeout debt resolved.
- Bus p50/p95 metrics published.
- Active-triage wiring live for at least 4 event classes (CI red, review blocked, stalled lane, token-burn anomaly).
- Rollback path: active-triage can be disabled via a feature flag without losing inbox state.

**Phase 1 Validation:**
- Zero lost-message incidents across preflight + proving run.
- Bus p95 meets or beats target set in Primitive A.
- Active triage produces ≥50% of issues created during the proving run (target floor: 10 auto-created issues across the run).
- Zero stale-catch incidents (events discovered minutes+ after occurrence).

### Primitive F — Token Economy Closeout

**Goals served:** #5 (token-efficient), supports #1 and #6.

**Work:**
- Execute token-economy Slice F evaluation protocol (drafted as PR #2716). The externally-committed 1-2 week observation window applies.
- Decision gate: adopt adaptive dispatch as active routing, retain as advisory, or kill.
- Lane × model × effort rollups surfaced in dashboard (already shipped via #2725) and integrated into the archivist's periodic briefings.
- Token-per-successful-merge metric wired into trace records and surfaced via Primitive A.

**Phase 0 Readiness:**
- Slice F observation window underway.
- Rollup dashboard live with the new metric.
- Baseline tokens-per-merge captured in §4.3.

**Phase 1 Validation:**
- Slice F decision recorded in MEMORY.md + committed evaluation artifact.
- Tokens-per-merge trending flat or down relative to baseline across the proving run.
- Tokens-per-proving-run-insight metric published.

### Primitive G — Existing-Debt Closeout

**Goals served:** non-capability primitive; gates all others.

**Work:**
- Portability manifest: zero hard-blocks in `ops/worktrees.py` (44 occurrences) and `ops/token_economy.py` (22 occurrences). Soft-coupling may remain.
- Retire `agent_ops/5_extraction`, `agent_ops/5_cross_model`, `agent_ops/5_skill_learning`, `agent_ops/5_portability_and_learning` subtrees with explicit status.
- Resolve remaining messaging-bus proving items (overlaps Primitive E).
- Platform-11 adaptive-dispatch partial reactivation (SP-5-02) closes inside Primitive B or is explicitly superseded.

**Phase 0 Readiness:**
- `PORTABILITY_MANIFEST` shows zero hard-blocks in the two named files.
- Each `agent_ops/5_*` subtree has an explicit resolution note (superseded / absorbed / abandoned) with a pointer to where remaining work lives.
- `agent_ops` plan fragmentation is gone.

**Phase 1 Validation:** n/a — this primitive is not validated against proving-run outcomes; it is purely a prerequisite.

### Primitive H — Reliability Lab and Replay Harness

**Goals served:** #15 (reliability / replay / failure-injection), supports #1, #2, #11.

**Work:**
- `tests/reliability/replay.py` — harness that reconstructs a task lifecycle from the event corpus (Primitive A) and asserts expected intermediate + final states.
- Failure-injection scenarios: lane stall, dead-letter message, stuck worktree, orphan cron, review-coordinator crash, Telegram outage.
- Automated postmortem generator: given a replay artifact, produce a draft incident file.
- Rollback validation: for each reversible change, the harness exercises forward and backward transitions. This is how goal #13 is verified end-to-end.
- Designed to double as a Phase 2 portability dry-run tool: once a shape audit produces adapter stubs, the harness can point at them and flag hidden coupling.

**Phase 0 Readiness:**
- Replay harness exists and can reconstruct at least 1 task-lifecycle scenario.
- At least 2 failure-injection scenarios implemented; both pass.
- Automated postmortem generator template committed and smoke-tested.
- Rollback validation covers every reversible change introduced in Phase 0.

**Phase 1 Validation:**
- Replay harness reconstructs ≥1 proving-run task lifecycle end-to-end with no drift from live events.
- ≥5 failure-injection scenarios exercised during the proving run (or during dedicated reliability sessions within it); all either pass or produce a documented incident.
- Automated postmortem generator produces ≥1 end-to-end incident draft from a real proving-run event stream.

---

## 6. Phase 1a — Platform Preflight

### 6.1 Purpose

Before committing to the full research proving run (which is long,
noisy, and partially confounded by research-level failure modes), run a
bounded end-to-end workflow that exercises every substrate surface. If
the platform has a structural flaw, it surfaces here in a short cycle
rather than weeks into the GBT retrain.

### 6.2 Preflight scope

A single small task family executed end-to-end through the full
platform. Candidates (operator chooses one at Phase 1a start):

- A scoped measurement refresh (e.g., re-run a standard comparator with updated rigor, produce a committed report).
- A small strategy tweak (e.g., a parameter-only change to an existing strategy, comparator evaluation, promotion or retention decision).
- A single-PR feature addition in the browser-game or experiment infrastructure.

Selection criterion: the task must exercise analyst shaping, author
implementation, ops orchestration, review, merged-PR outcome, skill
invocation, and prompt-policy application. Research outcome matters
secondarily; platform exercise matters primarily.

### 6.3 Preflight pass/fail checklist

Every item must pass for Phase 1a to green-light Phase 1:

| # | Surface | Pass criterion |
|---|---|---|
| 1 | Trace reconstruction | Task fully reconstructable from events alone (Primitive A) |
| 2 | Event-driven monitoring | At least one event during preflight triggers operator signal within target latency (Primitive A) |
| 3 | Routing | Analyst vs. author routing correct for every sub-task (Primitive B) |
| 4 | Prompt-policy | Every lane session in the preflight cites a prompt-policy version in its trace (Primitive B) |
| 5 | Messaging | Zero lost messages; p95 within target (Primitive E) |
| 6 | Active triage | At least one issue created via event-driven triage during preflight (Primitive E) |
| 7 | Archivist | Archivist produces at least one candidate file referencing the preflight; operator promotes at least one entry (Primitive D) |
| 8 | KB integration | At least one KB entry (NOTES, PLAYBOOK, anti-pattern, incident, or ADR) created during preflight (Primitive C) |
| 9 | Rollback | One reversible change (skill promotion, prompt-policy version, or dispatch policy) executed and rolled back successfully (Primitives B, H, goal #13) |
| 10 | Replay | Replay harness reconstructs the preflight task lifecycle without drift (Primitive H) |

### 6.4 Preflight outputs

`plans/steward_platform/1a_preflight/report.md` containing:
- Chosen preflight task, rationale, scope.
- Pass/fail status for each of the 10 checklist items.
- Any gaps identified, with Phase 0 follow-ups if re-opening is required.
- Ledger entries (§15) for each gap or win.

### 6.5 Preflight gate

- **All 10 pass:** proceed to Phase 1.
- **1-2 fail:** decide per-item whether a targeted fix inside preflight scope is sufficient, or whether a Phase 0 re-opening is required. If fixed in-scope, re-run the relevant checklist items.
- **3+ fail:** Phase 0 was not actually ready. Return to Phase 0, identify which primitives were under-built, resolve, and re-enter Phase 1a.

---

## 7. Phase 1 — Proving Run

### 7.1 Proving run selection

The proving run is a complete research program executed end-to-end
through the platform. Primary candidate: **GBT retrain informed by
human-gameplay data captured through the browser-game hosting
infrastructure.**

Why this candidate:
- Exercises the full research workflow: capture → analyze → hypothesize → design → implement → execute → evaluate → decide.
- Requires cross-lane coordination (analyst for shaping, author for implementation, ops for orchestration, review for quality, measurement for promotion gates).
- Has ground truth: the retrained strategy either measurably outperforms the baseline or it does not.
- Exercises the rigor apparatus documented in `.claude/rules/deferred/05_rigor.md`.
- Produces research value regardless of platform-test outcome — even if the platform proves weak, the retrain itself is useful research.

Alternative candidates (if GBT retrain is not the right shape for Phase 1):
- A new strategy addition executed end-to-end through the platform.
- A measurement methodology overhaul (new rigor regime applied across existing strategies).

### 7.2 Platform-level success criteria

Each of the 16 goals gets a measurable Phase 1 validation criterion
(these are the Phase 1 validation entries already specified per-primitive
in §5, collected here for readability):

| # | Capability | Measured by |
|---|---|---|
| 1 | Self-improving | ≥1 skill edits/promotions driven by outcome feedback during the run |
| 2 | Auditable/traceable | Full run reconstructable from trace corpus without transcript archaeology |
| 3 | Durable memory | ≥3 lessons from early in the run cited in later tasks |
| 4 | Intent-aware delegation | Analyst-vs-author routing errors ≤1 per 100 tasks |
| 5 | Token-efficient | Tokens per successful merge trending flat or down relative to baseline (§4.3) |
| 6 | Lane/model selection | Adaptive-dispatch decisions that operator would approve if audited ≥80% |
| 7 | Well-engineered prompts | Prompt-policy version cited in ≥90% of traces; policy deltas tied to outcome changes |
| 8 | Active triage | Share of issues created by event-driven triage vs. operator discovery ≥50%; ≥10 auto-created issues across the run |
| 9 | Durable messaging | Zero lost messages; p95 within target set in Primitive A |
| 10 | Event-driven monitoring | Event-to-operator-signal p95 within target; zero stale-catch incidents |
| 11 | Archiving/evaluation | Archivist candidate-to-promotion rate ≥10%; ≥1 promoted lesson with downstream use |
| 12 | KB system | KB grows during the run; promoted lessons findable via INDEX |
| 13 | Rollback/disable | At least one forward + backward transition exercised per reversible primitive; zero state-loss incidents |
| 14 | ADR capture | ≥1 ADR per major Phase 1 decision; every kill-criterion trigger produces an ADR |
| 15 | Reliability lab / replay | Replay harness reconstructs ≥1 proving-run task lifecycle without drift |
| 16 | Other | Any capability exposed by the run not captured above; documented in the proving-run report |

### 7.3 Separation of platform test from research test

The proving run has two separate evaluations that must not be conflated:

1. **Research evaluation** — does the GBT retrain actually beat the baseline at a statistically defensible level? Answered by the experiment's own rigor apparatus.
2. **Platform evaluation** — did the platform enable that experiment to execute efficiently, reproducibly, with compounding learning? Answered by §7.2.

A research failure is not a platform failure. A research success that
required operator heroics is not a platform success. The preflight
(Phase 1a) is the primary fast-fail platform check; Phase 1 is where
longitudinal platform evidence accumulates alongside research work.

### 7.4 Proving-run report

At end of Phase 1, the operator and analyst lanes produce
`plans/steward_platform/1_proving_run/report.md` containing:

- Research outcome (promoted / retained / killed).
- Per-capability evidence against §7.2 criteria.
- Identified platform gaps by severity.
- Proposed Phase 2 decision inputs.
- **Ledger synthesis:** each of the 16 capability rows resolves into one or more entries in `decision_inputs.md` (§15). The report reads from the ledger rather than duplicating it.

---

## 8. Phase 2 — Decision Gate

Phase 2 is a planning phase, not a build phase. Its output is either a
successor governing plan or a scoped sub-plan driving Phase 3+.

### 8.1 Inputs

- Phase 1 proving-run report.
- Phase 1a preflight report.
- Fund + RIN-SnD shape audits (from §4.2).
- Decision-inputs ledger (§15), filtered by decision axis.
- Any deferred workstreams from draft 1/2 not absorbed into the 8 primitives.

### 8.2 Decisions to make

1. **Portability.** Does the proving run establish that the platform produces value worth porting? If yes, target: Fund first or RIN-SnD first? If no, what specific weaknesses need further single-repo hardening?
2. **Meta-layer.** What cross-project state is actually useful? Daily brief? Shared KB patterns? A dedicated meta-steward home? A meta-orchestrator lane, or a skill family invokable from each project? Answered by what the proving run revealed about operator pain.
3. **cmux adoption.** Only relevant if portability goes forward. Shape: workspace-per-project, notification bindings, browser surfaces, operator action bindings.
4. **Next proving run.** Should Phase 3 include a proving run in Fund or RIN-SnD (the portability falsification test) before a full port? Default: yes.

### 8.3 Kill signals

Phase 2 may also surface kill signals for primitives that did not earn
their keep. Each of the 8 primitives has kill criteria (§11). Kill
decisions are first-class Phase 2 output alongside scope-expansion
decisions. Every kill decision spawns an ADR via Primitive C.

---

## 9. Existing Platform Baseline and Adaptation Path

Unchanged from draft 2 §8. Summary:

- Reuse `steward-session.sh`, `ops.py`, `src/bid_euchre/ops/core/`, task queue, message bus, attention broker, worker pool, role prompts.
- Adapt before replace. Replacement justified only when an existing piece materially blocks a new capability.
- Known gaps (portability debt, token-economy incomplete, messaging proving incomplete, lane layout over-sized) are addressed by Primitives B/E/F/G rather than left as background debt.

---

## 10. Target Architecture

Preserved from draft 1/2 §9 where still applicable; items deferred to
Phase 2 are marked.

### 10.1 Platform shape (Phase 0 target)

Single Bid-Euchre steward cell with:
- Always-on: `orchestrator`, `ops`, `review`.
- Off-by-default, bounded-activation: `analyst-*`, `author-*`, `brws-author-*`, `flex-*`.
- No meta-surface in Phase 0. Deferred to Phase 2 decision.

### 10.2 Truth model

- Repo-local runtime state = operational truth.
- Phoenix = observability/eval UI, not canonical state.
- KB artifacts = promoted knowledge, not raw evidence.
- GitHub = PR/review/CI truth.
- Meta-level truth: not applicable in Phase 0 (no meta-surface).

### 10.3 Lane policy (Phase 0 target)

Reduced from current 19-lane fleet:
- Always-on: orchestrator + ops + review (3).
- Specialist activation under bounded rules with operator-visible triggers.
- Retirement: unused specialists parked after idle thresholds.
- Routing: analyst owns shaping/findings/diagnostics; author owns merge-oriented implementation.

### 10.4 Event and trace model

As in draft 1 §9.7. First-class IDs canonical. Steward keeps a native
event model; Phoenix is a consumer, not a source.

### 10.5 Knowledge architecture (Phase 0)

Per-repo KB with 4-item promoted-artifact skeleton plus anti-pattern and
ADR supplements (§5 Primitive C). Meta-KB deferred to Phase 2.

### 10.6 Prompt / rule / skill layering

- User-level meta `CLAUDE.md` for global steering.
- User-level skills for reusable workflows.
- Project `CLAUDE.md` for repo constants.
- Project rules for path/topic-specific behavior.
- Project skills for repo-local workflows.
- **Prompt-policy registry** (§5 Primitive B) sits alongside these layers.
- Generated briefings for current incidents, lessons, steering notes.

### 10.7 Deferred cross-project architecture

Everything in draft 1 §9 describing meta-surfaces, cross-project
federation, planning-skeleton mirroring, or cross-repo promotion flow is
deferred to Phase 2 decision gate. It is not abandoned; it is
evidence-gated.

---

## 11. Kill Criteria

Per-primitive kill criteria. If a primitive fails its criterion during
Phase 0, 1a, or 1, Phase 2 evaluates whether to rework, downgrade, or
retire it. Kill triggers spawn an ADR.

Usage-based rather than clock-time-based per operator directive.

| Primitive | Kill criterion |
|---|---|
| A — Trace/observability | Phoenix has <5 operator opens across the entire proving run → demote to JSONL + notebook only |
| B — Adaptive dispatch + skill + prompt-policy | Skill promotions/edits driven by outcome feedback = 0 across the proving run → revert to manual skill curation |
| C — KB | <3 promoted lessons observably cited during the proving run → collapse to single NOTES.md per repo |
| D — Archivist | Candidate-to-promotion rate <10% across the proving run → rewrite template or retire script |
| E — Messaging/triage | Active triage produces <20% of issues created across the proving run → revert to operator-discovery model |
| F — Token economy | Slice F cannot produce a defensible promote/retain/kill decision → freeze adaptive dispatch in advisory indefinitely |
| G — Debt closeout | Not kill-able; blocks all other primitives |
| H — Reliability lab | <2 replay scenarios pass or <3 failure-injection scenarios exercised by end of Phase 1 → demote to a simpler event-diff assertion set; postmortem generator deferred |

---

## 12. Risks

| Risk | Mitigation |
|------|------------|
| Phase 0 primitive scope creep | Readiness/validation split keeps substrate tight; every primitive done-when is either a file, a test, or a metric |
| Research stall conflated with platform stall in proving run | §7.3 enforces separation; preflight (§6) provides a fast-fail platform check |
| Phoenix becomes unused infrastructure | Kill criterion §11-A; two named workflows at deploy time |
| Archivist produces noise, not signal | Kill criterion §11-D; candidate-to-promotion rate measured |
| Prompt-policy pollution degrades steering | Candidate → confirmed lifecycle; operator-visible policy versions; rollback via policy version pinning |
| Platform-11/13 repeat-postponement pattern | Operator has confirmed constraints that paused earlier attempts no longer apply |
| Portability option decays because we defer it | §4.2 parallel shape-audit work keeps the option warm at low cost |
| Event-driven monitoring adds attention noise | Signal thresholds tuned by archivist feedback; event classes can be muted via policy |
| KB grows without compaction | §5-C retention policy; INDEX highlights stale content |
| Lane reduction causes bottleneck on active lanes | Specialist activation thresholds tunable; retirement only if idle, not if contention |
| Baseline drifts or is lost | Baselines committed as a versioned artifact in §4.3; re-measurement part of Phase 2 input synthesis |
| Preflight passes trivially without exercising surfaces | Preflight pass/fail checklist (§6.3) is granular (10 items across all primitives); selection criterion (§6.2) forces cross-lane exercise |

---

## 13. Success Criteria

1. All 8 primitives reach their Phase 0 Readiness criteria.
2. Phase 1a preflight passes all 10 checklist items or completes the re-work loop per §6.5.
3. Proving run executes end-to-end through the platform with measurable attention compression relative to baseline (§4.3).
4. Proving-run platform evaluation produces a per-capability scorecard against all 16 goals.
5. Decision gate (Phase 2) produces a scoped successor plan (portability, meta-layer, further iteration, or combination) based on proving-run evidence *read from the decision-inputs ledger* (§15), not reconstructed from transcripts.
6. At least 3 KB lessons have observable downstream use during the proving run.
7. Tokens per successful merge during the proving run are flat or declining relative to baseline.
8. Messaging bus has zero lost-message incidents and published p95 latency meeting target.
9. Adaptive dispatch either ships as active routing or is documented as retained-advisory with evaluation evidence.
10. At least one skill and one prompt-policy have been promoted or edited with outcome-feedback evidence.
11. Reliability-lab replay harness reconstructs ≥1 proving-run task lifecycle without drift.
12. Rollback paths validated for every reversible change introduced in Phase 0.
13. `decision_inputs.md` contains ≥20 tagged entries by end of Phase 1, with at least one entry per capability in §2.

---

## 14. Open Items

1. **Proving-run scope.** GBT retrain is primary candidate; alternates listed in §7.1. Operator confirms selection before Phase 1.
2. **Preflight scope.** Candidate task families listed in §6.2. Operator chooses at Phase 1a start based on what best exercises all surfaces.
3. **Prompt-policy schema.** Registry structure, versioning semantics, lifecycle state machine detailed in a sub-plan under Primitive B.
4. **Event-driven latency target.** First-cut ≤5 minutes p95; sub-plan under Primitive A may tighten based on baseline.
5. **Archivist template structure.** Candidate-file sections, promotion criteria, review cadence specified in a sub-plan under Primitive D.
6. **KB INDEX generation.** Tooling choice specified in a sub-plan under Primitive C.
7. **Phoenix local deployment details.** Docker-compose shape, retention, exporter path specified under Primitive A.
8. **Specialist activation thresholds.** Exact idle-to-parked and task-arrival-to-active thresholds specified in a sub-plan.
9. **Target-repo shape-audit output format.** Standardized one-page template for Fund and RIN-SnD audits.
10. **Phase 2 decision template.** Decision-gate rubric and output format specified at end of Phase 0 to avoid recency bias.

---

## 15. Decision-Inputs Ledger

A persistent ledger at `plans/steward_platform/decision_inputs.md`
captures every finding during Phases 0, 1a, and 1 that should bear on
the Phase 2 decision gate. Purpose: prevent Phase 2 from being
archaeological. Every primitive, the preflight, the proving run, the
archivist script, and the parallel shape audits feed entries into this
ledger.

### 15.1 Entry schema

Each entry must include both operational fields (primary routing at
Phase 2) and classification tags (secondary filtering):

```
## [YYYY-MM-DD] <short title>

**Decision Axis:** portability | meta-layer | kill | next-wave | (multiple, comma-separated)
**Owner:** <lane-id or operator>
**Review By:** <YYYY-MM-DD or "Phase 2 entry">
**Disposition:** open | incorporated | superseded | rejected
**Source:** primitive-X | preflight | proving-run | shape-audit-<repo> | archivist | ad-hoc
**Tags:** <comma-separated from taxonomy below>
**Severity:** high | medium | low
**Evidence:** <link to commit / trace / incident / artifact>

### Finding
<what we observed>

### Implication for Phase 2
<what this suggests about the decision axis above>
```

### 15.2 Decision axes (primary routing)

Each entry is routed to one or more of the four Phase 2 decisions:

- **portability** — evidence that bears on whether to port to a second repo, and which repo first.
- **meta-layer** — evidence about what cross-project mechanism (if any) earns its slot.
- **kill** — evidence that a primitive should be retired or downgraded.
- **next-wave** — evidence about what else the platform should take on after Phase 2.

An entry without a decision axis cannot be written; that's the
operational discipline.

### 15.3 Tag taxonomy (secondary classification)

- `portability-signal` — evidence the contract will or will not port cleanly.
- `meta-layer-signal` — evidence a cross-project mechanism would or would not earn its slot.
- `capability-gap` — a goal from §2 that the phase did not deliver well enough.
- `capability-win` — a goal that over-delivered.
- `kill-signal` — evidence a primitive should be retired or downgraded.
- `surprise-finding` — something the plan did not anticipate.
- `target-repo-shape` — findings from Fund / RIN-SnD shape audits.
- `cost-signal` — operator-time, token, or complexity cost exceeding expectation.
- `adr-trigger` — a finding that warrants a formal ADR under Primitive C.

### 15.4 Disposition lifecycle

- `open` — under active review; Phase 2 has not yet resolved it.
- `incorporated` — reflected in a Phase 2 decision or in a subsequent plan revision.
- `superseded` — replaced by a later entry; the referenced newer entry carries the disposition.
- `rejected` — evaluated and deliberately not acted on; reasoning in a linked ADR.

Disposition transitions are additive (a new entry closes out or
supersedes the old); the original entry is never edited.

### 15.5 Ownership and review cadence

- Each entry has an owner responsible for its disposition at Phase 2.
- Entries with `Review By: Phase 2 entry` are reviewed as a batch at Phase 2 start.
- Entries with a concrete `Review By` date are expected to be dispositioned by that date; overdue entries surface in the operator briefing.
- End-of-session archivist runs produce a ledger digest: open entries by decision axis, overdue review-by dates, recent additions.

### 15.6 Write expectations

- Every primitive's Phase 0 Readiness verification produces at least one ledger entry summarizing the primitive's substrate state.
- Every primitive's Phase 1 Validation produces at least one ledger entry summarizing the outcome evidence.
- Every kill-criterion trigger (§11) produces a ledger entry with `Decision Axis: kill`, `Tags: kill-signal`, and spawns an ADR.
- The archivist script's nightly output proposes new ledger entries; operator reviews and accepts or rejects each.
- The preflight report (§6.4) is structured so that each of the 10 checklist items produces one or more ledger entries.
- The proving-run report (§7.4) is structured so that each of the 16 capability rows produces one or more ledger entries.
- The parallel target-repo shape audits produce entries under `portability` decision axis with `target-repo-shape` and `portability-signal` tags.
- Ledger entries are additive-only; corrections append a new entry referencing the earlier one rather than editing the original.

### 15.7 Phase 2 use

The Phase 2 decision gate begins by reading the ledger filtered by
decision axis:

- Portability decision: `Decision Axis: portability` entries, tag-filtered by `portability-signal` + `target-repo-shape` + `cost-signal`.
- Meta-layer decision: `Decision Axis: meta-layer` entries, tag-filtered by `meta-layer-signal` + `surprise-finding` + `cost-signal`.
- Kill decisions: `Decision Axis: kill` entries, with `kill-signal` + supporting `capability-gap` entries.
- Next-wave ambition: `Decision Axis: next-wave` entries, tag-filtered by `capability-win` + `surprise-finding`.

Any entry still in `Disposition: open` with `Severity: high` becomes a
mandatory Phase 2 input.

---

## 16. Delta From Draft 2

Recording what changed relative to draft 2 so future readers can
reconstruct the revision:

- **Readiness/validation split.** Every primitive now has distinct Phase 0 Readiness and Phase 1 Validation criteria. This resolves analyst-a's P0 finding that Phase 1 depended on Phase 0 done-when criteria which themselves required Phase 1 evidence — an impossible boundary.
- **Phase 1a Platform Preflight added.** New phase between Phase 0 and Phase 1 that exercises every substrate surface under a short-scoped task with a 10-item pass/fail checklist. Provides fast-fail platform check before committing to the full research proving run. Resolves analyst-a's P1 finding on proving-run confounding.
- **Phase 0 Step 0: Baseline Capture added.** Explicit artifact at `plans/steward_platform/0_hardening/baseline.md` captures attention compression, token-per-merge, issue-discovery, message-bus latency, and event-latency baselines. Resolves analyst-a's finding that baselines were referenced without being defined.
- **Ledger schema upgraded.** Added `Decision Axis`, `Owner`, `Review By`, and `Disposition` fields. Decision axis is primary routing; tags become secondary classification. Resolves analyst-a's P2 finding on ledger operationalization.
- **Consistency errors fixed.** "7 primitives" corrected to 8 throughout. "#1-#13" corrected to "#1-#16" where applicable. Stale references to "13 goals" updated. Resolves analyst-a's P2 finding.
- **Time-boxes removed per operator directive.** "6-8 week" Phase 0 budget gone. Kill criteria converted from clock-time ("within 4 weeks") to usage-based ("across the proving run"). Externally-committed observation windows (e.g., Slice F 1-2 weeks) retained since they are external commitments, not plan-level budgets.
- **First-cut target latencies made concrete.** Event-to-operator-signal p95 ≤5 minutes; message-bus p95 ≤30 seconds. Open for sub-plan tightening. Resolves the "undefined targets" finding.
- **Active-triage issue count N made concrete.** Floor of 10 auto-created issues across the proving run. Open for sub-plan revision.

No capabilities cut. No phases shortened. The plan got tighter, not
thinner.

---

## Outcome

_To be filled after implementation._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN, #NNN
- Notes: deviations from plan, preflight and proving-run outcomes, Phase 2 decisions.
