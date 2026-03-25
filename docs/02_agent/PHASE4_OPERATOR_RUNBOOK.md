# Phase 4 Operator Runbook — Remote Channel

> **Audience:** Human operator managing the steward fleet
> **Last updated:** 2026-03-25

---

## 1. Remote Channel Overview

Phase 4 adds a **Telegram remote channel** so the operator can monitor and
interact with the steward fleet from a phone when away from the desk.

### Architecture

```
Operator (phone)
    |
    | Telegram Bot API
    v
Claude Channels Plugin (orchestrator pane only)
    |
    +-- Inbound: <channel> tag in UserPromptSubmit -> orchestrator processes
    +-- Outbound: MCP reply tool -> operator's Telegram chat
    |
    +-- Audit trail: .claude/runtime/audit_trail/remote_exchanges.jsonl
    +-- Controller: .claude/runtime/fleet_status.json (single source of truth)
```

### Key Principles

- **Orchestrator-only ingress:** Only the orchestrator pane receives Telegram
  messages. Author lanes remain tmux-only.
- **Controller is truth:** The controller projection (fleet_status.json) is
  the canonical state. Telegram is a transport adapter, not a state store.
- **Audit everything:** Every inbound and outbound remote exchange is
  recorded in the repo-owned audit trail.
- **Kill switch:** The `STEWARD_TELEGRAM_ENABLED` env var controls whether
  Telegram is active. Set to `0` to disable without code changes.

### Telegram Setup

1. **Bot token:** Configured via the Telegram plugin (`claude plugins`).
   The bot token is stored in Claude Code's plugin keychain, not in repo files.

2. **Pairing:** The operator sends a message to the bot from their Telegram
   account. The first message triggers a pairing request that must be
   approved via `/telegram:access` in the terminal.

3. **Kill switch:** The tmux launcher (`.claude/tmux/steward-session.sh`)
   auto-detects whether the Telegram plugin is installed and enabled.
   Override with:
   ```bash
   STEWARD_TELEGRAM_ENABLED=0 .claude/tmux/steward-session.sh  # Disable
   STEWARD_TELEGRAM_ENABLED=1 .claude/tmux/steward-session.sh  # Force enable
   ```

4. **Channel flag:** When enabled, the orchestrator pane launches with
   `--channels plugin:telegram@claude-plugins-official`. Other panes do not
   receive this flag.

---

## 2. Controller Projection Reference

The controller projection is the single control-plane truth for the steward
platform. It lives at **.claude/runtime/fleet_status.json**.

### Reading the Projection

```bash
# CLI view (human-friendly)
uv run python scripts/internal/ops.py fleet status

# Raw JSON
cat .claude/runtime/fleet_status.json | jq '.items[] | {item_id, severity, category, summary, state}'
```

### Item Structure

Each item in the projection has:

| Field | Description |
|-------|-------------|
| `item_id` | Stable hash-based ID for tracking across cycles |
| `severity` | `info`, `warn`, `high`, or `urgent` |
| `category` | Grouping: `lane_health`, `pr_status`, `stalled_lane`, `approval_stall`, `idle_lane`, `stale_dispatch`, `merged_pr`, etc. |
| `source` | Which subsystem produced it (`monitor`, `task_queue`, etc.) |
| `summary` | Human-readable one-liner |
| `state` | `open`, `acked`, `cleared`, or `suppressed` |
| `recommended_action` | Suggested next step |
| `first_seen_at` | ISO 8601 timestamp of first detection |

### Severity Levels

| Severity | Meaning | Push to Telegram? | Blocks merge/dispatch? |
|----------|---------|-------------------|----------------------|
| `info` | Informational | No | No |
| `warn` | Needs attention soon | No | No |
| `high` | Requires action | Yes (when idle) | Yes (urgent-state-guard) |
| `urgent` | Escalated / critical | Yes (when idle) | Yes (urgent-state-guard) |

### Mutation Commands

```bash
# Acknowledge an item (stops push reminders, keeps in projection)
uv run python scripts/internal/ops.py fleet --ack <item_id_or_prefix>

# Clear an item (resolved, remove from active view)
uv run python scripts/internal/ops.py fleet --clear <item_id_or_prefix>

# Suppress an item (won't resurface in future cycles)
uv run python scripts/internal/ops.py fleet --suppress <item_id_or_prefix>
```

### Remote Ack Commands (via Telegram)

