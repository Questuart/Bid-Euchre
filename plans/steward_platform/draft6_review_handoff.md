# Handoff: Steward Platform Governing Plan — Narrow Review of Draft 6

**Date:** 2026-04-23
**From:** orchestrator (co-drafted with operator)
**To:** steward-analyst (lane TBD by orchestrator dispatch — fresh eyes preferred; both analyst-a and analyst-b have reviewed prior drafts)
**Review target:** `plans/steward_platform/governing_plan.draft6.md`
**Scope:** **Narrow**, not full-spectrum. Per analyst-b §4 recommendation, draft 6 is close enough to promotion-ready that a full review cycle would be over-investment. This review focuses on whether the F1-F13 fixes from analyst-b's draft-5 review landed correctly and introduced no new structural gaps.

---

## Prior lineage (skim, don't re-derive)

Six iterations: draft 1 (operator) → analyst-a review (graded B) → drafts 2/3/4 (orchestrator) → analyst-b review of draft 5 (graded B+) → operator directives → draft 6.

All drafts and reviews are committed to `plans/steward_platform/`:

- `governing_plan.md` — draft 1 (preserved)
- `governing_plan.draft2.md` — preserved
- `governing_plan.draft3.md` — preserved
- `governing_plan.draft4.md` — preserved
- `governing_plan.draft5.md` — preserved
- **`governing_plan.draft6.md` — under review now**
- `draft2_review_analyst-a.md` — analyst-a's review of draft 2
- `draft5_review_analyst-b.md` — analyst-b's review of draft 5
- `post_phase2_sidecar.md` — deferred ideas (companion artifact)
- `phase2_harness_engineering_research.md` — borrowed-practices memo (companion)

## What changed draft 5 → draft 6 (the delta under review)

**From analyst-b's review (F1-F13):**

| Finding | Disposition in draft 6 |
|---|---|
| F1 — Kill-criteria falsifiability under thin proving run | Adopted analyst-b's soft re-evaluation trigger; combined with operator-directed reinstatement of *relative clock-time tracking*, the trigger uses **two signals** (activity volume + relative elapsed time) to differentiate "primitive failed" / "insufficient evidence" / "primitive on track" / "scope completed but expensive." See §3 (definitions), §11 preamble. |
| F2 — Primitive D's GC half is Phase-0-labeled but Phase-1-substantive | Adopted: D's lessons inflow stays Phase 0; GC outflow split to Phase 1 (parallels Primitive H shape). Phase 0 readiness for D's outflow is "code path smoke-tested against seeded fake KB." |
| F3 — Primitive B weight | Operator chose **Option B**: keep B unified with a sub-deliverables table (B.1-B.7) mapping each deliverable to its own readiness/validation/kill mini-row. Primitive count stays at 8 total / 7 Phase 0. §11-B kill row split into row 1 (B.1/B.2/B.5) and row 2 (B.3/B.4/B.6/B.7). |
| F4 — Preflight item 10 swap (legibility for replay) didn't substitute on substance | Adopted: item 10 is now end-to-end data-discipline probe (trace + bus + KB + task-packet mutual consistency); legibility scorecard folds into item 8 (KB integration). Preflight remains 10-item gate. |
| F5 — §10.7 fallback options lack a stated default | Adopted: Option 1 (defer portability) is the named default; Option 2 (port-with-compensatory-scoping) requires three named conditions all met (independent reliability evidence; analyst-lane budget drawn in advance; first-repo port framed as reversibility-first experiment with kill trigger). |
| F6 — `compile_decision_inputs.py` floating | Adopted: Primitive C Work + Phase 0 Readiness now include the script + `/compile-decision-inputs` skill registration. |
| F7 — `harness_assumptions.md` schema needs worked example | Adopted: full worked example committed in §5-C; brittleness signal must be machine-observable (grep pattern, CI check, hook precondition). |
| F8 — GC acceptance criterion gameable | Folded into F2 fix: ≥3 acceptances across ≥2 distinct categories. |
| F9 — Success criterion #17 needs F6's fix | Folded into F6 fix. |
| F10 — Legibility floor operator-deferred and gameable | Adopted: provisional 7/10 floor committed in §5-C and ADR 001; sub-plan may tighten but may not loosen. |
| F11 — Goal #8 split between B and E | Adopted: §2 Goal #8 text now explicitly assigns *discovery* to Primitive E and *escalation via approval classes* to Primitive B sub-deliverables B.6/B.7. |
| F12 — Event schema versioning | Adopted: Primitive A Work now includes `schema_version` field; Phase 0 schema is `v1`; additive evolutions are `v1.N`; breaking changes require `v2` with migration sub-plan. |
| F13 — §16 Delta editorial | Resolved by structure: §16 Delta From Draft 5 is the new section, §17 Delta From Draft 4, §18 Delta From Draft 3 (preserved). |

