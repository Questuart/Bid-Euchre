# Draft 8 Final Review — steward-analyst

**Date:** 2026-04-23
**Reviewer:** steward-analyst
**Review basis:** artifact set reviewed from the local worktree snapshots for `docs/steward-platform-draft-8` and `docs/steward-platform-adr-seeds`, because the draft-8 promotion package is not yet present in the current `main` checkout. Target paths below use repo-root-relative names from the package under review.
**Primary targets:** `plans/steward_platform/governing_plan.draft8.md`, `plans/steward_platform/claude_code_changelog_implications.md`, `plans/steward_platform/0_hardening/sub/rework_spec.md`, `plans/steward_platform/plugin_source_evaluation.md`, and ADR seeds under `plans/steward_platform/adrs/`.

---

## 1. Track A — Holistic Review

### 1.1 Dimension Grades

| Dimension | Grade | Reasoning |
|---|---|---|
| Strategic clarity | A- | The plan now has a crisp governing thesis: steward is a governed self-improvement loop inside one project cell, and the proving run is explicitly separated from portability and meta-layer decisions. |
| Platform thesis quality | A- | The native-substrate-first plus bespoke-orchestration-spine thesis is coherent across `governing_plan.draft8.md`, `claude_code_changelog_implications.md`, and the plugin ADR seeds; the plan is no longer pretending Claude Code is irrelevant while still overbuilding beside it. |
| Scope discipline | B+ | Eight primitives and sixteen goals are still large, but they are now genuinely bounded; the remaining inflation risk is mostly inside Primitive B and Primitive G rather than in uncontrolled new scope. |
| Simplicity and leverage | B | The plan still carries more bespoke machinery than ideal, especially in Primitive C and the changelog/plugin surfaces, but most of that machinery is now tied to explicit leverage rather than speculative architecture taste. |
| Execution realism | B- | The plan is shippable, but several implementation surfaces are still under-scaffolded enough that Phase 0 kickoff would require tightening passes before author lanes can move cleanly. |
| Directive quality | B+ | Most directives are now concrete and well-shaped, especially the phase gates and the native/plugin/bespoke preference, but a few load-bearing directives still contain internal inconsistencies or unresolved ordering. |
| Risk handling | B+ | The risk table is materially stronger than earlier drafts and includes the important newer failure modes, though it still underplays repo-access readiness, template-scaffold readiness, and Primitive A-to-downstream cascade as implementation blockers rather than only strategy risks. |
| Adaptability | A- | Phase 2 can plausibly pivot to portability, meta-layer work, more single-repo iteration, or primitive kills without rewriting the whole plan; the deferred architecture surfaces are now properly evidence-gated. |

### 1.2 Overall Grade

**Overall grade:** B+

### 1.3 Final Recommendation

**Final recommendation:** PROMOTE-AFTER-FIXES

### 1.4 Rationale

In absolute terms, this is now a strong governing plan and a coherent companion package. The remaining problems are mostly implementation-readiness defects, not strategic defects. I would not ask for a draft 9 rework cycle. I would require a short tightening pass that resolves the concrete blockers in §3 before promotion and Phase 0 kickoff.

---

## 2. Track B — Implementation Review

### 2.1 Implementation-Readiness Scorecard

| # | Question | Status | Reasoning / blocker |
|---|---|---|---|
| 1 | Phase 0 startability | READY-WITH-FIXES | An author lane can start Primitive A or C tomorrow, but not cleanly until the B.9↔G ordering is resolved and the missing template scaffold exists. |
| 2 | Dependency graph | READY-WITH-FIXES | Most primitive dependencies are clean, but B.9 and Primitive G currently form a circular readiness dependency around `--system-prompt-file` and Setup-hook adoption. |
| 3 | ADR seed readiness | READY-WITH-FIXES | ADRs 005, 010, and B8 are close to promotion-ready; ADR 007 still needs source-evidence tightening and one open-question boundary clarified. |
| 4 | Open Item completeness | READY-WITH-FIXES | Most open items are actionable, but several still need ownership/mechanism text before an author lane can resolve them without inventing local scope. |
| 5 | Baseline capture readiness | READY-WITH-FIXES | The artifact location is specified, but the mechanism is still “capture a baseline” rather than “run these commands/scripts,” so Phase 0 kickoff would improvise too much. |
| 6 | Shape audit readiness | READY-WITH-FIXES | The output format is strong, but one target repo path is not actually present in the current environment, so the audit cannot start for both repos without a path/access correction. |
| 7 | Preflight readiness | READY-WITH-FIXES | The preflight is concrete enough to run, but the package still says “10 items” in places where the checklist has 11, which would silently under-report the new repeat-task-improvement probe. |
| 8 | Success-criteria measurability | READY-WITH-FIXES | Most success criteria point to inspectable artifacts, but “attention compression relative to baseline” and parts of baseline capture remain under-mechanized. |
| 9 | Kill-criteria falsifiability | READY-WITH-FIXES | The kill rows are much better than prior drafts, but a few still rely on scaffolding that does not yet exist and therefore are not yet executable as written. |
| 10 | Template scaffolding | NOT-READY | The plan relies on templates that do not exist yet (`execution_plan`, `promotion_rollback`, `primitive_closeout`), so the enforcement story is incomplete at kickoff. |
| 11 | Script scaffolding | READY-WITH-FIXES | The script specs are mostly concrete enough to build, but `compile_decision_inputs.py` still has a schema inconsistency and baseline-capture support scripts are not named. |
| 12 | `.claude/system_prompts/` vs `.claude/agents/` reconciliation (G10) | READY-WITH-FIXES | The ADR requirement is correct, but there is not yet enough candidate text to treat it as “resolved at kickoff” without one short decision memo. |
| 13 | Lane archetype mapping (G13) | READY-WITH-FIXES | This is a real work item, not merely a quick rename, but it is bounded and can be handled as a first Primitive G sub-sub-plan rather than a plan blocker. |
| 14 | Plugin source-evaluation fold-in completeness | READY-WITH-FIXES | The key decisions are folded in, but ADR 007 still carries weaker evidence hygiene than the other seeds and should be tightened before filing. |
| 15 | Cross-reference integrity | NOT-READY | Pattern 9 is directionally good, but the package still has at least one direct ownership violation and one schema-spec inconsistency that would make the lint story false on day one. |

