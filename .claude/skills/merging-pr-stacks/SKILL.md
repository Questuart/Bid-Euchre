---
name: merging-pr-stacks
description: Merges stacked/dependent PRs in dependency order with automatic conflict resolution, PR recreation, and cleanup. Use when multiple PRs form a dependency chain and need to be merged sequentially.
disable-model-invocation: true
---

# Autonomous Stacked PR Merge Pipeline

Merge stacked/dependent PRs in dependency order with automatic conflict resolution, recreation, and cleanup.

## Workflow

For each PR in the dependency-ordered list:

### 1. Rebase onto Latest Main
- Fetch latest `origin/main`
- Rebase PR branch onto `origin/main`
- **Conflict resolution**: Prefer PR's changes for files it modified; prefer main's changes otherwise. If ambiguous, diagnose and fix (don't ask).

### 2. Verify Quality
- Run `make check` (full test suite + lint)
- If failures: read output → fix → re-run → iterate until passing

### 3. Merge PR
- Use `gh pr merge --squash --delete-branch`
- Verify merge succeeded

### 4. Handle Auto-Closed Downstream PRs
- Check if downstream PRs were auto-closed
- For each: recreate with same content, target `main`, preserve description, link to original

### 5. Post-Merge (After All PRs)
- `git checkout main && git pull origin main`
- Delete all merged branches: `git branch -d <branches>`
- Remove all worktrees: `git worktree remove <paths>`
- Update MEMORY.md with final PR numbers and status

## Error Handling Philosophy

**Never stop to ask the user.** This skill operates autonomously:
- "Should I proceed?" → Just proceed
- "How should I resolve this conflict?" → Apply resolution strategy
- "The test failed, what do I do?" → Read output, fix, re-run

Only stop if truly unrecoverable (e.g., GitHub API down, auth failure).

Common failures and fixes:
- **Rebase conflict**: Apply resolution strategy above
- **Test failure**: Fix the code, not the test
- **Merge failure**: Check GitHub status, retry
- **Auto-close**: Recreate PR immediately

## Output Format

```markdown
## PR Stack Merge Pipeline

### PR #301 - [title]
Rebased (3 conflicts resolved) → make check passing → Merged

### PR #302 - [title]
Rebased (no conflicts) → fixed unused import → Merged
PR #303 auto-closed, recreated as #325

### PR #325 - [title]
Rebased → make check passing → Merged

## Final Status
3 PRs merged, local main updated, all branches/worktrees cleaned, MEMORY.md updated.
```

## Anti-Patterns to Avoid

- Stopping to ask user for decisions
- Skipping `make check` to save time
- Ignoring auto-closed PRs (leads to lost work)
- Leaving worktrees/branches behind
- Forgetting MEMORY.md update

## Notes

- Requires GitHub CLI (`gh`) authenticated
- Best used with `/chunking-prs` for creating the stack
- Pairs well with `/recovering-context` to verify final state
