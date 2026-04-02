# Platform-12: Cross-Model Service Lanes — Scope Lock

**Status:** POSTPONED INDEFINITELY (2026-04-01 operator decision — platform work postponed to focus on browser game product)
**Author:** analyst lane
**Date:** 2026-03-25
**Updated:** 2026-03-25 (operator feedback round 1)
**Parent:** `plans/agent_ops/governing_plan.md` — Phase 6, Platform-12
**Registry ID:** (to be assigned)

---

## Problem Statement

All steward lanes currently run Claude Opus 4 at high reasoning effort. Only the
ops lane runs Sonnet. This uniform-Opus approach maximizes quality but doesn't
match the varying complexity of dispatched work — and it makes fleet cost
opaque:

- **Convention fixes** (5-15 min, 1-2 files): Haiku or Sonnet at low effort
  would suffice, at dramatically lower cost and faster turnaround
- **Standard implementation** (15-45 min, 2-4 files): Opus at medium effort
  balances quality and cost
- **Complex architectural refactors** (60-120 min, 5+ files): Opus at high
  effort is the right fit — which is what we already have everywhere
- **Lightweight formatting / linting**: Could use the fastest available model
  at lowest effort
- **Review work** (Codex CLI): Already uses a different model externally, but
  not through the lane system

**Current baseline:**
- All author/analyst/flex lanes: **Opus 4, high reasoning effort**
- Ops lane: **Sonnet 4** (adequate for dispatch/monitoring)
- No per-lane model differentiation beyond ops
- No reasoning effort control — all lanes run high
- `task_queue.KNOWN_AUTHOR_LANES` treats all lanes identically
- `worker_pool.py` dispatches based on availability, not capability
- Token economy tracking (`token_economy.py`) doesn't distinguish model tiers
  or reasoning effort
- Codex review runs as a local subprocess, not as a service lane with the same
  task packet / message bus coordination
- Cost attribution is invisible — no way to know which lanes, models, or effort
  levels are driving spend

**Governing plan done-when:**
> - A second-model reviewer can consume assigned review work and emit durable
>   findings without becoming a hidden blocking loop
> - Second-model findings are recorded as verdicts in the Platform-3 review
>   substrate, not as a separate review truth model
> - Second-model failures degrade into explicit service-lane health signals
>   rather than silent stalls

## Proposed Solution

### Two-Axis Model: Model × Reasoning Effort

The solution has **two independent configuration axes:**

1. **Model** (per-lane, set at launch): Which Claude model runs in the lane
2. **Reasoning effort** (per-task, set at dispatch): How hard the model thinks

This separation matters because model is a session-level property (Claude Code
`--model` flag at launch), while reasoning effort can be set per-prompt via
the API's `reasoning_effort` parameter or Claude Code's effort configuration.

```
                    ┌─────────────────────────────────────────┐
                    │            Orchestrator                   │
                    │  dispatch with: model_hint + effort_hint │
                    └───────────┬───────────────────────────────┘
                                │
                    ┌───────────▼───────────────────────────────┐
                    │          Worker Pool Manager               │
                    │  match model_hint → lane.model             │
                    │  pass effort_hint → task packet metadata   │
                    └───────────┬───────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼───────┐   ┌──────────▼──────┐   ┌────────────▼──────┐
│  author-a      │   │  author-b        │   │  codex-review      │
│  model: opus   │   │  model: sonnet   │   │  model: codex-cli  │
│  effort: dynamic│  │  effort: fixed   │   │  effort: n/a       │
│  (high/med/low)│   │  (single-level)  │   │  (external model)  │
└────────────────┘   └─────────────────┘   └────────────────────┘
```

### Model Configuration (Axis 1 — Per-Lane)

**Per-lane model assignment** via the worktree registry (existing JSON files in
`.claude/runtime/worktree_registry/`):

```json
{
  "lane_id": "author-a",
  "model": "opus",
  "effort_levels": ["high", "medium", "low"],
  "capabilities": ["convention_fix", "small_feature", "test_writing"],
  "...existing fields..."
}
```

Model is set at **lane launch time** via the `claude --model <model>` flag.
Since Claude Code doesn't support dynamic model switching within a session,
the model is a session-level property. This means **no API changes are needed**
— just launch-flag routing. The `tmux send-keys` dispatch pattern already
controls lane startup commands; we simply parameterize the model flag per pane.

**MVP models:**

