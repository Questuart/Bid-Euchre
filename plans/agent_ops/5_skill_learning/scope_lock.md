# Platform-11: Skill Learning Loop — Scope Lock

**Status:** DRAFT (operator feedback incorporated)
**Author:** analyst lane
**Date:** 2026-03-25
**Updated:** 2026-03-25 (operator feedback round 1)
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
- Token economy tracking (`token_economy.py`) exists but is not connected to
  dispatch outcomes — cost, token usage, and lines-added metrics are available
  but not used for routing decisions

**Governing plan done-when:**
> - Repeated successful workflows can produce skill suggestions with provenance
> - Promotion/refinement cannot bypass review, context-safety, and rollback gates

## Proposed Solution

### Data Model

**Task Outcome Records** — extend the existing event system to capture structured
completion data. The outcome model must be rich enough to control for task
difficulty — fast completion alone does not indicate good routing if one lane
mostly receives easy work.

```
{
  "event_type": "task_completed",
  "lane_id": "author-a",
  "task_id": "...",
  "domain": "platform",
  "task_type": "convention_fix",        // NEW: categorized task type (see taxonomy)
  "complexity_estimate_at_dispatch": 2, // NEW: 1-5 scale, assigned at dispatch time
  "elapsed_minutes": 28,               // NEW: wall-clock duration
  "review_rounds": 1,                  // NEW: how many review iterations
  "files_changed": 3,                  // NEW: scope proxy
  "lines_added": 45,                   // NEW: from economy tracking
  "token_usage": 12500,                // NEW: from economy tracking
  "estimated_cost_usd": 0.15,          // NEW: from economy tracking
  "session_type": "overnight",         // NEW: overnight | daytime | interactive
  "requires_review_gate": true,        // NEW: was review gate required?
  "outcome": "merged",                 // NEW: terminal outcome (see below)
  "rollback_or_rework_required": false, // NEW: was rework needed post-merge?
  "acceptance_without_major_rewrite": true, // NEW: merged without major rewrite?
  "operator_override": false,          // NEW: did operator override advisor?
  "pr_number": 1801                    // existing
}
```

**Outcome granularity:** `"merged"` is too coarse — a task can merge after
painful cleanup and still look like success. Valid outcome values:

| Value | Meaning |
|-------|---------|
| `merged_clean` | Merged with ≤1 review round, no rework |
| `merged_with_rework` | Merged but required significant revision |
| `abandoned` | Task was abandoned or reassigned |
| `rolled_back` | Merged then reverted |
| `blocked` | Could not proceed, escalated |

**Lane Affinity Model** — per-lane success metrics aggregated from outcomes,
controlled for task complexity:

```
{
  "lane_id": "author-a",
  "task_type_stats": {
    "convention_fix": {
      "count": 12,
      "avg_minutes": 22,
      "avg_complexity": 1.8,
      "clean_merge_rate": 0.83,
      "rework_rate": 0.08,
      "avg_review_rounds": 1.1,
      "avg_token_usage": 8500,
      "avg_cost_usd": 0.12
    },
    "cross_module_refactor": {
      "count": 3,
      "avg_minutes": 95,
      "avg_complexity": 4.0,
      "clean_merge_rate": 0.67,
      "rework_rate": 0.33,
      "avg_review_rounds": 2.3,
      "avg_token_usage": 45000,
      "avg_cost_usd": 0.58
    }
  },
  "confidence": 0.72,
  "last_updated": "..."
}
```

### Adaptive Dispatch Heuristics

> **Naming convention:** This is not a "learning algorithm." Phase 1 implements
> outcome-informed dispatch heuristics. Reserve "learning" for the broader
> platform capability when genuine model-based prediction is warranted.

**Phase 1 (MVP): Outcome-Informed Dispatch Advisor.** Moving-average statistics
per lane × task_type, controlled for complexity. No ML.

- Exponentially weighted moving average (EWMA) with α=0.3 for recency bias
- Affinity score controlled for complexity:
  `score = clean_merge_rate * (1 / complexity_adjusted_minutes) * (1 - rework_rate)`
  where `complexity_adjusted_minutes = avg_minutes / avg_complexity`