### 2.2 Concrete Blocker List

| Blocker ID | Severity | Blocker | Must land before |
|---|---|---|---|
| I1 | High | Resolve the B.9 ↔ Primitive G circular readiness dependency around `--system-prompt-file` and Setup-hook adoption. | Promotion / Phase 0 kickoff |
| I2 | High | Create the missing template scaffold referenced as enforcement infrastructure (`plans/_templates/execution_plan.md`, `plans/_templates/promotion_rollback.md`, `plans/_templates/primitive_closeout.md`, or equivalent) and align the plan text to the actual template set. | Promotion / Phase 0 kickoff |
| I3 | Medium | Fix the preflight checklist count mismatch (11 actual items vs 10 in outputs/gate text). | Promotion |
| I4 | Medium | Fix the `compile_decision_inputs.py` spec mismatch (schema has five prompts; digest spec still says four). | Promotion / script build |
| I5 | Medium | Add explicit ownership for `scripts/internal/sweep_session_plans.py` in Primitive G Work/Readiness to satisfy Pattern 9. | Promotion |
| I6 | Medium | Correct the target-repo audit assumption for `RIN-SnD` path/access; current environment has `Fund` but not `RIN-SnD` at the presumed location. | Phase 0 kickoff |
| I7 | Medium | Tighten baseline-capture mechanics with named commands/scripts or a small baseline-capture helper so Phase 0 does not start with measurement improvisation. | Phase 0 kickoff |
| I8 | Low-Medium | Tighten ADR 007 source evidence to a concrete repository/path reference and decide whether the `extra_fields` question is genuinely open or already resolved by the ADR decision. | ADR filing at kickoff |

### 2.3 Per-ADR Readiness Assessment

| ADR | Status | Assessment |
|---|---|---|
| `plans/steward_platform/adrs/005-review-plugin-evaluation.md` | READY-WITH-FIXES | The decision is clear and testable. Minor tightening only: explicitly say the cherry-picked validator/fan-out work is Phase 1+ and not part of Phase 0 kickoff scope. |
| `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` | READY-WITH-FIXES | Architecturally strong, but weaker than the others on evidence hygiene. Replace the vague source line with the concrete monorepo/plugin path already captured in `plugin_source_evaluation.md`, and either close or bound the `extra_fields` open question. |
| `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` | READY | This ADR is self-contained, grounded, and has a clear soft re-evaluation trigger. |
| `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` | READY | This is promotion-ready. The decision boundary is crisp and implementation-neutral in the right way. |

### 2.4 Overall Implementation-Readiness Verdict

**Overall implementation-readiness verdict:** SHIP-AFTER-FIXES

The package is close enough that a tightening pass is the right move. It is not yet “open a Phase 0 packet tomorrow without touching the plan” ready.

---

## 3. Findings

