# Portability and Learning Checkpoints

**Phase:** 5 (`5_portability_and_learning`)
**Status:** PARTIAL — Platform-10 COMPLETE, Platform-11 PARTIALLY REACTIVATED (2026-04-20 — adaptive dispatch subset only)
**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-04-20 by author-d (SP-5-02 partially reactivated; operator approval 2026-04-20 for adaptive dispatch subset bounded to absorb token-economy Slices C/D/E)

---

### Step 1 — Platform-10: Complete core-vs-adapter portability layer

**Status:** COMPLETE
**Sub-plan:** SP-5-01 (`plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-10-portability-completion.md`)
**Depends on:** Phase 4 COMPLETE (satisfied 2026-04-01)
**Done when:**
- Lane topology (KNOWN_AUTHOR_LANES) is provided by adapter, not hardcoded in task_queue.py ✅
- Ops CLI primary commands (monitor, task, dispatch, controller) use ServiceProvider ✅
- Portability manifest documents all remaining Bid-Euchre-specific coupling ✅
- Hook callers use ServiceProvider or adapter imports ✅

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| SP-5-01 PR1: Lane topology extraction | COMPLETE | 2026-04-14 | author-a | PR #2655 merged — AbstractLaneConfig ABC, BidEuchreLaneConfig adapter, backward-compat re-export |
| SP-5-01 PR2: ServiceProvider CLI migration | COMPLETE | 2026-04-14 | author-b | PR #2656 merged — _get_provider() helper, 4 primary command groups migrated |
| SP-5-01 PR3: Coupling manifest + audit script | COMPLETE | 2026-04-14 | author-a | PR #2657 merged — PORTABILITY_MANIFEST.md + audit_portability.py + regression test |
| SP-5-01 PR4: Hook migration + cleanup | COMPLETE | 2026-04-14 | author-b | PR #2659 merged — post-merge-notify.sh, inbound-channel-audit.py, park skill migrated |

**Groundwork shipped (Phase 4):**
- PR #1807 — Core ops ABCs (4 interfaces)
- PR #1813 — Core ops extraction (controller, monitor wrappers)
- PR #1817 — Repo adapter (TaskQueueService, WorkerPoolService)
- PR #1950 — ServiceProvider wiring
- PR #1954 — Core adapter contract tests (2256 LOC)

### Step 2 — Platform-11: Skill learning loop

**Status:** IN_PROGRESS (partially reactivated 2026-04-20 — adaptive dispatch subset only)
**Sub-plan:** SP-5-02 (`plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-11-skill-learning-loop.md`)
**Scope lock:** `plans/agent_ops/5_skill_learning/scope_lock.md`
**Depends on:** Phase 4 COMPLETE (satisfied 2026-04-01)

**Reactivation scope (2026-04-20):**
Operator decision 2026-04-20 approved partial reactivation bounded to the
adaptive dispatch subset. This reactivation absorbs Slices C/D/E of the
token-economy restart plan (`plans/sessions/2026-04-20_token_economy_restart_plan.md`),
with `model_hint` and `effort_hint` folded into the existing `task_type` +
`complexity_estimate` packet metadata work. The skill-suggestion pipeline
work (PR5) remains out of the current reactivation scope — it stays
POSTPONED until the dispatch-advisor portion is validated. Platform-12 and
Platform-13 remain POSTPONED.

**Done when:**
- Task type taxonomy and enriched outcome recording exist
- Affinity model computed from outcomes log via EWMA
- Dispatch advisor ranks lanes (advisory mode)
- Anti-corruption guardrails enforce all 7 protections
- Skill suggestion pipeline generates proposals through existing promotion gates
- All existing tests pass

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| SP-5-02 PR1: Task type taxonomy + outcome schema | IN_PROGRESS | 2026-04-20 | — | Absorbs token-economy Slice C packet metadata work; adds `model_hint`/`effort_hint` alongside `task_type`/`complexity_estimate` |
| SP-5-02 PR2: Outcomes log + affinity model | IN_PROGRESS | 2026-04-20 | — | Absorbs token-economy Slice C outcome-capture work |
| SP-5-02 PR3: Dispatch advisor + guardrails | IN_PROGRESS | 2026-04-20 | — | Absorbs token-economy Slices D/E (fixed policy + shadow-mode adaptive) |
| SP-5-02 PR4: Advisory wiring + outcome hook | IN_PROGRESS | 2026-04-20 | — | Absorbs token-economy Slices D/E dispatch wiring |
| SP-5-02 PR5: Skill suggestion pipeline | POSTPONED | — | — | Out of current reactivation scope — stays postponed until dispatch advisor validated |

### Step 3 — Phase 5 closeout and transition to Phase 6

**Status:** POSTPONED
**Depends on:** Steps 1 and 2 COMPLETE
**Done when:**
- Both Platform-10 and Platform-11 done-when criteria verified
- Evaluation framework follow-up issue filed (deferred from SP-5-02)
- Phase 5 checkpoints all COMPLETE
- Sub-plan registry updated
- Phase 6 unblocked

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`, `POSTPONED`

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-5-01 | `plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-10-portability-completion.md` | **completed** | Step 1 |
| SP-5-02 | `plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-11-skill-learning-loop.md` | in_progress | Step 2 |

## Blockers

_(none)_

## Session Log

| Date | Summary |
|------|---------|
| 2026-04-01 | Phase 5 scaffolding created by analyst-a (task packet 3abba00f182e). Sub-plans SP-5-01 (Platform-10, 4 PRs, 6h) and SP-5-02 (Platform-11, 5 PRs, 9.5h) drafted. Total: 9 PRs, 15.5h. Platform-10 groundwork audit: ABCs + ServiceProvider + adapter + tests exist (5 PRs shipped), but no callers migrated yet. 196 repo-specific coupling occurrences across 34 ops files. |
| 2026-04-01 | **POSTPONED INDEFINITELY** — operator decision to focus on browser game product. Phase 4 was the final delivered platform phase. All steps and sub-plans marked POSTPONED. |
| 2026-04-14 | **Platform-10 REACTIVATED AND COMPLETED** — orchestrator session "Stabilize & Extract". All 4 SP-5-01 PRs shipped (#2655, #2656, #2657, #2659). Coupling manifest produced (250 occurrences across 36 files). audit_portability.py regression gate added. Platform-11 remains POSTPONED. Goal: enable steward extraction into Fund repo. |
| 2026-04-20 | **Platform-11 PARTIALLY REACTIVATED** — operator decision 2026-04-20 approved partial SP-5-02 reactivation bounded to the adaptive dispatch subset. SP-5-02 absorbs Slices C/D/E of the token-economy restart plan (`plans/sessions/2026-04-20_token_economy_restart_plan.md`); Slices A/B/F remain on separate session plans; `model_hint`/`effort_hint` folded into existing `task_type`/`complexity_estimate` packet metadata work. SP-5-02 PR5 (skill suggestion pipeline) stays POSTPONED. Platform-12 and Platform-13 remain POSTPONED. Motivated by analyst-a scoping on #2169. |
