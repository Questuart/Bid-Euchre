# Steward Platform Governing Plan — Draft 2 Review (analyst-a)

**Date:** 2026-04-22
**Reviewer:** steward-analyst (lane analyst-a)
**Target:** `plans/steward_platform/governing_plan.draft2.md`
**Prior artifact:** `plans/steward_platform/governing_plan.md` (draft 1, PROPOSED, 2026-04-22)
**Handoff:** `plans/steward_platform/draft2_review_handoff.md`
**Review stance:** skeptical; prefer simpler solutions; flag over-engineering;
propose better alternatives; judge against the *best plausible plan* standard,
not the *workable plan* standard.

---

## TL;DR

Draft 2 is a materially better plan than draft 1. The load-bearing critiques
from the prior review — falsification-test placement, horizontal-scope
over-reach, primitive inflation, KB taxonomy, archivist-as-lane, meta-layer
commitment, and missing kill criteria — are all at least partially resolved,
and most are fully resolved. The reframe to *prove before port* with an
end-to-end research run as the Phase 1 falsification test is sound; it raises
the bar from "does the contract port" to "is this platform worth porting at
all," which is the right first question.

Draft 2 does, however, introduce new weaknesses of its own:

1. An internal inconsistency about primitive count (plan says both 7 and 8).
2. Goal inflation from 12 to 16, including an open-ended "any further
   improvements" clause (#16) that makes the Phase 0 scope permanently
   elastic.
3. A Phase 0 time-box (6-8 weeks) that does not plausibly fit the declared
   primitive set, especially after adding Primitive H (Reliability Lab).
4. A decision-inputs ledger whose write-discipline, tag taxonomy, and
   separation from existing ADR/incident/playbook surfaces are
   under-designed and at real risk of becoming a graveyard.
5. Several kill-criteria thresholds that the author has set sympathetically
   toward the primitive's own survival.
6. A proving-run framing that does not hedge against data-sparsity: the
   primary candidate (GBT retrain on human-gameplay capture) assumes the
   browser game has accumulated enough data to drive a full retrain cycle,
   which is not established.
7. Under-specified parallel target-repo audit (§4.2).
8. A fixed-constraint ("Platform-11/13 postponement pattern not applicable")
   that is asserted without stating what has changed since those
   postponements. The reasoning deserves to be written down rather than
   carried as a conversational premise.

**Grade: B (up from C+ on draft 1).** Approve with revisions. The plan
should not enter Phase 0 execution until the seven revisions in §3 below are
applied. Nothing in this review calls for rework from scratch or for
challenging the fixed constraints the operator has set aside — with one
explicit exception flagged in §3.7.

---

## 1. Per-Finding Disposition Of Prior Critique

Prior review summary (reproduced from the handoff recap). For each finding I
classify: **RESOLVED** (fully addressed), **PARTIAL** (addressed but with a
remaining gap), **MISSED** (not addressed), or **OBVIATED** (superseded by a
different framing).

### 1.1 Strategic findings

| # | Prior finding | Disposition | Evidence / remaining gap |
|---|---|---|---|
| S1 | Plan conflated operator-UX/context-management pain with a portability pain and proposed one unified solution | **OBVIATED** | Operator explicitly separated the two pains in the trajectory note. Draft 2 §1 scopes the plan to the vertical-ambition problem (on Bid-Euchre) and defers the cross-project allocation problem to Phase 2. The conflation is gone. |
| S2 | Falsification test (cross-repo adoption) was deferred to Phase 4 — architecture was built on a contract the plan never validated | **RESOLVED** | Draft 2 §1, §6 moves the falsification test to Phase 1 and reframes it as a research proving run. The reframe is the right move. §6.3 separates research from platform evaluation. |
| S3 | ~12 new primitives in a plan that preached "adapt before replace" | **PARTIAL** | Draft 2 §5 lists 8 primitives (A-H), down from the implied ~12 but above the prior recommended ≤5. Each is tied to a named goal. The reduction is real, but the count is still aggressive for a 6-8 week Phase 0 (see §2.3 below). Primitive H in particular is a large net-new addition since draft 1. |

### 1.2 Scoping findings

