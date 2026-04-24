# ADR 001 — Platform Pattern Reset: Platform-11/13 Dismissal + Agent-Readability Scorecard Floor

**Status:** SEEDED at Phase 0 kickoff (filing at Phase 0 kickoff per §4.5 + §5-C preconditions)
**Primitive:** Meta (cross-cutting; binds to B, C, G)
**Supersedes:** `agent_ops` Phase 5 `Platform-11` (Skill Learning Loop) and `Platform-13` (Second-Project Validation), both POSTPONED INDEFINITELY 2026-04-01
**Seed source:**
- `plans/steward_platform/governing_plan.md` §4.5 + §5-C + §12 Risks row 6 (all reference `knowledge/adr/001-platform-pattern-reset.md`)
- `plans/agent_ops/5_skill_learning/scope_lock.md` (Platform-11 scope + postponement)
- `plans/agent_ops/5_extraction/scope_lock.md` (Platform-13 scope + postponement)
- `plans/agent_ops/governing_plan.md` §3, §7, §11 (phase boundaries, ordering, task definitions)
- `MEMORY.md` session 2026-04-01 — operator decision on postponement
- `MEMORY.md` session 2026-04-22c → 2026-04-23 — draft 8 promotion that supersedes the Phase-5/6 framing

**Location caveat.** The governing plan references this ADR's canonical home as `knowledge/adr/001-platform-pattern-reset.md` under Primitive C. That path does not yet exist — Primitive C builds `knowledge/adr/` at Phase 0 (§5-C Readiness). This file is seeded at `plans/steward_platform/adrs/001-platform-reset.md` alongside ADRs 005 / 007 / 010 / B8 (which followed the same pattern per `adrs/README.md`) and will migrate to `knowledge/adr/001-platform-pattern-reset.md` at Phase 0 close (or earlier if the KB skeleton lands first). Cross-references inside the governing plan remain stable because both paths resolve to the same content under the promotion path.

---

## Context

The steward platform's predecessor — the `agent_ops` initiative — scoped two phases past Phase 4 (`4_remote_channel`, completed 2026-04-01):

- **Phase 5 — Portability and Learning.** Contained `Platform-10` (core-vs-adapter split) and `Platform-11` (Skill Learning Loop).
- **Phase 6 — Second-Model and Validation.** Contained `Platform-12` (Cross-Model Review) and `Platform-13` (Second-Project Validation / Extraction Proof).

Both phases were postponed indefinitely on 2026-04-01 when the operator redirected focus to the browser-game product. The two scope_lock files (`plans/agent_ops/5_skill_learning/scope_lock.md`, `plans/agent_ops/5_extraction/scope_lock.md`) carry matching **POSTPONED INDEFINITELY** banners and have not been amended since. `plans/agent_ops/governing_plan.md` §3 states: *"Phase 5 (`5_portability_and_learning`) — **POSTPONED INDEFINITELY**. 2026-04-01: Operator decision — platform work postponed indefinitely to focus on browser game product. Phase 4 was the final delivered platform phase. All Phase 5+ scope locks and sub-plans marked POSTPONED."*

The steward platform initiative (governing plan at `plans/steward_platform/governing_plan.md`, promoted from draft 8) was drafted across 8 iterations + 4 analyst reviews + 1 plugin source-evaluation between 2026-04-22 and 2026-04-23 (see MEMORY.md session block for lineage). Draft 8 restructures platform work into 8 primitives (A-H), with Phase 0 hardening + Phase 1 proving run as the immediate deliverable. The 8-primitive structure is not a continuation of the `Platform-1 … Platform-14` numbering — it is a reset.

**This ADR codifies three linked decisions at Phase 0 kickoff:**

1. Platform-11 (Skill Learning Loop) is dismissed from active scope as a stand-alone initiative; its intended scope is absorbed into draft 8 Primitive B (specifically B.2 Skill promotion loop and B.12 Improvement-mechanism evaluation, with adaptive-dispatch closeout explicitly named in Primitive G Work).
2. Platform-13 (Second-Project Validation / Extraction Proof) is dismissed from active scope as a stand-alone initiative; its intended scope is absorbed into draft 8 Primitive G (existing-debt closeout + native-substrate migration) plus the Phase 2 portability decision gate.
3. The agent-readability scorecard (10 rows, defined in §5-C) has its initial Phase 0 **floor set at 7/10 rows passing**. Sub-plans under Primitive C may tighten the floor to 8/10 or 9/10 but may not loosen it below 7/10. The scorecard is re-scored at end of Phase 0 (preflight item 8 sub-criterion) and end of Phase 1.

