# Token Economy Optimization — Deep Analysis

**Date:** 2026-04-03
**Issue:** #2159
**Task Packet:** 7ae5cf90a529
**Lane:** analyst-c

## Executive Summary

This analysis investigates token economy optimization opportunities for the
steward fleet, prompted by Anthropic engineering tips. The fleet currently runs
**all lanes on Opus 4.6** with no model tiering, no effort tuning, and no
compact window configuration. Based on telemetry from 1,223 sessions across
19 lanes (729 MB of JSONL data), we identify 4 high-impact optimization levers
that can reduce effective token burn by an estimated 30–50% without degrading
output quality.

---

## 1. Current State Audit

### 1.1 Token Consumption by Lane Pool

Data source: `~/.claude/projects/*steward*/*.jsonl` (1,223 sessions)

| Pool | Sessions | Avg Output/Session (K) | Avg Cache Read/Session (M) | Avg Duration (min) | Commits | Output/Commit (K) |
|------|----------|----------------------|--------------------------|-------------------|---------|-------------------|
| **Author** (4 lanes) | 520 | 16.7 | 8.1 | 65.8 | 877 | 9.9 |
| **Browser** (4 lanes) | 279 | 10.2 | 4.0 | 28.8 | 266 | 10.7 |
| **Analyst** (4 lanes) | 56 | 13.1 | 4.0 | 38.3 | 34 | 21.6 |
| **Flex** (4 lanes) | 144 | 9.5 | 4.0 | 38.6 | 142 | 9.7 |
| **Control** (ops+review) | 142 | 13.5 | 6.5 | 103.9 | 0 | N/A |

**Key observations:**

- **Cache read dominates input**: 7,362M cache read tokens vs 0.7M fresh input
  tokens. On Claude Pro, cache reads are heavily discounted (90% cheaper than
  fresh input). This means caching is already working well.
- **Review lane is the #2 consumer**: 153 MB of JSONL, 126 sessions — nearly
  as much as author-a (157 MB). Review runs Codex CLI + iterative auto-fix
  loops, which are verbose.
- **Author lanes produce the most output per session** (16.7K avg), but have
  the best efficiency per commit (9.9K output tokens per commit).
- **Analyst lanes have 2× worse token-per-commit ratio** (21.6K) because
  their work is primarily reading + writing analysis reports, not code commits.
- **Control plane (ops/review) produces zero commits** but burns substantial
  tokens on monitoring, status checks, and review iterations.

### 1.2 Model Usage

Sampled from recent JSONL across all project directories:

| Model | Messages |
|-------|----------|
| `claude-opus-4-6` | 3,878 |
| `claude-sonnet-4-6` | 416 |
| `claude-sonnet-4-5-20250929` | 255 |
| `<synthetic>` | 11 |

**Finding:** 85% of all messages use Opus 4.6. The small Sonnet usage appears
to be from manual ad-hoc sessions, not from any fleet policy. There is **no
model selection policy** — every lane defaults to Opus.

### 1.3 Session Lifecycle

- **Dispatch mechanism**: `dispatch_to_worker()` sends `/clear` via tmux, then
  nudges with `/start-task <packet_id>`. No model or effort flags are injected.
- **Compact window**: `CLAUDE_CODE_AUTO_COMPACT_WINDOW` is **not set anywhere**
  in the codebase or environment. The default Claude Code behavior applies
  (compact at ~80% of context window).
- **Session cleanup**: `/clear` is sent before dispatch, which resets the
  session. No auto-compact on idle.
- **No `--effort` or `--model` flags** are passed during session start or
  dispatch.

### 1.4 Existing Infrastructure

