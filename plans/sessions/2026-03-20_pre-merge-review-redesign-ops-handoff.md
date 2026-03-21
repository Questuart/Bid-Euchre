# Pre-Merge Review Redesign — Ops Handoff

**Lane Direction:** `ops` owns orchestration, dependency enforcement, cutover readiness, and merge order. Do not implement author-lane scopes unless a lane is blocked or unavailable.

**Date:** 2026-03-20
**Plan File:** `plans/sessions/2026-03-20_pre-merge-review-redesign.md`
**Dependencies:** none

## Your Mission

1. Read the plan and all lane handoffs before dispatching work.
2. Keep the PR stack ordered as:
   - PR1 queue foundations
   - PR2 runner shadow mode
   - PR3 ops visibility
   - PR4 atomic cutover
   - PR5 follow-on only if needed
3. Keep manual `steward-review` as the real gate until PR4 lands.
4. Do not allow PR4 to merge until:
   - PR2 can process real queued requests in shadow mode
   - PR3 shows verdict freshness clearly
5. Keep write scopes disjoint. Reassign only if a lane stalls.

## Coordination Rules

- PR1 must be small and land first.
- PR2 and PR3 may run in parallel only after PR1's packet contract is stable.
- PR4 is a cutover PR; do not split it.
- PR5 must not block the MVP merge gate.

## What To Watch

- accidental overlap on `.claude/settings.json` or hook files
- accidental overlap on queue packet schema
- any attempt to revive the legacy local review loop as a fallback gate
- any plan drift that folds docs or delegated subreview into PR4

## Shadow-Mode Exit Criteria For PR2

Before PR4:

- at least a few real or simulated requests complete end to end
- stale-SHA cases are discarded rather than treated as `clean`
- runner failure yields `error`, not silent success

## Merge Readiness Checklist

- PR1 merged
- PR2 merged and shadow-validated
- PR3 merged
- manual review confirms PR4 disables old authority and enables the new guard in one step

## Deliverables

- clear lane dispatch order
- no overlapping cutover edits
- cutover only after shadow-mode confidence exists

## Exit Criteria

- PR1 through PR4 are sequenced correctly
- manual review remains the real gate until PR4
- no enforcement gap is introduced during cutover
