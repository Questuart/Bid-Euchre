# SP-5-02: Platform-11 Skill Learning Loop

**Status:** postponed (2026-04-01 operator decision — platform work postponed indefinitely)
**Author:** analyst-a
**Date:** 2026-04-01
**Parent:** `plans/agent_ops/governing_plan.md` — Phase 5, Platform-11
**Registry ID:** SP-5-02
**Scope lock:** `plans/agent_ops/5_skill_learning/scope_lock.md`

---

## Problem Statement

The steward dispatches work using static priority and manual lane assignment.
Task completion outcomes are logged but never analyzed. There is no feedback
loop to improve dispatch accuracy or detect lane-task affinity patterns.

**Governing plan done-when:**
> - Repeated successful workflows can produce skill suggestions with provenance
> - Promotion/refinement cannot bypass review, context-safety, and rollback gates

The scope lock (2026-03-25) contains a comprehensive design with operator
feedback incorporated. This sub-plan translates that design into a concrete
PR decomposition for dispatch.

## Existing Infrastructure

| Component | State | Notes |
|-----------|-------|-------|
| `events.py` | Ready | Has `task_completed` event type; extensible payload |
| `task_queue.py` | Ready | `TaskPacket` is frozen dataclass; metadata dict available for new fields |
| `worker_pool.py` | Ready | `select_worker()` and `dispatch_to_worker()` accept domain hints |
| `skill_promotion.py` | Ready | Full lifecycle: propose → review → promote → disable. Context-safety scanning built in |
| `token_economy.py` | Ready | Cost/token/lines-added metrics available |
| `monitor.py` | Ready | Check registration pattern established |

## Open Question Resolution

The scope lock identifies two open questions. Recommended resolutions:

**Q1: Claude Code native capabilities / prior art**
→ **Skip investigation spike.** Claude Code's `/insights` feature and public
repos (Open Claw, Hermes) are not mature enough to provide reusable learning
loop components. The scope lock's MVP design (EWMA + task type taxonomy) is
well-specified and doesn't depend on external prior art. Investigation would
add 1h of lane time with low expected value.

**Q2: Complexity estimation at dispatch**
→ **Option A (orchestrator assigns manually) for MVP**, with Option B
(heuristic from file count) as a documented follow-up. The orchestrator
already assigns `priority` and `domain` at dispatch time; adding
`complexity_estimate` (1-5 integer) is minimal friction.

## PR Decomposition: 5 PRs

### PR1: Task type taxonomy and enriched outcome recording

**Scope:** Add `task_type` and `complexity_estimate` to TaskPacket metadata,
define the task type taxonomy, and enrich `task_completed` events with
structured outcome fields.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/learning.py` | NEW — Task type taxonomy enum/constants, outcome record dataclass, `TaskOutcome` with all fields from scope lock | ~120 |
| `src/bid_euchre/ops/task_queue.py` | Add `task_type` and `complexity_estimate` as optional TaskPacket metadata fields (no schema break — stored in existing `metadata` dict) | ~15 |
| `src/bid_euchre/ops/events.py` | Add `task_outcome_recorded` to VALID_EVENT_TYPES | ~3 |
| `tests/unit/test_ops_learning.py` | NEW — taxonomy validation, outcome record construction, serialization | ~80 |
| `tests/unit/test_ops_task_queue.py` | Test that task_type/complexity flow through metadata | ~20 |

**Design decision:** `task_type` and `complexity_estimate` go into the
existing `metadata` dict rather than as top-level TaskPacket fields. This
avoids breaking the frozen dataclass schema and keeps the extension
backward-compatible. The `learning.py` module provides accessor helpers:
`get_task_type(packet)`, `get_complexity(packet)`.

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_learning.py tests/unit/test_ops_task_queue.py -v
```

### PR2: Append-only outcomes log and affinity model computation

