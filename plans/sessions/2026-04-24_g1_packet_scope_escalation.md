# Session plan: Packet d70a297dbe6a (G.1 audit) scope-conflict escalation

**Date:** 2026-04-24
**Lane:** analyst-a
**Task packet:** `d70a297dbe6a` — "Primitive G.1 — Bespoke-surface delete-list audit"
**Dispatched:** 2026-04-24T18:17:49Z by orchestrator
**Escalation type:** Deviate Authority — mis-scoped packet; target path already occupied
**Blocker message:** `d1ffd03d24944b3d` (analyst-a → orchestrator, type=blocker)

## Outcome

Pending orchestrator decision on reshape. No code or plan edits beyond this
session artifact and the blocker message. Work is parked until the
orchestrator chooses one of the options in §4.

## §1. What this packet asked me to produce

Per the packet description, G.1 produces a single markdown file at
`plans/steward_platform/7_primitive_G/shaping.md` with five required
sections:

1. **Bespoke-surface inventory table** — shrinking-stakes order; columns:
   `surface | line_count | call_site_count | test_count | native_candidate | confidence | rationale`.
2. **Per-surface substitution candidates** — native-substrate replacement
   with source-grounded rationale.
3. **G.1–G.N decomposition proposal** — phases with dependency order,
   stop-loss criteria, proving-run design (parallel-run + measured
   token-cost delta).
4. **Methodology preservation section** — explicit PORTABLE vs
   SUBSTRATE-REPLACEABLE separation.
5. **Verification Plan section** — per Pattern 10 + analyst prompt
   policy.

Scope surfaces enumerated: `scripts/internal/ops.py` +
`src/bid_euchre/ops/**`, `.claude/hooks/**`, `.claude/skills/**`,
`scripts/internal/review_driver.py`, `.claude/rules/prompt_policy/**` +
`effort_policy.md` + `tool_risk_registry.md`, `.claude/tmux/steward-session.sh`
+ `lane_models.json`.

## §2. What I found on main

**Finding:** `plans/steward_platform/7_primitive_G/shaping.md` already
exists at the target path. It is a 616-line shaping doc authored by
analyst-c under packet `c7c6a25ee902` and merged via
**PR #2784 on 2026-04-24T05:55:07Z** — approximately 12.5 hours
*before* this packet (d70a297dbe6a) was dispatched.

The existing doc covers:

- All 12 §5-G Work bullets (governing plan lines 577–590) mapped to
  14 execution packets across 6 tracks (A–F).
- Per-packet specs with scope, upstream gates, Pattern 10 verification
  surface, rollback path, effort estimate (§3–§8).
- Upstream-artifact crosswalk (§2) citing PRs #2765, #2766, #2768,
  #2778, #2779, #2780, #2741, #2743, #2762.
- Pattern 10 deliverable → surface table (§9, 14 rows).
- Rollback-validation Phase 0 slice (§10) — Goal #13 coverage.
- Phase 2 Decision Inputs (§11, 5 prompts).
- Verification Plan (§12, 13 rows + 4 worked examples).
- Self-review + risks surfaced (§13).

## §3. Overlap analysis — d70a297dbe6a vs. PR #2784 existing shape

### §3.1 Strong overlap — the existing doc covers these d70a297dbe6a requirements