When an alert is pushed to Telegram, reply with:

| Command | Effect | Example |
|---------|--------|---------|
| `ack <prefix>` | Acknowledge item | `ack a1b2` |
| `dismiss <prefix>` | Clear/resolve item | `dismiss a1b2` |
| `mute <prefix>` | Suppress item permanently | `mute a1b2` |
| `clear <prefix>` | Same as dismiss | `clear a1b2` |

The `<prefix>` is the first 4+ characters of the `item_id` shown in the
alert message. Prefix must uniquely match one item; if ambiguous, the
system returns the list of candidates.

### Reconcile Cycle

The controller runs during each monitor cycle:

1. Monitor collects findings (lane health, stalls, CI, PRs, etc.)
2. `reconcile()` merges findings with task state, review verdicts, messages,
   and audit records into the controller projection
3. Items carry stable `item_id` values across cycles (hash-based dedup)
4. Existing items preserve their state (`acked`, `cleared`, etc.)
5. Items not seen in the current cycle are expired after a grace period

---

## 3. Alert Push Behavior

### Push Flow

```
Monitor cycle
  -> reconcile() writes fleet_status.json
  -> evaluate_push_needed(fleet_status, idle_status, push_state)
  -> Filter: only HIGH/URGENT + state=open
  -> Filter: idle gate (fleet must be idle)
  -> Filter: dedup (cooldown not elapsed, severity not escalated)
  -> prepare_alert_push() formats Telegram message
  -> Orchestrator sends via MCP reply tool
  -> record_push() updates push state
  -> Audit trail records the outbound exchange
```

### Push State

Push state is persisted at **.claude/runtime/alert_push_state.json** and
tracks per-item:

| Field | Description |
|-------|-------------|
| `last_pushed_at` | ISO 8601 timestamp of last push |
| `push_count` | Number of times this item has been pushed |
| `last_severity` | Severity at time of last push |

### Idle Gating

Alerts are only pushed when the fleet is idle (no meaningful events within
the idle threshold, default 90 minutes). This prevents spamming the
operator while lanes are actively working.

The idle detector (`src/bid_euchre/ops/idle_detector.py`) reads the event
log and checks for meaningful events (task starts/completions, CI outcomes,
review verdicts). Control-plane lanes (orchestrator, ops, review) are
excluded from the activity check.

### Dedup and Backoff

An item is re-pushed only when:

1. **New item:** Never been pushed before
2. **Cooldown elapsed:** More than 15 minutes since last push (configurable
   via `DEFAULT_COOLDOWN_MINUTES`)
3. **Severity escalated:** Item severity increased since last push (e.g.,
   `high` -> `urgent`)

### Telegram Message Format

Pushed alerts include:
- Severity emoji (urgent: alarm, high: warning)
- Item ID prefix (for ack commands)
- Summary text
- Recommended action (if available)

---

## 4. Troubleshooting

### Common Failure Modes

#### Telegram messages not arriving

1. **Check kill switch:** Verify `STEWARD_TELEGRAM_ENABLED` is set:
   ```bash
   tmux show-environment -t steward STEWARD_TELEGRAM_ENABLED
   ```

2. **Check plugin status:**
   ```bash
   claude plugins list  # Should show telegram as enabled
   ```

3. **Check pairing:** The bot must be paired with the operator's Telegram
   account. If unpaired, messages are silently dropped.

4. **Check orchestrator pane:** Only the orchestrator receives `--channels`.
   Verify the orchestrator is running and not stalled.

#### Alerts not being pushed

1. **Fleet not idle:** Alerts only push when idle. Check:
   ```bash
   uv run python -c "from bid_euchre.ops.idle_detector import is_fleet_idle; r = is_fleet_idle(); print(f'idle={r.idle}, minutes={r.idle_minutes:.0f}')"
   ```

2. **No HIGH/URGENT items:** Only high and urgent items are pushed:
   ```bash
   uv run python scripts/internal/ops.py fleet status  # Check for high/urgent
   ```

3. **All items acked:** Acked items are not pushed:
   ```bash
   cat .claude/runtime/fleet_status.json | jq '[.items[] | select(.state == "open" and (.severity == "high" or .severity == "urgent"))] | length'
   ```

4. **Push state cooldown:** Items within the 15-minute cooldown won't be
   re-pushed:
   ```bash
   cat .claude/runtime/alert_push_state.json | jq .
   ```

#### Remote ack not working

