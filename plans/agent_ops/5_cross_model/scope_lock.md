# Platform-12: Cross-Model Service Lanes — Scope Lock

**Status:** DRAFT (pending morning review)
**Author:** analyst lane
**Date:** 2026-03-25
**Parent:** `plans/agent_ops/governing_plan.md` — Phase 6, Platform-12
**Registry ID:** (to be assigned)

---

## Problem Statement

All steward lanes currently run the same Claude model (typically Claude Sonnet 4
via Claude Code). This is a one-size-fits-all approach that doesn't match the
varying complexity of dispatched work:

- **Convention fixes** (5-15 min, 1-2 files): Haiku-class speed would suffice,
  at lower cost and faster turnaround
- **Complex architectural refactors** (60-120 min, 5+ files): Opus-class depth
  and reasoning would improve first-pass quality
- **Lightweight formatting / linting**: Could use the fastest available model
- **Review work** (Codex CLI): Already uses a different model externally, but
  not through the lane system

**Current state:**
- `task_queue.KNOWN_AUTHOR_LANES` treats all lanes identically
- `worker_pool.py` dispatches based on availability, not capability
- No per-lane or per-task model configuration
- Token economy tracking (`token_economy.py`) doesn't distinguish model tiers
- Codex review runs as a local subprocess, not as a service lane with the same
  task packet / message bus coordination

**Governing plan done-when:**
> - A second-model reviewer can consume assigned review work and emit durable
>   findings without becoming a hidden blocking loop
> - Second-model findings are recorded as verdicts in the Platform-3 review
>   substrate, not as a separate review truth model
> - Second-model failures degrade into explicit service-lane health signals
>   rather than silent stalls

## Proposed Solution

### Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Orchestrator                  │
                    │  (dispatch with model_hint metadata) │
                    └───────────┬───────────────────────────┘
                                │
                    ┌───────────▼───────────────────────────┐
                    │         Worker Pool Manager            │
                    │  (match task.model_hint to lane.model) │
                    └───────────┬───────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
    ┌───────▼──────┐   ┌───────▼──────┐   ┌───────▼──────┐
    │  author-a     │   │  author-b     │   │  codex-review │
    │  model: sonnet│   │  model: opus  │   │  model: codex │
    │  tier: standard│  │  tier: premium│   │  tier: advisory│
    └──────────────┘   └──────────────┘   └───────────────┘
```

### Model Configuration

**Per-lane model assignment** via the worktree registry (existing JSON files in
`.claude/runtime/worktree_registry/`):

```json
{
  "lane_id": "author-a",
  "model": "sonnet",
  "model_tier": "standard",
  "capabilities": ["convention_fix", "small_feature", "test_writing"],
  ...existing fields...
}
```

**Per-task model hint** via TaskPacket metadata:

```python
@dataclass
class TaskPacket:
    ...existing fields...
    model_hint: str | None = None       # "opus", "sonnet", "haiku", None=any
    model_tier: str | None = None       # "premium", "standard", "economy", None=any
    complexity_estimate: str | None = None  # "high", "medium", "low"
```

**Routing logic:** The worker pool manager matches `task.model_hint` or
`task.model_tier` to `lane.model_tier`. When no hint is provided, any lane can
accept the task (backward compatible). When a hint is provided but no matching
lane is available, the task queues until a matching lane frees up (with a
configurable timeout before falling back to any available lane).

### Service Lane Types

| Lane Type | Model | Role | Health Monitoring |
|-----------|-------|------|------------------|
| `author-*` (standard) | Sonnet | Implementation work | Existing lane health |
| `author-*` (premium) | Opus | Complex architecture | Existing + cost tracking |
| `author-*` (economy) | Haiku | Convention fixes, formatting | Existing + throughput tracking |
| `codex-review` | Codex CLI | Advisory code review | New: review-specific health |
| `codex-maint` | Codex CLI | Maintenance tasks | New: maintenance-specific health |

### Codex Service Lane Integration

Transform the current Codex subprocess review loop into a proper service lane:

1. **Review request flow:** PR opened → review request enters review queue →
   `codex-review` lane picks up request → runs Codex CLI → writes verdict →
   publishes status
2. **Task packet interface:** Same `TaskPacket` schema with `domain="review"`,
   `model_hint="codex"`
3. **Health signals:** Lane health tracks Codex response time, failure rate,
   and degraded-service state
4. **Circuit breaker:** If Codex fails 3 consecutive reviews, lane enters
   `degraded` state and findings surface in supervisor dashboard
5. **Fallback:** When `codex-review` is degraded, reviews continue through
   the existing local review coordinator path

### Token Economy Integration

Extend `token_economy.py` with multi-model accounting:

```python
@dataclass
class SessionRecord:
    ...existing fields...
    model: str = "sonnet"               # NEW
    model_tier: str = "standard"        # NEW
    estimated_cost_usd: float = 0.0     # NEW: per-model cost estimation
