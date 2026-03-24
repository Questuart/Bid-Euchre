# SP-4-05 Step 6: Proving Run Results

**Parent:** `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`
**Status:** PASSED
**Date:** 2026-03-24
**Executed by:** flex-b lane

---

## Summary

All three proving run scenarios passed. The reactive control-loop
infrastructure (post-merge hook, monitor fallback, stall recovery ladder)
works end-to-end as designed.

---

## Scenario 1: Local Merge (Hook Fast Path)

**PR:** #1515 (`proving/local-merge-test`)
**Test packet:** `107ce27f717c`

**Setup:** Created a docs-only PR marking the test plan as EXECUTING.
Dispatched test packet to flex-b with `metadata.pr_number = 1515`.

**Observation:** PR #1515 was auto-merged by the `enable-auto-merge` GitHub
Action before the manual `gh pr merge` ran. The CLI returned "already merged".
Despite this, the `post-merge-notify.sh` hook's completion logic still
executed successfully — the packet transitioned and the bus message was sent.

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| Packet completed | `status: completed` | `status: completed` | PASS |
| Sentinel created | `/tmp/.claude-post-merge-notify-1515` exists | File exists | PASS |
| Bus message sent | `completion` message to orchestrator | `343bc97ff6be461f` from flex-b | PASS |
| Lane freed | No active dispatched packet for flex-b | Packet completed | PASS |

**Bonus finding:** The hook handles the "already merged" edge case from
`gh pr merge` — the exit code is 0 and the completion logic fires. This
means even if GitHub auto-merge races the CLI, the lifecycle is correct.

---

## Scenario 2: Auto-Merge / External Merge (Monitor Fallback)

**Test packet:** `08a24f95c8b0` (dispatched to flex-c, linked to already-merged PR #1515)

**Setup:** Created a test packet pointing to PR #1515 (already merged in
Scenario 1). Dispatched to flex-c to simulate a different lane. No local
hook could have fired for this lane.

**Execution:** Ran `uv run python scripts/internal/ops.py monitor --no-auto-dispatch`.

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| Packet completed | `status: completed` | `status: completed` | PASS |
| Monitor finding | `merged_dispatch` category | `Auto-completed packet '08a24f95c8b0' (PR #1515 merged via auto-merge)` | PASS |
| No sentinel | (monitor path, not hook) | No sentinel file | PASS |
| Lane freed | flex-c has no active packet | Packet completed | PASS |

**Key validation:** The monitor's `check_merged_dispatches()` correctly
queries GitHub for the PR state and auto-completes the packet when the
PR is merged. This is the fallback path for PRs merged outside a Claude
session (GitHub UI, auto-merge, etc.).

---

## Scenario 3: Stall Detection and Recovery Ladder

**Test packet:** `ef326ef36e8a` (dispatched to flex-c, backdated 20 min)

**Setup:** Created a dispatched+acked test packet with `dispatched_at`
backdated 20 minutes. Used mock activity probe (`_activity_probe`) returning
a frozen epoch to simulate a lane with no tmux activity.

**Execution:** Ran `check_stalled_lanes()` for 5 cycles with test hooks.

| Cycle | Finding | Severity | Recovery Action | Result |
|-------|---------|----------|-----------------|--------|
| 1 | (none — building observation) | — | — | PASS |
| 2 | (none — unchanged_count=1 < threshold=2) | — | — | PASS |
| 3 | `stall_recovery` | WARN | Re-nudge (recovery_count=0 → 1) | PASS |
| 4 | `stall_recovery` | HIGH | Escalate (recovery_count=1 → 2) | PASS |
| 5 | `stall_recovery` | HIGH | Escalate (recovery_count=2 → 3) | PASS |

**Cross-cycle persistence:** The stall state file at
`.claude/runtime/stall_state.json` correctly persisted observations across
invocations. When cleared and re-run, the ladder replayed identically.

**Recovery ladder verified:**
- Step 1 (nudge): Fires exactly once at `unchanged_count >= 2` when `recovery_count == 0`
- Step 2 (escalate): Fires on all subsequent cycles when `recovery_count >= 1`
- Nudge call count: exactly 1 (cycle 3 only)
- Escalation is idempotent and safe to repeat

---

## Cross-Cutting Assertions

| Assertion | Result |
|-----------|--------|
| Orchestrator inbox receives typed lifecycle signals | PASS — completion message `343bc97ff6be461f` delivered |
| No manual `gh pr list --state merged` polling required | PASS — hook and monitor handle automatically |
| Lane becomes eligible for new dispatch after completion | PASS — packets transition to `completed` |
| Packet metadata captures pr_number, lane identity | PASS — all test packets had correct metadata |
| Cross-cycle state persists for stall detection | PASS — observations survive between invocations |

---

## Issues Discovered

None blocking. One notable edge case documented:

- **Auto-merge race:** When `enable-auto-merge` merges a PR before the
  manual `gh pr merge` executes, the CLI returns "already merged" with
  exit code 0. The hook's completion logic still fires correctly. This is
  a **positive finding** — no fix needed.

---

## Conclusion

The SP-4-05 reactive control-loop infrastructure is proven. All three
signal paths work:

1. **Hook fast path** — immediate completion on `gh pr merge`
2. **Monitor fallback** — detects externally-merged PRs on next cycle
3. **Stall recovery ladder** — 2-step escalation (nudge → escalate)

SP-4-05 Step 6 is COMPLETE.
