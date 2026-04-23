# Steward Platform — Governing Plan (Draft 6)

**Date:** 2026-04-23
**Status:** PROPOSED — revision of `governing_plan.draft5.md` incorporating analyst-b's review (1045-line critique at `plans/steward_platform/draft5_review_analyst-b.md`, graded draft 5 at B+, recommended revise→draft 6→short-review→promote) plus three operator directives:
- Reinstate clock-time tracking as **relative measurement**, not absolute budget.
- Adopt **agent-first plan and KB design** as a consistent theme across all artifacts (new goal #16).
- Resolve F3 (Primitive B weight): keep B unified with a sub-deliverables table (Option B).
**Scope:** Mature the existing Bid-Euchre steward control plane into a full-ambition single-repo platform (self-improving, auditable, durably remembered, token-efficient, actively triaging, replay-testable, agent-readable), prove it on a complete research run, and only then decide what to port and whether a meta-layer earns its slot.
**Supersedes:** `governing_plan.draft5.md`, `governing_plan.draft4.md`, `governing_plan.draft3.md`, `governing_plan.draft2.md`, and `governing_plan.md`. The prior `agent_ops` governing plan remains historical record for shipped Phase 0-4 work and in-flight Phase 5 work absorbed into Phase 0 below.

**Revision drivers (draft 5 → draft 6):**
- **F1 (high) — clock-time falsifiability gap.** Operator directive: clock-time tracking returns as *relative measurement* (not absolute budget). Combined with analyst-b's soft-re-evaluation-trigger fix, "insufficient evidence" primitives are differentiated by activity volume AND elapsed time relative to other primitives. See §11 preamble + §13 + per-primitive Readiness sections.
- **F2 (high) — Primitive D's GC half is Phase-0-labeled but Phase-1-substantive.** The KB doesn't exist at Phase 0 start; GC has nothing to detect. Fix: split archivist. Inflow (lessons) is Phase 0; outflow (GC) is Phase 1, parallels Primitive H. Tightened Phase 1 Validation: ≥3 acceptances across ≥2 distinct categories (was ≥1 trivially clearable).
- **F3 (medium-high) — Primitive B weight.** Operator chose Option B: keep B unified with a sub-deliverables table mapping each of B's 7 deliverables to its own readiness/validation mini-rows. Primitive count stays at 8 total / 7 Phase 0.
- **F4 (medium) — Preflight item 10 swap (legibility for replay) didn't substitute on substance.** Fix: replace item 10 with an end-to-end data-discipline probe (trace + bus + KB + task-packet mutual consistency); fold agent-readability scorecard into item 8 (KB integration).
- **F5 (medium) — §10.7 fallback options lacked stated default.** Fix: Option 1 (defer portability) is the named default; Option 2 (port-with-compensatory-scoping) requires three named conditions all met.
- **F6 (medium) — `compile_decision_inputs.py` was load-bearing but no primitive owned it.** Fix: added to Primitive C Work + Phase 0 Readiness; `/compile-decision-inputs` skill registered.
- **F7-F13 (low-medium) — quality-of-life adoptions.** Worked example for `harness_assumptions.md` schema; GC threshold tightening (folded into F2); digest script success-criterion ownership (folded into F6); agent-readability provisional 7/10 floor in governing plan; Goal #8 ownership disambiguation between B (approval classes) and E (event-driven triage); event schema versioning (`schema_version` field, v1.N additive, v2 breaking); §16 Delta editorial accuracy.
- **Operator directive — Goal #16 Agent-first plan and KB design.** All durable artifacts are designed for agent navigation and execution first; human readability is secondary. Reframes the existing legibility scorecard as agent-readability scorecard. Affects template enforcement under Primitive C and is a consistent theme across all repo plans, not just this initiative.
**Earlier revision drivers preserved for lineage:** see §17-§19 (Delta from drafts 5/4/3).

---

## 1. Decision

Build the steward platform out to its full vertical ambition inside the
Bid-Euchre repo first, prove it by executing an end-to-end research program
through it (e.g., GBT retrain informed by human-gameplay capture, or a
measurement-methodology-overhaul alternative if data is insufficient), and
use the proving run's outcomes to decide portability scope and meta-layer
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

The 16 capabilities below are the **closed Phase 0 scope-lock**. Operator
or reviewer proposals for additional capabilities during Phase 0 are
filed as Phase 2 Decision Inputs (see §15), not absorbed into Phase 0.
This list is a floor for what the platform must eventually support; it is
also the ceiling for what Phase 0 attempts to build.

The platform must satisfy all of the following inside Bid-Euchre by the
end of Phase 1, with substrate standing up in Phase 0 and
outcome-evidence generated during Phases 1a and 1:

1. **Self-improving** — skill promotion, prompt-policy evolution, and adaptive dispatch feed back into future task execution.
2. **Auditable and traceable** — every task, message, event, and decision is reconstructable from durable artifacts without transcript archaeology.
3. **Durable memory over time** — lessons from session N observably influence session N+K; MEMORY.md and KB compound rather than decay.
4. **Intent-aware delegation** — the platform chooses *shape / delegate / author* correctly for each task type, with the analyst-vs-author boundary enforced.
5. **Token-efficient** — tokens per successful merge, per proving-run decision, and per research insight are measured and trend flat or down.
6. **Adaptive lane and model selection** — lanes turn on and off under bounded rules; model/effort selection matches task complexity.
7. **Well-engineered prompts** — prompts sent to lanes are authored under a versioned prompt-policy contract, not ad-hoc per invocation.
8. **Active issue triage** — issue *discovery* is driven by event-driven signals not operator discovery after the fact (Primitive E owns this); high-risk actions are *escalated* via approval classes (Primitive B sub-deliverable B.6/B.7) before they surface as issues at all. Both halves must work for goal #8 success.
9. **Durable near-instantaneous messaging** — the message bus preserves lane-to-lane communication with low p95 latency and zero loss.
10. **Event-driven monitoring** — attention is driven by events as they occur, not polling loops that catch conditions after they've gone stale.
11. **Chat archiving and evaluation** — session chats are archived, mined for lessons, and feed back into skill and prompt-policy improvement.
12. **Knowledge-base system** — repo-local KB with clear structure, auto-indexed, earned-by-content growth.
13. **Rollback / disable paths** — every platform change (skill promotion, prompt-policy version, adaptive-dispatch shift, KB restructure) is reversible in one step without losing previously accumulated state.
14. **ADR-style architecture decision capture** — decisions about contracts, lane topology, model choices, promotions, and kill signals are recorded in a structured, auditable form distinct from lessons, playbooks, and incidents.
15. **Reliability lab / replay / failure-injection** — the platform can replay multi-lane task lifecycles from durable events, simulate lane stalls and dead-letter messages, and generate postmortems automatically. Used both as a regression test and as a future portability-validation harness.
16. **Agent-first plan and KB design** — all durable artifacts (governing plan, sub-plans, KB entries, ADRs, prompt-policies, decision-input subsections, planning templates, briefings, run reports) are designed for agent navigation and execution first. Concrete conventions: predictable section IDs and headers; machine-parseable structured fields where useful; consistent cross-reference patterns (file:line, anchor-style links); grep-clean naming; loadable as agent context with minimal preamble; subsection schemas have worked examples to prevent drift. Human readability is a secondary consideration; clarity for the agent loading the artifact is primary. This is a consistent theme across all repo planning artifacts going forward, not just this initiative; planning templates under Primitive C enforce conformance.

Deferred until Phase 2 decision gate (post-proving-run):

- Horizontal scope expansion (Fund, RIN-SnD adoption)
- `cmux`-based operator UX for multi-project supervision
- Dedicated meta-steward home / cross-project state directory
- Meta-orchestrator lane or pattern
- Cross-project promotion flow
- Planning skeleton mirror/sync mechanism

These remain eventual platform targets. They do not ship until the
proving run establishes what cross-project state is worth federating and
what cross-project decisions are worth centralizing.

**Deferred-items home:** `plans/steward_platform/post_phase2_sidecar.md`
is the active reference for deferred platform-evolution ideas (including
the items above and several architecture extensions). The sidecar
records each idea with explicit revisit criteria — when and under what
evidence the idea earns its way back into active scope.

**External practice reference:** `plans/steward_platform/phase2_harness_engineering_research.md`
is a borrowed-practices memo synthesizing harness-engineering patterns
from OpenAI, Anthropic, LangGraph, and Thoughtworks. Used as reference
input when shaping Phase 2 decisions and deciding which of the 8 Phase 0
primitives are the right targets for Phase 2 investment.

---

## 3. Key Definitions

- **Vertical ambition:** the capability depth of the platform inside a single repo.
- **Horizontal ambition:** the number of repos the platform concurrently serves.
- **Phase 0 readiness criteria:** substrate-level conditions that must be true to enter Phase 1a. "The thing exists and passes targeted tests." Does not require proving-run outcome evidence.
- **Phase 1 validation criteria:** outcome-level conditions measured during the proving run. "The thing produces the effect it was built for." Measured against real usage.
- **Platform preflight (Phase 1a):** a bounded end-to-end workflow that exercises every substrate surface (trace, routing, messaging, archivist, rollback, skill loop, prompt-policy) under a short-scoped task. Purpose: fast-fail platform check before committing to the full research proving run.
- **Proving run (Phase 1):** a complete end-to-end research program executed through the platform, used to validate that the platform produces observable research value. Primary candidate: GBT retrain informed by human-gameplay capture, subject to data-sufficiency check (§6.1).
- **Hardening gate (Phase 0):** a closed list of existing-debt items and new-primitive readiness deliverables that must be complete before any Phase 1a or Phase 1 work begins.
- **Decision gate (Phase 2):** a planning phase, not a build phase, whose output is a subsequent governing plan or scoped sub-plan based on proving-run findings.
- **Prompt-policy:** the versioned contract describing how prompts are constructed for each lane type and task type. A prompt-policy edit is auditable and reversible.
- **Archivist:** a scheduled workflow (not a persistent lane) that reads events, messages, task outcomes, and review results, producing candidate lessons, incidents, and KB promotions for operator review.
- **Event-driven monitoring:** attention routing in which events (CI failure, inbox urgency, stall detection, threshold breach) produce operator or lane signals within a target latency, rather than being discovered by a polling cron that finds them stale.
- **Analyst lane:** shapes, investigates, diagnoses, recommends. Findings-oriented.
- **Author lane:** implements, tests, ships PRs. Merge-oriented.
- **Phase 2 Decision Inputs subsection:** the structured write surface (§15) that every primitive closeout, sub-plan outcome, preflight/proving-run report, and shape audit ends with. Four prompts + disposition status. Read at Phase 2 via an auto-generated digest.
- **Relative clock-time tracking:** elapsed wall-clock time is recorded per primitive readiness, per Phase 1 validation accumulation, and per debt-closeout slice. *Recorded as measurement, not as budget* — no absolute targets are committed in the plan because we don't know what's realistic until we measure. Used as one of two signals (alongside activity volume) to differentiate "primitive failed" from "insufficient evidence" at Phase 2.
- **Agent-readability:** the property of a durable artifact (plan section, KB entry, ADR, sub-plan, briefing, etc.) being navigable, parseable, and loadable by an agent with minimal preamble. Tested by the agent-readability scorecard (formerly "legibility scorecard"; renamed to clarify that the primary audience is agents, not humans, per goal #16).
- **Soft re-evaluation trigger:** when a primitive sees activity below its kill-criterion threshold during the proving run, the kill criterion does not fire automatically. Instead, the primitive routes to Phase 2 flagged as "insufficient evidence" with both signals attached: activity volume and elapsed-time relative to other primitives. Phase 2 decides retire / re-scope / re-evaluate-in-Phase-3. Default is re-evaluate.

---

## 4. Execution Structure

### 4.1 Phases

| Phase | Directory | Description | Depends On |
|-------|-----------|-------------|------------|
| 0 | `0_hardening` | Close existing debt and build substrate for **7 primitives (A-G)** to readiness; capture baselines | Existing `agent_ops` Phase 0-4 assets |
| 1a | `1a_preflight` | Short-scoped platform preflight: one bounded end-to-end workflow exercising every substrate surface; go/no-go for Phase 1 | Phase 0 readiness criteria met |
| 1 | `1_proving_run` | Execute a complete research program through the platform **and concurrently build out Primitive H (replay harness, failure-injection catalog, postmortem generator, canary task suite, idempotency discipline)**; measure against Phase 1 validation criteria | Phase 1a pass + data-sufficiency check (§6.1) |
| 2 | `2_decision_gate` | Evaluate proving-run evidence via the decision-inputs digest; decide portability scope, meta-layer shape, and next-wave ambitions; produce Phase 3 scope as sub-plan or successor governing plan. **Phase 2 cannot decide portability unless Primitive H has completed its Phase 1 Validation** (§10.7 design coupling) | Phase 1 complete |
| 3 | _(reserved)_ | Shape TBD by Phase 2 decision | Phase 2 |
| 4 | _(reserved)_ | Shape TBD | Phase 3 |

No absolute clock-time budgets are attached to phases — we don't know what
is realistic until we measure. Sequencing and readiness/validation gates
are the discipline; the work takes the time it takes. **However**,
elapsed wall-clock time is *measured* per primitive readiness, per Phase
1 validation accumulation, and per debt-closeout slice (see §3
"Relative clock-time tracking"). These measurements feed Phase 2
decision inputs (cost-signal axis) and inform the soft re-evaluation
trigger (§11 preamble). The principle: track time relatively, not
absolutely; let measurement teach what's normal.

### 4.2 Parallel target-repo shape audit during Phase 0

One analyst-lane task per repo, **budgeted at 2-3 days of analyst time
per repo** (not background work; not unlimited). Running concurrent with
Phase 0, not competing for primary author-lane attention.

Fund + RIN-SnD shape audit output lives at
`plans/steward_platform/0_hardening/target_repo_audit.md`, one section
per repo, each using this fixed format:

- **Build system, test framework, CI shape.**
- **Branch conventions, release conventions.**
- **`.claude/` presence and layout (if any).**
- **Hosted-service dependencies and external contracts.**
- **Tooling conventions** (package manager, linter, formatter, type checker).
- **Portability-debt preview.** Per-file mapping of the top-10 most steward-coupled files in the target repo, classified `hard-block` vs. `soft-coupling` using the `PORTABILITY_MANIFEST.md` taxonomy.
- **Lane-layout feasibility.** Which current steward lane roles would plausibly map 1:1 vs. require adapters vs. not apply at all.
- **Top 3 adoption risks** in operator's own words.

Each audit section ends with a Phase 2 Decision Inputs subsection (§15).

Purpose: produce a decision-grade portability input for Phase 2, not a
surface inventory. If the audit cannot be produced to this depth in 2-3
days per repo, that itself is a portability-signal finding that feeds a
Phase 2 Decision Input.

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

The baseline artifact ends with a Phase 2 Decision Inputs subsection (§15).

### 4.4 Step Template (per slice)

1. **Scope lock** — read governing plan, phase plan, active sub-plans; establish slice boundary.
2. **Contract check** — inspect platform contract, prompt-policy registry, KB skeleton, trace schema, adapter contract; amend contract before implementation if insufficient.
3. **Implementation** — targeted edits inside declared write scope; preserve repo isolation and the steward-native event model.
4. **Verification** — targeted tests, manual steward smoke, at least one unhappy-path check, phase-specific validation.
5. **Learning / handoff** — update checkpoints, KB artifacts, prompt-policy candidates, improvement backlog; **append a Phase 2 Decision Inputs subsection** (§15) to the sub-plan outcome block or primitive closeout document; **record elapsed wall-clock time** for the slice (start → close) under a `Slice elapsed:` line. No slice is considered complete without both the subsection and the elapsed-time record.

### 4.5 Phase 0 Dependencies

Before Phase 0 starts:
- Existing `agent_ops` Phase 0-4 assets remain in place and are treated as substrate.
- Paused `agent_ops` Phase 5 sub-efforts (`5_extraction`, `5_cross_model`, `5_skill_learning`, `5_portability_and_learning`) are explicitly retired or absorbed (see Primitive G).
- `Bid-Euchre` remains the only active target repo until Phase 2 decision gate.
- ADR `knowledge/adr/001-platform-pattern-reset.md` is filed at Phase 0 kickoff, naming the specific constraints that paused Platform-11 and Platform-13 and the specific conditions that have since lifted (see §12 Risks row 6).

---

## 5. Workstreams — The 8 Primitives

Each primitive maps to one or more of the 15 goals. Per the analyst's
structural fix, each primitive is specified with three distinct sections:

- **Work:** what gets built.
- **Readiness:** substrate-level "the thing exists and is wired" conditions — Phase 0 for primitives A-G, Phase 1 for primitive H.
- **Validation:** outcome-level "the thing produces the effect" conditions, measured during preflight (for A-G) and during the proving run (for A-H).

No speculative additions; every primitive ties directly to a named goal.
Primitive H (Reliability Lab) is **intended to be** usable as a Phase 2
portability de-risking surface (§10.7); this reuse is design intent, not
verified readiness.

**Primitive-to-phase mapping:**

- **Phase 0 (7 primitives):** A, B, C, D, E, F, G. These must reach readiness before Phase 1a preflight is attempted.
- **Phase 1 (1 primitive + proving run):** H builds out concurrently with the proving run. The proving run does not wait for H to be done; H accumulates coverage as the run proceeds. By end of Phase 1, H must meet its Phase 1 Validation criteria for the Phase 2 gate to be able to make a portability decision.

Primitive ordering in §5: A, B, C, D, E, F, G, H (alphabetical; matches
§11 kill-criteria table ordering). Phase membership is noted in each
primitive's header.

### Primitive A — Unified Trace and Observability Layer (Phase 0)

**Goals served:** #2 (auditable/traceable), #10 (real-time monitoring), #11 (archiving/evaluation, in part).

**Work:**
- Finalize event schema around first-class IDs: `project_id`, `cell_id`, `session_id`, `task_id`, `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`, `schema_version`.
- **Event schema versioning (F12):** schema carries a `schema_version` field. Phase 0 schema is `v1`; additive evolutions (new fields, new event classes) are `v1.N` and remain replay-compatible; breaking changes require `v2` with an explicit migration plan filed as a sub-plan under Primitive A. Replay harness (Primitive H) asserts `v1.N`-to-`v1.M` compatibility before a Phase 1 replay claim is accepted.
- Ensure every lane, hook, and command emits into the unified schema.
- Deploy **Phoenix** as a local observability sidecar (single Docker container). Justified by two named workflows:
  1. **Reproducibility audits.** Trigger: an operator or analyst files a "replay this task" request against a task_id. Consumer: analyst lane. Cadence: on demand, expected ≤1/week. Output: a green "matches event corpus" note *or* an incident draft with the divergence timeline. A workflow "counts" toward §11-A kill-criterion measurement only when it produces one of these two outputs.
  2. **Session-archive evaluation for lesson extraction.** Trigger: nightly archivist run (Primitive D). Consumer: archivist script + operator reviewer. Cadence: nightly. Output: candidate-lessons file at `knowledge/_candidates/<date>.md` whose promoted items flow into NOTES / PLAYBOOKS / incidents. A workflow "counts" only when candidates are actually promoted.
- Replace polling-based attention with event-driven monitoring for inbox urgency, CI failure, stall detection, and threshold breach.
- Retention policy: raw events kept runtime-only; promoted artifacts committed.
- Publish event-to-operator-signal p95 latency (first-cut target: ≤5 minutes; sub-plan may tighten).
- Publish message-bus p95 delivery latency (first-cut target: ≤30 seconds for durable messages).

**Phase 0 Readiness:**
- Event schema finalized; committed.
- Every lane and hook emits into the schema; hook coverage audit passes.
- Phoenix container deployable via a documented command; first-cut retention policy enforced; both named workflows documented with trigger/consumer/cadence/output.
- Event-driven attention routing wired end-to-end (at least one event class routes to operator without polling).
- Baseline latencies captured (§4.3) and latency-measurement surfaces published to dashboard.
- Rollback path validated: the polling fallback can be re-enabled via a feature flag in under a minute.

**Phase 1 Validation:**
- Proving-run experiment fully reconstructable from trace corpus alone.
- Phoenix has ≥3 promoted findings (KB entries, incidents, or prompt-policy edits) traceable to Phoenix-surface inspection across the proving run.
- Event-to-operator-signal p95 meets or beats target; zero stale-catch incidents recorded.
- Message-bus p95 meets or beats target; zero lost messages.

### Primitive B — Adaptive Dispatch, Skill Improvement, and Prompt-Policy (Phase 0)

**Goals served:** #1 (self-improving), #4 (intent-aware delegation), #6 (lane/model selection), #7 (well-engineered prompts); also serves the *escalation-via-approval-classes* slice of #8 (see §2 Goal #8 disambiguation: discovery is in Primitive E, escalation classes are here).

**Sub-deliverables table** (per F3 Option B — keep B unified rather than split into B1/B2):

| Sub-deliverable | Goal | Phase 0 Readiness | Phase 1 Validation | Kill |
|---|---|---|---|---|
| B.1 Adaptive dispatch | #6 | SP-5-02 advisor wired end-to-end in shadow mode; rollback via policy-version pin | Adaptive-dispatch decisions operator would approve if audited ≥80% | See §11-B row 1 |
| B.2 Skill promotion loop | #1 | Skill-outcome linkage live; commit-message lint enforces trace-ID or incident-fingerprint citation | ≥1 skill promotion/edit during proving run with commit citing a specific trace ID or fingerprint | See §11-B row 1 |
| B.3 Prompt-policy registry | #7 | Registry exists with initial policies for orchestrator/ops/review/analyst-*/author-*; versioned; rollback via version pin | Prompt-policy version cited in ≥90% of proving-run traces | See §11-B row 2 |
| B.4 Prompt-policy change discipline | #7 | Commit-message template + pre-commit lint for trigger/expected-effect/rollback fields | Zero policy changes landed without all three fields during proving run | See §11-B row 2 |
| B.5 Analyst-vs-author routing rules encoded as policy | #4 | Routing rules in prompt-policy registry, not convention | Routing errors ≤1 per 100 tasks during proving run | See §11-B row 1 |
| B.6 Tool risk registry | #7, #8-escalation | `.claude/rules/tool_risk_registry.md` committed; mapped to four approval classes (direct / approve / edit / reject) per task type | Zero approval-class violations during proving run | See §11-B row 2 |
| B.7 Approval-class references in every prompt-policy | #7, #8-escalation | Each lane's prompt-policy references the appropriate approval class per task type | All lane policies cite an approval class for every task type they handle | See §11-B row 2 |

**Combined notes:**
- All sub-deliverables share the same `prompt_policy_version` machinery and rollback path (policy version pin works; dispatch policy can revert to prior shadow version; skill promotions can be unpromoted via a single command).
- The tool risk registry **documents, does not replace**, the existing auto-mode classifier at `.claude/rules/80_permission_model.md`.
- Combined readiness gate: every row above shows green.

### Primitive C — Durable Memory and Knowledge Base (Phase 0)

**Goals served:** #3 (durable memory), #12 (KB system), #14 (ADR capture).

**Work:**
- KB skeleton in `knowledge/` — promoted-artifact classes:
  - `NOTES.md` — curated lessons, append-only, operator-edited prose.
  - `PLAYBOOKS.md` — runbooks. Procedural.
  - `anti_patterns.md` — actively consulted "do not do X" entries; `trigger → harm → preferred alternative`.
  - `incidents/<fingerprint>.md` — machine-fingerprinted per-incident files.
  - `adr/<NNN>-<slug>.md` — ADR-style architecture decisions. ADR 001 (platform pattern reset) is filed at Phase 0 kickoff.
  - **`harness_assumptions.md` (new in draft 5)** — live list of current harness assumptions that are likely to go stale as models improve or the substrate changes. Entries use the structure `assumption → observation supporting it → brittleness signal → refresh trigger`. Examples of entry topics: session-death thresholds, hook firing semantics, tmux capture format, classifier latency, compaction breakpoints. Distinct from ADRs (which record decisions) and anti-patterns (which record prohibited patterns): this register names *dependencies on current harness behavior* so the platform can detect drift.
  - `INDEX.md` — auto-generated from all of the above.
- MEMORY.md tightened to link into KB entries, not just recap.
- Retention and compaction policy for MEMORY.md, raw session logs, and raw trace exports.
- Commit policy: only promoted artifacts committed.
- **Planning templates** at `plans/_templates/` with governing-plan, sub-plan, execution-plan, checkpoint, promotion/rollback, and review-rubric templates. **Each sub-plan template includes the Phase 2 Decision Inputs subsection (§15) as a required section.** **Each template enforces goal-#16 agent-first conventions** (predictable section IDs, machine-parseable structured fields, consistent cross-reference style, grep-clean naming, worked example for any new schema introduced). Conformance via `/create-plan` and `/create-adr` skills.
- **Agent-readability scorecard** (renamed from "legibility scorecard" per goal #16; same 10 items, primary audience clarified): `knowledge/agent_readability_scorecard.md` measures whether the repo is navigable by agents. Items: (1) CLAUDE.md ≤ 200 lines; (2) single canonical entry point for new sessions; (3) active governing plan findable in ≤2 hops from repo root; (4) all skills discoverable from `.claude/skills/`; (5) lane registry authoritative not inferred; (6) MEMORY.md indexes rather than recaps; (7) ADR index current; (8) KB INDEX current; (9) no orphan references in plans; (10) rule files grep-discoverable from CLAUDE.md. **Provisional floor: ≥7/10 items pass.** ADR 001 records the floor; sub-plan under Primitive C may tighten to 8/10 or 9/10 but may not loosen. Re-scored at end of Phase 0 (preflight item 8 sub-criterion) and end of Phase 1.
- **`compile_decision_inputs.py` (F6):** implement `scripts/internal/compile_decision_inputs.py` per §15.4 spec — globs `plans/steward_platform/**/*.md` and sub-plan outcome files for `^## Phase 2 Decision Inputs` sections, parses 4 prompts + disposition, groups by Decision Axis, generates `decision_inputs_digest.md` + nightly snapshot at `_digest_snapshots/<date>.md`, flags missing subsections at the path level. ~50 lines. Invokable as `/compile-decision-inputs` skill from any lane.
- **Worked example for `harness_assumptions.md` schema (F7):** the entry schema is `assumption → observation supporting it → brittleness signal → refresh trigger`; **brittleness signal must be machine-observable** (grep pattern, CI check, hook precondition); natural-language signals are insufficient. Initial worked example committed at file head:

  ```
  ### Session-death threshold
  **Assumption:** Spawned sub-agents die silently at approximately 15 minutes
  or 700 KB context, whichever first.
  **Observation supporting:** #2120 incident, #2215 fix PR, #2271 retrospective.
  **Brittleness signal:** grep pattern in agent-invocation logs for output
  length > 700KB with no completion event. Pre-commit check on
  `.claude/rules/70_agent_reliability.md` flags edits to the threshold
  without an accompanying ADR.
  **Refresh trigger:** Operator action on next Claude Code release that
  changes sub-agent runtime semantics; measured by a one-shot spawned
  agent that reads the release notes and reports change-delta to the
  archivist.
  ```

**Phase 0 Readiness:**
- KB skeleton files exist, validated by a lint script that enforces structure; `harness_assumptions.md` includes ≥5 initial entries each conforming to the worked-example schema (each has a machine-observable brittleness signal).
- `INDEX.md` auto-regenerates via a committed script; targeted tests cover the generator.
- `/create-plan` and `/create-adr` skills present; templates conform and enforce both the Phase 2 Decision Inputs subsection AND goal-#16 agent-first conventions.
- `compile_decision_inputs.py` runs nightly; smoke-tested against seeded subsection fixtures; first digest generated from Phase 0 closeouts; `/compile-decision-inputs` skill registered.
- MEMORY.md compaction script present and smoke-tested.
- ADR 001 filed at Phase 0 kickoff (records Platform-11/13 dismissal evidence AND the agent-readability scorecard floor of 7/10).
- ≥2 additional ADRs recorded for Phase 0 design decisions (e.g., the readiness/validation split, the preflight insertion, the hybrid decision-inputs pattern, Primitive H deferral, F3 Option B, agent-first as goal #16).
- Agent-readability scorecard committed; initial score recorded; floor (≥7/10) met.
- Rollback path validated: KB entries can be un-promoted (moved back into `_candidates/`) in one step; MEMORY.md compaction can be reverted via git; digest snapshots can be regenerated from source subsections.

**Phase 1 Validation:**
- KB accumulates ≥10 lessons during preflight + proving run.
- ≥3 of those lessons are cited by a downstream PR body or task-packet description in a way verifiable by `grep` during the proving run.
- `anti_patterns.md` has ≥5 entries each tied to an observed failure mode.
- `harness_assumptions.md` has ≥1 entry refreshed or retired during the proving run based on observed behavior (validates the "living register" intent).
- ≥1 additional ADR per major Phase 1 decision (kill signals, primitive changes, preflight outcomes).
- Agent-readability scorecard re-scored at end of Phase 1; score is equal to or better than Phase 0 baseline AND meets the floor recorded in ADR 001 (default ≥7/10).
- `compile_decision_inputs.py` runs nightly throughout Phase 1 without flagging missing subsections (write-discipline holds).

### Primitive D — Archivist Script and Session Postmortem (inflow Phase 0; outflow Phase 1)

**Goals served:** #11 (archiving/evaluation), supports #3 (durable memory).

**Phase split rationale (F2):** the inflow half (lessons / incidents / postmortems) operates against events, PR outcomes, and task completions that exist from Phase 0 onward. The outflow half (entropy / GC report) operates against the *KB itself*, which doesn't exist meaningfully at Phase 0 start — NOTES, PLAYBOOKS, anti_patterns, incidents, ADRs all begin empty or near-empty. GC has nothing to detect at Phase 0 readiness. So GC is split to Phase 1 work, parallel to Primitive H's Phase 1 framing.

**Work:**
- `scripts/internal/archivist.py` — scheduled (nightly + end-of-session) script. Reads events, inbox, PR outcomes, task completions. Two outputs across two phases:
  - **Phase 0, inflow:** `knowledge/_candidates/<date>_lessons.md` — templated candidate lessons, incident candidates, token-efficiency outliers for operator promotion. Readiness: scaffolding + targeted unit tests against seeded fake-event fixtures.
  - **Phase 1, outflow:** `knowledge/_candidates/<date>_gc.md` — entropy report: stale KB entries (not referenced in N sessions), dead skills (not invoked since promotion), obsolete prompt-policy versions (superseded), orphan artifacts (referenced file or trace ID no longer exists), KB entries where linked evidence has expired. Phase 0 ships the *code path* smoke-tested against seeded fake KB state (same fixtures as inflow). Full activation begins when the KB has accumulated ≥2 weeks of promoted entries during Phase 1.
- Operator or analyst reviews candidates on each side and approves.
- Session postmortem: end-of-session trigger writes a per-session handoff into MEMORY.md + feeds candidates into the archivist queue.
- Not a lane. Invokable as a skill from any lane for real-time curation (`/run-archivist --mode lessons` or `--mode gc`).

**Phase 0 Readiness:**
- Archivist inflow runs nightly and on end-of-session hook; targeted tests cover templating and event-reading.
- GC code path present and smoke-tested against seeded fake KB fixtures; activation gated on ≥2 weeks of KB accumulation during Phase 1.
- Candidate file formats (both lessons and GC) committed; operator review workflow documented for each.
- `/run-archivist` skill available with `--mode lessons` and `--mode gc` flags.
- Rollback path validated: candidate-to-promoted moves tracked; a promotion can be reverted by moving content back into `_candidates/`; stale-marking or deletion can be reverted via git.

**Phase 1 Validation:**
- ≥1 promoted lesson observably cited downstream during the proving run (grep-verifiable in a PR body or task-packet description).
- Candidate-to-promoted ratio ≥10% weekly (inflow working).
- **≥3 GC-report proposals accepted across ≥2 distinct categories** (stale entries / dead skills / obsolete policies / orphan artifacts / expired evidence) during the proving run (F8 — prevents trivial-clearance via 3 stale-ref removals).
- Session postmortems trigger reliably at end of each proving-run session.
- KB net growth is positive but bounded: ratio of inflow (new lessons) to outflow (stale removals) demonstrates curation discipline, not hoarding.

### Primitive E — Messaging and Active Triage Closeout (Phase 0)

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
- Rollback path validated: active-triage can be disabled via a feature flag without losing inbox state.

**Phase 1 Validation:**
- Zero lost-message incidents across preflight + proving run.
- Bus p95 meets or beats target set in Primitive A.
- Active triage produces ≥50% of issues created during the proving run, measured over ≥20 observed issues across the run.
- Zero stale-catch incidents (events discovered minutes+ after occurrence).

### Primitive F — Token Economy Closeout (Phase 0)

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

### Primitive G — Existing-Debt Closeout (Phase 0)

**Goals served:** non-capability primitive; gates all others. Also absorbs the rollback-validation slice of Goal #13 for any reversible change introduced in Phase 0.

**Work:**
- Portability manifest: zero hard-blocks in `ops/worktrees.py` (44 occurrences) and `ops/token_economy.py` (22 occurrences). Soft-coupling may remain.
- Retire `agent_ops/5_extraction`, `agent_ops/5_cross_model`, `agent_ops/5_skill_learning`, `agent_ops/5_portability_and_learning` subtrees with explicit status (superseded / absorbed / abandoned).
- Resolve remaining messaging-bus proving items (overlaps Primitive E).
- Platform-11 adaptive-dispatch partial reactivation (SP-5-02) closes inside Primitive B or is explicitly superseded.
- Every reversible change introduced in Phase 0 has an exercised forward + backward transition recorded (satisfies Goal #13 for Phase 0 changes).

**Phase 0 Readiness:**
- `PORTABILITY_MANIFEST` shows zero hard-blocks in the two named files.
- Each `agent_ops/5_*` subtree has an explicit resolution note (superseded / absorbed / abandoned) with a pointer to where remaining work lives.
- `agent_ops` plan fragmentation is gone.
- Rollback validation recorded for every reversible Phase 0 change.

**Phase 1 Validation:** n/a — this primitive is not validated against proving-run outcomes; it is purely a prerequisite.

### Primitive H — Reliability Lab, Replay Harness, and Canary Suite (Phase 1)

**Phase membership:** Phase 1 (concurrent with proving run). Primitive H is
*not* a Phase 0 readiness gate. It builds out during Phase 1 and must
complete its Phase 1 Validation by end of Phase 1 for the Phase 2 gate
to be able to make a portability decision (§10.7).

**Goals served:** #15 (reliability / replay / failure-injection), supports #1, #2, #11, #13 (rollback for Phase 1 changes).

**Work:**
- `tests/reliability/replay.py` — harness that reconstructs a task lifecycle from the event corpus (Primitive A) and asserts expected intermediate + final states.
- Failure-injection scenarios: lane stall, dead-letter message, stuck worktree, orphan cron, review-coordinator crash, Telegram outage.
- Automated postmortem generator: given a replay artifact, produce a draft incident file.
- Rollback-validation coverage for Phase 1 changes (Primitive G covers Phase 0 changes).
- **Canary task suite (new in draft 5):** 3-5 canonical steward tasks defined as YAML/markdown specs at `tests/reliability/canaries/`. Each spec: task description, expected lane routing, approximate token budget, expected prompt-policy citations in traces, pass/fail verdict protocol. Suite reruns are triggered automatically (via CI or cron) on any material change to prompt-policy registry, dispatch policy, messaging bus, or replay harness itself. Canary failures surface as issues via Primitive E's active triage.
- **Idempotency checklist for side effects (new in draft 5):** required PR-review item at `.claude/rules/idempotency_checklist.md` covering every replay/interrupt-sensitive operation (message send, task status update, event emission, file write). PR template includes the checklist; review lane verifies. Makes implicit idempotency needs mechanizable.
- **Intended to be** usable as a Phase 2 portability dry-run tool: once a shape audit produces adapter stubs, the harness can point at them and flag hidden coupling. This reuse is design intent, not verified readiness. See §10.7 and §11-H for the coupling between H and the Phase 2 portability decision.

**Phase 1 Readiness (mid-Phase-1, before the proving run produces its main evidence):**
- Replay harness exists and can reconstruct at least 1 lifecycle (may use a non-proving-run seed task).
- At least 2 failure-injection scenarios implemented; both pass.
- Automated postmortem generator template committed and smoke-tested.
- Canary task suite defined (3-5 tasks) and one trigger path wired (e.g., on prompt-policy registry commits).
- Idempotency checklist committed and added to the PR template.

**Phase 1 Validation (by end of Phase 1):**
- Replay harness reconstructs ≥1 proving-run task lifecycle end-to-end with no drift from live events.
- ≥3 failure-injection scenarios exercised during the proving run (or during dedicated reliability sessions within it); all either pass or produce a documented incident. **At least one scenario is selected post-hoc by an analyst lane after primitives A, B, and E ship** — to avoid Goodharting the self-chosen minimum.
- Automated postmortem generator produces ≥1 end-to-end incident draft from a real proving-run event stream.
- Canary task suite reruns on ≥2 material platform changes during the proving run; at least one canary run catches a regression (or, if none caught, the operator records in Primitive B's prompt-policy history an ADR stating "no regressions caught" as either evidence of stability or as a kill-candidate signal for canary scope).
- Zero PRs merged without the idempotency checklist filled during the proving run (for PRs touching replay/interrupt-sensitive code).

---

## 6. Phase 1a — Platform Preflight

### 6.1 Proving-run candidate and data-sufficiency check

The proving run is a complete research program executed end-to-end
through the platform. Primary candidate: **GBT retrain informed by
human-gameplay data captured through the browser-game hosting
infrastructure.**

Why this candidate:
- Exercises the full research workflow: capture → analyze → hypothesize → design → implement → execute → evaluate → decide.
- Requires cross-lane coordination (analyst for shaping, author for implementation, ops for orchestration, review for quality, measurement for promotion gates).
- Has ground truth.
- Exercises the rigor apparatus in `.claude/rules/deferred/05_rigor.md`.
- Produces research value regardless of platform-test outcome.

**Pre-Phase-1 data-sufficiency check.** Before Phase 1 is committed to
the GBT retrain, the analyst lane confirms:

- Human-gameplay session count ≥ threshold specified by the first strategy-training sub-plan filed in Phase 0.
- Session quality distribution (% completed games, opponent heterogeneity, contract-type coverage) meets a documented floor.
- At least one end-to-end ingest → features → train → eval loop ran against the existing corpus inside Phase 0.

If any of the three is not met, the proving run pivots to the
**measurement-methodology-overhaul alternative** — a new rigor regime
applied across existing strategies, which stresses the platform's
coordination / learning / rigor surfaces without requiring external data
accretion. The decision to pivot is itself a Phase 2 Decision Input (§15)
with `Portability readiness` filled to note "research value via browser
data was not accessible within Phase 1."

### 6.2 Preflight purpose

Before committing to the full research proving run (long, noisy,
partially confounded by research-level failure modes), run a bounded
end-to-end workflow that exercises every substrate surface. If the
platform has a structural flaw, it surfaces here in a short cycle rather
than weeks into the research program.

### 6.3 Preflight scope

A single small task family executed end-to-end through the full
platform. Candidates (operator chooses one at Phase 1a start):

- A scoped measurement refresh.
- A small strategy tweak.
- A single-PR feature addition in the browser-game or experiment infrastructure.

Selection criterion: the task must exercise analyst shaping, author
implementation, ops orchestration, review, merged-PR outcome, skill
invocation, and prompt-policy application. Research outcome matters
secondarily; platform exercise matters primarily.

### 6.4 Preflight pass/fail checklist

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
| 8 | KB integration + agent-readability | At least one KB entry (NOTES, PLAYBOOK, anti-pattern, incident, harness assumption, or ADR) created during preflight (Primitive C); **agent-readability scorecard re-scored at preflight close with score ≥ floor recorded in ADR 001 (default 7/10)** (folded in from former item 10 per F4). |
| 9 | Rollback | One reversible change (skill promotion, prompt-policy version, or dispatch policy) executed and rolled back successfully (Primitives B, H, goal #13) |
| 10 | End-to-end data discipline (F4) | Pick one task completed during preflight; assert its trace corpus (Primitive A), message bus state (Primitive E), KB artifacts (Primitive C), and task-packet state are mutually consistent: no orphan events, no lane-attribution mismatches, no task-packet state contradicting its completion event. Tests Primitives A + E + C + task queue together without needing H. (Replaces draft-5 item 10 "agent legibility scorecard" which folds into item 8 below; replay item from draft 4 stays moved to Phase 1 validation under Primitive H.) |

### 6.5 Preflight outputs

`plans/steward_platform/1a_preflight/report.md` containing:
- Chosen preflight task, rationale, scope.
- Pass/fail status for each of the 10 checklist items.
- Any gaps identified, with Phase 0 follow-ups if re-opening is required.
- **Phase 2 Decision Inputs subsection** (§15) for each of the 10 checklist items.

### 6.6 Preflight gate

- **All 10 pass:** proceed to Phase 1 (after data-sufficiency check §6.1).
- **1-2 fail:** decide per-item whether a targeted fix inside preflight scope is sufficient, or whether a Phase 0 re-opening is required. If fixed in-scope, re-run the relevant checklist items.
- **3+ fail:** Phase 0 was not actually ready. Return to Phase 0, identify which primitives were under-built, resolve, and re-enter Phase 1a.

---

## 7. Phase 1 — Proving Run + Primitive H Buildout

Phase 1 has two concurrent tracks:

- **Track A — Proving run.** Execute the research program (GBT retrain or methodology-overhaul alternative) end-to-end through the platform. Exercises primitives A-G built in Phase 0.
- **Track B — Primitive H buildout.** Replay harness, failure-injection catalog, postmortem generator, canary task suite, idempotency checklist. Builds concurrently; captures proving-run events; accumulates scenarios as the run proceeds.

Tracks are coupled but not blocked on each other. The proving run does
not wait for H to be done; H captures the run as it unfolds. By end of
Phase 1, both tracks complete their validation criteria for Phase 2 to
have the inputs it needs.

**Why concurrent rather than sequential (Track B before Track A):**
building H before the proving run requires seeding it with a synthetic
event stream, which would re-test existing data rather than exercise
live platform behavior. Concurrent buildout lets H capture the real
proving run, which is the strongest possible evidence base for H's
Phase 1 Validation.

### 7.1 Platform-level success criteria

Each of the 15 goals gets a measurable Phase 1 validation criterion
(collected from per-primitive Phase 1 Validation sections in §5):

| # | Capability | Measured by |
|---|---|---|
| 1 | Self-improving | ≥1 skill edits/promotions driven by outcome feedback during the run, citing trace IDs or incident fingerprints |
| 2 | Auditable/traceable | Full run reconstructable from trace corpus without transcript archaeology |
| 3 | Durable memory | ≥3 lessons from early in the run cited (grep-verifiable) in later tasks |
| 4 | Intent-aware delegation | Analyst-vs-author routing errors ≤1 per 100 tasks |
| 5 | Token-efficient | Tokens per successful merge trending flat or down relative to baseline (§4.3) |
| 6 | Lane/model selection | Adaptive-dispatch decisions that operator would approve if audited ≥80% |
| 7 | Well-engineered prompts | Prompt-policy version cited in ≥90% of traces; policy deltas tied to outcome changes |
| 8 | Active triage | Share of issues created by event-driven triage vs. operator discovery ≥50%, measured over ≥20 observed issues |
| 9 | Durable messaging | Zero lost messages; p95 within target set in Primitive A |
| 10 | Event-driven monitoring | Event-to-operator-signal p95 within target; zero stale-catch incidents |
| 11 | Archiving/evaluation | Archivist candidate-to-promotion rate ≥10%; ≥1 promoted lesson with grep-verifiable downstream use |
| 12 | KB system | KB grows during the run; promoted lessons findable via INDEX |
| 13 | Rollback/disable | At least one forward + backward transition exercised per reversible primitive; zero state-loss incidents |
| 14 | ADR capture | ≥1 ADR per major Phase 1 decision; every kill-criterion trigger produces an ADR |
| 15 | Reliability lab / replay | Replay harness reconstructs ≥1 proving-run task lifecycle without drift |

### 7.2 Separation of platform test from research test

The proving run has two separate evaluations:

1. **Research evaluation** — does the GBT retrain (or methodology-overhaul alternative) actually produce a defensible outcome? Answered by the experiment's own rigor apparatus.
2. **Platform evaluation** — did the platform enable that experiment to execute efficiently, reproducibly, with compounding learning? Answered by §7.1.

A research failure is not a platform failure. A research success that
required operator heroics is not a platform success. The preflight
(Phase 1a) is the primary fast-fail platform check; Phase 1 is where
longitudinal platform evidence accumulates alongside research work.

### 7.3 Proving-run report

At end of Phase 1, the operator and analyst lanes produce
`plans/steward_platform/1_proving_run/report.md` containing:

- Research outcome (promoted / retained / killed).
- Per-capability evidence against §7.1 criteria.
- Identified platform gaps by severity.
- **Phase 2 Decision Inputs subsection** (§15) for each of the 15 capability rows + any cross-cutting findings.

---

## 8. Phase 2 — Decision Gate

Phase 2 is a planning phase, not a build phase. Its output is either a
successor governing plan or a scoped sub-plan driving Phase 3+.

### 8.1 Inputs

- Phase 1 proving-run report.
- Phase 1a preflight report.
- Fund + RIN-SnD shape audits (from §4.2).
- **Decision-inputs digest** (§15) — auto-generated summary of all Phase 2 Decision Inputs subsections filed during Phases 0, 1a, and 1, grouped by decision axis.
- `plans/steward_platform/post_phase2_sidecar.md` — deferred-ideas parking lot; candidates for promotion if proving run surfaces matching pain.
- `plans/steward_platform/phase2_harness_engineering_research.md` — external-practices reference for framing Phase 2 direction.
- Any deferred workstreams from drafts 1-3 not absorbed into the 8 primitives.

### 8.2 Decisions to make

1. **Portability.** Does the proving run establish that the platform produces value worth porting? If yes, target: Fund first or RIN-SnD first? If no, what specific weaknesses need further single-repo hardening?
2. **Meta-layer.** What cross-project state is actually useful? Answered by what the proving run revealed about operator pain.
3. **cmux adoption.** Only relevant if portability goes forward. Shape to be determined by proving-run evidence and shape-audit findings; not pre-described.
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

### 10.1 Platform shape (Phase 0 target)

Single Bid-Euchre steward cell with:
- Always-on: `orchestrator`, `ops`, `review`.
- Off-by-default, bounded-activation: `analyst-*`, `author-*`, `brws-author-*`, `flex-*`.
- No meta-surface in Phase 0.

### 10.2 Truth model

- Repo-local runtime state = operational truth.
- Phoenix = observability/eval UI, not canonical state.
- KB artifacts = promoted knowledge, not raw evidence.
- GitHub = PR/review/CI truth.
- Meta-level truth: not applicable in Phase 0.

### 10.3 Lane policy (Phase 0 target)

Reduced from current 19-lane fleet:
- Always-on: orchestrator + ops + review (3).
- Specialist activation under bounded rules with operator-visible triggers.
- Retirement: unused specialists parked after idle thresholds.
- Routing: analyst owns shaping/findings/diagnostics; author owns merge-oriented implementation.

### 10.4 Event and trace model

First-class IDs canonical (see Primitive A). Steward keeps a native event
model; Phoenix is a consumer, not a source.

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
deferred to Phase 2 decision gate. Companion artifacts carry the
detail:

- `plans/steward_platform/post_phase2_sidecar.md` — deferred ideas and architecture extensions, each with explicit revisit criteria.
- `plans/steward_platform/phase2_harness_engineering_research.md` — borrowed-practices memo that informs what's worth adopting at Phase 2 and what stays in the sidecar.

Phase 2 decision-gate analysts consult both alongside the digest (§15)
when shaping the successor plan.

**Design coupling note.** Primitive H (Reliability Lab), now a Phase 1
primitive, is intended to serve as the portability dry-run tool when
Phase 2 decides to port. Phase 2 cannot commit to portability unless H
has completed its Phase 1 Validation criteria (§5-H). If H is demoted
under its kill criterion (§11-H) or fails to complete validation by end
of Phase 1, the **default is Option 1 below; Option 2 requires all named
conditions to be met** (F5 — pre-commit a default so Phase 2 doesn't
decide under cost pressure):

**Option 1 (default): defer the portability decision until H is rebuilt
and validated.** Pushes portability to Phase 3+. The Phase 2 gate still
produces a successor plan whose first item is H rework, but that plan
does not commit to a target repo until H completes validation.

**Option 2 (conditional): accept the portability decision with
compensatory scoping.** All three conditions required:

1. The named target repo has independent reliability evidence (e.g., its own CI passing on a representative test surface, its own integration tests, recent production shipping history) that the Phase 2 report cites explicitly.
2. The compensatory analyst-lane discovery work is budgeted in advance at ≥X analyst-days (X recorded in the Phase 2 report) and the budget is drawn before the port begins, not promised.
3. The first-repo port is explicitly framed as a reversibility-first experiment with a kill trigger defined at port start.

If any of the three conditions is unmet, the plan defaults to Option 1.

This coupling is recorded to prevent accidental
accept-a-demoted-H-and-still-commit-to-port under cost pressure.

### 10.8 Agent-first artifact design (Goal #16)

Cross-cutting architectural principle. Every durable artifact in the
plan ecosystem is optimized for agent loading and execution; human
readability is secondary.

**Concrete conventions enforced via Primitive C templates:**

- **Predictable section IDs.** Every governing-plan and sub-plan section uses the format `§N.M` for cross-reference. Headers carry numeric prefixes through to subsections. Stable across revisions.
- **Machine-parseable structured fields.** Where useful, sub-plan and primitive metadata uses YAML-style or table-style structured fields (status, owner, scope, validation commands, primitive mapping). Free-form prose is reserved for content that cannot be structured.
- **Consistent cross-reference patterns.** Internal references use `§N.M`; file references use `path/from/repo/root.md` (no `./` or `../`); commit references use PR or commit-SHA syntax. Lint script (Primitive C) flags inconsistent forms.
- **Grep-clean naming.** Artifact names are unique enough to be greppable across the repo (e.g., `harness_assumptions.md` not `assumptions.md`; `compile_decision_inputs.py` not `compile.py`).
- **Loadable as agent context with minimal preamble.** Every artifact's first ~25 lines establish enough scope (who, what, when, where in the lifecycle) for an agent to know whether to load the rest. Long prose preambles are anti-pattern.
- **Worked examples for any new schema.** Schemas (KB entry templates, sub-plan templates, ADR templates, harness-assumption entries, decision-input subsections) ship with at least one full worked example so future entry authors don't drift.
- **Stable IDs in mutable artifacts.** Decision-input subsections, ADRs, and incident files carry stable IDs that survive revision; supersession is recorded via reference, not in-place edit.

**Sub-plans and ADRs and template files are also subject to these
conventions.** The `agent_readability_scorecard.md` and the agent-readability
lint script (Primitive C) enforce conformance across the full repo
plan/KB surface, not just the governing plan.

**This is not theme styling.** It is execution infrastructure: every
agent that loads a planning artifact pays a cost proportional to how
long the artifact takes to scan and how machine-readable it is. Treating
agent-readability as primary saves token cost on every load.

---

## 11. Kill Criteria

Per-primitive kill criteria. If a primitive fails its criterion during
Phase 0, 1a, or 1, Phase 2 evaluates whether to rework, downgrade, or
retire it. Kill triggers spawn an ADR.

Thresholds sharpened per analyst-a's review: kill criteria must be
adversarial against the author's sympathies, not aligned with them.
Usage-based rather than clock-time-based.

**Soft re-evaluation trigger (F1, operator clock-time directive).** Usage-based
kill criteria have a known unfalsifiability trap: a primitive that sees
below-threshold activity during a thin proving run (including the §6.1
methodology-overhaul pivot) produces no evidence for or against its kill
criterion. To avoid accreting unfalsifiable primitives into Phase 2 as
"no evidence yet, keep alive," every kill criterion below carries an
implicit **soft re-evaluation trigger**: if a primitive's activity
during the proving run is below the threshold needed to evaluate its
kill criterion, *and* its elapsed-time relative to other primitives is
not yet at the relative norm, the primitive is flagged at Phase 2 as
"insufficient evidence" and explicitly scoped for a follow-up evaluation
window (Phase 3). The plan default for an "insufficient evidence"
primitive is **re-evaluate in Phase 3**, not "keep alive indefinitely."
Retire requires explicit justification. This preserves the usage-based
kill discipline while closing the unfalsifiability trap.

**Two-signal differentiation:** the soft trigger uses both *activity
volume* and *relative elapsed time* (recorded per §3 Relative clock-time
tracking). Cases:

- Activity below threshold AND relative time short → "insufficient evidence" → re-evaluate.
- Activity below threshold AND relative time long → kill candidate; scope was hit but produced no signal.
- Activity at threshold AND relative time short → primitive on track; no kill action.
- Activity at threshold AND relative time long → cost-signal flag; scope completed but expensive.

| Primitive | Kill criterion |
|---|---|
| A — Trace/observability (Phase 0) | Phoenix has <3 promoted findings (KB entries, incidents, or prompt-policy edits) traceable to Phoenix-surface inspection across the proving run → demote to JSONL + notebook only |
| B — Adaptive dispatch + skill + prompt-policy (Phase 0) — row 1 (B.1/B.2/B.5 sub-deliverables) | Zero skill promotions/edits where the commit message cites a specific trace ID or incident fingerprint across the proving run → revert to manual skill curation |
| B — Adaptive dispatch + skill + prompt-policy (Phase 0) — row 2 (B.3/B.4/B.6/B.7 sub-deliverables) | <50% of proving-run traces cite a prompt-policy version → registry did not land; freeze in advisory. Also: ≥3 approval-class violations (high-risk action taken without required approval) during the proving run → revisit tool risk registry classification boundaries |
| C — KB (Phase 0) | <3 promoted lessons cited by a downstream PR body or task-packet description in a grep-verifiable form during the proving run → collapse to single NOTES.md per repo. Also: `harness_assumptions.md` has zero entries refreshed/retired over the proving run → retire the register (assumption it captures real drift is falsified) |
| D — Archivist (inflow Phase 0; outflow Phase 1) | Candidate-to-promotion rate <10% across the proving run (lessons inflow) OR <3 GC-report proposals accepted across ≥2 distinct categories (outflow) → rewrite templates or retire the GC half |
| E — Messaging/triage (Phase 0) | Active triage produces <20% of issues created, measured over ≥20 observed issues → revert to operator-discovery model |
| F — Token economy (Phase 0) | Slice F cannot produce a defensible promote/retain/kill decision → freeze adaptive dispatch in advisory indefinitely |
| G — Debt closeout (Phase 0) | Not kill-able; blocks all other primitives |
| H — Reliability lab + canary (Phase 1) | <2 replay scenarios pass or <3 failure-injection scenarios exercised, **including at least one scenario selected post-hoc by an analyst lane after primitives A/B/E ship**; OR the canary task suite never runs on a material platform change during the proving run → demote to a simpler event-diff assertion set; postmortem generator + canary suite deferred. Demotion blocks §10.7 portability-decision readiness; Phase 2 must re-evaluate portability cost if demoted |

---

## 12. Risks

| Risk | Mitigation |
|------|------------|
| Phase 0 primitive scope creep | Closed-list §2 + §13 scope-lock statement; every primitive done-when is a file, test, or metric; operator/reviewer capability proposals route to Phase 2 Decision Inputs, not to Phase 0 |
| Research stall conflated with platform stall in proving run | §7.2 enforces separation; preflight (§6) provides a fast-fail platform check; data-sufficiency check (§6.1) pivots to methodology-overhaul alternative if browser data is thin |
| Phoenix becomes unused infrastructure | Kill criterion §11-A measures promoted findings, not UI opens; two named workflows with trigger/consumer/cadence/output in Primitive A |
| Archivist produces noise, not signal | Kill criterion §11-D; candidate-to-promotion rate measured |
| Prompt-policy pollution degrades steering | Candidate → confirmed lifecycle; operator-visible policy versions; rollback via policy version pinning |
| Platform-11/13 repeat-postponement pattern | Operator has confirmed constraints that paused earlier attempts no longer apply. The specific constraints that paused Platform-11 and Platform-13 and have since lifted are recorded in ADR `knowledge/adr/001-platform-pattern-reset.md` filed at Phase 0 kickoff, which serves as the evidentiary basis for this plan's Phase-0 primitive count. If the postponement pattern recurs in Phase 0, the ADR is reopened and Phase 0 is recast before continuing |
| Portability option decays because we defer it | §4.2 parallel shape-audit work (2-3 days per repo, 8-item output) keeps the option warm at low cost |
| Event-driven monitoring adds attention noise | Signal thresholds tuned by archivist feedback; event classes can be muted via policy |
| KB grows without compaction | §5-C retention policy; INDEX highlights stale content |
| Lane reduction causes bottleneck on active lanes | Specialist activation thresholds tunable; retirement only if idle, not if contention |
| Baseline drifts or is lost | Baselines committed as a versioned artifact in §4.3; re-measurement part of Phase 2 input synthesis |
| Preflight passes trivially without exercising surfaces | Preflight pass/fail checklist (§6.4) is granular (10 items across all primitives); selection criterion (§6.3) forces cross-lane exercise |
| Primitive A slip cascades to D, E, H | Dependency surfaced here; Primitive A ordered first in §5 and lands before B/D/E/H substrate work begins; every downstream primitive's readiness check re-verifies A emits to the schema |
| Decision-inputs subsections skipped under load | Template enforcement via `/create-plan` skill refuses to accept sub-plan closeouts without the subsection; digest script flags missing subsections nightly |

---

## 13. Success Criteria

1. The 7 Phase 0 primitives (A-G) reach their Phase 0 Readiness criteria; Primitive H reaches its Phase 1 Validation criteria by end of Phase 1.
2. Phase 1a preflight passes all 10 checklist items or completes the re-work loop per §6.6.
3. Proving run executes end-to-end through the platform with measurable attention compression relative to baseline (§4.3).
4. Proving-run platform evaluation produces a per-capability scorecard against all 15 goals.
5. Decision gate (Phase 2) produces a scoped successor plan based on proving-run evidence *read from the decision-inputs digest* (§15), not reconstructed from transcripts.
6. ≥3 KB lessons have grep-verifiable downstream use during the proving run.
7. Tokens per successful merge during the proving run are flat or declining relative to baseline.
8. Messaging bus has zero lost-message incidents and published p95 latency meeting target.
9. Adaptive dispatch either ships as active routing or is documented as retained-advisory with evaluation evidence.
10. ≥1 skill and ≥1 prompt-policy promoted or edited with outcome-feedback evidence citing trace IDs.
11. Reliability-lab replay harness reconstructs ≥1 proving-run task lifecycle without drift (Phase 1).
12. Canary task suite runs on ≥2 material platform changes during the proving run (Phase 1).
13. Rollback paths validated for every reversible change introduced in Phase 0 (Primitive G) and Phase 1 (Primitive H).
14. `harness_assumptions.md` has ≥1 entry refreshed or retired based on observed behavior during the proving run.
15. GC-report proposals accepted ≥3 times across ≥2 distinct categories during the proving run (archivist outflow working).
16. Agent-readability scorecard re-scored at end of Phase 1 equal to or better than Phase 0 baseline AND meets the ≥7/10 floor recorded in ADR 001.
17. Goal #16 conformance: every Phase 0 closeout, sub-plan, ADR, and KB entry passes the agent-readability lint script (template enforcement under Primitive C).
18. Relative clock-time recorded for every primitive readiness slice and Phase 1 validation accumulation (per §3 Relative clock-time tracking); used as the second signal in §11 soft re-evaluation trigger and as a cost-signal feed into Phase 2 decision inputs.
17. Every primitive closeout, sub-plan outcome, preflight report, proving-run report, and shape audit includes a Phase 2 Decision Inputs subsection per §15; digest script regenerates nightly without flagging missing subsections.

---

## 14. Open Items

1. **Proving-run scope.** GBT retrain is primary candidate subject to §6.1 data-sufficiency check; methodology-overhaul is the pivot alternative. Operator confirms selection (or pivot) at Phase 1 entry.
2. **Preflight scope.** Candidate task families listed in §6.3. Operator chooses at Phase 1a start.
3. **Prompt-policy schema.** Registry structure, versioning semantics, lifecycle state machine detailed in a sub-plan under Primitive B.
4. **Event-driven latency target.** First-cut ≤5 minutes p95; sub-plan under Primitive A may tighten based on baseline.
5. **Archivist template structure.** Candidate-file sections, promotion criteria, review cadence specified in a sub-plan under Primitive D.
6. **KB INDEX generation.** Tooling choice specified in a sub-plan under Primitive C.
7. **Phoenix local deployment details.** Docker-compose shape, retention, exporter path specified under Primitive A.
8. **Specialist activation thresholds.** Idle-to-parked and task-arrival-to-active thresholds specified in a sub-plan.
9. **Data-sufficiency thresholds** (§6.1). Minimum session count, quality distribution floor, ingest-loop completion criterion specified in the first strategy-training sub-plan in Phase 0.
10. **Phase 2 decision template.** Decision-gate rubric and output format specified at end of Phase 0 to avoid recency bias.
11. **ADR 001 content.** Draft at Phase 0 kickoff; names three-to-four concrete constraints that paused Platform-11/13 and have since lifted (see §12 Risks row 6).

---

## 15. Decision Inputs For Phase 2 — Hybrid Pattern (Durable Infrastructure)

This section codifies the Phase 2 decision-capture pattern as **durable
steward-platform infrastructure**, not a one-off artifact. The same
pattern is expected to serve future governing plans, future sub-plans,
and any successor initiative. Investing in template + script + convention
now pays compounding returns across every subsequent
build-prove-decide cycle.

### 15.1 Pattern overview

Two surfaces:

- **Write surface:** structured "Phase 2 Decision Inputs" subsections embedded in every primitive closeout, every sub-plan outcome, the preflight report, the proving-run report, the baseline artifact, each target-repo shape audit, and a single cross-cutting meta-findings file. Writing happens adjacent to the work that produced the finding; write-discipline is template-enforced and does not decay.
- **Read surface:** auto-generated digest file (`plans/steward_platform/decision_inputs_digest.md`) produced by a nightly `scripts/internal/compile_decision_inputs.py` script that greps all subsections, groups by Decision Axis, and produces an operator-readable summary. Phase 2 opens the digest to make decisions.

Write-surface virtues: zero-overhead (part of the closeout you were
writing anyway); writer-reader distance is short; `grep`-auditable;
template-enforced.

Read-surface virtues: central one-file operator view; lifecycle
dispositions visible at a glance; filter-by-axis for each Phase 2
decision.

### 15.2 Subsection schema

Every primitive closeout, sub-plan outcome, preflight/proving-run report,
baseline artifact, and shape-audit section ends with:

```
## Phase 2 Decision Inputs

**Portability readiness:** [one sentence with evidence link, or "no change"]
**Meta-layer need:** [one sentence with evidence link, or "no change"]
**Kill signal for primitive(s) named:** [yes/no with evidence link, or N/A]
**Surprise finding:** [one sentence if any, or "none"]
**Disposition:** open | incorporated | superseded | rejected
```

Four content prompts plus one disposition status line. No tag taxonomy;
the prompts themselves carry the decision-axis routing.

### 15.3 Meta-findings file

Cross-cutting findings that do not belong in any single primitive
closeout — operator observations across multiple primitives, archivist
discoveries that span phases, analyst-lane pattern observations — go in
`plans/steward_platform/meta_findings.md`, one subsection per finding,
using the same schema.

### 15.4 Digest generation

`scripts/internal/compile_decision_inputs.py` runs nightly (and on
demand via a `/compile-decision-inputs` skill). It:

- Globs `plans/steward_platform/**/*.md` and sub-plan outcome files for `^## Phase 2 Decision Inputs` sections.
- Parses each subsection's four prompts + disposition status + source file path.
- Groups entries by the content of their four prompts into four decision-axis buckets (portability / meta-layer / kill / surprise), with any one entry possibly appearing in multiple buckets.
- Produces `plans/steward_platform/decision_inputs_digest.md` with per-axis sections and per-entry source-file references.
- Archives into nightly snapshots at `plans/steward_platform/_digest_snapshots/` for audit trail.
- Flags any sub-plan outcome or primitive closeout that is missing the subsection (template enforcement failure).

### 15.5 Disposition lifecycle

- `open`: under active review; Phase 2 has not yet resolved it.
- `incorporated`: reflected in a Phase 2 decision or subsequent plan revision; references the decision artifact.
- `superseded`: replaced by a later subsection; references the newer entry.
- `rejected`: evaluated and deliberately not acted on; reasoning recorded in a linked ADR.

Subsections are additive-only; corrections append a new subsection
referencing the earlier one rather than editing the original.

### 15.6 Write-discipline enforcement

Mechanization prevents the pattern from decaying:

- `plans/_templates/sub_plan.md` — includes the subsection as a required section. `/create-plan` skill refuses to finalize sub-plans lacking the subsection.
- `plans/_templates/primitive_closeout.md` — required format for primitive closeouts.
- Digest script nightly report flags missing subsections at the path level.
- §13 Success Criterion #13 makes subsection discipline a platform-level success criterion.

### 15.7 Phase 2 use

Phase 2 decision gate begins by reading `decision_inputs_digest.md`:

- Portability decision: all entries with non-"no change" Portability readiness prompts, plus shape-audit findings.
- Meta-layer decision: all entries with non-"no change" Meta-layer need prompts, plus surprise findings.
- Kill decisions: all entries with "yes" Kill signal prompts.
- Next-wave ambition: surprise findings and capability-over-delivery patterns.

Any entry still in `Disposition: open` with a Phase 2-relevant content
prompt becomes a mandatory Phase 2 input. Dispositions update as Phase 2
resolves; updates are append-only new subsections referencing the
originals.

### 15.8 Durability — why we invest here now

This pattern is built deliberately as infrastructure that outlives the
current initiative because:

- Every governing plan and every sub-plan going forward will need a way to surface findings to downstream decisions without re-inventing the mechanism.
- The `plans/_templates/` and `scripts/internal/` homes are the same homes the rest of the steward platform uses; nothing special is created.
- The cost of paying once is small (a template + a ~50-line script + a skill); the cost of re-inventing the mechanism per initiative compounds.
- This pattern is itself an ADR candidate (filed alongside ADR 001 at Phase 0 kickoff) so future plan authors understand why the mechanism is shaped this way.

---

## 16. Delta From Draft 5

Recording what changed relative to draft 5 (analyst-b's review fed in plus three operator directives):

- **Goal #16 added: agent-first plan and KB design** (operator directive). All durable artifacts (governing plan, sub-plans, KB entries, ADRs, prompt-policies, decision-input subsections, planning templates, briefings, run reports) optimized for agent navigation; human readability secondary. Consistent theme across all repo planning artifacts. Goal count: 15 → 16.
- **Legibility scorecard renamed to "agent-readability scorecard"** (operator directive driving goal #16 application). Same 10 items; primary audience clarified.
- **Relative clock-time tracking reinstated** (operator clarification on draft 3's clock-time removal). No absolute budgets; *measurement* per primitive readiness, per Phase 1 validation accumulation, per debt-closeout slice. Recorded in step-template step 5 closeouts. Used as the second signal in §11's soft re-evaluation trigger and as cost-signal feed into Phase 2.
- **F1 (analyst-b high) — soft re-evaluation trigger added to §11.** Combined with reinstated clock-time, "insufficient evidence" primitives are differentiated by activity volume AND relative elapsed time. Default Phase 2 action: re-evaluate in Phase 3. Closes the unfalsifiability gap that the proving-run pivot alternative + usage-based kill criteria together created.
- **F2 (analyst-b high) — Primitive D split.** Lessons inflow stays Phase 0; GC outflow moves to Phase 1 (parallels Primitive H shape). Phase 0 readiness for D's outflow is "code path smoke-tested against seeded fake KB"; full activation begins after ≥2 weeks of KB accumulation in Phase 1. GC validation threshold tightened to ≥3 accepted across ≥2 distinct categories (was ≥1 trivially clearable, F8).
- **F3 (analyst-b medium-high) — Primitive B sub-deliverables table** (operator chose Option B). B stays unified; sub-deliverables table maps each of B's 7 deliverables (B.1-B.7) to its own readiness/validation mini-rows. Primitive count stays at 8 total / 7 Phase 0. §11-B kill row split into row 1 (B.1/B.2/B.5) and row 2 (B.3/B.4/B.6/B.7) so each row has a single coherent failure mode.
- **F4 (analyst-b medium) — preflight item 10 swap to data-discipline probe.** Replaces draft-5 item 10 ("agent legibility scorecard") with end-to-end data-discipline probe across Primitives A + E + C + task queue. Agent-readability scorecard folds into item 8 (KB integration) per F4 alternative. Preflight remains a 10-item gate with genuinely different surface coverage from draft 5.
- **F5 (analyst-b medium) — §10.7 default stated.** Option 1 (defer portability) is the named default. Option 2 (port-with-compensatory-scoping) requires three named conditions all met (target repo independent reliability evidence; analyst-lane budget drawn in advance; first-repo port framed as reversibility-first experiment with kill trigger). Closes the cost-pressure decision-hygiene gap.
- **F6 (analyst-b medium) — `compile_decision_inputs.py` ownership.** Added to Primitive C Work and Phase 0 Readiness. `/compile-decision-inputs` skill registered. Success criterion #17 now has a clear primitive owner.
- **F7 (analyst-b low-medium) — `harness_assumptions.md` worked example committed.** Schema enforced: brittleness signal must be machine-observable (grep pattern, CI check, hook precondition); natural-language signals are insufficient. Entry follows `assumption → observation → brittleness signal → refresh trigger` with one full worked example.
- **F8 (analyst-b medium) — GC threshold tightened.** Folded into F2 fix: ≥3 accepted across ≥2 distinct categories.
- **F9 (analyst-b low) — digest script ownership.** Folded into F6 fix.
- **F10 (analyst-b low-medium) — agent-readability floor committed in plan.** Provisional ≥7/10 floor in §5-C and ADR 001; sub-plan may tighten but may not loosen.
- **F11 (analyst-b low) — Goal #8 disambiguation.** §2 Goal #8 text now explicitly assigns *discovery* to Primitive E and *escalation via approval classes* to Primitive B sub-deliverables B.6/B.7.
- **F12 (analyst-b medium) — event schema versioning.** Primitive A Work now includes `schema_version` field; Phase 0 schema is `v1`; additive evolutions are `v1.N` (replay-compatible); breaking changes require `v2` with explicit migration sub-plan.
- **F13 (analyst-b low) — §16 Delta editorial.** Documented in this section instead of the prior bullet about preflight cardinality preservation.

No primitives added or removed. No phases added or removed. Plan got
sharper on falsifiability, write-discipline, and agent-first conventions.

---

## 17. Delta From Draft 4

Recording what changed relative to draft 4:

- **Primitive H deferred from Phase 0 to Phase 1** per analyst-a §3.3 Option A. H now builds concurrently with the proving run in Phase 1; Primitive G absorbs rollback validation for Phase 0 changes; H's Phase 1 Validation is a mandatory input for any Phase 2 portability decision (§10.7). Phase 0 primitive count: 8 → 7 (A-G). Total primitives (Phase 0 + Phase 1): still 8.
- **Primitive B extended** with tool risk registry + approval classes and with prompt-policy change discipline (trigger / expected effect / rollback condition as structured commit-message fields).
- **Primitive C extended** with `harness_assumptions.md` as 6th KB artifact and with the agent legibility scorecard as a periodic-review artifact.
- **Primitive D extended** with the entropy / garbage-collection report as a second archivist output symmetric to candidate-lessons.
- **Primitive H extended** (now Phase 1) with the canary task suite and the idempotency checklist.
- **Preflight checklist** (§6.4) swaps the replay item (Primitive H, not available at preflight time) for the agent legibility item (Primitive C). Preflight remains a 10-item gate.
- **Kill criteria (§11)** updated: phase membership noted per primitive; Primitive C kill adds the `harness_assumptions.md` refresh-rate check; Primitive D kill adds the GC-output check; Primitive B kill adds the approval-class-violation check; Primitive H kill moves entirely to Phase 1 and absorbs the canary-suite-running check.
- **Success criteria (§13)** expanded from 13 to 17 items to cover: canary running, harness assumptions refreshing, GC proposals accepted, legibility scorecard maintenance, plus the prior criteria now phase-annotated.
- **§10.7 design coupling note** sharpened with two explicit Phase 2 options if H fails validation (defer portability, or accept port with compensatory scoping).

## 18. Delta From Draft 3 (preserved for lineage)

Recording what changed relative to draft 3:

- **Goal #16 struck.** Previous draft 3 §2 item #16 ("Any further improvements") removed. Floor-not-ceiling intent moved to §2 preamble as a scope-lock statement. Resolves analyst-a finding 2.2 (scope-creep license contradicting the plan's own risk mitigation).
- **Ledger replaced with hybrid subsections + digest pattern.** Previous draft 3 §15 ledger removed. Replaced with the write/read-surface split analyst-a proposed, extended to include meta-findings file + template enforcement + digest script + durability framing. Resolves analyst-a finding 2.4 (ledger graveyard risk, tag taxonomy collapse).
- **Kill criteria tightened** per analyst-a §3.5: Phoenix counts promoted findings not UI opens; skill/prompt edits must cite trace IDs or incident fingerprints; KB citations must be grep-verifiable in PR bodies or task packets; messaging triage rate has minimum denominator; reliability lab requires post-hoc surprise scenario.
- **Proving-run data-sufficiency check added** (§6.1) with measurement-methodology-overhaul pivot alternative. Resolves analyst-a finding 2.6.
- **Platform-11/13 dismissal tied to ADR 001.** §12 Risks row 6 references `knowledge/adr/001-platform-pattern-reset.md` filed at Phase 0 kickoff. Resolves analyst-a finding 2.8.
- **Target-repo audit specified with 2-3 days budget and 8-item output format** (§4.2). Resolves analyst-a finding 2.7.
- **Phoenix workflows sharpened** with trigger/consumer/cadence/output per workflow (§5 Primitive A). Resolves analyst-a finding 2.9 / D1 Partial.
- **§7.2 (now §8.2) #3 cmux shape description struck.** Only trigger condition remains ("Only relevant if portability goes forward"). Shape is a Phase 2 decision output, not a pre-description. Resolves analyst-a finding 2.10.
- **§5-H "Intended to be" hedge** added to the portability-dry-run framing. §10.7 adds a design-coupling note: demoting H under its kill criterion forces a Phase 2 re-evaluation of portability cost. Resolves analyst-a finding 2.11.
- **Primitive A cascade risk** called out explicitly in §12 Risks: if A slips, D/E/H slip; A ordered first; downstream primitives re-verify A emits before starting their own substrate work.
- **Step template (§4.4 step 5)** now requires appending a Phase 2 Decision Inputs subsection to every closeout. Subsection discipline is a §13 success criterion.
- **ADR 001 referenced in Phase 0 Dependencies (§4.5)** and Primitive C Readiness (§5-C).
- **Primitive ordering confirmed A, B, C, D, E, F, G, H** alphabetical; matches §11 kill-criteria table ordering. Resolves analyst-a finding 2.1 primitive-ordering concern.
- **Primitive H kept in Phase 0** in draft 4 (analyst-a §3.3 Option A was to defer; operator directive "do not reduce vertical ambition" took precedence). *Reversed in draft 5 after operator clarified that "pre-Phase-2" is the real constraint, not "Phase 0."*

No capabilities cut. No phases added. The plan got sharper on measurement
and write-discipline.

---

## Outcome

_To be filled after implementation._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN, #NNN
- Notes: deviations from plan, preflight and proving-run outcomes, Phase 2 decisions.

## Phase 2 Decision Inputs

**Portability readiness:** no change (plan itself is pre-execution; Phase 2 inputs begin accruing once Phase 0 work opens; parallel Fund + RIN-SnD shape audits per §4.2 will be the first portability-tagged entries).
**Meta-layer need:** no change (deferred to Phase 2 decision gate by design).
**Kill signal for primitive(s) named:** N/A (no primitive execution yet).
**Surprise finding:** The review → revision cycle across drafts 1→6 (draft 1 → analyst-a review (B grade) → drafts 2-4 → analyst-b review (B+ grade) → draft 5 → operator directives → draft 6) is itself a demonstration of the Phase 2 Decision Inputs pattern, the agent-readability theme (goal #16), and the hybrid subsections+digest mechanism all working in miniature. Each draft's "Delta From Draft N" section behaves as a structured finding log; analyst review artifacts fed directly into successor draft scope; the scorecard + grade conventions (B, B+, with concrete fix lists) are themselves agent-readable. Worth reflecting in ADR 001 alongside the Platform-11/13 dismissal evidence as the empirical basis for the durable-infrastructure framing in §15.8 and §10.8.
**Disposition:** open
