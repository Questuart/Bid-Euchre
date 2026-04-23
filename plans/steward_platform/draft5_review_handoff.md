# Handoff: Steward Platform Governing Plan — Review of Draft 5

**Date:** 2026-04-22
**From:** orchestrator (co-drafted with operator)
**To:** steward-analyst (lane analyst-b — fresh eyes; analyst-a reviewed draft 2 and has been recused from this pass to get an orthogonal second opinion)
**Review target:** `plans/steward_platform/governing_plan.draft5.md`
**Review stance:** skeptical; prefer simpler solutions; flag over-engineering; propose better alternatives; judge against the *best plausible plan* standard, not the *workable plan* standard. Fixed constraints listed below should not be re-litigated without load-bearing reason.

---

## Prior lineage (context you should skim, not re-derive)

The plan has iterated through five drafts. Each draft's file exists in
`plans/steward_platform/`:

- `governing_plan.md` — draft 1 (operator's original). **Do not edit.** Preserved for diffing.
- `governing_plan.draft2.md` — first orchestrator revision after initial reviewer critique.
- `governing_plan.draft3.md` — second orchestrator revision with readiness/validation split.
- `governing_plan.draft4.md` — third orchestrator revision incorporating analyst-a's full 806-line review of draft 2.
- `governing_plan.draft5.md` — **current, under review.** Adopts analyst-a §3.3 Option A and adds seven operator-proposed scope extensions.

Supporting artifacts in the same directory:
- `draft2_review_handoff.md` — original handoff that produced analyst-a's review.
- `draft2_review_analyst-a.md` — analyst-a's 806-line review.
- `post_phase2_sidecar.md` — deferred-ideas parking lot (cross-project meta, cmux, etc.).
- `phase2_harness_engineering_research.md` — borrowed-practices memo sourced from OpenAI/Anthropic/LangGraph/Thoughtworks.
- `draft5_review_handoff.md` — this document.

## Core trajectory (compressed so you don't have to reconstruct it)

1. Draft 1 proposed a multi-project Claude-Code-native platform with a meta-orchestrator. Critiqued as conflating operator-UX pain with portability pain; falsification test deferred to Phase 4; ~12 new primitives.
2. Operator clarified the two pains are related via cross-project allocation but agreed to sequence: prove before port.
3. Draft 2 narrowed to Bid-Euchre only with 8 primitives and introduced a readiness/validation split. Analyst-a's 806-line review gave it a **B**, approve with revisions, with 11 specific findings.
4. Draft 3 applied analyst-a's structural fixes (readiness/validation split, preflight insertion, baseline capture, ledger schema upgrade).
5. Operator approved a "hybrid" pattern for Phase 2 decision capture: structured subsections embedded in every primitive closeout + auto-generated digest, not a standalone ledger.
6. Draft 4 landed that hybrid plus most analyst-a findings, and explicitly framed the Phase 2 decision-input pattern as durable infrastructure for future governing plans.
7. Analyst-a's full review (which had been paste-summarized to orchestrator at first, then read in full) proposed **deferring Primitive H from Phase 0 to Phase 1 (§3.3 Option A)**. Operator clarified that "pre-Phase-2" was the real constraint and accepted the deferral. Operator additionally proposed seven scope extensions from `phase2_harness_engineering_research.md`.
8. Draft 5 adopts both — Primitive H as a Phase 1 primitive and the seven scope extensions.

## What changed draft 4 → draft 5 (the delta under review)

Two tracks of change:

**Track 1 — Primitive H deferred to Phase 1:**
- Phase 0 now has 7 primitives (A-G) at readiness; Phase 1 adds Primitive H concurrent with the proving run.
- Rollback validation for Phase 0 changes stays inside Primitive G (absorbs Goal #13's Phase 0 slice); Primitive H picks up rollback for Phase 1 changes.
- Preflight (§6.4) loses the replay-harness checklist item (H doesn't exist at preflight time) and gains an agent-legibility scorecard item (from Primitive C). Preflight remains a 10-item gate.
- §10.7 design coupling: Phase 2 cannot commit to portability unless Primitive H has completed its Phase 1 Validation. Two fallback options stated if H fails or is demoted.
- §7 Phase 1 restructured to describe two concurrent tracks: Track A (proving run) + Track B (H buildout).

**Track 2 — Seven scope extensions:**

| Extension | Home | Brief |
|---|---|---|
| Harness assumptions register | Primitive C (6th KB artifact) | `knowledge/harness_assumptions.md` — live list of current harness assumptions likely to go stale as models improve |
| Canary task suite | Primitive H (Phase 1) | 3-5 canonical steward tasks rerun after major prompt-policy / routing / messaging changes |
| Tool risk registry + approval classes | Primitive B | `.claude/rules/tool_risk_registry.md` mapping task-types to approval modes (direct / approve / edit / reject) |
| Agent legibility scorecard | Primitive C + preflight | 10-item checklist measuring whether the repo is navigable by agents |
| Entropy / garbage-collection report | Primitive D | Second archivist output (symmetric to candidate-lessons) for stale KB entries, dead skills, obsolete policies |
| Prompt-policy change discipline | Primitive B | Each policy change records trigger + expected effect + rollback condition as structured commit-message fields |
| Idempotency checklist for side effects | Primitive H | Required PR-review item for replay/interrupt-sensitive operations |

Kill criteria updated to cover the new capabilities. Success criteria
expanded from 13 to 17 items. §16 Delta From Draft 4 documents the
changes.

## What you are asked to do

Review draft 5 as a proposed successor to draft 4 under the same review
stance.

Priority review asks:

1. **Phase 0 / Phase 1 partition soundness.** Draft 5 puts 7 primitives in Phase 0 and Primitive H in Phase 1. Is the partition clean? Does Phase 1's "dual track" framing (§7) hold up, or does the proving run and H buildout create hidden ordering dependencies (e.g., H's replay capture needs the event schema's Phase 0 form to match Phase 1 emission exactly)?

2. **Seven scope extensions net effect.** Each extension is individually defensible; collectively, are they proportional, or has Primitive B / C / D / H quietly become too heavy? If you would defer any extension, name it and argue for it specifically.

3. **Kill-criteria integrity.** Draft 5 kill criteria (§11) now cover the new capabilities (approval-class violations, harness-assumptions refresh, GC acceptance, canary running). Are any self-sympathetic per the standard analyst-a applied in draft 2? Are any *over*-strict in a way that would trigger false negatives?

4. **Does deferring H to Phase 1 introduce new problems?** Specifically: preflight can no longer gate on replay; the cascade-risk note from draft 4 may need sharpening; the §10.7 design coupling now has to carry more weight because H's Phase 1 Validation is the Phase-2-portability-gate-gate.

5. **Success criteria, Phase 2 decision-input discipline, and ledger pattern.** Draft 5 inherits draft 4's hybrid subsections + digest pattern. Is the enforcement (template in `plans/_templates/`, digest script at `scripts/internal/compile_decision_inputs.py`, nightly missing-subsection report) sufficient to keep the pattern durable?

6. **Anything new that wasn't on the table for draft 2-4.** Fresh-eyes findings the prior reviewer missed.

7. **Promotion readiness.** If draft 5 addresses your findings, could it be renamed to `governing_plan.md` and adopted as canonical, with drafts 1-4 archived? Or does it need further revision first?

## Fixed constraints (do not relitigate without load-bearing reason)

- **Horizontal scope:** 1 repo (Bid-Euchre) in Phases 0 + 1. Fund + RIN-SnD port is a Phase 2 decision-gate output.
- **Vertical ambition:** 15 capabilities in §2 are the floor; no cuts.
- **Proving-run framing:** prove before port, research run validates platform before portability.
- **Primitive H in Phase 1, not Phase 0:** operator-confirmed. Do not relocate H back to Phase 0 unless you have a specific new argument not made by analyst-a already.
- **Seven scope extensions:** operator-confirmed. Do not recommend removing them unless you have a specific new argument.
- **Subsections + digest hybrid pattern for Phase 2 decision capture:** operator-confirmed. Do not propose a ledger-only or subsection-only alternative.
- **Meta-layer, cmux, meta-steward-home:** not in Phase 0/1. Phase 2 decision outputs.

## Up for challenge

- Kill-criteria thresholds (§11). All first-cut.
- Phase 1 dual-track framing (§7). Novel structure; may have integration gaps.
- Preflight item-10 swap (replay → legibility). May need different replacement.
- Within-primitive weight distribution (B and H are getting heavy).
- Success criteria count (17 items). May be too granular or not granular enough.
- §15 hybrid pattern's enforcement mechanics.
- Phase 2 design coupling (§10.7) wording after the H deferral.

## Deliverables

- **Per-finding disposition** of analyst-a's draft 2 findings against draft 5 (resolved / partial / missed / obviated).
- **New findings** introduced by draft 4 → draft 5 delta.
- **Concrete revision proposals** with replacement text in a fenced block (not just direction).
- **Updated grade and recommendation** in absolute terms. Default scale: A / A- / B+ / B / B- / C+ / C / below. Current draft 4 was graded B by analyst-a.
- **Adoption recommendation:** if draft 5 is promotion-ready, say so; if not, specify blockers and priority.
- **Open questions** back to orchestrator / operator.
- **Written artifact** at `plans/steward_platform/draft5_review_analyst-b.md`.

## Mechanics

- **Write scope:** `plans/steward_platform/` for the review artifact; do not edit the five draft plan files directly.
- **Preservation:** drafts 1-5 all remain unchanged after your review.
- **Time expectation:** depth over speed; 2-4 hours of focused work is appropriate.
- **Escalation:** if you find a blocker or decision point needing operator input, message the orchestrator with a concrete question rather than stalling.
- **Task packet ID:** will be assigned at dispatch and included in your inbox message.

Take the stance that the plan should be the *best plausible plan* for
the steward platform's intended future, not merely a workable one.
