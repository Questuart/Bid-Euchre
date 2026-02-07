# Memory Ref - Session Context Recovery

Start every session by recovering project context from MEMORY.md before beginning work.

## Purpose

Ensure Claude has full context of project state, recent work, and next steps at the start of each session. This prevents redundant questions and maintains continuity across sessions.

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

## Usage

Invoke with `/memory_ref` at the start of any session, or when resuming work after a break. This skill ensures you never lose context between sessions.

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

## Benefits

- ✅ Eliminates "what were we working on?" questions
- ✅ Prevents duplicate PRs or forgotten work
- ✅ Surfaces blockers or follow-ups immediately
- ✅ Maintains project momentum across sessions

## Notes

- This skill should be invoked at session start for best results
- MEMORY.md is updated after major completions (via `/ship` workflow)
- Consider using this automatically via a SessionStart hook
