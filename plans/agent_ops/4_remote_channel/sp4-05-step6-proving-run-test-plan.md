# SP-4-05 Step 6: Reactive Control-Loop Proving Run Test Plan

**Parent:** `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`
**Status:** EXECUTING — proving run in progress
**Date:** 2026-03-24
**Proving run started:** 2026-03-24T04:30Z

---

## Objective

Demonstrate that the local steward platform reacts to lifecycle events without
manual GitHub polling. The proving run exercises three scenarios end-to-end:

1. **Local merge** — `gh pr merge` inside a Claude session triggers the hook fast path
2. **Auto-merge / external merge** — the monitor fallback detects and completes the packet
3. **Stall detection** — the recovery ladder re-nudges then escalates

Each scenario verifies the full signal chain: packet state transition, lane
freed signal, orchestrator-visible next-action finding, and bus message delivery.

---

## Prerequisites

Before running the proving run, verify:

- [ ] SP-4-05 PR 1 is merged (completion helper unification — `#1478`, `#1479`)
- [ ] SP-4-05 PR 2 is merged (typed lifecycle reconciler — `#1469`, `#1482`)
- [ ] Steward fleet is running (`tmux has-session -t steward` succeeds)
- [ ] At least one author lane is idle (`uv run python scripts/internal/ops.py --json status` shows `pool_status: idle`)
- [ ] Monitor ops loop is active in the ops pane (or can be manually invoked)

---

## Scenario 1: Local Merge (Hook Fast Path)

**Goal:** Verify that `gh pr merge` inside a Claude session triggers
`post-merge-notify.sh`, which transitions the packet to `completed`, frees the
lane, and delivers a `completion` bus message to the orchestrator.

### Setup

```bash
# 1. Create a tiny test packet dispatched to a test lane (e.g., flex-c)
uv run python scripts/internal/ops.py task create \
  --title "proving-run: local merge test" \
  --description "Trivial change to verify hook completion path" \
  --scope "plans/agent_ops/4_remote_channel/sp4-05-step6-proving-run-test-plan.md" \
  --validation "make check-quiet" \
  --domain platform

# 2. Approve and dispatch to a test lane
uv run python scripts/internal/ops.py task approve <PACKET_ID>
uv run python scripts/internal/ops.py task dispatch <PACKET_ID> --lane flex-c
```

### Execution

From the **flex-c lane** (or simulate by setting `CLAUDE_AGENT_NAME`):

```bash
# 3. Accept the task
uv run python scripts/internal/ops.py task accept <PACKET_ID> --lane flex-c

# 4. Create a trivial branch, commit, and open a PR
git fetch origin main && git checkout -b proving/local-merge-test origin/main
# (make a trivial documentation-only change, commit, push, gh pr create)

# 5. Run make check-quiet (docs-only PR skips heavy jobs)
make check-quiet

# 6. Wait for CI to pass, then merge
gh pr merge <PR_NUM> --squash
```

### Expected Outputs

| Check | Command | Expected |
|-------|---------|----------|
| Packet completed | `uv run python scripts/internal/ops.py task show <PACKET_ID>` | `status: completed` |
| Sentinel created | `ls /tmp/.claude-post-merge-notify-<PR_NUM>` | File exists |
| Bus message sent | `uv run python scripts/internal/ops.py inbox --lane orchestrator` | Contains `completion` message with `pr_number: <PR_NUM>` |
| Lane freed | `uv run python scripts/internal/ops.py --json status` | Lane `flex-c` shows no active dispatched packet |

### Verification Script

```bash
#!/usr/bin/env bash
# Run after gh pr merge completes
set -euo pipefail

PACKET_ID="${1:?Usage: verify_local_merge.sh <PACKET_ID> <PR_NUM>}"
PR_NUM="${2:?Usage: verify_local_merge.sh <PACKET_ID> <PR_NUM>}"

echo "=== Scenario 1: Local Merge Verification ==="

# Check packet status
STATUS=$(uv run python -c "
from bid_euchre.ops.task_queue import load_packet
pkt = load_packet('$PACKET_ID')
print(pkt.status if pkt else 'NOT_FOUND')
")
echo "Packet status: $STATUS"
[ "$STATUS" = "completed" ] && echo "  ✅ PASS" || echo "  ❌ FAIL"

# Check sentinel
if [ -f "/tmp/.claude-post-merge-notify-${PR_NUM}" ]; then
    echo "Sentinel: exists ✅"
else
    echo "Sentinel: missing ❌"
fi

# Check bus message
MSG=$(uv run python -c "
from bid_euchre.ops.message_bus import read_inbox
msgs = read_inbox('orchestrator')
found = any(
    m.message_type == 'completion' and
    (m.payload or {}).get('pr_number') == '$PR_NUM'
    for m in msgs
)
print('found' if found else 'not_found')
")
echo "Bus message: $MSG"
[ "$MSG" = "found" ] && echo "  ✅ PASS" || echo "  ❌ FAIL"

echo ""
```

---

## Scenario 2: Auto-Merge / External Merge (Monitor Fallback)

**Goal:** Verify that when a PR merges server-side (GitHub auto-merge or manual
merge outside a Claude session), the monitor's `check_merged_dispatches()`
detects the merge and auto-completes the packet.

### Setup

```bash
# 1. Create and dispatch a test packet
uv run python scripts/internal/ops.py task create \
  --title "proving-run: auto-merge test" \
  --description "Trivial change to verify monitor fallback completion path" \
  --scope "plans/agent_ops/4_remote_channel/sp4-05-step6-proving-run-test-plan.md" \
  --validation "make check-quiet" \
  --domain platform

uv run python scripts/internal/ops.py task approve <PACKET_ID>
uv run python scripts/internal/ops.py task dispatch <PACKET_ID> --lane flex-c
```

### Execution

```bash
# 2. Accept the task and open a PR
uv run python scripts/internal/ops.py task accept <PACKET_ID> --lane flex-c
git fetch origin main && git checkout -b proving/auto-merge-test origin/main
# (make trivial doc change, commit, push, gh pr create)

# 3. Link the PR number to the packet metadata
uv run python -c "
from bid_euchre.ops.task_queue import update_packet_metadata
update_packet_metadata('<PACKET_ID>', {'pr_number': <PR_NUM>})
"

# 4. Enable auto-merge (requires CI to pass)
gh pr merge <PR_NUM> --auto --squash

# 5. Wait for CI to pass and GitHub to auto-merge
# (monitor detects via gh pr view — no local hook fires)

# 6. Run the monitor manually (or wait for the ops loop to fire)
uv run python scripts/internal/ops.py monitor --no-auto-dispatch
```

### Expected Outputs

| Check | Command | Expected |
|-------|---------|----------|
| Packet completed | `uv run python scripts/internal/ops.py task show <PACKET_ID>` | `status: completed` |
| Monitor finding | Inspect monitor output | Finding `category: merged_dispatch`, `severity: info` for this packet |
| Bus message sent | `uv run python scripts/internal/ops.py inbox --lane orchestrator` | Contains `completion` message (may differ from hook path — verify) |
| Lane freed | `uv run python scripts/internal/ops.py --json status` | Lane `flex-c` shows no active dispatched packet |

### Verification Script

```bash
#!/usr/bin/env bash
set -euo pipefail

PACKET_ID="${1:?Usage: verify_auto_merge.sh <PACKET_ID> <PR_NUM>}"
PR_NUM="${2:?Usage: verify_auto_merge.sh <PACKET_ID> <PR_NUM>}"

echo "=== Scenario 2: Auto-Merge Verification ==="

# Verify PR is MERGED on GitHub
GH_STATE=$(gh pr view "$PR_NUM" --json state --jq '.state')
echo "GitHub PR state: $GH_STATE"
[ "$GH_STATE" = "MERGED" ] && echo "  ✅ PASS" || echo "  ❌ FAIL (PR not merged yet)"

# Run monitor to trigger fallback completion
echo "Running monitor sweep..."
uv run python scripts/internal/ops.py monitor --no-auto-dispatch 2>&1 | head -20

# Check packet status
STATUS=$(uv run python -c "
from bid_euchre.ops.task_queue import load_packet
pkt = load_packet('$PACKET_ID')
print(pkt.status if pkt else 'NOT_FOUND')
")
echo "Packet status: $STATUS"
[ "$STATUS" = "completed" ] && echo "  ✅ PASS" || echo "  ❌ FAIL"

# NOTE: No sentinel expected for auto-merge path (sentinel is hook-only)
if [ ! -f "/tmp/.claude-post-merge-notify-${PR_NUM}" ]; then
    echo "Sentinel absent (expected for monitor path): ✅"
else
    echo "Sentinel present (unexpected — hook may have fired too): ⚠️"
fi

echo ""
```

### Key Difference from Scenario 1

The **auto-merge watcher** in `post-merge-notify.sh` fires a background poller
when `--auto` is used with `gh pr merge`. However, if the PR is merged entirely
server-side (e.g., via GitHub UI), **no hook fires at all**. The monitor's
`check_merged_dispatches()` is the sole completion path. This scenario must
test the pure monitor fallback, so prefer merging via GitHub UI or ensuring the
auto-merge happens after the session hook context is lost.

---

## Scenario 3: Stall Detection and Recovery Ladder

**Goal:** Verify that a dispatched lane with no tmux activity progress triggers
the 2-step recovery ladder:
1. **First stall detection:** re-nudge the lane (WARN finding)
2. **Second consecutive stall:** escalate to orchestrator (HIGH finding)

### Setup

```bash
# 1. Create and dispatch a test packet to a lane that will intentionally stall
uv run python scripts/internal/ops.py task create \
  --title "proving-run: stall detection test" \
  --description "Intentionally stalled lane to verify recovery ladder" \
  --scope "plans/agent_ops/4_remote_channel/sp4-05-step6-proving-run-test-plan.md" \
  --validation "make check-quiet" \
  --domain platform

uv run python scripts/internal/ops.py task approve <PACKET_ID>
uv run python scripts/internal/ops.py task dispatch <PACKET_ID> --lane flex-c

# 2. Accept the task (creates the ack, needed for stall detection)
uv run python scripts/internal/ops.py task accept <PACKET_ID> --lane flex-c
```

### Execution

```bash
# 3. Do NOT start any work — let the lane sit idle to simulate a stall

# 4. Override stall timing for faster testing (default is 10 min threshold)
#    Option A: Backdate the dispatch timestamp in the packet metadata
uv run python -c "
from bid_euchre.ops.task_queue import update_packet_metadata
from datetime import datetime, timezone, timedelta
old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
update_packet_metadata('<PACKET_ID>', {'dispatched_at': old_time})
"

# 5. Run monitor cycle 1 — should detect stall and re-nudge
echo "=== Monitor Cycle 1 (expect re-nudge) ==="
uv run python scripts/internal/ops.py monitor --no-auto-dispatch 2>&1

# 6. Wait briefly (no activity change expected)
sleep 5

# 7. Run monitor cycle 2 — should detect stall again and escalate
echo "=== Monitor Cycle 2 (expect escalation) ==="
uv run python scripts/internal/ops.py monitor --no-auto-dispatch 2>&1
```

### Expected Outputs

| Cycle | Finding Category | Severity | Recovery Action | Detail |
|-------|-----------------|----------|-----------------|--------|
| 1 | `stall_recovery` | `warn` | `nudge` | Re-nudge sent to lane |
| 2 | `stall_recovery` | `high` | `escalate` | Escalation to orchestrator |

### Verification Script

```bash
#!/usr/bin/env bash
set -euo pipefail

PACKET_ID="${1:?Usage: verify_stall.sh <PACKET_ID>}"

echo "=== Scenario 3: Stall Detection Verification ==="

# Check stall state file for the lane
STALL_STATE=$(uv run python -c "
import json
from pathlib import Path
state_path = Path('.claude/runtime/stall_state.json')
if state_path.exists():
    data = json.loads(state_path.read_text())
    obs = data.get('observations', {})
    for lane, info in obs.items():
        if info.get('packet_id') == '$PACKET_ID':
            print(f'lane={lane} unchanged={info.get(\"unchanged_count\",0)} recovery={info.get(\"recovery_count\",0)}')
else:
    print('NO_STATE_FILE')
")
echo "Stall state: $STALL_STATE"

# Check orchestrator inbox for HIGH severity finding
ESCALATED=$(uv run python -c "
from bid_euchre.ops.message_bus import read_inbox
msgs = read_inbox('orchestrator')
found = any(
    'stall' in (m.summary or '').lower() and 'escalat' in (m.summary or '').lower()
    for m in msgs
)
print('found' if found else 'not_found')
")
echo "Escalation in orchestrator inbox: $ESCALATED"
[ "$ESCALATED" = "found" ] && echo "  ✅ PASS" || echo "  ❌ FAIL"

echo ""
```

### Stall State Internals

The stall detector persists cross-cycle state at
`.claude/runtime/stall_state.json`. Each observation records:

```json
{
  "observations": {
    "flex-c": {
      "packet_id": "<PACKET_ID>",
      "activity_epoch": 1234567890,
      "unchanged_count": 2,
      "recovery_count": 2
    }
  }
}
```

- `unchanged_count >= STALL_CONSECUTIVE_CYCLES` (default 2) triggers the ladder
- `recovery_count == 0` → re-nudge (step 1)
- `recovery_count >= 1` → escalate (step 2)

---

## Cleanup Procedure

After all scenarios are complete:

```bash
# 1. Clean up proving-run sentinels
rm -f /tmp/.claude-post-merge-notify-*

# 2. Clean up proving-run stall state entries
uv run python -c "
import json
from pathlib import Path
state_path = Path('.claude/runtime/stall_state.json')
if state_path.exists():
    data = json.loads(state_path.read_text())
    obs = data.get('observations', {})
    # Remove test lane entries
    for key in list(obs):
        if obs[key].get('packet_id', '').startswith('proving'):
            del obs[key]
    state_path.write_text(json.dumps(data, indent=2))
"

# 3. Archive any leftover test packets
uv run python scripts/internal/ops.py task list  # inspect for proving-run packets
# Archive individually if needed:
# uv run python -c "from bid_euchre.ops.task_queue import archive_packet; archive_packet('<ID>')"

# 4. Clean up test branches
git branch -d proving/local-merge-test proving/auto-merge-test 2>/dev/null || true
git push origin --delete proving/local-merge-test proving/auto-merge-test 2>/dev/null || true
```

---

## Success Criteria

All three scenarios must pass for the proving run to be considered successful:

| # | Scenario | Key Assertion |
|---|----------|---------------|
| 1 | Local merge | Hook completes packet within seconds of `gh pr merge` |
| 2 | Auto-merge / external | Monitor fallback completes packet on next cycle |
| 3a | Stall — first detection | Monitor re-nudges lane (WARN finding) |
| 3b | Stall — second detection | Monitor escalates to orchestrator (HIGH finding) |

**Cross-cutting assertions (all scenarios):**
- Orchestrator inbox receives a typed lifecycle signal for every state transition
- No manual `gh pr list --state merged` polling is required
- Lane becomes eligible for new dispatch after completion
- Packet metadata captures `pr_number`, branch, and lane identity

---

## Failure Modes and Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Packet stays `dispatched` after local merge | Hook not firing — check `CLAUDE_AGENT_NAME` or `CLAUDE_PROJECT_DIR` | Verify env vars; run hook manually with test input |
| No bus message after completion | `send_message()` failed — check bus root path | Verify `.claude/runtime/bus/` exists and is writable |
| Monitor doesn't detect merged PR | `metadata.pr_number` not set on packet | Ensure PR-number linkage from Step 1 is working |
| Stall detection doesn't fire | Packet dispatch age < `STALL_THRESHOLD_MINUTES` (10 min) | Backdate `dispatched_at` in metadata |
| Re-nudge doesn't trigger | Lane doesn't have an ack file | Ensure `task accept` was run before stall test |
| Escalation doesn't fire on cycle 2 | Activity epoch changed between cycles | Ensure lane pane is truly idle (no commands) |
| `check_merged_dispatches` times out | GitHub CLI rate limit or network issue | Check `gh auth status`; retry after cooldown |

---

## Relationship to SP-4-05 Steps

| SP-4-05 Step | Status Required | What It Proves |
|-------------|----------------|----------------|
| Step 1 (packet-to-PR linkage) | ✅ Merged | Scenario 2 depends on `metadata.pr_number` |
| Step 2 (completion unification) | ✅ Merged | Scenario 1 uses the shared completion helper |
| Step 3 (typed reconciler) | ✅ Merged | Scenario 2 uses typed findings from monitor |
| Step 4 (persistent ops loop) | ✅ Merged | Scenario 2 relies on monitor running continuously |
| Step 5 (noise reduction) | ✅ Merged | Orchestrator reads should be clean during verification |
| **Step 6 (this plan)** | 📋 Plan ready | Execute after all above steps are merged |
