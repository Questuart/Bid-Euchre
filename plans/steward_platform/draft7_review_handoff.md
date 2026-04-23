# Handoff: Steward Platform Governing Plan — Two-Track Review of Draft 7

**Date:** 2026-04-23
**From:** orchestrator (co-drafted with operator)
**To:** steward-analyst (lane TBD by orchestrator dispatch — fresh eyes preferred; analyst-a, analyst-b, analyst-c have all reviewed prior drafts)
**Review target:** `plans/steward_platform/governing_plan.draft7.md` (~1500 lines)
**Companion artifacts to review alongside:**
- `plans/steward_platform/claude_code_changelog_implications.md` (Tier S inventory + per-system rework specs)
- `plans/steward_platform/0_hardening/sub/rework_spec.md` (per-surface tactical sub-plan)

**Review stance:** skeptical; prefer simpler solutions; flag over-engineering; propose better alternatives; judge against the *best plausible plan* standard, not the *workable plan* standard.

---

## Two-Track Review Scope

This is the **most important framing.** The operator wants two distinct review tracks executed in this single dispatch:

### Track 1 — Verification of draft 6 → 7 delta (narrow)

Did the changes from draft 6 to draft 7 land cleanly, with no new structural gaps and no unintended scope contamination?

This track is similar to analyst-c's draft 6 review pattern (per-fix disposition table; new gap findings if any).

### Track 2 — Gap analysis: plan/sub-plan vs. analyst's view (broad)

**This is the operator's explicit additional ask, beyond the narrow verification:** review what the plan and sub-plan are tackling **versus** what the analyst thinks **should** be done, given:

- **Current state of steward** — the 19-lane fleet, the existing ops package, the messaging bus closeout debt, the token-economy Slice F evaluation in flight, the agent_ops Phase 5 fragmentation, the merged PRs through #2748, the live cron-based monitoring, the live remote-channel infrastructure.
- **Current state of the steward code** — the actual modules in `src/bid_euchre/ops/`, the actual hooks in `.claude/hooks/`, the actual skills in `.claude/skills/`, the actual scripts in `scripts/internal/`, the actual rules in `.claude/rules/`, the actual session state in MEMORY.md.
- **Project ambitions** — single-repo proof first → port to Fund + RIN-SnD → eventual meta-layer; the 16 vertical-ambition goals; the operator-as-team reality; the agent-first plan/KB design discipline (goal #16); the native-substrate-adoption discipline (extensibility pattern #2).

**Specific gap-analysis prompts:**

1. **What is the plan/sub-plan addressing that doesn't actually need addressing now?** Items that look load-bearing on paper but don't carry weight given current state.
2. **What is the plan/sub-plan NOT addressing that should be in scope?** Items the operator + orchestrator missed, given how the existing code actually behaves.
3. **What in the existing code is being preserved that should be cut?** Bespoke implementations that native substrate (per Tier S inventory) now obviates.
4. **What in the existing code is being cut that should be preserved?** Pieces of bespoke implementation that the plan or sub-plan disposes of, but that have steward-specific semantics native doesn't cover.
5. **Does the rework_spec.md sub-plan actually cover the existing system completely?** What modules / hooks / scripts / skills are missing from the catalog?
6. **Does the §10.9 extensibility patterns section actually capture what makes the platform durable and extensible long-term?** What patterns are missing or should be reframed?
7. **Does the changelog review skill (§5-D + §6 of addendum) realistically capture the right external-signal sources for a self-improving Claude-Code-first platform?** What sources are missing? What scraping is over-scoped?

Both tracks land in the same review artifact at `plans/steward_platform/draft7_review_<lane>.md`. Use clear section headers to separate Track 1 from Track 2 deliverables.

---

## Prior lineage (skim, don't re-derive)

Seven iterations: draft 1 (operator) → analyst-a review (graded B) → drafts 2/3/4 (orchestrator) → analyst-b review of draft 5 (graded B+) → operator directives → draft 6 → analyst-c narrow review (graded A-, recommended PROMOTE-AFTER-G-FIXES) → operator directives + Tier S × system-rework + companion-artifact additions → **draft 7**.

All drafts and reviews are committed to `plans/steward_platform/`:

- `governing_plan.md` — draft 1 (preserved)
- `governing_plan.draft2.md` through `governing_plan.draft6.md` — preserved
- **`governing_plan.draft7.md` — under review now**
- `draft2_review_analyst-a.md` (806 lines)
- `draft5_review_analyst-b.md` (1045 lines)
- `draft6_review_analyst-c.md` (427 lines)
- `phase2_harness_engineering_research.md` — borrowed-practices memo (companion)
- `post_phase2_sidecar.md` — deferred-ideas parking lot (companion)
- **`claude_code_changelog_implications.md` (NEW in draft 7)** — Tier S inventory + per-system rework specs + changelog review skill spec (companion to the plan; refreshed by `/review-claude-changelog`)
- **`0_hardening/sub/rework_spec.md` (NEW in draft 7)** — per-surface tactical sub-plan; Phase 0 execution artifact under Primitive G

## What changed draft 6 → draft 7 (the delta under Track 1 review)

**Track A — analyst-c gap findings (G1–G5) + operator clock-time directive:**

| Finding | Disposition in draft 7 |
|---|---|
| G1 (medium) Agent-readability lint script load-bearing but floating | ADOPTED. `agent_readability_lint.py` + `/lint-agent-readability` skill added to Primitive C Work + Phase 0 Readiness. |
| G2 (low) `Slice elapsed:` enforcement asymmetric | RESOLVED by clock-time mechanism removal (no `Slice elapsed:` requirement → no enforcement asymmetry to fix). |
| G3 (low-medium) Primitive C density | ADOPTED light option. One-paragraph thematic-coherence justification added to §5-C explaining why C's deliverables form a single coherent cluster without needing a sub-deliverables table. |
| G4 (low-medium) §15 schema didn't represent "insufficient evidence" class | ADOPTED. 5th prompt added to §15.2 schema: `**Re-evaluation needed in Phase 3:**`. §15.4 digest spec extended; §15.7 Phase 2 use extended with 5th bucket. |
| G5 (low, editorial) §13 duplicate item "17" | ADOPTED. §13 renumbered cleanly. |
| Q3 (low) §11-H post-hoc scenario timing | ADOPTED. Clarified as "during Phase 1 as the proving run accumulates." |
| Operator directive — clock-time simplification | ADOPTED. `Slice elapsed:` mechanism removed from step 5; §3 + §4.1 + §11 simplified to intent-only language; SC #18 removed; §11 soft trigger simplified to single-signal (activity volume only). |

**Track B — Tier S × system-rework integration (per Claude Code changelog implications):**

Per-primitive native-substrate adoption:

| Primitive | Native-substrate adoptions added |
|---|---|
| A (trace + observability) | Monitor tool; conditional hooks; lifecycle hooks (PermissionDenied/StopFailure/TaskCompleted/TeammateIdle/ConfigChange); session metadata (`${CLAUDE_SESSION_ID}`, `last_assistant_message`, session title); recaps; HTTP hooks; `schema_version` field |
| B (adaptive dispatch + skill + prompt-policy) | B.8 native task system evaluation (ADR); B.9 `--system-prompt-file` per lane (Boris Cherny / davidad signal); B.10 effort-level configuration per task type (`/effort` xhigh-default, max-for-hardest) |
| C (KB + memory) | Shared project memory across worktrees; auto memory supplementary; plugin executables on PATH; tool-search; `agent_readability_lint.py` (G1); `/autofix-pr` evaluation ADR (ADR 005); Auto mode codification ADR (ADR 006) |
| D (archivist) | Native lifecycle hook streams as inputs; recaps as session-postmortem input; `/cost` outlier signal; **changelog review skill** (`/review-claude-changelog` scheduled 2-3×/week; scrapes official changelog + operator-curated external-signal sources from `knowledge/external_signal_sources.md`) |
| E (messaging + active triage) | Conditional hooks; TeammateIdle (replaces heartbeat classifier); StopFailure; HTTP hooks; native channels evaluation; ADR 004 hook migration boundary |
| F (token economy) | Native `/usage` (parallel sessions / subagents / cache misses / long context breakdown); native `/cost`; read-tool token reductions baseline re-capture; per-tool MCP result-size override; ADR 003 native vs. bespoke boundary |
| G (existing-debt closeout + native migration) | **Major scope reshape.** Worktrees migration (~80% LOC reduction); Setup hook formalizes `steward-session.sh` bootstrap; remote-control / remote sessions for away-mode; heartbeat retirement; `/fewer-permission-prompts` periodic; skills consolidation per `rework_spec.md` |
| H (reliability lab) | Monitor tool for replay assertions; read-tool reductions baseline; conditional hooks for canary triggers; verification pattern (`/go`-style) framing |

**Track C — new sections:**
- §4.2 9th audit item (Native Claude Code adoption state)
- §10.9 Extensibility patterns (six cross-cutting principles)
- §15.3 new tag (`native-substrate-signal`)
- §15.2 5th prompt (per G4)
- §13 success criteria #19 (changelog scan produces signal) + #20 (≥1 native-substrate adoption lands)
- §14 Open items expanded with ADRs 002–006 + `external_signal_sources.md` initial content
- New addendum file `claude_code_changelog_implications.md`
- New sub-plan `0_hardening/sub/rework_spec.md`

## Track 1 deliverables (verification)

- **Per-fix disposition table** for the 7 G/Q/operator-directive items above. ADOPTED-CLEAN / ADOPTED-WITH-GAP / NOT-ADOPTED / SUPERSEDED-BY-OPERATOR.
- **Per-primitive Tier S integration disposition** for each of A/B/C/D/E/F/G/H. Did the native-substrate adoption land coherently in each primitive?
- **New gap findings (G6, G7, ...)** if integration introduced new structural issues.
- **Promotion recommendation:** PROMOTE-AS-IS / PROMOTE-AFTER-FIXES / REVISE-DRAFT-8.

## Track 2 deliverables (gap analysis)

- **Plan-vs-actual gap table** with one row per identified gap. Format:

  ```
  | Gap | Plan/sub-plan position | Analyst position | Severity | Proposed action |
  |---|---|---|---|---|
  ```

- **Existing-system rework critique** of the `rework_spec.md` sub-plan: completeness, accuracy, missing modules / hooks / skills / scripts.
- **Extensibility patterns critique** of §10.9: missing patterns, over-codified patterns, mis-framed patterns.
- **Changelog review skill source critique:** what's missing from the source list, what's over-scoped.
- **Strategic gaps:** anything the plan implicitly assumes about steward state, code, or ambitions that doesn't actually hold.

## Updated grade

Default scale: A / A- / B+ / B / B- / C+ / C / below. Draft 6 was A-.

## Out-of-scope

- Re-litigating analyst-a/b/c findings (all dispositioned in prior reviews).
- Challenging fixed constraints unless you have a specific load-bearing argument: single-repo Phase 0/1; vertical-ambition floor of 16 goals; prove-before-port; Primitive H in Phase 1; hybrid subsections+digest pattern; deferred meta-layer; clock-time intent-only (no mechanism); F3 Option B (sub-deliverables table for Primitive B); goal #16 agent-first design.

If you find something material outside scope, surface as an open question, not a finding.

## Mechanics

- **Write scope:** `plans/steward_platform/` for the review artifact only. Do not edit drafts 1-7.
- **Write the review under goal-#16 conventions** (predictable structure; machine-parseable disposition table; grep-clean cross-references; per-finding stable IDs G6, G7, ...; clear Track 1 / Track 2 separation).
- **Time expectation:** this is a two-track review. Track 1 is narrow (1-2 hours focused work appropriate). Track 2 is broader (2-3 hours; reading the actual ops code in `src/bid_euchre/ops/` is in scope for a thorough Track 2 pass — without code-reading, the gap analysis is shallow).
- **Total expected effort:** 3-5 hours focused work. Depth where it matters; pass-through where draft 7 cleanly resolved a prior finding.
- **Escalation:** if you find a blocker, message orchestrator with concrete question rather than stalling.

Take the stance that the plan should be promotion-ready — but don't lower the bar to ship it. The goal is the **best plausible plan**, not just a workable one.

## Note on prior BLOCKER pattern

If draft 7 + companion artifacts aren't visible from your worktree at task-start, you've hit the same lineage-sync issue analyst-b hit on draft 5. Sync your worktree (`git fetch origin; git pull --rebase origin/main`); the orchestrator commits draft 7 + companions before dispatching this packet. If they're still not visible, write a structured BLOCKER per analyst-b's pattern (`draft7_review_BLOCKER.md`) and the orchestrator will reshape.
