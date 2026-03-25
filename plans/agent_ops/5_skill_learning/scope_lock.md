# Platform-11: Skill Learning Loop — Scope Lock

**Status:** DRAFT (pending morning review)
**Author:** analyst lane
**Date:** 2026-03-25
**Parent:** `plans/agent_ops/governing_plan.md` — Phase 5, Platform-11
**Registry ID:** (to be assigned)

---

## Problem Statement

The steward dispatches work using static priority and manual lane assignment.
Skill files (`.claude/skills/*/SKILL.md`) are authored manually and promoted
through a review-gated process (`skill_promotion.py`). But the platform has no
feedback loop: it cannot learn from repeated task patterns to improve dispatch
accuracy, task estimation, or lane-task affinity.

**Current state:**
- Dispatch uses `task_queue.py` priority ordering + manual orchestrator judgment
- Skill files are static SKILL.md templates edited by humans or review follow-ups
- Worker pool assignment (`worker_pool.py`) is round-robin or explicit lane targeting
- Task completion outcomes are logged to the event system but never analyzed
- No mechanism to detect that "author-a is 2x faster at convention fixes" or "flex lanes consistently fail on complex refactors"

**Governing plan done-when:**
> - Repeated successful workflows can produce skill suggestions with provenance
> - Promotion/refinement cannot bypass review, context-safety, and rollback gates

## Proposed Solution

### Data Model

**Task Outcome Records** — extend the existing event system to capture structured
completion data:

```
{
  "event_type": "task_completed",
  "lane_id": "author-a",
  "task_id": "...",
  "domain": "platform",
  "task_type": "convention_fix",        // NEW: categorized task type
  "elapsed_minutes": 28,                // NEW: wall-clock duration
  "review_rounds": 1,                   // NEW: how many review iterations
  "files_changed": 3,                   // NEW: scope proxy
  "outcome": "merged",                  // NEW: terminal outcome
  "pr_number": 1801                     // existing
}
```

**Lane Affinity Model** — per-lane success metrics aggregated from outcomes:

```
{
  "lane_id": "author-a",
  "task_type_stats": {
    "convention_fix": {"count": 12, "avg_minutes": 22, "success_rate": 0.92},
    "complex_refactor": {"count": 3, "avg_minutes": 95, "success_rate": 0.67}
  },
  "last_updated": "..."
}
```

### Learning Algorithm

**Phase 1 (MVP):** Moving-average statistics per lane × task_type. No ML.
- Exponentially weighted moving average (EWMA) with α=0.3 for recency bias
- Simple affinity score: `score = success_rate * (1 / avg_minutes)`
- Dispatch advisor: given a task_type, rank available lanes by affinity score
- Falls back to round-robin when no history exists (cold start)

**Phase 2 (deferred):** Lightweight logistic regression on feature vectors
(task_type, domain, file_count, estimated_complexity) → predicted best lane.
Only justified when Phase 1 data shows clear lane differentiation.

### Skill Suggestion Pipeline

When a workflow pattern repeats successfully N times (N=5 default):
1. Extract the common steps from task outcome records
2. Generate a candidate SKILL.md with provenance (source task IDs, success count)
3. Submit as a skill promotion proposal via `skill_promotion.py`
4. Require review-gate approval before activation (existing gate)
5. Track suggestion acceptance/rejection rate as feedback

### Integration Points

| Component | Integration | Change Type |
|-----------|------------|-------------|
| `task_queue.py` | Add `task_type` field to TaskPacket | Schema extension |
| `worker_pool.py` | Consume lane affinity model for dispatch ranking | New advisor input |
| `events.py` | Add outcome fields to `task_completed` events | Schema extension |
| `skill_promotion.py` | Accept auto-generated suggestions with provenance | New suggestion source |
| `monitor.py` | Surface learning-loop health (data freshness, cold-start lanes) | New monitoring check |

### Storage

Lane affinity model persists at `.claude/runtime/learning/lane_affinity.json`.
Task type taxonomy defined in a new `src/bid_euchre/ops/learning.py` module.
No SQLite or external dependencies — JSON files consistent with existing ops patterns.

## Open Questions (for operator)

1. **What feedback signals matter most?**
   - PR merge time (wall clock from dispatch to merge)?
   - Review rounds (fewer = better)?
   - Lane idle time between tasks (lower = better throughput)?
   - **Recommendation:** Start with merge time + review rounds. Idle time is harder to attribute to lane quality vs work availability.

2. **Where does learning state live?**
   - JSON file in `.claude/runtime/learning/` (consistent with ops patterns)
   - SQLite (more query-friendly, but adds a dependency)
   - In-memory only (lost on session restart — bad for multi-session learning)
   - **Recommendation:** JSON file. Consistent with existing ops patterns. Can migrate to SQLite later if query needs grow.

3. **How to avoid overfitting to overnight run patterns?**
   - Overnight runs have different task mix (more convention fixes, fewer complex refactors)
   - Time-of-day bias: overnight lanes may be faster because there's less contention
   - **Recommendation:** Include `session_type` (overnight/daytime/interactive) in outcome records. Weight daytime observations higher for dispatch decisions. Require minimum N=5 observations per task_type before using affinity scores.

4. **Task type taxonomy — who defines it?**
   - Option A: Manual taxonomy in config (convention_fix, complex_refactor, investigation, etc.)
   - Option B: Auto-derived from file paths and PR descriptions
   - **Recommendation:** Option A for MVP. ~8-10 categories based on existing dispatch patterns. Auto-derivation is a Phase 2 enhancement.

5. **Evaluation criteria — how do we know the loop improved dispatch quality?**
   - Before/after comparison of: avg merge time, review rounds, lane idle time
   - Need baseline measurement BEFORE enabling the learning loop
   - **Recommendation:** Capture 2 full overnight runs of baseline statistics before activating dispatch advisor. Compare with 2 post-activation runs. Require >20 tasks per run for meaningful comparison.

6. **Should skill suggestions be auto-filed as GitHub issues?**
   - Pro: Durable, reviewable, fits existing workflow
   - Con: Issue noise, may create false sense of urgency
   - **Recommendation:** File as issues with `skill-suggestion` label, low priority. Operator reviews in batch during morning check-in.

## File Scope (estimated)

| File | Status | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/learning.py` | NEW | ~250 |
| `src/bid_euchre/ops/task_queue.py` | MODIFY | ~20 (add task_type field) |
| `src/bid_euchre/ops/worker_pool.py` | MODIFY | ~30 (consume affinity advisor) |
| `src/bid_euchre/ops/events.py` | MODIFY | ~10 (add outcome fields to VALID_EVENT_TYPES) |
| `src/bid_euchre/ops/skill_promotion.py` | MODIFY | ~40 (auto-suggestion source) |
| `src/bid_euchre/ops/monitor.py` | MODIFY | ~20 (learning health check) |
| `tests/unit/test_ops_learning.py` | NEW | ~200 |
| `tests/unit/test_ops_task_queue.py` | MODIFY | ~30 |
| `tests/integration/test_learning_loop.py` | NEW | ~100 |

## Dependencies

- **Platform-10 (preferred, not blocking):** The core-vs-adapter split would
  make the learning module cleanly portable. However, the learning loop can be
  built on top of existing ops modules and extracted later.
- **Platform-5 (satisfied):** Skill promotion pipeline already exists.
- **Event system (satisfied):** `events.py` already supports extensible payloads.

## Implementation Estimate

| Slice | PRs | Lane-hours | Description |
|-------|-----|------------|-------------|
| Data model + outcome recording | 1 | 1.5h | Extend TaskPacket + events with task_type, outcome fields |
| Lane affinity model | 1 | 2h | `learning.py` — EWMA computation, persistence, cold-start fallback |
| Dispatch advisor wiring | 1 | 1.5h | Wire affinity scores into worker_pool dispatch ranking |
| Skill suggestion pipeline | 1 | 2h | Pattern detection + auto-suggestion via skill_promotion |
| Monitoring + evaluation baseline | 1 | 1h | Health check, baseline capture, evaluation report |
| **Total** | **5 PRs** | **~8h** | |

## Risks

1. **Cold start problem.** No historical data to train from on first activation.
   Mitigation: fall back to round-robin until N≥5 observations per task_type.

2. **Feedback loop instability.** If the advisor routes all convention fixes to
   author-a (because it's fastest), author-a never gets complex refactor
   experience and other lanes never improve at convention fixes.
   Mitigation: 20% exploration rate — randomly assign to non-optimal lane 1-in-5
   tasks.

3. **Stale learning state.** Lane capabilities may change (new skills installed,
   model changes). Mitigation: EWMA decay ensures recent observations dominate.
   Add a `learning_state_age` monitor check that warns if no new outcomes
   recorded in >24h.

4. **Skill suggestion noise.** Auto-generated suggestions may be low quality.
   Mitigation: require review gate (existing), require N≥5 successes, and
   rate-limit to max 2 suggestions per overnight run.

5. **Schema migration.** Adding fields to TaskPacket and events requires
   backward compatibility. Mitigation: all new fields are optional with defaults.
   Existing payloads continue to work.
