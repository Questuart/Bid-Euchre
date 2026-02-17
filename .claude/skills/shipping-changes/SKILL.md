---
name: shipping-changes
description: Ships a change from development through PR creation, CI verification, merge, and cleanup. Use when changes are ready to be committed, pushed, and merged into main.
---

# Ship Workflow

Complete workflow for shipping a change from development through PR to merge.

## Workflow

1. **Validate**: Run `make check` — all tests and lint must pass
2. **Commit**: Stage and commit all changes with a descriptive message
3. **Worktree check**: Verify you're in a worktree (not main checkout)
4. **Push and create PR**: Push branch, create PR using the template from `.github/pull_request_template.md`
5. **CI verification**: Wait for CI to pass
6. **Merge**: Merge the PR via `gh pr merge --squash --delete-branch`
7. **Update local**: `git checkout main && git pull origin main`
8. **Cleanup**: Remove the worktree and remote branch
9. **Record**: Update MEMORY.md with the merged PR number and status

## Error Handling

**`make check` fails:**
- Read the failure output, fix the issue, re-run
- Do not skip validation — iterate until passing

**CI fails after push:**
- Check CI output: `gh pr checks <PR_NUMBER>`
- Fix locally, commit, push again
- If CI failure is unrelated to your changes, note it and investigate

**Merge conflicts:**
- Rebase onto latest main: `git fetch origin && git rebase origin/main`
- Resolve conflicts, re-run `make check`, force-push the branch
- Verify PR is still valid before merging

**PR creation fails:**
- Verify branch is pushed: `git push -u origin <branch>`
- Check `gh auth status` for authentication issues

## Output Format

```markdown
## Ship Complete

- Commit: [short hash] [message]
- PR: #NNN [title] — merged
- Tests: N passing, lint clean
- MEMORY.md updated
- Worktree cleaned up
```

## Anti-Patterns to Avoid

- Shipping without running `make check` first
- Committing from main checkout instead of a worktree
- Merging with failing CI
- Forgetting to update MEMORY.md after merge
- Leaving orphaned worktrees or remote branches behind

## Notes

- This workflow assumes you're working in a git worktree (not the main checkout)
- CI must pass before merge — the skill will wait for this
- After merge, the worktree and remote branch are cleaned up automatically