1. **Syntax:** The ack command must be one of: `ack <prefix>`,
   `dismiss <prefix>`, `mute <prefix>`, `clear <prefix>`

2. **Prefix ambiguity:** If the prefix matches multiple items, the system
   returns candidates instead of acking. Use a longer prefix.

3. **Item already acked:** If the item is already acked/cleared/suppressed,
   the mutation returns false. Check item state in the projection.

#### Lanes stalling on permission prompts

See `plans/sessions/2026-03-25_permission-stalls-investigation.md` for the
full investigation. Short version: the settings self-edit prompt is
platform-hardcoded. Workaround: send `Esc + 2` to the tmux pane, or add
`--dangerously-skip-permissions` to author lane launch commands.

#### Audit trail issues

1. **Check audit trail exists:**
   ```bash
   wc -l .claude/runtime/audit_trail/remote_exchanges.jsonl
   ```

2. **Check recent entries:**
   ```bash
   tail -5 .claude/runtime/audit_trail/remote_exchanges.jsonl | jq .
   ```

3. **Lock contention:** The audit trail uses `flock` for concurrent-write
   safety. If writes seem stuck, check for stale lock files:
   ```bash
   ls -la .claude/runtime/audit_trail/.remote_exchanges.lock
   ```

### Recovery Steps

#### Controller projection stale or corrupt

```bash
# Force a fresh reconcile
uv run python -c "from bid_euchre.ops.control_plane import reconcile; reconcile()"

# Or delete and let the next monitor cycle regenerate
rm .claude/runtime/fleet_status.json
```

#### Push state stale

```bash
# Reset push state (all items become eligible for push again)
rm .claude/runtime/alert_push_state.json
```

#### Orchestrator not processing Telegram messages

```bash
# Check if orchestrator pane is alive
tmux capture-pane -t steward:central-ops.1 -p | tail -10

# Check for stall patterns
tmux capture-pane -t steward:central-ops.1 -p | grep -i "permission\|stall\|error"

# If stalled, try sending a simple prompt
tmux send-keys -t steward:central-ops.1 "status" Enter
```

#### Complete remote channel reset

```bash
# 1. Kill the steward session
tmux kill-session -t steward

# 2. Clear runtime state
rm -f .claude/runtime/fleet_status.json
rm -f .claude/runtime/alert_push_state.json

# 3. Restart with Telegram
STEWARD_TELEGRAM_ENABLED=1 .claude/tmux/steward-session.sh
```

---

## 5. Morning Proving Checklist

Use this checklist when resuming after an overnight autonomous run to verify
the remote channel is working end-to-end.

### Pre-Checks

- [ ] Steward session is running: `tmux has-session -t steward`
- [ ] Orchestrator pane is active (not stalled): capture and inspect pane
- [ ] Telegram plugin enabled: `claude plugins list | grep telegram`
- [ ] Kill switch on: `tmux show-environment -t steward STEWARD_TELEGRAM_ENABLED`

### Remote Round-Trip Test

1. **Outbound test:** From the orchestrator, send a message to Telegram:
   - Trigger a `/check-in` or monitor cycle that produces a HIGH item
   - Verify the alert appears on the operator's phone

2. **Inbound test:** Reply to the alert from Telegram:
   - Send `ack <prefix>` from the phone
   - Verify the orchestrator receives and processes the ack
   - Verify the item state changes in fleet_status.json

3. **Audit test:** Verify both directions were recorded:
   ```bash
   tail -5 .claude/runtime/audit_trail/remote_exchanges.jsonl | jq '.direction'
   ```
   Should show both `"outbound"` and `"inbound"` entries.

### Health Checks

- [ ] Controller projection fresh: check `generated_at` in fleet_status.json
- [ ] No stale HIGH/URGENT items lingering from overnight
- [ ] Push state reasonable: not hundreds of stale entries
- [ ] Audit trail growing: `wc -l .claude/runtime/audit_trail/remote_exchanges.jsonl`

### Quick Fixes

| Symptom | Fix |
|---------|-----|
| No Telegram messages | Check `STEWARD_TELEGRAM_ENABLED`, restart orchestrator pane |
| Alert spam | Check push state cooldown, ack items, increase cooldown |
| Ack not working | Check prefix length, verify item exists and is `open` |
| Stale projection | Run manual `reconcile()`, check monitor cron |
| Audit trail empty | Check hook registration in `.claude/settings.json` |
