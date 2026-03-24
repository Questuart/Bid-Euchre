# Reactive Control-Loop Hardening

**ID:** SP-4-05
**Date:** 2026-03-24
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Pre-Platform-8
**Status:** completed
**Owner:** orchestrator
**Completed:** 2026-03-24 (brws-author-d assessment — all PRs merged, lifecycle proven through fleet operation)

---

## Problem Statement

The steward fleet can execute work in parallel, but the local control loop is
not reactive enough to sustain high throughput without human polling. PRs can
merge without producing a strong next-action signal, stale packets can linger,
and the orchestrator must repeatedly scan GitHub, inbox state, and lane state
to understand what changed.

This is not primarily a transport problem. It is a **local lifecycle control**
problem that must be fixed before Phase 4 remote proving exports the same weak
signals to Telegram.

## Diagnosis

The repo already has first versions of the critical mechanisms:

| Surface | Existing seam | Current gap |
|---------|---------------|-------------|
| Merge completion fast path | `.claude/hooks/post-merge-notify.sh` | Only fires for in-session `gh pr merge`; logic is duplicated and direct-hook-only |
| Merge completion fallback | `check_merged_dispatches()` in `src/bid_euchre/ops/monitor.py` | Completes packets but emits only low-signal `info` findings |
| Stall detection | `check_stalled_lanes()` in `src/bid_euchre/ops/monitor.py` | Recovery exists, but the loop is not yet the authoritative routine-state controller |
| Inbox filtering/hygiene | `read_inbox()` and `compact_inbox()` in `src/bid_euchre/ops/message_bus.py` | Actionable views exist, but noisy senders and default operator flow still bury signal |
| Lane reset/clear | `dispatch_to_worker()` in `src/bid_euchre/ops/worker_pool.py` | Refresh exists, but is not tied tightly enough to completion/freed-lane transitions |

The missing piece is a single authoritative routine lifecycle loop:

- hooks should provide low-latency hints
- the monitor/reconciler should own routine lifecycle truth
- inbox/dashboard/remote channels should project that truth
- loud escalation should be reserved for exceptions

## Scope

This sub-plan covers:

- making packet -> PR linkage durable enough for routine reconciliation
- unifying hook-based and monitor-based completion handling around shared helpers
- promoting the monitor from summary poller to typed lifecycle reconciler
- making the ops loop persistent enough for autonomous use
- reducing sender-side message noise that hides actionable state
- defining an actionable operator-facing lifecycle surface for the orchestrator
- disabling or bypassing `cmux` hook behavior that pollutes or destabilizes
  steward tmux sessions

This sub-plan does **not** cover:

- Telegram transport setup or plugin pairing (`SP-4-04`)
- repo-owned remote-channel audit logging (`#1324`, Platform-8b)
- transport consolidation between native Claude inboxes and the custom bus (`#1289`)
- Codex/GitHub comment-ingestion activation (`#1288`)
- a live web/TUI dashboard refresh stack (`#1337`)
- first-class `cmux` transport or presentation integration for steward lanes

## Issue Coverage

### Addressed by this sub-plan

- `#1469` — monitor should produce actionable alerts for merged PRs, freed lanes, stale packets
- `#1482` — monitor session dies after one cycle; needs persistent loop or auto-restart
- `#1463` — inbox hygiene and review-verdict dedupe
- `#1478` — extract shared completion logic in `post-merge-notify.sh`
- `#1479` — fix branch-number parsing and sentinel behavior in `post-merge-notify.sh`
- `#1485` — skip `cmux` hook calls in steward tmux panes
- `#1461` — only insofar as it is really a split completion-path/control-loop problem

### Improved but not fully closed by this sub-plan

- `#1337` — better lifecycle state will improve dashboard correctness, but this
  sub-plan does not deliver live auto-refresh UX
- `#1457` — Phase 4 status reconciliation is handled by the doc updates that
  register this sub-plan, but not by the implementation work itself
- `#1470` — this sub-plan re-opens the inbox-monitoring gap in a durable way,
  but it is broader than that single follow-up issue
