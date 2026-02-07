# PR Stack - Autonomous Stacked PR Merge Pipeline

Merge stacked/dependent PRs in dependency order with automatic conflict resolution, recreation, and cleanup.

## Purpose

Stacked PRs are a recurring workflow pattern that causes significant friction:
- GitHub auto-closes downstream PRs when base branches are deleted
- Rebase conflicts require manual resolution
- Each PR needs CI verification before merge
- Cleanup is tedious (branches, worktrees, MEMORY.md)

This skill automates the entire pipeline end-to-end without human intervention.

## Workflow

For each PR in the dependency-ordered list:

### 1. Rebase onto Latest Main
- Fetch latest `origin/main`
- Rebase PR branch onto `origin/main`
- **Conflict resolution strategy**:
  - Prefer PR's changes for files it modified
  - Prefer main's changes for other files
  - If ambiguous, diagnose and fix (don't ask)

### 2. Verify Quality
- Run `make check` (full test suite + lint)
- If failures occur:
  - Read failure output
  - Fix the issue
  - Re-run `make check`
  - Iterate until passing

### 3. Merge PR
- Use `gh pr merge --squash --delete-branch`
- Wait for merge to complete
- Verify merge succeeded

### 4. Handle Auto-Closed Downstream PRs
- Check if any downstream PRs were auto-closed
- For each auto-closed PR:
  - Recreate with same content
  - Target correct new base (usually `main`)
  - Preserve original PR description
  - Link to original PR number

### 5. Post-Merge (After All PRs)
- `git checkout main && git pull origin main`
- Delete all merged branches: `git branch -d <branches>`
- Remove all worktrees: `git worktree remove <paths>`
- Update MEMORY.md with final PR numbers and status

## Usage

```bash
/pr_stack #301 #302 #303 #304
```

Example prompts:
- "I have a stack of PRs that need to be merged in dependency order: #311, #312, #313, #314, #315. Execute the full merge pipeline."
- "Merge PR stack #320-#323 in order. Auto-fix any failures, recreate auto-closed PRs, clean up everything."

## Conflict Resolution Strategy

When rebasing encounters conflicts:

1. **For files in the PR's changeset**: Use PR's version (ours)
2. **For files not in the PR's changeset**: Use main's version (theirs)
3. **For ambiguous cases**:
   - Read both versions
   - Apply the most recent logical change
   - Prefer preserving functionality
   - Add comments if uncertain

## Error Handling Philosophy

**Never stop to ask the user.** This skill operates autonomously:

- ❌ "Should I proceed?" → Just proceed
- ❌ "How should I resolve this conflict?" → Apply strategy above
- ❌ "The test failed, what do I do?" → Read output, fix, re-run
- ✅ Diagnose, fix, continue

Only stop if truly unrecoverable (e.g., GitHub API down, auth failure).

## Parallel Operations

Where possible, use sub-tasks for parallel work:
- Checking multiple PRs for auto-close status
- Verifying CI status across multiple PRs
- Running independent quality checks

## Output Format

Real-time progress tracking:

```markdown
## PR Stack Merge Pipeline

### PR #301 - [title]
✅ Rebased onto main (3 conflicts resolved)
✅ make check passing
✅ Merged and branch deleted

### PR #302 - [title]
✅ Rebased onto main (no conflicts)
⚠️  make check failed (unused import) - fixed
✅ Merged and branch deleted
⚠️  PR #303 auto-closed, recreating as #325

### PR #303 → #325 - [title]
✅ Recreated targeting main
✅ Rebased (no conflicts)
✅ make check passing
✅ Merged and branch deleted

---

## Final Status
✅ 3 PRs merged: #301, #302, #325
✅ Local main updated
✅ All branches deleted
✅ All worktrees removed
✅ MEMORY.md updated

Total time: 8 minutes
```

## Anti-Patterns to Avoid

❌ Stopping to ask user for decisions
❌ Skipping `make check` to save time
❌ Ignoring auto-closed PRs (leads to lost work)
❌ Leaving worktrees/branches behind
❌ Forgetting MEMORY.md update

## Recovery from Failures

If a step fails:
1. Read the error message carefully
2. Check file states (`git status`, `git diff`)
3. Apply appropriate fix
4. Retry the step
5. Continue pipeline

Common failures and fixes:
- **Rebase conflict**: Apply resolution strategy
- **Test failure**: Fix the code, not the test
- **Merge failure**: Check GitHub status, retry
- **Auto-close**: Recreate PR immediately

## Benefits

- ✅ Handles 8-PR stacks in minutes, not hours
- ✅ No manual PR recreation needed
- ✅ Automatic conflict resolution
- ✅ Full quality gates maintained
- ✅ Complete cleanup (no orphaned worktrees)
- ✅ Zero user intervention required

## Notes

- This skill is designed for autonomous operation
- Best used with `/pr_chunk` for creating the stack
- Requires GitHub CLI (`gh`) authenticated
- Works with your worktree-only workflow
- Pairs well with `/memory_ref` to verify final state
