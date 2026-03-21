# Pre-Merge Review Redesign — Author A Handoff

**Lane Direction:** `author-a` owns PR1 only: queue foundations and the immediate precheck-to-verdict path. Keep the scope tight and avoid hooks, settings, runner logic, and ops UI.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Dependencies:** none

## Assignment

Implement PR1 — Queue Foundations.

## Scope

Build the durable packet substrate keyed by `PR + HEAD SHA`:

- request model
- verdict model
- file layout helpers
- stale-verdict detection helpers
- immediate deterministic-precheck failure -> `blocked` verdict

Suggested write scope:

- `src/bid_euchre/ops/review_queue.py` (new)
- `src/bid_euchre/ops/events.py`
- `tests/unit/test_review_queue.py` (new)

## Out Of Scope

- `.claude/hooks/**`
- `.claude/settings.json`
- `scripts/internal/review_driver.py`
- `scripts/internal/review_lane_runner.py`
- `scripts/internal/ops.py`
- `src/bid_euchre/ops/reviews.py`

## Implementation Guidance

- keep the packet format explicit and small
- make every verdict carry the reviewed SHA
- make stale-verdict invalidation deterministic and testable
- prefer append-only / file-based runtime state under `.claude/runtime/`
- reuse the repo's existing event log conventions where helpful

## Validation

Minimum:

- targeted unit tests for request / verdict read-write
- stale verdict invalidation test
- deterministic precheck failure creates `blocked` verdict

## Exit Criteria

- packet helpers are landed
- precheck-to-verdict path exists
- SHA freshness is part of the shared contract
- PR1 stays small enough for fast review
