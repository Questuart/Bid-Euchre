# Steward Platform Governing Plan — Draft 5 Review (analyst-b)

**Date:** 2026-04-23
**Reviewer:** steward-analyst (lane analyst-b — fresh eyes; analyst-a reviewed draft 2 and is recused)
**Target:** `plans/steward_platform/governing_plan.draft5.md`
**Prior drafts (for diffing):** `governing_plan.md` (draft 1), `governing_plan.draft2.md`, `governing_plan.draft3.md`, `governing_plan.draft4.md`
**Prior review:** `draft2_review_analyst-a.md` (806 lines, graded draft 2 at **B**)
**Handoff:** `draft5_review_handoff.md`
**Review stance:** skeptical; prefer simpler solutions; flag over-engineering; propose better alternatives; judge against the *best plausible plan* standard, not the *workable plan* standard.

---

## TL;DR

Draft 5 is a materially better plan than draft 4 on the two axes the
operator cared most about: (a) it gets Primitive H's weight out of the
Phase 0 gate without discarding the capability, and (b) it closes a cluster
of small but real blind spots by adopting the seven scope extensions from
`phase2_harness_engineering_research.md`. Most of analyst-a's draft-2
findings are fully resolved in draft 5; no prior finding is missed; two
("primitive-count consistency" and "decision-inputs graveyard risk") are
resolved with concrete enforcement mechanisms rather than hand-waves.

Draft 5 is also, however, the heaviest the plan has been — Primitives B
and C have absorbed a lot in this round — and the new material arrived
without rebalancing. There are a handful of concrete weaknesses I think
block promotion as-is:

1. **Primitive D's entropy/GC report presumes a populated KB** that does
   not exist at Phase 0 start; its Phase 0 Readiness is hollow and its
   Phase 1 Validation threshold (≥1 accepted GC proposal) is a low bar
   that can be trivially cleared without the report producing real signal.
2. **Preflight item 10 (legibility scorecard) is not substitutable for
   the dropped replay item.** Legibility measures whether the repo is
   navigable by an agent; replay measures whether the platform can
   reconstruct behavior from events. These are orthogonal and the swap
   leaves a hole in the preflight surface that §10.7 now has to carry.
3. **§10.7's two Phase 2 fallback options lack a stated default.** When
   H fails validation, there is no pre-committed plan-level preference
   between "defer portability" and "port anyway with compensatory
   scoping." Leaving that to in-the-moment operator judgement is exactly
   the decision-hygiene gap the governing plan is supposed to close.
4. **Primitive B is now carrying seven distinct deliverables** (adaptive
   dispatch, skill loop, prompt-policy registry, policy-change discipline,
   tool risk registry, approval classes, analyst/author routing). The
   readiness/validation split is cleanly drawn but the primitive has drifted
   from "a thing" to "a thematic cluster"; a reviewer at Phase 1a preflight
   cannot tell whether the primitive is done or not without going row by
   row.
5. **`scripts/internal/compile_decision_inputs.py` is load-bearing
   infrastructure referenced four times in the plan but is not a named
   Work bullet under any primitive.** The digest pattern's entire
   read-surface hinges on this script; it currently floats.
6. **Clock-time removal is operator-directed and correct in isolation,
   but §11 kill criteria are now entirely usage-based with no fallback
   for "what if usage doesn't happen."** A primitive that sees zero
   activity during the proving run has no kill path and will accrete into
   Phase 2 as "no evidence yet, keep alive." This is a specific
   load-bearing challenge to a fixed constraint and is argued in F1.

Beyond these, the plan has some smaller fresh-eyes findings (F7 through
F13 below) worth addressing before promotion.

