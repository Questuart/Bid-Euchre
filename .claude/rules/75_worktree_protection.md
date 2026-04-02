# Worktree Protection

> Steward worktrees are persistent lane infrastructure. They must never be
> removed, even if the branch's current PR has been merged.

## Protected Worktrees

These worktrees are permanent and must not be deleted:

**Platform pool:**
- `Bid-Euchre-steward-author`
- `Bid-Euchre-steward-author-b`
- `Bid-Euchre-steward-author-c`
- `Bid-Euchre-steward-author-d`

**Browser-game pool:**
- `Bid-Euchre-steward-brws-author-a`
- `Bid-Euchre-steward-brws-author-b`
- `Bid-Euchre-steward-brws-author-c`
- `Bid-Euchre-steward-brws-author-d`

**Analyst pool:**
- `Bid-Euchre-steward-analyst` (analyst-a)
- `Bid-Euchre-steward-analyst-b`
- `Bid-Euchre-steward-analyst-c`
- `Bid-Euchre-steward-analyst-d`

**Flex pool:**
- `Bid-Euchre-steward-flex-a`
- `Bid-Euchre-steward-flex-b`
- `Bid-Euchre-steward-flex-c`
- `Bid-Euchre-steward-flex-d`
- `Bid-Euchre-steward-flex-d`

**Control plane:**
- `Bid-Euchre-steward-review`
- `Bid-Euchre-steward-ops`

**Legacy (retired from active layout but still protected):**
- `Bid-Euchre-steward-author-scratch`

## Cleanup Rules

**Safe to remove:**
- Ephemeral `work-*` worktrees (0 commits ahead, clean working tree)
- Named `worktree-*` worktrees whose PR is merged and working tree is clean

**Never remove:**
- Any worktree matching `*steward*`
- Any worktree whose working tree is dirty (save diffs first)

**Before any `git worktree remove`:**
1. Verify the worktree is not in the protected list above
2. Verify the branch's PR is merged (if applicable)
3. Verify the working tree is clean (`git status --short` is empty)
4. If dirty, save changes (`git diff > /tmp/<name>.diff`) before removal

**Never run `git worktree prune`** — it removes stale entries indiscriminately,
including entries for worktrees that may have been temporarily unmounted.