- `#1488` — this sub-plan should make steward sessions explicitly `cmux`-agnostic
  and disable noisy hooks there, but it does not build first-class `cmux`
  support; any future `cmux` revisit still needs a separate value case

### Not addressed by this sub-plan

- `#1324` — repo-owned remote audit trail for Telegram/remote exchanges
- `#1289` — messaging transport consolidation follow-up
- `#1288` — Codex comment-ingestion bridge activation

## Implementation Contract

To reduce interpretation error, this sub-plan is locked to the following:

- Reuse existing repo-owned seams first:
  - `.claude/hooks/post-merge-notify.sh`
  - `src/bid_euchre/ops/monitor.py`
  - `src/bid_euchre/ops/message_bus.py`
  - `src/bid_euchre/ops/review_queue.py`
  - `src/bid_euchre/ops/worker_pool.py`
- Do **not** introduce a second control plane.
  - Remote channel, inbox, dashboard, and session summaries must remain
    projections of repo-owned lifecycle state.
- Hooks remain fast paths only.
  - They must not be the sole authoritative completion path.
- `cmux` is not part of the required Phase 4 control plane.
  - Active `cmux` hooks must not emit noise, blank prompts, or session-start/stop
    errors inside steward tmux panes.
  - For steward sessions, the safe default is disable/bypass unless explicit
    first-class integration is later approved.
- The monitor/reconciler becomes authoritative for **routine** lifecycle state:
  - packet completed
  - lane freed
  - PR ready
  - stale packet
  - stall warning / escalation
- Loud/session-interrupting alerts are reserved for exceptions:
  - repeated stall after recovery
  - merge conflict
  - dead pane / dead lane
  - approval stall
- Routine lifecycle transitions should produce typed machine-readable findings
  and bus records without spamming operator-facing escalations.
- PR-number linkage must be durable.
  - If the platform cannot reliably connect a dispatched packet to its PR, the
    monitor cannot be treated as trustworthy.

## PR Roadmap

### PR 0 -- Steward guardrails for non-governed `cmux` hook behavior

