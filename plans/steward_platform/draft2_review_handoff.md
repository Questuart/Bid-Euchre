# Handoff: Steward Platform Governing Plan — Review of Draft 2

**Date:** 2026-04-22
**From:** orchestrator (co-drafted with operator)
**To:** steward-analyst (review stance: skeptical, prefer simpler solutions, flag over-engineering, propose better alternatives)
**Review target:** `plans/steward_platform/governing_plan.draft2.md`
**Prior artifact preserved:** `plans/steward_platform/governing_plan.md` (draft 1, PROPOSED, 2026-04-22)

---

## Your prior context (recap)

You (or another reviewer on your lane) previously produced a critique of
`plans/steward_platform/governing_plan.md` (draft 1, 466 lines, PROPOSED,
2026-04-22, supersedes the `agent_ops` plan). Load-bearing findings from
that review, reproduced for continuity:

- **Strategic:** the plan conflated an operator-UX/context-management pain with a portability pain, and proposed one unified solution; the plan's falsification test (cross-repo adoption) was deferred to Phase 4, meaning the one experiment validating the contract happened *after* the architecture built on that contract was in place; ~12 new primitives introduced in a plan that also preached "adapt before replace."
- **Scoping:** "make steward excellent first" was not scoped; KB taxonomy (7 dirs × 3 repos + 7-dir meta-KB) was premature scaffolding; archivist-as-lane was the wrong tool for curation.
- **Directive:** Phoenix commitment from phase one was premature absent named workflows; meta-steward-home as a new repo was under-justified; meta-orchestrator as a lane vs. UX pattern was unresolved.
- **Risk:** target repos (`Fund`, `RIN-SnD`) were not inspected before the plan committed to them as adoptable targets; no kill criteria per workstream; no phase gates.

Prior verdict: **C+ — approved with major revisions, not rejected for
rework.** Required-changes list led by "invert phase order" and "cut
primitives to ≤5."

## What happened between the prior review and now

Trajectory summary so you understand how draft 2 was arrived at. Operator
engaged with the critique and the plan was redirected in six substantive
moves:

1. **Operator clarified the problem.** Two pains, not one:
   - (a) steward is Bid-Euchre-coupled and not usable across repos;
   - (b) operator can't track project shapes across repos and wants a central surface that helps them *allocate* attention/tokens across projects.
   The second is a cross-project allocation problem, not just UX. This partially rehabilitates the meta-layer rationale the initial review challenged.

2. **Codex (second reviewer) produced a parallel review.** Converged with the prior critique on most points (cross-repo proof early, hardening gate, archivist-as-script, meta-orch-as-UX first, kill criteria, target-repo audit). Pushed back on: splitting into two initiatives (prefers one plan with tracks), Phoenix deferral (prefers early sidecar with kill criteria), KB reduction (prefers sparse skeleton over two-file flat), new repo for meta-home (prefers dedicated home, not necessarily a new repo).

3. **Synthesis landed on most disputed points.** One plan with tracks, not two initiatives. KB skeleton reduced to 4 items (`NOTES.md`, `PLAYBOOKS.md`, `incidents/`, `INDEX.md`), not 7. Meta-home = directory under `~/.claude/`, not a new repo, until concrete need. Phoenix disposition reframed to "name two analytical workflows or defer."

4. **Operator reframed the falsification test.** Moved from the prior "spike second repo to falsify portability" to a deeper framing: **"prove the platform produces research value on the repo where signal is densest before deciding to port."** The falsification test becomes a **full research proving run** inside Bid-Euchre (primary candidate: a GBT retrain informed by human-gameplay data captured via the existing browser-game hosting infrastructure), not a second-repo spike. Second-repo adoption becomes a Phase 2 decision-gate output rather than a Phase 1 precondition.

5. **Vertical vs. horizontal ambition clarified.** Operator rejected any reduction in vertical ambition (capability depth per repo) and provided an explicit 12-capability list. Horizontal ambition (number of repos) is deliberately narrowed to 1 (Bid-Euchre) until the proving run completes. These are orthogonal axes; conflating them was an error in the initial framing.

6. **Goal list expanded from 12 to 15.** In response to an operator question about what vertical ambitions draft 1 addressed that the 12-list missed, three additions:
   - #13 Rollback / disable paths (from draft 1 §7 evidence contract)
   - #14 ADR-style architecture decision capture (from draft 1 §4.2 and §9.8)
   - #15 Reliability-lab / replay / failure-injection (sourced from `plans/agent_ops/post_sprint_brainstorm.md` §1; not in draft 1 proper but flagged there as a vertical-scope post-sprint candidate)

