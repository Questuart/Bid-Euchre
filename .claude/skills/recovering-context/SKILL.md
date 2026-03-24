---
name: recovering-context
description: Recovers project context from MEMORY.md at session start, presenting recent completions, PR status, and next steps. Use at the beginning of any session or when resuming work after a break.
---

# Session Context Recovery

Start every session by recovering project context from MEMORY.md before beginning work.

## Workflow

1. **Read MEMORY.md** from the auto memory directory
   - Load the complete project memory file
   - Parse current project state and recent completions

2. **Scan inbox for carry-forward alerts** (orchestrator lanes only):
   ```bash
   uv run python scripts/internal/ops.py inbox --lane orchestrator --status pending
   ```
   If unacked P0/P1 messages exist from a previous session, surface them
   **before any other work**. These represent conditions the previous session
   failed to address — merge conflicts, lane stalls, supervisor alerts, or
   escalations that were never processed.

   Priority classification:
   - **P0 (urgent):** `supervisor_alert`, `recovery` — surface immediately
   - **P1 (high):** `completion`, `escalation`, `blocker` — surface before planning
   - **P2 (normal/low):** `ack`, `progress` — note in summary

   If the inbox command fails (e.g., state machine bug), note the failure and
   proceed — do not block session recovery on inbox availability.

3. **Summarize key context** in three parts:
   - **Last completed**: What was most recently finished (PRs merged, features shipped, bugs fixed)
   - **PR status**: Which PRs are open, merged, or in progress (with PR numbers)
   - **Next planned work**: What's queued up or in progress

4. **Present summary** to the user in a clear, scannable format.
   If carry-forward alerts were found in step 2, present them prominently
   at the top of the summary:
   ```
   ⚠ CARRY-FORWARD ALERTS (from previous session)
   - [N] unacked supervisor_alerts (oldest: <age>)
   - [N] unacked escalations
   → Process these before starting new work.
   ```

5. **Ask for direction**: "What would you like to work on?"

## Output Format

```markdown
## Project Context (from MEMORY.md)

### Recently Completed
- PR #XXX: [description] - merged YYYY-MM-DD
- PR #YYY: [description] - merged YYYY-MM-DD

### Current PR Status
- PR #ZZZ: [description] - open, CI passing
- No other open PRs

### Next Planned Work
- [Next work item from memory]
- [Follow-up item]

---

What would you like to work on?
```

## Error Handling

- **MEMORY.md missing**: Report that no memory file exists. Offer to create one by scanning recent git history (`git log --oneline -20`) and open PRs (`gh pr list`).
- **MEMORY.md empty**: Report empty state. Bootstrap context from git log and open PRs as above.
- **MEMORY.md corrupted/unparseable**: Report the issue, show raw contents, and offer to rebuild from git history.

## Anti-Patterns to Avoid

- Skipping memory recovery and asking the user "what are we working on?" from scratch
- Inventing context that isn't in MEMORY.md
- Presenting stale PR statuses without checking (if uncertain, verify with `gh pr view`)
- Dumping the entire MEMORY.md raw instead of summarizing

## Gotchas

- MEMORY.md has a 200-line loading limit — lines after 200 are truncated; keep MEMORY.md as a concise index with details in topic files
- MEMORY.md may be stale if the last session didn't update it — cross-check with `git log --oneline -10` for recent PRs
- PR statuses in MEMORY.md are snapshots — verify with `gh pr view <N> --json state` if acting on them
- Topic memory files (e.g., `memory/pr_history.md`) may contain more detailed context than MEMORY.md itself
- Don't dump raw MEMORY.md to the user — summarize the three key parts (completed, status, next)

## Notes

- This skill should be invoked at session start for best results
- MEMORY.md is updated after major completions (via `/shipping-changes` workflow)