**Grade: B+ (up from draft 4's B).** Approve with revisions. I recommend a
**revise → draft 6 → promote** path, not direct promotion of draft 5.
Draft 6 would apply F1/F2/F3/F4/F5/F6 (the six load-bearing findings
above) plus whichever of F7-F13 the operator finds persuasive. None of
these require rework from scratch or challenge the fixed constraints
except F1 (clock-time, argued below under load-bearing reasoning).

---

## 1. Per-Finding Disposition of Analyst-A's Draft-2 Review

Analyst-a's review had 12 prior findings (carried from the draft-1 review)
plus 11 new findings introduced against draft 2. I classify each against
draft 5: **RESOLVED** / **PARTIAL** / **MISSED** / **OBVIATED**.

### 1.1 Prior findings (carried from draft-1 review of draft 1)

| # | Finding | Draft-2 Disposition | Draft-5 Disposition | Evidence in draft 5 |
|---|---|---|---|---|
| S1 | Conflated operator-UX pain with portability pain | OBVIATED | OBVIATED | §1 scope is single-repo; cross-project deferred to Phase 2 |
| S2 | Falsification test deferred to Phase 4 | RESOLVED | RESOLVED | §1 / §7 proving run as Phase 1 falsification; §7.2 separates research from platform test |
| S3 | ~12 primitives in a "prove before port" plan | PARTIAL | **RESOLVED** | 8 primitives total, 7 in Phase 0 + 1 deferred to Phase 1 under the usage-based gate. The structural concern (primitive inflation) is fully resolved by H's Phase 1 framing. |
| SC1 | "Make steward excellent" not scoped | RESOLVED | RESOLVED | §2 lists 15 concrete capabilities; closed scope-lock language tightened |
| SC2 | KB taxonomy over-designed | RESOLVED | RESOLVED | 6-item KB (NOTES, PLAYBOOKS, anti_patterns, incidents, adr, harness_assumptions) plus INDEX. Still proportional; harness_assumptions is a genuinely new category, not a regression. |
| SC3 | Archivist-as-lane | RESOLVED | RESOLVED | §5-D keeps archivist as a scheduled script; now produces two outputs (lessons + GC) |
| D1 | Phoenix workflows as categories not workflows | PARTIAL | RESOLVED | §5-A workflows now have trigger/consumer/cadence/output; kill criterion counts promoted findings, not UI opens |
| D2 | Meta-steward-home as a new repo | RESOLVED | RESOLVED | Deferred to Phase 2; §2 deferred-items block + post_phase2_sidecar |
| D3 | Meta-orchestrator as a lane vs. pattern | RESOLVED | RESOLVED | §10.1 excludes meta-surface from Phase 0; §8.2 Decision #2-3 keeps it as Phase 2 output |
| R1 | Target repos not inspected before the plan commits to them | PARTIAL | RESOLVED | §4.2 specifies 2-3 days per repo, 8-item output format, PORTABILITY_MANIFEST taxonomy tie-in |
| R2 | No kill criteria per workstream | RESOLVED | RESOLVED | §11 all 8 primitives have kill criteria with usage-based thresholds |
| R3 | No phase gates | RESOLVED | RESOLVED | §4.1 phase table has explicit Depends-On edges; preflight, proving run, and Phase 2 are all gated |

**Summary:** All 12 prior findings are now resolved. S3 and D1, which
were partial in draft 2, are fully resolved in draft 5.

### 1.2 Draft-2 new findings (introduced by analyst-a)

| # | Finding | Draft-5 Disposition | Evidence in draft 5 |
|---|---|---|---|
| 2.1 | Primitive-count inconsistency (7 vs 8 in the plan text) | RESOLVED | §4.1 consistently says "7 primitives (A-G)" Phase 0; §5 opens "8 Primitives" over full plan with phase membership per primitive; §13 #1 is explicit; §16 Delta says 8→7 Phase 0, still 8 total |
| 2.2 | Goal #16 scope-creep license | RESOLVED | Already resolved in draft 3 and preserved; §2 preamble has the closed-scope-lock statement; §17 Delta records the removal |
| 2.3 | Phase 0 time-box (6-8 weeks) unrealistic | OBVIATED | Clock-time removed in draft 3 per operator directive; §4.1 note at end reads "No clock-time budgets are attached to phases. Sequencing and readiness/validation gates are the discipline; the work takes the time it takes." See F1 for a load-bearing challenge to this removal. |
| 2.4 | Decision-inputs ledger graveyard risk + tag taxonomy | RESOLVED | §15 is the hybrid pattern analyst-a proposed in §3.4 of their review, extended: write surface is 4 prompts + disposition, read surface is auto-generated digest, meta-findings file for cross-cutting, template enforcement via `/create-plan`, digest script nightly missing-subsection report. §15.8 frames it as durable infrastructure with an ADR candidate of its own. The pattern analyst-a proposed was adopted almost verbatim and then hardened. |
| 2.5 | Self-sympathetic kill-criteria thresholds | RESOLVED | §11 rows adopted analyst-a's sharpening: Phoenix counts promoted findings; skill/policy edits cite trace IDs; KB cites in grep-verifiable downstream PRs; messaging has ≥20-issue denominator floor; reliability lab requires post-hoc surprise scenario. |
| 2.6 | Proving-run data-sufficiency check missing | RESOLVED | §6.1 Pre-Phase-1 data-sufficiency check + measurement-methodology-overhaul pivot alternative. Pivot decision is itself a Phase 2 Decision Input. |
| 2.7 | Target-repo audit under-specified | RESOLVED | §4.2 — 2-3 days per repo, 8-item output format, portability-debt taxonomy tie-in. If audit can't be produced to depth in time, that's itself a portability signal. |
| 2.8 | Platform-11/13 dismissal needs evidence | RESOLVED | §12 Risks row 6 references ADR 001 filed at Phase 0 kickoff; §4.5 Phase 0 Dependencies also references it. Full ADR content is Open Item #11. |
| 2.9 | Phoenix workflow specificity | RESOLVED | §5-A — reproducibility audits and session-archive evaluation both have trigger/consumer/cadence/output rows. Kill criterion counts promoted findings. |
| 2.10 | §7.2 (now §8.2) cmux pre-describes its shape | RESOLVED | §8.2 Decision #3 now reads only "cmux adoption. Only relevant if portability goes forward. Shape to be determined by proving-run evidence and shape-audit findings; not pre-described." |
| 2.11 | Primitive H / Phase 2 portability coupling | RESOLVED | §10.7 explicit design-coupling note with two Phase 2 fallback options if H fails validation. §5-H opens with the "intended to be" hedge analyst-a requested. (But see F6: the fallback options lack a stated default.) |

**Summary:** 11 of 11 new findings resolved. None missed.

### 1.3 Scorecard

| Bucket | Resolved | Partial | Missed | Obviated |
|---|---|---|---|---|
| Prior (12) | 12 | 0 | 0 | 0 |
| Draft-2 new (11) | 10 | 0 | 0 | 1 |
| **Total (23)** | **22** | **0** | **0** | **1** |

This is a strong showing. 22 of 23 findings resolved cleanly across two
revision cycles (drafts 3, 4, 5 over ~1 day) without drift or
defensiveness. The one "obviated" (2.3 Phase 0 time-box) was resolved by
operator directive rather than by re-analysis, which is why F1 below
re-examines whether the clock-time removal was over-corrected.

---

## 2. New Findings (draft 4 → draft 5 delta)

Thirteen findings, F1 through F13. Severity is noted; fixes are drafted
concretely in §3.

### F1 — Clock-time removal leaves kill criteria without a falsifiability trigger

**Severity:** high. This is a load-bearing challenge to a pre-existing
fixed constraint (clock-time removed in draft 3 per operator directive),
reopened because the §11 kill-criteria sharpening (good) and the
Primitive H Phase 1 deferral (good) together expose a new gap that
didn't exist when clock-time was first removed.

**Evidence:**

- §4.1 final note: *"No clock-time budgets are attached to phases.
  Sequencing and readiness/validation gates are the discipline; the work
  takes the time it takes."*
- §11 kill criteria are all usage-based: *"<3 promoted findings"*, *"Zero
  skill promotions"*, *"<3 promoted lessons cited"*, *"<10%
  candidate-to-promotion rate"*, *"<20% of issues created via active
  triage"*, etc. Every threshold is a counting condition over proving-run
  activity.
- But: §6.1 says the proving run may pivot to a
  methodology-overhaul alternative if browser-game data is thin. The
  pivot is itself a Phase 2 Decision Input with `Portability readiness`
  filled to note "research value via browser data was not accessible within
  Phase 1."
- Combination: if the proving run is a thin methodology-overhaul pivot
  (which is the explicit fallback the plan protects for), and if Phase 0
  takes as long as it takes, then every primitive has a path to
  "insufficient evidence, keep alive" rather than "failed, retire." The
  plan's own risk mitigation prevents kill-criterion evaluation from
  biting.

**Why this is load-bearing despite the fixed-constraint flag:**

The operator's clock-time removal directive was sound *for what it
directly addressed* — the draft 2 time-box was set unrealistically and
the honest fix is to drop the time-box rather than pad it. But the
directive was made before draft 5's kill-criteria sharpening and before
the proving-run pivot alternative was added. Usage-based kill criteria
need some mechanism that says "enough time has passed or enough activity
has occurred for the absence of a signal to be meaningful." Otherwise
kill criteria are unfalsifiable in the pathological case.

**Specific pathological case:** Primitive A ships trace + Phoenix + event
routing, but the proving run pivots to methodology overhaul which
primarily exercises Primitives B/C/D (policy + KB + archivist). Phoenix
sees <3 promoted findings over the pivot run not because Phoenix is
broken but because the run didn't produce the kind of work Phoenix
detects. Does Primitive A get killed? The plan as written says yes
(§11-A threshold is <3 promoted findings). The plan also says Phase 2
re-evaluates. The gap is that Phase 2's re-evaluation has no distinction
between "killed because the primitive failed" and "killed because the
run didn't give it enough to work with."

**Recommendation:** Not to restore a clock-time box. The directive to
remove was correct. *Instead*, add a **soft re-evaluation trigger**: if
a primitive sees below-threshold activity during the proving run, the
kill criterion does not fire automatically; it escalates to Phase 2 as
"insufficient evidence — re-evaluate scope or extend." This preserves
the usage-based discipline while avoiding the unfalsifiability trap.
Draft text in §3.

### F2 — Entropy/GC report is a Phase 0 primitive whose inputs don't exist until Phase 1

**Severity:** high.

**Evidence:**

- §5-D Primitive D Work: second archivist output `<date>_gc.md` for
  "stale KB entries (not referenced in N sessions), dead skills (not
  invoked since promotion), obsolete prompt-policy versions
  (superseded), orphan artifacts (referenced file or trace ID no longer
  exists), KB entries where linked evidence has expired."