```

Dashboard token economy section gains:
- Per-model token breakdown
- Cost efficiency comparison (tokens/PR by model tier)
- Model utilization rates

## Open Questions (for operator)

1. **Per-lane model config or per-task model selection?**
   - Option A: Each lane is permanently assigned a model at startup via
     `.claude/settings.json` or registry config
   - Option B: Model is selected per-task and lanes dynamically switch
   - Option C: Hybrid — lanes have a default model but can be overridden per-task
   - **Recommendation:** Option A (per-lane). Claude Code doesn't support
     dynamic model switching within a session. A lane's model is determined at
     `claude` CLI launch time via `--model` flag. Per-task switching would
     require session restart, defeating the purpose.

2. **Cost tracking implications?**
   - Different models have dramatically different pricing (Opus ~5x Sonnet,
     Haiku ~0.1x Sonnet)
   - Token economy currently tracks volume but not cost
   - **Recommendation:** Add `estimated_cost_usd` field using a simple lookup
     table of per-model rates. This is approximate but useful for fleet cost
     awareness.

3. **Model capability mismatches?**
   - What happens when Haiku is assigned a complex refactor by accident?
   - How do we detect capability mismatch vs just a slow task?
   - **Recommendation:** Use `complexity_estimate` in TaskPacket. The
     orchestrator sets it at dispatch time. Worker pool validates
     `complexity_estimate` against `lane.model_tier` and warns on mismatch
     (but doesn't block — operator may intentionally override).

4. **Does this need Claude Code API changes or just launch-flag routing?**
   - Claude Code supports `--model` flag at launch
   - No runtime model switching API exists
   - The `tmux send-keys` dispatch pattern already controls lane startup commands
   - **Recommendation:** Launch-flag routing only. Modify `steward-session.sh`
     to accept per-pane model config. No API changes needed.

5. **Codex service lane — local or remote?**
   - Current Codex review uses local Codex CLI (ChatGPT subscription, ~60s)
   - Alternative: Codex Cloud API (when available)
   - **Recommendation:** Keep local Codex CLI for now. The service lane
     abstraction means we can swap the backend later without changing the
     integration contract.

6. **How many model tiers at MVP?**
   - Minimum: 2 (standard Sonnet + advisory Codex)
   - Comfortable: 3 (add Opus for premium lanes)
   - Full: 4 (add Haiku for economy lanes)
   - **Recommendation:** Start with 2 tiers (standard + advisory). Add
     premium/economy only when overnight runs demonstrate clear task-type
     differentiation from Platform-11 learning data.

## File Scope (estimated)

| File | Status | Lines |
|------|--------|-------|
| `src/bid_euchre/ops/model_routing.py` | NEW | ~200 (routing logic, tier definitions) |
| `src/bid_euchre/ops/task_queue.py` | MODIFY | ~25 (model_hint, model_tier fields) |
| `src/bid_euchre/ops/worker_pool.py` | MODIFY | ~50 (model-aware dispatch matching) |
| `src/bid_euchre/ops/token_economy.py` | MODIFY | ~40 (multi-model accounting) |
| `src/bid_euchre/ops/supervisor.py` | MODIFY | ~30 (service-lane health classification) |
| `src/bid_euchre/ops/review_queue.py` | MODIFY | ~30 (Codex service lane integration) |
| `.claude/tmux/steward-session.sh` | MODIFY | ~20 (per-pane model config) |
| `tests/unit/test_ops_model_routing.py` | NEW | ~200 |
| `tests/unit/test_ops_worker_pool.py` | MODIFY | ~50 |
| `tests/integration/test_codex_service_lane.py` | NEW | ~150 |

## Dependencies

- **Platform-10 (strongly preferred):** Core-vs-adapter split makes model
  routing cleanly generic. Without it, model routing will contain
  Bid-Euchre-specific assumptions that must be extracted later.
- **Platform-3 (satisfied):** Review substrate already exists for Codex
  verdict recording.
- **Platform-5 (satisfied):** Skill system exists for capability tagging.
- **Platform-11 (preferred, not blocking):** Learning loop data would inform
  which task types benefit from which model tiers. Without it, model assignment
  is manual.

## Implementation Estimate

| Slice | PRs | Lane-hours | Description |
|-------|-----|------------|-------------|
| Model routing core + tier definitions | 1 | 1.5h | `model_routing.py`, TaskPacket extensions |
| Worker pool model-aware dispatch | 1 | 1.5h | Matching logic, fallback timeout, mismatch warnings |
| Codex service lane | 2 | 3h | Review queue integration, health signals, circuit breaker |
| Token economy multi-model accounting | 1 | 1h | Per-model cost tracking, dashboard extension |
| Session launcher model config | 1 | 1h | `steward-session.sh` per-pane model flags |
| **Total** | **6 PRs** | **~8h** | |

## Risks

1. **Claude Code model switching limitation.** Model is fixed at session start.
   Cannot dynamically switch mid-session. This means premium lanes must be
   pre-allocated, not on-demand. Mitigation: explicit lane-model assignment in
   session launcher.

2. **Codex service lane reliability.** Codex CLI already has ~10% failure rate
   in current review loop. Wrapping it as a service lane doesn't fix the
   underlying reliability. Mitigation: circuit breaker + explicit degraded
   state + fallback path.

3. **Cost runaway.** Opus lanes burn tokens 5x faster. An overnight run with
   4 Opus lanes could exceed budget. Mitigation: per-tier token budget in token
   economy. Alert when premium tier exceeds configurable threshold.

4. **Complexity estimate accuracy.** Orchestrator must estimate task complexity
   at dispatch time, before seeing the code. Misjudgment routes simple tasks to
   expensive lanes or complex tasks to weak lanes. Mitigation: mismatch warning
   in worker pool + learning loop feedback (Platform-11).

5. **Lane pool fragmentation.** With 3-4 model tiers, each tier has fewer
   available lanes. A premium task may wait even though economy lanes are idle.
   Mitigation: configurable fallback timeout (default 10min) before degrading to
   any available lane.
