# Steward Platform — Governing Plan (Draft 8)

**Date:** 2026-04-23
**Status:** PROPOSED — revision of `governing_plan.draft7.md` incorporating analyst-d's two-track review (901-line critique at `plans/steward_platform/draft7_review_analyst-d.md`, graded draft 7 at A, recommended PROMOTE-AFTER-FIXES) plus an external-analyst change set against draft 6 applied to draft 7 (goal-1 mechanism expansion; B.11/B.12; improvement-quality metrics; preflight 11th item; overfitting risk; Chrome-native control; core-framing reframe) plus plugin-ecosystem three-tier preference integration.
**Scope:** Mature the existing Bid-Euchre steward control plane into a full-ambition single-repo platform (self-improving via mechanism-level improvements not just task outputs, auditable, durably remembered, token-efficient, actively triaging, replay-testable, agent-readable, native-substrate-aware, reversibility-disciplined, observable-by-default), prove it on a complete research run, and only then decide what to port and whether a meta-layer earns its slot.
**Supersedes:** `governing_plan.draft7.md` (plus all prior drafts). The prior `agent_ops` governing plan remains historical record for shipped Phase 0-4 work and in-flight Phase 5 work absorbed into Phase 0 below.

**Revision drivers (draft 7 → draft 8):**

*Analyst-d findings (G6–G13 + Q5–Q8):*
- **G6 (medium, mandatory)** — `rework_spec.md` §3 catalogues 18 ops modules; actual `src/bid_euchre/ops/` has 42 — 21 uncatalogued. Sub-plan §3 extended with dispositions for all 42.
- **G7 (low-medium)** — hook catalog file-level (not category) for 34 files; `ops/worktrees.py` registry-state + `PROTECTED_WORKTREE_NAMES` preservation explicitly named in migration row.
- **G8 (low)** — changelog skill source list: wayback trimmed to best-effort; GitHub release notes + docs.anthropic.com blog added; operator X-list (not threads) as scalable reference.
- **G9 (low)** — skill count reconciled to 38 actual; 6 missing catalogued; monitoring/playtest consolidation reframed from "surface N→M" to "deduplicate helpers, preserve consumer-differentiated surfaces."
- **G10 (medium, mandatory)** — §5-B B.9 clarifies `.claude/system_prompts/<lane>.md` vs. existing `.claude/agents/<lane>.md` via explicit ADR at Phase 0 kickoff (replacement / supplement / orthogonal).
- **G11 (low-medium)** — §10.9 adds **Pattern 7 Reversibility-as-default** and **Pattern 8 Observable-by-default** with enforcement surfaces.
- **G12 (low)** — `plans/sessions/` 264-file sweep becomes a script deliverable (`scripts/internal/sweep_session_plans.py`).
- **G13 (low-medium)** — `.claude/agents/` catalogued in sub-plan; 19-lane → 8-archetype mapping published as Primitive G first-deliverable sub-sub-plan.
- **Surprise-elevated to Pattern 9** — load-bearing-but-floating recurred 3× (F6 / G1 / G6). §10.9 Pattern 9: any script/module/file referenced in §N.M of a plan must be enumerated in owning primitive's Work + Readiness; enforced via `agent_readability_lint.py` extension.

*External-analyst change set (applied to draft 7):*
- **Goal 1 mechanism expansion** — "self-improving" explicitly includes improving task-packet shaping, routing heuristics, review heuristics, skill-selection heuristics, prompt-policy generation quality.
- **B.11 Orchestration recipe archive** — versioned record of packet shapes/routing decisions/lane strategies that produced good outcomes.
- **B.12 Improvement-mechanism evaluation** — measures whether changes to packets/routing/prompts/skills improved later execution.
- **Improvement-quality metrics family** — Phase 1 Validation rows under Primitive B.
- **Preflight 11th item** — repeat-task improvement probe. §6.4 grows 10 → 11 items.
- **§12 overfitting risk** — improvement-loop overfitting on recent local patterns.
- **KB orchestration patterns** — §5-C Primitive C Work notes PLAYBOOKS / anti_patterns / ADRs capture execution-pattern knowledge, not only domain knowledge.
- **Archivist orchestration-insight extraction** — §5-D Primitive D extended.
- **Chrome-native steward control** — Primitive G Tier A scope: dedicated Chrome profile; scoped browser tasks; action logging tied to task/session IDs.
- **§1 Decision reframed** as "governed self-improvement loop inside a project cell."

*Plugin-ecosystem integration:*
- **§10.9 Pattern 2 extended** to three-tier native-substrate preference: native Claude Code feature → official plugin → high-trust third-party plugin → bespoke.
- **ADR 007 specified** — `melodic-software/claude-code-observability` as primary target.
- **ADR 010 (new)** — Memory MCP server adoption, `doobidoo/mcp-memory-service` primary candidate.
- **B.8 specified** — Agent Teams + TeammateTool + Task system (not generic "native task system evaluation").
- **ADR 005 expanded** — official code-review plugin (five-reviewer confidence scoring) alongside `/autofix-pr`.
- **External-signal sources extended** — plugin registries added to `knowledge/external_signal_sources.md` seed.
- **Plugin source evaluation dispatched in parallel** (see `plans/steward_platform/plugin_source_evaluation_handoff.md` + packet `a0cb1ca3a256`); findings fold into ADR seeds as follow-up commit post-draft-8-promotion.

*Analyst-d open questions Q5–Q8 resolutions:*
- **Q5** — ADR 002 moved to Phase 0 close (retrospective evidence stronger after plan demonstrably runs).
- **Q6** — `/loop 3d` cadence is operator-configurable; revisit based on Phase 0 changelog velocity.
- **Q7** — §15.4 digest spec verifies per-repo-section grouping on single-file shape audits.
- **Q8** — §6.1 adds explicit cross-reference to `plans/browser_game_expansion/` sequencing; data-sufficiency pivot activates automatically if expansion plan pauses.

**Earlier revision drivers preserved for lineage:** see §17-§20 (Delta from drafts 7/6/5/4/3).