| d70a297dbe6a requirement | Covered by PR #2784 §§ | Notes |
|---|---|---|
| Per-surface substitution candidates (native-substrate mapping) | §3–§8 per-packet "Scope" + "Verification surface" subsections | Every surface named in d70a297dbe6a's scope list has a substitution proposal |
| G.1–G.N decomposition with dependency order | §1.3 Track topology + §§3–§8 | 14 packets (G-A1..G-F2) in 6 tracks, with serial/parallel/gating notes |
| Stop-loss / deferral criteria per phase | §3.3 G-A3, §4.1 G-B1, §4.2 G-B2 "If substrate unavailable → defer to Phase 1" | Three substrate-gated packets each have explicit deferral paths |
| Methodology preservation (PORTABLE vs SUBSTRATE-REPLACEABLE) | §11 Phase 2 Decision Inputs — "Portability readiness" paragraph | Partial — not a dedicated section |
| Verification Plan (Pattern 10) | §12 | Complete |
| Rollback validation | §10 (Phase 0 slice of Goal #13) | Complete for §3–§8 packets |

### §3.2 Genuine gaps — d70a297dbe6a requirements NOT covered by PR #2784

| d70a297dbe6a requirement | Status in PR #2784 | Gap |
|---|---|---|
| **Bespoke-surface inventory TABLE** with columns `surface \| line_count \| call_site_count \| test_count \| native_candidate \| confidence \| rationale` | Not present | Existing doc has per-packet specs, not a summary inventory matrix across all bespoke surfaces |
| **Dedicated methodology-preservation section** separating PORTABLE vs SUBSTRATE-REPLACEABLE | Touched in §11, not a standalone section | Operator-legible separation of methodology (what survives substrate change) vs. mechanics (what's substrate-specific) is absent as a first-class doc section |
| **Proving-run design** (parallel-run + measured token-cost delta) | Rollback smoke exists (§10); no parallel-run or token-cost-delta methodology | The mechanism-evaluation discipline — run bespoke + native side-by-side, measure token-cost delta — is absent |
| **Broader bespoke-surface coverage** — `scripts/internal/ops.py` as a unit, `scripts/internal/review_driver.py`, `.claude/rules/prompt_policy/**` as delete/reduce candidates, `.claude/tmux/steward-session.sh` + `lane_models.json` as a unit with audit disposition | Partial; each cited in passing | Existing doc addresses specific surgery targets (worktrees.py, dashboard.py, heartbeat, token_economy.py, 5 hook/skill dirs) but doesn't inventory the full bespoke ops + rules + hooks + skills surface with keep/reduce/delete decisions |

### §3.3 Collision — writing at the declared path would overwrite

The packet says "G.1 produces: File: plans/steward_platform/7_primitive_G/shaping.md"
as if the file does not exist. Executing the packet as written would
overwrite 616 lines of shipped content that:

- PR #2784's MEMORY.md session entry references by path.
- Downstream packets (B.9a/B.9b chain, Primitive F Packet 11 coordination,
  Primitive H.0 canary) cite specific §§ (§3.1, §4.1, §5.1, §9, §10, §12).
- The governing plan §5-G references as the current active shaping for
  Primitive G Phase 0.

A silent overwrite would break citations across the plan graph and
discard the analyst-c review cycle that produced the PR #2784 doc.

## §4. Reshape options

### Option A (RECOMMENDED) — Sidecar audit artifact

**Proposed path:** `plans/steward_platform/7_primitive_G/bespoke_surface_audit.md`
(or `plans/steward_platform/7_primitive_G/g1_delete_list_audit.md`).

**Scope:**

- Write the inventory TABLE with columns `surface | line_count | call_site_count | test_count | native_candidate | confidence | rationale` covering the full bespoke-surface set enumerated in d70a297dbe6a.
- Write the methodology-preservation section as a first-class doc section (PORTABLE vs SUBSTRATE-REPLACEABLE).
- Write the proving-run design section (parallel-run + token-cost-delta measurement methodology).
- Cross-reference the existing shaping.md §3–§8 per-packet specs rather than duplicate.
- Add §12-analogue Verification Plan rows for the sidecar artifact itself.

**Pros:**

- Zero risk to PR #2784's citation surface.
- Captures the three genuine gaps (§3.2) without relitigating the 14-packet decomposition.
- Preserves the analyst-c review cycle + downstream citations.
- Matches the steward-platform doc convention of sidecar artifacts
  (baseline.md, claude_code_changelog_implications.md, plugin_source_evaluation.md,
  rework_spec.md, g13_archetype_mapping.md, b9a_prompt_authoring_shaping.md
  all sit alongside shaping.md rather than replacing it).

**Cons:**

- Two-file surface for Primitive G audit material (mitigated by mutual
  cross-references in each doc's References section).

### Option B — Close packet as substantively absorbed

**Proposed disposition:**

- Close d70a297dbe6a as "substantively absorbed by PR #2784".
- Optionally file 3 micro-packets (one per §3.2 genuine gap) as follow-up:
  - Micro-packet 1: Inventory table as a §N amendment to existing shaping.md.
  - Micro-packet 2: Methodology-preservation section as a §N amendment.
  - Micro-packet 3: Proving-run design as a §N amendment or sidecar.

**Pros:**

- Clean packet-state (no mis-scoped active packet in queue).
- Smaller amendment footprint per micro-packet.

**Cons:**

- Three amendment PRs against an already-shipped doc vs. one sidecar PR.
- Each amendment risks further churn on PR #2784's citation surface
  (every edit bumps line numbers downstream citations may reference).

### Option C — Replace existing shaping.md with rewrite

**Not recommended.** Would require:

- Re-establishing all §3–§8 per-packet specs (analyst-c's audit + review cycle).
- Updating downstream citations across MEMORY.md, governing_plan.md §5-G,
  and Primitive F/H cross-references to the new line/section numbers.
- Discarding analyst-c's review cycle + the PR #2784 commit signal.

Only defensible if the operator explicitly wants a full rewrite, which
the packet text does not signal.

## §5. Recommendation

**Option A (sidecar audit).** It closes the three genuine gaps from §3.2
without touching PR #2784's citation surface. Matches the existing
steward-platform doc-layout convention.

Sidecar scope would be ~300–500 lines (inventory table is the bulk;
methodology section is ~50 lines; proving-run design is ~100 lines; refs
and verification plan ~50 lines).

If Option A is approved, the orchestrator should either:

1. **Re-dispatch d70a297dbe6a** with an amended description pointing at
   the sidecar path and scope updated to cross-reference PR #2784.
   Cleanest packet-state path.
2. **Or mark d70a297dbe6a reshape-pending** and dispatch a successor
   packet. Preserves this packet's audit trail in the task queue as
   "reshape-escalated on 2026-04-24".

## §6. Why I did not just pick Option A and start writing

Per `.claude/skills/start-task/SKILL.md` Phase 1 step 4 ("If scope is
ambiguous, ask the orchestrator for clarification before proceeding. Do
not guess at scope boundaries.") and per the steward-analyst lane
charter Deviate Authority clause ("If investigation reveals the task
was mis-scoped … return it to the orchestrator with a proposed reshape
rather than executing the original packet"), the right move is to
surface this escalation and let the orchestrator choose.

The three options have materially different downstream consequences
(Option A preserves citation stability; Option B triples PR count;
Option C discards shipped work). That's an orchestrator-level decision,
not an analyst-a unilateral one.

## §7. Evidence

- Existing shape: `plans/steward_platform/7_primitive_G/shaping.md` (616 lines, on origin/main)
- Origin PR: #2784 merged 2026-04-24T05:55:07Z by Questuart
- Origin packet: `c7c6a25ee902` (analyst-c; referenced in PR #2784 body)
- Governing plan reference: §5-G lines 552–606
- This packet: `d70a297dbe6a` dispatched 2026-04-24T18:17:49Z by orchestrator
- Blocker message: `d1ffd03d24944b3d` (analyst-a → orchestrator, high priority)

## §8. Next steps

1. Orchestrator reads this doc.
2. Orchestrator picks one of Options A / B / C (or proposes a fourth).
3. If Option A: orchestrator re-dispatches d70a297dbe6a with sidecar path
   and cross-reference scope, or dispatches a successor packet.
4. If Option B: orchestrator closes d70a297dbe6a as absorbed and dispatches
   the 3 micro-packets on the operator's schedule.
5. If Option C: orchestrator confirms the intent and dispatches a
   rewrite packet with explicit citation-migration scope.

Until then, analyst-a is parked on packet d70a297dbe6a with this
escalation as the durable artifact.

## §9. Not addressed (scope guard)

This escalation does NOT:

- Write content at `plans/steward_platform/7_primitive_G/shaping.md` (existing doc preserved).
- Begin the sidecar-audit content (no G.1 deliverable authored).
- Change any governing-plan text.
- File any GitHub issue (blocker message + this doc are sufficient surface for orchestrator review).
- Dispatch to any other lane.

All such actions await orchestrator reshape decision.

## Verification Plan

Per Pattern 10 + analyst prompt policy: every shaping doc deliverable
names a verification surface. This session plan IS the deliverable of
the G.1 escalation, and its verification surface is:

| Deliverable (§N of this doc) | Class | Verification surface | Acceptance condition |
|---|---|---|---|
| §2 existence of PR #2784 content | evidence | `gh pr view 2784 --json mergedAt,author` + `git show origin/main:plans/steward_platform/7_primitive_G/shaping.md \| wc -l` | merge timestamp 2026-04-24T05:55:07Z; line count ≈ 616 |
| §3.1 strong-overlap table rows | cross-check | grep-verify each cited §§ in `plans/steward_platform/7_primitive_G/shaping.md` | all 6 rows resolve |
| §3.2 genuine-gap table rows | cross-check | grep-negative for the missing surfaces/sections in existing shape | all 4 rows confirmed-absent (inventory table columns, dedicated methodology section, proving-run design methodology, broader bespoke-surface coverage) |
| §4 options | shaping proposal | operator-review prompt: "Is Option A the lowest-blast-radius path that closes the §3.2 gaps?" | operator chooses one of A/B/C/other |
| §5 recommendation | shaping recommendation | same operator-review prompt | operator decision recorded in follow-up packet or inbox reply |
| §8 next-step decision point | orchestrator action | orchestrator message back to analyst-a (ack, reshape, or reject) | response in message bus within operator response-time window |

**Pass = orchestrator reads, decides, and dispatches the reshape.**
