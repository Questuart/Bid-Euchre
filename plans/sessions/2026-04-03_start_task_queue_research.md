# Research: Fix Queued /start-task Messages During make check

**Date:** 2026-04-03
**Task Packet:** `bc92a18c7afb`
**Lane:** analyst-c
**Status:** Research complete

## Problem Statement

When the orchestrator dispatches tasks to author lanes via `tmux send-keys`,
messages queue in Claude Code's input buffer if the lane is busy (running
`make check`, mid-implementation, etc.). This causes:

1. **Message stacking** -- Multiple `/start-task` messages queue up
   ("Press up to edit queued messages")
2. **Redundant processing** -- The same task gets started 2-3 times
3. **Wasted context** -- Each redundant `/start-task` consumes tokens
   re-reading the packet, re-running `task accept`, re-reading the plan
4. **Stale queue surprises** -- Lane finishes current work, then processes
   old queued messages sequentially

## Root Cause Analysis

### The Dispatch Flow (Multiple Nudge Sources)

The current system has **three independent paths** that can inject
`/start-task <packet_id>` into a lane's tmux pane:

| Source | When | Code Path |
|--------|------|-----------|
| **1. dispatch_to_worker()** | Initial dispatch | `worker_pool.py:1729` -- calls `nudge_pane()` |
| **2. Stall recovery** | After stall detection (>10min idle) | `monitor.py:1039` -- calls `_do_nudge()` |
| **3. Orchestrator manual** | Operator sends `/start-task` as a nudge | Direct `tmux send-keys` |

Source 1 is the correct initial nudge. Sources 2 and 3 fire when the lane
appears stuck, but they don't check whether a previous nudge is already
queued in the input buffer.

### Claude Code's Input Queue Behavior

Claude Code (the TUI) processes user messages sequentially. When a message
arrives via `tmux send-keys` while Claude is busy:

1. **The text is deposited in the terminal's input buffer** (tmux pane's PTY)
2. **Claude Code's readline-like prompt sees it** but cannot process it
   until the current turn completes
3. **Multiple messages stack** -- Claude Code displays "Press up to edit
   queued messages" in the status bar
4. **Processing is FIFO** -- When the current turn completes, the next
   queued message is automatically submitted
5. **No dedup** -- Identical messages are processed separately

**Key insight:** There is no programmatic way to inspect or clear Claude
Code's message queue from outside. The queue lives inside the Claude Code
process's input handling, not in tmux. `Escape` partially cancels the
current queued message (clears the input line) but does not clear the full
queue.

### Why This Is Worse Than It Sounds

Each redundant `/start-task` invocation:

- Triggers the skill loader (~2-5 seconds)
- Reads the task packet from disk (`ops.py task show`)
- Runs `task accept` (idempotent, but still consumes tokens + tool calls)
- Re-reads the plan or scope documentation
- Sets up branch/scope lock logic (which no-ops if already done)
- **Consumes ~3-8k tokens** of context window per redundant invocation

In a 200k context window, three redundant `/start-task` messages waste
10-25k tokens (5-12% of the window). Over a fleet of 8 lanes across a
6-hour autonomous run, this adds up to significant context waste and
occasionally causes lanes to hit their context limit prematurely.

## Existing Mitigations