| Model | Effort Levels | Lanes |
|-------|---------------|-------|
| **Opus 4** | high, medium, low | Premium author lanes (complex work) |
| **Sonnet 4** | single (fixed) | Standard author lanes, ops |
| **Haiku 4** | single (fixed) | Economy lanes (convention fixes, formatting) |
| **Codex CLI** | n/a (external) | Review lane |

> **Note:** Only Opus supports 3 reasoning effort levels at MVP. Sonnet and
> Haiku are single-effort — their effort level is fixed and not configurable
> per-task. This keeps the initial complexity bounded.

### Reasoning Effort Configuration (Axis 2 — Per-Task)

**Per-task reasoning effort** via TaskPacket metadata, set dynamically at
dispatch time by the orchestrator based on task complexity:

```python
@dataclass
class TaskPacket:
    ...existing fields...
    model_hint: str | None = None         # "opus", "sonnet", "haiku", "codex", None=any
    effort_hint: str | None = None        # "high", "medium", "low", None=lane-default
    complexity_estimate: str | None = None # "high", "medium", "low"
```

**Effort routing rules:**
- Opus lanes accept all three effort levels — orchestrator sets effort per-task
- Sonnet/Haiku lanes ignore `effort_hint` (single-effort models at MVP)
- When `effort_hint` is None, the lane uses its default effort level
- The orchestrator determines effort from task complexity: convention fixes →
  low, standard features → medium, architectural work → high

**Model routing logic:** The worker pool manager matches `task.model_hint` to
`lane.model`. When no hint is provided, any lane can accept the task (backward
compatible). When a hint is provided but no matching lane is available, the task
queues until a matching lane frees up (with a configurable timeout before
falling back to any available lane).

### Service Lane Types

| Lane Type | Model | Effort | Role | Health Monitoring |
|-----------|-------|--------|------|------------------|
| `author-*` (premium) | Opus | high/med/low | Complex architecture, multi-file features | Existing + cost tracking + effort tracking |
| `author-*` (standard) | Sonnet | fixed | Standard implementation, moderate features | Existing lane health |
| `author-*` (economy) | Haiku | fixed | Convention fixes, formatting, linting | Existing + throughput tracking |
| `codex-review` | Codex CLI | n/a | Advisory code review | New: review-specific health |
| `ops` | Sonnet | fixed | Dispatch, monitoring, fleet management | Existing |

> **Stable end goal:** A mixed fleet where model AND effort are both tuned to
> task requirements. Not just "pick a model" but "pick a model at the right
> thinking intensity." The two axes together define the cost/quality tradeoff
> space.

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

### Token Economy Integration — 3-Dimensional Tracking

Extend `token_economy.py` with **three-dimensional** cost and usage tracking:
**lane × model × reasoning effort**. This is the key to understanding what is
causing cost bloat with granular attribution.

```python
@dataclass
class SessionRecord:
    ...existing fields...
    model: str = "opus"                   # NEW: opus, sonnet, haiku, codex
    reasoning_effort: str = "high"        # NEW: high, medium, low
    estimated_cost_usd: float = 0.0       # NEW: per-model + per-effort cost estimate

# Cost estimation lookup (approximate — even crude estimates are valuable)
COST_RATES = {
    # (model, effort): cost_multiplier relative to sonnet-fixed
    ("opus", "high"): 5.0,
    ("opus", "medium"): 3.0,    # Reduced reasoning = fewer output tokens
    ("opus", "low"): 1.5,
    ("sonnet", "fixed"): 1.0,   # Baseline
    ("haiku", "fixed"): 0.1,
    ("codex", "n/a"): 0.0,      # ChatGPT subscription, no API cost
}
```

**Usage and cost tracked along all three dimensions:**
- Per-lane: "author-a spent $X this run"
- Per-model: "Opus lanes account for Y% of total cost"
- Per-effort: "High-effort tasks cost Z× more than medium"
- Combined: "author-a running Opus at high effort: $W per PR"

### Live Dashboard

A live dashboard (not just CLI text output) for fleet economy visualization:

**Required views:**
1. **Cost breakdown** — stacked bar chart: lane × model × effort attribution
2. **Usage heatmap** — which lanes are active, what model/effort, current task
3. **Efficiency metrics** — cost per PR, tokens per PR, by model tier
4. **Trend lines** — cost over time, with model mix evolution
5. **Alert indicators** — budget threshold warnings, cost anomalies

**Implementation options (to be decided during planning):**
- Rich terminal dashboard (e.g., `textual` TUI) — runs in a tmux pane
- Lightweight HTML dashboard served by the existing FastAPI app
- Jupyter notebook with auto-refresh — reuses existing notebook infra