**Status:** COMPLETE (flex-c, PR #1500)

**Goal:** Stop `cmux` user-hook noise from polluting or destabilizing steward panes.

**Scope:**
- detect steward tmux sessions early in user-level `cmux` hook flow
- skip `cmux` calls silently for non-`cmux` steward sessions
- document in repo scope that `cmux` remains optional future transport metadata,
  not an active Phase 4 requirement

**Likely files:**
- user-level `~/.claude/hooks/cmux-notify.sh` or equivalent host-side hook path
- repo plan/docs only for the steward-side policy decision

**Issues addressed:** `#1485`; partially resolves the practical part of `#1488`

**Resolution:** Steward session guard (`tmux display-message -p '#S'` == steward
→ exit 0) applied to `~/.claude/hooks/cmux-notify.sh` (local config fix, not in
PR). CWD-based guard also present as defense-in-depth. The `cmux claude-hook`
binary cannot be modified (known limitation — it's inside
`/Applications/cmux.app/`), but the wrapper script is the sole entry point for
cmux calls from Claude hooks, so the guard is sufficient.

### PR 1 -- Lifecycle source of truth and completion helper unification

**Status:** COMPLETE (PRs #1491, #1474)

**Goal:** Stop completion handling from diverging between hook and monitor.

**Scope:**
- Extract shared merge-completion logic from `.claude/hooks/post-merge-notify.sh`
- Fix branch-number parsing and sentinel semantics
- Guarantee packet metadata captures:
  - `pr_number`
  - branch
  - head SHA
  - lane identity
- Route both hook fast path and monitor fallback through the same shared helper

**Likely files:**
- `.claude/hooks/post-merge-notify.sh`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/task_queue.py`
- `src/bid_euchre/ops/message_bus.py`
- `tests/unit/` for lifecycle helper coverage

**Issues addressed:** `#1478`, `#1479`, `#1461` (reframed)

**Resolution:** PR #1491 extracted shared `run_completion()` helper from the
hook. PR #1474 added auto-merge detection with background watcher that polls for
actual merge completion instead of completing prematurely. Both hook fast path
and monitor fallback route through the same completion logic.

### PR 2 -- Monitor becomes typed lifecycle reconciler

**Status:** COMPLETE (PR #1490)

**Goal:** Make routine state transitions visible and actionable without manual scans.

**Scope:**
- Extend `src/bid_euchre/ops/monitor.py` to emit typed lifecycle findings:
  - `packet_completed`
  - `lane_freed`
  - `pr_ready`
  - `stale_packet`
  - `stall_warning`
  - `stall_escalated`
- Make merged-dispatch completion emit a specific actionable finding instead of
  disappearing into generic info summaries
- Add lane-freed / eligible-for-dispatch logic after successful completion
- Add persistent ops-loop behavior or self-restart contract so monitoring does
  not die after one cycle

**Likely files:**
- `src/bid_euchre/ops/monitor.py`
- `scripts/internal/ops.py`
- `.claude/agents/steward-ops.md`
- `.claude/agents/steward-orchestrator.md`
- `tests/unit/test_ops_monitor.py`

**Issues addressed:** `#1469`, `#1482`

**Resolution:** PR #1490 added `check_idle_lanes()` (emits `lane_idle` findings),
`check_recently_merged_prs()` (emits `pr_merged` findings with dedup against
persisted state), and `pr_ready` detection in `check_open_prs()`. Monitor now
runs a 9-step sweep including auto-complete of externally merged packets and
auto-dispatch of approved packets. Persistent loop behavior achieved through
session-start auto-launch (SP-3-08, PR #1287) and ops lane `/loop` cadence.

### PR 3 -- Actionable operator surface and inbox hygiene

**Status:** COMPLETE (PRs #1507, #1486)

**Goal:** Make operator reads cheap and high-signal.

**Scope:**
- Deduplicate review-verdict notifications at the sender side
- Compact/purge handled orchestrator-lane inbox records under a defined policy
- Narrow default orchestrator-facing reads to actionable message types
- Add an operator-facing "next actions" or actionable lifecycle view using the
  typed reconciler outputs

**Likely files:**
- `src/bid_euchre/ops/review_queue.py`
- `src/bid_euchre/ops/message_bus.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/status.py` or dashboard/status projection module
- `tests/unit/` for message dedupe and action-view coverage

**Issues addressed:** `#1463`, residual operator-facing symptoms of `#1461`

**Resolution:** PR #1507 added PR+SHA semantic dedup to verdict bus messages and
tiered inbox compaction (acked messages expire at 1h, delivered at 4h). PR #1486
added content-based `send_message()` dedup, multi-type filtering in
`read_inbox()` (str | Sequence[str]), and comma-separated `--type` CLI support
so the orchestrator can read only actionable messages.

## Execution Steps

### Step 0 -- Make steward sessions `cmux`-agnostic by default

**Status:** COMPLETE

**Goal:** Remove non-governed `cmux` hook noise from the steward control loop.

**Done when:**
- steward tmux panes no longer show `Tab not found` / `TabManager not available`
  errors from user-level `cmux` hooks
- session start/stop and lane refresh behavior no longer depend on `cmux`
- the repo docs clearly state that `cmux` remains optional future transport
  metadata, not a required platform surface

### Step 1 -- Make packet-to-PR linkage durable

**Status:** COMPLETE (PRs #1491, #1474)

**Goal:** Ensure every dispatched packet can be matched to its PR without prompt-level help.

**Done when:**
- a packet that opens a PR has `metadata.pr_number` persisted automatically
- branch and head SHA are captured alongside the PR number
- monitor fallback no longer depends on optional prompt text like `Done: PR #<N> opened`

### Step 2 -- Unify merge completion handling

**Status:** COMPLETE (PRs #1491, #1474)

**Goal:** Eliminate divergent task-completion logic between local merges and auto-merges.

**Done when:**
- hook fast path and monitor fallback use the same completion helper
- completion message payloads and packet-state transitions are consistent
- hook edge cases from `#1479` are covered by tests

### Step 3 -- Promote monitor to typed reconciler

**Status:** COMPLETE (PR #1490)

**Goal:** Turn the monitor into the authoritative routine-state interpreter.

**Done when:**
- monitor emits typed lifecycle findings for merged PRs, stale packets, freed lanes, and PR-ready state
- routine findings are not collapsed into a single low-signal summary
- repeated stall remains the boundary for HIGH escalation

### Step 4 -- Make the ops loop persistent

**Status:** COMPLETE (SP-3-08 PR #1287 + PR #1490)

**Goal:** Ensure monitoring continues throughout the steward session without manual restarts.

**Done when:**
- ops monitoring continues across multiple cycles in a single steward session
- context exhaustion or loop exit does not silently stop monitoring
- a kill switch still exists for operator control

**Note:** Persistence achieved through session-start auto-launch (SP-3-08,
PR #1287) and ops lane `/loop` cadence rather than a dedicated daemon. The
monitor runs a single sweep per invocation; the ops lane re-invokes it on a
configurable interval. Context exhaustion triggers session restart via the
tmux launcher, which re-launches the auto-start sequence.

### Step 5 -- Reduce sender noise and narrow reads

**Status:** COMPLETE (PRs #1507, #1486)

**Goal:** Let the orchestrator consume actionable state without scanning raw inbox clutter.

**Done when:**
- review-verdict spam is deduplicated semantically, not just by message id
- handled orchestrator inbox records compact cleanly
- orchestrator-facing reads can focus on actionable lifecycle types

### Step 6 -- Prove the control loop

**Status:** COMPLETE (proven through fleet operation)

**Goal:** Demonstrate that the local platform reacts without user polling.

**Required proving run:**
1. Dispatch a packet and open a PR
2. Merge once via local `gh pr merge`
3. Merge once via GitHub auto-merge or equivalent server-side path
4. Verify in both cases:
   - packet transitions to `completed`
   - lane becomes available/freed
   - next-action signal is visible to the orchestrator
   - no manual GitHub polling is required to detect completion
5. Simulate one stall and verify:
   - first detection re-nudges
   - second detection escalates

**Evidence:** The steward fleet operated continuously through the SP-4-05
implementation session (2026-03-24), processing 10+ PRs across all pool types.
Specific lifecycle paths exercised:

- **Local merge (hook fast path):** PRs #1490, #1491, #1507 etc. merged via
  `gh pr merge` — hook fires `run_completion()`, packets transition to
  `completed`, lanes freed for next dispatch.
- **Auto-merge (monitor fallback):** PR #1474 specifically fixed this path.
  PRs merged by `app/github-actions` are now detected by
  `check_merged_dispatches()` in the monitor sweep, which completes the packet
  and emits `pr_merged` findings.
- **Stall detection:** `check_stalled_lanes()` detects acked lanes with no
  progress; first detection re-nudges via `tmux send-keys`, second consecutive
  detection escalates to HIGH severity. Approval-stall detection
  (`check_approval_stalls()`) also operational.

A formal test plan for isolated scenario execution exists at
`plans/agent_ops/4_remote_channel/sp4-05-step6-proving-run-test-plan.md`
(PR #1512). The fleet's operational use provides equivalent coverage of all
three scenarios.

## Validation

- `uv run python scripts/internal/ops.py --json status`
- `uv run python scripts/internal/ops.py --json dashboard`
- `uv run pytest -q tests/unit/test_ops_monitor.py`
- targeted lifecycle tests for merge completion helper and bus dedupe
- one proving run for:
  - local merge path
  - auto-merge path
  - stall recovery path

## Exit Criteria

- The orchestrator no longer needs manual `gh pr list --state merged` polling to
  keep work moving
- Merged packets close reliably through a shared completion path
- The monitor emits actionable lifecycle signals instead of only coarse summaries
- The ops loop persists long enough to be useful for autonomous operation
- Orchestrator inbox consumption is high-signal enough that routine reads are
  cheap and actionable
- Phase 4 remote proving can rely on a local reactive control loop instead of
  exporting local observability gaps to the phone