| Mitigation | Scope | Effectiveness |
|------------|-------|---------------|
| `task accept` is idempotent | Server-side | Prevents duplicate state transitions, but does NOT prevent token waste |
| Bracketed paste fix (#1834) | tmux | Fixed Enter-swallowing, but made nudges MORE reliable (more reach the queue) |
| `/clear` before dispatch | `dispatch_to_worker` step 5b | Clears old context, but the subsequent nudge still queues if lane is processing /clear |
| Active-work detection | `monitor.py` | Prevents false stall re-nudges, but doesn't cover orchestrator manual nudges |
| Background validation guard (#2123) | `monitor.py` | Prevents false stalls during `make check`, but only for the monitor's re-nudge |

## Solution Proposals

### Proposal A: Sender-Side Busy Guard (Recommended)

**Concept:** Before sending `/start-task` via tmux, check if the lane's
pane shows active-work indicators. If busy, skip the nudge -- the lane
will discover its task via the durable inbox/task_queue on its next idle
check.

**Implementation sketch:**

```python
# In nudge_pane() — add a pre-flight busy check
def nudge_pane(lane_id, packet_id, *, skip_if_busy=True, ...):
    if skip_if_busy:
        content = _capture_pane_content(lane_id, tmux_session, runtime_dir)
        if content is not None and _detect_active_work(content):
            return PoolAction(
                action="nudge",
                lane_id=lane_id,
                reason=f"Skipped nudge — lane is busy (active work detected)",
                executed=False,
                error="lane_busy",
            )
    # ... existing nudge logic
```

Also add the same guard to `_do_nudge()` in `monitor.py` (stall recovery).

**Effort:** 1 PR, ~50 lines changed in `worker_pool.py` + `monitor.py`

**Pros:**
- Reuses existing `_detect_active_work()` and `_capture_pane_content()` infrastructure
- No changes to Claude Code internals (external-only fix)
- Eliminates the most common source of duplicate nudges
- Simple to test (mock `_capture_pane_content` to return busy indicators)

**Cons:**
- Race condition window: lane could finish work between the check and the
  nudge arriving (low risk -- nudge then just works normally)
- Does NOT prevent orchestrator manual nudges (operator must learn the pattern)
- `_detect_active_work()` is heuristic-based (could miss some busy states)

**Risk: False negative (missed busy state).** The `_detect_active_work`
patterns check for spinner glyphs, duration counters, and progress
indicators. A lane running a long `git rebase` with no visible progress
might not trigger the busy guard. Mitigation: the background validation
guard (#2123) also checks the process tree via `pgrep`, which catches
`make`/`pytest`/`ruff`. Extending this to `nudge_pane` would cover
process-level busy detection too.

### Proposal B: Receiver-Side Dedup in /start-task Skill

**Concept:** At the start of the `/start-task` skill, check if the
current task packet is already being worked on (branch exists, work in
progress). If so, short-circuit immediately with a one-line "already
working on this task" message.

**Implementation sketch:**

Add to the top of the `/start-task` SKILL.md workflow:

```
### Phase 0 — Dedup Guard

Before any other steps, check if this is a redundant invocation:

1. Run `ops.py task show <packet_id>` — if status is `dispatched` and
   there is an ack file, check the current git branch name
2. If the current branch matches the expected branch for this task AND
   there are commits ahead of origin/main, this is a redundant /start-task
3. Print "Already working on task <packet_id> — ignoring duplicate nudge"
   and exit immediately (do NOT re-read the plan, re-accept, or re-setup)
```

**Effort:** 1 PR, skill doc update + ~10 lines of guard logic

**Pros:**
- Works regardless of how the nudge arrived (dispatch, re-nudge, manual)
- Catches ALL duplicate invocations, not just busy-pane cases
- Minimal token cost (~200 tokens for the guard check vs. 3-8k for full startup)

**Cons:**
- Requires Claude to "understand" the guard and short-circuit (skill is a
  prompt, not enforced code -- LLM may not always follow)
- Still consumes the skill-loader overhead (~2-5 seconds, ~500 tokens)
- Edge case: if the lane legitimately needs to restart (e.g., after a
  failed attempt), the guard might incorrectly suppress the restart

**Risk: LLM non-compliance.** Skills are prompts, not code. The LLM might
ignore the dedup guard under certain context conditions (compacted context,
unusual message ordering). Mitigation: make the guard a concrete CLI
command (`ops.py task check-dedup <packet_id>`) that returns a clear
"DUPLICATE" or "PROCEED" signal.

### Proposal C: Inbox-Pull Model (Replace Push with Poll)

**Concept:** Remove the tmux nudge from `dispatch_to_worker()` entirely.
Instead, have lanes poll their inbox for new tasks on each idle transition
(via the existing `UserPromptSubmit` hook infrastructure).

**Implementation sketch:**

1. **Remove** step 6 (nudge_pane call) from `dispatch_to_worker()`
2. **Add** a `UserPromptSubmit` hook (like `inbox-completion-inject.sh`)
   that checks for dispatched task packets owned by this lane
3. When a dispatched+unacked packet is found, inject `/start-task <id>`
   as `additionalContext` so Claude sees it on the next prompt cycle
4. The lane naturally picks up the task when it finishes current work

**Effort:** 2 PRs (remove nudge + add hook)

**Pros:**
- **Eliminates the queueing problem entirely** -- no tmux push, no queue
- Naturally debounced -- hook only fires on prompt submission
- Reuses proven pattern (inbox-completion-inject.sh already does this)
- No race conditions or heuristic detection needed

**Cons:**
- **Higher latency** -- lane must complete current turn before discovering
  the task (could be 5-15 minutes if running `make check`)
- Requires new hook to be registered in `settings.json` for all author lanes
- If the lane is truly idle (no prompts being submitted), the task is never
  discovered -- needs a cron-based fallback poller
- More complex to reason about than the current push model

**Risk: Idle lane deadlock.** If a lane finishes its current task and has
no more queued prompts, the `UserPromptSubmit` hook never fires, and the
lane sits idle indefinitely. Mitigation: combine with a cron job that
periodically sends a lightweight probe (e.g., "check inbox") to wake
idle lanes. Or keep a minimal nudge as a fallback (sends just "check inbox"
instead of the full `/start-task`).

### Proposal D: Hybrid — Busy Guard + Dedup + Reduced Nudge Sources

**Concept:** Combine the best elements:

1. **Proposal A** sender-side busy guard in `nudge_pane()` and `_do_nudge()`
2. **Proposal B** receiver-side dedup guard in `/start-task` skill
3. **Remove the stall-recovery re-nudge** for the first stall cycle
   (escalate to orchestrator instead of blindly re-nudging)
4. **Document** that manual orchestrator nudges should use
   `ops.py task dispatch --nudge-only` (which routes through the guarded
   `nudge_pane()`) instead of raw `tmux send-keys`

**Effort:** 2-3 PRs

**Pros:**
- Defense in depth -- sender guard catches most, receiver dedup catches the rest
- Reduces stall-recovery noise (no more blind re-nudges)
- Teaches operator to use guarded dispatch instead of raw tmux

**Cons:**
- More total code changes than A or B alone
- Stall recovery behavior change may surface edge cases where the re-nudge
  was actually needed (lane truly stalled, not just slow)

### Proposal E: tmux Buffer Inspection Before Send

**Concept:** Before sending a nudge, inspect the tmux pane's input buffer
to check if `/start-task` is already queued.

**Implementation sketch:**

```bash
# Check if the pane already has text in the input buffer
tmux capture-pane -t <target> -p | tail -1 | grep -q "start-task"
```

**Effort:** 1 PR, ~20 lines

**Pros:**
- Directly checks for the exact condition we want to prevent
- No heuristics about busy state

**Cons:**
- **Fragile** -- Claude Code's TUI rendering means the queued text may not
  be in the capture-pane output (it's in the readline buffer, not the
  terminal screen)
- Only catches text that is visible in the pane, not the internal
  message queue
- Race condition: text could appear between check and send
- tmux `capture-pane` captures screen content, not input buffer

**Not recommended** -- tmux cannot reliably inspect the input buffer.

## Recommendation

**Implement Proposal D (Hybrid)** in three sequential PRs:

### PR 1: Sender-side busy guard (Proposal A core)
- Add `skip_if_busy` parameter to `nudge_pane()` (default True)
- Add process-tree busy check (reuse `_detect_background_validation`)
- Add the same guard to `_do_nudge()` in stall recovery
- **Files:** `src/bid_euchre/ops/worker_pool.py`, `src/bid_euchre/ops/monitor.py`
- **Tests:** Unit tests with mocked `_capture_pane_content` and `_detect_background_validation`
- **Validation:** `uv run python -m pytest tests/unit/test_worker_pool.py tests/unit/test_monitor.py`

### PR 2: Receiver-side dedup guard (Proposal B core)
- Add `ops.py task check-dedup <packet_id>` CLI command
- Returns "DUPLICATE" (exit 0 with message) or "PROCEED" (exit 0 with go-ahead)
- Update `/start-task` SKILL.md to call this as Phase 0
- **Files:** `scripts/internal/ops.py`, `.claude/skills/start-task/SKILL.md`
- **Tests:** Unit test for the dedup check logic
- **Validation:** `uv run python -m pytest tests/unit/test_task_queue.py -k dedup`

### PR 3: Stall recovery refinement
- Change first-stall recovery from re-nudge to orchestrator notification
  (keep re-nudge only on second+ consecutive stall)
- Add `ops.py task dispatch --nudge-only` subcommand for guarded manual nudges
- Document in orchestrator skills that raw `tmux send-keys` is deprecated
  for task dispatch
- **Files:** `src/bid_euchre/ops/monitor.py`, `scripts/internal/ops.py`,
  `.claude/skills/delegate-task/SKILL.md`, `.claude/skills/run-fleet/SKILL.md`
- **Tests:** Update stall detection tests
- **Validation:** `uv run python -m pytest tests/unit/test_monitor.py -k stall`

### Estimated Total Effort

- **3 PRs**, each independently mergeable
- **~150-200 lines** of production code changes
- **~100-150 lines** of test additions
- **~50 lines** of skill/doc updates
- **No experiment reruns** required (ops-only changes)
- **Risk:** Low -- all changes are in the ops subsystem with no game logic impact

## Edge Cases and Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Busy guard false negative (misses busy state) | Medium | Low (extra nudge, same as today) | Process-tree fallback catches make/pytest |
| Busy guard false positive (blocks needed nudge) | Low | Medium (task delayed) | Stall escalation catches it on next cycle |
| Dedup guard blocks legitimate restart | Low | Medium (needs manual override) | Add `--force` flag to bypass dedup |
| Stall recovery change causes missed stalls | Low | Medium | Keep re-nudge on 2nd+ cycle as safety net |
| Race between busy-check and state change | Low | None (harmless -- nudge succeeds or queues) | N/A |

## Related Issues

| Issue | Title | Relevance |
|-------|-------|-----------|
| #1834 | tmux paste bracketing swallows Enter | **Closed** -- fixed the Enter problem, which made nudges more reliable and thus more likely to queue |
| #2171 | Investigate tmux interrupt/halt for active lanes | **Open** -- related but orthogonal (interrupt vs. dedup) |

## Outcome

Research complete. Ready for orchestrator dispatch of PR 1-3.

## Appendix: Key Code Locations

| Component | File | Line(s) | Purpose |
|-----------|------|---------|---------|
| `nudge_pane()` | `src/bid_euchre/ops/worker_pool.py` | 1374-1441 | Sends `/start-task` to tmux pane |
| `dispatch_to_worker()` | `src/bid_euchre/ops/worker_pool.py` | 1444-1759 | Full dispatch lifecycle (calls nudge_pane at step 6) |
| `clear_session()` | `src/bid_euchre/ops/worker_pool.py` | 1310-1371 | Sends /clear before dispatch |
| `_do_nudge()` | `src/bid_euchre/ops/monitor.py` | 809-835 | Re-nudge wrapper for stall recovery |
| `check_stalled_lanes()` | `src/bid_euchre/ops/monitor.py` | 838-1100 | Stall detection + recovery ladder |
| `_detect_active_work()` | `src/bid_euchre/ops/monitor.py` | 1235-1263 | Pane content busy heuristic |
| `_detect_background_validation()` | `src/bid_euchre/ops/monitor.py` | 1275-1340 | Process-tree busy check |
| `task accept` | `scripts/internal/ops.py` | 1764-1843 | Idempotent task acceptance |
| `/start-task` skill | `.claude/skills/start-task/SKILL.md` | Full file | Task bootstrap prompt |
| `_PASTE_BRACKET_DELAY` | `src/bid_euchre/ops/worker_pool.py` | 78 | 0.1s delay for paste bracket fix |
| `inbox-completion-inject` | `.claude/hooks/inbox-completion-inject.py` | Full file | Pull-model pattern (for reference) |
