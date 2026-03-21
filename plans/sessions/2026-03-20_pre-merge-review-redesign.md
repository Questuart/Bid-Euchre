# Pre-Merge Review Redesign — PR4: Atomic Cutover

**Date:** 2026-03-20
**Branch:** `fix/atomic-cutover-review-guard`
**Lane:** author-d (sole owner of PR-create hooks, merge-guard hooks, shared hook registration)

## Summary

Ship the atomic cutover from legacy review-loop merge authority to
queue-backed, verdict-gated merges. After this PR:

1. PR creation enqueues a durable review request via `review_queue.write_request()`
2. `review_driver.py` writes verdict files via `review_queue.write_verdict()` at terminal states
3. A PreToolUse merge guard blocks `gh pr merge` unless verdict + CI are clean
4. Legacy auto-merge behavior in `review_driver.py` is removed

## Dependencies (all merged)

- PR1 #1176 — queue substrate (`review_queue.py`: ReviewRequest, ReviewVerdict, write/read)
- PR2 #1179 — runner shadow mode (`review_lane_runner.py`)
- PR3 #1178 — ops visibility (`reviews.py`: QueueEntry, formatting)

## Key APIs from Dependencies

```python
# From bid_euchre.ops.review_queue
ReviewRequest(pr_number, head_sha, branch, requester)
ReviewVerdict(pr_number, reviewed_sha, status, reason, findings)
write_request(req, queue_dir)  -> Path
write_verdict(verdict, queue_dir)  -> Path
read_verdict(pr_number, queue_dir)  -> ReviewVerdict | None
is_verdict_stale(pr_number, current_head_sha, queue_dir)  -> bool
STATUS_PASSED = "passed"
STATUS_BLOCKED = "blocked"
STATUS_FAILED = "failed"
```

## Cutover Rules

1. Do not disable old authority before the new guard is live
2. Do not enable the new guard before the runner can produce verdicts
3. Do not leave both old and new merge-authority paths active at once

## Design

### Hook: post-pr-review.sh (modified)

Replace `/reviewing-changes` skill injection with `review_queue.write_request()`.
Call via inline Python to use the existing substrate.

### Hook: pre-merge-review-guard.sh (new)

PreToolUse hook on Bash commands matching `gh pr merge`:
1. Extract PR number from command
2. Read verdict via `review_queue.read_verdict()`
3. Get current HEAD SHA via `gh pr view`
4. Block if: no verdict, stale SHA, verdict not passed
5. Check CI status
6. Block if CI not success
7. Allow otherwise (exit 0)

### review_driver.py changes

- At terminal states: write verdict via `review_queue.write_verdict()`
- `_step_ready_to_merge`: remove `enable_auto_merge()` call
- Centralized via `_write_verdict_if_applicable()` in `step()` dispatch

### settings.json changes

Register `pre-merge-review-guard.sh` as PreToolUse Bash hook.

## Files

- `.claude/hooks/post-pr-review.sh` — replace `/reviewing-changes` with queue enqueue
- `.claude/hooks/pre-merge-review-guard.sh` — new: PreToolUse merge guard
- `.claude/settings.json` — register merge guard hook
- `scripts/internal/review_driver.py` — write verdicts, disable auto-merge
- `tests/unit/test_merge_guard.py` — merge guard tests

## Out Of Scope

- Queue schema redesign (done in PR1)
- Runner redesign (done in PR2)
- Ops UI redesign (done in PR3)
- Changes to `github_pr_state.py` (queue substrate replaces need)

## Validation

- [ ] PR creation enqueues a request file
- [ ] review_driver writes verdict at terminal states
- [ ] Merge guard blocks: no verdict, stale verdict, non-passed verdict, CI failure
- [ ] Merge guard allows: matching passed verdict for current SHA + CI green
- [ ] Legacy loop no longer calls enable_auto_merge
- [ ] `make check` passes

## Outcome

<!-- Filled after implementation -->
