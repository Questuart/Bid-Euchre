# PR-5 Closeout Baseline Cleanup

**Date:** 2026-03-20
**Goal:** Close remaining baseline gaps so the repo is ready for the post-PR-5
bridge and the later platform pre-phase.

## Context

PR-5 slices 5, 6, and 7 all merged. Several follow-up fixes also landed:

- slice 5: `#1054` (+ hardening: `#1070`, `#1088`)
- slice 6: `#1068`, `#1091`
- slice 7: `#1098`
- dirty-worktree liveness fallback: `#1104`
- retry chronology for `get_pending_retries()`: `#1112`

This cleanup PR addresses the one remaining code gap (`get_retry_summary()`
chronology) and updates plan/checkpoint docs to match what actually shipped.

## What This PR Does

1. **Fix `get_retry_summary()` chronology** — the follow-up counting in
   `get_retry_summary()` was not chronology-aware. #1112 fixed
   `get_pending_retries()` but missed the summary function. This PR applies
   the same string-comparison approach to the summary's follow-up counting.

2. **Refresh closeout docs** — mark all slices done with correct PR
   attributions, update blockers, set next queue.

## What This PR Does NOT Do

- `get_pending_retries()` fix — already on main via #1112
- Dirty-worktree liveness — already on main via #1104
- Review-event production wiring — deferred to bridge slice
- Platform-1 implementation

## Done When

- [x] `get_retry_summary()` chronology fix applied
- [x] Regression tests added
- [x] PR-5 closeout docs match reality with correct attribution
- [x] Review-event gap explicitly documented as deferred
- [x] Targeted ops tests pass
- [x] `make check-quiet` passes

## Outcome

1. **`get_retry_summary()` chronology fix (new in this PR):** Follow-up events
   before the earliest failure for a task are no longer counted. Uses
   string-comparison approach matching #1112's pattern. 2 new tests added.

2. **Docs/checkpoint refresh:** Done with correct provenance — #1104 for
   dirty-worktree, #1112 for `get_pending_retries()`, this PR for
   `get_retry_summary()`. Next queue: bridge → filesystem → Platform-1.
