# Handoff: Steward Platform Governing Plan — Final Pre-Promotion Review

**Date:** 2026-04-23
**From:** orchestrator (co-drafted with operator across an 8-draft lineage + 4 analyst reviews + 1 plugin source evaluation)
**To:** steward-analyst (fresh eyes — analyst-a/b/c/d all reviewed prior drafts; any flex lane or external agent suitable)
**Purpose:** Two-track final review before promotion to canonical `governing_plan.md`. The plan has been through four analyst reviews (B → B+ → A- → A) plus a plugin-source-evaluation cycle. This final review is the pre-promotion check: **is the artifact set holistically sound AND implementation-ready?**

**Review stance:** skeptical; best-plausible-plan standard; flag over-engineering; propose better alternatives. Fixed constraints (listed below) should not be relitigated unless you have a load-bearing argument.

---

## 1. What is being reviewed

Full artifact set on `origin/main`, all paths relative to repo root.

### 1.1 Primary review targets

- `plans/steward_platform/governing_plan.draft8.md` — the governing plan (ready for promotion rename to `governing_plan.md`)
- `plans/steward_platform/claude_code_changelog_implications.md` — Tier S inventory + per-system rework specs + changelog review skill spec + plugin discovery section
- `plans/steward_platform/0_hardening/sub/rework_spec.md` — per-surface tactical sub-plan (ops modules / scripts / hooks / skills / plans / worktrees with disposition catalog)
- `plans/steward_platform/plugin_source_evaluation.md` — analyst-a's source-grounded evaluation of 4 Claude Code native-substrate plugins
- `plans/steward_platform/adrs/README.md` — ADR index
- `plans/steward_platform/adrs/005-review-plugin-evaluation.md` — official code-review plugin
- `plans/steward_platform/adrs/007-observability-plugin-evaluation.md` — `melodic-software/claude-code-observability`
- `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` — `doobidoo/mcp-memory-service`
- `plans/steward_platform/adrs/B8-native-task-system-evaluation.md` — Agent Teams + TeammateTool

### 1.2 Lineage context (skim, don't re-derive)

Preserved drafts 1-7 available for diffing; prior review artifacts available as lineage evidence:

- `governing_plan.md` (draft 1, operator original)
- `governing_plan.draft2.md` through `governing_plan.draft7.md`
- `draft2_review_analyst-a.md` (806 lines, graded B)
- `draft5_review_analyst-b.md` (1045 lines, graded B+)
- `draft6_review_analyst-c.md` (427 lines, graded A-)
- `draft7_review_analyst-d.md` (901 lines, graded A, PROMOTE-AFTER-FIXES)
- `phase2_harness_engineering_research.md` — borrowed-practices memo
- `post_phase2_sidecar.md` — deferred ideas
- `draft{2,5,6,7}_review_handoff.md` — prior-review handoffs
- `plugin_source_evaluation_handoff.md` — analyst-a's plugin source-evaluation handoff

---

## 2. Two-Track Review Scope

### Track A — Holistic review

Apply the standard governing-plan rubric to the *full integrated artifact set* (not just draft 8 in isolation). Each dimension gets an explicit grade (A / A- / B+ / B / B- / C+ / C / below) with one-sentence reasoning.

