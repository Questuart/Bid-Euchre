# Proving Run 1 Follow-up Fix Handoff

**Lane Direction:** Use `author-b` if available; otherwise any free `author-*` lane may take this. Keep this PR tightly bounded to the proving blocker fixes. Do not hand-write `verdict.json`, do not close `#1189`, and do not expand into cross-worktree queue canonicalization in this PR.

**Date:** 2026-03-21
**Blocking Repro PR:** `#1189`
**Plan File:** `plans/sessions/2026-03-20_post-pr4-proving-checklist.md`
**Goal:** Fix the proving-run defects that currently strand asset/docs PRs in `waiting_for_ci` and leave timed-out review runs looking non-terminal.

## What Failed

Proving Run 1 found two real defects:

1. path-filtered CI checks with state `SKIPPED` are treated as `unknown`, so the review driver never advances past `waiting_for_ci`
2. when the review driver hits its runtime limit, it exits without writing a terminal verdict or updating loop state to a terminal reason

These failures block the review gate from being considered proven.

## Scope

Ship only the bounded fix for:

- `scripts/internal/github_pr_state.py`
- `.claude/hooks/pre-merge-review-guard.sh`
- `scripts/internal/review_driver.py`
- `tests/unit/test_github_pr_state.py`
- `tests/unit/test_merge_guard.py`
- `tests/unit/test_review_driver.py`

## Explicitly Out Of Scope

Do not include:

- manual verdict creation for `#1189`
- queue-path or verdict-path canonicalization across worktrees
- `scripts/internal/review_lane_runner.py`
- prompt changes or PR5 delegation work
- docs cleanup

## Required Behavior

### 1. `SKIPPED` must count as terminal-success for CI aggregation

Apply the same fix in both places that currently classify CI:

- `scripts/internal/github_pr_state.py`
- `.claude/hooks/pre-merge-review-guard.sh`

Expected behavior:

- all CI checks `SUCCESS` or `SKIPPED` => `success`
- any `FAILURE` => `failure`
- any `PENDING` or `IN_PROGRESS` => `pending`
- only genuine unknown/unreadable states => `unknown`

### 2. Runtime-limit exit must become a terminal non-clean outcome

In `scripts/internal/review_driver.py`, when the 15-minute runtime limit is reached:

- update loop state to a terminal failure-style outcome
- set a concrete `stop_reason`
- persist the updated state
- write a non-clean verdict for the current PR/SHA
- do not leave observers seeing `waiting_for_ci` with `stop_reason = null`

The goal is not to degrade to clean; it is to fail closed and make the timeout visible.

## Implementation Guidance

1. Add the CI-classifier fix first.
2. Mirror the same logic in the merge guard so live merge behavior matches driver behavior.
3. Then fix the timeout path in `review_driver.py`.
4. Keep the timeout verdict/status conservative: `failed` is preferred over anything that could be misread as mergeable.

## Validation

Minimum targeted coverage:

- `uv run python -m pytest -q tests/unit/test_github_pr_state.py`
- `uv run python -m pytest -q tests/unit/test_merge_guard.py`
- `uv run python -m pytest -q tests/unit/test_review_driver.py`

Required new assertions:

1. `get_ci_status()` returns `success` when CI states are a mix of `SUCCESS` and `SKIPPED`
2. the bash merge guard allows green CI when some CI checks are `SKIPPED`
3. runtime-limit exit in `review_driver.py` leaves a terminal state with non-null `stop_reason`
4. runtime-limit exit writes a non-clean verdict instead of silently disappearing

## PR Notes

The PR body should call out:

- this is a proving-window blocker fix, not feature expansion
- `#1189` remains open as the rerun target
- cross-worktree verdict discovery is intentionally deferred to the next proving decision point

Suggested commit message:

- `fix: unblock proving run 1 CI and timeout handling`

## Exit Criteria

- one bounded fix PR is opened
- only the six scoped files are included
- `SKIPPED` no longer strands asset/docs PRs in `waiting_for_ci`
- timeout no longer leaves review state looking live when the process has exited
- `#1189` is ready to be rerun with no manual override
