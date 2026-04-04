---
name: away-mode
description: Check operator away-mode status, send advisory toggle notifications, configure Telegram push preferences, and view push history. Use from the orchestrator or ops lane to manage operator presence and remote notifications.
---

# /away-mode -- Operator Away-Mode Management

Check status, send advisory toggle notifications, and configure the operator's
away-mode detection and Telegram push notification settings. Wraps the
`ops.py away` CLI and Telegram push infrastructure into a single
operator-facing skill.

## When to Use

- You want to check whether the operator is currently present, idle, or away
- You need to manually toggle away-mode (e.g., operator announces they are
  leaving or returning)
- You want to configure which alert severities trigger Telegram push
- You want to review recent Telegram push history
- The `/fleet-check` Step 5 needs a manual override of away detection

## Arguments

Optional positional argument controlling the action:

| Argument | Description |
|----------|-------------|
| (none) | Show current status (default) |
| `status` | Same as no argument -- show detailed status |
| `on` | Manually mark operator as away |
| `off` | Manually mark operator as returned/present |
| `config` | Show current Telegram push configuration |
| `history` | Show recent Telegram push history |

## Workflow

### Action: Check Status (default)

Run the away-mode detector against the latest operator interaction event:

```bash
uv run python scripts/internal/ops.py away status --json
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

### Action: Manual Toggle On (`on`)

When the operator announces they are leaving:

1. **Send an advisory notification** to the orchestrator so it knows the
   operator intends to be away. This does **not** change the detected
   away-mode state — the threshold-based detector infers state from
   interaction timestamps automatically.

   ```bash
   uv run python scripts/internal/ops.py message send \
     --from <lane> --to orchestrator --type progress \
     --summary "Operator manually marked as away via /away-mode on"
   ```

2. **Verify** the current detected state:

   ```bash
   uv run python scripts/internal/ops.py away status
   ```

> **Note:** This notification is advisory only — it does not override the
> threshold-based detector. The detector will transition to `away` on its
> own once the idle threshold is reached. The operator will transition back
> to `present` automatically when they next interact with any Claude Code
> session (UserPromptSubmit events are tracked by the event system).

### Action: Manual Toggle Off (`off`)

When the operator announces they have returned:

1. **Send an advisory notification** that the operator has returned. The
   detector will transition to `present` automatically once it sees a
   fresh interaction event; this message is informational only.

   ```bash
   uv run python scripts/internal/ops.py message send \
     --from <lane> --to orchestrator --type progress \
     --summary "Operator returned (manual toggle via /away-mode off)"
   ```

2. **Verify** the current detected state:

   ```bash
   uv run python scripts/internal/ops.py away status
   ```

### Action: Show Push Configuration (`config`)

Display the current Telegram push settings:

```bash
# Check if Telegram push is enabled
echo "STEWARD_TELEGRAM_ENABLED=${STEWARD_TELEGRAM_ENABLED:-unset}"

# Show push state (cooldowns, per-item tracking)
cat .claude/runtime/alert_push_state.json 2>/dev/null || echo "(no push state file)"

# Show escalation thresholds
uv run python scripts/internal/ops.py away status --json | python3 -c "
import sys, json
data = json.load(sys.stdin)
t = data['thresholds']
print(f\"Idle threshold:          {t['idle_minutes']:.0f}m\")
print(f\"Away threshold:          {t['away_minutes']:.0f}m\")
print(f\"Extended-away threshold: {t['extended_away_minutes']:.0f}m\")
"
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
# Recent push-related events from the event log
uv run python scripts/internal/ops.py events --limit 20

# Read the persisted push state (per-item cooldown and history)
cat .claude/runtime/alert_push_state.json 2>/dev/null || echo "(no push state file)"
```

The push state file (`.claude/runtime/alert_push_state.json`) tracks per-item
push history including `last_pushed` timestamp, `push_count`, and `severity`.
It is written by `alert_push.py` after each push cycle.

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
