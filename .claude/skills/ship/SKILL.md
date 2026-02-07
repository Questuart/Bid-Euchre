# Ship Workflow

Complete workflow for shipping a change from development through PR to merge.

## Steps

1. Run `make check` and ensure all tests/lint pass
2. Commit all changes with a descriptive message
3. Create a worktree if not already in one
4. Push branch and create PR on GitHub. Use the PR template
5. Wait for CI to pass, then merge the PR
6. Switch to main, pull latest
7. Clean up the worktree and remote branch
8. Update MEMORY.md with the merged PR number and status

## Usage

Invoke this skill with `/ship` when you're ready to ship your changes.

## Notes

- This workflow assumes you're working in a git worktree (not the main checkout)
- The PR will be created using the template from `.github/pull_request_template.md`
- CI must pass before merge - the skill will wait for this
- After merge, the worktree and remote branch are cleaned up automatically
- MEMORY.md is updated with the final PR number and merge status