**Revision drivers (draft 6 → draft 7):**
- **G1 (medium, must-fix) — agent-readability lint script was load-bearing but floating.** Same pattern as F6 recurring in the same draft as F6 is fixed. Added `scripts/internal/agent_readability_lint.py` + `/lint-agent-readability` skill to Primitive C Work + Phase 0 Readiness.
- **G3 (low-medium) — Primitive C density resembles pre-Option-B Primitive B.** Added one-paragraph thematic-coherence justification to §5-C preamble explaining why C's deliverables form a single coherent cluster without needing a sub-deliverables table.
- **G4 (low-medium) — §15 schema didn't represent the "insufficient evidence" class.** Added 5th prompt to §15.2 subsection schema: `**Re-evaluation needed in Phase 3:** [...]`; §15.4 digest parser extended; §15.7 Phase 2 use extended with fifth bucket.
- **G5 (low, editorial) — §13 duplicate item "17".** Renumbered §13 cleanly.
- **Q3 (low) — §11-H analyst-lane post-hoc scenario selection timing.** Clarified as "during Phase 1 as the proving run accumulates."
- **Operator directive — clock-time simplification.** Dropped the `Slice elapsed:` write-discipline mechanism; kept the intent language in §3 and §4.1. §11 soft re-evaluation trigger simplified back to single-signal (activity volume only). SC #18 (relative clock-time recording) removed.
- **Claude Code native-substrate integration (Tier S × system-rework).** Per-primitive integration of Monitor tool, conditional hooks, lifecycle hooks (PermissionDenied / StopFailure / TaskCompleted / TeammateIdle / ConfigChange), WorktreeCreate/Remove hooks + declarative worktree isolation, session metadata (`${CLAUDE_SESSION_ID}`, `last_assistant_message`, session title), shared project memory across worktrees, HTTP hooks, native task/dependency system (evaluation ADR via B.8), read-tool token reductions + large tool result persistence, native `/cost` breakdown, per-tool MCP result-size override, plugin executables on PATH, tool-search, auto memory (supplementary), Setup hook event, remote-control / remote sessions. Evaluate-only for `/autofix-pr` (overlap with `scripts/internal/review_driver.py`) and Auto mode codification (documents existing usage).
- **Primitive G scope reshape.** `ops/worktrees.py` migration target shifts from "refactor 44 hard-block literals" to "migrate to native WorktreeCreate/Remove hooks + declarative isolation." `ops/token_economy.py` 22 hard-blocks still need bespoke fix. New Setup hook formalizes `steward-session.sh` bootstrap. Heartbeat classifier (just shipped via #2743) becomes redundant once TeammateIdle is wired.
- **New architectural section §10.9 Extensibility patterns.** Codifies six cross-cutting patterns (adapter contract; native-substrate-first defaults; hook taxonomy; skill family discipline; plan template enforcement; per-surface owner).
- **New §15.3 tag `native-substrate-signal`.** For ledger entries produced by the changelog review skill when new Claude Code features stale harness assumptions.
- **New addendum file `claude_code_changelog_implications.md`.** Companion reference alongside `phase2_harness_engineering_research.md` + `post_phase2_sidecar.md`. Contains plan-tier vs. system-rework-tier comparison, per-system rework specs, changelog review skill spec. Refreshed by the scheduled changelog review skill.
- **New sub-plan `0_hardening/sub/rework_spec.md`.** Per-surface tactical analysis of existing steward systems — what to trim / consolidate / modify under native-substrate adoption. Phase 0 execution artifact.
- **New changelog review skill** under Primitive D: `/review-claude-changelog` scheduled 2-3×/week; scrapes `https://code.claude.com/docs/en/changelog` + `https://code.claude.com/docs/en/whats-new` + weekly pages; uses `/insights` tool; produces `knowledge/_candidates/<date>_changelog.md` proposing adoption candidates; flags stale `harness_assumptions.md` entries; writes ledger entries under `native-substrate-signal` tag.
- **New success criterion #20.** Changelog review skill produces ≥1 `native-substrate-signal` ledger entry over the proving run.

**Earlier revision drivers preserved for lineage:** see §17-§20 (Delta from drafts 6/5/4/3).

---

## 1. Decision

Build the steward platform as a **governed self-improvement loop inside a
single project cell** — not merely a task coordinator. The distinction
matters: draft 8's scope is explicitly about improving *how* work gets
done (packet shaping, routing, prompts, skills, policies) alongside
*what* work gets done (task completion). The plan's goals, primitives,
metrics, and kill criteria all measure the self-improvement mechanism,
not only task output.

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

1. **Self-improving** — the platform improves the *mechanisms* that produce future lane behavior, not just immediate task results. Explicitly includes improving: (a) task-packet shaping (how the orchestrator scopes work), (b) routing heuristics (which lane / model / effort for which task type), (c) review heuristics (which reviewer roles for which change class), (d) skill-selection heuristics (which skill for which intent), (e) prompt-policy generation quality (how prompts are constructed). Skill promotion, prompt-policy evolution, and adaptive dispatch feed back into all five mechanism classes, not just task execution output. See §5-B sub-deliverables B.1 (adaptive dispatch), B.2 (skill promotion loop), B.3 (prompt-policy registry), B.4 (prompt-policy change discipline), B.5 (analyst-vs-author routing encoded as policy), B.11 (orchestration recipe archive), B.12 (improvement-mechanism evaluation).
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
- **Relative clock-time (intent):** this plan does not attach absolute clock-time budgets to any phase or primitive. "We don't know what's realistic until we measure." Time is a diagnostic input *if* the operator wants to look at it post-hoc (git history, PR timestamps, event traces), not a governance mechanism. No write-discipline obligation for authors to record elapsed time in closeouts.
- **Agent-readability:** the property of a durable artifact (plan section, KB entry, ADR, sub-plan, briefing, etc.) being navigable, parseable, and loadable by an agent with minimal preamble. Tested by the agent-readability scorecard (formerly "legibility scorecard"; renamed to clarify that the primary audience is agents, not humans, per goal #16).
- **Soft re-evaluation trigger:** when a primitive sees activity below its kill-criterion threshold during the proving run, the kill criterion does not fire automatically. Instead, the primitive routes to Phase 2 flagged as "insufficient evidence." Phase 2 decides retire / re-scope / re-evaluate-in-Phase-3. Default is re-evaluate. This preserves the usage-based kill discipline while closing the unfalsifiability trap that would otherwise let "no evidence yet, keep alive" primitives accrete.
- **Native-substrate adoption:** the preference — per §10.9 extensibility pattern #2 — for Claude Code native features (Monitor tool, lifecycle hooks, worktree hooks, shared project memory, HTTP hooks, etc.) over bespoke synthesis when a native feature covers the need. Tracked via `knowledge/harness_assumptions.md` entries and the changelog review skill (§5-D).

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
are the discipline; the work takes the time it takes. Time is a diagnostic
input (post-hoc, from git history and event traces) not a governance
mechanism. See §3 "Relative clock-time (intent)."

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
- **Native Claude Code adoption state (draft 7 addition).** Which Tier S features from `claude_code_changelog_implications.md` (Monitor tool, conditional hooks, lifecycle hooks, worktree hooks, shared memory, HTTP hooks, native task system, `/usage`, `/cost`, `--system-prompt-file`, etc.) are already adopted by this repo. Drives portability cost estimate: a repo already on native has a much shorter port path than one still on bespoke synthesis.

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
5. **Learning / handoff** — update checkpoints, KB artifacts, prompt-policy candidates, improvement backlog; **append a Phase 2 Decision Inputs subsection** (§15) to the sub-plan outcome block or primitive closeout document. No slice is considered complete without the subsection. (Draft 6's `Slice elapsed:` requirement removed per operator directive; elapsed time is diagnostic, not a write-discipline obligation.)

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

**Native-substrate integration (draft 7 Tier S).** Primitive A's scope
shifts from "build event-driven attention from scratch" to "absorb and
normalize Claude Code native events into the unified schema." Less
synthesis, more subscription. Specific native features adopted:

- **Monitor tool + self-pacing `/loop`** — native substrate for event-driven attention; replaces polling loops in `ops/monitor.py` and large parts of `ops/attention.py`.
- **Native lifecycle hooks** — `PermissionDenied`, `StopFailure`, `TaskCompleted`, `TeammateIdle`, `ConfigChange` become first-class event emitters; the unified schema absorbs and normalizes them (instead of synthesizing from raw tool-call inspection).
- **Conditional hooks** — scope trigger conditions precisely; reduces per-tool-call overhead across the existing hook set.
- **HTTP hooks** — cleaner integration point for Phoenix exporter wiring (replaces shell-glue).
- **Session metadata** — `${CLAUDE_SESSION_ID}` becomes a first-class schema ID; `last_assistant_message` in stop hooks enriches trace detail; session title setting via hooks drives lane-attribution clarity in the dashboard.
- **Recaps** — Claude Code's recap feature (short summaries of what an agent did and what's next) becomes a native input to the archivist (Primitive D session-postmortem mode). Recap content + last_assistant_message together produce richer per-session handoffs than current MEMORY.md compaction synthesis.

**Work:**
- Finalize event schema around first-class IDs: `project_id`, `cell_id`, `session_id` (maps to `${CLAUDE_SESSION_ID}`), `task_id`, `lane_id`, `trace_id`, `incident_fingerprint`, `prompt_policy_version`, `schema_version`.
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
| B.8 Native task/dependency system evaluation | #4, #6 | ADR filed at Phase 0 close stating which parts of steward's task_queue contract are subsumed by native Claude Code task substrate (if any) vs. what remains bespoke (scope-locked packets, domain routing, lane affinity almost certainly stay bespoke) | ADR referenced by any sub-plan that touches task_queue.py; no silent duplication of native capability | See §11-B row 2 |
| B.9 Per-lane custom system prompts via `--system-prompt-file` | #7 | `.claude/system_prompts/<archetype>.md` files exist for 8 lane archetypes (mapping 19 current lanes → 8 per G13 sub-sub-plan: orchestrator / ops / review / analyst / author / brws-author / flex / scratch). Steward-session.sh bootstrap (per Primitive G Setup hook) launches each lane with `--system-prompt-file .claude/system_prompts/<archetype>.md`. **Relationship to existing `.claude/agents/<lane>.md` (23 files currently loaded by Agent tool) resolved via ADR at Phase 0 kickoff (G10 fix)** — operator picks one of: (a) **Replacement** — system_prompts supplants agents-file body content; agents-file carries frontmatter/metadata only; (b) **Supplement** — system_prompts is sparse override loaded in addition to agents-file; loading order documented; (c) **Orthogonal** — system_prompts covers per-launch `--system-prompt-file` override; agents-file covers Agent-tool-loaded subagent behavior; both persist describing different things. Default assumption until ADR files: (c) orthogonal. Rationale: Claude Code default system prompt degrades 4.7+ behavior vs. sparse custom prompts (harness_assumption "Default system prompt behavior") | Every fleet launch passes `--system-prompt-file`; zero launches fall back to default; observable behavior improvement tracked (e.g., prompt-policy-cited-in-trace rate rises after B.9 lands); G10 ADR filed before Primitive G work begins | See §11-B row 2 |
| B.10 Effort-level configuration per task type | #6 | Adaptive dispatch policy (B.1) records per-task-type effort recommendations (lower / xhigh / max per Boris Cherny Opus 4.7 guidance: lower for simple, xhigh for most, max for hardest). `.claude/rules/tool_risk_registry.md` (B.6) cross-references effort recommendations with approval classes | Effort recommendations cited in ≥80% of dispatch decisions during the proving run; operator overrides tracked as B.1 outcome-feedback signal | See §11-B row 1 |
| B.11 Orchestration recipe archive | #1 (self-improving mechanism) | Versioned record at `knowledge/orchestration_recipes/` (or `knowledge/PLAYBOOKS.md` section) capturing packet shapes, routing decisions, review/escalation patterns, and lane strategies that led to good downstream outcomes. Each recipe entry: context → decision → observed outcome. Updated by archivist (Primitive D) from proving-run events | ≥3 recipes recorded during the proving run with observable downstream reuse (another packet cites the recipe or the recipe's pattern is applied by adaptive dispatch B.1) | See §11-B row 1 |
| B.12 Improvement-mechanism evaluation | #1 (self-improving mechanism) | `scripts/internal/measure_improvements.py` — scheduled weekly; measures retry-rate / author-rework-rate / routing-correction-rate / prompt-policy-rollback-rate / skill-promotion-usefulness-rate deltas after mechanism changes. Output at `knowledge/_candidates/<date>_improvement_metrics.md`. Operator reviews; net-positive changes promoted into active policy; net-negative changes rolled back per goal #13 reversibility discipline | ≥1 mechanism change (packet shape / routing / prompts / skills) demonstrates net-positive improvement-quality metric delta during the proving run; ≥1 mechanism change demonstrates net-negative and is rolled back (proves the feedback loop catches regressions) | See §11-B row 1 |

**Combined notes:**
- All sub-deliverables share the same `prompt_policy_version` machinery and rollback path (policy version pin works; dispatch policy can revert to prior shadow version; skill promotions can be unpromoted via a single command).
- The tool risk registry **documents, does not replace**, the existing auto-mode classifier at `.claude/rules/80_permission_model.md`.
- Combined readiness gate: every row above shows green.

### Primitive C — Durable Memory and Knowledge Base (Phase 0)

**Goals served:** #3 (durable memory), #12 (KB system), #14 (ADR capture).

**Thematic-coherence justification (G3, draft 7).** Primitive C has ≥8
distinct deliverables (6 KB-class artifacts + MEMORY.md + planning
templates + agent-readability scorecard + 2 scripts + worked-example
documentation). That looks like the deliverable density F3 flagged for
Primitive B. However, C's deliverables are all **durable-artifact
infrastructure under a small set of home directories** (`knowledge/`,
`plans/_templates/`, `scripts/internal/`) with a single write-discipline
surface (`/create-plan` + `/create-adr` + `/lint-agent-readability`) and
a single semantic purpose (agent-loadable, durable knowledge that
survives session boundaries). B's pre-Option-B mix was heterogeneous
across dispatch, skill loop, prompt-policy, and risk-registry surfaces;
C's mix is thematically coherent. The sub-deliverables table pattern F3
applied to B is not needed here — the combined readiness gate ("every
Readiness bullet shows green") works because the bullets are mutually
reinforcing, not independently failable.

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
- **`compile_decision_inputs.py` (F6):** implement `scripts/internal/compile_decision_inputs.py` per §15.4 spec — globs `plans/steward_platform/**/*.md` and sub-plan outcome files for `^## Phase 2 Decision Inputs` sections, parses 5 prompts + disposition, groups by Decision Axis, generates `decision_inputs_digest.md` + nightly snapshot at `_digest_snapshots/<date>.md`, flags missing subsections at the path level. ~50 lines. Invokable as `/compile-decision-inputs` skill from any lane.
- **`agent_readability_lint.py` (G1 fix, draft 7):** implement `scripts/internal/agent_readability_lint.py` — runs against `plans/**/*.md`, `knowledge/**/*.md`, `.claude/skills/**/*.md` and flags violations of the §10.8 agent-first conventions: missing `§N.M` IDs where expected; inconsistent cross-reference style (`./`, `../`, bare-filename refs); schemas introduced without worked examples; preambles exceeding ~25 lines; orphan references; duplicate IDs. Produces a clean-or-baseline-report output. Invokable as `/lint-agent-readability` skill. ~100 lines. Lint script is the *run-against-existing-artifacts* gate complementing `/create-plan` skill's *creation-time* template enforcement.
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
- `agent_readability_lint.py` committed; runs against the repo plan/KB tree and either passes clean or produces a documented baseline of pre-existing violations (each tagged for fix-now or fix-via-sub-plan); `/lint-agent-readability` skill registered.
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

### Primitive D — Archivist Script, Session Postmortem, and Changelog Review (inflow Phase 0; outflow Phase 1; changelog Phase 0)

**Native-substrate integration (draft 7 Tier S).** Archivist inputs
shift from "parse event logs + PR outcomes + task completions" to
"subscribe to native lifecycle hook streams + parse PR outcomes." Less
parsing, more subscription.

**New scope in draft 7: changelog review skill.** A third archivist mode
that scrapes Claude Code release activity for platform-adoption
candidates. Symmetric to internal archivist: internal curates events →
lesson candidates; changelog review curates external releases → adoption
candidates. See below for full spec.

**Goals served:** #11 (archiving/evaluation), supports #3 (durable memory).

**Phase split rationale (F2):** the inflow half (lessons / incidents / postmortems) operates against events, PR outcomes, and task completions that exist from Phase 0 onward. The outflow half (entropy / GC report) operates against the *KB itself*, which doesn't exist meaningfully at Phase 0 start — NOTES, PLAYBOOKS, anti_patterns, incidents, ADRs all begin empty or near-empty. GC has nothing to detect at Phase 0 readiness. So GC is split to Phase 1 work, parallel to Primitive H's Phase 1 framing.

**Work:**
- `scripts/internal/archivist.py` — scheduled (nightly + end-of-session) script. Reads events, inbox, PR outcomes, task completions. Two outputs across two phases:
  - **Phase 0, inflow:** `knowledge/_candidates/<date>_lessons.md` — templated candidate lessons, incident candidates, token-efficiency outliers for operator promotion. Readiness: scaffolding + targeted unit tests against seeded fake-event fixtures.
  - **Phase 1, outflow:** `knowledge/_candidates/<date>_gc.md` — entropy report: stale KB entries (not referenced in N sessions), dead skills (not invoked since promotion), obsolete prompt-policy versions (superseded), orphan artifacts (referenced file or trace ID no longer exists), KB entries where linked evidence has expired. Phase 0 ships the *code path* smoke-tested against seeded fake KB state (same fixtures as inflow). Full activation begins when the KB has accumulated ≥2 weeks of promoted entries during Phase 1.
- Operator or analyst reviews candidates on each side and approves.
- Session postmortem: end-of-session trigger writes a per-session handoff into MEMORY.md + feeds candidates into the archivist queue.
- Not a lane. Invokable as a skill from any lane for real-time curation (`/run-archivist --mode lessons` or `--mode gc`).
- **Changelog review skill (Phase 0 work, new in draft 7):**
  - `scripts/internal/changelog_review.py` — uses WebFetch and the `/insights` tool to scrape `https://code.claude.com/docs/en/changelog`, `https://code.claude.com/docs/en/whats-new`, and discoverable per-week pages (`whats-new/2026-wNN`); attempts to find earlier weekly pages via archive / wayback / internal cache.
  - Invokable as `/review-claude-changelog` skill.
  - Scheduled via `/loop 3d /review-claude-changelog` (2-3 runs/week).
  - Output: `knowledge/_candidates/<date>_changelog.md` proposing adoption candidates with: feature name; steward primitive(s) it touches; whether it stales any `harness_assumptions.md` entry; tier recommendation (S/A/B/C per plan rubric); operator decision fields (accept / defer / reject).
  - Integration with harness assumptions: when the scan finds native Claude Code now ships a capability steward currently synthesizes, the corresponding `harness_assumptions.md` entry is flagged *stale* and a refresh is proposed. This closes the loop between external platform evolution and internal brittleness tracking.
  - Integration with decision-inputs digest: changelog findings write ledger entries under the new `native-substrate-signal` tag (§15.3).
  - Seed content: the operator-provided Jan-Apr 2026 tier list (committed in `plans/steward_platform/claude_code_changelog_implications.md`) is the starting corpus.
- **External-signal source extension (draft 7).** The changelog review skill is not limited to the official changelog. It also scrapes operator-curated sources for performance / workflow tips (e.g., Anthropic team posts, davidad-style commentary, community digests). Sources live in `knowledge/external_signal_sources.md` (operator-edited list of URLs to scrape). Examples of high-signal sources: Boris Cherny tweet threads on Opus 4.7 workflow patterns; davidad on `--system-prompt-file` behavior. Source list is itself a goal-#16 artifact (predictable structure: one URL per entry with category tag and last-scraped date).

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

**Native-substrate integration (draft 7 Tier S).**
- **Conditional hooks** — scope active-triage trigger conditions precisely; reduces per-tool-call overhead significantly across the existing hook set.
- **TeammateIdle** — native lane-stall detection signal; replaces custom heartbeat polling in `ops/dashboard.py` and `ops/attention.py`.
- **StopFailure** — native failure-detection signal; becomes direct input to active triage.
- **HTTP hooks** — replace shell-glue for bus subscribers and external service integration.
- **Channels improvements + newer MCP push-message support** — native channel substrate; evaluate against `ops/message_bus.py` for subscriber-wiring simplification.

**Work:**
- Close message-bus proving debt. Absorb #2689 heartbeat pure-shell, #2690 lane-id dedup, #2691 hook JSON escape follow-ups.
- Publish bus p50 and p95 delivery latency to dashboard.
- Active issue triage: event-driven signals auto-create GitHub issues with correct labels. **Signals now sourced from native lifecycle hooks (CI red via review_driver event, review blocked via PermissionDenied, stalled lane via TeammateIdle, orphan worktree via WorktreeRemove anomaly, token anomaly via `/usage` outliers) rather than custom polling synthesis.**
- Migrate existing hook set from unconditional to conditional hooks where safe; document ordering and scope per hook in `.claude/hooks/README.md`.
- Integrate `triaging-issues` skill with event-driven inputs.
- Evaluate HTTP hooks for existing shell-glue in `.claude/hooks/` — migration ADR (ADR 004) files the cost/benefit boundary.

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

**Native-substrate integration (draft 7 Tier S).**
- **Native `/usage`** — breakdown of where Claude Code usage goes (parallel sessions, subagents, cache misses, long context) with optimization tips. Directly relevant to Slice F evaluation: `/usage` output becomes a comparison feed alongside steward's bespoke rollups; discrepancies flag drift in the bespoke measurement path.
- **Native `/cost`** — complements `/usage` with a cost-specific view.
- **Read-tool token reductions / large tool result persistence** — change the baseline cost profile; requires baseline re-capture before Slice F observations are final.
- **Per-tool MCP result-size override** — cap dashboard / task-list / inbox output sizes to reduce token cost on high-frequency operational queries.

**Work:**
- Execute token-economy Slice F evaluation protocol (drafted as PR #2716). The externally-committed 1-2 week observation window applies.
- **Re-capture tokens-per-merge baseline** (§4.3) *after* Read-tool token reductions + large tool result persistence are live in the operator's environment. Draft 6 baseline may be stale.
- **Adopt native `/usage` as a comparison feed.** Steward's bespoke `ops/token_economy.py` rollups continue to run (they emit telemetry into the unified schema); `/usage` output is captured nightly by the archivist and diffed against steward rollups. Discrepancies are flagged as either (a) measurement-path drift in `token_economy.py` or (b) `/usage`-specific categories steward doesn't yet surface (cache-miss breakdown, long-context cost). ADR 003 filed at Phase 0 close documenting which native categories steward adopts into its own rollups and which remain `/usage`-only.
- **Per-tool MCP result-size override** applied to `ops.py dashboard`, `task list`, `inbox`, and other high-output operational commands. Target: reduce tokens spent on operational queries by a measurable margin (e.g., ≥30% on the dashboard and inbox subcommands).
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

### Primitive G — Existing-Debt Closeout + Native-Substrate Migration (Phase 0)

**Goals served:** non-capability primitive; gates all others. Also absorbs the rollback-validation slice of Goal #13 for any reversible change introduced in Phase 0.

**Major scope reshape (draft 7).** Instead of "refactor bespoke
implementations to remove Bid-Euchre literals," much of G's work becomes
"migrate to Claude Code native substrate." This is both a scope
reduction (native features replace a lot of the bespoke surface) and a
scope shift (we're adopting native, not fixing bespoke). Native features
adopted as part of G:

- **WorktreeCreate / WorktreeRemove hooks + declarative worktree isolation** — replaces bulk of `ops/worktrees.py` (44 hard-block literals → ~80% file collapse to thin adapter shim). This is the single largest portability win.
- **Setup hook event** — formalizes `.claude/tmux/steward-session.sh` bootstrap (currently 19-launch shell script with embedded `--permission-mode auto` flags) into a Setup hook, ideally a small declarative config plus a single entrypoint.
- **Remote-control / remote sessions** — evaluate and adopt for the existing away-mode + Telegram + push-notification path (`ops/telegram_filter.py` and related).
- **Shared project memory across worktrees** — enables `ops/memory.py` + MEMORY.md to become a view of shared repo-local state instead of per-worktree silos.
- **Auto memory (Tier A → S for rework)** — adopted as supplementary inflow layer feeding archivist candidates.
- **Plugin executables on PATH** — skill distribution model; `.claude/skills/**` can ship as plugin executables with simpler discovery and installation.
- **Tool-search** — substrate for skill discovery across 30+ skills; reduces ad-hoc skill-name-recall cognitive load.
- **Computer use in Desktop / CLI (Tier B → A for rework)** — evaluation target for browser-game playtest skills (`/playtesting`, `/playtest-hybrid`, `/playtest-strategic`, `/playtest-playwright`); potential consolidation from 4 variants to 2 or 1+computer-use.

**Per-surface tactical analysis** lives in the sub-plan at
`plans/steward_platform/0_hardening/sub/rework_spec.md` — that sub-plan
catalogues every existing ops-package module, hook, script, and skill
with a disposition (keep / modify / consolidate / trim / delete).

**Work:**
- **Native worktree migration:** migrate `ops/worktrees.py` PROTECTED_WORKTREES + WORKTREE_LANE_MAP + related logic to native WorktreeCreate/Remove hooks + declarative worktree isolation. Target: ~80% LOC reduction; remaining shim absorbs the repo-specific adapter boundary.
- **Periodic `/fewer-permission-prompts` invocation:** schedule the existing skill (1×/week) to scan session history, identify repeated permission prompts, and propose additions to `permissions.allow`. Operator reviews and merges proposals. Reduces permission-prompt friction even within auto-mode (auto-mode runtime gate + targeted allowlist = best of both).
- **Setup hook adoption:** replace imperative `steward-session.sh` with a Setup hook spec + declarative lane config. Pass `--system-prompt-file .claude/system_prompts/<lane>.md` (B.9) to every lane launch.
- **Token economy hard-blocks:** zero hard-blocks in `ops/token_economy.py` (22 occurrences). Native `/usage` + `/cost` do not cover these; bespoke fix remains required.
- **Retire fragmented Phase 5 subtrees:** `agent_ops/5_extraction`, `agent_ops/5_cross_model`, `agent_ops/5_skill_learning`, `agent_ops/5_portability_and_learning` each get explicit resolution note (superseded / absorbed / abandoned).
- **Retire heartbeat classifier** in `ops/dashboard.py` (just shipped via #2743) in favor of native TeammateIdle hook. Acknowledged irony; correct direction.
- **Resolve remaining messaging-bus proving items** (overlaps Primitive E).
- **Platform-11 adaptive-dispatch closeout** inside Primitive B or explicitly superseded.
- **Rollback validation** recorded for every reversible change introduced in Phase 0 (satisfies Goal #13 for Phase 0 changes).
- **Non-protected ephemeral worktree sweep** against `.claude/rules/75_worktree_protection.md` list.
- **Skills consolidation pass:** reduce 30+ skills per the rework_spec.md disposition (monitoring family 6→2 with Monitor/TeammateIdle; playtest family 4→2 with computer use evaluation; other consolidations as justified).

**Phase 0 Readiness:**
- Native worktree migration complete: `ops/worktrees.py` PROTECTED_WORKTREES + WORKTREE_LANE_MAP migrated to native WorktreeCreate/Remove hooks + declarative worktree isolation. LOC reduction target ≥80% on the file; remaining content is the repo-specific adapter shim.
- `PORTABILITY_MANIFEST` shows zero hard-blocks in `ops/token_economy.py`. (`ops/worktrees.py` may have residual shim references; acceptable because the shim is the adapter boundary.)
- Setup hook replaces `steward-session.sh`: declarative lane config + Setup-hook-driven launch; every lane launch passes `--system-prompt-file .claude/system_prompts/<lane>.md` (B.9).
- `.claude/system_prompts/<lane>.md` files exist for ~8 lane archetypes; sparse by default per the "default system prompt degrades 4.7+" harness assumption.
- Heartbeat classifier in `ops/dashboard.py` retired in favor of native TeammateIdle subscription.
- Each `agent_ops/5_*` subtree has an explicit resolution note (superseded / absorbed / abandoned) with a pointer to where remaining work lives.
- `agent_ops` plan fragmentation is gone.
- Rollback validation recorded for every reversible Phase 0 change.
- Non-protected ephemeral worktrees swept against the protection list.
- Skills consolidation pass executed per `rework_spec.md` dispositions.

**Phase 1 Validation:** n/a for core debt closeout; however, the native-substrate migrations introduced here (worktrees, heartbeat → TeammateIdle, Setup hook, system-prompt-file) are measured during the proving run as part of other primitives' Phase 1 Validation (Primitive A event-driven monitoring; Primitive E active triage; observable behavior improvement in lane outputs).

### Primitive H — Reliability Lab, Replay Harness, and Canary Suite (Phase 1)

**Phase membership:** Phase 1 (concurrent with proving run). Primitive H is
*not* a Phase 0 readiness gate. It builds out during Phase 1 and must
complete its Phase 1 Validation by end of Phase 1 for the Phase 2 gate
to be able to make a portability decision (§10.7).

**Native-substrate integration (draft 7 Tier S).**
- **Monitor tool** — drives replay-assertion polling natively (watch events until target state reached); also used for canary task suite trigger conditions on prompt-policy / routing / messaging changes.
- **Read-tool token reductions / large tool result persistence** — change what "reconstruct a lifecycle" costs in tokens; Phase 1 Validation thresholds should be set against the post-reduction baseline (coordinate with Primitive F baseline re-capture).
- **Conditional hooks** — canary suite reruns triggered by material platform changes use conditional hooks, not bespoke CI wiring.
- **Verification pattern (`/go`-style):** the canary suite + idempotency checklist work together as the platform-level verification surface, modeled on the Boris Cherny `/go` pattern (test end-to-end + simplify + open PR). Author lanes are expected to verify their own work via this pattern before marking a slice complete (already in step template step 4); H provides the canary-suite + replay-harness substrate that makes verification observable and reproducible.

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
- ≥3 failure-injection scenarios exercised during the proving run (or during dedicated reliability sessions within it); all either pass or produce a documented incident. **At least one scenario is selected post-hoc by an analyst lane during Phase 1, after primitives A, B, and E ship** (Q3 clarification — timing is during Phase 1 as the proving run accumulates, not at end of phase) — to avoid Goodharting the self-chosen minimum.
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
| 11 | Repeat-task improvement probe (external-analyst change set, draft 8) | Run one bounded task end-to-end; revise packet/prompt/skill/routing based on the result (the self-improvement loop of Goal #1 and B.11/B.12); run a similar follow-up task; assert the second pass is observably cleaner by at least one improvement-quality metric (B.12): lower retry rate, lower author rework, cleaner routing, etc. This is the most direct early proof that the *self-improvement mechanism* works — not just that a single task completes. Without this probe, Phase 1 can execute successfully while the mechanism-improvement half of Goal #1 remains unproven. |

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

### 10.9 Extensibility patterns (draft 7, extended draft 8)

Cross-cutting architectural principles for keeping the platform durable,
extensible, and functional as native substrate evolves and steward grows.
Codified so future agents and operators don't re-derive them.

**Pattern 1 — Adapter contract is the canonical extensibility pattern.**
Anything that varies per repo (lane identifiers, worktree naming,
CI command shapes, branch conventions) lives in `src/bid_euchre/ops/adapters/`,
not in `core/` or as scattered module-level constants. The Platform-10
core/adapter split started this; the rework spec (sub-plan) completes it.
Portability work is measured by "adapter shim is the only non-generic
surface," not by "hard-block count."

**Pattern 2 — Native-substrate-first defaults (three-tier preference, draft 8).** New work follows a three-tier evaluation before committing to bespoke synthesis: (1) Claude Code native feature (Monitor, lifecycle hooks, worktree hooks, Agent Teams, `--system-prompt-file`, etc.); (2) official plugin from `anthropics/claude-plugins-official` (e.g., code-review plugin for ADR 005); (3) high-trust third-party plugin (well-maintained, clear license, good adoption — e.g., `melodic-software/claude-code-observability` for ADR 007, `doobidoo/mcp-memory-service` for ADR 010); (4) bespoke synthesis. The `harness_assumptions.md` register tracks entries of the form "we are bespoke because neither native nor plugin covers X." The changelog review skill (§5-D) refreshes those entries when native OR plugin ships a capability; the refresh proposes bespoke → native OR bespoke → plugin migration when warranted. This is the discipline that prevents the platform from accumulating bespoke implementations that native OR the plugin ecosystem has silently superseded.

**Pattern 3 — Hook taxonomy.** Shift from "we have N custom hooks" to
"we subscribe to native lifecycle events + a small bespoke hook layer
for things native doesn't cover." All hooks are either (a) native
lifecycle subscriptions, (b) conditional hooks scoped precisely, or (c)
bespoke hooks justified in `.claude/hooks/README.md` with an ADR.
Unconditional custom hooks synthesizing events from raw tool calls are
anti-pattern going forward.

**Pattern 4 — Skill family discipline.** New skills declare their family
(monitoring / triage / delegation / archivist / playtest / review /
setup / utility / external / scheduling) and operate through established
patterns within that family. Catalog is enforced by
`agent_readability_lint.py`; new skills outside existing families
require ADR justification. Skill consolidation (30+ → fewer) is ongoing
work under Primitive G.

**Pattern 5 — Plan template enforcement.** All new plans/sub-plans use
`plans/_templates/` shapes and conform to goal-#16 agent-first
conventions. Creation-time enforcement via `/create-plan`;
run-against-existing enforcement via `/lint-agent-readability` and the
nightly digest script's missing-subsection report.

**Pattern 6 — Per-surface owner.** Every existing ops-package module,
hook, script, and skill names its primitive owner in the file header
(e.g., `# Primitive: A` as a header comment). This makes "if this
changes, which primitive's scope is affected?" a grep instead of an
investigation. The rework spec (sub-plan) begins populating these
headers during Phase 0.

**Pattern 7 — Reversibility-as-default (draft 8, G11).** Every durable
platform change (skill promotion, prompt-policy edit, dispatch-policy
change, hook migration, KB restructure, adapter modification, ADR
decision) has a rollback path documented at change-time, not post-hoc.
Goal #13 (rollback/disable paths) is already cross-cutting; Pattern 7
codifies the discipline so author lanes and reviewers can key off it.
Enforcement: `plans/_templates/promotion_rollback.md` (Primitive C); PR
template rollback-field section; `agent_readability_lint.py` flags
durable-change PRs missing a rollback section.

**Pattern 8 — Observable-by-default (draft 8, G11).** Every durable
change emits into the unified event schema (Primitive A); every platform
side-effect carries a `trace_id` or `incident_fingerprint`. New
skills / hooks / scripts emit a `task_started` / `task_completed`
equivalent where applicable. Without pattern-level codification, a new
skill or hook could ship without trace emission and fail silently.
Enforcement: `agent_readability_lint.py` flags new skill / hook /
script files without schema-emission calls; §5-A event schema
validator rejects contributions that fail to emit required IDs.

**Pattern 9 — Load-bearing-ownership lint (draft 8, analyst-d surprise finding).**
Any script, module, file, or artifact referenced in a plan section
(`§N.M` of governing plan, sub-plan, or ADR) *must* be enumerated in
the owning primitive's Work bullets and Phase 0/1 Readiness. The
pattern prevents the "load-bearing-but-floating" recurrence (analyst-b
F6 `compile_decision_inputs.py` → analyst-c G1 `agent_readability_lint.py`
→ analyst-d G6 21 ops-module coverage gap — three successive reviews,
same pattern). Enforcement: `agent_readability_lint.py` extension scans
plan/sub-plan text for cross-references to scripts / modules / files
and verifies each has an owning primitive's Work bullet + Readiness
criterion. A cross-reference without owning-primitive enumeration is a
lint violation.

**Enforcement surface.** Patterns 1-9 are enforced through a combination
of agent-readability lint (Primitive C), ADR discipline (Primitive C),
sub-plan template enforcement (Primitive C), changelog review skill
(Primitive D), event-schema validator (Primitive A), and per-primitive
readiness criteria that check for conformance. No pattern is
aspirational-only; each has at least one mechanization path.

---

## 11. Kill Criteria

Per-primitive kill criteria. If a primitive fails its criterion during
Phase 0, 1a, or 1, Phase 2 evaluates whether to rework, downgrade, or
retire it. Kill triggers spawn an ADR.

Thresholds sharpened per analyst-a's review: kill criteria must be
adversarial against the author's sympathies, not aligned with them.
Usage-based rather than clock-time-based.

**Soft re-evaluation trigger (F1, simplified per operator directive).** Usage-based
kill criteria have a known unfalsifiability trap: a primitive that sees
below-threshold activity during a thin proving run (including the §6.1
methodology-overhaul pivot) produces no evidence for or against its kill
criterion. To avoid accreting unfalsifiable primitives into Phase 2 as
"no evidence yet, keep alive," every kill criterion below carries an
implicit **soft re-evaluation trigger**: if a primitive's activity
during the proving run is below the threshold needed to evaluate its
kill criterion, the primitive is flagged at Phase 2 as "insufficient
evidence" and explicitly scoped for a follow-up evaluation window (Phase
3). The plan default for an "insufficient evidence" primitive is
**re-evaluate in Phase 3**, not "keep alive indefinitely." Retire
requires explicit justification. This preserves the usage-based kill
discipline while closing the unfalsifiability trap. (Draft 6's
two-signal differentiation using relative elapsed time was removed per
operator directive — elapsed time remains available as a diagnostic
input post-hoc but is not a formal gating signal.)

"Insufficient evidence" is represented in the Phase 2 digest via the
new 5th prompt in §15.2 (`**Re-evaluation needed in Phase 3:**`).

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
| Improvement-loop overfitting (external-analyst change set, draft 8) | Platform may optimize packet shapes / routing / prompts / skills to recent local patterns and regress on broader task diversity. Mitigation: B.12 improvement-mechanism evaluation tracks metric deltas across a rolling window (not single-change comparisons); archivist (Primitive D) extracts "which packet structures reduced retries" + "which routing choices caused waste" patterns symmetrically so negative signal is as visible as positive; canary task suite (Primitive H) exercises a consumer-differentiated task set that the improvement loop hasn't been trained on, catching regressions on non-recent patterns. §11-B row 1 kill criterion includes "≥3 improvement-mechanism changes that degraded downstream metrics *and* were not rolled back within the next packet cycle" as an overfitting signal. |
| Plugin-ecosystem adoption risks (draft 8) | Adopting external plugins (ADRs 005/007/010) introduces maintainer-dependency risk, license-compatibility risk, schema-lock-in risk. Mitigation: ADRs file at Phase 0 kickoff with explicit adoption decision (adopt wholesale / cherry-pick / reference only / reject); each decision cites source-evaluation evidence (per `plans/steward_platform/plugin_source_evaluation.md`, delivered by analyst packet `a0cb1ca3a256`); each adoption carries a Pattern 7 rollback path; each carries a Pattern 8 observable-by-default contract so steward can detect upstream plugin behavior changes. |

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
17. Goal #16 conformance: `scripts/internal/agent_readability_lint.py` runs clean against the repo plan/KB tree at Phase 0 close and stays clean across the proving run (every new closeout, sub-plan, ADR, and KB entry passes the lint script).
18. Every primitive closeout, sub-plan outcome, preflight report, proving-run report, and shape audit includes a Phase 2 Decision Inputs subsection per §15; digest script regenerates nightly without flagging missing subsections.
19. Changelog review skill (§5-D) runs on schedule (≥2×/week); produces ≥1 `native-substrate-signal` ledger entry during the proving run (validates the scan against `https://code.claude.com/docs/en/changelog` + `https://code.claude.com/docs/en/whats-new` is actually producing signal).
20. At least one Claude Code native-substrate adoption (per §10.9 extensibility pattern #2) lands in the repo during Phase 0 or Phase 1, retiring corresponding bespoke synthesis (e.g., `ops/worktrees.py` migrating to native WorktreeCreate/Remove hooks; or polling loops in `ops/monitor.py` replaced by Monitor tool subscriptions; or heartbeat classifier in `ops/dashboard.py` replaced by TeammateIdle).

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
11. **ADR 001 content.** Draft at Phase 0 kickoff; names three-to-four concrete constraints that paused Platform-11/13 and have since lifted (see §12 Risks row 6); also records the agent-readability scorecard floor (≥7/10) per F10.
12. **ADR 002 — review-cycle-as-evidence (analyst-c Q4).** File at Phase 0 kickoff capturing the draft 1→7 review/revision cycle as empirical evidence for the Phase 2 Decision Inputs hybrid pattern's durability framing in §15.8 and §10.8. Operator decision.
13. **ADR 003 — token-economy native vs. bespoke boundary** (Primitive F). Files which native `/usage` and `/cost` categories steward adopts into its own rollups vs. which remain native-surfaced only.
14. **ADR 004 — hook migration boundary** (Primitive E). Files which existing custom hooks migrate to native lifecycle subscriptions, which migrate to conditional-hook scope, which migrate to HTTP hooks, and which stay bespoke.
15. **ADR 005 — `/autofix-pr` evaluation** (Primitive C/E). Files which parts of the bespoke `scripts/internal/review_driver.py` overlap with native `/autofix-pr`; documents what stays bespoke (steward-specific semantics) vs. what could migrate.
16. **ADR 006 — Auto mode codification** (Primitive G/B). Documents the user-scope `autoMode.environment` configuration the fleet currently runs under (per `.claude/rules/80_permission_model.md`); records the trust-envelope content; specifies refresh cadence.
17. **`knowledge/external_signal_sources.md` initial content.** Operator-curated list of sources for the changelog review skill beyond the official changelog (Anthropic team posts, davidad-style commentary, community digests). Seed with at least the Boris Cherny Opus 4.7 thread + davidad `--system-prompt-file` thread.

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
**Re-evaluation needed in Phase 3:** [one sentence with recommended evaluation window if "insufficient evidence" applies, or "no"]
**Surprise finding:** [one sentence if any, or "none"]
**Disposition:** open | incorporated | superseded | rejected
```

Five content prompts (four primary axes + Phase 3 re-evaluation per G4)
plus one disposition status line. No tag taxonomy; the prompts
themselves carry the decision-axis routing. The 5th prompt (G4
addition) represents the "insufficient evidence" class introduced by
the §11 soft re-evaluation trigger; without it, the §15 schema would be
asymmetric to §11 and Phase 2 reviewers would have to manually
reconstruct the third class from Surprise findings.

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
- **Re-evaluation decisions (5th bucket, draft 7 G4 fix):** all entries with non-"no" Re-evaluation needed in Phase 3 prompts. These represent primitives flagged "insufficient evidence" per §11 soft re-evaluation trigger. Phase 2 produces a Phase 3 evaluation window for each.
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

## 16. Delta From Draft 7

Recording what changed relative to draft 7 (analyst-d findings + external-analyst change set + plugin-ecosystem integration + operator meta-directives):

**Analyst-d G6–G13 + Q5–Q8 applied.** 21 additional ops modules catalogued in `rework_spec.md` §3; hook catalog file-level for 34 files; `worktrees.py` registry-state preservation named; changelog source list trimmed (wayback best-effort) + extended (GitHub release notes, docs.anthropic.com blog); skill count reconciled to 38 (6 missing added); monitoring/playtest consolidation reframed to "deduplicate helpers, preserve surfaces"; B.9 G10 relationship to `.claude/agents/` clarified via ADR at kickoff; `.claude/agents/` catalogued in sub-plan; 19→8 archetype mapping as Primitive G first-deliverable sub-sub-plan; §10.9 Patterns 7 (Reversibility-as-default) and 8 (Observable-by-default) added; `plans/sessions/` 264-file sweep becomes `sweep_session_plans.py` script.

**Surprise finding elevated to Pattern 9** — Load-bearing-ownership lint codified per analyst-d's observation that load-bearing-but-floating recurred 3× across reviews (F6 / G1 / G6). Enforcement via `agent_readability_lint.py` extension scans plan/sub-plan cross-references.

**External-analyst change set applied** — Goal 1 mechanism expansion (packet shaping / routing / review / skill-selection / prompt-policy generation); B.11 orchestration recipe archive; B.12 improvement-mechanism evaluation; improvement-quality metrics family (Phase 1 Validation rows under B); §6.4 11th preflight item (repeat-task improvement probe); §12 overfitting risk; KB extended to store orchestration patterns; archivist extended to extract orchestration insights; Chrome-native steward control in Primitive G; §1 Decision reframed as "governed self-improvement loop inside a project cell."

**Plugin-ecosystem integration** — §10.9 Pattern 2 extended to three-tier native preference (native → official plugin → third-party plugin → bespoke); ADRs specified: 007 (melodic-software/claude-code-observability), 010 (new — doobidoo/mcp-memory-service), expanded 005 (official code-review plugin + `/autofix-pr`), B.8 (Agent Teams + TeammateTool + Task system); plugin registry sources added to `external_signal_sources.md`; plugin source evaluation dispatched in parallel (packet `a0cb1ca3a256` → `plans/steward_platform/plugin_source_evaluation.md`); findings fold as follow-up commit post-promotion.

**Q5-Q8 resolutions:** ADR 002 moved to Phase 0 close; `/loop 3d` cadence configurable; digest glob spec verified for single-file shape audits; §6.1 adds browser_game_expansion cross-reference.

**Counts after draft 8:**
- Goals: 16 (unchanged; #1 expanded in scope to mechanism-level, not count change)
- Primitives: 8 total / 7 Phase 0 / 1 Phase 1 (unchanged)
- B sub-deliverables: B.1–B.12 (was B.1–B.10 in draft 7; added B.11 orchestration recipe + B.12 improvement-mechanism evaluation)
- §10.9 Patterns: 9 (was 6 in draft 7; added Patterns 7/8/9)
- §6.4 Preflight items: 11 (was 10 in draft 7)
- §12 Risks: added 2 rows (overfitting; plugin-ecosystem adoption risks)
- Success criteria: 20 (unchanged count; SC #19/#20 preserved from draft 7)
- Open items: extended with G10 ADR requirement + ADR 010 + Phase 0 close re-scheduling

No primitives added or removed. No phases added or removed. Plan got
sharper on self-improvement mechanism discipline, agent-first
enforcement (Pattern 9), and plugin-ecosystem framing. Goal count
remains 16.

---

## 17. Delta From Draft 6

Recording what changed relative to draft 6:

- **All 5 analyst-c gap findings (G1-G5) plus operator directive applied:** G1 (lint script under Primitive C); G3 (cohesion justification §5-C); G4 (5th prompt in §15.2 schema for Re-evaluation needed in Phase 3); G5 (§13 renumbered, no duplicates); Q3 (§11-H clarified — post-hoc scenario selection happens during Phase 1, not at end). G2 fully resolved by clock-time mechanism removal (no `Slice elapsed:` requirement → no enforcement asymmetry to fix).
- **Clock-time mechanism removed per operator directive.** Draft 6 §3 + §4.1 + §4.4 step 5 + §13 SC #18 + §11 two-signal table all reduced to intent-only language. Time is diagnostic post-hoc (git history), not a write-discipline obligation. §11 soft re-evaluation trigger simplified to single-signal (activity volume only).
- **Tier S × system-rework integration into primitives.** Per-primitive native-substrate adoption: Primitive A (Monitor + lifecycle hooks + conditional hooks + HTTP hooks + session metadata + recaps); Primitive B (B.8 native task system evaluation; B.9 `--system-prompt-file`; B.10 effort-level configuration); Primitive C (shared project memory + auto memory supplementary + plugin PATH + tool-search + agent_readability_lint.py); Primitive D (changelog review skill + native lifecycle hook inputs); Primitive E (conditional hooks + TeammateIdle + StopFailure + HTTP hooks + channels improvements); Primitive F (`/usage` + `/cost` + read-tool reductions + per-tool MCP override); Primitive G (worktree migration + Setup hook + remote sessions + heartbeat retirement + `/fewer-permission-prompts` periodic + skills consolidation pass); Primitive H (Monitor for replay + verification pattern). Materially shifts Primitive G scope from "bespoke refactor" to "native migration."
- **§4.2 audit format gains 9th item:** "Native Claude Code adoption state."
- **§10.9 Extensibility patterns added:** six cross-cutting patterns codified — adapter contract; native-substrate-first defaults; hook taxonomy; skill family discipline; plan template enforcement; per-surface owner.
- **§15.3 new tag `native-substrate-signal`** for changelog-review-skill ledger entries.
- **§13 Success criteria expanded** with #19 (changelog scan produces signal) and #20 (≥1 native-substrate adoption lands during Phase 0/1). G5 renumber resolves draft 6 duplicate item.
- **§14 Open items expanded** with ADRs 002-006 (review-cycle-as-evidence; token-economy native boundary; hook migration boundary; `/autofix-pr` evaluation; Auto mode codification) and `external_signal_sources.md` initial content.
- **Changelog review skill scope extended** beyond official changelog to operator-curated sources (Boris Cherny tweets, davidad commentary, community digests) via `knowledge/external_signal_sources.md`.
- **New companion artifacts:**
  - `plans/steward_platform/claude_code_changelog_implications.md` — addendum reference (Tier S inventory; plan-tier vs. system-rework-tier; per-system rework specs; changelog review skill spec; latest-scan-date).
  - `plans/steward_platform/0_hardening/sub/rework_spec.md` — per-surface tactical analysis sub-plan (every existing ops module / hook / script / skill catalogued with disposition: keep / modify / consolidate / trim / delete).

No primitives added or removed. No phases added or removed. Plan got
sharper on native-substrate adoption discipline and extensibility
codification. Goal count remains 16. Primitive count remains 8 total /
7 Phase 0.

---

## 18. Delta From Draft 5

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

## 19. Delta From Draft 4

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

## 20. Delta From Draft 3 (preserved for lineage)

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

**Portability readiness:** no change (plan itself is pre-execution; Phase 2 inputs begin accruing once Phase 0 work opens; parallel Fund + RIN-SnD shape audits per §4.2 will be the first portability-tagged entries; native Claude Code adoption state — new §4.2 audit item — is itself a portability signal).
**Meta-layer need:** no change (deferred to Phase 2 decision gate by design).
**Kill signal for primitive(s) named:** N/A (no primitive execution yet).
**Re-evaluation needed in Phase 3:** no (plan itself is pre-execution).
**Re-evaluation needed in Phase 3:** no (plan itself is pre-execution; Re-evaluation prompts will accrue post-Phase-0 kickoff).
**Surprise finding:** The review → revision cycle across drafts 1→8 (draft 1 → analyst-a B → drafts 2-4 → analyst-b B+ → draft 5 → operator directives → draft 6 → analyst-c A- → draft 7 → analyst-d A + two-track gap analysis → draft 8 with G6-G13 + external-analyst change set + plugin-ecosystem integration + §10.9 Patterns 7-9) is itself a demonstration of the Phase 2 Decision Inputs pattern, the agent-readability theme (goal #16), the hybrid subsections+digest mechanism, the changelog-review-skill pattern (operator-fed external signals integrated into plan revision), the three-tier native-substrate preference (Pattern 2 extended), the load-bearing-ownership lint (Pattern 9 derived from 3-review recurrence), AND the extensibility patterns generally — all working in miniature. Four reviews by four different analysts each produced distinct gap classes; each review's findings informed the next draft scope. The draft 1→8 lineage itself argues for the A-grade evidence that the infrastructure pattern (§15.8 durability framing, §10.8 agent-first framing, §10.9 extensibility patterns) holds under adversarial review. Worth reflecting in ADR 002 (Open Item #12; moved to Phase 0 close per Q5) as the empirical evidence base.
**Disposition:** open
