# Pre-Merge Review Redesign — Author C Handoff

**Lane Direction:** `author-c` owns PR3 only: queue and verdict visibility in ops tooling. Do not change hook behavior, merge behavior, or runner logic.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Dependencies:** PR1 packet contract

## Assignment

Implement PR3 — Queue / Verdict Visibility.

## Scope

Surface review state to the operator:

- request pending
- verdict outcome
- reviewed SHA
- stale verdict vs current HEAD
- reviewer error state

Suggested write scope:

- `src/bid_euchre/ops/reviews.py`
- `scripts/internal/ops.py`
- `tests/unit/test_ops_reviews.py`
- `tests/unit/test_ops_cli.py`

## Out Of Scope

- `.claude/hooks/**`
- `.claude/settings.json`
- `scripts/internal/review_lane_runner.py`
- `scripts/internal/review_driver.py`
- delegated subreview

## Implementation Guidance

- this PR is observability, not enforcement
- read packet state from the queue substrate rather than legacy review-loop state
- make stale-vs-current SHA obvious in CLI output
- keep CI status and review status conceptually separate

## Validation

Minimum:

- `ops.py reviews` shows pending / blocked / clean / stale / error states
- missing packet state degrades cleanly
- no merge-behavior changes are introduced

## Exit Criteria

- operators can inspect queue and verdict state before cutover
- PR3 stays read-only from a merge-authority perspective