- §5-D Phase 0 Readiness: *"Archivist script runs nightly and on
  end-of-session hook; targeted tests cover templating and event-reading
  for both inflow and outflow outputs."*
- §5-D Phase 1 Validation: *"≥1 GC-report proposal accepted during the
  proving run (outflow working)."*
- But the KB does not exist yet at Phase 0 start. §5-C Phase 0 Readiness
  stands up the KB skeleton and populates `harness_assumptions.md` with
  ≥5 initial entries, but NOTES / PLAYBOOKS / anti_patterns / incidents
  / adr all begin empty. The prompt-policy registry and skill registry
  also begin empty or near-empty at Phase 0 start.

**Implication:** At Phase 0 readiness time, the GC report's inputs are
*definitionally* nearly-empty. It cannot meaningfully detect stale KB
entries because the KB has no entries. It cannot detect dead skills
because no skills have been promoted yet. It cannot detect obsolete
policy versions because the registry is fresh.

The GC report only starts doing its job mid-Phase-1, at which point the
KB has been accruing for weeks. So its substance is a Phase 1 capability
wearing a Phase 0 readiness label.

This is also why the Phase 1 Validation threshold (≥1 accepted GC
proposal) is low: the first GC pass will have little to work with. ≥1 is
easy to satisfy trivially.

**Recommendation:** Split Primitive D's GC half into Phase 1 work (like
Primitive H). Phase 0 readiness for D covers the lessons inflow only.
Phase 1 work adds the GC outflow as a sub-primitive, with its readiness
"can run against accumulated state" and its validation "produces useful
proposals." This maps cleanly to the way Primitive H is already phased.

Alternative: keep GC in Phase 0 but tighten Phase 0 readiness to
"scaffolding + a targeted unit test against a seeded fake KB"; then
reinterpret §5-D Phase 1 Validation as "≥1 GC proposal accepted *of
material signal quality*" — not just ≥1 proposal accepted, which today
can be cleared by accepting a trivial stale-ref removal.

### F3 — Primitive B has become a thematic cluster, not a primitive

**Severity:** medium-high. Directly relevant to handoff ask #2 (extensions
proportionality).

**Evidence:**

Primitive B's Work section (§5-B) now has seven distinct deliverables:

1. Close SP-5-02 adaptive dispatch (advisor → operator-visible → promoted)
2. Skill promotion loop tied to outcomes, commit-message trace-ID citation
3. Prompt-policy registry (net-new, versioned contract)
4. Analyst-vs-author routing rules encoded as policy
5. Prompt-policy change discipline (trigger / expected effect / rollback condition as structured commit-message fields) — **new in draft 5**
6. Tool risk registry + approval classes — **new in draft 5**
7. Policy candidate → confirmed lifecycle

Its Phase 0 Readiness has 6 bullets. Its Phase 1 Validation has 6
bullets. Every extension added in draft 5 added ≥1 Readiness item and ≥1
Validation item.

**Implication:** An author-lane reviewer at Phase 1a preflight cannot
answer "is Primitive B done?" from a single test or artifact. The
primitive has drifted from "a thing" to "a list of related things."
This is the pattern analyst-a flagged in draft-2 finding 2.3 against the
8-primitive count — except that ambition was resisted and the count was
held; instead, the *weight per primitive* inflated.

From the fixed-constraint list, the 7 extensions are operator-approved
so I cannot recommend removing any. But there is a cleaner shape: split
Primitive B into **B1 (adaptive dispatch / skill loop)** and **B2
(prompt-policy + tool risk + approval classes)**. Both are Phase 0. The
split costs one table row in §11 (adding a B2 kill criterion) and a
one-line update to the §13 success criteria. It gains: readable
readiness/validation surfaces per sub-primitive, and a clean home for
the tool-risk-registry kill criterion that today is stapled onto
Primitive B's kill row alongside the unrelated skill/policy kill
condition.

**Alternative:** if operator prefers to keep B as one primitive,
introduce a "**B Sub-deliverables**" table in §5-B listing the 7
deliverables against their own readiness/validation mini-rows. Structure
without adding primitive count.

### F4 — Preflight item 10 (legibility scorecard) does not substitute for the dropped replay item

**Severity:** medium.

**Evidence:**

- Draft 4 preflight item 10 (per §17 Delta reference): replay checklist,
  testing Primitive H.
