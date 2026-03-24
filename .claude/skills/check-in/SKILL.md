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

### Phase 1 — Inbox Poll (MANDATORY FIRST STEP)

1. **Read pending inbox messages:**
   ```bash
   uv run python scripts/internal/ops.py inbox --lane orchestrator --status pending
   ```

2. **Filter for high-priority message types** — process these BEFORE any other
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

3. **Acknowledge processed messages:**
   ```bash
   # Ack individual high-priority messages after acting on them
   uv run python scripts/internal/ops.py inbox ack <MSG_ID> --lane orchestrator

   # Bulk-ack low-priority informational messages
   uv run python scripts/internal/ops.py inbox ack-all --lane orchestrator --type ack
   ```

4. **Surface unacked HIGH alerts prominently.** If any `supervisor_alert` or
   `escalation` messages remain unacked from a previous cycle, flag them as
   overdue and prioritize response:
   ```
   WARNING: 3 unacked supervisor_alerts (oldest: 45min ago)
     - "Monitor: 3 HIGH, 0 warn, 14 info findings !"
     - "STALL: author-b no output for 20min"
     - "CONFLICT: PR #1556 has merge conflicts"
   ```

### Phase 2 — Lane Health

5. **Check dashboard state:**
   ```bash
   uv run python scripts/internal/ops.py --json dashboard --no-probe
   ```

6. **Inspect attention items and warnings.** Look for:
   - Lanes with no recent activity (potential stalls)
   - Dirty worktrees that need recovery
   - Blocked or overdue task packets

7. **Check active task packets:**
   ```bash
   uv run python scripts/internal/ops.py task list
   ```

### Phase 3 — PR and CI Health

8. **List open PRs:**
   ```bash
   gh pr list --state open --json number,title,headRefName,author
   ```

9. **Check for stuck PRs** — any PR open > 1 hour without CI progress or
   review verdict warrants investigation.

10. **Check recently merged PRs** for follow-up work:
    ```bash
    gh pr list --state merged --limit 5 --json number,title,mergedAt
    ```

### Phase 4 — Issue Triage

11. **Scan for new or updated issues:**
    ```bash
    gh issue list --state open --limit 10 --json number,title,labels,updatedAt
    ```

12. **Classify each** as: blocker to active work, next-wave candidate, or backlog.

### Phase 5 — Summary

13. **Produce a compact status block:**

    ```
    CHECK-IN @ <timestamp>
    ────────────────────────
    INBOX:  <N> pending (<M> HIGH-priority)
    LANES:  <N> active, <M> idle, <K> stalled
    PRs:    <N> open, <M> merged since last check
    ISSUES: <N> open (<M> new since last check)
    ALERTS: <list any unresolved HIGH alerts>
    NEXT:   <recommended action>
    ```

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
