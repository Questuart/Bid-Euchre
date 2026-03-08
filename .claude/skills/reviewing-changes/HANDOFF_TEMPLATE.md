# Handoff Template

Generate this block at the end of every `/reviewing-changes` run. Replace all `[bracketed]` placeholders with actual values from the review.

The user can `/copy` this into a new Claude Code session to resume work.

---

```markdown
---
## Session Handoff — [branch-name]

**PR:** #[number] — [title] — [url]

### What Was Done
- [1-3 bullet summary derived from diff and commit messages]

### Files Changed
- `[path/to/file.py]` — [one-line description]
- ...

### Issues Encountered
- [Any test failures, lint issues, or complications during implementation]
(or "None.")

### Review Findings
- Blockers: [N] ([list each with file:line and rule ID])
- Warnings: [N] ([list each briefly])
- Follow-up issues: [N created] (or "none needed")
  - [issue URL] — [category]
  - ...

### Codex Review Metadata
- Status: [COMPLETE / PENDING / NOT AVAILABLE]
- Response channel: [inline_review / comment / none]
- Responded: [yes/no]
- Latency: [N seconds / timeout]
- Format compliant: [yes/no]
- Findings parseable: [yes/no]
- Finding counts: [CRITICAL: N, WARNING: N, NIT: N / unparseable]
- Checks reported: [list of check IDs / none]
- Summary: [1-3 sentence summary of Codex findings, or "Awaiting response"]

### Needs Human Decision
- [Each BLOCK item with context on why it needs judgment]
- [Each WARN item the agent couldn't resolve]
(or "None — ready to merge.")

### Current State
- Worktree: `[worktree-path]`
- Branch: `[branch]` → PR #[number]
- make check: [PASSED / FAILED]
- Commit status: [`success` / `failure` / `not published`]
- Codex review: [PENDING / COMPLETE / NOT AVAILABLE]
- Verdict: [READY FOR CODEX/HUMAN REVIEW / NEEDS ATTENTION]

### Context for Next Agent
[2-3 sentences: What this PR does, any gotchas from the review,
what the next agent needs to know.]
---
```
