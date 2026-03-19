---
name: managing-worktrees
description: Manages git worktrees: creation, cleanup, and protection rules. Use when creating new worktrees, cleaning up after merges, or checking worktree status.
---

# Worktree Management Guide

All code changes in this repo MUST happen in worktrees, never on main. This skill covers creation, cleanup, and the protection rules for persistent worktrees.

## Creating a Worktree

```bash
git fetch origin main
git worktree add ../Bid-Euchre-<name> -b <branch> origin/main
```

Convention: worktree directory name should match the branch name for discoverability.

## Listing Worktrees

```bash
git worktree list
```

Check if a specific worktree is clean:
```bash
git -C ../Bid-Euchre-<name> status --short
```

## Protected Worktrees — NEVER Remove

These are persistent steward lane infrastructure:

```
Bid-Euchre-steward-author
Bid-Euchre-steward-author-b
Bid-Euchre-steward-author-c
Bid-Euchre-steward-author-d
Bid-Euchre-steward-author-scratch
Bid-Euchre-steward-review
Bid-Euchre-steward-ops
```

**Rule:** Any worktree matching `*steward*` is permanent and must never be removed.

## Safe Cleanup Protocol

Before removing ANY worktree, follow this 3-step protocol:

1. **Check the protected list** — is it a steward worktree? If yes, STOP.
2. **Verify the PR is merged** (if applicable):
   ```bash
   gh pr view <PR> --json state
   ```
3. **Verify the working tree is clean**:
   ```bash
   git -C <path> status --short
   ```
   If dirty, save changes first: `git -C <path> diff > /tmp/<name>.diff`

Then remove:
```bash
git worktree remove ../Bid-Euchre-<name>
git branch -d <branch>
```

## Gotchas

- **NEVER** run `git worktree prune` — it removes stale entries indiscriminately, including temporarily unmounted worktrees
- **NEVER** remove any worktree matching `*steward*` — these are persistent lane infrastructure
- Always save diffs before removing dirty worktrees: `git -C <path> diff > /tmp/<name>.diff`
- The UserPromptSubmit hook auto-creates worktrees when you try to edit on main — don't fight it, just use the created worktree
- Worktree names should match branch names for discoverability
- After merging, clean up BOTH the worktree AND the local branch

## References

- `.claude/rules/75_worktree_protection.md` — Authoritative protection rules and cleanup policy