- Dispatch advisor: given a task_type + complexity estimate, rank available
  lanes by affinity score
- Falls back to round-robin when no history exists (cold start)
- **Advisor is advisory only** — orchestrator retains final dispatch authority
  until the advisor is validated against baseline (see Evaluation section)

**Exploration policy** (replaces naive 20% random):
- Only explore on tasks below a risk threshold (complexity ≤ 3)
- Never explore on high-blast-radius tasks (complexity 4-5)
- Prefer exploration among plausible lanes (top-3 ranked), not fully random
- Decay exploration rate as confidence increases:
  `explore_rate = max(0.05, 0.20 * (1 - confidence))`
- Log all exploration decisions for evaluation

**Phase 2 (deferred):** Lightweight logistic regression on feature vectors
(task_type, domain, file_count, estimated_complexity) → predicted best lane.
Only justified when Phase 1 data shows clear lane differentiation and
the heuristic advisor has been validated against baseline.

### Skill Suggestion Pipeline

Task outcome records alone usually don't contain enough procedural detail to
reconstruct reliable skills — they capture outcomes, not method. Candidate
skill suggestions must draw from richer evidence.

**Evidence sources for skill suggestions:**
- Task metadata (type, domain, complexity, file patterns)
- Artifacts touched (which files, modules, test paths)
- Structured operator notes or traces (when available)
- Review comments and correction patterns (from review coordinator)
- Source task provenance (which tasks contributed to the pattern)

**Minimum evidence threshold** — all must be met before generating a suggestion:
- Repeated success (N≥5) on same task type
- Same major file or subsystem pattern across instances
- Low review churn (avg review rounds ≤ 1.5)
- Consistent step sequence observable from traces or notes

**Pipeline:**
1. Detect repeated pattern meeting all evidence thresholds above
2. Extract procedural steps from traces, review comments, and artifact patterns
3. Generate a candidate SKILL.md with full provenance (source task IDs,
   success count, evidence summary)
4. Submit as a skill promotion proposal via `skill_promotion.py`
5. **No auto-promotion** — require review-gate approval before activation
6. Track suggestion acceptance/rejection rate as feedback
7. Rate-limit: max 2 suggestions per overnight run to control noise
8. File accepted suggestions as GitHub issues with `skill-suggestion` label,
   low priority — operator reviews in batch during morning check-in

### Integration Points

| Component | Integration | Change Type |
|-----------|------------|-------------|
| `task_queue.py` | Add `task_type` + `complexity_estimate_at_dispatch` to TaskPacket | Schema extension |
| `worker_pool.py` | Consume lane affinity model for dispatch ranking (advisory) | New advisor input |
| `events.py` | Add enriched outcome fields to `task_completed` events | Schema extension |
| `token_economy.py` | Supply cost, token usage, lines-added metrics to outcomes | Read integration |
| `skill_promotion.py` | Accept auto-generated suggestions with provenance | New suggestion source |
| `monitor.py` | Surface learning-loop health (data freshness, cold-start lanes, skew alerts) | New monitoring checks |

### Storage

JSON files consistent with existing ops patterns. No SQLite or external
dependencies for MVP. Structured as append-only log + derived state:

| File | Purpose | Format |
|------|---------|--------|
| `.claude/runtime/learning/outcomes.jsonl` | Append-only event log of all task outcomes | JSONL, one record per completed task |
| `.claude/runtime/learning/lane_affinity.json` | Derived affinity model, rebuilt from log | JSON, regenerated on demand |
| `.claude/runtime/learning/snapshot_meta.json` | Version metadata for derived state | JSON, tracks rebuild timestamp + log offset |

**Design rationale:** The append-only outcomes log is the source of truth.
`lane_affinity.json` is a derived cache that can be rebuilt from the log at
any time. This gives full auditability (every outcome is preserved) and
rebuild capability (if the derived model is corrupted or the scoring formula
changes, regenerate from the log).

Task type taxonomy defined in a new `src/bid_euchre/ops/learning.py` module.

## Operator Decisions (from feedback round 1)

1. **Feedback signals:** Focus on merge time + review rounds for dispatch
   decisions. But **track all available metrics from the start** (cost, token
   usage, lines added, idle time) to create robust data for future iterations.
   Borrow metrics from economy tracking (`token_economy.py`).

2. **Storage:** JSON files in `.claude/runtime/learning/`. Append-only log +
   derived state (see Storage section above).

3. **Session type bias:** Include `session_type` in outcome records. Weight
   daytime observations higher. Require N≥5 observations per task_type before
   using affinity scores.

4. **Taxonomy:** Manual for MVP (see Task Type Taxonomy below). ~9 categories
   based on existing dispatch patterns. Auto-derivation is Phase 2.

5. **Evaluation:** Matched-cohort evaluation required (see Evaluation section
   below). Simple before/after comparison is insufficient.

6. **Skill suggestions:** File as GitHub issues with `skill-suggestion` label,
   low priority. Operator reviews in batch during morning check-in.

## Open Questions (remaining)

1. **Claude Code native capabilities:** How do Claude Code's built-in skills
   and `/insights` function work? Can we leverage them for the learning loop?
   Are there public repos for similar agentic development (Open Claw, Hermes,
   etc.) with skill learning loops we can draw from?
   **Action:** Investigation spike needed before implementation begins.

2. **Complexity estimation at dispatch:** Who assigns `complexity_estimate_at_dispatch`?
   - Option A: Orchestrator assigns manually (reliable but adds dispatch friction)
   - Option B: Heuristic from file count + scope_declared patterns (automated but noisy)
   - **Recommendation:** Option A for MVP with Option B as fallback when orchestrator omits it.

3. **Confidence threshold for advisory → active:** At what confidence level does
   the advisor transition from "shown to orchestrator" to "used for automatic
   ranking"? Needs operational experience to calibrate.

## Task Type Taxonomy (MVP)

Manual taxonomy based on observed dispatch patterns. The category
`ambiguous_or_open_ended` is critical — routing failures come from ambiguity
in task definition, not technical complexity alone.

| Task Type | Description | Typical Complexity |
|-----------|-------------|-------------------|
| `convention_fix` | Style, naming, import ordering, lint fixes | 1-2 |
| `focused_bugfix` | Single-cause bug with clear repro | 2-3 |
| `test_repair` | Fix broken tests, add missing coverage | 1-3 |
| `doc_update` | Documentation, plans, scope locks, MEMORY.md | 1-2 |
| `investigation` | Root-cause analysis, spike, feasibility study | 2-4 |
| `small_feature` | Bounded feature, ≤3 files, clear spec | 2-3 |
| `cross_module_refactor` | Multi-file structural change, API migration | 3-5 |
| `infra_or_tooling_change` | CI, hooks, scripts, build system | 2-4 |
| `ambiguous_or_open_ended` | Underspecified scope, requires clarification | 3-5 |

**Taxonomy rules:**
- Every dispatched task must have a `task_type` assigned at dispatch time
- If the orchestrator is unsure, use `ambiguous_or_open_ended` — this is data,
  not a failure
- Taxonomy is versioned; changes require a migration note in `snapshot_meta.json`

## Anti-Corruption Guardrails

Explicit guardrails to prevent the dispatch advisor from creating perverse
incentives or feedback loops:

1. **Advisory-only until validated:** The dispatch advisor is informational
   until it has been evaluated against baseline metrics (see Evaluation).
   The orchestrator retains final dispatch authority.

2. **No auto-promotion of skills:** All skill suggestions require review-gate
   approval. The learning loop cannot bypass `skill_promotion.py` gates.

3. **No lane ranking as prestige scoreboard:** Affinity scores are dispatch
   signals, not performance reviews. They must not be surfaced as lane
   "rankings" or used for lane deprecation decisions.

4. **Minimum observation threshold:** No routing based on fewer than N=5
   observations per task_type per lane AND minimum confidence > 0.3. Below
   this, fall back to round-robin.

5. **Skew monitoring:** Monitor for one lane taking a disproportionate share
   of one task type (lane monoculture). Alert if any lane handles >60% of
   a task type's volume over a rolling 20-task window.

6. **Exploration constraints:** See exploration policy in Adaptive Dispatch
   Heuristics section — never explore on high-blast-radius tasks.

7. **Operator override tracking:** Every operator override of the advisor is
   logged. High override rate (>30%) triggers review of advisor quality.

## Evaluation Framework

> Operator feedback: "2 overnight runs before and 2 after" is too flimsy.

**Matched-cohort design:** Compare advisor-recommended vs actual routing on
matched task cohorts — same task types, session types, and similar complexity
buckets.

**Baseline capture (before activating advisor):**
- Minimum 3 overnight runs + 2 daytime sessions
- Minimum 40 tasks total with representation across ≥5 task types
- Record all outcome fields even before advisor exists (creates training data)

**Evaluation metrics:**

| Metric | Description | Better = |
|--------|-------------|----------|
| Time to accepted completion | Dispatch → clean merge | Lower |
| Review rounds | Number of review iterations | Lower |
| Rework rate | % of tasks requiring major revision post-review | Lower |
| Rollback rate | % of tasks reverted after merge | Lower |
| Operator override rate | % of advisor recommendations overridden | Lower (but > 0 is healthy) |
| Advisor acceptance rate | % of recommendations followed | Higher |
| Clean merge rate | % of tasks merged with ≤1 review round | Higher |
| Cost per task (by type) | Token cost from economy tracking | Lower |

**Activation criteria:** Advisor transitions from advisory to active ranking
only when evaluation shows statistically significant improvement on ≥2 of the
above metrics (p < 0.05, paired comparison on matched cohorts).

## File Scope (estimated)

| File | Status | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/learning.py` | NEW | ~350 (affinity model, EWMA, exploration policy, log rebuild) |
| `src/bid_euchre/ops/task_queue.py` | MODIFY | ~25 (add task_type + complexity_estimate fields) |
| `src/bid_euchre/ops/worker_pool.py` | MODIFY | ~40 (consume affinity advisor, log overrides) |
| `src/bid_euchre/ops/events.py` | MODIFY | ~15 (add enriched outcome fields) |
| `src/bid_euchre/ops/token_economy.py` | MODIFY | ~15 (expose cost/token metrics for outcome records) |
| `src/bid_euchre/ops/skill_promotion.py` | MODIFY | ~50 (evidence-based suggestion source) |
| `src/bid_euchre/ops/monitor.py` | MODIFY | ~30 (learning health check + skew alerts) |
| `tests/unit/test_ops_learning.py` | NEW | ~300 (affinity, exploration, guardrails, rebuild) |
| `tests/unit/test_ops_task_queue.py` | MODIFY | ~30 |
| `tests/integration/test_learning_loop.py` | NEW | ~150 (end-to-end: outcome → affinity → dispatch) |

## Dependencies

- **Platform-10 (preferred, not blocking):** The core-vs-adapter split would
  make the learning module cleanly portable. However, the learning loop can be
  built on top of existing ops modules and extracted later.
- **Platform-5 (satisfied):** Skill promotion pipeline already exists.
- **Event system (satisfied):** `events.py` already supports extensible payloads.

## Implementation Estimate

| Slice | PRs | Lane-hours | Description |
|-------|-----|------------|-------------|
| Investigation spike | 1 | 1h | Claude Code /insights, public repo survey for prior art |
| Data model + outcome recording | 1 | 2h | Enrich TaskPacket + events, wire economy metrics, outcome granularity |
| Append-only log + rebuild | 1 | 1.5h | `outcomes.jsonl` writer, affinity model rebuild from log |
| Adaptive dispatch heuristics | 1 | 2h | `learning.py` — EWMA, complexity-controlled scoring, exploration policy |
| Anti-corruption guardrails | 1 | 1.5h | Skew monitor, override tracking, observation thresholds |
| Dispatch advisor wiring | 1 | 1.5h | Wire affinity scores into worker_pool (advisory mode) |
| Skill suggestion pipeline | 1 | 2h | Evidence-based pattern detection + suggestion via skill_promotion |
| Baseline capture + evaluation | 1 | 1.5h | Matched-cohort evaluation framework, baseline recording |
| **Total** | **~8 PRs** | **~13h** | |

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
