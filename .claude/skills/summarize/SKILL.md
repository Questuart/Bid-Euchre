# Summarize — PR Session Summary, Lessons Learned & Review

Generate a structured summary of PRs completed in this session, commit lessons learned to auto memory, then launch a reviewer agent to verify the work.

## When to Use

Invoke `/summarize` at the end of a session after PRs have been created, merged, or completed. Produces a consistent, scannable report, persists lessons for future sessions, and kicks off an automated review.

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

After the summary is generated and lessons are committed, spawn a **reviewer agent** using the Task tool (`subagent_type: general-purpose`) to verify the session's work. Pass the full summary text as context.

**Agent prompt template** (fill in the `{...}` placeholders from the summary):

```
You are a code reviewer for the Bid Euchre project. Verify that the following
session work was completed correctly. Do NOT make any code changes — this is
a read-only review.

## Session Summary to Review
{paste the full summary from Step 2 here}

## Review Checklist

For EACH PR listed above, perform these checks:

### A. Merge State Verification
- Run: `gh pr view {PR_NUMBER} --json state,mergeCommit,title`
- Confirm state matches what the summary claims (merged/open)
- If merged, confirm merge commit exists on main

### B. Code Presence on Main
- Run: `git log --oneline -20` to see recent commits
- For each PR, verify the squash-merge commit message appears
- Spot-check 1-2 key files per PR to confirm the code is present:
  - Read the file and verify the new function/class/change exists
  - Check that imports are wired correctly

### C. Test Coverage
- Run: `uv run python -m pytest tests/unit/test_chart_generators.py -v --tb=short 2>&1 | tail -30`
  (or the relevant test file for the PR)
- Confirm the new tests listed in the summary actually exist and pass
- Verify test count matches what the summary claims

### D. Integration Sanity
- Run: `make check` from the project root
- Confirm all checks pass (repo-lint, ruff, pytest, notebook-check)
- If any failures, report them with full error output

### E. Review Checklist (from docs/02_agent/REVIEW_CHECKLIST.md)
For each PR, verify:
- [ ] No generated artifacts committed under data/runs/ or data/reports/
- [ ] Scope is focused (one concept per PR)
- [ ] New behavior has matching tests
- [ ] No import boundary violations (src/ must not import experiments/)

### F. MEMORY.md Consistency
- Read the auto memory file at:
  /Users/claude_runner/.claude/projects/-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre/memory/MEMORY.md
- Confirm PR numbers and status match what was actually merged
- Check that lessons learned were persisted (not just claimed)

## Output Format

Produce a review report with this structure:

### Review Results

| PR | Merge | Code | Tests | Checklist | Verdict |
|----|-------|------|-------|-----------|---------|
| #NNN | pass/fail | pass/fail | pass/fail | pass/fail | PASS/FAIL |

### Issues Found
- [List any discrepancies, missing code, failing tests, or summary inaccuracies]
- If none: "No issues found."

### make check Result
- [PASS/FAIL with summary line count: "N tests passed, 0 failed"]
```

**Agent configuration:**
- Use `subagent_type: general-purpose`
- Do NOT run in background — wait for the review result
- The reviewer must work from the main checkout (read-only, no edits)
- If the reviewer finds issues, present them to the user for action

## Notes

- The summary is output as chat text (not written to a file) unless the user requests it saved
- Lessons are always committed to auto memory regardless
- If no lessons were learned, say so explicitly rather than inventing filler
- Keep lessons concrete and actionable — "use PATH=$(pwd)/.venv/bin:$PATH for commits in worktrees" not "remember to set up PATH"
- When multiple PRs touch the same file, note potential merge conflicts in Follow-Up Work
- The reviewer agent is read-only — it must NEVER edit files, create commits, or push code
- If `make check` is already known to pass from the session, the reviewer can skip re-running it and note "verified earlier in session" — but should still run it if any doubt exists
- For large sessions (5+ PRs), the reviewer may spot-check a subset rather than exhaustively verifying every file, but must check all merge states and test counts
