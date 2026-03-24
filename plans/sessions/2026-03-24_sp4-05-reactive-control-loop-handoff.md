# Session Handoff — SP-4-05 Reactive Control-Loop Hardening

**Date:** 2026-03-24
**Status:** READY TO DISPATCH
**Primary owner:** orchestrator
**Parent sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`

---

## Executive Summary

The next platform priority is not more transport work. It is local lifecycle
reactivity.

The platform can execute work, but throughput is currently limited by a weak
control loop:

- merged PRs are not always turned into strong next-action signals
- monitor findings are too coarse for autonomous orchestration
- PR linkage to task packets is too soft
- inbox noise hides actionable state
- the ops monitor loop is not yet persistent enough to be trusted

This handoff establishes `SP-4-05` as the governing implementation slice for
those gaps.

## Key Decisions

### 1. Control-loop diagnosis

Treat this as a **local lifecycle control-plane** problem, not a pure
message-bus delivery bug.

Target architecture:

- hooks = low-latency hints
- monitor/reconciler = routine lifecycle truth
- inbox/dashboard/Telegram = projections
- loud alerts = exceptions only

### 2. `cmux` decision

`cmux` is **not** a required dependency for the steward platform at this stage.

- current repo usage is placeholder metadata only
- current user-level `cmux` hooks are producing tmux-pane noise and possible
  refresh instability
- do not deepen `cmux` integration in Phase 4
- immediate fix: bypass/disable `cmux` hooks for steward sessions
- future revisit only if a clear operator-UX value case appears after the local
  control loop is stable

### 3. Phase placement

This work is now the primary **Pre-Platform-8** control-plane slice.

- Telegram host/plugin preflight can continue in parallel
- remote proving must not claim away-from-desk reliability until `SP-4-05`
  passes a local proving run

## Issues Covered

### Should be directly addressed by this sequence

- `#1469` — actionable monitor alerts
- `#1482` — monitor dies after one cycle
- `#1463` — inbox hygiene / review verdict dedupe
- `#1478` — extract shared completion logic in `post-merge-notify.sh`
- `#1479` — fix branch-number parsing / sentinel edge cases
- `#1485` — skip `cmux` hooks for steward tmux panes

### Should be partially resolved or reframed

- `#1461` — do not treat as a standalone shared-bus bug unless direct local
  merge delivery is still broken after helper unification
- `#1488` — practical resolution is “steward is `cmux`-agnostic by default”;
  deeper `cmux` integration is explicitly deferred

### Explicitly out of scope for this sequence

- `#1324` — remote audit trail
- `#1289` — transport consolidation
- `#1288` — comment-ingestion bridge activation
- `#1337` — live dashboard UX

## PR Roadmap

### PR 0 — Steward `cmux` guardrails

**Goal:** Stop user-level `cmux` hooks from polluting or destabilizing steward panes.

**Implementation:**
- patch user-level `~/.claude/hooks/cmux-notify.sh` or equivalent host hook
- detect steward tmux sessions early
- exit silently for steward sessions
- do not add repo-side `cmux` integration work beyond docs/policy

**Close when:**
- no more `Tab not found` / `TabManager not available` noise in steward panes
- `#1485` can close
- `#1488` can remain open only if you want a future revisit issue

### PR 1 — Lifecycle source of truth

**Goal:** Make packet -> PR linkage and merge completion trustworthy.

**Implementation:**
- extract shared completion logic from `.claude/hooks/post-merge-notify.sh`
- fix branch-digit parsing and sentinel semantics
- guarantee packet metadata captures:
  - `pr_number`
  - branch
  - head SHA
  - lane
- route both hook fast path and monitor fallback through the same helper

**Likely files:**
- `.claude/hooks/post-merge-notify.sh`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/task_queue.py`
- `src/bid_euchre/ops/message_bus.py`
- targeted unit tests

**Issues:** `#1478`, `#1479`, substantive part of `#1461`

### PR 2 — Monitor becomes typed lifecycle reconciler

**Goal:** Make routine state transitions machine-actionable.

**Implementation:**
- extend `src/bid_euchre/ops/monitor.py` to emit typed lifecycle findings:
  - `packet_completed`
  - `lane_freed`
  - `pr_ready`
  - `stale_packet`
  - `stall_warning`
  - `stall_escalated`
- make merged-dispatch completion emit a specific actionable finding
- make the ops loop persistent or self-restarting enough to survive real use
- keep HIGH escalation for exceptions only

**Likely files:**
- `src/bid_euchre/ops/monitor.py`
- `scripts/internal/ops.py`
- `.claude/agents/steward-ops.md`
- `.claude/agents/steward-orchestrator.md`
- tests for monitor behavior

**Issues:** `#1469`, `#1482`

### PR 3 — Actionable operator surface

**Goal:** Make operator reads cheap and high-signal.

**Implementation:**
- dedupe review-verdict notifications semantically at sender side
- compact handled orchestrator inbox records under a clear policy
- narrow default orchestrator-facing reads to actionable lifecycle state
- expose a small “next actions” / actionable-lifecycle view if practical

**Likely files:**
- `src/bid_euchre/ops/review_queue.py`
- `src/bid_euchre/ops/message_bus.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/status.py` or dashboard/status module

**Issues:** `#1463`

## Ordering Rules

1. Land PR 0 first if steward panes are still noisy or blanking during refresh.
2. Land PR 1 before PR 2 so the monitor can trust packet/PR linkage.
3. Land PR 2 before PR 3 if there is any conflict over actionable event shape.
4. Do not broaden into Telegram proving in the middle of this sequence unless
   the host-side preflight is entirely independent.

## Validation

### Required proving run after PR 2 or PR 3

Run one small dispatch cycle and prove both:

1. local `gh pr merge`
2. GitHub auto-merge / server-side merge

For both, verify:

- packet transitions from `dispatched` to `completed`
- lane becomes available/freed
- the orchestrator gets a strong actionable lifecycle signal
- no manual `gh pr list --state merged` polling is needed

Also verify stall handling:

- first detection re-nudges
- second detection escalates

### Commands

```bash
uv run python scripts/internal/ops.py --json status
uv run python scripts/internal/ops.py --json dashboard
uv run pytest -q tests/unit/test_ops_monitor.py
```

Add targeted lifecycle-helper and message-dedupe tests as needed.

## Issue Handling Guidance

- Close `#1485` once steward panes are demonstrably quiet with `cmux` hooks present.
- Close `#1478` and `#1479` with PR 1.
- Close `#1469` and `#1482` with PR 2 after proving.
- Close or narrow `#1463` with PR 3 depending on whether any separate cleanup
  issue remains.
- Do **not** reopen `#1461` unless the direct local merge hook path still fails
  after PR 1.
- Keep `#1488` open only if you intentionally want a future “reassess `cmux`
  value” reminder; otherwise close it as “defer indefinitely / not part of
  current steward architecture.”

## Files Already Updated

The planning docs already reflect this decision:

- `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`
- `plans/agent_ops/4_remote_channel/plan.md`
- `plans/agent_ops/4_remote_channel/checkpoints.md`
- `plans/agent_ops/sub_plan_registry.md`
- `plans/agent_ops/governing_plan.md`

## Operator Note

Do not treat `cmux` as a hidden dependency during implementation. The current
platform should behave correctly in plain steward tmux sessions without any
`cmux` support. If `cmux` remains installed on the host, it must be inert unless
explicitly invoked for a later approved UX/presentation experiment.
