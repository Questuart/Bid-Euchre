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
- [Any complications during implementation]
(or "None.")

### Review Loop
- Run ID: [pr_<number>_<sha[:7]>]
- State dir: `.claude/runtime/review_loops/pr_<number>/`
- Initial SHA: [head_sha]
- Status: SPAWNED (async — check GitHub commit status for final result)
- Recovery: `python scripts/internal/review_driver.py --pr <number> --trigger manual`

### Needs Human Decision
- [Any items requiring judgment before merge]
(or "None — review loop will publish final status.")

### Current State
- Worktree: `[worktree-path]`
- Branch: `[branch]` → PR #[number]
- Commit status: `pending` (review loop in progress)
- Verdict: DISPATCHED — review loop running asynchronously

### Context for Next Agent
[2-3 sentences: What this PR does, what the review loop will check,
what the next agent needs to know.]
---
```