## Decision

### D1 — Platform-11 (Skill Learning Loop) is dismissed from active scope and superseded

**Original scope (from `plans/agent_ops/5_skill_learning/scope_lock.md`):**
- Task outcome records (enriched taxonomy, complexity, token economy fields)
- Lane affinity model (per-lane × task-type statistics)
- Adaptive dispatch heuristics (EWMA, complexity-controlled scoring, exploration policy)
- Skill suggestion pipeline (evidence-based candidate extraction, review-gated promotion)
- Anti-corruption guardrails (advisory-only, skew monitoring, operator overrides)
- Evaluation framework (matched-cohort design, statistical activation criteria)

**Supersession path:**

| Platform-11 element | Superseded by (draft 8) |
|---|---|
| Skill suggestion pipeline | **B.2** — Skill promotion loop (Primitive B sub-deliverable; Phase 0 Readiness wires candidate-generation surfaces; Phase 1 Validation measures promoted-skill citation) |
| Adaptive dispatch heuristics | **Primitive G Work bullet** — "Platform-11 adaptive-dispatch closeout inside Primitive B or explicitly superseded" (§5-G) |
| Improvement-mechanism evaluation | **B.12** — Improvement-mechanism evaluation (Primitive B sub-deliverable; tracks metric deltas across rolling window; catches overfitting per §12 row "Improvement-loop overfitting") |
| Anti-corruption guardrails | **Primitive B + §11-B kill criteria** — advisory-only until validated; review-gate cannot be bypassed; rollback paths mandated per §10.9 Pattern 7 |
| Evaluation framework | **§11-B + §6.4 preflight item 11 (repeat-task improvement probe)** — matched-cohort measurement surface lives in the preflight checklist, not a dedicated Platform-11 deliverable |

**Dismissal is *not* a rejection of the work.** The operator already partially reactivated Platform-11 on 2026-04-20 (see MEMORY.md session 2026-04-21c block) for the adaptive-dispatch subset, absorbed into slices C/D/E of `plans/sessions/2026-04-20_token_economy_restart_plan.md`. That absorbed subset shipped as PRs #2694, #2715, #2721, #2725 during session 2026-04-21c. The remaining Platform-11 scope (skill suggestion pipeline, full learning-loop framing) is superseded by the draft-8 Primitive B structure — not deferred.

### D2 — Platform-13 (Second-Project Validation / Extraction Proof) is dismissed from active scope and superseded

**Original scope (from `plans/agent_ops/5_extraction/scope_lock.md`):**
- Core-vs-adapter split validation via second-project boot
- Hello-steward synthetic proof project (smoke)
- RIN balance sheet real-project proof (full, including failure cases)
- Outside-validation via GitHub download by a third party
- Adapter contract + translation-layer specification
- Multi-repo runtime isolation requirements

**Supersession path:**

| Platform-13 element | Superseded by (draft 8) |
|---|---|
| Core-vs-adapter split (Platform-10 dependency) | **Primitive G** — existing-debt closeout + native-substrate migration. Platform-10 already landed (see `MEMORY.md`: "Platform-10 COMPLETE 2026-04-14"); Primitive G absorbs the remaining portability debt (42 ops modules + 34 hooks + 38 skills catalogued in `plans/steward_platform/0_hardening/sub/rework_spec.md`) |
| Adapter contract + translation layer | **Phase 2 portability decision gate** — §3 table row 2: "decide portability scope, meta-layer shape, and next-wave ambitions." Adapter contract is a Phase 2 *decision* output, not a Phase 0/1 *construction* deliverable |
| Second-project boot proof (hello-steward, RIN) | **Phase 2 portability scope decision** — §4.2 shape audits (2-3 days per candidate repo, 8-item output) keep the option warm at low cost; full extraction deferred to Phase 3 scope as determined by Phase 2 |
| Multi-repo runtime isolation | **§10.7 Primitive H design coupling + Primitive G Tier A scope** — portability readiness is verified via replay harness (Primitive H) + portability manifest (Primitive G); the "explicit `repo_root` parameter" and "no reliance on `cwd`" constraints are absorbed into the rework spec |
| Failure-case proving (1 failed test cycle, 1 rejected PR, 1 retry loop) | **Primitive H** — Reliability Lab, Replay Harness, Canary Suite. The adversarial coverage Platform-13 required for a "real" extraction claim is now a general-purpose reliability surface, not a one-shot extraction gate |