1. **Strategic clarity** — does the plan define the right destination? Is the "governed self-improvement loop inside a project cell" framing sound, falsifiable, and useful for agent execution?
2. **Platform thesis quality** — is the native-substrate-first + bespoke-orchestration-spine thesis defensible? Is it consistent across the plan + ADR seeds?
3. **Scope discipline** — 8 primitives, 16 goals, B.1-B.12 sub-deliverables, 9 §10.9 patterns, 20 success criteria, 11-item preflight. Is this proportional to the problem, or has the plan inflated across 8 revisions?
4. **Simplicity and leverage** — where is bespoke scope still high relative to value produced? Are there primitives or sub-deliverables that should collapse or defer?
5. **Execution realism** — given operator-as-team and the actual steward codebase, is this shippable in a reasonable timeframe? Which primitives have the highest cost/time underestimate risk?
6. **Directive quality** — are the prescribed methods (e.g., Phase 1 dual-track with Primitive H concurrent; hybrid subsections + digest; agent_readability_lint enforcement) the best shape for the outcomes?
7. **Risk handling** — does §12 Risks cover the real failure modes? What risks are missing? Particularly: improvement-loop overfitting, plugin-ecosystem adoption risks, Primitive A cascade risk, plan fragmentation under Phase 0 execution.
8. **Adaptability** — can Phase 2 pivot cleanly to any of (a) portability to a second repo, (b) meta-layer build, (c) further single-repo iteration, (d) kill specific primitives, (e) cross-project learning? Does the plan gate enough but not over-gate?

**Track A deliverables:**
- Per-dimension grade + reasoning
- Overall grade (default scale above)
- Final recommendation: **PROMOTE-AS-IS** / **PROMOTE-AFTER-FIXES** / **REVISE-DRAFT-9**

### Track B — Implementation review

**Core question: could an author lane start Phase 0 work against this tomorrow?** This is the track none of the prior reviews explicitly covered.

Evaluate the plan's *implementation readiness*:

1. **Phase 0 startability.** Pick any two Phase 0 primitives at random. Could an author lane open a scope-locked task packet and start implementing today? If no, what's missing — sub-plan detail? ADR decisions? Schema spec? Template scaffolding?

2. **Dependency graph.** §5 primitives reference each other (e.g., Primitive E active-triage depends on Primitive A event-schema; Primitive D archivist depends on Primitive A traces; Primitive B sub-deliverables cross-reference). Is the dependency graph acyclic? Are there hidden circular dependencies between primitives' Phase 0 Readiness criteria?

3. **ADR seed readiness.** `plans/steward_platform/adrs/005/007/010/B8.md` are marked SEEDED. Are they *actually promotion-ready*, or do they have gaps that need operator input before Phase 0 kickoff filing? Spot-check each: does it name its owning primitive? Does it have concrete Decision text? Are the Consequences testable? Are the Open Questions actually scoped?

4. **Open Item completeness (§14).** 17 Open Items. For each, can an author or analyst lane take ownership and resolve it? Or are some hand-wavy ("evaluate X", "calibrate Y") without enough structure to start?

5. **Baseline capture readiness (§4.3).** Can baseline capture actually run today? Is the measurement mechanism specified, or is it "capture a baseline" with no tooling?

6. **Shape audit readiness (§4.2).** Could an analyst lane start a Fund or RIN-SnD shape audit this week with the 9-item output format specified? Are there missing inputs (access to those repos, audit-tool readiness, etc.)?

7. **Preflight readiness (§6).** Is Phase 1a concrete enough that an operator + author lane could select a preflight task and execute the 11 checklist items? Or are some items ("end-to-end data discipline probe") still too abstract?

8. **Success criteria measurability (§13, 20 items).** For each SC, can you point to the specific artifact or metric that would be inspected? Or are some SCs ("attention compression relative to baseline") under-specified?

9. **Kill criteria falsifiability (§11, 8 rows).** For each kill row, are the thresholds observable during a real proving run? Are any still self-sympathetic per analyst-b's original critique pattern?

10. **Template scaffolding.** `plans/_templates/` is referenced but its contents are partly aspirational. What templates must exist before Phase 0 kickoff vs. which can be filled during Phase 0?

11. **Script scaffolding.** Primitive C names `compile_decision_inputs.py`, `agent_readability_lint.py`; Primitive D names `archivist.py`, `changelog_review.py`; Primitive G references `sweep_session_plans.py`. Each has a spec in the plan. Are the specs concrete enough for an author lane to build, or are there ambiguities that would stall implementation?

