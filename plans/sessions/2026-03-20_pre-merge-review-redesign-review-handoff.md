# Pre-Merge Review Redesign — Review Lane Handoff

**Lane Direction:** `review` is the active reviewer-of-record for the implementation stack until the new queue-backed path lands. Do not implement code. Review each PR for correctness, scope control, stale-review risk, and cutover safety.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Dependencies:** none

## Your Mission

Review each implementation PR in order and enforce the plan boundaries:

- PR1 must stay substrate-only
- PR2 must stay shadow-mode only
- PR3 must stay visibility-only
- PR4 must be atomic cutover only

## What To Look For

- queue or verdict contracts that are not SHA-bound
- stale-review paths that could still yield `clean`
- runner behavior that treats reviewer failure as success
- ops visibility that confuses review state with CI state
- PR4 split-brain cutover risk:
  - old authority not fully disabled
  - new guard active without verdict producer
  - both paths active concurrently

## Review Priorities

1. correctness and enforcement semantics
2. stale-SHA handling
3. write-scope discipline
4. targeted tests for the new guarantees

## Expected Review Output

For each PR, produce:

- blocking findings first
- explicit note on whether the PR stayed within its assigned write scope
- explicit note on whether the PR preserves or improves merge-safety

## Exit Criteria

- each PR has a scoped independent review
- cutover safety is explicitly reviewed before PR4 merges
