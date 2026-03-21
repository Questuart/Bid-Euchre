# Pre-Merge Review Redesign — Author D Handoff

**Lane Direction:** `author-d` owns PR4 only: the atomic cutover. This lane is the only lane allowed to edit PR-create hooks, merge-guard hooks, or shared hook registration for this redesign.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Dependencies:** PR2 runner shadow-mode confidence, PR3 ops visibility

## Assignment

Implement PR4 — Atomic Cutover.

## Scope

Ship the cutover in one PR:

- enqueue durable review requests on PR creation / update
- add a hard local merge guard
- disable legacy pre-merge review-loop authority
- publish the new authoritative review status

Suggested write scope:

- `.claude/hooks/post-pr-review.sh`
- `.claude/hooks/post-pr-review-loop.sh`
- `.claude/hooks/pre-merge-review-guard.sh` (new)
- `.claude/settings.json`
- `scripts/internal/github_pr_state.py`
- `scripts/internal/set_review_status.sh` if needed
- `tests/unit/test_github_pr_state.py`
- `tests/unit/test_merge_guard.py` (new)

## Out Of Scope

- queue schema redesign
- runner redesign
- ops UI redesign
- delegated correctness / architecture / coverage review
- broad docs cleanup

## Cutover Rules

- do not disable old authority before the new guard is live
- do not enable the new guard before the runner can produce verdicts
- do not leave both old and new merge-authority paths active at once

## Implementation Guidance

- replace auto-invoked `/reviewing-changes` with queue enqueue where appropriate
- ensure merge guard checks both CI state and matching clean verdict for current SHA
- remove or neutralize legacy local loop auto-merge behavior
- keep the cutover diff focused; avoid opportunistic cleanup

## Validation

Minimum:

- PR creation enqueues a request
- merge guard blocks:
  - no verdict
  - stale verdict
  - non-clean verdict
- merge guard allows matching clean verdict for current SHA
- legacy loop no longer acts as reviewer-of-record

## Exit Criteria

- cutover is atomic
- no enforcement gap exists
- the new queue-backed path is the only pre-merge reviewer-of-record path
