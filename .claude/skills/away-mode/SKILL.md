---
name: away-mode
description: Check operator away-mode status, send advisory presence notifications, configure Telegram push preferences, and view push history. Use from the orchestrator or ops lane to manage operator presence and remote notifications.
---

# /away-mode -- Operator Away-Mode Management

Check the operator's away-mode detection state, send advisory presence
notifications, and inspect Telegram push configuration and history. Wraps the
`ops.py away` CLI and Telegram push infrastructure into a single
operator-facing skill.

## When to Use

- You want to check whether the operator is currently present, idle, or away
- You need to send an advisory away/return notification (e.g., operator
  announces they are leaving or returning)
- You want to configure which alert severities trigger Telegram push
- You want to review recent Telegram push history
- The `/fleet-check` Step 5 needs a manual override of away detection

## Arguments

Optional positional argument controlling the action:

| Argument | Description |
|----------|-------------|
| (none) | Show current status (default) |
| `status` | Same as no argument -- show detailed status |
| `on` | Send advisory "away" notification to orchestrator |
| `off` | Send advisory "returned" notification to orchestrator |
| `config` | Show current Telegram push configuration |
| `history` | Show recent Telegram push history |

## Workflow

### Action: Check Status (default)

Run the away-mode detector against the latest operator interaction event:

```bash
uv run python scripts/internal/ops.py --json away status
```

Interpret the result:

| State | Tier | Meaning | Action |
|-------|------|---------|--------|
| `present` | 0 | Operator active within last 15m | No action needed |
| `idle` | 1 | No interaction for 15-45m | Monitor, no push yet |
| `away` | 2 | No interaction for 45-120m | Telegram push eligible |
| `extended_away` | 3 | No interaction for 120m+ | Full autonomous mode |

Report the state, minutes inactive, and last interaction time to the
operator (or to the orchestrator if running from ops lane).

### Action: Advisory Away Notification (`on`)

> **Advisory only.** There is no mutable away-mode state to toggle.
> `detect_operator_state()` is a pure function that infers presence from the
> most recent `UserPromptSubmit` event timestamp. The notification below
> tells the orchestrator to treat the operator as absent — but the detector
> will transition back to `present` automatically on the next interaction.

When the operator announces they are leaving, send a message-bus notification:

```bash
uv run python scripts/internal/ops.py message send \
  --from <lane> --to orchestrator --type progress \
  --summary "Operator manually marked as away via /away-mode on"
```

Then confirm the current detected state:

```bash
uv run python scripts/internal/ops.py away status
```

### Action: Advisory Return Notification (`off`)

When the operator announces they have returned, notify the orchestrator:

```bash
uv run python scripts/internal/ops.py message send \
  --from <lane> --to orchestrator --type progress \
  --summary "Operator returned (manual toggle via /away-mode off)"
```

Then confirm the current detected state:

```bash
uv run python scripts/internal/ops.py away status
```

### Action: Show Push Configuration (`config`)

Display the current Telegram push settings:

```bash
# Check if Telegram push is enabled
echo "STEWARD_TELEGRAM_ENABLED=${STEWARD_TELEGRAM_ENABLED:-unset}"

# Show escalation thresholds (included in status output)
uv run python scripts/internal/ops.py away status

# Show persisted push state (per-item cooldowns and history)
# Written by alert_push.py after each push cycle — may not exist if no push has run yet.
cat .claude/runtime/alert_push_state.json 2>/dev/null || echo "(no push state file yet)"
```

**Configurable thresholds** can be overridden per-invocation:

```bash
# Example: shorter idle window for daytime operation
uv run python scripts/internal/ops.py away status --idle 10 --away 30 --extended-away 90
```

The defaults are:
- Idle: 15 minutes
- Away: 45 minutes
- Extended away: 120 minutes

### Action: Show Push History (`history`)

Review recent Telegram push events from the audit trail:

```bash
# Filter event log to push-related events (alert_push, telegram_push types)
uv run python scripts/internal/ops.py events --type alert_push --limit 10
uv run python scripts/internal/ops.py events --type telegram_push --limit 10

# Read the persisted push state (per-item cooldowns, push counts, last-pushed times)
# Written by alert_push.py after each push cycle — may not exist if no push has run yet.
cat .claude/runtime/alert_push_state.json 2>/dev/null || echo "(no push state file yet)"
```

The push state file (`.claude/runtime/alert_push_state.json`) tracks per-item
push history including `last_pushed` timestamp, `push_count`, and `severity`.
It is written by `alert_push.py` after each push cycle. If the file does not
exist, no push cycle has completed in this worktree.

## Telegram Push Flow

The away-mode skill integrates with the following push infrastructure:

```
UserPromptSubmit events
        |
        v
  away_mode.py  ---------> detect_operator_state()
  (pure logic)               |
                             v
                    OperatorPresence: PRESENT | IDLE | AWAY | EXTENDED_AWAY
                             |
                             v  (if AWAY or EXTENDED_AWAY)
                    alert_push.py  --> evaluate_push_needed()
                    (transport-agnostic)
                             |
                             v
                    telegram_push.py  --> prepare_alert_push()
                    (formats message)
                             |
                             v
                    MCP reply tool  --> Telegram delivery
                    (called by orchestrator/ops skill)
```

**Key files:**
- `src/bid_euchre/ops/away_mode.py` -- Pure state detection logic
- `src/bid_euchre/ops/alert_push.py` -- Transport-agnostic push evaluation
- `src/bid_euchre/ops/telegram_push.py` -- Telegram message formatting
- `src/bid_euchre/ops/queue_priority.py` -- Away-mode-aware queue reorder
- `scripts/internal/ops.py` -- CLI entry point (`away status`, `away reorder`)

## Integration with Fleet Operations

- **`/fleet-check` Step 5** checks away status to decide whether to push
  a status summary via Telegram
- **`/monitor`** (ops lane) runs the full alert push cycle including away
  detection, push evaluation, and Telegram delivery
- **Queue reorder** (`ops.py away reorder`) adjusts task queue priority
  based on operator presence -- higher autonomy when operator is away

## Gotchas

- **Manual toggle is advisory.** It sends a message bus notification to
  the orchestrator but does not override the threshold-based detector. If
  the operator interacts with a session after toggling `on`, the detector
  will correctly transition back to `present`.
- **Telegram push requires `STEWARD_TELEGRAM_ENABLED=1`.** If this env
  var is not set, all push operations are silently skipped.
- **Push state is per-item.** Each controller item has its own cooldown
  and push count. Re-pushing only happens on cooldown expiry or severity
  escalation.
- **Clock skew safety.** If `last_interaction` is in the future (clock
  skew), the detector treats the operator as `present` to be safe.

## References

- `src/bid_euchre/ops/away_mode.py` -- Core detection module (Platform-9b)
- `src/bid_euchre/ops/telegram_push.py` -- Push adapter (Platform-9a PR3)
- `src/bid_euchre/ops/alert_push.py` -- Push evaluator (Platform-9a PR1)
- `.claude/skills/fleet-check/SKILL.md` -- Orchestrator cron (Step 5)
- `.claude/skills/monitor/SKILL.md` -- Ops monitoring cycle
- Issue #2338 -- Feature request for this skill