7. **Decision-inputs ledger added.** Operator raised the concern that findings during hardening and the proving run might be lost by the time Phase 2 evaluates them. Result: a persistent, additive-only ledger at `plans/steward_platform/decision_inputs.md` with a tag taxonomy, fed by every primitive, the archivist script, the proving-run report, and the parallel shape audits.

## The artifact under review

**`plans/steward_platform/governing_plan.draft2.md`** — ~560 lines, written as a successor to draft 1, preserving draft 1 untouched for diffing.

Headline structure:
- **3 real phases** (0 Hardening, 1 Proving Run, 2 Decision Gate) plus reserved Phase 3+.
- **8 primitives** (A Trace/observability, B Adaptive dispatch + skill + prompt-policy, C Durable memory + KB, D Archivist script, E Messaging + active triage, F Token economy closeout, G Debt closeout, H Reliability lab).
- **Parallel** one-analyst-shift shape audit of `Fund` and `RIN-SnD` during Phase 0 — keeps portability option warm without gating.
- **16-row proving-run scorecard** (the 15 capabilities + "other").
- **Per-primitive kill criteria.**
- **Decision-inputs ledger** with 9-tag taxonomy.
- **Explicit "Delta From Draft 1" section** documenting what changed and why.

## What you are asked to do

Review draft 2 as a proposed successor to draft 1 under the same review
stance as before: skeptical, prefer simpler solutions, call out
over-engineering, propose better alternatives where the directives aren't
the most effective path.

Specific review asks, in priority order:

1. **Does draft 2 adequately address your prior critique?** For each P0/P1/P2 finding from the initial review, does draft 2 resolve it, partially resolve it, or miss it? Produce a disposition table.
2. **Does the reframing introduce new problems?** The key reframe is "prove before port" with the proving run (GBT retrain) as Phase 1.
   - Is that the right falsification test?
   - Does anything about that test being a *research* activity — with its own research-level failure modes — confound its usefulness as a *platform* test?
   - Draft 2 §6.3 attempts to separate the two evaluations; is that separation clean enough?
3. **Is the 8-primitive Phase 0 scope executable in 6-8 weeks?** Primitive count went up from the prior recommended "≤5" to 8 because the operator expanded the goal list. Every primitive ties to a named goal and has kill criteria. Is this still too much for a Phase 0 time-box? If so, which primitive(s) would you defer?
4. **Is the decision-inputs ledger (§15) a sound pattern or will it become a graveyard?** The ledger is supposed to prevent Phase 2 from being archaeological.
   - Does the tag taxonomy work?
   - Is the write-discipline realistic or will it be ignored?
   - Are there proven patterns from ADR practice, incident-management tooling, or research-notebook workflows that this should borrow from?
5. **What is draft 2 still wrong about?** Anywhere the synthesis over-corrected, re-introduced old problems, or papered over hard questions.

## Constraints the operator has fixed

Things the operator has explicitly taken off the table. Do not relitigate
unless you see a load-bearing reason — and if you do, say so explicitly
and make the case:

- **Horizontal scope:** 1 repo (Bid-Euchre) in Phase 0/1. `Fund` + `RIN-SnD` port is a Phase 2 decision-gate output, not a precondition.
- **Vertical ambition:** the 15-capability list in §2 is a *floor* for what the platform should do per repo, not a ceiling. Do not recommend cutting capabilities to reduce scope.
- **Proving-run framing:** a full research run validates the platform before portability does. Alternatives to the GBT retrain as the first proving candidate are fair game; alternatives to the "prove before port" principle are not.
- **Track-record risk:** operator has dismissed the Platform-11/13 postponement pattern as not applicable; constraints that paused those efforts are no longer in place.
- **Meta-layer:** not in Phase 0. Meta-orchestrator, cross-project promotion, cmux adoption, meta-KB, and planning-skeleton sync are all Phase 2 decision outputs, not Phase 0 commitments. If you think any of them should move earlier, argue explicitly.

## What is explicitly still up for challenge

The operator has invited scrutiny on these:

