---
name: summarizing-sessions
description: Generates a structured summary of PRs completed in a session, commits lessons learned to auto memory, and launches a reviewer agent to verify the work. Use at the end of a session after PRs have been created or merged.
disable-model-invocation: true
---

# PR Session Summary, Lessons Learned & Review

Generate a structured summary of PRs completed in this session, commit lessons learned to auto memory, then launch a reviewer agent to verify the work.

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
| #NNN | short title | N files | N new | merged / open |

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

### 4. Launch Review Agent

After the summary is generated and lessons are committed, spawn a **reviewer agent** using the Agent tool (`subagent_type: general-purpose`) to verify the session's work. Pass the full summary text as context.

**Agent prompt template** — see [REVIEWER_TEMPLATE.md](REVIEWER_TEMPLATE.md) for the full reviewer agent prompt.

**Agent configuration:**
- Use `subagent_type: general-purpose`
- Do NOT run in background — wait for the review result
- The reviewer must work from the main checkout (read-only, no edits)
- If the reviewer finds issues, present them to the user for action

## Anti-Patterns to Avoid

- Inventing lessons learned when nothing notable happened (say "no lessons" explicitly)
- Writing vague lessons ("remember to test things") instead of specific ones ("use `PATH=$(pwd)/.venv/bin:$PATH` for commits in worktrees")
- Skipping the reviewer agent to save time
- Claiming PRs are merged without verifying via `gh pr view`
- Writing the summary to a file unless the user requests it (output as chat text)

## Notes

- If no lessons were learned, say so explicitly rather than inventing filler
- When multiple PRs touch the same file, note potential merge conflicts in Follow-Up Work
- The reviewer agent is read-only — it must NEVER edit files, create commits, or push code
- For large sessions (5+ PRs), the reviewer may spot-check a subset rather than exhaustively verifying every file
