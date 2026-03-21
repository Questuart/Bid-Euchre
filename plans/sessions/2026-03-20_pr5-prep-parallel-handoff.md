# PR5 Prep In Parallel — Author Scratch Handoff

**Lane Direction:** `author-scratch` may run this in parallel while PR4 is underway because it is planning-only. Do not edit hooks, settings, runtime review code, or live docs yet.

**Date:** 2026-03-20
**Goal:** Prepare PR5 so it can start immediately after the post-PR4 proving window clears, without overlapping the cutover work.

## Scope

Planning and inventory only:

- PR5 file inventory
- delegation policy for `review` -> specialized reviewers
- doc rewrite outline for the new queue-backed review flow
- explicit list of what remains deferred, including `SendMessage` integration

## Deliverables

Produce a short execution package covering:

1. which files PR5 should touch
2. when `review` should delegate vs review locally
3. how findings from delegated reviewers are consolidated
4. which docs must be updated after proving
5. which items remain deferred to later platform work

## Explicitly Deferred

Do not implement:

- `.claude/hooks/**`
- `.claude/settings.json`
- `scripts/internal/review_lane_runner.py`
- `scripts/internal/github_pr_state.py`
- `src/bid_euchre/ops/reviews.py`

Do not add:

- `SendMessage` integration
- GitHub PR comment mirroring
- new merge-guard behavior

## Suggested Output

A compact session plan or handoff draft for PR5 that `ops` can dispatch once the proving window passes.

## Exit Criteria

- PR5 is ready to start quickly after proving
- no cutover files were touched
- deferred integrations are explicitly listed rather than silently pulled forward
