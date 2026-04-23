# Steward Platform Governing Plan — Draft 6 Narrow Review (analyst-c)

**Date:** 2026-04-23
**Reviewer:** steward-analyst (lane analyst-c — fresh eyes; analyst-a reviewed draft 2 and analyst-b reviewed draft 5; both recused)
**Target:** `plans/steward_platform/governing_plan.draft6.md`
**Scope:** **Narrow.** Per `plans/steward_platform/draft6_review_handoff.md`, this is a focused short-cycle review evaluating whether the draft-5 → draft-6 delta (analyst-b's F1–F13 + three operator directives) integrated cleanly. **Out of scope:** re-litigating analyst-a/analyst-b findings; challenging fixed constraints (single-repo, prove-before-port, Primitive H in Phase 1, hybrid subsections+digest pattern, deferred meta-layer, 16-goal vertical-ambition floor).
**Prior reviews:** `plans/steward_platform/draft2_review_analyst-a.md` (B), `plans/steward_platform/draft5_review_analyst-b.md` (B+).
**Review stance:** "should be promotion-ready, but don't lower the bar to ship it." Skeptical on integration substance, not on adopted scope.
**Self-conformance note:** This artifact is written under the goal-#16 agent-first conventions it is being asked to evaluate (predictable §N.M section IDs; machine-parseable disposition table; `path/from/repo/root.md` cross-references; per-finding stable IDs G1–G5; grep-clean naming).

---

## TL;DR

Draft 6 cleanly absorbed all 13 analyst-b findings and the 3 operator
directives. Every F-fix is ADOPTED-CLEAN on substance; the integration
introduced no contradictions with fixed constraints and no regression
against prior fixes. The two-signal soft re-evaluation trigger (§11
preamble) and the §10.8 agent-first architecture section are both
materially good additions, not surface-level patches.

Five gap findings (G1–G5) below — one medium-severity (G1, exact-shape
recurrence of F6's "load-bearing but floating script" pattern), three
low-to-low-medium tightening items (G2/G3/G4), and one editorial
numbering bug (G5). G1 is the only finding that should block direct
promotion; G2–G5 can be cleaned up in the same pass or absorbed as Phase
0 sub-plan opening tasks.

**Grade: A-** (up from draft 5's B+). The draft got sharper on every
axis analyst-b flagged (falsifiability, write-discipline, agent-first
conventions) without bloating scope or dropping prior structure.

**Recommendation: PROMOTE-AFTER-G-FIXES.** Apply G1 (mandatory) and as
many of G2/G3/G4/G5 as the operator finds persuasive in a tightening
pass; promote the result to `plans/steward_platform/governing_plan.md`
without a draft 7 review cycle. G1 is structurally identical to F6 and
the same fix shape applies.

---

## 1. Per-Fix Disposition Table (F1–F13 + 3 operator directives)

Disposition values: **ADOPTED-CLEAN** / **ADOPTED-WITH-GAP** /
**NOT-ADOPTED** / **SUPERSEDED-BY-OPERATOR**. One-sentence evidence per
row. Cross-references use `§N.M` for in-plan references and
`path/from/repo/root.md` for file references.

| ID | Source | Disposition | Evidence in `plans/steward_platform/governing_plan.draft6.md` |
|---|---|---|---|
| F1 | analyst-b high — kill-criteria falsifiability under thin proving run | **ADOPTED-CLEAN** | §11 preamble + two-signal differentiation table integrate activity-volume + relative-elapsed-time signals with named outcomes for all four cases; default routing is "re-evaluate in Phase 3" not "keep alive." |
| F2 | analyst-b high — Primitive D's GC half is Phase-0-labeled but Phase-1-substantive | **ADOPTED-CLEAN** | §5-D header re-labels as "inflow Phase 0; outflow Phase 1"; rationale paragraph names the symmetry with Primitive H; §5-D Readiness for outflow is "code path smoke-tested against seeded fake KB"; §11-D kill folds in F8 (≥3 across ≥2 categories). |
| F3 | analyst-b medium-high — Primitive B weight | **SUPERSEDED-BY-OPERATOR (Option B)** | §5-B sub-deliverables table maps B.1–B.7 to per-row Readiness/Validation/Kill cells; §11-B kill split into row 1 (B.1/B.2/B.5) and row 2 (B.3/B.4/B.6/B.7); combined readiness gate ("every row above shows green") names the per-row evaluation discipline. |
| F4 | analyst-b medium — Preflight item 10 swap (legibility for replay) didn't substitute on substance | **ADOPTED-CLEAN** | §6.4 item 10 is now end-to-end data-discipline probe across Primitives A + E + C + task queue; §6.4 item 8 absorbs agent-readability scorecard re-scoring; preflight remains 10-item gate per F4 alternative. |
| F5 | analyst-b medium — §10.7 fallback options lack a stated default | **ADOPTED-CLEAN** | §10.7 names Option 1 (defer portability) as default; Option 2 requires three named conditions all met (independent reliability evidence; analyst-lane budget drawn in advance; reversibility-first first-repo port with kill trigger); fallback to Option 1 if any condition unmet. |
| F6 | analyst-b medium — `compile_decision_inputs.py` floating | **ADOPTED-CLEAN** | §5-C Work bullet names `scripts/internal/compile_decision_inputs.py` with full §15.4 cross-reference; §5-C Phase 0 Readiness includes "first digest generated from Phase 0 closeouts"; `/compile-decision-inputs` skill registered. |
| F7 | analyst-b low-medium — `harness_assumptions.md` schema needs worked example | **ADOPTED-CLEAN** | §5-C ships full worked example ("Session-death threshold") at file head with all four schema fields; brittleness signal explicitly required to be machine-observable (grep pattern, CI check, hook precondition); natural-language signals stated as insufficient. |
| F8 | analyst-b medium — GC acceptance criterion gameable | **ADOPTED-CLEAN** | §5-D Phase 1 Validation row tightens to "≥3 GC-report proposals accepted across ≥2 distinct categories" with the five categories enumerated (stale entries / dead skills / obsolete policies / orphan artifacts / expired evidence). |
| F9 | analyst-b low — Success criterion #17 needs F6's fix | **ADOPTED-CLEAN** | §13 success criteria reference the digest script with Primitive C now its named owner via F6 fix; ownership chain is closed. |
| F10 | analyst-b low-medium — Legibility floor operator-deferred and gameable | **ADOPTED-CLEAN** | §5-C Phase 0 Readiness commits provisional ≥7/10 floor; §5-C Phase 1 Validation re-asserts "score equal to or better than Phase 0 baseline AND meets the floor recorded in ADR 001 (default ≥7/10)"; ratchet direction (sub-plan may tighten but may not loosen) named. |
| F11 | analyst-b low — Goal #8 split between B and E | **ADOPTED-CLEAN** | §2 Goal #8 text explicitly assigns *discovery* to Primitive E and *escalation via approval classes* to Primitive B sub-deliverables B.6/B.7; named in §5-B sub-deliverables table B.6/B.7 rows and in §5-E Goals served. |
| F12 | analyst-b medium — Event schema versioning | **ADOPTED-CLEAN** | §5-A Work names `schema_version` field as a first-class ID; Phase 0 schema is `v1`; additive evolutions are `v1.N` and replay-compatible; breaking changes require `v2` with explicit migration sub-plan; replay harness asserts `v1.N`-to-`v1.M` compatibility. |
| F13 | analyst-b low — §16 Delta editorial | **ADOPTED-CLEAN** | §16 is correctly "Delta From Draft 5"; §17 is "Delta From Draft 4"; §18 is "Delta From Draft 3 (preserved for lineage)." |
| OD1 | operator — relative clock-time tracking | **ADOPTED-CLEAN** | §3 defines "Relative clock-time tracking" with explicit "measurement, not budget" framing; §4.1 phase-table note repeats the principle; §4.4 step 5 mandates `Slice elapsed:` line per slice; §11 preamble integrates the signal into the soft re-evaluation trigger; §13 SC #18 captures the discipline at success-criterion level. (G2 below flags one residual enforcement asymmetry.) |
| OD2 | operator — goal #16 agent-first plan and KB design | **ADOPTED-WITH-GAP** | §2 adds Goal #16 with concrete conventions; §10.8 codifies the architectural principle with seven enumerated rules; §5-C templates "enforce both the Phase 2 Decision Inputs subsection AND goal-#16 agent-first conventions"; agent-readability scorecard renamed; SC #16 + #17 enforce. **Gap:** §10.8 references an "agent-readability lint script (Primitive C)" but Primitive C Work and Phase 0 Readiness do not enumerate the script as a deliverable — load-bearing-but-floating in exactly the F6 shape. See G1. |
| OD3 | operator — F3 Option B (sub-deliverables table) over Option A (split B into B1/B2) | **SUPERSEDED-BY-OPERATOR** | Already covered in F3 row above. Holds up under reading; the row-by-row readiness/validation/kill mapping makes per-deliverable status legible without splitting the primitive count. |

**Summary:** 13/13 analyst-b findings ADOPTED-CLEAN (F3 was
operator-overridden Option B and lands cleanly under that constraint).
2/3 operator directives ADOPTED-CLEAN; OD2 is ADOPTED-WITH-GAP via G1.
No prior fix was reversed; no constraint was violated; no scope was
silently expanded.

---

## 2. New Gap Findings (G1–G5)

Each finding has a stable ID; severity (high / medium / low); concrete
proposed fix. Severity scale matches analyst-b's draft-5 review.

### G1 — Agent-readability lint script load-bearing but floating (exact F6 shape)

**Severity:** medium.

**Evidence in draft 6:**
- `plans/steward_platform/governing_plan.draft6.md` §10.8: "Lint script (Primitive C) flags inconsistent forms" and "the agent-readability lint script (Primitive C) enforce[s] conformance across the full repo plan/KB surface, not just the governing plan."
- §13 Success Criterion #17: "Goal #16 conformance: every Phase 0 closeout, sub-plan, ADR, and KB entry passes the agent-readability lint script (template enforcement under Primitive C)."
- §5-C Work bullets: enumerate `compile_decision_inputs.py` (per F6) but do **not** name an `agent_readability_lint.py` (or equivalent) script. The bullet on planning templates says they "enforce goal-#16 agent-first conventions" at creation time via `/create-plan` and `/create-adr` skills, but template-time enforcement is a *creation* gate, not a *run-against-existing-artifacts* gate. The lint script referenced in §10.8 and SC #17 has no Work-bullet home.
- §5-C Phase 0 Readiness: lists 9 readiness conditions; none mention an agent-readability lint script committed or runnable.

**Why this matters:** This is the same pattern analyst-b flagged in F6 —
load-bearing infrastructure referenced multiple times in the plan but
not owned by any primitive's Work or Readiness. The F6 precedent says
the fix is to enumerate the script under the primitive that semantically
owns it (here, Primitive C — same home as `compile_decision_inputs.py`)
and add a Phase 0 Readiness condition that the script exists and runs
clean against the current repo plan/KB tree.

Without the fix, the §10.8 enforcement language and SC #17 are aspirational
rather than gated. A Phase 0 closeout could pass without the lint script
existing, and the goal-#16 enforcement story collapses to "skill refuses
to finalize templates lacking the subsection" — which is good but covers
*creation*, not *drift*.

**Proposed fix:**
1. Add to §5-C Work: `scripts/internal/agent_readability_lint.py` (or
   `lint_agent_readability.py` — name should be grep-clean per goal #16).
   Purpose: scan `plans/**/*.md`, `knowledge/**/*.md`,
   `.claude/skills/**/*.md` and flag violations of the §10.8 conventions
   (missing `§N.M` IDs, inconsistent cross-reference style, schemas
   without worked examples, preambles longer than ~25 lines, orphan
   references). Invokable as `/lint-agent-readability` skill.
2. Add to §5-C Phase 0 Readiness: "Agent-readability lint script
   committed; runs against the repo plan/KB tree and either passes or
   produces a documented baseline of pre-existing violations with each
   tagged for either fix-now or fix-via-sub-plan disposition."
3. Add to §11-C kill row: a co-criterion that the lint script either
   never runs against new artifacts during the proving run, or its
   findings are ignored — either signals goal-#16 enforcement did not
   land. (Optional, low-priority.)

**Cost to fix:** ~3 lines in §5-C Work, 1 line in §5-C Readiness, no
new architectural decisions. Same shape as the F6 fix.

### G2 — `Slice elapsed:` line enforcement asymmetric to Decision Inputs subsection enforcement

**Severity:** low.

**Evidence in draft 6:**
- §4.4 step 5: "**record elapsed wall-clock time** for the slice (start
  → close) under a `Slice elapsed:` line. **No slice is considered
  complete without both the subsection and the elapsed-time record.**"
- §13 Success Criterion #18: "Relative clock-time recorded for every
  primitive readiness slice and Phase 1 validation accumulation."
- §15.6 (write-discipline enforcement): names the `compile_decision_inputs.py`
  digest script as the mechanization that "flags missing subsections at
  the path level" for the Decision Inputs subsection. There is no
  equivalent mechanization for the `Slice elapsed:` line.

**Why this matters:** The plan's stated principle (§15.8) is that
mechanization prevents pattern decay — that's why the digest script
exists. The same principle applies to the `Slice elapsed:` line:
without machine enforcement, "no slice is considered complete without
the elapsed-time record" is a soft gate that depends on per-author
discipline. The §11 soft re-evaluation trigger relies on having relative
elapsed-time data; if the data is missing for some primitives, the
trigger's two-signal differentiation degrades to one signal for those
primitives.

**Proposed fix:** Either (a) extend `compile_decision_inputs.py` to also
grep for `^Slice elapsed:` lines in primitive closeouts and sub-plan
outcome files, flagging missing entries at the path level alongside
missing subsections; or (b) add the same check to the
`agent_readability_lint.py` script proposed in G1. Update §15.6 (or a
new §15.7) to name the enforcement surface. Add to §13 SC #18 a clause
that the digest script (or lint) flags zero missing `Slice elapsed:`
records during the proving run.

**Cost to fix:** ~10 lines in `compile_decision_inputs.py`, 1 line in
§15.6, 1 line in SC #18.

### G3 — Primitive C now structurally similar to pre-Option-B Primitive B (deliverable density)

**Severity:** low-medium.

**Evidence in draft 6:**
- §5-C Work bullets enumerate: 6 KB-skeleton classes (NOTES, PLAYBOOKS,
  anti_patterns, incidents, adr, harness_assumptions); MEMORY.md
  tightening + retention/compaction policy; planning templates with
  goal-#16 enforcement; agent-readability scorecard; INDEX auto-generator;
  `compile_decision_inputs.py` + `/compile-decision-inputs` skill;
  worked example for `harness_assumptions.md`; (per G1) implicit
  `agent_readability_lint.py`. That is **8+ distinct deliverables under
  one primitive header**.
- §5-C Phase 0 Readiness has 9 bullets — close to the per-row count that
  prompted F3 against Primitive B before the Option B sub-deliverables
  table was applied.

**Why this matters:** Analyst-b's F3 reasoning ("a reviewer at Phase 1a
preflight cannot tell whether the primitive is done or not without going
row by row") applies symmetrically to Primitive C. A reviewer evaluating
C's Phase 0 Readiness has to walk 9 conditions across at least 4 distinct
artifact families (KB, MEMORY.md, templates+skills, scripts). The F3
Option B fix solved this for B by making the per-row mapping explicit;
C currently has no such table.

**Counter-argument** (and why this is low-medium not medium): C's
deliverables are arguably more cohesive than B's were. Every C
deliverable lives under `knowledge/`, `plans/_templates/`, or
`scripts/internal/` (the digest script). Every C deliverable serves the
same agent-readable-durable-memory purpose. B's pre-Option-B mix
spanned dispatch, skill loop, prompt-policy, and risk registry across
unrelated surfaces; C's mix is more thematically coherent. So the F3
critique applies less forcefully here, but it is not absent.

**Proposed fix:** Either (a) apply F3's Option B treatment symmetrically
to C with a sub-deliverables table (C.1 KB skeleton, C.2 MEMORY.md
discipline, C.3 templates + skills, C.4 agent-readability scorecard +
lint, C.5 digest script); or (b) add a one-paragraph note under §5-C
explaining why C's deliverables form a single coherent cluster (single
durable-artifact home, single `/create-plan` enforcement surface) such
that the sub-deliverables table is unnecessary. Option (b) is lighter
weight and preserves the asymmetry-by-justification.

**Cost to fix:** Option (b) is ~5 lines in §5-C; Option (a) is ~15
lines (table) + minor re-numbering.

### G4 — Soft re-evaluation trigger introduces "insufficient evidence" Phase 2 input class not represented in §15 schema

**Severity:** low-medium.

**Evidence in draft 6:**
- §11 preamble (added per F1): "every kill criterion below carries an
  implicit **soft re-evaluation trigger**: if a primitive's activity
  during the proving run is below the threshold needed to evaluate its
  kill criterion, *and* its elapsed-time relative to other primitives is
  not yet at the relative norm, the primitive is flagged at Phase 2 as
  'insufficient evidence' and explicitly scoped for a follow-up
  evaluation window (Phase 3)."
- §15.2 subsection schema: four prompts (Portability readiness /
  Meta-layer need / Kill signal for primitive(s) named / Surprise
  finding) plus Disposition. The Kill signal prompt asks `[yes/no with
  evidence link, or N/A]` — binary, with no "insufficient evidence"
  branch.
- §15.7 Phase 2 use: kill decisions read from "all entries with 'yes'
  Kill signal prompts." Insufficient-evidence primitives have no
  semantic home; they default to the Surprise finding prompt or to a
  free-text override.

**Why this matters:** The §15 schema is the read surface for Phase 2.
If the §11 trigger produces a third class of primitive disposition
("insufficient evidence → re-evaluate in Phase 3") but the schema only
has prompts for the two-class case (kill / not-kill), the digest cannot
group insufficient-evidence primitives. Phase 2 reviewers either have to
construct the third class manually from scattered Surprise-finding
prompts or skip the discipline entirely. This re-introduces the
graveyard risk that analyst-a originally flagged against the ledger
pattern (§18 Delta From Draft 3 bullet 2).

**Proposed fix:** Either (a) extend the Kill signal prompt schema in
§15.2 to permit `[yes/no/insufficient-evidence with evidence link, or
N/A]`, with the insufficient-evidence branch carrying a recommended
Phase 3 re-evaluation window; or (b) add a fifth prompt:
`**Re-evaluation needed in Phase 3:** [one sentence with recommended
window, or "no"]`. Option (b) is more legible for the digest and easier
for `compile_decision_inputs.py` to bucket. The compile script then
groups insufficient-evidence entries into a fifth axis bucket alongside
portability / meta-layer / kill / surprise.

**Cost to fix:** ~3 lines in §15.2 schema, ~5 lines in §15.4 digest
spec, ~1 line in `compile_decision_inputs.py` (parser regex extension).

### G5 — §13 Success Criteria has duplicate item-numbering ("17" appears twice)

**Severity:** low (editorial; not structural).

**Evidence in draft 6:**
- `plans/steward_platform/governing_plan.draft6.md` §13 lists 18
  numbered items but two of them are numbered "17":

```
16. Agent-readability scorecard re-scored at end of Phase 1 ...
17. Goal #16 conformance: every Phase 0 closeout, sub-plan, ADR, and KB entry passes the agent-readability lint script ...
18. Relative clock-time recorded for every primitive readiness slice and Phase 1 validation accumulation ...
17. Every primitive closeout, sub-plan outcome, preflight report, proving-run report, and shape audit includes a Phase 2 Decision Inputs subsection per §15; digest script regenerates nightly without flagging missing subsections.
```

**Why this matters:** §10.8 explicitly calls out predictable section IDs
and stable IDs in mutable artifacts as goal-#16 conventions ("artifacts
that survive revision"). A duplicate item number in the success-criteria
table is precisely the anti-pattern the convention prohibits. Drafting
the plan under conventions it itself enumerates is signal — and the
inverse (a numbering bug in the criteria table that asserts numbering
discipline) is also signal. Trivially fixable.

**Proposed fix:** Renumber so the final "Every primitive closeout..."
item is #19 (preserving lineage from earlier drafts where it was the
sole subsection-discipline criterion). One-line fix.

---

## 3. Promotion Recommendation

**PROMOTE-AFTER-G-FIXES.**

Rationale:

- 13/13 analyst-b findings ADOPTED-CLEAN; 2/3 operator directives
  ADOPTED-CLEAN; 1 operator directive ADOPTED-WITH-GAP (OD2 → G1). No
  prior fix reversed; no fixed constraint violated; no scope silently
  expanded. The integration substance is sound.
- G1 is the only G-finding that should block direct promotion. It
  recurs F6's exact pattern (load-bearing script not owned by any
  primitive Work bullet) and the same fix shape applies. Without it,
  goal-#16 enforcement is partly aspirational.