12. **`.claude/system_prompts/<archetype>.md` vs. `.claude/agents/<lane>.md` reconciliation (G10).** Draft 8 Primitive G Readiness says "relationship resolved via ADR at Phase 0 kickoff." Is the ADR candidate text ready to file, or is this still operator-decision-pending?

13. **Lane archetype mapping (G13).** Draft 8 names 8 archetypes (orchestrator / ops / review / analyst / author / brws-author / flex / scratch) but the 19-lane → 8-archetype mapping is listed as "Primitive G first-deliverable sub-sub-plan." Is that sub-sub-plan a substantial work item or a quick mapping exercise?

14. **Plugin source evaluation fold-in completeness.** Do the four ADR seeds (005/007/010/B8) fully capture analyst-a's findings, or are there decisions in `plugin_source_evaluation.md` that should also surface elsewhere (e.g., in §5-A Work bullets, in §11 kill criteria, in §12 Risks)?

15. **Cross-reference integrity.** Goal #16 Pattern 9 (load-bearing-ownership lint) says every file/module/script referenced in §N.M must be enumerated in owning primitive's Work + Readiness. Spot-check 5-10 cross-references: do they resolve cleanly?

**Track B deliverables:**
- Implementation-readiness scorecard per the 15 questions above (READY / READY-WITH-FIXES / NOT-READY with blocker)
- Concrete blocker list (what must land before Phase 0 kickoff can begin)
- Per-ADR readiness assessment
- Overall implementation-readiness verdict: **SHIP** / **SHIP-AFTER-FIXES** / **NOT-READY**

---

## 3. Fixed constraints (do not relitigate without load-bearing reason)

These are operator-affirmed decisions across the 8-draft lineage. Challenge is acceptable only with a specific new argument not previously considered:

- **Single-repo Phase 0/1** — Bid-Euchre only until Phase 2 decision gate
- **Prove-before-port** — research proving run validates platform before portability decision
- **Vertical-ambition floor: 16 goals** — no cuts
- **Goal #16 agent-first design** — agents are primary audience; humans secondary
- **Primitive H in Phase 1, not Phase 0** — concurrent with proving run
- **F3 Option B** — Primitive B unified with sub-deliverables table (B.1-B.12), not split into B1/B2
- **Clock-time intent-only** — no mechanism / no `Slice elapsed:` write discipline; time is diagnostic
- **Native-substrate three-tier preference** (§10.9 Pattern 2) — native → official plugin → third-party plugin → bespoke
- **Hybrid subsections + digest pattern** (§15) — 5 prompts + disposition; `compile_decision_inputs.py` generates digest
- **ADR adoption decisions per analyst-a source evaluation:**
  - ADR 005: retain `review_driver.py`; cherry-pick parallel + validator-subagent patterns
  - ADR B8: keep `task_queue.py` bespoke; adopt lifecycle hooks + SendMessage as supplemental
  - ADR 007: adopt dispatcher pattern in bespoke `ops/events.py` with §9.7 IDs first-class
  - ADR 010: reject wholesale mcp-memory-service adoption; Phase 3 soft re-evaluation trigger

---

## 4. Up for challenge

Items the operator has invited scrutiny on:

- Any ADR seed wording (005/007/010/B8)
- Kill criterion thresholds (§11, 8 rows)
- Preflight item specificity (§6.4, 11 items)
- §10.9 Patterns 7/8/9 (newer additions; less battle-tested)
- Phase 1 Validation criteria measurability (every primitive's validation section)
- Any §14 Open Item that feels under-scoped
- Whether the plan's companion-artifact count (plan + changelog-implications + rework-spec + plugin-source-evaluation + 5 ADRs) is sustainable or whether consolidation would improve agent loadability
- Whether the sub-plan (`rework_spec.md`) has over-scoped the rework or correctly scoped it
- Whether the 4 seeded ADRs should be promoted-as-drafts at kickoff or iterated further before filing

---

## 5. Deliverables

Produce `plans/steward_platform/draft8_final_review_<your-lane>.md` containing:

### 5.1 Track A (Holistic)
- Per-dimension grade table (8 dimensions)
- Overall grade
- Final recommendation (PROMOTE-AS-IS / PROMOTE-AFTER-FIXES / REVISE-DRAFT-9)
- Rationale (absolute terms, not relative to team capacity)

### 5.2 Track B (Implementation)
- Per-question scorecard (15 questions)
- Concrete blocker list
- Per-ADR readiness assessment (005 / 007 / 010 / B8)
- Overall implementation-readiness verdict (SHIP / SHIP-AFTER-FIXES / NOT-READY)

### 5.3 New gap findings

For each new finding:
- Stable finding ID (H1+ for holistic / I1+ for implementation, to avoid collision with prior F1-F13 / G1-G13)
- Severity (high / medium / low)
- Evidence citation (`§N.M` of plan or sub-plan or ADR)
- Why it matters
- Proposed fix (concrete text or concrete action)
- Cost to fix (low / medium / high)

### 5.4 Open questions back to orchestrator / operator

For anything requiring operator disposition before promotion.

### 5.5 Phase 2 Decision Inputs subsection (per §15.2 schema)

Standard 5-prompt + disposition subsection.

---

## 6. Mechanics

- **Write scope:** `plans/steward_platform/` for the review artifact only. Do not edit the plan, sub-plan, ADRs, or any companion files.
- **Write the review under goal-#16 conventions:**
  - Predictable `§N.M` section IDs
  - Machine-parseable tables for scorecards and dispositions
  - `path/from/repo/root.md` cross-references (no `./` or `../`)
  - Grep-clean stable finding IDs (H1+ or I1+ to avoid collision with prior F1-F13 / G1-G13)
  - Loadable as agent context with minimal preamble
- **Time expectation:** 4-6 hours focused work. Track A is ~1-2h rubric application. Track B is 2-3h — requires actually reading the ADR seeds line-by-line and spot-checking cross-references. Track B is the value-add; don't skip its specificity.
- **Code reading is in scope.** Spot-check `src/bid_euchre/ops/` modules referenced in Pattern 9 lint audits. Spot-check `scripts/internal/` for scripts that already exist vs. the new scripts named in the plan.
- **Reading prior reviews is optional** but recommended for context on gap patterns that have already been caught and resolved.
- **Escalation:** if you find a blocker that requires operator disposition before finalization, write a partial review and message the orchestrator with a specific question rather than stalling.

---

## 7. What "promotion-ready" means concretely

If your recommendation is **PROMOTE-AS-IS** or **PROMOTE-AFTER-FIXES** (with fixes being tightening-pass scope, not rework), the next operator action is:

1. Rename `plans/steward_platform/governing_plan.draft8.md` → `plans/steward_platform/governing_plan.md`
2. Move drafts 1-7 to `plans/steward_platform/_archive/`
3. File the 4 seeded ADRs (005/007/010/B8) + ADR 001 (platform pattern reset + agent-readability floor) + ADR 006 (Auto mode codification) at Phase 0 kickoff with operator signoff + filing date
4. Start Phase 0 Primitive G work (debt closeout + native migration)

Your review should confirm or deny that the above is safe to proceed against.

---

## 8. Note on lineage

This plan has been the subject of unusually extensive review (4 prior analyst reviews + 1 plugin source evaluation across 8 drafts). The grade trajectory (B → B+ → A- → A) suggests each review cycle has improved the artifact rather than revealed new structural issues. **Your review is the final adversarial check.** If you find material issues that the 4 prior reviews missed, that's valuable — but don't manufacture issues to justify the review. If the plan is ready to ship, say so.

The draft-1-through-draft-8 review-revision cycle is itself empirical evidence for the platform's self-improvement loop discipline (§1 Decision reframe). Reflecting on that evidence is in scope for Track A dimension 2 (platform thesis quality).
