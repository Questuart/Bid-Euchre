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

2. **Summarize key context** in three parts:
   - **Last completed**: What was most recently finished (PRs merged, features shipped, bugs fixed)
   - **PR status**: Which PRs are open, merged, or in progress (with PR numbers)
   - **Next planned work**: What's queued up or in progress

3. **Present summary** to the user in a clear, scannable format

4. **Ask for direction**: "What would you like to work on?"

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

## Notes

- This skill should be invoked at session start for best results
- MEMORY.md is updated after major completions (via `/shipping-changes` workflow)
