# Steward Platform Governing Plan — Draft 7 Two-Track Review (analyst-d)

**Date:** 2026-04-23
**Reviewer:** steward-analyst (lane analyst-d — fresh eyes; analyst-a reviewed draft 2, analyst-b reviewed draft 5, analyst-c reviewed draft 6; all three recused)
**Target:** `plans/steward_platform/governing_plan.draft7.md` (1265 lines)
**Companion artifacts under review:** `plans/steward_platform/claude_code_changelog_implications.md` (188 lines); `plans/steward_platform/0_hardening/sub/rework_spec.md` (200 lines)
**Scope:** Two-track. **Track 1** — narrow verification of draft 6 → 7 delta (analyst-c G1–G5 + Q3 + operator clock-time directive + Tier S × system-rework integration across Primitives A–H + new §10.9 / §15.3 / §15.2 fifth prompt / SC #19–#20). **Track 2** — plan/sub-plan scope vs. analyst's view of what should be in scope given current steward state, current code, and project ambitions.
**Prior reviews:** `plans/steward_platform/draft2_review_analyst-a.md` (B), `plans/steward_platform/draft5_review_analyst-b.md` (B+), `plans/steward_platform/draft6_review_analyst-c.md` (A-).
**Review stance:** skeptical; best-plausible-plan not workable-plan; prefer simpler solutions; flag over-engineering; propose better alternatives.
**Self-conformance note:** This artifact is written under goal-#16 agent-first conventions it is being asked to evaluate — predictable `§N.M` section IDs; machine-parseable disposition tables; `path/from/repo/root.md` cross-references; stable G6–G13 finding IDs that do not collide with analyst-a's S/SC/D/R, analyst-b's F1–F13, or analyst-c's G1–G5/Q1–Q4.

---

## TL;DR

**Track 1 verdict.** The draft 6 → 7 delta is substantively clean. All 5
analyst-c gap findings (G1–G5), Q3, and the operator clock-time directive
are ADOPTED-CLEAN. The Tier S × system-rework integration lands coherently
across Primitives A–H with per-primitive native-substrate adoption lists
tied to identified existing code surfaces. The two new companion artifacts
(`claude_code_changelog_implications.md` + `0_hardening/sub/rework_spec.md`)
are substantive, not placeholders. The six new §10.9 extensibility
patterns are codified and tied to enforcement surfaces, not aspirational
prose.

**Track 2 verdict.** The plan is well-framed against the overall ambition
(single-repo proof → port → meta-layer; 16 goals; agent-first;
native-substrate-first). The biggest Track 2 concerns are **coverage
gaps in `rework_spec.md`** (~21 of ~42 `src/bid_euchre/ops/` modules
uncatalogued; all ~34 concrete hook files folded under ~10 category rows;
`.claude/agents/` directory entirely absent from the catalog) and a
**sub-plan-vs-agents-file relationship that B.9 does not reconcile**
(new `.claude/system_prompts/<lane>.md` files vs. existing
`.claude/agents/<lane>.md` files already loaded by the Agent tool). No
strategic direction is wrong; rather the plan's execution surface is
larger than the sub-plan currently names.

**Track 1** introduces **eight new gap findings (G6–G13)**, none of
which require a draft 8 review cycle. G6 (rework_spec ops-module coverage
hole) is the only medium-severity finding; the rest are tightening items
addressable in the same promote-with-fixes pass.

**Grade: A.** Up from draft 6's A-, on the strength of the Tier S
integration substance and the extensibility-patterns codification.
Draft 7 is visibly sharper than draft 6 on *both* the native-substrate
discipline and the plan-as-infrastructure framing. G6 is not
grade-dragging because rework_spec.md is a Phase 0 execution sub-plan,
not the governing plan itself — its catalog gaps are sub-plan-level
tightening, not plan-level defects.

**Recommendation: PROMOTE-AFTER-FIXES.** Apply G6 (mandatory sub-plan
tightening before Phase 0 kickoff) and as many of G7–G13 as persuasive
in a single tightening pass. Promote
`plans/steward_platform/governing_plan.draft7.md` → `governing_plan.md`
without a draft-8 narrow review. Companion artifacts should land in the
same commit.

---

## 1. Track 1 — Verification of Draft 6 → 7 Delta

### 1.1 Per-Fix Disposition Table (analyst-c G1–G5 + Q3 + operator directive)

Disposition values: **ADOPTED-CLEAN** / **ADOPTED-WITH-GAP** /
**NOT-ADOPTED** / **SUPERSEDED-BY-OPERATOR**.

| ID | Source | Disposition | Evidence in `plans/steward_platform/governing_plan.draft7.md` |
|---|---|---|---|
| G1 | analyst-c medium — agent-readability lint script load-bearing but floating | **ADOPTED-CLEAN** | §5-C Work bullet names `scripts/internal/agent_readability_lint.py` (~100 lines, invokable as `/lint-agent-readability`) with full description of target directories (`plans/**/*.md`, `knowledge/**/*.md`, `.claude/skills/**/*.md`) and violation classes (missing `§N.M` IDs, inconsistent cross-reference style, schemas without worked examples, preambles >~25 lines, orphan references, duplicate IDs); §5-C Phase 0 Readiness adds the "committed; runs against the repo plan/KB tree and either passes clean or produces a documented baseline" condition; `/lint-agent-readability` skill registered. Exact F6/G1 fix shape applied symmetrically. |
| G2 | analyst-c low — `Slice elapsed:` enforcement asymmetry | **RESOLVED-BY-DIRECTIVE** | Operator clock-time directive removed the `Slice elapsed:` write-discipline mechanism (§3 "Relative clock-time (intent)" rewrite, §4.1 phase table no-budget note, §4.4 step 5 removal of elapsed-time line, §13 SC #18 removal, §11 preamble simplification to single-signal). With no `Slice elapsed:` line to enforce, the asymmetry G2 flagged no longer exists. Properly dispositioned. |
| G3 | analyst-c low-medium — Primitive C density | **ADOPTED-CLEAN (light option)** | §5-C preamble adds explicit "Thematic-coherence justification (G3, draft 7)" paragraph naming the 8 deliverables, the single write-discipline surface (`/create-plan` + `/create-adr` + `/lint-agent-readability`), the single semantic purpose (agent-loadable durable knowledge surviving session boundaries), and why C's mix differs from pre-Option-B B's heterogeneous dispatch/skill/policy/risk-registry span. Uses analyst-c's proposed Option (b), not the heavier sub-deliverables table. |
| G4 | analyst-c low-medium — §15 schema missing "insufficient evidence" class | **ADOPTED-CLEAN** | §15.2 schema adds 5th prompt `**Re-evaluation needed in Phase 3:** [one sentence with recommended evaluation window if "insufficient evidence" applies, or "no"]`; §15.4 digest spec extended to parse five prompts; §15.7 Phase 2 use extended with fifth "re-evaluation decisions" bucket; §11 preamble names the trigger explicitly as "flagged at Phase 2 as 'insufficient evidence'" with cross-reference to §15.2 5th prompt. Symmetric to §11 trigger. |
| G5 | analyst-c low editorial — §13 duplicate "17" | **ADOPTED-CLEAN** | §13 renumbered clean: items #1–#18 are the pre-draft-7 criteria (formerly #1–#18 with the duplicate), #19 is "Changelog review skill produces ≥1 signal" (new per draft 7), #20 is "≥1 native-substrate adoption lands" (new per draft 7). No duplicate item numbers. One-line fix applied as promised. |
| Q3 | analyst-c low — §11-H post-hoc scenario selection timing | **ADOPTED-CLEAN** | §5-H Phase 1 Validation row "At least one scenario is selected post-hoc by an analyst lane during Phase 1, after primitives A, B, and E ship (Q3 clarification — timing is during Phase 1 as the proving run accumulates, not at end of phase)"; §11-H kill row repeats the "selected post-hoc by an analyst lane after primitives A/B/E ship" phrasing. Timing unambiguous. |
| OD-clock | operator directive — clock-time simplification | **ADOPTED-CLEAN** | §3 rewrites "Relative clock-time (intent)" as diagnostic-input-not-mechanism framing; §4.1 phase table loses absolute clock-time budgets and gains "sequencing and readiness/validation gates are the discipline" note; §4.4 step 5 no longer mandates `Slice elapsed:` line; §13 SC #18 (relative clock-time recording) removed cleanly; §11 preamble two-signal table collapses to single-signal (activity volume); §11 preamble closes "Draft 6's two-signal differentiation using relative elapsed time was removed per operator directive — elapsed time remains available as a diagnostic input post-hoc but is not a formal gating signal." Consistent across all sites. |

**Summary:** 5/5 analyst-c G-findings ADOPTED-CLEAN (G2 properly
dispositioned as resolved by operator directive, not separately adopted).
Q3 ADOPTED-CLEAN. Operator clock-time directive ADOPTED-CLEAN. No prior
fix reversed; no fixed constraint violated; no scope silently expanded.

### 1.2 Per-Primitive Tier S × System-Rework Integration Table

Each primitive's native-substrate adoption evaluated for: (a) features
named concretely (not hand-wave); (b) existing-code surface identified
(not floating); (c) Phase 0 Readiness / Phase 1 Validation rows updated
to reflect native adoption; (d) no contradiction with prior structure.

| Primitive | Tier S adoptions named | Existing code surface identified | Readiness/Validation updated | Contradictions | Disposition |
|---|---|---|---|---|---|
| A (trace/observability) | Monitor tool; conditional hooks; 5 lifecycle hooks (PermissionDenied/StopFailure/TaskCompleted/TeammateIdle/ConfigChange); HTTP hooks; session metadata (`${CLAUDE_SESSION_ID}`, `last_assistant_message`, session title); recaps; `schema_version` field | `ops/monitor.py` (polling) and `ops/attention.py` named as replacement targets; Phoenix exporter wired via HTTP hooks not shell-glue; native lifecycle hooks subscribe into unified schema; F12 schema versioning preserved with native hooks treated as `v1.N` additive | §5-A Work bullets updated; §5-A Readiness "event-driven attention routing wired end-to-end (at least one event class routes to operator without polling)" absorbs native-substrate use | none | **ADOPTED-CLEAN** |
| B (dispatch/skill/prompt-policy) | B.8 native task/dependency system evaluation ADR; B.9 `--system-prompt-file` per lane with `.claude/system_prompts/<lane>.md`; B.10 effort-level configuration `/effort` (lower/xhigh/max per Boris Cherny) | B.8 names `task_queue.py` for evaluation; B.9 names `steward-session.sh` bootstrap surface and calls out default-system-prompt-degrades-4.7+ harness assumption; B.10 ties to B.1 dispatch policy records | §5-B sub-deliverables table extended B.1–B.10 with per-row Readiness/Validation/Kill; §11-B row 1 absorbs B.10; §11-B row 2 absorbs B.6/B.7/B.8/B.9 | G10 below (B.9 relationship to `.claude/agents/<lane>.md` is unclear) | **ADOPTED-WITH-GAP → G10** |
| C (KB/memory) | shared project memory across worktrees; auto memory supplementary; plugin executables on PATH; tool-search; `agent_readability_lint.py` (G1); `/autofix-pr` evaluation ADR 005; Auto mode codification ADR 006 | Shared memory targets `MEMORY.md` + `ops/memory.py`; auto memory feeds archivist candidate pipeline; plugin PATH targets `.claude/skills/` distribution; `agent_readability_lint.py` ~100 LOC named concretely; ADRs 005/006 enumerated in §14 | §5-C Work + Readiness + Validation updated; new G1-fix Readiness bullet; thematic-coherence justification paragraph for G3 | none | **ADOPTED-CLEAN** |
| D (archivist/changelog) | Native lifecycle hook streams as inputs; recaps + last_assistant_message as session-postmortem input; `/cost` outlier signal; new **changelog review skill** `/review-claude-changelog` scheduled 2-3×/week | `scripts/internal/archivist.py` (Phase 0 + 1) + new `scripts/internal/changelog_review.py` (~75 LOC); `knowledge/external_signal_sources.md` seed; changelog sources named explicitly (`changelog`, `whats-new`, weekly pages, wayback best-effort, operator-curated URLs) | §5-D Work expanded with full changelog-review-skill spec; §5-D Readiness adds scheduling + output format + integration points; §13 SC #19 new success criterion ties skill to measurable signal output | G8 below (changelog skill source list may be over-scoped on wayback crawl and under-scoped on GitHub release notes / ADR-style docs.anthropic.com blog) | **ADOPTED-WITH-GAP → G8** |
| E (messaging/triage) | Conditional hooks; TeammateIdle (replaces heartbeat); StopFailure; HTTP hooks; native channels evaluation; ADR 004 hook migration boundary | `ops/dashboard.py` heartbeat classifier (just shipped via #2743) explicitly flagged for retirement; ADR 004 hook-migration boundary scoped; HTTP hooks replace shell-glue | §5-E Work expanded; §5-E Readiness "Active-triage wiring live for at least 4 event classes (CI red, review blocked, stalled lane, token-burn anomaly)" ties to native lifecycle subscriptions | none | **ADOPTED-CLEAN** |
| F (token economy) | Native `/usage`; native `/cost`; read-tool token reductions baseline re-capture; per-tool MCP result-size override; ADR 003 native vs. bespoke boundary | Slice F evaluation protocol (PR #2716); `ops/token_economy.py` 22 hard-blocks explicitly noted as still needing bespoke fix; `/usage` as comparison feed against steward rollups with discrepancy-flag logic | §5-F Work expanded with `/usage` comparison feed; re-capture baseline noted; per-tool MCP override applied to specific commands (`dashboard`, `task list`, `inbox`); Phase 0 Readiness "Baseline tokens-per-merge captured in §4.3" | none | **ADOPTED-CLEAN** |
| G (debt closeout + native migration) | WorktreeCreate/Remove + declarative isolation; Setup hook; remote sessions; heartbeat retirement; `/fewer-permission-prompts` periodic; skills consolidation; tool-search | Names `ops/worktrees.py` 44 hard-blocks → ~80% LOC reduction target; `steward-session.sh` bootstrap → Setup hook; `ops/dashboard.py` heartbeat retirement; skills consolidation references `rework_spec.md` dispositions (monitoring 6→2, playtest 4→2) | §5-G scope reshape paragraph opens with "Major scope reshape (draft 7)"; Readiness bullets enumerate each migration; Phase 1 Validation explicitly notes "n/a for core debt closeout; however, the native-substrate migrations … are measured during the proving run as part of other primitives' Phase 1 Validation" | G6/G7/G9/G13 below (rework_spec coverage holes, worktrees.py registry state preservation, skill count math, agent-file reconciliation) | **ADOPTED-WITH-GAP → G6/G7/G9/G13** |
| H (reliability/replay) | Monitor tool for replay-assertion polling; read-tool reductions baseline; conditional hooks for canary triggers; verification pattern (`/go`-style) framing | Canary task suite Phase 1 trigger via conditional hooks; replay harness Monitor tool use named; Boris Cherny `/go` pattern cross-referenced for author-lane verification | §5-H Work + Phase 1 Readiness + Phase 1 Validation updated; Q3 post-hoc-scenario timing clarification preserved; kill row §11-H retains "selected post-hoc" adversarial discipline | none | **ADOPTED-CLEAN** |

**Summary:** 4/8 primitives (A, C, E, F, H) ADOPTED-CLEAN on integration.
4/8 primitives (B, D, G) ADOPTED-WITH-GAP, with gaps routing to the new
G6–G13 findings. Gaps are all sub-plan-level or draft-editorial; none
challenge the integration direction. Primitive G absorbed the largest
scope reshape and carries the highest fraction of the gap surface —
expected, because G owns the native-migration corridor.

### 1.3 New Sections Integration Check

| New element | Location | Integration quality | Disposition |
|---|---|---|---|
| §4.2 9th audit item "Native Claude Code adoption state" | §4.2 bullets | Adds portability-signal input to target-repo audits; "a repo already on native has a much shorter port path than one still on bespoke synthesis" is the explicit portability cost modifier; cleanly parallels the other 8 items | **ADOPTED-CLEAN** |
| §10.9 Extensibility patterns | New §10.9 with 6 patterns (adapter / native-first / hook taxonomy / skill family / plan template / per-surface owner) | Each pattern tied to at least one enforcement surface (lint script / ADR / README / skill); "Enforcement surface" closing paragraph makes explicit "No pattern is aspirational-only; each has at least one mechanization path" | **ADOPTED-WITH-GAP → G11** (missing reversibility/rollback pattern; missing observability-by-default pattern) |
| §15.3 new tag `native-substrate-signal` | §15.3 meta-findings file §5.3 | Ledger entry class for changelog-review-skill output; wired through §15.4 digest and §5-D integration bullet | **ADOPTED-CLEAN** |
| §15.2 5th prompt | §15.2 schema | See G4 row above; symmetric to §11 trigger; digest + Phase 2 read-surface updated | **ADOPTED-CLEAN** |
| §13 SC #19 (changelog scan produces signal) | §13 | Ties `/review-claude-changelog` kill criterion to outcome; ≥1 `native-substrate-signal` ledger entry over proving run | **ADOPTED-CLEAN** |
| §13 SC #20 (≥1 native-substrate adoption lands) | §13 | Names three concrete candidates (ops/worktrees.py → WorktreeCreate/Remove; polling loops in ops/monitor.py → Monitor tool; heartbeat classifier → TeammateIdle); outcome-measurable | **ADOPTED-CLEAN** |
| §14 Open Items ADRs 002–006 + `external_signal_sources.md` | §14 items #11–#17 | ADR chain: 001 (Platform-11/13 + scorecard floor), 002 (review-cycle-as-evidence per analyst-c Q4), 003 (token-economy native vs. bespoke), 004 (hook migration boundary), 005 (`/autofix-pr` evaluation), 006 (Auto mode codification); each tied to a primitive owner | **ADOPTED-CLEAN** |
| Companion `claude_code_changelog_implications.md` | new file 188 lines | Tier inventory (S/A/B/C); plan-tier vs. system-rework-tier promotion table; per-system rework headlines; changelog review skill spec; external-signal sources seed; refresh history table | **ADOPTED-CLEAN** |
| Companion `0_hardening/sub/rework_spec.md` | new file 200 lines | Per-surface dispositions catalog; highest-leverage priority sequence §2; ops-package catalog §3; scripts §4; hooks §5; skills §6; plans cleanup §7; worktrees filesystem §8; Phase 2+ repo-structure note §9 | **ADOPTED-WITH-GAP → G6, G7, G9, G12, G13** (coverage holes enumerated below) |

### 1.4 Track 1 Summary

5/5 analyst-c G-findings resolved cleanly. Q3 resolved cleanly. Operator
clock-time directive applied consistently across §3, §4.1, §4.4 step 5,
§11 preamble, §13 SC #18 removal. Tier S × system-rework integration
lands cleanly for Primitives A, C, E, F, H and with identified gaps for
B, D, G (all routing to new findings G6–G13, none challenging direction).
§10.9, §15.2 5th prompt, §15.3 new tag, SC #19/#20, ADRs 002–006, and
both companion artifacts substantively land. No prior fix reversed; no
fixed constraint violated; no scope silently expanded.

---

## 2. Track 2 — Plan/Sub-plan vs. Analyst's View

Track 2 is broader: what does the plan/sub-plan address that doesn't
need addressing now? What does it *not* address that should be in scope?
What's preserved that should be cut? What's cut that should be preserved?
Does `rework_spec.md` cover the existing system completely? Does §10.9
capture the durable patterns? Does the changelog review skill target
the right sources?

### 2.1 Plan-vs-Actual Gap Table

| Gap | Plan/sub-plan position | Analyst position | Severity | Proposed action |
|---|---|---|---|---|
| **Ops-module coverage in `rework_spec.md`** | §3 catalog enumerates 18 ops modules | Actual `src/bid_euchre/ops/` top level has **42 modules**; ~21 uncatalogued (see G6 for enumeration) | medium | Extend §3 catalog in sub-plan before Phase 0 kickoff |
| **Hook-file coverage in `rework_spec.md`** | §5 catalog has ~10 hook-category rows | `.claude/hooks/` has **34 concrete hook files** (.sh + .py, excluding `lib/`); ~22 are folded under generic category rows without concrete targeting | low-medium | Convert §5 to one-row-per-hook or at minimum enumerate the specific file names under each category |
| **`.claude/agents/` directory** | Not mentioned in `rework_spec.md`; `.draft7.md` B.9 adds `.claude/system_prompts/<lane>.md` without reconciling with existing `.claude/agents/<lane>.md` | **23 agent files already exist** under `.claude/agents/` (19 steward lanes + 4 specialist reviewers + README); these are the current lane prompts loaded by Claude Code's Agent tool; B.9's new `.claude/system_prompts/` relationship is ambiguous (replacement? supplement? both loaded?) | medium | Add `.claude/agents/` catalog row to `rework_spec.md`; §5-B B.9 row clarifies: either (a) `.claude/system_prompts/` *replaces* `.claude/agents/*` bodies, or (b) `--system-prompt-file` and agent-file are both loaded in specific order, or (c) agent-file stays, system_prompts is orthogonal per-lane sparse override — one of the three, but not silent |
| **`ops/worktrees.py` registry state preservation** | `rework_spec.md` §3 row says "trim hard ~80%" via WorktreeCreate/Remove hooks + declarative isolation | File is **1133 LOC** with a durable registry under `.claude/runtime/worktree_registry/` and per-worktree reconciliation / orphan detection / protected-list enforcement; native hooks cover lifecycle events but the registry-state semantics and the `PROTECTED_WORKTREE_NAMES` enforcement are steward-specific and must survive the migration | medium | `rework_spec.md` row extended with explicit "registry state preserved or migrated to declarative form; PROTECTED list remains enforced on the adapter shim side"; migration ADR (filed when sub-sub-plan opens) documents the data-preservation contract |
| **`ops/token_economy.py` size reality** | `rework_spec.md` §3 + governing-plan §5-F / §5-G names "22 hard-blocks still bespoke" and target "zero hard-blocks" | File is **3103 LOC** — the largest single module in the ops package; the 22 hard-blocks are a small portability axis but the module is still the rigor center of the token-economy story; native `/usage` / `/cost` adoption is supplemental telemetry, not a replacement | low-medium | §5-F Work bullet clarifies: native `/usage` / `/cost` are **telemetry inputs and comparison feeds**, not a bespoke-replacement path; the 22 hard-blocks close in parallel but the module's bulk remains bespoke and steward-specific; `rework_spec.md` §3 row amended from "Modify substrate" to "Modify substrate; bespoke core preserved" to prevent the "native will replace this" implicit over-trim |
| **Plan references `MEMORY.md` and `knowledge/` as if they exist** | Governing plan and `rework_spec.md` refer to `MEMORY.md` (repo-local) and `knowledge/` (new KB skeleton) throughout | **Neither `MEMORY.md` nor `knowledge/` exists in the repo root currently.** `MEMORY.md` exists only at user scope (`~/.claude/projects/...`); `knowledge/` is a Phase 0 Primitive C deliverable that has not yet been created. This is expected for a pre-Phase-0 plan but worth flagging: the "shared project memory across worktrees" (Tier S) adoption depends on the substrate decision whether `MEMORY.md` lives repo-local (gitignored or committed) or user-scope | low | Primitive C Phase 0 Readiness adds an explicit bullet: "Substrate decision made — `MEMORY.md` lives repo-local (gitignored) vs. user-scope, and this decision is recorded in ADR 001 or a new ADR." Removes ambiguity in shared-memory semantics |
| **Browser-game-expansion plan reconciliation** | Governing plan §6.1 names "GBT retrain informed by human-gameplay data captured through the browser-game hosting infrastructure" as primary proving-run candidate | The **`plans/browser_game_expansion/` governing plan is ACTIVE** (per MEMORY.md status line); its shape determines the data-sufficiency check outcomes; draft 7 does not cross-reference the expansion plan's sequencing / data accretion expectations. Risk: Phase 1 data-sufficiency check (§6.1) fails silently if browser-game-expansion work lags or changes shape | low-medium | §6.1 adds a sentence: "Coordinate with `plans/browser_game_expansion/governing_plan.md` sequencing; the data-sufficiency thresholds specified in the first strategy-training sub-plan (§14 Open Item #9) must be compatible with the expansion plan's data-accretion timeline" |
| **Plans-directory fragmentation scale** | `rework_spec.md` §7 names `plans/agent_ops/5_*` subtrees for retirement + "session plans with ABANDONED/SUPERSEDED outcomes sweep and archive" | **264 session-plan files** exist in `plans/sessions/`; an "archive and sweep" is a substantial discovery task, not a line-item. Also `plans/` top-level has `future_research_directions.md`, `AGENTS.md`, `post_pr5_follow_on_roadmap.md` alongside governing-plan subdirectories; the scope of "plan fragmentation cleanup" is larger than §7 implies | low | `rework_spec.md` §7 adds cardinality note (~264 session plans + 12 top-level entries); splits the "sweep and archive" into a dedicated sub-sub-plan under Primitive G rather than treating as a line-item |
| **`scripts/internal/` coverage in `rework_spec.md`** | §4 enumerates ~10 scripts (including 4 planned-new) | `scripts/internal/` has ~70 .py/.sh files; at least ~6 are core-platform (not arc_d_v2 / experiment-specific) not named: `plan_review_driver.py`, `claude_fix_adapter.py`, `codex_plan_review_adapter.py`, `compact_session_context.py`, `deterministic_prechecks.py`, `review_common.py`, `review_state.py` | low | §4 catalog extended with platform-scripts subset or explicit "other scripts (~60) are experiment-specific (arc_d_v2, hosted-play, etc.) and out of scope for platform rework" note |
| **`.claude/rules/` catalog not in `rework_spec.md`** | §7 mentions "audit" of `.claude/rules/` overlap with `CLAUDE.md` | `.claude/rules/` has 7 top-level rule files + `deferred/` subdirectory with more; `80_permission_model.md` is the auto-mode rule referenced by ADR 006; `75_worktree_protection.md` is referenced by the worktrees migration; the rules directory is execution infrastructure for agent behavior, not optional | low | `rework_spec.md` §7 adds a rules-catalog row; each rule file named with disposition (keep / consolidate-with / deprecate) per Primitive C's ADR discipline |
| **External-signal source list over/under-scoped** | Governing plan §5-D + `claude_code_changelog_implications.md` §5/§6 lists: Boris Cherny threads, davidad commentary, Anthropic team posts, community digests; plan sources include wayback / archive for earlier weekly pages | **Over-scoped:** wayback / archive crawls add fragility and latency for marginal signal; most weekly pages are accessible directly from the current changelog index. **Under-scoped:** Claude Code GitHub release notes (`https://github.com/anthropics/claude-code/releases`), `docs.anthropic.com` blog posts on Claude Code, operator-curated X/Twitter lists (not individual threads) | low | §5-D trim wayback crawl to "best-effort; not a readiness blocker"; add GitHub release notes + docs.anthropic.com blog index + optional operator X-list to the external-signal sources seed; see G8 |
| **§10.9 missing extensibility patterns** | 6 patterns codified: adapter / native-first / hook taxonomy / skill family / plan template / per-surface owner | Two additional patterns plausibly belong: (7) **Reversibility-as-default** (goal #13 says every platform change is reversible; `rework_spec.md` row effort estimates don't include rollback cost; §10.9 does not codify the discipline); (8) **Observable-by-default** (every durable change emits into the trace corpus; §10.9 does not codify despite this being the substrate Primitive A depends on) | low-medium | §10.9 adds Pattern 7 (Reversibility-as-default) and Pattern 8 (Observable-by-default); each tied to enforcement surface; see G11 |
| **Skill consolidation math** | `rework_spec.md` §6 lists 10 families + summary "Net target: 30+ skill reduction ~8; new additions ~6 (net flat)" | Actual `.claude/skills/` has **38 skill directories** (not 30+); missing from §6 families: `chunking-prs`, `executing-plans`, `fixing-bugs`, `merging-pr-stacks`, `shipping-changes`, `summarizing-sessions` (6 skills) | low | §6 extended with "Recent additions" family or absorbed into Specific Workflows; total count reconciled with 38 actual skills |
| **Agent-first discipline for the plan itself** | §10.8 enumerates 7 agent-first conventions; §13 SC #17 makes lint-clean a success criterion | `plans/steward_platform/governing_plan.draft7.md` itself at **1265 lines**, companion `rework_spec.md` at 200 lines, companion `claude_code_changelog_implications.md` at 188 lines — are these agent-loadable with minimal preamble? The plan has no "load-this-first" pointer; an agent landing at `plans/steward_platform/` from repo root navigates 7 drafts, 3 review files, 3 companion artifacts, 1 handoff, and 1 target `governing_plan.md` file (none currently present). Risk: agent context cost of loading into the plan is high despite goal-#16 aspirations | low | Primitive C Phase 0 Readiness adds: "`plans/steward_platform/README.md` committed naming the load order: governing_plan.md → claude_code_changelog_implications.md → rework_spec.md → sub-plan set. Prevents agents from loading 7 drafts by accident." |
| **Phase 0 duration-to-scope reality check** | Governing plan §5 Phase 0 covers Primitives A–G (7 primitives) + step 0 baseline + §4.2 target-repo audits (2-3 days each = 4-6 analyst-days) | The Phase 0 scope is substantial: event schema + Phoenix deployment; prompt-policy registry + 8 lane system prompts + tool risk registry + 4 skill-promotion loops; 6+ KB artifact classes + 6 planning templates + 3 scripts + scorecard + lint + digest; archivist + changelog skill; messaging bus finalization + 4 event-class triage wiring + hook migration ADR; token-economy rework + `/usage` comparison + baseline re-capture; worktree native migration + Setup hook + system_prompts + heartbeat retirement + skills consolidation + permission allowlist work. Clock-time intent-only means Phase 0 could stretch arbitrarily without a tripwire | low-medium | Governing plan §5 preamble or §14 Open Item added: Phase 0 kickoff ADR 001 (or new ADR) records a provisional Phase 0 time-budget as a *diagnostic* (not a mechanism); if the diagnostic runs significantly beyond it (e.g., 2×), Phase 0 work is re-scoped to a shorter critical path with explicit deferrals rather than accreting indefinitely. Preserves operator directive (clock-time is intent) while preventing Phase 0 sprawl |

### 2.2 What the plan/sub-plan addresses that doesn't need addressing now?

One clear candidate:

- **§14 Open Item #12 — ADR 002 review-cycle-as-evidence.** Analyst-c's
  Q4 surfaced this as a filing-timing question; the draft 7 Open Item
  lists it alongside ADR 001 at Phase 0 kickoff. Filing it at kickoff
  treats the review-cycle pattern as evidentially durable — but the
  evidence base is self-referential (the draft-1-through-draft-7
  lineage). It's a good retrospective ADR candidate but its
  decision-load on Phase 0 execution is essentially zero. Defer to end
  of Phase 0 (when the plan has demonstrably run, not just been drafted)
  rather than filing at kickoff. Low-stakes re-sequencing; no formal
  finding.

Two weaker candidates that stay but shouldn't bulk up Phase 0:

- **`/autofix-pr` evaluation ADR 005.** Listed as evaluate-only; the
  overlap with `scripts/internal/review_driver.py` is real but the
  current review pipeline works. ADR 005 filing at Phase 0 close is
  appropriate; no reason to rush.
- **Remote sessions for away-mode adoption.** Tier S in the changelog
  implications doc; Primitive G Work bullet adopts. But the existing
  away-mode + Telegram + push-notification path is proven (messages
  134-136 session 2026-04-01 per MEMORY.md). Native adoption is
  optional; the existing substrate works. Appropriate to ADR
  evaluation; inappropriate to treat as Phase 0 must-ship.

None of these are findings — they're framing notes that appear to be
already handled by Phase 0 Readiness being scoped to *existence and
wiring*, not *replacement-in-full*.

### 2.3 What the plan/sub-plan is NOT addressing that should be in scope?

Three items worth considering:

- **Lane archetype consolidation.** The governing plan §10.3 says
  "Reduced from current 19-lane fleet" but does not name the target. The
  actual fleet today: orchestrator + ops + review (3 control-plane) +
  4 author + 4 brws-author + 4 analyst + 4 flex (16 specialist) = 19
  lanes. B.9 introduces `.claude/system_prompts/<lane>.md` for **"~8
  lane archetypes"** — that's the consolidation target, but it's only
  named once and without a readiness criterion. The mapping from 19
  current lanes → 8 archetypes isn't specified. This is sub-plan work,
  but the archetype count should be a Primitive G readiness criterion
  or §10.3 should state the target count. See G13.
- **`.claude/hooks/README.md` as authoritative source.** Governing plan
  §5-E Work says "Migrate existing hook set from unconditional to
  conditional hooks where safe; document ordering and scope per hook in
  `.claude/hooks/README.md`." Existing `.claude/hooks/README.md` exists
  but its current authority vs. actual hook behavior is unverified;
  for the hook-taxonomy pattern (§10.9 Pattern 3) to work, the README
  must be the authoritative reference. Add Primitive E Phase 0
  Readiness: "`.claude/hooks/README.md` is authoritative; all hooks
  listed with trigger/scope/category; lint script validates README ↔
  hook-set consistency."
- **Post-merge review coupling.** `.claude/CLAUDE.md` documents a
  post-merge review hook that runs an Explore agent on every merged
  PR. This is existing platform behavior; it is substrate for Phase 1
  validation (every PR merged during proving run gets reviewed), but
  the governing plan does not mention it. If it's assumed-working, say
  so; if it's rework candidate (maybe it overlaps with `/autofix-pr`
  or ADR 005), catalog it. Low-stakes; could be a note in
  `rework_spec.md`.

### 2.4 What in the existing code is being preserved that should be cut?

The `rework_spec.md` dispositions (keep / modify / consolidate / trim /
delete) already express this. Two items stand out for tightening:

- **`ops/dashboard.py` heartbeat classifier (#2743 just shipped).** The
  "ironic retirement" acknowledgement in §5-G and `rework_spec.md` is
  honest; the right call is retire when TeammateIdle lands. Preserving
  it while TeammateIdle substrate matures is fine. No change.
- **`ops/telegram_filter.py` + `ops/telegram_push.py` + `ops/remote_ack.py`.**
  These three modules implement the proven Telegram round-trip. Native
  "remote-control / remote sessions" adoption is a Phase 0 candidate
  but the existing path works and has operational history. Risk of
  cutting prematurely is operator-surface regression. Keep these
  modules through Phase 0; evaluate native cutover during Phase 1
  validation as a native-substrate-adoption candidate counted toward
  SC #20. `rework_spec.md` §3 has `telegram_filter.py` as "Evaluate for
  absorption"; the other two are uncatalogued (G6). Evaluation should
  not force cutover.

### 2.5 What in the existing code is being cut that should be preserved?

Two items:

- **`rework_spec.md` §6 monitoring-family consolidation (6→2).** The 6
  skills are `monitor`, `check-in`, `fleet-check`, `inbox-poll`,
  `lane-status`, `capture-pane`. They serve genuinely different
  consumers: `check-in` is orchestrator situational-awareness,
  `fleet-check` is the durable ops-cron cycle, `inbox-poll` is any-lane
  lightweight, `lane-status` is the correctness gate for
  dispatch/nudge decisions, `capture-pane` is the tmux-content inspect
  with support for batch/stuck-only modes, `monitor` is the full ops
  monitoring cycle. Collapsing 6→2 via Monitor + TeammateIdle risks
  losing specific operator-UX affordances. Preserve the consumer
  differentiation; reduce implementation duplication (multiple scripts
  calling the same underlying monitor functions) rather than surface
  count. See G9.
- **`ops/events.py` + `ops/audit_trail.py` + `ops/snapshots.py` trio.**
  `rework_spec.md` §3 proposes "Consolidate candidate" for
  `snapshots.py` with `audit_trail.py` and "Modify; expand
  normalization" for `events.py`. These three together carry the
  Primitive A schema-normalization work; native lifecycle hooks feed
  into them. Consolidating snapshots into audit_trail before the schema
  finalization lands (Phase 0 Primitive A Readiness) risks the
  native-hook absorption touching an in-flight structure. Preserve
  all three until Primitive A schema `v1` freezes; consolidate in a
  post-Primitive-A sub-sub-plan.

### 2.6 Does `rework_spec.md` cover the existing system completely?

**No — coverage gaps enumerated below as G6.** The catalog is
substantive but incomplete:

- **Ops package:** 18 enumerated; 42 total; ~21 uncatalogued
  (alert_push, away_mode, ci, compaction, context_safety, fs_boundary,
  idle_detector, lane_heartbeat, learning, queue_priority, recovery,
  remote_ack, repairs, retries, review_queue, reviews, scope, status,
  supervisor, telegram_push, watchdogs).
- **Hooks:** ~10 categories; 34 concrete hook files; ~22 not named
  individually. Notable uncategorized: `alert-inject.{py,sh}`,
  `attention-broker-autostart.sh`, `compact-context.sh`,
  `fleet-check-autostart.sh`, `inbound-channel-audit.{py,sh}`,
  `inbox-completion-inject.{py,sh}`, `post-bash-dispatch.sh`,
  `post-merge-notify.sh`, `post-monitor-push-relay.sh`,
  `post-plan-review.sh`, `post-push-ci-check.sh`, `post-task-event.sh`,
  `post-telegram-audit.sh`, `post-tool-daemon-notify.sh`,
  `post-write-check.sh`, `pre-worktree-cleanup.sh`, `rule-loader.sh`,
  `scope-drift-guard.sh`, `session-sync-worktree.sh`,
  `urgent-state-guard.py`, `worktree-guard.sh`, `worktree-reminder.sh`.
- **Agents:** 0 enumerated; 23 files (19 lanes + 4 specialists + README).
  Silent gap because B.9 references `.claude/system_prompts/<lane>.md`
  without reconciling with existing `.claude/agents/<lane>.md` contents.
- **Rules:** 0 enumerated in detail; 7 top-level + `deferred/`
  subdirectory. §7 "audit" mention is insufficient for Primitive G
  scope.
- **Scripts:** 10 enumerated (including 4 planned-new); ~70 total in
  `scripts/internal/`; ~6 platform-scripts uncatalogued (see G6).
- **Templates:** `plans/_templates/` already exists with 4 template
  files (checkpoints, governing_plan, sub_plan, sub_plan_registry) —
  partial substrate for Primitive C. Not mentioned in `rework_spec.md`.

### 2.7 Does §10.9 capture durable extensibility patterns?

**Mostly yes; two patterns missing.** The 6 codified patterns are:
adapter contract (Pattern 1); native-substrate-first (Pattern 2); hook
taxonomy (Pattern 3); skill family discipline (Pattern 4); plan template
enforcement (Pattern 5); per-surface owner (Pattern 6). All six are
tied to enforcement surfaces per §10.9's closing paragraph.

Missing:

- **Pattern 7 — Reversibility-as-default.** Every durable platform
  change has a rollback path documented at change-time, not
  post-hoc. Goal #13 says reversibility is a property of every platform
  change; SC #13 says rollback paths are validated for every
  reversible change introduced in Phase 0 (Primitive G) and Phase 1
  (Primitive H). But §10.9 does not codify rollback discipline as a
  cross-cutting pattern. Without pattern-level codification, the
  reversibility discipline lives only in §13 + §11 kill criteria —
  neither of which is a "how do I build something reversibly?" guide
  for author lanes.
- **Pattern 8 — Observable-by-default.** Every durable change emits
  into the unified event schema (Primitive A); every platform
  side-effect carries a trace_id or incident_fingerprint. This is
  already the substrate — but §10.9 does not codify it. Without
  pattern-level codification, a new skill or hook could ship without
  trace emission and fail silently. See G11.

### 2.8 Does the changelog review skill target the right external-signal sources?

**Mostly yes; see 2.1 table row for over/under-scoping details.**

Over-scoped: wayback / archive crawls for earlier weekly pages. The
current `https://code.claude.com/docs/en/changelog` index is
comprehensive enough; wayback adds fragility and operational complexity
without proportionate signal.

Under-scoped:

- **Claude Code GitHub release notes** (`https://github.com/anthropics/claude-code/releases`).
  Each release has structured feature annotations; complementary to the
  docs changelog.
- **docs.anthropic.com blog** (if Anthropic publishes architecture /
  model-behavior posts relevant to Claude Code). Tier S inventory
  already cites davidad-style external threads; the blog is a more
  durable source.
- **Operator X/Twitter lists.** Tier S inventory cites specific threads
  (Boris Cherny, davidad); an operator-curated *list* URL (vs.
  individual threads) scales better as the external-signal source
  evolves.

The scrape-every-3-days cadence is probably right; fewer-than-twice-a-week
misses releases; more-than-thrice-a-week over-indexes on minor updates.

### 2.9 Strategic Gaps (plan-level assumptions vs. repo reality)

Three strategic-layer observations, surfaced not as findings but as
inputs for the operator's own framing:

- **Proving-run candidate fragility.** The primary proving-run candidate
  (GBT retrain via browser-game data) depends on an ACTIVE separate
  governing plan (`plans/browser_game_expansion/`). Draft 7 §6.1
  names the data-sufficiency check pivot-to-methodology-overhaul as
  the fallback, which is sound. But the "default primary" framing
  understates how tightly the proving run is coupled to expansion-plan
  progress. Worth a §6.1 cross-reference (see Track 2 gap table row).
- **Platform-vs-product confusion risk.** `src/bid_euchre/ops/`
  conflates Bid-Euchre game code with steward platform code. The
  rework_spec §9 Phase 2+ note names this as a post-Phase-2
  consideration; it's correctly deferred. But the coverage gap in
  Track 2.6 is partly *because* the package is this large and partly
  *because* platform-vs-product boundary is not yet drawn. Phase 0
  accepts the boundary blur; Phase 2 will inherit it. Acknowledge,
  don't resolve; §10.7 already defers the meta-layer shape.
- **Agent-first as dogfood risk.** Goal #16 and §10.8 + §10.9 codify
  agent-first as primary audience. The plan itself is ~1265 lines; the
  full draft-lineage is 7 files totaling ~8000+ lines. An agent loading
  into `plans/steward_platform/` pays a meaningful context cost. The
  "load-order README" in Track 2.1 gap table row addresses the worst
  of this. The deeper observation: the plan's agent-first discipline
  is self-consistent (this review itself demonstrates it), but
  `plans/_templates/` does not yet carry the goal-#16 conventions.
  Primitive C's template work must propagate conventions *into* the
  templates before any new sub-plan under Primitive A/B/D/E/F/G/H
  inherits them. Cascade order matters.

---

## 3. New Gap Findings (G6–G13)

Each finding has a stable ID; severity (high / medium / low / low-medium
/ low-editorial); concrete proposed fix. IDs continue analyst-c's G1–G5
numbering to maintain grep-clean finding history across drafts.

### G6 — `rework_spec.md` ops-module catalog has 21 uncovered modules

**Severity:** medium.

**Evidence:**
- `plans/steward_platform/0_hardening/sub/rework_spec.md` §3 enumerates
  18 ops modules.
- Actual `src/bid_euchre/ops/` top level has **42 modules**; 21 not
  catalogued: `alert_push.py`, `away_mode.py`, `ci.py`, `compaction.py`,
  `context_safety.py`, `fs_boundary.py`, `idle_detector.py`,
  `lane_heartbeat.py`, `learning.py`, `queue_priority.py`,
  `recovery.py`, `remote_ack.py`, `repairs.py`, `retries.py`,
  `review_queue.py`, `reviews.py`, `scope.py`, `status.py`,
  `supervisor.py`, `telegram_push.py`, `watchdogs.py`.
- Primitive G Phase 0 Readiness says "Skills consolidation pass
  executed per `rework_spec.md` dispositions." If the catalog is
  incomplete, the execution instruction is incomplete.

**Why this matters:** Author lanes executing Phase 0 under Primitive G
read `rework_spec.md` as the canonical catalog. Uncatalogued modules
land in an undefined-behavior zone: keep? modify? consolidate? trim?
delete? Without dispositions, author lanes either skip them (scope
creep risk if they actually need rework) or re-derive dispositions
(duplicate analyst work). F6 precedent says the sub-plan should own
the catalog.

**Proposed fix:**
1. Extend `plans/steward_platform/0_hardening/sub/rework_spec.md` §3
   to cover all 42 ops modules. Dispositions likely mix of
   "Keep (no trigger)" for most (alert_push, away_mode, ci,
   compaction, context_safety, fs_boundary, review_queue, reviews,
   retries, status, supervisor, watchdogs — all steward-specific
   orchestration with no native analog) and a few "Modify substrate"
   or "Consolidate candidate" as evaluated.
2. Default disposition for a module with no native analog and no
   consolidation partner: "Keep; review at Phase 1 close for native
   analog evolution" (defer without treating as open work).
3. Section re-counted; priority-sequence §2 updated if any newly-named
   module bumps into the top 12.

**Cost to fix:** ~40 lines in `rework_spec.md` §3. One analyst pass.
Can land in the same tightening pass as G7–G13.

### G7 — `rework_spec.md` hook catalog lists categories without individual files; `ops/worktrees.py` registry-state preservation not named

**Severity:** low-medium (split finding — two related issues).

**Evidence:**
- `rework_spec.md` §5 catalog has 10 category rows covering `.claude/hooks/`.
- Actual `.claude/hooks/` has 34 concrete hook files (.sh + .py,
  excluding `lib/`). 22 uncategorized-by-name (see Track 2.6 for list).
- `rework_spec.md` §3 row for `worktrees.py` says "Trim hard (~80%)"
  via WorktreeCreate/Remove hooks + declarative isolation. Module is
  1133 LOC; `PROTECTED_WORKTREE_NAMES` frozenset and durable registry
  under `.claude/runtime/worktree_registry/` are steward-specific
  semantics not covered by native hooks alone.

**Why this matters:** Hook-migration ADR 004 (§14 Open Item #14) files
the boundary "which custom hooks migrate to native lifecycle
subscriptions, which migrate to conditional-hook scope, which migrate
to HTTP hooks, and which stay bespoke." Without an individual-file
catalog, ADR 004 either has to do its own discovery (expensive) or
accept fuzzy boundaries. For `worktrees.py` registry: the migration
target "~80% LOC reduction" implies 80% of registry-semantic code goes
away, but the registry is steward-specific state that governs
protection enforcement. Migration risk is real.

**Proposed fix:**
1. Convert `rework_spec.md` §5 from category-granular to file-granular
   or add "hooks within category" sub-bullets enumerating the 22
   uncategorized files.
2. Extend the `worktrees.py` row in §3 with explicit registry-state
   and PROTECTED-list-preservation notes: "native WorktreeCreate/Remove
   hooks cover lifecycle; adapter shim preserves `PROTECTED_WORKTREE_NAMES`
   enforcement and durable registry semantics from
   `.claude/runtime/worktree_registry/`. Migration ADR (filed when
   sub-sub-plan opens) documents the data-preservation contract."

**Cost to fix:** ~25 lines in `rework_spec.md` §5 + ~3 lines in §3
worktrees row.

### G8 — Changelog review skill source list is over-scoped on wayback, under-scoped on GitHub releases + blog

**Severity:** low.

**Evidence:**
- `plans/steward_platform/governing_plan.draft7.md` §5-D lists sources:
  `https://code.claude.com/docs/en/changelog`,
  `https://code.claude.com/docs/en/whats-new`, weekly pages,
  wayback / archive best-effort, operator-curated URLs in
  `knowledge/external_signal_sources.md`.
- `claude_code_changelog_implications.md` §5 + §6 match.
- Current changelog index covers recent releases comprehensively; archive
  / wayback crawl adds fragility for earlier weekly pages.
- GitHub release notes at `https://github.com/anthropics/claude-code/releases`
  are a structured parallel source not listed.
- `docs.anthropic.com` blog / Anthropic engineering posts on Claude Code
  are not listed.

**Why this matters:** The skill runs 2-3×/week; wayback / archive calls
add operational fragility and latency without proportionate signal.
GitHub release notes structure features clearly (version tags, release
bodies, contributors) — easier to parse than scraped weekly pages.
Under-scoping the blog misses architecture-level posts that drive Tier
S decisions (exactly the kind of operator-curated signal the plan
wants to absorb).

**Proposed fix:**
1. Trim wayback / archive crawl to "best-effort; not a readiness
   blocker" (already true in §5-D but worth sharpening).
2. Add `https://github.com/anthropics/claude-code/releases` to the
   source list (governing plan §5-D and changelog-implications §5).
3. Add `docs.anthropic.com` blog index URL (or a categorized filter
   URL) to `knowledge/external_signal_sources.md` seed.
4. Replace "individual operator-curated threads" with "operator X/Twitter
   list URLs" where the list is a stable reference that scales as the
   thread surface evolves.

**Cost to fix:** ~5 lines in §5-D; ~3 lines in companion §5; ~3 lines
in §6 seed.

### G9 — Skill consolidation math off by 8; monitoring-family consolidation risks operator-UX regression

**Severity:** low.

**Evidence:**
- `rework_spec.md` §6 header says "30+ skills"; summary says "Total
  skill-count reduction ~8 from existing 30+; new additions per draft
  6/7 add ~6 (net flat)."
- Actual `.claude/skills/` has **38 skill directories** (listed above
  in Track 2.6). §6's family buckets miss 6 skills: `chunking-prs`,
  `executing-plans`, `fixing-bugs`, `merging-pr-stacks`,
  `shipping-changes`, `summarizing-sessions`.
- §6 monitoring family proposes 6→2 collapse: `monitor`, `check-in`,
  `fleet-check`, `inbox-poll`, `lane-status`, `capture-pane` → keep
  `fleet-check` (aggregator) + `lane-status` (one-off). Each of the 6
  has a different consumer / usage pattern per the skills catalog at
  dispatch (see `.claude/skills/lane-status/SKILL.md`,
  `.claude/skills/capture-pane/SKILL.md`, etc.).

**Why this matters:** The "30+" count understates by 8 — minor
editorial. More importantly, the monitoring-family 6→2 collapse targets
*surface count* rather than *implementation duplication*. The 6 skills
are consumer-differentiated (orchestrator situational-awareness,
durable ops-cron cycle, any-lane lightweight poll, dispatch correctness
gate, batch/stuck pane inspection, full ops monitoring cycle). A
collapse risks losing affordances; what the rework actually needs is
to reduce *behind-the-scenes duplication* in the implementations
calling shared ops-module functions.

**Proposed fix:**
1. Reconcile §6 count: "38 skills" not "30+"; add 6 missing skills to
   appropriate family buckets.
2. Reframe monitoring-family disposition from "collapse 6→2" to
   "evaluate implementation-duplication reduction; preserve
   consumer-differentiated surfaces where they each have distinct
   consumers." Target becomes "deduplicate the underlying helpers,
   keep the skill surface."
3. Apply same reframing-check to playtest-family 4→2 collapse:
   `playtesting` (HTTP-only), `playtest-hybrid` (HTTP + Playwright
   snapshots), `playtest-strategic` (intelligent bidding), and
   `playtest-playwright` (visual-focused). Computer use may
   consolidate 2 of the 4 but consumer-differentiation argues against
   forcing 4→1.

**Cost to fix:** ~10 lines in `rework_spec.md` §6 (count + family
adds + monitoring/playtest reframing).

### G10 — B.9 `.claude/system_prompts/<lane>.md` vs. existing `.claude/agents/<lane>.md` relationship unspecified

**Severity:** medium.

**Evidence:**
- `plans/steward_platform/governing_plan.draft7.md` §5-B sub-deliverable
  B.9 introduces `.claude/system_prompts/<lane>.md` files for "~8 lane
  archetypes" passed to each lane launch via `--system-prompt-file`.
- Actual `.claude/agents/` directory has 23 files including
  `steward-orchestrator.md` (295 lines), `steward-author-a.md` (101
  lines), 3 more author lanes (b/c/d), 4 brws-author lanes, 4 flex
  lanes, analyst, ops, review, author-scratch, plus 4 specialist
  reviewer agents — all currently serving as per-lane prompts loaded
  by Claude Code's Agent tool.
- B.9 does not reconcile: does `--system-prompt-file` *replace* the
  `.claude/agents/<lane>.md` body? Is it *combined* with the agents
  file? Does it *override* specific sections?
- `rework_spec.md` catalog does not mention `.claude/agents/` at all.

**Why this matters:** B.9 is stated as a high-leverage low-cost win
("4.7+ behavior improvement"), but the implementation path is
ambiguous. If author lanes implement B.9 by writing sparse
`.claude/system_prompts/<lane>.md` files alongside the existing verbose
`.claude/agents/<lane>.md` files, the two prompts may conflict or
double-load — defeating the "sparse beats default" thesis. If B.9
implies retiring `.claude/agents/<lane>.md` bodies, that's a substantial
cutover the plan doesn't name. Primitive G Phase 0 Readiness includes
"`.claude/system_prompts/<lane>.md` files exist for ~8 lane archetypes;
sparse by default per the 'default system prompt degrades 4.7+' harness
assumption" — but the cutover relationship is silent.

**Proposed fix:**
1. §5-B B.9 row clarifies one of three paths:
   - (a) **Replacement:** `.claude/system_prompts/<lane>.md` supplants
     `.claude/agents/<lane>.md` body content; agents-file carries only
     frontmatter / metadata. Cutover is explicit.
   - (b) **Supplement:** `.claude/system_prompts/<lane>.md` is a
     sparse override loaded *in addition to* `.claude/agents/<lane>.md`;
     loading order documented.
   - (c) **Orthogonal:** `.claude/system_prompts/<lane>.md` covers per-launch
     override (via `--system-prompt-file`), `.claude/agents/<lane>.md`
     covers Agent-tool-loaded subagent behavior; they describe different
     things and both persist.
2. Choice recorded in ADR 006 (Auto mode codification) or a new ADR
   before Phase 0 Primitive G work begins.
3. `rework_spec.md` §3 or §7 gains a `.claude/agents/` catalog row.

**Cost to fix:** ~8 lines in §5-B B.9 row; ~5 lines in `rework_spec.md`
adding agents-directory catalog; 1 ADR at Phase 0 kickoff.

### G11 — §10.9 missing reversibility + observable-by-default patterns

**Severity:** low-medium.

**Evidence:**
- `plans/steward_platform/governing_plan.draft7.md` §10.9 codifies 6
  patterns: adapter contract; native-substrate-first; hook taxonomy;
  skill family discipline; plan template enforcement; per-surface owner.
- §10.9 closing paragraph: "No pattern is aspirational-only; each has
  at least one mechanization path."
- Goal #13 (rollback/disable paths) + SC #13 (rollback validated for
  every reversible change) + §11 kill criteria + §15 dispositions
  assume reversibility discipline is cross-cutting — but §10.9 doesn't
  codify it.
- Primitive A + schema versioning + `${CLAUDE_SESSION_ID}` + trace
  corpus require observable-by-default discipline for every new
  skill/hook/script — but §10.9 doesn't codify it.

**Why this matters:** Patterns are enforcement infrastructure;
reversibility and observability are repeatedly invoked in plan text as
if codified, but the enforcement surface (lint script / ADR / README /
template) would need an explicit pattern to key off. Without
codification, a new skill or hook could ship without rollback path or
trace emission and pass the current lint rules.

**Proposed fix:** Add two patterns to §10.9:

**Pattern 7 — Reversibility-as-default.** Every durable platform change
(skill promotion, prompt-policy edit, dispatch-policy change, hook
migration, KB restructure) has a rollback path documented at
change-time, not post-hoc. The `plans/_templates/promotion_rollback.md`
(Primitive C) and PR-template rollback field enforce change-time
rollback-path documentation. `agent_readability_lint.py` optionally
flags durable-change PRs missing a rollback section.

**Pattern 8 — Observable-by-default.** Every durable change emits into
the unified event schema (Primitive A); every platform side-effect
carries a `trace_id` or `incident_fingerprint`. New skills / hooks /
scripts emit a `task_started` / `task_completed` equivalent where
applicable. `agent_readability_lint.py` optionally flags new skill /
hook / script files without schema-emission calls.

**Cost to fix:** ~15 lines in §10.9 + ~3 lines extending the lint-script
responsibility in §5-C.

### G12 — `plans/sessions/` has 264 files; "sweep and archive" line-item understates scope

**Severity:** low.

**Evidence:**
- `rework_spec.md` §7 line: "Session plans with ABANDONED/SUPERSEDED
  outcomes: Sweep and archive (move to `plans/sessions/_archive/`)".
- Actual `plans/sessions/` has 264 `.md` files; `_archive/`
  subdirectory exists but is empty.
- §7 treats this as a single-line disposition; the discovery work
  (which have ABANDONED/SUPERSEDED outcomes vs. open) is non-trivial.

**Why this matters:** "Sweep and archive" as a one-liner under-scopes
the discovery. An author lane executing Phase 0 Primitive G might spend
hours classifying 264 files without a clear outcome-tag parser. This is
sub-sub-plan territory, not a line-item.

**Proposed fix:**
1. `rework_spec.md` §7 row extended with cardinality note: "264 session
   plans; discovery task — each file's `## Outcome` section contains
   either COMPLETED / ABANDONED / SUPERSEDED status. Script
   `scripts/internal/sweep_session_plans.py` (~30 lines) enumerates,
   classifies, archives in one pass. Owner: Primitive G sub-sub-plan."
2. Script is a Primitive G deliverable rather than an inline operation.

**Cost to fix:** ~5 lines in `rework_spec.md` §7 + 1 new script in
Primitive G sub-sub-plan list.

### G13 — `.claude/agents/` absent from `rework_spec.md`; lane archetype count (8) vs. current 19 lanes not mapped

**Severity:** low-medium (closely related to G10).

**Evidence:**
- `rework_spec.md` has no section for `.claude/agents/`. Directory has
  23 files.
- Governing plan §10.3 says "Reduced from current 19-lane fleet" but
  no target count.
- §5-B B.9 says "~8 lane archetypes" for `.claude/system_prompts/`
  files.
- No mapping of 19 existing lane types → 8 archetypes.

**Why this matters:** Phase 0 Primitive G Readiness says
"`.claude/system_prompts/<lane>.md` files exist for ~8 lane archetypes"
— that's the operational target. But which 8? Is the orchestrator an
archetype? The specialist reviewers (architecture, correctness,
coverage, plan-reviewer) archetypes or subagents? Author-a/b/c/d
same archetype or different? Without the mapping, author lanes
executing B.9 either produce inconsistent system_prompts or ask
clarifying questions mid-Phase-0.

**Proposed fix:**
1. `rework_spec.md` adds new §3 sub-row or new §6b:
   "`.claude/agents/` directory (23 files): 19 lane files + 4 specialist
   reviewer agents + README. Disposition: consolidate to 8 archetypes
   per B.9; each archetype has both a `.claude/agents/<archetype>.md`
   (for Agent tool loading) and a `.claude/system_prompts/<archetype>.md`
   (for per-launch `--system-prompt-file` sparse override), or per G10
   resolution."
2. Mapping 19 → 8 published as first deliverable of Phase 0 Primitive G
   sub-sub-plan. Candidate mapping: (1) orchestrator (2) ops (3) review
   (4) analyst (5) author (6) brws-author (7) flex (8) scratch — with
   specialist reviewers as subagent archetypes not lane archetypes.
3. §10.3 lane-policy target count "~7-8 archetypes" added explicitly.

**Cost to fix:** ~15 lines in `rework_spec.md` (new agents catalog
section); ~2 lines in governing plan §10.3.

---

## 4. Promotion Recommendation

**PROMOTE-AFTER-FIXES.**

**Rationale:**

- **Track 1 clean.** 5/5 analyst-c G-findings ADOPTED-CLEAN; Q3
  ADOPTED-CLEAN; operator clock-time directive ADOPTED-CLEAN across 5
  plan sites. Tier S × system-rework integration lands substantively
  for 5/8 primitives (A, C, E, F, H) with 3/8 (B, D, G) routing to new
  G-findings that are tightening, not direction changes. §10.9, §15.2
  5th prompt, §15.3 new tag, SC #19/#20, ADRs 002–006, and both
  companion artifacts substantively land. No prior fix reversed; no
  fixed constraint violated; no scope silently expanded.
- **Track 2 productive.** Plan is well-framed against single-repo-proof
  → port → meta-layer ambition; 16 goals; agent-first; native-first.
  The biggest Track 2 concerns are sub-plan-level (rework_spec coverage
  holes) and one plan-level clarification (B.9 vs. `.claude/agents/`
  reconciliation). Strategic gaps are framing nudges, not structural
  challenges.
- **G6 is mandatory before Phase 0 kickoff.** Uncovered ops modules
  leave execution in undefined-behavior territory. Same F6/G1 fix
  shape applies symmetrically to sub-plan.
- **G7, G10, G11, G13 are strong tightenings.** Each resolves a
  concrete ambiguity that will cost an author lane an hour or more
  mid-Phase-0 if left. Low fix cost, high mid-execution cost saved.
- **G8, G9, G12 are editorial tightenings.** Nice-to-have; don't block.
- **Companion artifacts land in the same PR.** `rework_spec.md` updates
  (G6, G7, G9, G12, G13) are sub-plan-level and land as part of the
  governing-plan promotion.

**Concrete proposal:**

1. Tightening pass applies G6 (mandatory), G7/G10/G11/G13 (strong
   tightenings), G8/G9/G12 (editorial). Total cost ~120–150 lines
   across `draft7.md` + `rework_spec.md` + `claude_code_changelog_implications.md`.
2. Promote the result to `plans/steward_platform/governing_plan.md`
   *in the same commit as the tightening pass*. Drafts 1–7 archive as
   the review-lineage record.
3. File ADR 001 (Platform-11/13 dismissal evidence + agent-readability
   scorecard ≥7/10 floor + draft-7 promotion grade) at Phase 0 kickoff
   as the plan already specifies.
4. File ADR 006 (or a new ADR) resolving G10's `.claude/system_prompts/`
   vs. `.claude/agents/` relationship *before* Primitive G work begins.
5. No draft-8 narrow review cycle. Promotion is direct.

If the operator prefers a draft-8 narrow review, the cost is one more
cycle with marginal structural benefit — the plan is already A-grade.
Either path preserves the "narrow review → revise → promote" structure.

---

## 5. Updated Grade

**A.** Up from draft 6's A-.

The grade reflects:

- **+1 step** for Tier S × system-rework integration landing
  substantively across Primitives A/C/E/F/H with concrete native-feature
  identifications, existing-code surface targeting, and readiness /
  validation row updates. This is not a label change; the integration
  substance re-shapes Primitive G's scope materially and re-defines
  Primitive B's B.8/B.9/B.10 with concrete implementation paths.
- **+1 step** for §10.9 extensibility-patterns codification. Six
  patterns tied to enforcement surfaces (not aspirational prose); the
  pattern framework is durable infrastructure that outlives this
  initiative (same durability framing as §15.8). Missing Patterns 7–8
  (G11) don't drag the grade; they're additive not corrective.
- **No further step up** because: (a) rework_spec.md catalog coverage
  gap (G6) is substantive sub-plan-level incompleteness — it does not
  block direct promotion but does require a same-commit fix; (b) B.9
  vs. `.claude/agents/` relationship ambiguity (G10) is plan-level and
  was a miss in the Tier S integration for Primitive B; (c) §10.9
  missing Patterns 7–8 (G11) is a visible gap against the plan's own
  pattern discipline.
- **A+ would require** G6 and G10 closed (mandatory fixes) *plus* G11
  patterns added *plus* one of the strategic-layer observations (Track
  2.9) resolved. One tightening pass achieves the first three; the
  strategic-layer framing changes take operator judgment.

The prior A- grade was correct against draft 6; the A here is earned
by the Tier S integration depth and the extensibility codification,
not draft-inflation.

---

## 6. Open Questions to Operator / Orchestrator

Out-of-scope-for-this-review observations surfaced as questions per
the two-track handoff convention.

**Q5.** §14 Open Item #12 (ADR 002 review-cycle-as-evidence) is listed
alongside ADR 001 at Phase 0 kickoff filing. Would the ADR be stronger
evidence if filed at Phase 0 *close* instead of kickoff — when the plan
has demonstrably run, not just been drafted? This is a re-sequencing
question, not a structural challenge. Low stakes.

**Q6.** The `/review-claude-changelog` skill is scheduled via `/loop 3d`
(2-3×/week). Does the operator want the cadence itself to be revisitable
based on changelog velocity during Phase 0? E.g., if Claude Code ships
Tier S features at >1/week, the cadence tightens; if <1/month, it
loosens. Schedule-in-a-config-file vs. schedule-hardcoded.

**Q7.** Does the Phase 2 Decision Inputs digest (§15.4) compile outputs
from target-repo shape audits (§4.2) if the audits live at
`plans/steward_platform/0_hardening/target_repo_audit.md` (single file,
per-repo sections)? The §15.4 glob is
`plans/steward_platform/**/*.md` so it will, but the grouping logic
may surface one-audit-file-per-repo findings separately. Worth
verifying the digest's axis-bucket logic behaves correctly on the
shape-audit file. Sub-plan-level; not a draft 7 blocker.

**Q8.** §6.1 proving-run candidate is tightly coupled to
`plans/browser_game_expansion/` progress. If expansion plan enters a
pause / hold, does the data-sufficiency pivot (methodology-overhaul
alternative) activate automatically, or does Phase 1 entry block? Plan
reads as "activate automatically"; worth confirming as design intent.

---

## 7. Self-Conformance Check Against Goal #16 Conventions

Per the handoff: "drafting your own review under the conventions you're
evaluating is itself signal." Self-check against the seven §10.8
conventions:

| Convention | This artifact's conformance |
|---|---|
| Predictable `§N.M` section IDs | Yes — §1–§7 with stable section-prefixed structure; sub-sections §1.1–§7 with `.M` indexing. |
| Machine-parseable structured fields | Yes — disposition tables in §1.1 (per-fix) + §1.2 (per-primitive) + §1.3 (new sections) + §2.1 (plan-vs-actual gaps) use consistent column order; G6–G13 in §3 use stable subheaders (Severity / Evidence / Why this matters / Proposed fix / Cost). |
| Consistent cross-reference patterns | Yes — `§N.M` for in-plan internal references; `path/from/repo/root.md` for file references; no `./` or `../`. |
| Grep-clean naming | Yes — finding IDs G6–G13 unique and do not collide with analyst-a's S/SC/D/R, analyst-b's F1–F13, or analyst-c's G1–G5 / Q1–Q4. |
| Loadable as agent context with minimal preamble | Yes — first ~30 lines (header + TL;DR) establish reviewer, target, scope, recommendation, and grade. |
| Worked examples for any new schema | Not applicable — this artifact introduces no new schemas. |
| Stable IDs in mutable artifacts | Yes — disposition-table rows keyed by finding ID (G1–G5 from draft 6 review preserved; G6–G13 introduced cleanly); no in-place re-numbering would be needed on revision. |

If this review is itself appended to the draft-7-as-promoted lineage
(per §15 hybrid pattern), the disposition tables and G-findings are
auto-parseable by `compile_decision_inputs.py` extensions or a sibling
lint-style script. That structural property is the substantive test of
goal-#16 conventions; this artifact passes it.

---

## Phase 2 Decision Inputs

**Portability readiness:** no change (review of governing plan; no
portability evidence added).
**Meta-layer need:** no change (review is plan-internal; no meta-layer
signal).
**Kill signal for primitive(s) named:** N/A (no primitive execution
yet).
**Re-evaluation needed in Phase 3:** no (plan itself is pre-execution).
**Surprise finding:** The recurrence of the load-bearing-but-floating
pattern across three successive reviews (analyst-b F6 →
`compile_decision_inputs.py` ownership → analyst-c G1 →
`agent_readability_lint.py` ownership → analyst-d G6 → 21 ops-module
coverage gap in `rework_spec.md`) is itself signal that the
load-bearing-ownership review check is high-value and should become a
first-class discipline. A lint rule or template check — "any script,
module, or file referenced in §N.M of a plan or sub-plan must be
enumerated in the owning primitive's Work bullets and Phase 0/1
Readiness" — would close the recurrence at generalized-lint level.
Worth filing as a Primitive C sub-sub-plan candidate once the
`agent_readability_lint.py` (G1 fix) lands. Complementary to analyst-c's
Phase 2 Decision Inputs Surprise finding in draft 6 review.
**Disposition:** open