| # | Prior finding | Disposition | Evidence / remaining gap |
|---|---|---|---|
| SC1 | "Make steward excellent first" was not scoped | **RESOLVED** | Draft 2 §2 names 15 concrete capabilities (plus the open #16) and §5 binds each primitive to specific capabilities. The scope of "excellent" is now enumerable. |
| SC2 | KB taxonomy (7 dirs × 3 repos + 7-dir meta-KB) was premature scaffolding | **RESOLVED** | Draft 2 §5-C collapses to a 4-item skeleton (NOTES, PLAYBOOKS, incidents/, INDEX) plus two reasonable supplements (`anti_patterns.md`, `adr/`). Meta-KB deferred. This is a proportional design. |
| SC3 | Archivist-as-lane was the wrong tool for curation | **RESOLVED** | Draft 2 §5-D specifies a scheduled script + end-of-session hook, not a persistent lane. §3 Key Definitions reinforces this. |

### 1.3 Directive findings

| # | Prior finding | Disposition | Evidence / remaining gap |
|---|---|---|---|
| D1 | Phoenix commitment from phase one was premature absent named workflows | **PARTIAL** | Draft 2 §5-A names two workflows (reproducibility audits; session-archive evaluation) and adds a kill criterion (§11-A). The workflows exist, but both are described at a level that reads like categories rather than workflows. "Trace inspection for reproducibility audits" does not specify which audits, on what cadence, triggered by what signal, read by whom. Workflow sharpening needed (see §3.4). |
| D2 | Meta-steward-home as a new repo was under-justified | **RESOLVED** | Draft 2 §9.5 defers meta-KB to Phase 2; trajectory note specifies meta-home = directory under `~/.claude/`, not a new repo. |
| D3 | Meta-orchestrator as a lane vs. UX pattern was unresolved | **RESOLVED** | Draft 2 §9.1 excludes meta-surface from Phase 0; §7.2 makes the lane-vs-pattern decision an explicit Phase 2 decision output. The question is now scheduled, not papered over. |

### 1.4 Risk findings

| # | Prior finding | Disposition | Evidence / remaining gap |
|---|---|---|---|
| R1 | Target repos (`Fund`, `RIN-SnD`) were not inspected before the plan committed to them as adoptable | **PARTIAL** | Draft 2 §4.2 introduces a parallel one-analyst-shift shape audit. Direction is right, but scope ("one-page inventory," "not gating on Phase 1") is thin for a decision input that will drive a portability go/no-go in Phase 2. See §2.7. |
| R2 | No kill criteria per workstream | **RESOLVED** | Draft 2 §11 has per-primitive kill criteria. Thresholds are uneven — several are too sympathetic to the primitive's survival (see §2.5) — but the mechanism is in place. |
| R3 | No phase gates | **RESOLVED** | Draft 2 §4.1 phases explicitly depend on the previous phase's done-when. Phase 2 is a decision gate whose output is an evaluation artifact (§6.4 and §7). |

### 1.5 Summary scorecard

| Bucket | Resolved | Partial | Missed | Obviated |
|---|---|---|---|---|
| Strategic (3) | 1 | 1 | 0 | 1 |
| Scoping (3) | 3 | 0 | 0 | 0 |
| Directive (3) | 2 | 1 | 0 | 0 |
| Risk (3) | 2 | 1 | 0 | 0 |
| **Total (12)** | **8** | **3** | **0** | **1** |

No prior finding is missed. Three remain partial. The partials are the
primary substance of §2 below.

---

## 2. New Findings Introduced By Draft 2

### 2.1 Primitive-count inconsistency in the plan text

**Severity:** low (editorial) but a symptom of draft-authoring haste that
merits mention because this is a governing plan.

**Evidence:**
- §4.1 Phase 0 row says: *"Close existing debt and build out the full vertical stack (**7** primitives) inside Bid-Euchre."*
- §5 heading: *"Workstreams — The **8** Primitives."*
- §5 body lists A, B, C, D, E, F, G, H — eight primitives. Primitive ordering also places G before H in the heading structure but H is described before G in reading order (B, C, D, E, F, H, G). See §3.1.
- §12 Risks row 1: *"**7** primitives are a closed list."*
- §13 Success Criteria #1: *"All **8** primitives reach Phase 0 done-when."*

**Implication:** A governing plan disagreeing with itself on how many
workstreams Phase 0 contains is a freshness-of-drafting tell. More
substantively, a future reader or implementer grepping for "7 primitives"
will read a count that no longer matches the plan's intent. Fix is trivial
but required before committing.

### 2.2 Goal-count inflation and the infinite-scope clause (#16)

**Severity:** medium.

Draft 2 §2 lists 16 goals where draft 1 had implicit goals inside sections.
The expansion is explained — goals #13 (rollback), #14 (ADR), #15
(reliability lab) came from the synthesis trajectory with the operator. Goal
#16, however, reads:

> 16. **Any further improvements** the governing plan later identifies —
>     this list is a floor, not a ceiling.

This clause is not a goal. It is a standing license for scope expansion. A
governing plan is the scope-lock artifact for a phase; it cannot also carry
a clause that preauthorizes widening the scope-lock. The operator's stated
intent (the 15-list is a floor) is reasonable; the *encoding* of that intent
into the goal list is not.

**Parallel anti-pattern:** The plan's own §12 Risks row 1 lists "Phase 0
hardening scope creep" with mitigation "7 primitives are a closed list; new
gaps are filed, not absorbed." Goal #16 contradicts that mitigation
directly. Either the list is closed (then #16 comes out) or it is open
(then the risk row is wrong).

### 2.3 Phase 0 time-box unrealistic for the declared primitive set

**Severity:** high.

§12 Risks row 1 states the time-box as "6-8 weeks." The declared work in §5
is, at minimum:

| Primitive | Coarse estimate (weeks, serial) | Notes |
|---|---|---|
| A — Trace + Phoenix + event-driven monitoring | 2-3 | Phoenix single-container deploy is cheap. Replacing polling with event-driven monitoring is a cross-cutting refactor. |
| B — Adaptive dispatch close + skill loop + prompt-policy registry | 2-3 | SP-5-02 adaptive dispatch has been partial for months. Prompt-policy registry is net-new. |
| C — KB skeleton + planning templates + ADR tooling + MEMORY compaction | 1-2 | Mostly content/scaffolding + a tiny amount of code. |
| D — Archivist script + end-of-session hook | 1 | Straightforward if the event corpus is available. |
| E — Bus metrics + active triage automation + triage skill wiring | 1-2 | Bus metrics are cheap; active triage automation is the harder half. |
| F — Token economy Slice F evaluation + metrics wiring | 1-2 | Slice F protocol (#2716) is explicitly gated on 1-2 weeks of observation. That observation window eats ~25% of the low-end time-box. |
| G — Debt closeout (`worktrees.py` 44 hard-blocks, `token_economy.py` 22, plan retirement) | 1-2 | Linear but extensive. |
| H — Replay harness + failure-injection scenarios + automated postmortem + rollback validation | 2-4 | Largest new scope. Four distinct mini-primitives under one heading. |
| **Naive serial sum** | **11-19 weeks** | Pre-parallelism, pre-integration, pre-slack. |

With four author lanes (two platform, two browser) and coordination
overhead, realistic parallel compression is ~40-50%, not 70%+. Call it 7-12
weeks on good execution with no blockers — and the fleet has blockers.

Two further complications the plan under-weighs:

- **Slice F observation window** (Primitive F) is a *calendar-time*
  dependency, not a labor-time dependency. Parallelism cannot compress it.
- **Event-driven monitoring** (Primitive A) is load-bearing for active
  triage (Primitive E), kill-criterion measurement (Primitive H), and the
  archivist input surface (Primitive D). If A slips, three other primitives
  slip with it.

The plan's existing mitigation ("new gaps are filed, not absorbed") does not
address *declared* gaps whose cost was underestimated.

### 2.4 Decision-inputs ledger — graveyard risk and tag-taxonomy design

**Severity:** medium. The handoff explicitly asks for pressure testing here.

The ledger is a good instinct and a plausible solution, but §15 as written
combines a novel artifact, a novel tag taxonomy, a novel write-discipline,
and a novel Phase 2 read-protocol into one untested pattern.

**Graveyard risks:**

1. **Distance between writer and reader.** Entries are written by
   primitives during Phase 0 implementation and read by the Phase 2
   decision-gate analyst 6-16 weeks later. Lessons from ADR practice and
   research-lab notebook practice: artifacts written far from their
   consumer drift toward unreadable shorthand. Mitigation: require a
   *Phase 2-facing summary sentence* in each entry, reviewed on write.
2. **Write-discipline not mechanized.** §15 says "every primitive's
   done-when verification produces at least one ledger entry." There is no
   hook, linter, or CI check proposed to enforce this. The discipline will
   decay under load.
3. **Distinct-from-ADR boundary not drawn.** §5-C already introduces ADRs
   at `knowledge/adr/<NNN>-<slug>.md`. §15 introduces ledger entries. §15
   says ADR and ledger coexist (`adr-trigger` is a tag), but the boundary
   — "write ADR when X, write ledger entry when Y" — is not defined.
4. **Distinct-from-incident boundary not drawn.** `knowledge/incidents/`
   already captures incidents. A ledger entry with tag `kill-signal` + a
   primitive failure sounds a lot like an incident. Again: no boundary.

**Tag-taxonomy concerns:**

- 9 tags is borderline high; tag systems with >8 categories reliably
  collapse toward 2-3 dominant tags in practice. This is documented in
  incident-taxonomy literature and shows up repeatedly in ADR registries.
- `capability-gap` and `kill-signal` overlap heavily; most kill signals
  *are* severe capability gaps.
- `adr-trigger` is process metadata, not a content category. It belongs in
  a status field, not a tag.
- `cost-signal` is under-specified: operator-hours, tokens, and
  complexity-debt are three different things with different decision
  consequences.
- `surprise-finding` is a catch-all that will absorb anything that does not
  fit the other tags — the documented failure mode of "Other" or
  "Miscellaneous" labels.

**Alternative pattern (simpler):**

Rather than a separate ledger file with its own taxonomy, *structure each
sub-plan outcome and each primitive done-when verification to include a
"Phase 2 Decision Inputs" subsection* with a small fixed set of prompts:

```
## Phase 2 Decision Inputs

**Portability readiness:** [statement + evidence link, or "no change"]
**Meta-layer need:** [statement + evidence, or "no change"]
**Kill signal for this primitive:** [yes/no + evidence, or N/A]
**Surprise finding:** [one sentence if any, or "none"]
```

Phase 2 begins by globbing those subsections across all sub-plan outcome
blocks and all primitive closeouts. No separate ledger file; no separate
write-discipline; no decay-prone secondary artifact; 4 prompts instead of 9
tags. Writing happens adjacent to the context that produced the finding.

This is the *best plausible plan* shape, in my view, and considerably
simpler than §15 as drafted.

### 2.5 Kill-criteria thresholds are self-sympathetic

**Severity:** medium.

Kill criteria set by the primitive's author tend to protect the primitive.
Several thresholds in §11 show this tendency:

| Primitive | Threshold as written | Problem |
|---|---|---|
| A — Phoenix | *<5 operator opens across 4 weeks* | Opening the UI is not a value-proxy. 5 opens with no findings is a dead tool that survives. Threshold should be *number of promoted findings* or *number of traces that produced a KB entry*. |
| B — Adaptive dispatch + skill + prompt-policy | *skill promotions/edits driven by outcome feedback = 0* | Zero is a strict lower bound but the "driven by outcome feedback" qualifier is self-adjudicated. One manual edit retrospectively labeled "outcome-driven" keeps the primitive alive. Needs an evidence test: the promotion/edit must cite the specific trace or incident that motivated it. |
| C — KB | *<3 promoted lessons observably cited during the proving run → collapse to single NOTES.md* | Low bar (3), and "observably cited" is author-judged. Proposed: cited by a *downstream PR body* or a *task-packet description* in a way verifiable by grep. |
| E — Messaging/triage | *Active triage produces <20% of issues created* | OK as a rate, but 20% of a denominator of 5 is 1 issue. Add a minimum denominator (e.g., ≥20 issues observed). |
| H — Reliability lab | *<2 replay scenarios pass or <3 failure-injection scenarios exercised* | The plan's own author picks the scenarios; passing the self-chosen minimum is a tautological survival gate. Should be augmented with one *surprise scenario* picked post-hoc (after primitives A/B/E are in) to avoid Goodharting. |

None of these kill the plan. They do make the kill criteria less useful as
honest survival signals. Sharpening is cheap.

### 2.6 Proving-run framing lacks a data-sufficiency contingency

**Severity:** medium-to-high depending on browser-game data state.

§6.1 designates the primary proving-run candidate as "GBT retrain informed
by human-gameplay data captured through the browser-game hosting
infrastructure." Alternatives listed: new-strategy addition, measurement
methodology overhaul.

**Missing prerequisite:** a data-sufficiency check before the proving run
is committed. A GBT retrain needs enough human-gameplay instances to
(a) train meaningfully, (b) hold out a test set with statistical power,
and (c) give the existing rigor apparatus (`.claude/rules/deferred/05_rigor.md`)
real signal. Browser-game hosting is live but session-count and
session-quality — not examined in the plan — determine whether this is
viable in Phase 1 or a Phase 1-bound activity that blocks indefinitely on
user traffic.

**Confound for the platform evaluation:** If data is thin, the research
activity slows, which means the platform gets less exercise (§6.2 rows #1,
#3, #5, #8 all depend on *volume of platform activity during the run*).
§6.3's separation principle ("research failure ≠ platform failure") is
correct at a logical level but does not mitigate this: a thin run does not
fail, it simply does not inform.

**Proposed mitigation (concrete text in §3):** Add a Phase 0 exit check
that measures current human-gameplay data volume against a documented
minimum threshold. If below threshold, pivot the proving run to the
measurement-methodology-overhaul alternative, which stresses the platform's
coordination/learning/rigor apparatus without requiring external data
accretion.

### 2.7 Parallel shape audit (§4.2) is under-specified

**Severity:** low-to-medium.

§4.2 commits to "one analyst-shift" per repo audit producing a "one-page
inventory" covering CI shape, branch conventions, test framework, existing
`.claude/` presence, hosted-service dependencies, tooling conventions.

Two problems:

1. **One analyst-shift** is undefined. An hour? A day? A week of
   part-time? Since the output will gate a Phase 2 portability go/no-go
   decision, the cost should be named.
2. **Output format** does not include the portability-debt categories
   named in `PORTABILITY_MANIFEST.md` (hard-block vs. soft-coupling, top
   offending files, test isolation, lane-layout assumptions). A one-page
   inventory along the audit's existing axes will miss the structural
   questions the adapter contract actually needs answered.

Both are cheap to fix. Proposed revision in §3.6.

### 2.8 Platform-11/13 dismissal needs explicit evidence

**Severity:** low (governance) / medium (credibility).

The handoff's fixed-constraints section reads:

> **Track-record risk:** operator has dismissed the Platform-11/13
> postponement pattern as not applicable; constraints that paused those
> efforts are no longer in place.

The plan itself inherits this dismissal via §12 Risks row 6. But the plan
does not say *what the constraints were* and *what has changed since*.
Without that, the dismissal is a conversational assurance carried forward,
not a durable decision artifact.

The Phase-5 fragmentation (extraction, cross_model, skill_learning,
portability_and_learning — all with `scope_lock.md`; two POSTPONED; one
partially reactivated) is live evidence of the pattern. Treating it as
"not applicable" without naming the delta is a risk worth writing down
even if the operator is confident the delta is real. (This is consistent
with the plan's own Goal #14 — ADR-style decision capture — applied to
the plan itself.)

Proposed revision: add one paragraph to §12 Risks row 6 or to §16 Delta
From Draft 1 naming the three or four concrete constraints that have
lifted since the pattern emerged.

### 2.9 Phoenix workflows under-specified (sharpening of prior Partial D1)

**Severity:** low.

Prior finding D1 is Partial because the two workflows at §5-A read as
categories rather than workflows. Concretely, a workflow has:

- a trigger (what makes the operator or lane open Phoenix)
- a consumer (who reads the output and what they do next)
- a cadence (daily, per-PR, per-incident)
- an output (what gets promoted if useful)

Rewriting the two workflows with these four fields is a 30-minute job and
makes the kill criterion at §11-A measurable against something other than
raw UI opens.

### 2.10 §7.2 item 3 (cmux adoption) re-embeds a draft 1 commitment

**Severity:** low.

§7.2 Decisions #3: *"cmux adoption. Only relevant if portability goes
forward. Shape: workspace-per-project, notification bindings, browser
surfaces, operator action bindings."*

The framing conditional ("only relevant if portability goes forward") is
correct, but the *shape* ("workspace-per-project, notification bindings…")
is a draft 1 directive reimported into a Phase 2 decision rubric that is
supposed to be evidence-driven. If cmux is a Phase 2 decision output, the
plan should not pre-describe its shape; the shape should come from the
evidence. Shape commitments belong in a sub-plan written in Phase 2, not
in the governing plan's Phase 2 rubric.

Small edit: strike the shape description from §7.2-#3 and leave only the
trigger condition.

### 2.11 Primitive H doubles as Phase 2 portability de-risker — coupling risk

**Severity:** low.

§5-H positions the reliability lab as both a Phase 0 primitive *and* a
Phase 2 portability de-risking surface. Good reuse, but it also creates a
design coupling: any decision to cut/prune H in Phase 0 weakens the Phase 2
portability decision. The plan's own kill criterion §11-H demotes H to "a
simpler event-diff assertion set" if scenarios fail — but a demoted H is no
longer a portability de-risker, which changes what Phase 2 can decide.
Worth naming as an internal dependency in §7 or §11.

---

## 3. Concrete Revision Proposals

Each revision here is a direct edit to draft 2. Proposed text in fenced
blocks. Edits are listed roughly in priority order.

### 3.1 Fix primitive-count inconsistency (§4.1, §5, §12, §13)

**§4.1 Phase 0 row — replace:**

```
| 0 | `0_hardening` | Close existing debt and build out the full vertical stack (8 primitives) inside Bid-Euchre | Existing `agent_ops` Phase 0-4 assets |
```

**§5 heading — already reads "8 Primitives"; leave.**

**§5 primitive ordering:** move Primitive G (debt closeout) to follow
Primitive F and Primitive H to its end position. As drafted, the text
introduces H between F and G, which is confusing when G is a gating
non-capability primitive. New order: A, B, C, D, E, F, G, H — alphabetical
and matches the §11 kill-criteria table ordering.

**§12 Risks row 1 — replace:**

```
| Phase 0 hardening scope creep | Time-box Phase 0 at 6-8 weeks; the **8 primitives are a closed list** and every net-new capability request routes to a Phase 2 decision input rather than being absorbed into Phase 0 |
```

**§13 Success Criteria #1 — already reads "All 8 primitives"; leave.**

### 3.2 Delete Goal #16; restate "floor" intent in §2 preamble

**Strike §2 item #16** ("Any further improvements the governing plan later
identifies — this list is a floor, not a ceiling.").

**Add to §2 preamble instead:**

```
The 15 capabilities above are the *closed Phase 0 scope-lock*. Operator or
reviewer proposals for additional capabilities during Phase 0 are filed as
Phase 2 decision inputs (see §15), not absorbed into Phase 0.
```

This preserves the operator's intent (the list is not a hard maximum of
ambition forever) while removing the in-plan license for scope expansion
that §12 Risks row 1 already prohibits.

### 3.3 Rescope Phase 0 to fit the time-box (one of two options)

I do not recommend changing the time-box; I recommend rescoping the work to
fit it. Two options in descending order of preference.

**Option A (recommended): defer Primitive H to Phase 0.5 / early Phase 1.**

Rationale: H is the largest new scope introduced by draft 2. It includes
four distinct sub-primitives (replay, failure-injection, postmortem
generator, rollback validation). Rollback validation in particular can be
pulled into each primitive's own done-when (already the plan's intent at
Goal #13). The remainder — replay harness, failure-injection catalog,
postmortem generator — is valuable but not load-bearing for the proving
run itself. Phase 1 can execute the proving run with H as "work-in-progress
scaffolding" rather than "done-when capability," then tighten H in Phase 2
before any portability port.

**Proposed §5-H replacement:** move Primitive H to a new `§5.1 Phase 0.5
primitive` heading *or* to the Phase 1 execution section. Add a
Phase-0-done-when for rollback validation only:

```
### Primitive G — Existing-Debt Closeout (gated non-capability)

... [existing text] ...

**Done-when:** ... [existing] ... ; every reversible change introduced in
Phase 0 (skill version, prompt-policy version, adaptive-dispatch policy)
has an exercised forward+backward transition recorded, satisfying Goal
#13. [This absorbs the rollback-validation slice of the prior Primitive H
into G without importing the rest of H's scope.]
```

**Option B (acceptable): extend the time-box to 9-12 weeks.**

If the operator insists on keeping Primitive H in full Phase 0 scope, the
time-box needs to be restated. 9-12 weeks with acknowledged buffer is more
honest than 6-8 weeks with an undeclared "and also Primitive H." Pair the
extension with a mid-Phase-0 check-in (around week 6) that recasts the
remainder as Phase 0-a and Phase 0-b if slippage is visible.

### 3.4 Replace the decision-inputs ledger with a structured outcome subsection

**Strike §15 in its current form.** Replace with a substantially shorter
section:

```
## 15. Decision Inputs For Phase 2

Every primitive closeout, every sub-plan Outcome block, and the
proving-run report end with a **Phase 2 Decision Inputs** subsection using
this fixed template:

### Phase 2 Decision Inputs

**Portability readiness:** [one sentence with evidence link, or "no change"]
**Meta-layer need:** [one sentence with evidence link, or "no change"]
**Kill signal for primitive(s) named:** [yes/no with evidence link, or N/A]
**Surprise finding:** [one sentence if any, or "none"]

Phase 2 (§7) begins by grepping these subsections out of all sub-plan
outcomes, primitive closeouts, and the proving-run report. No separate
ledger file; no separate tag taxonomy; write-discipline lives adjacent to
the work that produced the finding, not in a parallel artifact.
```

Four prompts, no taxonomy, no separate file, one `grep` away from the
Phase 2 decision pass. This is the *best plausible plan* shape and is
simpler than §15 as drafted.

If the operator prefers the ledger shape, the narrower fallback change is:

- Collapse tags from 9 → 4 (`portability`, `meta-layer`, `kill`, `surprise`).
  Drop `capability-gap` (subsumed by `kill`), `capability-win` (use
  `meta-layer` + positive sentiment), `target-repo-shape` (put in audit
  itself), `cost-signal` (split into hours/tokens/complexity fields, not
  tags), `adr-trigger` (move to status).
- Add an enforced write hook: primitive done-when verification is not
  accepted until it posts at least one ledger entry with a timestamped
  source pointer. Mechanize via a lightweight precommit check on sub-plan
  outcome files.

### 3.5 Tighten kill-criteria thresholds

**§11 replacement rows** (proposed text; changes in **bold**):

```
| A — Trace/observability | **Phoenix has <3 promoted findings (KB entries, incidents, prompt-policy edits) across 4 weeks → demote to JSONL + notebook only** |
| B — Adaptive dispatch + skill + prompt-policy | **Zero skill promotions/edits where the commit message cites a specific trace ID or incident fingerprint across the proving run → revert to manual skill curation** |
| C — KB | **<3 promoted lessons cited by a downstream PR body or task-packet description during the proving run → collapse to single NOTES.md per repo** |
| E — Messaging/triage | **Active triage produces <20% of issues created, measured over ≥20 observed issues → revert to operator-discovery model** |
| H — Reliability lab | **<2 replay scenarios pass or <3 failure-injection scenarios exercised, **including at least one scenario selected post-hoc by an analyst lane after primitives A/B/E ship** → demote to a simpler event-diff assertion set; postmortem generator deferred** |
```

All unchanged rows (D, F, G) are fine as drafted.

### 3.6 Specify the §4.2 target-repo audit scope and output

**Replace §4.2 in full:**

```
### 4.2 Parallel low-cost work during Phase 0

One analyst-lane task per repo, budgeted at **2-3 days of analyst time
per repo** (not background work; not unlimited). Running concurrent with
Phase 0, not competing for primary author-lane attention.

- **Fund + RIN-SnD shape audit.** Output lives at
  `plans/steward_platform/0_hardening/target_repo_audit.md`, one section
  per repo, each using this fixed format:

  - **Build system, test framework, CI shape.**
  - **Branch conventions, release conventions.**
  - **`.claude/` presence and layout (if any).**
  - **Hosted-service dependencies and external contracts.**
  - **Tooling conventions (package manager, linter, formatter, type
    checker).**
  - **Portability-debt preview.** Per-file mapping of the top-10 most
    steward-coupled files in the repo, classified `hard-block` vs.
    `soft-coupling` using the `PORTABILITY_MANIFEST.md` taxonomy.
  - **Lane-layout feasibility.** Which current steward lane roles would
    plausibly map 1:1 vs. require adapters vs. not apply at all.
  - **Top 3 adoption risks** in operator's own words.

  Purpose: produce a decision-grade portability input for Phase 2, not a
  surface inventory. If the audit cannot be produced to this depth in 2-3
  days per repo, that is itself a portability-signal finding and feeds a
  Phase 2 Decision Input.
```

### 3.7 Record Platform-11/13 dismissal evidence

The handoff invites challenge on fixed constraints when there is
load-bearing reason. The Platform-11/13 dismissal is such a case: it is the
strongest empirical signal the fleet has about its own track record on
primitive-count ambition, and the plan carries it forward as a
conversational premise.

I am not challenging the operator's decision to set it aside. I am asking
the plan to *name* what changed, per Goal #14 (ADR-style decision capture).

**Add to §12 Risks row 6, appended to the mitigation column:**

```
The specific constraints that paused Platform-11 and Platform-13 and have
since lifted are recorded in an ADR filed at Phase 0 kickoff
(`knowledge/adr/001-platform-pattern-reset.md`), which serves as the
evidentiary basis for this plan's Phase-0 primitive count. If the
postponement pattern recurs in Phase 0, the ADR is reopened and Phase 0
is recast before continuing.
```

This is the lightest-touch version of the fix. It ties into Goal #14 and
Primitive C's ADR system rather than adding new structure.

### 3.8 Sharpen Phoenix workflows (§5-A)

Replace the two-workflow description in §5-A with:

```
Phoenix deployment is justified by two named workflows:

1. **Reproducibility audits.** Trigger: an operator or analyst files a
   "replay this task" request against a task_id. Consumer: analyst lane.
   Cadence: on demand, expected ≤1/week. Output: either a green "matches
   event corpus" note *or* an incident draft with the divergence
   timeline. A workflow "counts" toward §11-A kill-criterion measurement
   only when it produces one of these two outputs.

2. **Session-archive evaluation for lesson extraction.** Trigger: nightly
   archivist run (Primitive D). Consumer: archivist script + operator
   reviewer. Cadence: nightly. Output: a candidate-lessons file at
   `knowledge/_candidates/<date>.md` whose promoted items flow into
   NOTES / PLAYBOOKS / incidents. A workflow "counts" only when
   candidates are actually promoted.
```

This gives §11-A a real measurement, not a UI-open count.

### 3.9 Add proving-run data-sufficiency exit check (§6.1)

**Add to §6.1 after the "Why this candidate" list:**

```
**Pre-Phase-1 data-sufficiency check.** Before Phase 1 is committed to
the GBT retrain, the analyst lane confirms:

- Human-gameplay session count ≥ [threshold specified by the first
  strategy-training sub-plan in Phase 0].
- Session quality distribution (% completed games, opponent
  heterogeneity, contract-type coverage) meets a documented floor.
- At least one end-to-end ingest → features → train → eval loop ran
  against the existing corpus inside Phase 0.

If any of the three is not met, the proving run pivots to the
measurement-methodology overhaul alternative, which stresses the
platform's coordination/learning/rigor surfaces without a data-accretion
dependency. The decision to pivot is itself a Phase 2 Decision Input
under the `portability-signal` tag (evidence that research value via
browser data was not accessible within Phase 1).
```

### 3.10 Minor edits

- **§7.2 item #3:** strike the cmux shape description ("workspace-per-project,
  notification bindings, browser surfaces, operator action bindings").
  Leave only the trigger condition ("Only relevant if portability goes
  forward."). The shape is a Phase 2 decision output, not a rubric
  precondition.
- **§5-H, final bullet:** rephrase "Usable as a portability dry-run in
  Phase 2" as "**Intended to be** usable..." — signals design-intent
  coupling without claiming verified readiness.
- **§16 Delta From Draft 1:** fix the two occurrences of "7 primitives"
  that survive from an earlier draft (the "Primitive count disciplined"
  bullet says 7; the "Reliability Lab added" parenthetical says "Primitive
  count rose from 7 to 8"). Both should read "8 primitives" consistently.
- **§3 Key Definitions:** add an entry for *Proving run* since it is
  load-bearing throughout and currently defined only by §6.1 context.
  (Current definition reads: *"a complete end-to-end research program
  executed through the platform..."* — this is already in §3. Actually
  fine; ignore this bullet.)

---

## 4. Updated Grade And Recommendation

**Grade: B.**

Rationale (absolute terms, not relative to team capacity):

- The plan now answers the right *first* question ("is this platform worth
  porting") before the *second* question ("will it port"). That is a
  strategic improvement from C+ (draft 1).
- Primitive count and taxonomy are disciplined. KB and archivist are
  proportional. Meta-layer deferral is clean. Kill criteria exist.
- The plan is self-inconsistent in places (primitive count, goal
  inflation) and under-designed in others (ledger, Phase 0 time-box,
  proving-run data contingency, Phoenix workflows).
- Nothing is fatally wrong; everything flagged is a revision, not a
  redesign.

What separates a B from an A, under the *best plausible plan* standard
(not the workable-plan standard):

- An A plan does not disagree with itself about workstream count.
- An A plan does not include an open-ended scope-expansion clause.
- An A plan's time-box is falsifiable against its own declared work, with
  an explicit slack budget.
- An A plan does not leave its primary artifact-discipline mechanism
  (§15) under-designed on first publish.
- An A plan's kill criteria are adversarial against the author's
  sympathies, not aligned with them.

All of those gaps are reachable with 2-3 hours of revision. This is not a
rework.

**Recommendation: approve with revisions.**

Approval is contingent on applying the seven revision groups in §3, with
the following priority:

**Must-fix before Phase 0 kickoff** (blockers on execution):

1. §3.1 — primitive-count inconsistency (editorial but required).
2. §3.2 — delete Goal #16 and restate floor intent (scope-lock clarity).
3. §3.3 Option A — defer Primitive H scope; keep only rollback-validation
   absorbed into Primitive G. (Or Option B with explicit time-box extension.)
4. §3.4 — replace the ledger with structured outcome subsections, or at
   minimum collapse tags and mechanize write-discipline.

**Should-fix before Phase 0 kickoff** (plan credibility):

5. §3.5 — tighten kill-criteria thresholds.
6. §3.9 — add proving-run data-sufficiency exit check.
7. §3.7 — record Platform-11/13 dismissal evidence as an ADR.

**Nice-to-fix during Phase 0 kickoff** (can be absorbed into first
sub-plans without blocking the governing plan):

8. §3.6 — target-repo audit scope/output format (can land in a sub-plan
   under §4.2).
9. §3.8 — Phoenix workflow sharpening (can land in the Primitive A
   sub-plan).
10. §3.10 — minor edits (editorial).

---

## 5. Open Questions Back To Orchestrator / Operator

1. **Primitive H scoping.** Is the recommendation in §3.3 Option A (defer
   replay + failure-injection + postmortem generator; keep only rollback
   validation absorbed into Primitive G) acceptable? If the operator
   prefers to keep H in full Phase 0 scope, §3.3 Option B (extend the
   time-box to 9-12 weeks) is the alternative I would require before
   considering the plan executable as drafted.

2. **Ledger pattern.** Is the operator attached to the separate
   ledger-file shape, or is the structured-outcome-subsection alternative
   in §3.4 acceptable? The latter is materially simpler and less
   decay-prone; both satisfy the "no archaeology" requirement.

3. **Proving-run data-sufficiency threshold.** The check in §3.9 requires
   a numeric threshold ("≥N human-gameplay sessions"). What is the
   current observed rate of session accretion through the browser game?
   I did not have access to browser-game telemetry during the review;
   this answer determines whether §3.9 is a safety net or an active
   pivot trigger.

4. **Phase 0 time-box ownership.** §2.3 argues the declared primitive set
   likely needs 7-12 weeks, not 6-8. If the 6-8 target is a hard
   constraint (not a planning estimate), which primitive(s) does the
   operator want to defer? I recommend H; the operator may have a
   different preference.

5. **Platform-11/13 dismissal ADR.** Is there a short list of concrete
   constraints that lifted (operator confidence, tooling maturity, team
   capacity, new dependency available, etc.) that can seed the ADR in
   §3.7? Without that, the ADR is a placeholder, not a decision record.

6. **Analyst-vs-author routing policy enforcement (Primitive B).** The
   plan specifies this as "encoded as policy, not convention." Is there
   an existing prototype or convention that this will replace, or is
   this net-new? If net-new, the prompt-policy registry work likely
   subsumes two primitive-slices worth of effort (the registry itself
   and the routing-rule encoding), which affects the §3.3 time-box
   analysis.

7. **Review distribution.** Should this review be circulated to a second
   analyst lane for orthogonal reading, or is one reviewer sufficient
   for the revision pass before Phase 0 kickoff? The prior cycle used a
   Codex second review; this cycle did not.

---

## 6. Scope And Mechanics Notes

- **Write scope:** This review touches only `plans/steward_platform/`.
  `governing_plan.md` (draft 1) and `governing_plan.draft2.md` are
  unchanged. Proposed revisions are offered as replacement text in §3
  rather than as edits to the plan files.
- **Review stance applied:** skeptical, simpler-preferred,
  best-plausible-plan standard. Fixed constraints (1-repo horizontal
  scope, vertical-ambition floor, prove-before-port principle, no meta
  in Phase 0) were not relitigated; one fixed constraint
  (Platform-11/13 dismissal as not-applicable) was challenged per §2.8
  with explicit reasoning.
- **Artifact hand-off:** deliverable is this file. No edits to the plan
  files. No changes to checkpoints, MEMORY.md, or agent prompts.

---

## Outcome

_To be filled after operator disposition._

- Result: DISPOSED | PARTIALLY DISPOSED | DEFERRED
- Revisions applied: [pointer to draft 3 or to sub-plan edits]
- Notes:
