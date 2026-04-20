<!-- review-tier: medium -->
# Session Plan: Token Economy Restart + Adaptive Dispatch

**Date:** 2026-04-20
**Scope:** Resume token-economy optimization work for [#2169](https://github.com/Questuart/Bid-Euchre/issues/2169), extend the measurement layer to support model/effort-aware attribution, and scope adaptive dispatch now while keeping dispatch policy flexible until real steward-era results are available.
**Branch:** `ops/token-economy-restart`
**Related:** #2169, #2159, #1770, #1454, #1947

## Status (2026-04-20 — post-scoping)

This document is retained as the **intent-of-record** for the token-economy
restart program. After analyst-a's scoping on #2169 and operator decision on
2026-04-20, the slices are split across governance homes to avoid inventing
ad hoc planning structures (per `docs/02_agent/AGENTS.md` §12.3):

| Slice | Scope | Governance Home | Status |
|-------|-------|-----------------|--------|
| Slice A | Re-baseline and harden measurement path | Session plan under `plans/sessions/` (to be authored) | Pending session plan |
| Slice B | Extend telemetry to lane × model × effort | Session plan under `plans/sessions/` (to be authored) | Pending session plan |
| Slice C | Add routing metadata and outcome capture | **SP-5-02 (Platform-11) — partially reactivated 2026-04-20** | Folded into SP-5-02 |
| Slice D | Fixed policy controls | **SP-5-02 (Platform-11) — partially reactivated 2026-04-20** | Folded into SP-5-02 |
| Slice E | Adaptive dispatch in shadow mode | **SP-5-02 (Platform-11) — partially reactivated 2026-04-20** | Folded into SP-5-02 |
| Slice F | Evaluate and decide whether to promote | Evaluation session plan under `plans/sessions/` (to be authored after D/E land) | Pending session plan |

Operator (2026-04-20) approved partial Phase 5 Step 2 reactivation bounded to
the adaptive dispatch subset. `model_hint` and `effort_hint` from Slices C/D
are absorbed into SP-5-02's existing `task_type` + `complexity_estimate`
packet metadata work — see the SCOPE EXTENSION section in
`plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-11-skill-learning-loop.md`.

Platform-12 and Platform-13 remain POSTPONED. The body of this plan below is
retained so readers can see the full pre-split program; refer to the
governance homes above for current execution state.

## Summary

The repo already has a usable token-economy observability stack:

- telemetry import and rollups in `src/bid_euchre/ops/token_economy.py`
- CLI surfaces in `scripts/internal/ops.py`
- dashboard wiring in `src/bid_euchre/ops/dashboard.py`
- a pre-steward baseline at `plans/sessions/2026-03-23_token-economy-baseline.md`
- a later optimization analysis at `plans/sessions/2026-04-03_token_economy_optimization.md`

The compact-window quick win from #2169 already shipped in
`.claude/tmux/steward-session.sh`. The remaining work is to:

1. refresh the baseline with steward-era data
2. harden the measurement path
3. add model/effort-aware attribution
4. add task-routing hints for model and effort
5. build adaptive dispatch as an advisory framework with shadow-mode logging

This plan treats adaptive dispatch as part of the same token-economy program,
but not as a fixed algorithm. The interfaces and evaluation loop are in scope
now; the final scoring policy is intentionally left adjustable.

## Context

### Already shipped

- `src/bid_euchre/ops/token_economy.py` imports both legacy session-meta and
  per-project JSONL telemetry.
- `scripts/internal/ops.py` exposes `usage import`, `usage attribute`,
  `usage summary`, `usage lanes`, `usage throughput`, and
  `usage anti-patterns`.
- `src/bid_euchre/ops/dashboard.py` surfaces token-economy data in the
  dashboard view.
- `.claude/tmux/steward-session.sh` sets
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000` for all non-orchestrator lanes.

### Gaps still open

- The March 23 baseline only covers pre-steward data.
- Token rollups are lane-aware, but not model-aware or effort-aware.
- `src/bid_euchre/ops/task_queue.py` does not yet carry explicit
  `model_hint` / `effort_hint` routing metadata.
- `src/bid_euchre/ops/worker_pool.py` dispatches by availability/domain, not by
  token-efficiency or learned lane affinity.
- `scripts/internal/ops.py task complete` emits a minimal `task_completed`
  event payload without token-aware outcome fields.
- The skill-learning and cross-model design exists in postponed planning docs,
  but the operational substrate needed to evaluate it has not been realized.

## Scope

### In scope

1. Fresh steward-era baseline and current-state waste report
2. Measurement hardening for importer, attribution, CLI, and dashboard
3. Model × effort token attribution and rollups
4. `TaskPacket` routing hints using the existing metadata channel in
   `src/bid_euchre/ops/task_queue.py`
5. Dispatch-policy defaults for model and effort
6. Advisory-only adaptive dispatch with recommendation logging
7. Evaluation/reporting that compares recommendations, actual routing, and
   outcomes

### Out of scope

1. Reopening the postponed Phase 5/6 governing plan as a full platform program
2. Fully automatic adaptive routing on day one
3. Dynamic lane spawning or a new external scheduler
4. Provider/subscription failover from #1947
5. Replacing the current worker-pool lifecycle or task queue contract

## Data Contracts

This plan changes runtime metrics and routing metadata, so the data contracts
must remain explicit and backward-compatible.

### Existing code-owned contracts to preserve

- `src/bid_euchre/ops/task_queue.py`
  - `TaskPacket` is a frozen dataclass
  - `metadata: dict[str, Any]` is the extension point for non-breaking fields
- `src/bid_euchre/ops/events.py`
  - append-only JSONL event log under `.claude/runtime/events/events.jsonl`
- `src/bid_euchre/ops/token_economy.py`
  - repo-owned runtime store under `.claude/runtime/token_economy/`
- `src/bid_euchre/ops/worker_pool.py`
  - `select_worker()` and `dispatch_to_worker()` remain the dispatch surface

### Planning references that define the intended extension points

- `plans/agent_ops/5_cross_model/scope_lock.md`
- `plans/agent_ops/5_portability_and_learning/sub/2026-04-01_platform-11-skill-learning-loop.md`

This restart plan uses those documents as design inputs, but keeps the actual
implementation bounded to the current repo state and issue #2169.

## Deliverables

1. A new steward-era baseline report under `plans/sessions/`
2. Stable model/effort-aware token rollups in
   `src/bid_euchre/ops/token_economy.py`
3. CLI and dashboard support for model/effort breakdowns
4. `TaskPacket` metadata conventions for:
   - `model_hint`
   - `effort_hint`
   - `task_type`
   - `complexity_estimate`
5. Enriched task outcome recording that joins routing choice, elapsed time,
   token usage, review churn, and shipped outcome
6. Advisory dispatch scorer and recommendation log
7. Before/after evaluation proving whether the policy is helping

## Implementation Plan

### Slice A: Re-baseline and harden the measurement path

**Goal:** Establish trustworthy current-state data before changing routing.

**Requires:**
- current JSONL telemetry import path in `src/bid_euchre/ops/token_economy.py`
- current CLI and dashboard paths to still function

**Produces:**
- new steward-era baseline report
- measurement-health findings
- explicit gaps between current telemetry and desired optimization metrics

**Files:**
- `src/bid_euchre/ops/token_economy.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/dashboard.py`
- `tests/unit/test_token_economy.py`
- `tests/unit/test_ops_token_economy.py`
- `tests/unit/test_ops_dashboard.py`
- `plans/sessions/2026-04-20_token_economy_baseline_refresh.md` (new)

**Tasks:**
1. Re-run import and attribution on steward-era data
2. Verify summary/lanes/throughput/dashboard totals agree
3. Make stale or partial token stores visible in operator surfaces
4. Write a new baseline that answers:
   - where tokens are being spent now
   - how much spend maps to shipped output vs churn
   - which lanes/work types are the worst offenders

**Validation:**
- `uv run python -m pytest tests/unit/test_token_economy.py -v`
- `uv run python -m pytest tests/unit/test_ops_token_economy.py -v`
- `uv run python -m pytest tests/unit/test_ops_dashboard.py -v`

### Slice B: Extend telemetry to lane × model × effort

**Goal:** Make token-economy data rich enough to support routing decisions.

**Requires:**
- Slice A baseline and measurement verification
- confirmation of which model/effort data is actually available in JSONL

**Produces:**
- model-aware and effort-aware rollups
- CLI/dashboard views for those dimensions
- no routing behavior change yet

**Files:**
- `src/bid_euchre/ops/token_economy.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/dashboard.py`
- `tests/unit/test_token_economy.py`
- `tests/unit/test_ops_token_economy.py`

**Tasks:**
1. Extend import/rollup logic to capture model and effort where available
2. Preserve null-safe behavior when effort cannot be determined
3. Add summary views for:
   - lane × model
   - lane × effort
   - model × work outcome
4. Update the baseline report to show whether premium model spend is
   concentrated in productive or unproductive work

**Validation:**
- `uv run python -m pytest tests/unit/test_token_economy.py -v`
- `uv run python -m pytest tests/unit/test_ops_token_economy.py -v`

### Slice C: Add routing metadata and outcome capture

**Goal:** Create the durable substrate that both fixed policy and adaptive
dispatch will consume.

**Requires:**
- Slice B model/effort rollups
- existing `TaskPacket.metadata` extension path in
  `src/bid_euchre/ops/task_queue.py`

**Produces:**
- durable packet metadata conventions
- enriched task outcome records
- recommendation vs actual routing evidence

**Files:**
- `src/bid_euchre/ops/task_queue.py`
- `src/bid_euchre/ops/events.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/token_economy.py`
- `tests/unit/test_ops_task_queue.py`
- `tests/unit/test_ops_events.py`
- `tests/unit/test_ops_cli.py`

**Tasks:**
1. Standardize packet metadata keys:
   - `task_type`
   - `complexity_estimate`
   - `model_hint`
   - `effort_hint`
2. Enrich task completion payloads emitted by `scripts/internal/ops.py`
3. Join outcome records with token-economy metrics after completion
4. Record enough outcome detail to compare:
   - recommended lane vs actual lane
   - token spend
   - elapsed time
   - review rounds / rework
   - shipped outcome

**Validation:**
- `uv run python -m pytest tests/unit/test_ops_task_queue.py -v`
- `uv run python -m pytest tests/unit/test_ops_events.py -v`
- `uv run python -m pytest tests/unit/test_ops_cli.py -v`

### Slice D: Implement fixed policy controls

**Goal:** Ship low-risk model/effort tuning before adaptive routing makes any
recommendations.

**Requires:**
- Slice C packet metadata and outcome capture

**Produces:**
- lane defaults for model/effort
- task-level overrides for low-risk work classes
- a controlled first rollout

**Files:**
- `src/bid_euchre/ops/worker_pool.py`
- `src/bid_euchre/ops/task_queue.py`
- `.claude/tmux/steward-session.sh` (only if lane startup settings need to move)
- `tests/unit/test_ops_worker_pool.py`
- `tests/unit/test_steward_session.py`

**Tasks:**
1. Add lane-default model and effort policy in the worker-pool layer
2. Respect task-level `model_hint` / `effort_hint` when present
3. Start with low-risk categories only:
   - ops monitoring
   - review coordination
   - docs-only tasks
   - test-only tasks
   - convention fixes
4. Leave complex implementation work on current defaults until measured data
   shows the cheaper path is safe

**Validation:**
- `uv run python -m pytest tests/unit/test_ops_worker_pool.py -v`
- `uv run python -m pytest tests/unit/test_steward_session.py -v`

### Slice E: Adaptive dispatch in shadow mode

**Goal:** Scope adaptive dispatch now, but keep the scoring logic flexible and
non-binding until real results justify automatic routing.

**Requires:**
- Slice C outcome records
- Slice D fixed policy rollout

**Produces:**
- advisory scorer
- recommendation logging
- operator-override evidence
- a path to later automation if results are good

**Files:**
- `src/bid_euchre/ops/worker_pool.py`
- `src/bid_euchre/ops/events.py`
- `src/bid_euchre/ops/token_economy.py`
- `src/bid_euchre/ops/learning.py` (new, if needed for scorer/outcome logic)
- `tests/unit/test_ops_worker_pool.py`
- `tests/unit/test_ops_events.py`
- `tests/unit/test_token_economy.py`

**Tasks:**
1. Rank candidate lanes using simple, adjustable inputs:
   - task type
   - complexity
   - recent clean completion rate
   - average token usage
   - average cycle time
   - rework / review churn
2. Emit recommendation data before dispatch
3. Preserve orchestrator control; do not auto-route yet
4. Log:
   - recommendation
   - selected lane
   - override flag
   - eventual outcome

**Shadow-mode rule:** Adaptive dispatch must start as advisory-only. The
current dispatch path remains the source of truth until measured evidence shows
the advisor is helping.

**Validation:**
- `uv run python -m pytest tests/unit/test_ops_worker_pool.py -v`
- `uv run python -m pytest tests/unit/test_ops_events.py -v`

### Slice F: Evaluate and decide whether to promote

**Goal:** Decide whether the fixed policy and advisory dispatch should expand,
stay as-is, or be rolled back.

**Requires:**
- at least one controlled period of production-like use after Slices D and E

**Produces:**
- evaluation report
- explicit go/no-go recommendation for automatic routing

**Files:**
- `plans/sessions/2026-04-20_token_economy_restart_eval.md` (new)
- `src/bid_euchre/ops/token_economy.py` (only if reporting helpers are needed)

**Decision questions:**
1. Did tokens per merged PR or completed packet improve?
2. Did review churn or rework get worse?
3. Are model downgrades being used on the right classes of work?
4. Is the advisory scorer predictive enough to trust on low-risk tasks?

## Adaptive Dispatch Policy Guardrails

To keep adaptive dispatch flexible while preventing scope drift, the following
interfaces are locked but the scoring formula is not:

1. **Locked now**
   - packet metadata keys
   - event/outcome schema
   - recommendation logging
   - evaluation metrics

2. **Deliberately unlocked**
   - exact scoring weights
   - whether tokens or elapsed time dominate ranking
   - exploration rate / novelty penalty
   - confidence thresholds for eventual auto-routing

This lets the code ship a stable advisory framework while keeping room to tune
the policy against actual steward results.

## Testing Strategy

Targeted test files for this plan:

- `tests/unit/test_token_economy.py`
- `tests/unit/test_ops_token_economy.py`
- `tests/unit/test_ops_dashboard.py`
- `tests/unit/test_ops_task_queue.py`
- `tests/unit/test_ops_worker_pool.py`
- `tests/unit/test_ops_events.py`
- `tests/unit/test_ops_cli.py`
- `tests/unit/test_steward_session.py`

Preferred validation sequence as slices land:

```bash
uv run python -m pytest tests/unit/test_token_economy.py tests/unit/test_ops_token_economy.py -v
uv run python -m pytest tests/unit/test_ops_task_queue.py tests/unit/test_ops_worker_pool.py tests/unit/test_ops_events.py -v
uv run python -m pytest tests/unit/test_ops_cli.py tests/unit/test_ops_dashboard.py tests/unit/test_steward_session.py -v
make check-quiet
```

## Risks

1. **Telemetry ambiguity:** effort may not be recoverable reliably from all
   sessions; rollups must degrade gracefully.
2. **Policy overreach:** moving too much work to cheaper settings too early may
   increase rework and review churn.
3. **Adaptive monoculture:** a naive scorer could repeatedly select one lane and
   create hidden bottlenecks.
4. **Schema drift:** adding richer outcome payloads without a clear contract
   could make dashboards and audit tools disagree.
5. **False confidence:** good token savings with bad shipped outcomes would be a
   regression, not a win.

## Rollback Plan

1. Keep adaptive dispatch advisory-only behind a flag or explicit call path.
2. Keep fixed policy overrides narrow and easy to disable.
3. Preserve the current availability/domain-based dispatch as the fallback.
4. Treat new rollups as additive; do not remove existing lane-level summaries.
5. If the data becomes inconsistent, fall back to current token-economy
   reporting and disable routing-specific outputs until repaired.

## Timeline / Execution Order

Recommended execution order:

1. Slice A — baseline refresh and measurement hardening
2. Slice B — model/effort-aware attribution
3. Slice C — routing metadata and outcome capture
4. Slice D — fixed policy controls
5. Slice E — adaptive dispatch in shadow mode
6. Slice F — evaluation and promotion decision

The critical dependency is that no routing change lands before the refreshed
baseline and enriched outcome capture exist.

## Outcome

_To be filled after implementation._
