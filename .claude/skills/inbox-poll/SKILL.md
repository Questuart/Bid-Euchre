---
name: inbox-poll
description: Lightweight inbox check for any lane — reads pending messages, processes orchestrator directives, and acks. Use when a lane needs to check for new assignments or alerts without a full monitoring sweep.
---

# /inbox-poll -- Lane Inbox Check

Lightweight skill for any lane to check its inbox for orchestrator messages.
Designed for quick, low-overhead invocation -- no fleet-wide scanning, no
GitHub API calls, just inbox read + ack.

## When to Use

- Any lane needs to check for new orchestrator assignments
- A lane has been idle and wants to see if work was dispatched
- After a `/clear`, a lane needs to pick up any missed messages
- As a building block for other skills that need inbox awareness

## Arguments

- `[lane-id]` (optional) -- The lane to check. If omitted, infers from the
  current worktree directory name or `CLAUDE_AGENT_NAME` env var.

## Workflow

### Step 1 -- Determine lane identity

```bash
# Auto-detect from env or directory
LANE="${CLAUDE_AGENT_NAME:-$(basename "$CLAUDE_PROJECT_DIR" | sed 's/Bid-Euchre-steward-//')}"
echo "Polling inbox for: $LANE"
```

### Step 2 -- Read pending messages

```bash
uv run python scripts/internal/ops.py inbox --lane <LANE> --status pending --include-native
```

### Step 3 -- Process messages by type

| Message Type | Action |
|-------------|--------|
| `assignment` | New task dispatched -- invoke `/start-task <packet_id>` |
| `supervisor_alert` | Urgent -- read and act immediately |
| `recovery` | Lane recovery directive -- follow instructions |
| `blocker` | Another lane is blocked on you -- prioritize |
| `progress` | Info only -- note and ack |
| `ack` | Confirmation -- ack |
| `completion` | Task completed -- ack |

### Step 4 -- Ack processed messages

```bash
uv run python scripts/internal/ops.py inbox ack <MSG_ID> --lane <LANE>
```

Or bulk-ack old messages:
```bash
uv run python scripts/internal/ops.py inbox ack --bulk --max-age 1h --lane <LANE>
```

## Quick One-Liner

For a fast inbox check without the full skill workflow:

```bash
uv run python scripts/internal/ops.py inbox --lane <LANE> --status pending
```

## Gotchas

- This skill does NOT run monitoring, fleet checks, or GitHub API calls.
  It is inbox-only, designed to be fast (<5s).
- The `--include-native` flag imports Claude native inbox messages into the
  message bus. Always include it to avoid missing messages.
- If no messages are pending, report "Inbox empty" and return -- do not
  escalate or create busywork.
- Lane identity detection falls back to directory name parsing if
  `CLAUDE_AGENT_NAME` is not set.

## References

- `scripts/internal/ops.py inbox` -- inbox CLI implementation
- `.claude/skills/start-task/SKILL.md` -- task bootstrap (invoked on assignment)
- `.claude/skills/check-in/SKILL.md` -- orchestrator check-in (uses inbox poll
  as mandatory first step)