The `token_economy.py` module (PR #1808 and followups) provides:
- Import from both legacy session-meta and project JSONL formats
- Lane attribution via worktree path inference
- Usage summary, lane summary, throughput metrics
- Anti-pattern detection (verbosity waste, high tool error rate)
- Dashboard-ready aggregation

This is well-built but **not yet wired into the operational loop** — no
periodic import, no dashboard display, no alerting on waste patterns.

---

## 2. Model Assignment Policy

### 2.1 Task Type Classification

Claude Code supports `--model sonnet` and `--model opus` per session. The
`--fallback-model` flag enables auto-fallback when the primary model is
overloaded (but only works with `--print` mode currently).

**Recommended model assignment by task type:**

| Task Type | Examples | Recommended Model | Rationale |
|-----------|----------|------------------|-----------|
| **Multi-file features** | New strategy, new module, architectural work | **Opus** | Needs full codebase reasoning, cross-file coherence |
| **Complex bugfixes** | Race conditions, state machine bugs, edge cases | **Opus** | Needs deep analysis and careful reasoning |
| **Governing plan work** | Plan steps with design choices, sub-plan creation | **Opus** | Requires architectural judgment |
| **Single-file bugfixes** | Convention fixes, typo fixes, simple logic | **Sonnet** | Pattern-matching task, well-scoped |
| **Test-only PRs** | Adding missing test coverage, test refactors | **Sonnet** | Structured, repetitive work |
| **Docs-only PRs** | README updates, plan updates, checkpoint reconciliation | **Sonnet** | Low complexity, mostly text generation |
| **Review lane** | Precheck + Codex CLI coordination | **Sonnet** | Orchestration logic, not deep reasoning |
| **Ops lane** | Status monitoring, dispatch, cron management | **Sonnet** | Structured operational checks |
| **Analyst shaping** | Investigation, reading + writing analysis | **Opus** | Needs deep reasoning for complex analysis |
| **Analyst reports** | Formatting, issue filing, plan writing | **Sonnet** | Template-driven, low ambiguity |

### 2.2 Implementation Path

**Where to inject model selection:**

1. **Task packet metadata**: Add a `model_hint` field to `TaskPacket` in
   `task_queue.py`. The orchestrator sets this based on task complexity at
   dispatch time.

2. **Dispatch mechanism**: Modify `dispatch_to_worker()` in `worker_pool.py`
   to inject `--model <hint>` into the tmux pane environment before nudging.
   Options:
   - Set `CLAUDE_MODEL` env var before sending `/start-task` (if supported)
   - Send `claude --model <model> --continue` as the session start command
   - Configure per-lane defaults in a new `fleet_config.yaml`

3. **Lane-level defaults**: Add a `DEFAULT_MODEL` mapping in `worker_pool.py`
   alongside the existing `LANE_DOMAINS`:

   ```python
   LANE_MODELS: dict[str, str] = {
       # Control plane — always Sonnet (orchestration, not reasoning)
       "ops": "sonnet",
       "review": "sonnet",
       # Author lanes — Opus by default, overridable per-task
       "author-a": "opus",
       "author-b": "opus",
       ...
       # Analyst lanes — Opus for shaping, Sonnet for reporting
       "analyst-a": "opus",
       ...
   }
   ```

4. **Override chain**: Task packet `model_hint` > lane default > fleet default
   (Opus). This lets the orchestrator override lane defaults for specific tasks.

### 2.3 Estimated Impact

If we move review + ops to Sonnet (142 sessions, ~13.5K output each) and
use Sonnet for ~30% of author/browser tasks (single-file fixes, docs, tests):

- **Control plane savings**: ~142 × 13.5K × Opus-to-Sonnet cost ratio
- **Author/browser savings**: ~240 × 12K × Opus-to-Sonnet cost ratio
- **Estimated total**: 25–35% reduction in effective output token cost

On Claude Pro (subscription), the cost model is different — it's about rate
limits and throughput capacity rather than per-token cost. Using Sonnet for
simpler tasks **frees Opus capacity** for the lanes that need it.

---

## 3. Effort Level Tuning

### 3.1 Current State

Claude Code supports `--effort <level>` with values: `low`, `medium`, `high`,
`max`. No effort level is currently configured for any lane.

- **`low`**: Minimal reasoning, fast responses. Good for simple lookups and
  template-driven tasks.
- **`medium`**: Balanced reasoning. Good for most single-file edits.
- **`high`** (default): Full reasoning. Current implicit default.
- **`max`**: Extended thinking enabled. Good for complex architectural
  decisions.

### 3.2 Recommended Effort by Task Type

| Task Type | Effort | Rationale |
|-----------|--------|-----------|
| Docs/plan-only PRs | `medium` | Low complexity, mostly text |
| Single-file convention fixes | `medium` | Pattern-matching |
| Test-only PRs | `medium` | Structured, repetitive |
| Multi-file features | `high` | Needs cross-file reasoning |
| Complex bugfixes | `high` or `max` | Needs deep analysis |
| Ops monitoring/dispatch | `medium` | Operational checks |
| Review coordination | `medium` | Orchestration logic |
| Analyst investigation | `high` | Deep reading + synthesis |

### 3.3 Implementation Path

The `--effort` flag is a session-level setting. Options:

1. **Task packet field**: Add `effort_hint` alongside `model_hint`. The
   dispatch mechanism injects it into the session start command.
2. **Lane defaults**: Set per-lane effort in `LANE_EFFORT` mapping.
3. **Environment variable**: Check if Claude Code supports an `CLAUDE_EFFORT`
   env var (not documented — needs verification).

### 3.4 Estimated Impact

Effort tuning primarily affects **output token volume** and **response latency**.
Lower effort = fewer reasoning tokens = faster responses. For `medium` effort:
- ~20–30% fewer output tokens per response
- ~30–40% faster response times
- Applied to ~40% of tasks → ~8–12% total output token reduction

---

## 4. Compact Strategy

### 4.1 Current State

- `CLAUDE_CODE_AUTO_COMPACT_WINDOW` is **not set** anywhere.
- The Claude Code default behavior compacts at ~80% of the context window.
- The `compact-context.sh` hook re-injects 7 critical constraints after
  compaction.
- No auto-compact on idle.

### 4.2 Recommendations

**4.2a — Set explicit compact window:**

```bash
export CLAUDE_CODE_AUTO_COMPACT_WINDOW=60
```

This triggers compaction at 60% of context window instead of the default ~80%.
Benefits:
- Earlier compaction preserves more room for fresh context
- Reduces the risk of silent agent death from context exhaustion
  (`.claude/rules/70_agent_reliability.md` warns about this)
- Particularly valuable for long-running control plane sessions

**4.2b — Per-pool compact strategy:**

| Pool | Recommended Window | Rationale |
|------|-------------------|-----------|
| Author lanes | 60% | Sessions are bounded (one task), moderate length |
| Browser lanes | 60% | Similar to author — bounded tasks |
| Analyst lanes | 50% | Analyst sessions read many large files |
| Control (ops) | 40% | Long-running sessions, must stay responsive |
| Control (review) | 50% | Iterative review loops accumulate context |

**4.2c — Compact on idle:**

Currently, idle lanes sit with potentially large context windows. Add a
mechanism in `worker_pool.py` to send `/compact` to idle lanes after N minutes
of inactivity. This reduces the context size before the next task dispatch,
improving startup performance.

### 4.3 Implementation Path

1. Set `CLAUDE_CODE_AUTO_COMPACT_WINDOW` in the tmux session environment or
   per-pane via `tmux set-environment`.
2. Add compact-on-idle to `run_pool_maintenance()` in `worker_pool.py`.
3. Consider adding compact window to the `fleet_config.yaml` proposed in §2.2.

---

## 5. Session Lifecycle Optimization

### 5.1 `/clear` vs Fresh Session vs Resume

Current approach: `/clear` before each dispatch. This is correct — it
fully resets the context window while keeping the Claude Code process alive.

**Assessment:**
- `/clear` is sufficient and appropriate. Starting a fresh `claude` process
  would be slower (process startup, workspace initialization) with no benefit.
- `--continue` / `--resume` should NOT be used for new tasks — it would carry
  stale context from the previous task.

### 5.2 Cost of Stale Sessions

Long-running sessions (particularly ops at 103.9 min average) accumulate
large context windows. Each message in a long session re-sends the full
context, burning cache-read tokens even though much of the context is
irrelevant to the current action.

**Recommendation:** For control plane lanes, send `/compact` every 30 minutes
during active monitoring cycles. This can be wired into the existing cron
check-in mechanism.

### 5.3 Idle Lane Auto-Compact

When a lane completes a task and enters idle state (before the next dispatch):

1. Wait 2 minutes (let final tool calls complete)
2. Send `/compact` to the pane
3. This pre-shrinks context so the next `/start-task` begins with a clean
   window

Wire this into the `park_worker()` or `run_pool_maintenance()` flow.

---

## 6. Integration with Rate-Limit Handling (#1947)

### 6.1 Synergy with Model Selection

Model tiering directly addresses the rate-limit problem from #1947:

- **Opus rate limits** are typically tighter than Sonnet. Moving simpler tasks
  to Sonnet distributes load across two model rate limit pools.
- **`--fallback-model sonnet`** can be used for Opus sessions to auto-fallback
  when Opus is rate-limited. However, this currently only works with `--print`
  mode, not interactive sessions.
- **Subscription rotation** (#1947) combined with model tiering means:
  - Subscription A → Opus lanes (author-a, author-b, analyst-a)
  - Subscription B → Sonnet lanes (review, ops, flex)
  - This doubles effective rate limit headroom.

### 6.2 Implementation Ordering

1. **Model tiering first** — reduces Opus demand, partially mitigates rate
   limit pressure without infrastructure changes.
2. **Rate-limit detection second** — wire 429/retry-after detection into
   `monitor.py` and surface via inbox to orchestrator.
3. **Subscription rotation third** — requires credential management
   infrastructure.

---

## 7. Actionable Recommendations

### Priority 1 — Immediate (1–2 PRs, high impact)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| R1 | Set `CLAUDE_CODE_AUTO_COMPACT_WINDOW=60` in tmux session env | Prevent context exhaustion, improve long-session stability | Trivial — one `tmux set-environment` call |
| R2 | Move review + ops lanes to `--model sonnet` | Free Opus capacity for author work | Small — modify lane startup in session script |

### Priority 2 — Near-term (2–3 PRs, medium impact)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| R3 | Add `model_hint` and `effort_hint` to `TaskPacket` | Enable per-task model/effort selection | Small — add fields + dispatch wiring |
| R4 | Add compact-on-idle to `run_pool_maintenance()` | Reduce stale context waste | Small — send `/compact` to idle panes |
| R5 | Wire token economy import into periodic cron | Enable ongoing usage monitoring | Small — add cron job for `import_project_jsonl` |

### Priority 3 — Strategic (3–5 PRs, requires design)

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| R6 | Create `fleet_config.yaml` for centralized fleet config | Single source of truth for model, effort, compact per lane | Medium — new config format + loader |
| R7 | Add `--effort medium` for simple task types | Reduce output tokens by ~10% | Medium — task complexity classifier |
| R8 | Auto-fallback on rate limit (Claude Code `--fallback-model`) | Graceful degradation under load | Medium — needs `--print` mode investigation |
| R9 | Periodic token economy dashboard in check-in cron | Surface waste patterns to orchestrator | Medium — wire dashboard_token_economy into ops |

---

## 8. PR Decomposition

### PR-1: Fleet compact window configuration
- **Files**: Session startup script, `.claude/hooks/compact-context.sh`
- **Scope**: Set `CLAUDE_CODE_AUTO_COMPACT_WINDOW=60` for all panes
- **Validation**: Verify compaction triggers earlier in long sessions

### PR-2: Model tiering for control plane lanes
- **Files**: `src/bid_euchre/ops/worker_pool.py`, session startup
- **Scope**: Add `LANE_MODELS` mapping, inject `--model` at dispatch
- **Validation**: Verify review/ops lanes use Sonnet, author lanes use Opus

### PR-3: Task packet model/effort hints
- **Files**: `src/bid_euchre/ops/task_queue.py`, `worker_pool.py`
- **Scope**: Add `model_hint` and `effort_hint` fields, wire into dispatch
- **Validation**: Dispatch with model hint, verify JSONL shows correct model

### PR-4: Compact-on-idle maintenance
- **Files**: `src/bid_euchre/ops/worker_pool.py`
- **Scope**: Add compact step to `park_worker()` / `run_pool_maintenance()`
- **Validation**: Verify idle lanes receive `/compact` before next dispatch

### PR-5: Periodic token economy import + dashboard
- **Files**: `src/bid_euchre/ops/token_economy.py`, check-in skill
- **Scope**: Wire `import_project_jsonl` into periodic cron, add dashboard
  section to check-in output
- **Validation**: `uv run python -c "from bid_euchre.ops.token_economy import import_project_jsonl; print(import_project_jsonl())"`

---

## 9. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Sonnet produces lower-quality code for complex tasks | High | Only use Sonnet for well-scoped simple tasks; keep Opus as default for author lanes |
| `--effort medium` causes missed edge cases | Medium | Start with docs/test-only tasks; measure error rates before expanding |
| Compact window too aggressive → loses critical context | Medium | `compact-context.sh` hook re-injects 7 critical constraints; test with 60% before going lower |
| Model hint ignored by Claude Code | Low | Verify via JSONL model field after dispatch |
| Rate limit rotation complicates credential management | Medium | Defer to #1947; model tiering alone may suffice |

---

## 10. Validation Plan

After implementing the recommendations:

1. **Baseline capture**: Run `import_project_jsonl(force=True)` to get current
   state.
2. **Post-change monitoring**: After 1 fleet run (~50 sessions), re-import and
   compare:
   - Output tokens per session (should decrease ~20% for Sonnet lanes)
   - Cache read tokens per session (should decrease with earlier compaction)
   - Session duration (should be similar or shorter)
   - Commit count per session (should be unchanged — quality gate)
   - Model distribution (should show Sonnet for review/ops/simple tasks)
3. **Quality gate**: If commit-per-session drops or error rates increase on
   Sonnet lanes, revert to Opus for those lanes.

---

## Outcome

_To be filled after implementation._

---

## Appendix: Raw Telemetry Summary

**Total across all steward lanes:**
- 1,223 sessions
- 729 MB of JSONL data
- 7,362.6M cache read tokens
- 268.5M cache creation tokens
- 16.4M output tokens
- 0.7M fresh input tokens

**Per-lane breakdown (top 5 by JSONL size):**
- author-a: 159 sessions, 157 MB
- review: 126 sessions, 153 MB
- author-b: 135 sessions, 152 MB
- author-c: 105 sessions, 102 MB
- author-d: 121 sessions, 97 MB

**Models observed:**
- claude-opus-4-6: 3,878 messages (85%)
- claude-sonnet-4-6: 416 messages (9%)
- claude-sonnet-4-5-20250929: 255 messages (6%)

**Environment:**
- No `CLAUDE_MODEL`, `ANTHROPIC_MODEL`, or `CLAUDE_EFFORT` env vars set
- No `CLAUDE_CODE_AUTO_COMPACT_WINDOW` configured
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set
- Claude Code `--model` and `--effort` flags are available per-session