- Draft 5 §6.4 item 10: *"Agent legibility. Legibility scorecard (Primitive
  C) re-scored at end of Phase 0; score meets a documented floor
  (operator-set in sub-plan under Primitive C). Replaces the replay
  checklist item, which moves to Phase 1 validation (Primitive H) since H
  does not exist at preflight time."*
- Draft 5 §16 Delta: *"Preflight checklist (§6.4) swaps the replay item
  (Primitive H, not available at preflight time) for the agent legibility
  item (Primitive C). Preflight remains a 10-item gate."*

**Implication:** The swap preserves item count but not substance. The
original item tested that the platform could reconstruct behavior from
events (a data-discipline end-to-end probe). Its replacement tests that
the repo is navigable by agents (a workspace-ergonomics probe). These
are orthogonal concerns.

The preflight surface coverage now has:

- Trace reconstruction (item 1) ✓ — tests Primitive A
- Event-driven monitoring (item 2) ✓ — tests Primitive A
- Routing (item 3) ✓ — tests Primitive B
- Prompt-policy citation (item 4) ✓ — tests Primitive B
- Messaging (item 5) ✓ — tests Primitive E
- Active triage (item 6) ✓ — tests Primitive E
- Archivist (item 7) ✓ — tests Primitive D (inflow only)
- KB integration (item 8) ✓ — tests Primitive C
- Rollback (item 9) ✓ — tests Primitives B, H, goal #13
- Agent legibility (item 10) ✓ — tests Primitive C (again)

Primitive C is now tested by items 8 and 10. Primitive D's GC-outflow
half is not tested at preflight at all (it can't be — see F2). And there
is no end-to-end data-discipline probe that proves "the platform's
events are consistent enough to drive behavioral checks," which is what
the replay item was doing.

**Recommendation:** Keep the legibility scorecard but either (a) move it
into item 8 (KB integration) as a sub-bullet, or (b) replace item 10
with an **end-to-end data discipline** probe. Draft text in §3. Candidate
probe: "pick one task completed during preflight, assert its trace
corpus + message bus state + KB artifacts + task-packet state are all
mutually consistent (no orphan events, no lane attribution mismatches,
no task-packet state that contradicts its completion event)." This
tests Primitives A + E + C + the task queue together without needing H.

### F5 — §10.7 two fallback options lack a stated default

**Severity:** medium.

**Evidence:**

§10.7: *"If H is demoted under its kill criterion (§11-H) or fails to
complete validation by end of Phase 1, Phase 2 must either: (1) Defer
the portability decision until H is rebuilt and validated (pushes
portability to Phase 3+), or (2) Accept the portability decision with
explicit acknowledgment that no dry-run harness exists, and manually
scope the first-repo port with additional analyst-lane discovery work
to compensate."*

The plan presents the two options neutrally. Phase 2 is instructed to
*"either...or"* — with no stated preference.

**Implication:** The whole point of naming a coupling in a governing
plan is to pre-commit a default so that Phase 2 doesn't have to decide
under pressure, with the author and reviewer in the loop. As drafted,
§10.7 pushes the decision back into Phase 2 without guidance.

This weakens the design coupling it is supposed to strengthen. An
operator reading §10.7 in Phase 2 under cost pressure (new initiative
waiting, backlog accumulating) will pick Option 2 because Option 2
ships. The governing plan should be saying *"Default: Option 1. Option
2 is available if and only if a named condition is met."*

**Recommendation:** State Option 1 (defer portability) as the default,
and name the conditions under which Option 2 is acceptable. Candidate
conditions: (a) the named target repo has independent evidence of
portability safety (e.g., its own reliability testing), and (b) the
compensatory analyst-lane work is budgeted in advance, not promised
indefinitely. Draft text in §3.

### F6 — `compile_decision_inputs.py` is load-bearing but floating

**Severity:** medium.

**Evidence:**

The digest script `scripts/internal/compile_decision_inputs.py` is
referenced in:

- §3 Key Definitions (implicitly via "decision-inputs digest")
- §8.1 Phase 2 Inputs: *"Decision-inputs digest (§15) — auto-generated summary..."*
- §12 Risks last row: *"digest script flags missing subsections nightly"*
- §15.4 Digest generation: specifies globbing, parsing, grouping, archival, missing-subsection flagging
- §15.6 Write-discipline enforcement: *"Digest script nightly report flags missing subsections at the path level"*
- §15.8 Durability: *"a ~50-line script"*

But there is no Work bullet under any primitive that says "implement
`compile_decision_inputs.py`." It is most naturally Primitive C's
responsibility (KB / templates / planning scaffolding) but §5-C Work
bullets don't mention it. §5-C Readiness mentions
`/create-plan` and `/create-adr` skills but not
`/compile-decision-inputs`.

**Implication:** The entire read-surface of the decision-inputs hybrid
pattern (§15's load-bearing half) depends on a script that no primitive
owns. It is an orphan dependency.

The script is small (the plan itself says ~50 lines) and operator could
just write it, but the governing plan is supposed to trace every piece
of load-bearing infrastructure back to a primitive's readiness/validation
gates.

**Recommendation:** Add to Primitive C Work: "Implement
`scripts/internal/compile_decision_inputs.py` and `/compile-decision-inputs`
skill as specified in §15.4." Add to Primitive C Phase 0 Readiness:
"Digest script runs; smoke-tested; first digest generated from Phase 0
closeouts." Draft text in §3.

### F7 — `harness_assumptions.md` "brittleness signal" / "refresh trigger" entries need schema discipline

**Severity:** low-medium.

**Evidence:**

§5-C Work bullet on harness_assumptions: *"Entries use the structure
`assumption → observation supporting it → brittleness signal → refresh
trigger`."*

This is a 4-field schema for a live operational register. But:

- "Brittleness signal" is not defined anywhere. Is it a test? A
  log-string pattern? A heuristic?
- "Refresh trigger" is also undefined. Is it an operator-owned cron? A
  CI check? A hook on a specific file?
- §5-C Phase 0 Readiness says "≥5 initial entries" but provides no
  worked example.

**Implication:** The register is defined as a structured register but
its structure is not machine-checkable. Without a worked example, authors
filing entries will use different interpretations of "brittleness signal"
(some will put log patterns, some will put heuristics, some will put
natural-language narrative). Within 2-3 sessions, the 4-field schema
will collapse into free-form prose.

**Recommendation:** Add to §5-C Work: a single worked example entry,
with ≥1 brittleness signal that is a grep pattern and ≥1 refresh
trigger that is an operator action with observable precondition. Draft
text in §3. This is a 15-minute fix and substantially improves the
register's durability.

### F8 — GC-proposal acceptance criterion is gameable

**Severity:** medium.

**Evidence:**

§11-D Primitive D kill criterion: *"<1 GC-report proposal accepted
(outflow working) → rewrite templates or retire the GC half"*

§5-D Phase 1 Validation: *"≥1 GC-report proposal accepted during the
proving run (outflow working)."*

§13 Success Criterion #15: *"GC-report proposals accepted ≥1 time during
the proving run (archivist outflow working)."*

**Implication:** The threshold is ≥1 acceptance over the entire proving
run. For a tool whose purpose is ongoing entropy reduction, ≥1 is
trivially clearable — the operator accepts a trivial stale-reference
removal early in the run and the primitive is validated.

This is a milder version of the self-sympathetic threshold pattern
analyst-a flagged in draft-2 finding 2.5.

**Recommendation:** Tighten the criterion. Candidate: "≥3 GC-report
proposals accepted, **across ≥2 distinct categories** (stale entries /
dead skills / obsolete policies / orphan artifacts / expired evidence)
during the proving run." The "≥2 distinct categories" clause prevents
the "accept 3 trivial stale-ref removals" failure mode. Draft text in §3.

### F9 — §13 Success Criterion #17 requires the digest script but Primitive C doesn't ship it (ties to F6)

**Severity:** low, bundles with F6.

**Evidence:**

§13 #17: *"Every primitive closeout, sub-plan outcome, preflight report,
proving-run report, and shape audit includes a Phase 2 Decision Inputs
subsection per §15; digest script regenerates nightly without flagging
missing subsections."*

This is a platform-level success criterion that explicitly depends on
the digest script. But the digest script is not a named deliverable of
any primitive (F6).

**Recommendation:** Bundle with F6's fix. If Primitive C picks up the
digest script as Work + Readiness, this success criterion has a clear
owner.

### F10 — Legibility scorecard floor is operator-deferred and gameable

**Severity:** low-medium.

**Evidence:**

§6.4 item 10: *"score meets a documented floor (operator-set in sub-plan
under Primitive C)"*

§5-C Phase 1 Validation: *"Legibility scorecard re-scored at end of
Phase 1 with score equal to or better than Phase 0 baseline."*

**Implication:** The floor is deferred to a Phase 0 sub-plan. The Phase
1 Validation baseline is the Phase 0 first score. Combining these: the
primitive's author sets its own floor and the baseline for Phase 1
measurement is set by the same author at the same time.

This is exactly the self-adjudication pattern analyst-a flagged in
draft-2 finding 2.5. Analyst-a's own fix — require external evidence
(grep, PR citation) — doesn't apply cleanly to legibility (a scorecard
has no natural external witness). But the floor-setting authority
should be externalized somehow: either the floor is pre-committed in the
governing plan (e.g., ≥7/10 items pass), or it is set in ADR 001
(visible to review), or it is set by the review lane, not the author.