[P1] The package still contains a circular Phase 0 readiness dependency between B.9 and Primitive G.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:339`, `plans/steward_platform/governing_plan.draft8.md:559`, `plans/steward_platform/governing_plan.draft8.md:572`
- Impact: Phase 0 startability is muddied because B.9 readiness depends on Primitive G’s Setup-hook launch path while Primitive G readiness depends on B.9’s system-prompt artifacts already existing and being wired. This is the main true implementation blocker in the current graph.
- Fix:
  1. Split B.9 into two ordered checkpoints: `prompt artifact readiness` (system prompt files + ADR G10) under Primitive B, then `fleet launch adoption` under Primitive G.
  2. Make Primitive G depend on B.9 artifact readiness, not full B.9 readiness.
  3. Add one sentence under Primitive G Phase 0 Readiness clarifying that Setup-hook adoption consumes pre-existing prompt files rather than co-defining them.
- Validation:
  - `rg -n "B\\.9|Setup hook|system-prompt-file" plans/steward_platform/governing_plan.draft8.md`
  - Verify the plan no longer has a bidirectional dependency between the two sections.

[P1] The preflight checklist was expanded to 11 items, but the output and gate sections still treat it as a 10-item checklist.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:680-692`, `plans/steward_platform/governing_plan.draft8.md:696-700`, `plans/steward_platform/governing_plan.draft8.md:704-706`, `plans/steward_platform/governing_plan.draft8.md:1085`
- Impact: The new repeat-task-improvement probe can be silently omitted from reporting and gating, which weakens the exact mechanism-level self-improvement claim draft 8 was trying to strengthen.
- Fix:
  1. Update §6.5 and §6.6 to say 11 checklist items.
  2. Update Success Criterion #2 to match the 11-item gate.
  3. Spot-check any remaining “10 item” references in lineage/delta sections and remove stale text.
- Validation:
  - `rg -n "10 checklist|11 checklist|All 10 pass|All 11 pass|10 items|11 items" plans/steward_platform/governing_plan.draft8.md`

[P1] The template-enforcement story is not promotion-ready because the plan references required templates that do not exist in the repo scaffold.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:381`, `plans/steward_platform/governing_plan.draft8.md:978-980`, `plans/steward_platform/governing_plan.draft8.md:1211-1214`; current repo `plans/_templates/` contains only `checkpoints.md`, `governing_plan.md`, `sub_plan.md`, `sub_plan_registry.md`
- Impact: Track B question 10 fails in practice. The plan claims creation-time and review-time enforcement through template files that are not yet present, so author lanes cannot rely on the enforcement model at Phase 0 kickoff.
- Fix:
  1. Add the missing templates or collapse the enforcement story to the templates that actually exist.
  2. If `promotion_rollback.md` and `primitive_closeout.md` are required, create them before promotion.
  3. If `execution_plan.md` is intended to be a variant of `sub_plan.md`, say so explicitly and remove the phantom filename.
- Validation:
  - `find plans/_templates -maxdepth 2 -type f | sort`
  - `rg -n "promotion_rollback|primitive_closeout|execution-plan|execution_plan" plans/steward_platform/governing_plan.draft8.md`

[P2] Pattern 9’s load-bearing-ownership claim is already violated by `scripts/internal/sweep_session_plans.py`.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:17`, `plans/steward_platform/governing_plan.draft8.md:19`, `plans/steward_platform/0_hardening/sub/rework_spec.md:103`; no corresponding Primitive G Work or Readiness bullet names `scripts/internal/sweep_session_plans.py`
- Impact: The plan is claiming that ownership lint has solved the “floating load-bearing file” problem while still shipping at least one direct example of the problem. That undermines Track B question 15 and weakens confidence in Pattern 9 enforcement.
- Fix:
  1. Add `scripts/internal/sweep_session_plans.py` explicitly to Primitive G Work.
  2. Add one Primitive G readiness or closeout check confirming the archive sweep ran or was deferred with rationale.
  3. Run the same ownership check against the other newly introduced scripts before promotion.
- Validation:
  - `rg -n "sweep_session_plans" plans/steward_platform/governing_plan.draft8.md plans/steward_platform/0_hardening/sub/rework_spec.md`

[P2] The `compile_decision_inputs.py` spec still contradicts the five-prompt subsection schema it is supposed to parse.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:1158-1166`, `plans/steward_platform/governing_plan.draft8.md:1190-1193`
- Impact: This is a direct implementation trap for the first author lane that builds the digest script. The spec still says “four prompts” in the parser section even though the schema has five prompts plus disposition.
- Fix:
  1. Update §15.4 to say the script parses five prompts plus disposition.
  2. Align the grouping description with the actual buckets, including re-evaluation if it remains a first-class bucket.
  3. Add one tiny worked example of parser input/output in §15.4 if you want the script handoff to be unambiguous.
- Validation:
  - `rg -n "four prompts|five prompts|Disposition|Re-evaluation needed in Phase 3" plans/steward_platform/governing_plan.draft8.md`

[P2] The target-repo shape audit is not fully startable because one named target repo path is not currently present in the environment.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:203-217`; local environment check found `/Users/claude_runner/Desktop/Fund` but not `/Users/claude_runner/Desktop/RIN-SnD`
- Impact: Track B question 6 cannot honestly be marked READY. The audit format is good, but one of the two concrete audit targets is not actually available at the presumed path, which would stall the analyst lane or force path archaeology at kickoff.
- Fix:
  1. Add an explicit Phase 0 precondition: verify checkout path and access model for each target repo before dispatching the audit.
  2. Record the actual `RIN-SnD` path if it exists elsewhere, or say that the analyst lane must obtain it first.
  3. Treat “repo not present / access blocked” as a first-class audit outcome, not a silent failure.