**From operator directives (three new):**

1. **Reinstated clock-time as relative measurement.** Not a budget. Step template step 5 records elapsed wall-clock time per slice; primitives record cumulative time per readiness; Phase 1 records per-validation accumulation. Used as the second signal in §11 soft re-evaluation trigger and as a cost-signal feed into Phase 2 decision inputs. See §3 (definitions) and §4.1 phase table note.
2. **Goal #16 added: agent-first plan and KB design.** All durable artifacts (governing plan, sub-plans, KB entries, ADRs, prompt-policies, decision-input subsections, planning templates, briefings, run reports) optimized for agent navigation; human readability secondary. Applied across templates (Primitive C), KB scorecard (renamed agent-readability), and a new §10.8 architectural section codifying the conventions. Goal count: 15 → 16.
3. **F3 disposition: Option B (sub-deliverables table) over Option A (split B into B1/B2).** Preserves primitive count discipline (8 total / 7 Phase 0) at the cost of one larger primitive section.

## What you are asked to review

This is a **narrow** review. Do not re-evaluate draft 5 findings — analyst-b already did that thoroughly. Focus on:

1. **Did each F1-F13 fix land cleanly?** For each, was the analyst-b draft text adopted with substance preserved, or did the integration introduce new gaps? Disposition: ADOPTED-CLEAN / ADOPTED-WITH-GAP / NOT-ADOPTED / SUPERSEDED-BY-OPERATOR.
2. **Did the three new operator directives (relative clock-time, goal #16, F3 Option B) introduce new structural problems?** In particular:
   - Does the relative clock-time tracking actually integrate with §11 soft re-evaluation trigger as described, or is the integration handwavy?
   - Does goal #16 (agent-first design) have the right primitive ownership for enforcement (Primitive C templates), or does it leak across primitives?
   - Does the Primitive B sub-deliverables table approach (Option B) hold up under reading, or does it just dress up the F3 weight problem rather than solve it?
3. **Are there any draft 6-introduced cascade or coupling gaps?** Specifically:
   - Goal #16 enforcement depends on Primitive C lint scripts; Primitive C is also the home for the digest script (F6); is C now overloaded the way analyst-b worried Primitive B was?
   - Soft re-evaluation trigger (§11) introduces a new Phase 2 input class ("insufficient evidence"); does §15 ledger/digest pattern handle this cleanly or does it need a new tag/axis?
   - Relative clock-time tracking creates a per-primitive measurement requirement; is the recording mechanism (`Slice elapsed:` line in closeouts) sufficient or does it need a structured field?
4. **Promotion readiness.** If the draft-6 fixes look clean, can it be promoted to `governing_plan.md` (with drafts 1-5 archived) directly? Or does it need another revision cycle?

## Out of scope for this review

- Don't re-litigate analyst-a's draft 2 findings (all 23 dispositioned by analyst-b already).
- Don't re-litigate analyst-b's draft 5 findings (this review evaluates the fix, not the original finding).
- Don't propose new scope beyond the F1-F13 + 3 operator directives.
- Don't challenge the fixed constraints (single-repo, prove-before-port, Primitive H in Phase 1, hybrid subsections+digest pattern, deferred meta-layer, vertical-ambition floor of 16 goals).

If you find something material outside scope, surface as an open question, not a finding.

## Deliverables

- **Per-fix disposition table** (F1-F13 + 3 operator directives = 16 dispositions). For each, ADOPTED-CLEAN / ADOPTED-WITH-GAP / NOT-ADOPTED / SUPERSEDED-BY-OPERATOR with one-sentence evidence.
- **New gap findings** (G1, G2, ...) for any structural issue introduced by draft 6's integration. Each with severity (high / medium / low) and concrete proposed fix.
- **Promotion recommendation:** PROMOTE-AS-IS / PROMOTE-AFTER-G-FIXES / REVISE-DRAFT-7.
- **Updated grade.** Default scale: A / A- / B+ / B / B- / C+ / C / below. Draft 5 was B+.
- **Open questions** back to orchestrator/operator.
- **Written artifact** at `plans/steward_platform/draft6_review_<lane>.md`.

## Mechanics

- **Write scope:** `plans/steward_platform/` for the review artifact only. Do not edit drafts 1-6.
- **Write the review with goal-#16 conventions in mind** (predictable structure, machine-parseable disposition table, grep-clean cross-references). Drafting your own review under the same conventions you're being asked to evaluate is itself signal.
- **Time expectation:** narrow review; 1-2 hours focused work appropriate. Depth where it matters; pass-through where the analyst-b finding is straightforwardly resolved.
- **Escalation:** if you find a blocker, message orchestrator with concrete question rather than stalling.

Take the stance that the plan should be promotion-ready — but don't lower the bar to ship it.
