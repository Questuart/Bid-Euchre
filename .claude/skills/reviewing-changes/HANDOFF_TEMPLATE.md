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
- Status: [COMPLETE / PENDING / NOT AVAILABLE / UNAVAILABLE_LIMIT]
- Response channel: [inline_review / comment / none]
- Responded: [yes/no]
- Latency: [N seconds / timeout / early_exit]
- Format compliant: [yes/no / N/A]
- Findings parseable: [yes/no / N/A]
- Finding counts: [CRITICAL: N, WARNING: N, NIT: N / unparseable / N/A]
- Checks reported: [list of check IDs / none]
- Error message: [verbatim error if UNAVAILABLE_LIMIT, omit otherwise]
- CLI fallback used: [yes / no / failed]
- CLI fallback findings: [P0: N, P1: N, P2: N / N/A]
- Summary: [1-3 sentence summary of Codex findings, or "Awaiting response" / "Usage limit — CLI fallback used"]

### Needs Human Decision
- [Each BLOCK item with context on why it needs judgment]
- [Each WARN item the agent couldn't resolve]
(or "None — ready to merge.")

### Current State
- Worktree: `[worktree-path]`
- Branch: `[branch]` → PR #[number]
- make check: [PASSED / FAILED]
- Commit status: [`success` / `failure` / `not published`]
- Codex review: [PENDING / COMPLETE / NOT AVAILABLE / UNAVAILABLE_LIMIT]
- Verdict: [READY FOR CODEX/HUMAN REVIEW / NEEDS ATTENTION]

### Context for Next Agent
[2-3 sentences: What this PR does, any gotchas from the review,
what the next agent needs to know.]
---
```