- **Primitive count at 8.** Above the prior "≤5" recommendation. Justifiable on paper (each tied to a named goal), but argue if it's still too much.
- **Phoenix in Phase 0.** Draft 2 ships Phoenix with two named workflows (#2 auditable, #11 archive evaluation) as justification and a kill criterion. Previous reviews split: prior review said defer; Codex said early sidecar with kill criteria; synthesis shipped it. If the kill criterion's threshold (<5 operator opens in 4 weeks) is wrong, say so.
- **Kill-criterion thresholds (§11).** All first-cut. Worth pressure-testing.
- **Proving-run scorecard targets (§6.2).** Quantitative targets (≤1 routing error per 100 tasks, ≥80% adaptive-dispatch approval, ≥90% prompt-policy trace coverage, etc.). Challenge any that are obviously too loose or too strict.
- **Ledger tag taxonomy (§15).** 9 tags. Over- or under-specified?
- **Reliability lab scope (Primitive H).** New addition. Argue if it's the wrong shape or wrong size.
- **Phase 0 time-box (6-8 weeks).** Realistic?

## Related context for verification

If you want to check claims made in the plan against the codebase:

- **Portability debt counts:** `docs/02_agent/PORTABILITY_MANIFEST.md` — 130 hard-block + 123 soft-coupling non-cosmetic items, concentrated in `ops/worktrees.py` (44) and `ops/token_economy.py` (22).
- **Existing messaging-bus state:** 7 keystones merged session 2026-04-21c per `MEMORY.md`; closeout debt noted on follow-ups.
- **Token economy state:** Slices A–E merged; Slice F evaluation protocol shipped as PR #2716, execution gated on 1-2 week observation window.
- **Existing lanes and agents:** `.claude/agents/steward-*.md`; 19-lane current fleet defined in `.claude/rules/75_worktree_protection.md`.
- **Adaptive dispatch (Platform-11 partial reactivation):** `plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-11-skill-learning-loop.md`.
- **Phase 5 plan fragmentation:** `plans/agent_ops/5_extraction/`, `5_cross_model/`, `5_skill_learning/`, `5_portability_and_learning/` — all with `scope_lock.md`; two POSTPONED; one partially reactivated. Draft 2 Primitive G targets retirement.
- **Fund + RIN-SnD repos:** `~/Desktop/Fund` and `~/Desktop/RIN-SnD` — may be sandbox-restricted from your session. The Claude Code project cache confirms Fund is active (multiple session JSONLs); RIN-SnD is lightly used (1 JSONL). If you can't access them directly, the plan's parallel-shape-audit workstream (§4.2) is how the operator plans to characterize them; comment on whether that workstream's output format is sufficient.
- **Draft 1 being superseded:** `plans/steward_platform/governing_plan.md` — do not edit; preserved for diffing only.

## Suggested investigation order

1. Read `governing_plan.draft2.md` in full.
2. Diff it against `governing_plan.md` — or read the "Delta From Draft 1" section at the end of draft 2 first, then spot-check the diffs it claims.
3. Re-read your (or the prior reviewer's) original critique if accessible, then produce the disposition table per review ask #1.
4. Address review asks #2-#5 in order.
5. Produce an updated grade + recommendation with reasoning.

## Deliverables

- **Per-finding disposition** of the prior critique against draft 2 (resolved / partial / missed, with evidence).
- **New findings** introduced by the reframing or by the draft 2 additions (Primitive H, ledger, expanded goal list, proving-run framing).
- **Concrete revision proposals** for anything flagged. Where you propose a change, propose the text — not just a direction.
- **Updated overall grade and recommendation** (approve / approve with revisions / reject for rework), with reasoning in absolute terms, not relative to team capacity.
- **Open questions** back to the orchestrator or operator if your review surfaces any.

Take the stance that the plan should be the *best plausible plan* for the
steward platform's intended future, not merely a workable one.

---

## Mechanics

- **Scope lock on review:** you are reviewing, not implementing. Your write scope for this task is `plans/steward_platform/` (review artifacts, notes, proposed text) — do not edit `governing_plan.draft2.md` directly; propose changes as diffs or replacement text in a separate review artifact (e.g., `plans/steward_platform/draft2_review_<yourlane>.md`).
- **Preserve draft 1:** `plans/steward_platform/governing_plan.md` is the operator's original and must not be edited.
- **Expected output:** a markdown review document at `plans/steward_platform/draft2_review_<yourlane>.md` containing the deliverables above.
- **Time expectation:** this is a governing-plan review, not a coding task. Depth over speed. 2-4 hours of focused work is appropriate; longer if the review turns up structural issues that warrant deeper investigation.
- **Escalation path:** if the review surfaces a blocker or a decision you need operator input on, message the orchestrator with a concrete question rather than stalling. Use `ops.py message send --from <lane> --to orchestrator --type escalation` for anything time-sensitive.
