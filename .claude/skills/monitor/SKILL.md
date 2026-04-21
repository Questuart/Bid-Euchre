---
name: monitor
description: Runs a single ops monitoring cycle — lane health, stall detection, alert push, and fleet reconciliation. Use from the ops lane via durable cron (/loop 8m /monitor).
---

# /monitor -- Ops Monitoring Cycle

Run a single ops monitoring sweep: check lane health, detect stalls, push
alerts, and reconcile fleet state. Designed for durable cron invocation
(`/loop 8m /monitor`) that survives `/clear`.

## When to Use

- You are the ops lane and need to run a periodic monitoring sweep
- The orchestrator has set up `/loop 8m /monitor` as a durable cron
- You want a one-shot health sweep of the fleet
- After a `/clear`, the ops lane needs to resume monitoring

## Arguments

None. All options use sensible defaults for production monitoring.

For testing/debugging, invoke the CLI directly with flags:
```bash
uv run python scripts/internal/ops.py monitor --skip-pr-check --no-notify
```

## Workflow

### Step 1 -- Run the monitoring cycle

```bash
uv run python scripts/internal/ops.py monitor
```

This single command performs all monitoring sub-tasks:
- **Lane health scan:** Checks all registered worktrees for dirty state, stale
  branches, and inactive sessions
- **PR status check:** Queries GitHub for open PRs and their CI/review status
- **Stall detection:** Identifies lanes with permission prompts or stuck
  processes, attempts auto-recovery (re-nudge)
- **Alert push:** Sends supervisor alerts for critical findings and pushes
  urgent alerts via Telegram (if configured)
- **Fleet reconciliation:** Updates `fleet_status.json` controller projection
  with current lane states, task assignments, and health metrics
- **Auto-dispatch:** Dispatches approved task packets to idle lanes (if any
  are queued)

### Step 2 -- Interpret findings

The monitor outputs a structured summary:

| Finding Type | Severity | Action |
|-------------|----------|--------|
| Lane stall (permission prompt) | HIGH | Auto-recovery attempted; escalate if retry fails |
| PR CI failure | MEDIUM | Report to orchestrator inbox |
| Lane idle > 30min | LOW | Candidate for new task dispatch |
| Telegram push failure | LOW | Logged; retry next cycle |

If the cycle output or a downstream step needs more detail on a specific
lane's state, prefer the heartbeat-aware classifier over `dashboard`:

```bash
# Subprocess-free — safe for hook / batch contexts
uv run python scripts/internal/ops.py lane status --all --no-process-tree
```

The `--no-process-tree` flag skips the tmux/pgrep reconciler and relies on
Signal 0 (the heartbeat file written by the PR #2686 writer hook) plus the
cached fallback evidence, per PR #2695's hook-safe design. Use the full
(non-`--no-process-tree`) variant only from an interactive shell; the
reconciler spawns subprocesses that are inappropriate for a monitoring
cron. `dashboard`'s `[stale!]` flag still uses the older 30-minute
`last_active` heuristic (#2415 F1) — do not consume it for per-lane
liveness classification.

### Step 3 -- Escalate if needed

If critical findings are detected, the monitor sends supervisor alerts to the
orchestrator inbox automatically. For manual escalation:

```bash
uv run python scripts/internal/ops.py message send \
  --from ops --to orchestrator --type supervisor_alert \
  --priority high \
  --summary "Monitor found: <description>"
```

## CLI Flags Reference

| Flag | Effect |
|------|--------|
| `--skip-pr-check` | Skip `gh pr list` (for offline/testing) |
| `--no-notify` | Don't send findings to orchestrator inbox |
| `--no-recovery` | Report stalls but don't attempt re-nudge |
| `--no-auto-dispatch` | Don't dispatch queued tasks to idle lanes |
| `--no-reconcile` | Skip fleet_status.json update |
| `--no-push` | Disable Telegram alert push |

## Durable Cron Setup

The ops lane should run this skill on a repeating schedule:

```
/loop 8m /monitor
```

This survives `/clear` because the skill is registered in `.claude/skills/`
and the cron job references it by name, not by inline command.

## Gotchas

- This skill is for the **ops lane only**. The orchestrator uses `/fleet-check`
  or `/check-in` for its own monitoring.
- The monitor cycle takes 10-30s depending on fleet size and GitHub API latency.
- If `gh` CLI is not authenticated, `--skip-pr-check` avoids blocking the
  entire cycle.
- Telegram push requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars.

## References

- `scripts/internal/ops.py monitor` -- CLI implementation
- `scripts/internal/ops.py lane status` -- heartbeat-aware per-lane
  classifier (PR #2695, consumer for the PR #2686 writer)
- `.claude/skills/check-in/SKILL.md` -- orchestrator-side periodic check
- `.claude/skills/fleet-check/SKILL.md` -- orchestrator consolidated cron
- `.claude/rules/deferred/60_review_gate.md` -- review status context
- Issue #2415 -- heartbeat infrastructure (F1 failure mode: working lanes
  mis-classified as stale during long validation runs)