**Recommendation:** Commit to a provisional 7/10 floor in the governing
plan, noting that the sub-plan may tighten it after the initial scorecard
but cannot loosen it. Draft text in §3.

### F11 — Goal #8 (active triage) is split between two primitives with no ownership disambiguation

**Severity:** low.

**Evidence:**

§2 Goal #8: *"Active issue triage — issues are flagged, logged, and
triaged by event-driven signals, not operator discovery after the fact."*

§5-B Goals served: *"#1, #4, #6, #7, #8 (active triage, via tool-risk
approval classes)"*

§5-E Goals served: *"#8 (active triage), #9 (durable
near-instantaneous messaging)"*

**Implication:** Goal #8 is served by both B (tool-risk approval classes)
and E (event-driven triage automation). At Phase 1 Validation time, if
the approval-class mechanism is working but the event-driven triage is
not, which primitive fails the goal? Conversely, if event-driven triage
ships 60% of issues but tool-risk has a violation, which one is the
kill trigger?

§11-B and §11-E both have kill criteria that could fire on this goal,
but the goal doesn't say which one is load-bearing for goal #8 success.

**Recommendation:** Add sub-goal breakdown to §2 Goal #8 text: "issue
discovery via event-driven signals (Primitive E)" + "high-risk actions
escalated via approval classes (Primitive B)." Or: move approval-class
citation out of Goal #8 (tool-risk is more naturally goal #13 rollback
or goal #14 ADR). Draft text in §3.

### F12 — Event schema versioning not addressed for the Phase 0 → Phase 1 transition

**Severity:** medium.

**Evidence:**

§5-A Phase 0 Readiness: *"Event schema finalized; committed."*

But Primitive H (Phase 1) builds a replay harness that reconstructs
lifecycles from the event corpus. If the event schema is "finalized" at
Phase 0 but then needs to evolve during Phase 1 (new event classes for
failure-injection, additional IDs for replay matching), Primitive H has
to either (a) only replay events emitted after the evolution (breaking
Phase 0 → Phase 1 continuity), or (b) support schema migration.

Similarly, Primitive A's Phase 1 Validation says the *proving-run
experiment* is fully reconstructable from trace corpus alone — which
requires that any schema evolution during Phase 1 is replay-compatible
with Phase 0 events.

The plan doesn't name a schema-versioning policy.

**Recommendation:** Add to §5-A Work: "Event schema carries a
`schema_version` field; Phase 0 schema is v1; additive evolutions are
v1.N; breaking changes are v2 with an explicit migration plan." Draft
text in §3. This is 2 lines but prevents a category of silent replay
failures.

### F13 — §16 Delta From Draft 4 omits the preflight-item-10 substitution substance

**Severity:** low (editorial).

**Evidence:**

§16 Delta From Draft 4 records the preflight swap: *"Preflight checklist
(§6.4) swaps the replay item (Primitive H, not available at preflight
time) for the agent legibility item (Primitive C). Preflight remains a
10-item gate."*

The Delta notes the swap but does not note the substantive difference
(F4): replay tests data-reconstruction, legibility tests repo
navigability. A Delta section should either justify the swap on
substance or flag it as an acknowledged gap pending further thought.

As-is, the Delta reads as "preflight is still 10 items, so the coverage
is preserved." Counting items is not a coverage statement. The Delta is
a governance artifact; it should be accurate.