- Validation:
  - `ls -d /Users/claude_runner/Desktop/Fund /Users/claude_runner/Desktop/RIN-SnD`

[P3] ADR 007 is the least promotion-ready seed because its source-evidence section is still vague compared with the other seeded ADRs.
- Evidence: `plans/steward_platform/adrs/007-observability-plugin-evaluation.md:58-66`
- Impact: This does not block the governing plan itself, but it does weaken the “seeded and ready to file at kickoff” claim for one of the four plugin ADRs.
- Fix:
  1. Replace the generic source-evidence text with the concrete monorepo/plugin path already captured in `plans/steward_platform/plugin_source_evaluation.md:223-232`.
  2. If the exact repository path changed during evaluation, carry that corrected path directly into the ADR.
  3. Either close the `extra_fields` open question or restate it as a non-blocking implementation note.
- Validation:
  - `sed -n '58,66p' plans/steward_platform/adrs/007-observability-plugin-evaluation.md`
  - `sed -n '223,232p' plans/steward_platform/plugin_source_evaluation.md`

[P3] Baseline capture is strategically well-specified but still under-mechanized for immediate author-lane execution.
- Evidence: `plans/steward_platform/governing_plan.draft8.md:224-238`; no named helper script or command set in Primitive A/F/G Work for baseline production
- Impact: A Phase 0 kickoff lane can infer what to collect, but not exactly how to collect it. That is a “READY-WITH-FIXES” issue, not a strategic flaw, but it will slow kickoff and create inconsistent measurement shapes if left implicit.
- Fix:
  1. Add either a small `scripts/internal/capture_steward_baseline.py` spec or a command checklist under §4.3.
  2. Name the existing command surfaces to use for each metric (`ops.py dashboard`, `ops.py usage`, git/PR history, issue query, etc.).
  3. Put the capture commands directly into `plans/steward_platform/0_hardening/baseline.md` template or sub-plan.
- Validation:
  - `rg -n "baseline" plans/steward_platform/governing_plan.draft8.md`
  - Confirm the baseline artifact spec includes concrete command-level collection steps.

### 3.1 Open Questions / Assumptions

- The review assumes the draft-8 promotion package will be merged from the `docs/steward-platform-draft-8` / `docs/steward-platform-adr-seeds` worktrees into the canonical repo after this review.
- I treated “promotion-ready” as “safe to rename and kickoff after a tightening pass,” not “already executable with zero package edits.”
- I assumed the missing template files are intended to be real artifacts, not merely informal names for current templates.
- I assumed the `RIN-SnD` path issue is a real environment mismatch, not an intentional hidden checkout.

### 3.2 Short Summary

The plan is strategically ready. The remaining work is a short implementation-tightening pass: fix the B.9↔G dependency loop, repair the 11-item preflight references, add the missing template scaffold, align the digest-script spec, make Pattern 9 true in practice, and correct the shape-audit path assumption. After that, promotion is justified.

---

## 4. Open Questions Back To Orchestrator / Operator

1. Do you want the missing template files (`execution_plan`, `promotion_rollback`, `primitive_closeout`) created before promotion, or do you want the governing plan text reduced to the template set that already exists?
2. What is the actual checkout or access path for `RIN-SnD`? The assumed desktop path is not present in the current environment.
3. For G10, do you already have a preferred default among `replacement / supplement / orthogonal`, or should the kickoff ADR explicitly present all three with no soft preference?

---

## 5. Phase 2 Decision Inputs

**Portability readiness:** positive overall, but the package should not be promoted as “kickoff-ready” until the implementation blockers in §2.2 are resolved; otherwise Phase 0 would begin with avoidable plan-level ambiguity.
**Meta-layer need:** no change; the current review strengthens the case for keeping Phase 0/1 local and disciplined before widening orchestration scope.
**Kill signal for primitive(s) named:** no; none of the findings argue to remove a primitive, only to tighten execution scaffolding and dependency ordering.
**Re-evaluation needed in Phase 3:** no; the required work is pre-promotion tightening, not a future-phase revisit.
**Surprise finding:** the strongest remaining issues are not strategic at all — they are implementation-contract defects (dependency loop, missing template scaffold, ownership-lint miss, parser-schema mismatch), which is a good sign for the overall health of the plan.
**Disposition:** open
