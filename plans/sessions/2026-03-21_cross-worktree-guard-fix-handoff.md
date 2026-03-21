# Cross-Worktree Merge-Guard Fix Handoff

**Lane Direction:** Use a free `author-*` lane after `#1190` merges. Keep this PR tightly bounded to shared review-queue discovery across worktrees. Do not fold in docs cleanup, PR5 delegation work, or any `SendMessage`/notification integration.

**Date:** 2026-03-21
**Dependency:** `#1190` merged
**Blocking Repro PR:** `#1189`
**Plan File:** `plans/sessions/2026-03-20_post-pr4-proving-checklist.md`
**Goal:** Eliminate the cross-worktree merge-bypass gap by making review request/verdict discovery canonical across all worktrees for the same repo.

## What Failed

Cross-worktree proving showed a merge from another worktree succeeded when it should have been blocked.

Expected:

- merge attempt from worktree B with no local verdict should block until a matching clean verdict exists in the shared queue

Actual:

- merge succeeded from another worktree/session

This means the current merge enforcement is not universal across worktrees.

## Likely Root Cause

The current queue and guard still resolve review state through worktree-local paths:

- `src/bid_euchre/ops/review_queue.py` defaults to `.claude/runtime/review_queue`
- `.claude/hooks/pre-merge-review-guard.sh` reads `${CLAUDE_PROJECT_DIR}/.claude/runtime/review_queue/...`

That makes verdict visibility depend on which worktree/session performs the merge.

## Scope

Ship only the bounded fix for:

- `src/bid_euchre/ops/review_queue.py`
- `src/bid_euchre/ops/reviews.py`
- `.claude/hooks/pre-merge-review-guard.sh`
- `tests/unit/test_review_queue.py`
- `tests/unit/test_merge_guard.py`
- `tests/unit/test_ops_reviews.py`

Only touch other files if strictly required by the queue-root refactor.

## Explicitly Out Of Scope

Do not include:

- `scripts/internal/review_driver.py` behavior changes beyond what is required to use the shared queue root
- PR5 delegation or prompt changes
- docs updates
- manual verdict creation
- GitHub branch-protection changes
- queue/result messaging or `SendMessage` integration

## Required Behavior

### 1. One canonical review-queue root per repo, shared across worktrees

Implement a single queue-root resolver in Python and make all queue readers/writers use it.

Preferred approach:

- derive the shared root from the repo's git common dir
- store review queue state under a repo-shared runtime path, not under a worktree-local `.claude/runtime`
- add a narrow env override only if it makes tests and local debugging simpler

The key requirement is not the exact path spelling; it is that all worktrees for the same repo resolve to the same queue root.

### 2. The bash merge guard must use the same resolution logic

Do not duplicate path logic by hand in bash if avoidable.

Preferred approach:

- have the guard ask Python for the canonical verdict path or queue root
- keep one source of truth for queue-path resolution

### 3. Ops visibility must read the same shared substrate

`ops.py reviews` and the queue-display helpers should reflect the shared queue root, not a worktree-local one.

## Implementation Guidance

1. Add a queue-root helper in `review_queue.py`.
2. Update request/verdict path helpers to use that shared root by default.
3. Update the guard to resolve the verdict path through the same helper.
4. Update `ops` review visibility to scan the same shared queue root.
5. Keep the refactor minimal. Do not redesign the queue format itself.

## Validation

Minimum targeted coverage:

- `uv run python -m pytest -q tests/unit/test_review_queue.py`
- `uv run python -m pytest -q tests/unit/test_merge_guard.py`
- `uv run python -m pytest -q tests/unit/test_ops_reviews.py`

Required new assertions:

1. queue-root resolution is shared across simulated worktrees for the same repo
2. a verdict written from worktree A is visible to readers in worktree B
3. the merge guard run from worktree B blocks when no shared verdict exists
4. the merge guard run from worktree B allows merge when a matching clean shared verdict exists
5. `ops.py reviews` / queue helpers surface the shared verdict, not an empty local queue

## PR Notes

The PR body should call out:

- this is a proving-window blocker fix for cross-worktree enforcement
- `#1189` remains the rerun target after merge
- no docs or feature expansion are included

Suggested commit message:

- `fix: share review queue across worktrees`

## After Merge

Fix merged as **#1195** (`afeb20e0`).

### Proving Run 2 — Merge Guard Test

**Target PR:** #1199 (author-b, `proving-run/pr2-synthetic`)
**Auto-merge:** Already disabled on #1199.
**Verdict:** Written and clean — `status: "passed"`, SHA `2bf1833c`, writer `review_driver`
**CI:** All checks green.

**Test sequence:**

```bash
# 1. Cross-worktree test (from author-a or any non-author-b worktree):
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author
gh pr merge 1199 --squash

# 2. Capture evidence:
echo "Exit code: $?"
cat /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/.claude/runtime/review_queue/pr_1199/verdict.json

# 3. Same-worktree test (from author-b, only if cross-worktree blocked):
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author-b
gh pr merge 1199 --squash
```

**Expected:** With #1195's shared queue root, cross-worktree merge should ALLOW (shared verdict is visible). If it blocks, that's a bug in the fix.

## Exit Criteria

- ✅ one bounded PR opened and merged (#1195)
- ✅ queue and verdict discovery are canonical across worktrees
- ✅ merge guard no longer depends on the merge being attempted from the verdict-writer worktree
- ⬜ cross-worktree merge test passes on #1199
- ⬜ proving window closed