**Recommendation:** Rewrite the Delta bullet to either acknowledge the
F4 gap ("this swap preserves gate cardinality but the surfaces tested
differ; see F4 follow-up") or reflect the F4 fix once adopted. Cheap
fix. Draft text in §3.

---

## 3. Concrete Revision Proposals

Priority ordered. Each block is drop-in replacement text for the named
section; `[unchanged]` indicates lines to preserve.

### 3.1 F1 — Add soft re-evaluation trigger for usage-based kill criteria

**Add to §11 as a new paragraph before the table:**

```
Usage-based kill criteria have a known unfalsifiability trap: a primitive
that sees below-threshold activity during a thin proving run (including
the §6.1 methodology-overhaul pivot) produces no evidence for or against
its kill criterion. To avoid accreting unfalsifiable primitives into
Phase 2 as "no evidence yet, keep alive," every kill criterion below
carries an implicit **soft re-evaluation trigger**: if a primitive's
activity during the proving run is below the threshold needed to
evaluate its kill criterion, the primitive is flagged at Phase 2 as
"insufficient evidence" and explicitly scoped for a follow-up evaluation
window (either in Phase 2 planning or in Phase 3 execution), with
named conditions for that evaluation. The governing plan's default for
an "insufficient evidence" primitive is **re-evaluate in Phase 3**, not
"keep alive indefinitely." This preserves the usage-based discipline
while closing the unfalsifiability trap.
```

And in §8.2 Decisions, add a new item:

```
5. **Insufficient-evidence primitives.** For any primitive flagged at
   Phase 1 close as "insufficient evidence" (activity below the kill-
   criterion denominator), Phase 2 records whether to retire, re-scope,
   or re-evaluate in Phase 3. Retire requires explicit justification; the
   default is re-evaluate.
```

### 3.2 F2 — Split Primitive D GC half to Phase 1

**Revise §5-D Work:**

```
- `scripts/internal/archivist.py` — scheduled (nightly + end-of-session)
  script. Reads events, inbox, PR outcomes, task completions. Produces
  **one Phase 0 output** and **one Phase 1 output**:
  - **(Phase 0, inflow)** `knowledge/_candidates/<date>_lessons.md` —
    templated candidate lessons, incident candidates, token-efficiency
    outliers for operator promotion. Readiness: scaffolding + targeted
    unit tests against seeded fake-event fixtures.
  - **(Phase 1, outflow)** `knowledge/_candidates/<date>_gc.md` — entropy
    report: stale KB entries, dead skills, obsolete policy versions,
    orphan artifacts, KB entries where linked evidence has expired.
    Readiness: script present and smoke-tested against fake KB state
    (same seed fixtures as inflow); full activation begins when the KB
    has accumulated ≥2 weeks of promoted entries.
- Operator reviews candidates on each side and approves.
- Session postmortem: end-of-session trigger writes a per-session handoff
  into MEMORY.md + feeds candidates into the archivist queue.
- Not a lane. Invokable as a skill from any lane for real-time curation.
```

**Revise §5-D Phase 0 Readiness:**

```
- Archivist script runs nightly and on end-of-session hook for the
  inflow (lessons) output; targeted tests cover templating and
  event-reading.
- GC-outflow code path present and smoke-tested against seeded fake KB
  state; activation gated on ≥2 weeks of KB accumulation.
- Candidate file formats (both lessons and GC) committed; operator
  review workflow documented for each.
- `/run-archivist` skill available for ad-hoc invocation with
  `--mode lessons` and `--mode gc` flags.
- Rollback path validated: candidate-to-promoted moves tracked; a
  promotion can be reverted by moving content back into `_candidates/`.
  Stale-marking or deletion can be reverted via git.
```

**Revise §5-D Phase 1 Validation:** keep existing; also tighten F8:

```
- ≥1 promoted lesson observably cited downstream during the proving run.
- Candidate-to-promoted ratio ≥10% weekly (inflow).
- ≥3 GC-report proposals accepted during the proving run, across ≥2
  distinct categories (stale entries / dead skills / obsolete policies /
  orphan artifacts / expired evidence).
- Session postmortems trigger reliably at end of each proving-run
  session.
- KB net growth is positive but bounded: ratio of inflow to outflow
  demonstrates curation discipline.
```

**And update §11-D kill row correspondingly:**

```
| D — Archivist (inflow Phase 0; outflow Phase 1) | Candidate-to-promotion rate <10% across the proving run (lessons inflow) OR <3 GC-report proposals accepted across ≥2 distinct categories (outflow) → rewrite templates or retire the GC half |
```

**And §13 Success Criterion #15:**

```
15. GC-report proposals accepted ≥3 times across ≥2 distinct categories during the proving run (archivist outflow working).
```

### 3.3 F3 — Split Primitive B, or add a sub-deliverables table

**Option A (recommended): split B into B1 (dispatch / skill) and B2 (prompt-policy / tool-risk).**

Rename existing §5-B to §5-B1:

```
### Primitive B1 — Adaptive Dispatch and Skill Improvement (Phase 0)

**Goals served:** #1 (self-improving), #4 (intent-aware delegation), #6 (lane/model selection).

**Work:** [existing items 1, 2 from draft 5 §5-B]
- Close SP-5-02 adaptive dispatch ...
- Skill promotion loop tied to observed task outcomes ...
- Analyst-vs-author routing rules encoded as policy ...

**Phase 0 Readiness:** [existing items for dispatch and skill]
**Phase 1 Validation:** [existing items for dispatch and skill]
```

And add new §5-B2:

```
### Primitive B2 — Prompt-Policy Registry and Tool Risk (Phase 0)

**Goals served:** #7 (well-engineered prompts), #8 (active triage, via approval classes), supports #1, #6.

**Work:**
- Prompt-policy registry (versioned contract per lane type and task type).
- Prompt-policy change discipline (trigger / expected effect / rollback condition commit fields; pre-commit lint).
- Tool risk registry at `.claude/rules/tool_risk_registry.md`; approval-class reference per task type.
- Policy candidate → confirmed lifecycle.

**Phase 0 Readiness:**
- Registry exists; initial policies for each lane type with approval-class refs.
- Commit-message linter for policy-change discipline fields.
- Tool risk registry committed; each current prompt-policy references it.
- Rollback path validated (policy version pin).

**Phase 1 Validation:**
- Prompt-policy version cited in ≥90% of traces.
- Zero policy changes landed without trigger/expected-effect/rollback fields.
- Zero approval-class violations during the proving run.
```

**And update §11 to split B's kill row:**

```
| B1 — Adaptive dispatch + skill (Phase 0) | Zero skill promotions/edits where the commit message cites a specific trace ID or incident fingerprint across the proving run → revert to manual skill curation |
| B2 — Prompt-policy + tool risk (Phase 0) | ≥3 approval-class violations (high-risk action taken without required approval) during the proving run → revisit tool risk registry classification boundaries. Also: <50% of proving-run traces cite a prompt-policy version → registry did not land; freeze in advisory |
```

**Option B (fallback if operator prefers one primitive):** keep §5-B
unified; add a "Deliverables" sub-table at the top of §5-B mapping each
of the 7 deliverables to a row in the readiness and validation columns.

### 3.4 F4 — Preflight item 10 rewritten as end-to-end data discipline probe

**Replace §6.4 row 10:**

```
| 10 | End-to-end data discipline | Pick one task completed during preflight; assert its trace corpus (Primitive A), message bus state (Primitive E), KB artifacts (Primitive C), and task-packet state are mutually consistent: no orphan events, no lane-attribution mismatches, no task-packet state contradicting its completion event. **Legibility scorecard (Primitive C) is also re-scored at Phase 0 close and a floor is met (see §10) but is not item 10.** |
```

**And re-number: add a new checklist sub-item or fold legibility into
item 8 (KB integration):**

```
| 8 | KB integration | At least one KB entry (NOTES, PLAYBOOK, anti-pattern, incident, or ADR) created during preflight; legibility scorecard re-scored at preflight close with score ≥7/10 (or whatever floor is set in ADR 001) |
```

**And update §16 Delta:**

```
- **Preflight checklist (§6.4)** item 10 is now an end-to-end data-discipline probe across Primitives A + E + C (replacing the replay item, which moves to Phase 1 Validation under Primitive H). The legibility scorecard moves into item 8 (KB integration) rather than occupying its own row. Preflight remains a 10-item gate and now tests a genuinely different surface from item 1 (trace reconstruction): item 1 tests "can we reconstruct?", item 10 tests "are the reconstructed pieces mutually consistent?"
```

### 3.5 F5 — §10.7 state the default Phase 2 fallback

**Revise §10.7's "must either" paragraph:**

```
If H is demoted under its kill criterion (§11-H) or fails to complete
validation by end of Phase 1, the **default is Option 1 below; Option 2
requires all named conditions to be met.**

**Option 1 (default): defer the portability decision until H is rebuilt
and validated.** Pushes portability to Phase 3+. The Phase 2 gate still
produces a successor plan whose first item is H rework, but that plan
does not commit to a target repo until H completes validation.

**Option 2 (conditional): accept the portability decision with
compensatory scoping.** Conditions, all required:

- The named target repo has independent reliability evidence (e.g., its
  own CI, its own integration tests, recent production shipping history)
  that the Phase 2 report cites explicitly.
- The compensatory analyst-lane discovery work is budgeted in advance at
  ≥X analyst-days (X recorded in Phase 2 report) and the budget is
  drawn before port begins, not promised.
- The first-repo port is explicitly framed as a reversibility-first
  experiment with a kill trigger defined at port start.

If any of the three conditions is unmet, the plan defaults to Option 1.
```

### 3.6 F6 / F9 — Pull `compile_decision_inputs.py` under Primitive C

**Add to §5-C Work:**

```
- Implement `scripts/internal/compile_decision_inputs.py` and the
  `/compile-decision-inputs` skill as specified in §15.4. Script is ~50
  lines; scope: glob subsections, group by prompt content, generate
  digest, snapshot nightly, flag missing subsections.
```

**Add to §5-C Phase 0 Readiness:**

```
- Digest script runs; smoke-tested against seeded subsection fixtures;
  first digest generated from Phase 0 primitive closeouts and sub-plan
  outcomes.
- `/compile-decision-inputs` skill available for operator-triggered
  regeneration.
```

**No change to §13 #17 needed; it now has a clean owner.**

### 3.7 F7 — Worked example for harness_assumptions schema

**Add to §5-C Work under the `harness_assumptions.md` bullet:**

```
Worked example:

```
### Session-death threshold

**Assumption:** Spawned sub-agents die silently at approximately 15 minutes
or 700 KB context, whichever first.

**Observation supporting:** #2120 incident, #2215 fix PR, #2271 retrospective.

**Brittleness signal:** grep pattern in agent-invocation logs for
output length > 700KB with no completion event. Pre-commit check on
`.claude/rules/70_agent_reliability.md` to flag if the threshold is
edited without an accompanying ADR.

**Refresh trigger:** Operator action on next Claude Code release that
changes sub-agent runtime semantics; measured by a one-shot spawned
agent that reads the release notes and reports change-delta to the
archivist.
```

Entries follow this structure. Brittleness signal must be a
machine-observable pattern (grep pattern, CI check, hook precondition);
"natural language signal" is insufficient.
```

### 3.8 F10 — Legibility scorecard provisional floor in governing plan

**Revise §6.4 item 10 and §5-C Phase 1 Validation to commit to a floor:**

```
| 10 (or folded into item 8 per F4) | Agent legibility | Legibility scorecard re-scored at end of Phase 0; score ≥ 7/10 items passing. Sub-plan under Primitive C may tighten the floor (to 8/10 or 9/10) but may not loosen it. ADR 001 records the initial 7/10 floor and the sub-plan records any subsequent tightening. |
```

**And update §5-C Phase 1 Validation:**

```
- Legibility scorecard re-scored at end of Phase 1; score is equal to
  or better than Phase 0 baseline, AND meets the floor set in ADR 001
  (default 7/10 per §6.4 item 10).
```

### 3.9 F11 — Disambiguate Goal #8's ownership

**Revise §2 Goal #8:**

```
8. **Active issue triage** — issue *discovery* is driven by event-driven
   signals, not operator discovery after the fact (Primitive E); high-risk
   actions are escalated via approval classes (Primitive B2) before they
   surface as issues at all.
```

### 3.10 F12 — Event schema versioning

**Add to §5-A Work as a new bullet after "Finalize event schema..."**:

```
- Event schema carries a `schema_version` field. Phase 0 schema is v1;
  additive evolutions (new fields, new event classes) are v1.N and are
  replay-compatible; breaking changes require v2 with an explicit
  migration plan filed as a sub-plan under Primitive A. Replay harness
  (Primitive H) asserts v1.N-to-v1.M compatibility.
```

### 3.11 F13 — §16 Delta From Draft 4 preflight bullet rewrite

**Revise §16 third-to-last bullet:**

```
- **Preflight checklist (§6.4)** — draft 4 item 10 tested replay (a
  data-reconstruction probe via Primitive H). Draft 5 moves replay to
  Phase 1 Validation under Primitive H (since H does not exist at
  preflight time) and replaces item 10 with a data-discipline probe
  spanning Primitives A + E + C (see §3.4 of the draft-5 analyst-b
  review). Legibility scorecard folds into item 8 (KB integration).
  Preflight remains a 10-item gate and tests a genuinely different
  surface from item 1 (trace reconstruction).
```

---

## 4. Grade and Adoption Recommendation

### Grade: **B+**

Analyst-a graded draft 2 at **B**. Draft 5 improves on draft 2 along
every axis of analyst-a's critique (23-of-23 findings resolved or
obviated, most with stronger mechanism than analyst-a's minimum), and
fixes two of the three partial dispositions (S3 and R1) that held draft
2 below B+ in the first place.

Draft 5 is not at **A-** because the fresh-eyes findings F1-F6 are
real load-bearing gaps. In particular:

- F1 (kill-criteria falsifiability under thin proving run) is the kind
  of blind spot that, if unaddressed, produces a Phase 2 with no hard
  decision to make — which defeats the phase's purpose.
- F2 (Primitive D's GC report is Phase-0-labeled but Phase-1-substantive)
  and F4 (preflight item 10 surface coverage gap) are honest-but-load-bearing
  structural issues that were introduced by the draft-5 delta itself.
- F3 (Primitive B's weight inflation) is the "where did the ambition go"
  question analyst-a's draft-2 finding 2.3 posed. The answer in draft 5
  is "into Primitive B"; that is not obviously worse than "across 8
  primitives" but it makes B heavy enough to warrant a split.
- F5 (§10.7 default) is the decision-hygiene gap the plan is trying to
  close.
- F6 (`compile_decision_inputs.py` floating) is small but embarrassing
  for a plan that just spent §15.8 framing the digest pattern as
  durable infrastructure.

Draft 5 would reach **A-** with F1/F2/F3/F4/F5/F6 addressed. F7-F13 are
quality-of-life improvements; useful but not blocking.

### Adoption recommendation: **Revise → Draft 6 → Promote**

Draft 5 is close enough to promotion-ready that a full revision cycle
(with another fresh-eyes pass) would be over-investment. I recommend:

1. Orchestrator/operator applies F1/F2/F3/F4/F5/F6 (the six load-bearing
   fixes) with the draft text in §3 above.
2. Operator decides on F7-F13 piece by piece; accept, reject, or defer
   each as an Open Item.
3. Commit as `governing_plan.draft6.md`.
4. Dispatch a **short** review (1-2 hours) to either analyst-b again or
   a fresh analyst lane focused narrowly on "did the F1-F6 fixes land
   correctly and introduce no new structural gaps."
5. If that review returns clean, rename draft 6 to `governing_plan.md`,
   archive drafts 1-5, and open the Phase 0 execution work.

Timeline: I would not be surprised if the whole cycle (operator edits +
commit + review + promote) runs in a single focused session, as the
draft-2 cycle did.

Promoting draft 5 directly as `governing_plan.md` without addressing
F1/F2/F3/F4/F5/F6 would leave known load-bearing gaps in the canonical
artifact, which is exactly what the analyst-a and analyst-b review
cycles were supposed to catch. The investment-to-return ratio of one more
revision pass is strongly positive.

---

## 5. Open Questions Back to Orchestrator / Operator

1. **F1 (soft re-evaluation trigger):** Does the proposed mechanism
   ("insufficient evidence" → Phase 3 re-evaluate, not "keep alive
   indefinitely") match operator intent? Alternative: "insufficient
   evidence" routes to retire-by-default with operator override. The
   weaker default (re-evaluate) is what I drafted; the stronger default
   (retire) is available.

2. **F3 (Primitive B split):** Option A (split into B1 + B2) or Option B
   (keep one, add deliverables table)? Split has structural advantages;
   unified has governance simplicity.

3. **F4 (preflight item 10):** Does the operator find the "end-to-end
   data discipline" probe substantial enough as a Primitive C + A + E
   cross-check, or would they prefer a different probe? Candidates:
   "pick one merged PR during preflight, assert its full causal
   chain from task-packet dispatch → events → completion → KB is
   intact end-to-end."

4. **F5 (§10.7 default):** Operator comfort with pre-committing to
   "defer portability" as the governing-plan default? Or does the plan
   deliberately want to leave this to Phase 2 judgement? My argument is
   that pre-commitment protects Phase 2 from cost-pressure Option-2
   selection.

5. **F6 (digest script ownership):** Primitive C is the natural home.
   Any objection, or should it live as a standalone "platform
   infrastructure" line item outside the 8 primitives?

6. **F10 (legibility floor):** Provisional 7/10 OK as a governing-plan
   default, or does the operator prefer to leave the floor entirely to
   the sub-plan + ADR 001?

7. **F12 (schema versioning):** Is this the right place for it, or does
   the operator prefer to file schema versioning as a sub-plan item
   under Primitive A and leave it out of the governing plan?

8. **Not-a-question but worth flagging:** the review→revision cycle
   that produced drafts 1→5 in ~1 day is itself load-bearing evidence
   for the Phase 2 Decision Inputs hybrid pattern's durability, noted in
   draft 5's own §18 Phase 2 Decision Inputs surprise-finding line
   (line 947). I would carry that observation forward into ADR 001 as
   the operator suggested; the pattern worked in miniature on the
   governing plan itself.

---

## 6. Note on the BLOCKER artifact

`plans/steward_platform/draft5_review_BLOCKER.md` was written by this
lane when draft 5 and its handoff did not yet exist in the repo. The
orchestrator's recovery message instructed: *"please delete or supersede
it with the review artifact when produced."* This review artifact
supersedes it. The BLOCKER file is deleted in the same commit that lands
this review.

— analyst-b