### D3 — Agent-readability scorecard floor set at 7/10 rows

The 10-row scorecard (defined in §5-C) is:

1. CLAUDE.md ≤ 200 lines
2. Single canonical entry point for new sessions
3. Active governing plan findable in ≤2 hops from repo root
4. All skills discoverable from `.claude/skills/`
5. Lane registry authoritative not inferred
6. MEMORY.md indexes rather than recaps
7. ADR index current
8. KB INDEX current
9. No orphan references in plans
10. Rule files grep-discoverable from CLAUDE.md

**Floor: ≥7/10 rows pass.** Sub-plans under Primitive C may tighten to 8/10 or 9/10 but may not loosen. Re-scored at end of Phase 0 and end of Phase 1. Rationale below under Consequences.

## Context captured

### Platform-11 dismissal evidence

- **Scope lock banner:** `plans/agent_ops/5_skill_learning/scope_lock.md` line 3 — *"POSTPONED INDEFINITELY (2026-04-01 operator decision — platform work postponed to focus on browser game product)"*.
- **Parent governing plan (agent_ops):** `plans/agent_ops/governing_plan.md` §3 phase status table line 111 — *"Phase 5 (`5_portability_and_learning`) — **POSTPONED INDEFINITELY**. 2026-04-01: Operator decision"*.
- **Partial reactivation evidence:** `MEMORY.md` session 2026-04-21c block — *"Platform-11 partially reactivated 2026-04-20 (adaptive dispatch subset only); absorbs Slices C/D/E of `plans/sessions/2026-04-20_token_economy_restart_plan.md`. PR5 (skill suggestion pipeline) stays POSTPONED until dispatch advisor validated"*. Token-economy PRs #2694/#2715/#2721/#2725 shipped the absorbed subset.
- **Draft 8 absorption:** `plans/steward_platform/governing_plan.md` §5-G Primitive G Work — *"Platform-11 adaptive-dispatch closeout inside Primitive B or explicitly superseded"*. §5-B Primitive B deliverables B.2 (Skill promotion loop) and B.12 (Improvement-mechanism evaluation) carry the intended skill-learning scope forward.

### Platform-13 dismissal evidence

- **Scope lock banner:** `plans/agent_ops/5_extraction/scope_lock.md` line 3 — *"POSTPONED INDEFINITELY (2026-04-01 operator decision)"*.
- **Parent governing plan (agent_ops):** same §3 phase status line as Platform-11 (both live under Phase 5+; all Phase 5+ scope locks marked POSTPONED).
- **Platform-10 prerequisite satisfied:** `MEMORY.md` Governing Plans table — *"Platform-10 COMPLETE 2026-04-14"*. The core-vs-adapter split that Platform-13 was designed to validate is already in place. Absent further operator mandate, the remaining extraction-proof scope is Phase 2 decision-gate material, not standing Phase 0/1 work.
- **Draft 8 absorption:** `plans/steward_platform/governing_plan.md` §5-G Primitive G Work catalogues the 42 ops modules + 34 hooks + 38 skills needing native-substrate rework under `plans/steward_platform/0_hardening/sub/rework_spec.md`. §3 Phase 2 row — *"decide portability scope"* — absorbs the adapter-contract + second-project-boot decision into the Phase 2 gate.

### Conditions that have since lifted

Per §12 Risks row 6 of the steward platform governing plan: *"Operator has confirmed constraints that paused earlier attempts no longer apply."* The specific constraints identified:

1. **Browser-game product urgency has relaxed.** The 2026-04-01 postponement was driven by the operator's decision to prioritize the browser-game product (plans/browser_game/governing_plan.md — COMPLETE per `MEMORY.md`). Browser Phase 5 closeout (PR #1655, 2026-03-24d session) + browser-game expansion kickoff (`plans/browser_game_expansion/governing_plan.md` ACTIVE) demonstrate that the browser-game workstream is running with its own dedicated lane pool (brws-author-a/b/c/d) and no longer requires the full fleet's attention.
2. **Platform-10 has landed.** The core-vs-adapter split (Platform-13's technical dependency) completed 2026-04-14. The "is the boundary real?" question can now be answered via audit (shape audits, rework spec) rather than requiring a full second-project boot at Phase 0.
3. **Adaptive-dispatch proof-of-concept already shipped.** Session 2026-04-21c landed the adaptive-dispatch subset of Platform-11 as PRs #2694/#2715/#2721/#2725. The "does outcome-informed dispatch work at all?" question has partial evidence already. Full skill-suggestion pipeline remains deferred, but the MVP path is validated.

**Recurrence trigger.** If the postponement pattern recurs in Phase 0 — i.e., if operator availability, product priority, or substrate instability forces a second pause on the steward platform initiative — this ADR is reopened (new superseding ADR filed) and Phase 0 is recast before continuing (§12 Risks row 6 mitigation).

### Agent-readability scorecard floor rationale

The floor of **7/10** is derived from analyst-d's draft 7 review recommendation (see `plans/steward_platform/draft7_review_analyst-d.md` and the draft 7 → 8 revision drivers summary in `governing_plan.md` lines 20-54):

- **Below aspirational but above minimum-viable.** A 9/10 floor would block Phase 0 kickoff on cleanup work (e.g., orphan references from the plans/sessions 264-file sweep that Primitive G is explicitly scoped to resolve). A 5/10 floor would not materially improve agent navigability.
- **Operational anchor for goal #16.** Goal #16 (agent-first plan and KB design, added in draft 8) requires a measurable readiness threshold. 7/10 establishes a quantitative anchor that preflight item 8 (§6.4) and Phase 1 Validation can reference without forcing interpretation at measurement time.
- **Tightening allowed, loosening prohibited.** Sub-plans under Primitive C may set 8/10 or 9/10 for their own local deliverable (e.g., KB skeleton sub-plan could require 9/10 after the `plans/sessions/` sweep lands) but must never set a value below 7/10.

**Scorecard lifecycle:**

| Milestone | Expected action |
|---|---|
| Phase 0 kickoff | ADR 001 filed (this file); initial scorecard committed with baseline reading |
| Phase 0 Readiness | Scorecard re-run; ≥7/10 rows pass; result recorded in `knowledge/agent_readability_scorecard.md` |
| Phase 1a preflight item 8 | Scorecard re-run as sub-criterion; result fed into preflight pass/fail |
| End of Phase 1 | Scorecard re-run; score ≥ Phase 0 baseline AND ≥ floor recorded in this ADR |
| Phase 2 decision gate | Scorecard + floor passed forward into portability/meta-layer decisions as supporting evidence (not as a gate itself) |

## Consequences

### Positive

1. **Scope clarity for Phase 0.** Platform-11 and Platform-13 are no longer "looming open phases." They are named, dismissed, and re-absorbed into the 8-primitive structure. Future operators and agents reading the governing plan see a single active initiative, not a paused-phase backlog.
2. **`agent_ops` plan fragmentation resolved.** The `plans/agent_ops/5_*` subtrees have explicit resolution (superseded by named primitives). This closes the pattern of "POSTPONED sub-plans accumulating without supersession evidence" that the draft 8 §5-G Primitive G Work was designed to address.
3. **Agent-readability floor becomes a Phase 0 gate input.** Preflight item 8 (§6.4) has a numeric threshold to check against — not a subjective judgement call.
4. **Phase 2 decision surface is better bounded.** Portability scope (Platform-13 intent) and improvement-mechanism scope (Platform-11 intent) are routed to the Phase 2 gate via the decision-inputs digest (§15), not via ad-hoc phase revival.

### Negative / risks

1. **Supersession is claim, not proof.** This ADR asserts that B.2 + B.12 + Primitive G + Phase 2 gate together cover the intended scope of Platform-11 and Platform-13. The proof is the Phase 1 proving run; until then, the supersession is a design commitment. Mitigation: **Phase 3 re-evaluation trigger** (below).
2. **Floor may anchor too low.** 7/10 is a Phase 0 threshold; if Phase 1 finishes with exactly 7/10, the platform has made no progress on agent-readability during Phase 1. Mitigation: Phase 1 Validation criterion under §5-C requires *"score is equal to or better than Phase 0 baseline"* — so ratchet is explicit, not just "≥ floor."
3. **Scope recovery cost if dismissal is wrong.** If Platform-11's skill suggestion pipeline turns out to be needed in Phase 1 and B.2 doesn't cover it, recovery requires new scope-lock work. Mitigation: B.12 (Improvement-mechanism evaluation) monitors this exact gap; if it produces a kill signal (§11-B), Phase 2 Decision Inputs escalate the finding.

### Re-evaluation trigger (Phase 3)

Re-evaluation is required in Phase 3 if **any** of the following conditions holds at Phase 2:

1. **Skill promotion evidence thin.** B.2 and B.12 have produced <3 promoted skills or skill-suggestion PRs citing learning-loop evidence during the proving run (§11-B kill-adjacent criterion).
2. **Portability decision deferred without decision.** Phase 2 decision gate on portability is marked "insufficient evidence" rather than producing a go/no-go with evidence link.
3. **Adaptive dispatch regresses.** The adaptive-dispatch subset shipped in session 2026-04-21c produces a negative signal in Primitive F token-economy metrics during the proving run — indicating the Platform-11-adjacent work needs a reset, not just a closeout.
4. **Agent-readability scorecard stalls.** Phase 1 end score is exactly equal to Phase 0 baseline — no ratchet — AND no sub-plan has attempted to tighten the floor. Indicates write-discipline decay.

If Phase 3 re-evaluation is required, this ADR is marked `superseded` via a new ADR that cites the specific trigger(s) fired and proposes either (a) revival of Platform-11 / Platform-13 scope as a new primitive, or (b) explicit acceptance of the gap with a documented cost rationale.

## Alternatives considered

1. **Leave Platform-11 and Platform-13 open as future-phase commitments.** Rejected. The draft-8 8-primitive structure is not a continuation of the Platform-N numbering; leaving both phases open creates a governance ambiguity about whether the steward platform is the active initiative or a Phase-5 parallel effort. The dismissal is load-bearing: it collapses two initiative numbering systems into one.
2. **Revive Platform-11 and Platform-13 as Phase 0 work.** Rejected. Phase 0 is scoped to 7 primitives with a 1-2 week readiness target (§4). Reviving two Phase-5 sub-efforts at Phase 0 kickoff would blow the Phase 0 scope closed-list (§12 Risks row 1).
3. **Split dismissal ADRs — separate ADR 001a for Platform-11, 001b for Platform-13.** Rejected. The two dismissals share the same evidentiary basis (operator 2026-04-01 decision + draft 8 primitive absorption) and the same re-evaluation trigger (Phase 2 decision gate + Phase 1 proving-run evidence). Splitting would duplicate context without adding clarity.
4. **Set the agent-readability floor at 8/10 or 9/10.** Rejected for Phase 0. 8/10+ would require the `plans/sessions/` sweep (G12) to complete before preflight can pass; the sweep is Primitive G work that lands *during* Phase 0, not before. Locking the floor high creates a circular dependency (Phase 0 preflight blocks Phase 0 work). 7/10 can be met with current repo state plus modest pre-preflight hygiene.
5. **Set the floor at 5/10 or 6/10.** Rejected. Too permissive — does not create a meaningful readability ratchet, and makes the scorecard ceremonial rather than load-bearing.

## Open questions

1. **When exactly does Platform-11's full skill-suggestion pipeline reach supersession-is-final status?** Current disposition: superseded by B.2 + B.12, but PR5 (skill-suggestion pipeline portion) in `plans/sessions/2026-04-20_token_economy_restart_plan.md` remains POSTPONED explicitly "until dispatch advisor validated." If B.12 validates the dispatch advisor during Phase 1, is that sufficient to retire PR5 scope outright, or does operator re-review trigger a new scope lock? **Resolution:** Route to Phase 2 decision-inputs digest via B.12 Phase 1 Validation outcome.
2. **Does the agent-readability scorecard floor apply to `.claude/agents/` and `.claude/hooks/` in addition to `plans/**`, `knowledge/**`, `.claude/skills/**`?** §5-C describes 10 rows and lint coverage of `plans/`, `knowledge/`, and `.claude/skills/`. Rows 4 ("all skills discoverable") and 10 ("rule files grep-discoverable") already imply adjacent surfaces. **Resolution:** defer to Primitive G first-deliverable sub-plan (19-lane → 8-archetype mapping + `.claude/agents/` catalogue) — if that sub-plan expands scorecard coverage, record as a scorecard-schema ADR (not a modification of this one).
3. **Should Platform-13's "outside validation by third party" step (scope_lock step 3) be explicitly retired or carried forward as a Phase 3 ambition?** This ADR supersedes Platform-13 into the Phase 2 portability decision; the third-party-download validation was always a far-future step. **Resolution:** carry forward as a Phase 3 ambition only if Phase 2 decides "portability is a deliverable" rather than "portability is a property we protect in place."

## Source evidence

- **Steward platform governing plan:** `plans/steward_platform/governing_plan.md` — §4.5 (line 274), §5-C (lines 396-434), §12 Risks row 6 (line 1171), §10.9 Pattern references
- **Agent-ops governing plan:** `plans/agent_ops/governing_plan.md` — §3 Phase Status (lines 105-114), §7 Platform-11 definition (lines 1421-1429), §7 Platform-13 definition (lines 1470-1477)
- **Platform-11 scope lock:** `plans/agent_ops/5_skill_learning/scope_lock.md`
- **Platform-13 scope lock:** `plans/agent_ops/5_extraction/scope_lock.md`
- **Partial reactivation session handoff:** `MEMORY.md` session 2026-04-21c block (adaptive-dispatch PRs #2694/#2715/#2721/#2725)
- **Draft 8 promotion lineage:** `MEMORY.md` session 2026-04-22c → 2026-04-23 block (drafts 1-8 + 4 analyst reviews)
- **Analyst-d draft 7 review (source for 7/10 floor recommendation):** `plans/steward_platform/draft7_review_analyst-d.md`
- **Rework spec (Primitive G absorption surface):** `plans/steward_platform/0_hardening/sub/rework_spec.md`

## Phase 2 Decision Inputs

**Portability readiness:** Platform-13 was the prior initiative's extraction-proof path; dismissing it shifts the portability verification surface from "second-project boot" to "shape audits (§4.2) + rework-spec closeout (Primitive G) + Phase 2 decision gate." Portability readiness is measured at Phase 2 from the shape-audit outcomes and the Primitive G rework-spec completion — not from a hello-steward or RIN-SnD boot result.
**Meta-layer need:** no change. This ADR records dismissals of existing initiatives; it does not propose new meta-layer machinery. The §15 decision-inputs digest is the meta-layer surface that consumes this ADR's re-evaluation trigger.
**Kill signal for primitive(s) named:** no. This ADR pre-empts Phase 0 drift toward reviving Platform-11/13 as stand-alone work; it does not signal a kill on any of the 8 primitives (A-H). A kill signal on Primitive B or Primitive G would trigger a separate ADR.
**Re-evaluation needed in Phase 3:** yes — `RE-EVAL: Phase 3 conditional on Phase 1 proving-run evidence for (a) skill-promotion output volume (B.2 + B.12), (b) portability decision decisiveness (Phase 2 gate), (c) adaptive-dispatch regression signal (Primitive F metrics), or (d) agent-readability scorecard stall (Phase 1 end = Phase 0 baseline with no attempted ratchet).` Any single trigger fires this ADR's supersession path.
**Surprise finding:** The partial Platform-11 reactivation during session 2026-04-20 (adaptive-dispatch subset shipping as token-economy PRs) demonstrated that postponed initiatives can be revived piecewise without full scope-lock revival. This informs the supersession framing — Platform-11 and Platform-13 are not "frozen" but "redistributed across the active primitive set," and the redistribution surface is the draft 8 plan itself, not a new recovery process.
**Disposition:** open (pending Phase 0 kickoff filing confirmation by operator; transitions to `incorporated` once ADR 001 is referenced by the first committed Phase 0 Readiness checkpoint under Primitive C)