> **Operator note:** The dashboard is a first-class deliverable, not a
> nice-to-have. The goal is to make fleet economy legible enough to improve
> it — you can't optimize what you can't see.

## Resolved Questions (operator decisions)

These questions from the original draft have been resolved by operator feedback:

1. **Per-lane model config or per-task model selection?**
   → **RESOLVED: Per-lane model, per-task reasoning effort.** Model is set at
   lane launch time (launch-flag routing). Reasoning effort is set per-task at
   dispatch time by the orchestrator. Two separate axes.

2. **Cost tracking implications?**
   → **RESOLVED: 3-dimensional tracking (lane × model × effort).** Even crude
   estimates are valuable. Track cost attribution granularly enough to identify
   what's causing bloat.

3. **Does this need Claude Code API changes or just launch-flag routing?**
   → **RESOLVED: Launch-flag routing only.** No API changes needed. Model is
   per-lane via `--model` flag. The tmux dispatch pattern already parameterizes
   per-pane commands.

4. **How many model tiers at MVP?**
   → **RESOLVED: 3 models (Opus, Sonnet, Haiku) + Codex CLI.** Only Opus gets
   3 reasoning effort levels. Sonnet and Haiku are single-effort.

5. **Codex service lane — local or remote?**
   → **RESOLVED: Include Codex local CLI as a model option.** It's already in
   use for reviews. Formalize it as a service lane in the model roster.

## Open Questions (remaining)

1. **Dashboard technology choice?**
   - Rich TUI (`textual`) in a tmux pane vs. HTML dashboard vs. notebook
   - Tradeoff: TUI is always visible but limited in visualization richness;
     HTML/notebook can show charts but require a browser tab
   - **Recommendation:** Rich TUI for real-time fleet status, with a notebook
     for deeper post-run analysis. Two complementary views.

2. **Reasoning effort API surface?**
   - How does the effort hint reach Claude Code? Options:
     - (a) Set in the task prompt preamble ("respond at medium effort")
     - (b) Use Claude Code's `--reasoning-effort` flag if/when available
     - (c) Configure via `.claude/settings.json` per-lane, override per-task
   - **Recommendation:** Start with (a) — prompt-level effort hints — as the
     most immediately available mechanism. Graduate to (b) when Claude Code
     exposes the flag.

3. **Lane pool sizing for mixed fleet?**
   - Current: ~8 author lanes all running Opus high
   - With mixed fleet: how many lanes per model tier?
   - **Recommendation:** Start with 2 Opus (complex), 4 Sonnet (standard),
     2 Haiku (economy). Tune based on task mix data from overnight runs.

4. **Cost budget enforcement?**
   - Alert-only vs. hard-stop when per-tier budget exceeded?
   - **Recommendation:** Alert-only at MVP. Hard stops risk mid-task
     interruption. Add soft-stop (no new dispatches to tier) as a follow-up.

## File Scope (estimated)

| File | Status | Lines | Notes |
|------|--------|-------|-------|
| `src/bid_euchre/ops/model_routing.py` | NEW | ~250 | Model + effort routing, tier defs, cost rates |
| `src/bid_euchre/ops/fleet_dashboard.py` | NEW | ~300 | Live dashboard (TUI or HTML, per Q1 decision) |
| `src/bid_euchre/ops/task_queue.py` | MODIFY | ~30 | model_hint, effort_hint fields |
| `src/bid_euchre/ops/worker_pool.py` | MODIFY | ~60 | Model-aware dispatch, effort passthrough |
| `src/bid_euchre/ops/token_economy.py` | MODIFY | ~80 | 3-dimensional tracking (lane×model×effort) |
| `src/bid_euchre/ops/supervisor.py` | MODIFY | ~30 | Service-lane health classification |
| `src/bid_euchre/ops/review_queue.py` | MODIFY | ~30 | Codex service lane integration |
| `.claude/tmux/steward-session.sh` | MODIFY | ~25 | Per-pane model + effort config |
| `tests/unit/test_ops_model_routing.py` | NEW | ~250 | Routing logic, effort mapping, cost estimation |
| `tests/unit/test_ops_fleet_dashboard.py` | NEW | ~150 | Dashboard rendering, data aggregation |
| `tests/unit/test_ops_worker_pool.py` | MODIFY | ~50 | Model-aware dispatch tests |
| `tests/integration/test_codex_service_lane.py` | NEW | ~150 | Codex lane health, circuit breaker |

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
| Model routing core + effort tier definitions | 1 | 2h | `model_routing.py`, cost rates, effort mapping |
| TaskPacket extensions (model_hint + effort_hint) | 1 | 1h | Schema changes, backward compat |
| Worker pool model-aware dispatch | 1 | 1.5h | Matching logic, effort passthrough, fallback timeout |
| Token economy 3-dimensional tracking | 1 | 2h | Lane×model×effort accounting, cost estimation |
| Live fleet dashboard | 2 | 3h | Dashboard views, data aggregation, real-time updates |
| Codex service lane | 2 | 3h | Review queue integration, health signals, circuit breaker |
| Session launcher model + effort config | 1 | 1h | `steward-session.sh` per-pane model flags |
| **Total** | **~9 PRs** | **~13.5h** | |