- G2/G3/G4/G5 are tightening items. None require re-architecture; none
  challenge a fixed constraint; none require a draft-7 review cycle.
  They can land in the same tightening pass as G1 or be absorbed into
  Phase 0 sub-plan opening tasks.

**Concrete proposal:**

1. Operator (or orchestrator on operator's behalf) makes a tightening
   pass applying G1 (mandatory), G5 (one-line), and as much of
   G2/G3/G4 as preferred.
2. Promote the result to `plans/steward_platform/governing_plan.md`
   without a draft-7 analyst review cycle. Drafts 1–6 archive as the
   review-lineage record alongside the draft-2/draft-5/draft-6 review
   artifacts.
3. File ADR 001 (Platform-11/13 dismissal evidence + agent-readability
   floor + draft 1→6 review-cycle observation per draft 6's own §
   Outcome Phase 2 Decision Inputs surprise finding) at Phase 0
   kickoff, as the plan already specifies.

If the operator prefers to land all five G-findings before promotion,
that is also a reasonable path; the cost of the tightening pass is
small (~30 lines across §5-C, §15.2, §13, §10.8 cross-references).
Either path is materially cheaper than a draft-7 review cycle and
preserves the "narrow review → revise → promote" structure analyst-b
recommended.

---

## 4. Updated Grade

**A-** (up from draft 5's B+).

The grade reflects:

- **+1 step** for fully-clean integration of analyst-b's 13 findings
  with no reversal, no contradiction, and no scope expansion. F1 in
  particular is more than a patch — the two-signal differentiation
  table makes the soft trigger evaluable, not just rhetorical.
- **+1 step** for the §10.8 agent-first architecture section. Goal #16
  is not just a goal-list addition; §10.8 codifies seven enumerated
  conventions and ties them to template enforcement (with the G1
  caveat). This is real plan-level investment in agent-first discipline,
  not a label change.
- **No further step up** because of G1 (the lint-script ownership gap
  recurs F6 in the same draft as F6 is fixed — one of those should not
  shadow the other) and G4 (the §15 schema asymmetry against the §11
  trigger leaves a Phase 2 read-surface gap that the plan's own
  graveyard-risk reasoning would identify).
- **A** is reachable in one tightening pass. **A** would require G1
  closed and G4 either closed or explicitly deferred-with-rationale
  (e.g., "the schema asymmetry is acceptable because Phase 2 reviewers
  manually construct the third class from §11 trigger logs").

The prior B+ grade was correct against draft 5; the A- here is not
inflation, it is the credit for the F1/F2/F4/F5/F6 fixes landing
cleanly plus the §10.8 codification.

---

## 5. Open Questions Back to Orchestrator / Operator

These are out-of-scope-for-this-narrow-review observations surfaced as
questions per the handoff convention.

**Q1.** §13 Success Criteria has 18 items per the operator's "16 goals
+ 18 success criteria" framing, but the §13 list as written has 18
items only by counting both #17s. Is this intentional ambiguity
(criterion-count == goal-count + 2 was never the contract) or an
artifact of the renumbering bug (G5)? Asking because the lint-script
ownership question (G1) might want to land as a 19th success criterion
explicitly tying lint-script enforcement to goal-#16 discipline.

**Q2.** The §11 soft re-evaluation trigger uses "elapsed-time relative
to other primitives" as one of two signals. "Relative to other
primitives" requires a normalization decision: relative to the
slowest-readiness primitive, the median, the cumulative phase elapsed?
This is sub-plan-level detail and not in scope for the governing plan,
but the choice is load-bearing for the trigger's behavior. Worth
flagging as an Open Item under §14 (or as the first question for the
sub-plan that would extend `compile_decision_inputs.py` to surface
relative-time data).

**Q3.** The §11 kill criteria for Primitive H now hinge on at least one
failure-injection scenario being "selected post-hoc by an analyst lane
after primitives A, B, and E ship" — a good adversarial discipline.
Is the analyst-lane selection intended to happen during Phase 1 (as
the proving run accumulates events) or at end of Phase 1 (during
Phase 2 input assembly)? The plan reads either way; clarification
would tighten the §11-H kill row.

**Q4.** Out-of-scope but surfaced per handoff: draft 6's §Outcome
Phase 2 Decision Inputs surprise finding ("the review → revision cycle
across drafts 1→6 is itself a demonstration of the §15 pattern, the
goal-#16 theme, and the hybrid subsections+digest mechanism all working
in miniature") is itself a candidate ADR alongside ADR 001. Worth
filing as ADR 002 (or 001b) — the empirical evidence base is the
draft-1-through-draft-6 review/revision artifacts already committed
under `plans/steward_platform/`. This is the operator's call to make at
Phase 0 kickoff.

---

## 6. Self-Conformance Check Against Goal #16 Conventions

Per the handoff: "drafting your own review under the conventions you're
evaluating is itself signal." Self-check against the seven §10.8
conventions:

| Convention | This artifact's conformance |
|---|---|
| Predictable §N.M section IDs | Yes — §1–§6 with stable section-prefixed structure. |
| Machine-parseable structured fields | Yes — disposition table in §1 is single-line-per-finding with consistent column order; G1–G5 in §2 use stable subheaders + stable severity / evidence / proposed-fix subsections. |
| Consistent cross-reference patterns | Yes — `§N.M` for in-plan internal references; `path/from/repo/root.md` for file references; no `./` or `../`. |
| Grep-clean naming | Yes — finding IDs G1–G5 are unique; no naming collision with F1–F13 or analyst-a's S/SC/D/R taxonomy. |
| Loadable as agent context with minimal preamble | Yes — first ~20 lines (header + TL;DR) establish reviewer, target, scope, recommendation, and grade. |
| Worked examples for any new schema | Not applicable — this artifact introduces no new schemas. |
| Stable IDs in mutable artifacts | Yes — disposition table rows keyed by F-ID and OD-ID; G-findings carry stable G-IDs. |

If this review is itself appended to the draft-6-as-promoted lineage
(per §15 hybrid pattern), the disposition table and G-findings are
auto-parseable by `compile_decision_inputs.py` extensions or by a
sibling lint-style script. That structural property is the substantive
test of the goal-#16 conventions; this artifact passes it.

---

## Phase 2 Decision Inputs

**Portability readiness:** no change (review of governing plan; no portability evidence added).
**Meta-layer need:** no change (review is plan-internal; no meta-layer signal).
**Kill signal for primitive(s) named:** N/A (no primitive execution yet).
**Surprise finding:** The G1 finding (lint script load-bearing-but-floating) recurring the exact F6 pattern in the same draft as F6 is fixed is itself signal that the goal-#16 enforcement architecture would benefit from a generalized "load-bearing-script ownership" check. The same pattern could recur for any future cross-primitive script reference. A planning-template or `/create-plan` rule that flags "script referenced in §N.M but not enumerated in any primitive Work bullet" would close the recurrence path. Worth filing as a candidate Phase 0 sub-plan under Primitive C or as a goal-#16 lint rule once the lint script (G1 fix) lands.
**Disposition:** open