**Scope:** Implement the outcomes JSONL writer, affinity model computation
from the log (EWMA), and rebuild-from-log capability.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/learning.py` | EXTEND — `OutcomeLogger` (JSONL append writer with flock), `AffinityModel` (EWMA computation, per-lane × task_type stats, confidence scoring), `rebuild_affinity()` function | ~230 |
| `tests/unit/test_ops_learning.py` | EXTEND — JSONL round-trip, affinity computation from synthetic data, rebuild idempotency, EWMA decay validation | ~150 |

**Storage paths (gitignored):**
- `.claude/runtime/learning/outcomes.jsonl` — append-only event log
- `.claude/runtime/learning/lane_affinity.json` — derived affinity model
- `.claude/runtime/learning/snapshot_meta.json` — rebuild metadata

**Key invariants:**
- Affinity model is fully derivable from outcomes.jsonl (source of truth)
- EWMA with α=0.3 for recency bias
- Minimum N≥5 observations per task_type per lane before scoring
- Confidence = `min(1.0, observations / 20)` per task_type

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_learning.py -v -k "affinity or outcome"
```

### PR3: Dispatch advisor with anti-corruption guardrails

**Scope:** Build the dispatch advisor that ranks available lanes by affinity
score, plus all anti-corruption guardrails from the scope lock.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/learning.py` | EXTEND — `DispatchAdvisor` class: `rank_lanes()` (complexity-adjusted scoring), exploration policy (constrained by complexity and confidence), skew monitoring (>60% monoculture alert), override tracking | ~150 |
| `src/bid_euchre/ops/monitor.py` | Add `check_learning_health()` — data freshness warning (no outcomes in >24h), cold-start lane detection, skew alerts | ~30 |
| `tests/unit/test_ops_learning.py` | EXTEND — advisor ranking, exploration rate decay, skew detection, cold-start fallback to round-robin, guardrail enforcement | ~120 |
| `tests/unit/test_ops_monitor.py` | Test learning health check | ~20 |

**Advisor scoring formula:**
```
score = clean_merge_rate * (1 / complexity_adjusted_minutes) * (1 - rework_rate)
where complexity_adjusted_minutes = avg_minutes / avg_complexity
```

**Exploration policy:**
- Only explore on tasks with complexity ≤ 3
- Prefer exploration among top-3 ranked lanes (not fully random)
- Rate: `max(0.05, 0.20 * (1 - confidence))`

**Guardrails:**
- Advisory-only (orchestrator retains final authority)
- Minimum N≥5 and confidence > 0.3 before routing
- Skew alert if lane handles >60% of a task type over rolling 20-task window
- Override tracking with >30% rate triggering advisor quality review

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_learning.py tests/unit/test_ops_monitor.py -v
```

### PR4: Wire advisor into dispatch path (advisory mode)

**Scope:** Integrate the dispatch advisor into the worker_pool dispatch flow
as an advisory signal. The orchestrator sees the recommendation but retains
override authority. Also wire outcome recording into the post-merge hook.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/worker_pool.py` | In `select_worker()`, consult `DispatchAdvisor.rank_lanes()` when affinity data is available; log recommendation vs actual selection; record overrides | ~40 |
| `src/bid_euchre/ops/token_economy.py` | Add helper to extract cost/token metrics for outcome records | ~15 |
| `.claude/hooks/post-merge-notify.sh` | After completing a task packet, also record a `TaskOutcome` to `outcomes.jsonl` with timing, review rounds, PR number | ~25 |
| `scripts/internal/ops.py` | Add `learning` subcommand: `ops.py learning status` (show affinity model summary), `ops.py learning outcomes` (list recent outcomes) | ~60 |
| `tests/unit/test_ops_worker_pool.py` | Test advisor consultation in select_worker | ~30 |
| `tests/integration/test_learning_loop.py` | NEW — end-to-end: create packet with task_type → dispatch → complete → outcome recorded → affinity updated → next dispatch sees updated ranking | ~100 |

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_worker_pool.py tests/integration/test_learning_loop.py -v
uv run python scripts/internal/ops.py learning status  # Smoke
```

### PR5: Skill suggestion pipeline

**Scope:** Implement pattern detection in outcome data and evidence-based
skill suggestion generation through the existing skill_promotion pipeline.

**Files changed:**