> The dashboard adds ~2 PRs and ~3h vs. the original estimate. The 3-dimensional
> tracking adds ~1h to the token economy slice. Total scope increase is moderate
> and justified by the visibility gains.

## Risks

1. **Claude Code model switching limitation.** Model is fixed at session start.
   Cannot dynamically switch mid-session. This means model-tier lanes must be
   pre-allocated, not on-demand. Mitigation: explicit lane-model assignment in
   session launcher. This is a known simplification, not a bug.

2. **Reasoning effort API uncertainty.** Claude Code may not yet expose a
   `--reasoning-effort` flag or per-prompt effort control. The prompt-level
   hint fallback ("respond at medium effort") may not reliably change model
   behavior. Mitigation: start with prompt-level hints, measure actual token
   usage difference, graduate to API flag when available.

3. **Codex service lane reliability.** Codex CLI already has ~10% failure rate
   in current review loop. Wrapping it as a service lane doesn't fix the
   underlying reliability. Mitigation: circuit breaker + explicit degraded
   state + fallback path.

4. **Cost runaway.** Opus at high effort burns tokens 5x faster than Sonnet.
   An overnight run with 4 Opus-high lanes could exceed budget. Mitigation:
   per-tier token budget in token economy. Alert when premium tier exceeds
   configurable threshold. The 3-dimensional tracking makes this visible.

5. **Effort estimation accuracy.** Orchestrator must estimate both task
   complexity (→ model) and reasoning depth needed (→ effort) at dispatch time,
   before seeing the code. Two estimation axes compound the mismatch risk.
   Mitigation: mismatch warning in worker pool + learning loop feedback
   (Platform-11).

6. **Lane pool fragmentation.** With 3 model tiers, each tier has fewer
   available lanes. A premium task may wait even though economy lanes are idle.
   Mitigation: configurable fallback timeout (default 10min) before degrading to
   any available lane.

7. **Dashboard maintenance burden.** A live dashboard is a new surface area to
   maintain. Stale or broken dashboards erode trust. Mitigation: keep the first
   version simple (read-only views of existing data), iterate based on usage.

8. **Cost estimate accuracy.** Token costs depend on input+output token counts,
   which vary per task. Even crude per-model multipliers may be off by 2-3x for
   individual tasks. Mitigation: operator accepts crude estimates are better
   than nothing. Refine multipliers from actual usage data over time.

---

## Operator Feedback Changelog

### Round 1 (2026-03-25)

Eight points incorporated from operator review:

| # | Feedback | Impact |
|---|----------|--------|
| 1 | Baseline is Opus high (not Sonnet) | Rewrote Problem Statement to reflect actual fleet state |
| 2 | Reasoning effort is a key separate axis | Added two-axis model (Model × Effort), restructured architecture |
| 3 | Live dashboard required | Added Live Dashboard section, +2 PRs in estimate |
| 4 | Per-lane model, per-task effort | Split config into Axis 1 (per-lane) and Axis 2 (per-task) sections |
| 5 | 3-dimensional cost tracking (lane×model×effort) | Rewrote Token Economy section with full attribution model |
| 6 | Launch-flag routing only (no API changes) | Noted explicitly in Model Configuration — simplifies scope |
| 7 | Codex local CLI as model option | Added to MVP model table |
| 8 | MVP: Opus (3 efforts), Sonnet (fixed), Haiku (fixed) | Set in MVP models table, resolved open question #6 |

**Conflicts/tensions identified:** None. All 8 points are additive and
internally consistent. The reasoning effort axis adds scope (dashboard, effort
routing) but the launch-flag-only constraint keeps the implementation grounded.
