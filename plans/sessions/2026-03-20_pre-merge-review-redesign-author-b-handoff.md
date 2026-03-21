# Pre-Merge Review Redesign — Author B Handoff

**Lane Direction:** `author-b` owns PR2 only: the single `review` lane runner in shadow mode. Do not touch hook registration, merge behavior, or ops UI.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Dependencies:** PR1 packet contract

## Assignment

Implement PR2 — Review Lane Runner (Shadow Mode).

## Scope

Build the runner that:

- claims pending review requests
- verifies the current PR head SHA
- invokes `steward-review`
- writes verdict packets
- emits `error` or `blocked` when appropriate

Suggested write scope:

- `scripts/internal/review_lane_runner.py` (new)
- `.claude/agents/steward-review.md`
- `tests/unit/test_review_lane_runner.py` (new)

## Out Of Scope

- `.claude/hooks/**`
- `.claude/settings.json`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/reviews.py`
- legacy auto-merge disable
- delegated correctness / architecture / coverage review

## Implementation Guidance

- runner must not publish merge-authoritative success yet
- shadow mode is enough for this PR
- stale SHA results must be discarded
- reviewer failure must not collapse to `clean`
- keep `review` as the only writer of final verdicts

## Validation

Minimum:

- claim one queued request and write one verdict
- stale SHA is discarded
- runner failure writes `error`
- clean result is only written for the current SHA

## Exit Criteria

- runner can process realistic queued requests
- verdict writing is deterministic and SHA-bound
- PR2 does not change merge behavior
