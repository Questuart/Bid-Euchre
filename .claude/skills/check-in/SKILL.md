---
name: check-in
description: Periodic orchestrator status check — polls inbox, surfaces alerts, summarizes lane and PR health. Use during autonomous runs to maintain situational awareness.
---

# /check-in — Orchestrator Status Check

Periodic situational awareness snapshot for the orchestrator during autonomous
fleet runs. Designed to be invoked regularly (every 10-15 minutes or between
dispatch cycles) to catch alerts, stalls, and opportunities.

## When to Use

- During `/run-fleet` autonomous operation (referenced at line 204)
- After dispatching a wave of tasks, before planning the next wave
- When resuming after a break or context compaction
- Whenever you suspect lane stalls, missed alerts, or drift

## Critical Rule: Inbox First

**Always poll the orchestrator inbox BEFORE checking lane status, PRs, or
issues.** The overnight run of 2026-03-24 proved that ignoring the inbox
causes 25+ HIGH supervisor alerts to go unread for hours.

The inbox is the only channel through which ops, authors, and the review
lane can escalate to the orchestrator. Skipping it defeats the entire
monitoring infrastructure.

## Workflow

### Session Timing Rule

Record a single `fleet_start_time` at the beginning of the run and reuse it for
every later Telegram or remote status update. Do not hand-estimate elapsed
times.

When a check-in summary is relayed outside the local terminal:

1. Reuse the original UTC start timestamp for the run.
2. Compute `elapsed = now - fleet_start_time`.
3. Format it consistently as `T+<hours>h<minutes:02d>m`.

Examples:

- `T+0h05m`
- `T+1h20m`
- `T+2h00m`

### Phase 1 — Inbox Poll (MANDATORY FIRST STEP)

1. **Read pending inbox messages (priority-sorted):**
   ```bash
   uv run python scripts/internal/ops.py inbox --lane orchestrator --status pending --include-native --prioritized
   ```
   The `--include-native` flag imports any messages from the Claude native inbox
   into the message bus before listing, so nothing is missed.
   The `--prioritized` flag groups messages by tier: P0 (`supervisor_alert`,
   `recovery`) first, then P1 (`completion`, `escalation`, `blocker`), then
   P2 (`ack`, `progress`).

2. **Triage imported native inbox items first.** Native messages are imported
   as `progress` type (P2) by default, but may contain urgent content. Scan
   the P2 tier for messages with `source_transport: claude_native` — read
   their `native_text` and mentally re-classify before bulk-acking P2.

3. **Filter for high-priority message types** — process these BEFORE any other
   status checks:

   | Message Type | Priority | Action |
   |-------------|----------|--------|
   | `supervisor_alert` | **IMMEDIATE** | Read content, assess severity, plan response |
   | `recovery` | **IMMEDIATE** | Verify resolution, ack if confirmed |
   | `escalation` | **HIGH** | Investigate blocker, unblock or reassign |
   | `blocker` | **HIGH** | Author lane is stuck — provide guidance or reassign |
   | `completion` | NORMAL | Author finished task — verify PR, plan follow-up |
   | `ack` | LOW | Informational — bulk-ack |
   | `progress` | LOW | Informational — note and continue |

4. **Acknowledge processed messages:**
   ```bash
   # Ack individual high-priority messages after acting on them
   uv run python scripts/internal/ops.py inbox ack <MSG_ID> --lane orchestrator

   # Bulk-ack all remaining pending messages
   uv run python scripts/internal/ops.py inbox ack-all --lane orchestrator

   # Or selectively bulk-ack by summary pattern (regex)
   uv run python scripts/internal/ops.py inbox ack-all --lane orchestrator --filter-summary "Task received|progress"
   ```

5. **Surface unacked HIGH alerts prominently.** If any `supervisor_alert` or
   `escalation` messages remain unacked from a previous cycle, flag them as
   overdue and prioritize response:
   ```
   WARNING: 3 unacked supervisor_alerts (oldest: 45min ago)
     - "Monitor: 3 HIGH, 0 warn, 14 info findings !"
     - "STALL: author-b no output for 20min"
     - "CONFLICT: PR #1556 has merge conflicts"
   ```

### Phase 2 — Lane Health

6. **Check dashboard state:**
   ```bash
   uv run python scripts/internal/ops.py --json dashboard --no-probe
   ```

7. **Inspect attention items and warnings.** Look for:
   - Lanes with no recent activity (potential stalls)
   - Dirty worktrees that need recovery
   - Blocked or overdue task packets

8. **Check active task packets:**
   ```bash
   uv run python scripts/internal/ops.py task list
   ```

### Phase 2b — Branch Divergence Detection

> **Why:** Parallel author lanes branching off the same `origin/main` snapshot
> diverge as other PRs merge. Catching divergence early (before PR creation)
> avoids costly merge conflicts and wasted review cycles.

9. **For each active author lane with a dispatched task**, check how far its
   branch has diverged from `origin/main`:
   ```bash
   # From each lane's worktree, or using git directly:
   git fetch origin main
   git rev-list --count origin/main..<branch-name>   # commits ahead
   git rev-list --count <branch-name>..origin/main   # commits behind
   ```

10. **Flag divergence warnings** using these thresholds:

    | Commits Behind `origin/main` | Severity | Action |
    |------------------------------|----------|--------|
    | 0 | OK | No action needed |
    | 1–5 | INFO | Note in check-in summary |
    | 6–15 | WARN | Recommend lane rebase before PR |
    | 16+ | HIGH | Send rebase nudge to the lane |

    When severity is WARN or HIGH, include it in the check-in summary:
    ```
    DIVERGENCE:
      author-a: 3 behind (OK)
      author-b: 12 behind (WARN — recommend rebase)
      author-d: 22 behind (HIGH — rebase nudge sent)
    ```

11. **Send rebase nudge** to lanes at HIGH divergence:
    ```bash
    uv run python scripts/internal/ops.py message send \
      --from orchestrator --to <lane> --type escalation \
      --priority high \
      --summary "Branch diverged 16+ commits from main — rebase before continuing"
    ```

12. **Check for merge conflict potential** — if two active lanes are touching
    overlapping files (visible from their task packet `scope_declared`), flag
    this as a potential conflict even at low divergence counts.

### Phase 3 — PR and CI Health

9. **List open PRs:**
   ```bash
   gh pr list --state open --json number,title,headRefName,author
   ```

10. **Check for stuck PRs** — any PR open > 1 hour without CI progress or
   review verdict warrants investigation.

11. **Check recently merged PRs** for follow-up work:
    ```bash
    gh pr list --state merged --limit 5 --json number,title,mergedAt
    ```

### Phase 4 — Issue Triage

12. **Scan for new or updated issues:**
    ```bash
    gh issue list --state open --limit 10 --json number,title,labels,updatedAt
    ```

13. **Classify each** as: blocker to active work, next-wave candidate, or backlog.

### Phase 5 — Summary

14. **Produce a compact status block:**

    ```
    CHECK-IN @ <timestamp>
    ────────────────────────
    INBOX:      <N> pending (<M> HIGH-priority)
    LANES:      <N> active, <M> idle, <K> stalled
    DIVERGENCE: <N> OK, <M> WARN, <K> HIGH (list HIGH lanes)
    PRs:        <N> open, <M> merged since last check
    ISSUES:     <N> open (<M> new since last check)
    ALERTS:     <list any unresolved HIGH alerts>
    NEXT:       <recommended action>
    ```

15. **If you send the summary to Telegram or another remote channel,**
   prefix it with the computed elapsed value from `fleet_start_time`, not a
   manually estimated string.

## Integration with /run-fleet

The `/run-fleet` skill references `/check-in` as the periodic status
summarizer. During autonomous operation:

- Run `/check-in` at least once per dispatch cycle
- Run `/check-in` immediately after any lane recovery or escalation
- Run `/check-in` before planning a new wave

## Anti-Patterns

- Checking lane status or PRs without reading the inbox first
- Bulk-acking supervisor_alerts without reading their content
- Ignoring `recovery` messages (they confirm whether a previously-reported
  problem has been resolved)
- Running `/check-in` without acting on HIGH-priority findings
- Treating the check-in as a formality instead of a decision point

## References

- `.claude/skills/run-fleet/SKILL.md` — autonomous fleet orchestration
- `.claude/skills/monitor-pr/SKILL.md` — detailed PR health checks
- `.claude/agents/steward-orchestrator.md` — orchestrator role and message bus
- `.claude/agents/steward-ops.md` — ops monitor and supervisor alerts
- `src/bid_euchre/ops/message_bus.py` — inbox message types and lifecycle
- Issue #1569 — root cause: orchestrator missed 25+ HIGH alerts during
  overnight run because inbox was never polled
