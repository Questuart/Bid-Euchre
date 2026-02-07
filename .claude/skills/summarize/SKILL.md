# Summarize — PR Session Summary & Lessons Learned

Generate a structured summary of PRs completed in this session, then commit lessons learned to auto memory.

## When to Use

Invoke `/summarize` at the end of a session after PRs have been created, merged, or completed. Produces a consistent, scannable report and persists lessons for future sessions.

## Workflow

### 1. Gather PR Data

- Read MEMORY.md from auto memory directory for session context
- Identify all PRs created or merged in this session (from conversation history or MEMORY.md)
- For each PR, collect: PR number, title, branch, files changed, test counts, `make check` status

### 2. Generate Summary Report

Output the following **exact template** (fill in values, omit sections that don't apply):

```markdown
## Session Summary

### Goal
[1-2 sentences describing the overarching objective of this session's work]

### PRs Completed

| PR | Title | Files | Tests | Status |
|----|-------|-------|-------|--------|
| #NNN | short title | N files | N new | make check passing |

### What Was Done
- [Bullet per PR: what it adds/changes, key implementation detail]

### Key Outcomes
- [Quantitative results: total new tests, new functions, new suites, etc.]
- [Qualitative results: what's now possible that wasn't before]

### Lessons Learned
- [Things that went wrong, took longer than expected, or surprised you]
- [Patterns discovered that should be reused]
- [Anti-patterns to avoid next time]

### Recommended Merge Order
[If multiple PRs: ordered list with rationale. If single PR: "N/A"]

### Follow-Up Work
- [Any TODO items, known gaps, or next steps discovered during implementation]
```

### 3. Commit Lessons to Memory

After generating the summary, **automatically** update auto memory:

1. **Read** the current MEMORY.md
2. **Check** if a "Lessons Learned" or relevant topic file exists (e.g., `memory/patterns.md`)
3. **Append** any new lessons to the appropriate section:
   - Anti-patterns go under `### Anti-Patterns to Avoid` in MEMORY.md
   - Workflow patterns go under `### Key Patterns Learned` in MEMORY.md
   - If a lesson is specific to a subsystem, create/update a topic file and link from MEMORY.md
4. **Deduplicate**: Don't add lessons that are already recorded
5. **Confirm** to the user which lessons were persisted and where

## Notes

- The summary is output as chat text (not written to a file) unless the user requests it saved
- Lessons are always committed to auto memory regardless
- If no lessons were learned, say so explicitly rather than inventing filler
- Keep lessons concrete and actionable — "use PATH=$(pwd)/.venv/bin:$PATH for commits in worktrees" not "remember to set up PATH"
- When multiple PRs touch the same file, note potential merge conflicts in Follow-Up Work