| File | Change | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/learning.py` | EXTEND — `SkillSuggestionDetector`: scan outcomes for repeated patterns meeting evidence thresholds (N≥5, same task_type, low review churn ≤1.5 rounds, same file patterns), generate candidate SKILL.md with provenance | ~120 |
| `src/bid_euchre/ops/skill_promotion.py` | Add `propose_from_learning()` function that accepts a learning-generated suggestion and runs it through the existing propose → review pipeline. Rate limit: max 2 suggestions per overnight run | ~50 |
| `tests/unit/test_ops_learning.py` | EXTEND — pattern detection with synthetic outcome data, evidence threshold enforcement, rate limiting | ~80 |
| `tests/unit/test_ops_skill_promotion.py` | Test learning-sourced proposals flow through existing pipeline with provenance | ~40 |

**Evidence thresholds (all must be met):**
- Repeated success: N≥5 on same task_type
- Same major file or subsystem pattern across instances
- Low review churn: avg review rounds ≤ 1.5
- Consistent step sequence observable from outcome metadata

**Validation:**
```bash
uv run python -m pytest tests/unit/test_ops_learning.py tests/unit/test_ops_skill_promotion.py -v -k "suggestion or learning"
```

## Dependency Graph

```
PR1 (taxonomy + outcome schema) ──→ PR2 (outcomes log + affinity) ──→ PR3 (advisor + guardrails) ──→ PR4 (wiring)
                                                                                                   ↘
                                                                                                    PR5 (skill suggestions)
```

- PR1 → PR2 → PR3 → PR4: strictly sequential (each builds on the prior)
- PR5 depends on PR2 (needs outcome data) but is parallelizable with PR3/PR4

## Implementation Estimate

| PR | Lane-Hours | Description |
|----|------------|-------------|
| PR1 | 1.5h | Taxonomy + enriched outcome recording |
| PR2 | 2h | Outcomes log + affinity model |
| PR3 | 2h | Dispatch advisor + guardrails |
| PR4 | 2h | Advisory wiring + outcome recording hook |
| PR5 | 2h | Skill suggestion pipeline |
| **Total** | **9.5h** | |

## Acceptance Criteria

1. `TaskPacket` metadata supports `task_type` and `complexity_estimate` fields
2. Task completions are recorded to `outcomes.jsonl` with structured outcome
   data (timing, review rounds, outcome granularity, cost metrics)
3. Affinity model is computed from outcomes log using EWMA with α=0.3
4. Dispatch advisor ranks lanes by affinity score, controlled for complexity
5. All 7 anti-corruption guardrails from scope lock are implemented and tested
6. Advisor is advisory-only — orchestrator can override with tracking
7. Learning health monitoring is wired into the monitor cycle
8. Repeated patterns meeting evidence thresholds generate skill suggestions
   through the existing promotion pipeline
9. Rate limit: max 2 skill suggestions per overnight run
10. All existing tests pass (`make check`)

## Done-When Verification

From governing plan:

> repeated successful workflows can produce skill suggestions with provenance

**Verified by:** PR5 (skill suggestion detector with provenance metadata)

> promotion/refinement cannot bypass review, context-safety, and rollback gates

**Verified by:** PR5 uses existing `skill_promotion.py` pipeline which enforces
propose → review → promote with context-safety scanning at both proposal and
promotion time. No new bypass paths introduced.

## Evaluation Framework (Deferred)

The scope lock specifies a matched-cohort evaluation framework. This is
deferred to a follow-up PR after the advisor has accumulated baseline data
from 3+ overnight runs and 2+ daytime sessions (minimum 40 tasks across
≥5 task types). Filing as a GitHub issue at Phase 5 closeout.

## Risks

1. **Cold start.** No historical data exists. The advisor will be inactive
   (fallback to round-robin) until N≥5 per task_type accumulates. This may
   take 2-3 overnight runs. Mitigation: not a problem, just slow ramp-up.

2. **Outcome recording in hooks.** The post-merge hook is inline Python in a
   shell script. Adding outcome recording adds another failure point.
   Mitigation: wrap in try/except — outcome recording is best-effort; the
   merge must never fail because of a learning log write error.

3. **Schema evolution.** Adding fields to outcome records over time requires
   backward-compatible reading. Mitigation: all new fields are optional with
   defaults. The affinity rebuild function tolerates missing fields gracefully.

4. **Skill suggestion noise.** Auto-generated suggestions may be low quality
   during early ramp-up. Mitigation: rate limit (max 2 per overnight run),
   evidence thresholds (N≥5, low churn), and operator review (filed as GitHub
   issues with `skill-suggestion` label, never auto-promoted).

5. **Affinity model accuracy.** EWMA with a single scoring formula may not
   capture lane-task affinity well. Mitigation: the advisor is advisory-only;
   the orchestrator retains final authority. Accuracy improves with data
   volume and can be refined in Phase 2 (logistic regression, deferred).
