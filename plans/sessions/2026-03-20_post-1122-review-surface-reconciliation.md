# Post-1122 Review-Surface Reconciliation

**Date:** 2026-03-20
**Status:** proposed
**Goal:** Reconcile the remaining review-surface documentation and terminology
issues immediately after `#1122` landed, now that the comment-ingestion bridge
is merged and `#1116` is closed.

## Context

Recent state changes:

- `#1122` merged the consolidated PR comment-ingestion bridge
- `#1116` was closed as superseded
- there are currently no open PRs blocking the review-surface doc files

Two previously deferred docs issues are now unblocked:

- `#1121` — reconcile `reviewing-changes` branch-protection status across docs
- `#1046` — clarify the two different senses of “advisory”

There is also one validate-first issue that may now be closeable:

- `#1118` — duplicate/dead comment-ingestion code from the old `#1116` design

## Why This Exists

The review-surface bridge has shifted quickly:

- `reviewing-changes` semantics changed over time
- `claude-review` remains advisory
- Codex Cloud is comment-based
- `#1122` changed the comment-ingestion path and synced some docs

Before resuming the broader safe issue queue, the repo should have a clean and
internally consistent story for what counts as:

- merge-relevant gate
- advisory check
- review overlay
- branch-protection requirement

## Decisions Locked By This Plan

1. This is a **small docs/reconciliation pass**, not a review-architecture
   redesign.
2. The implementation should describe current reality, not restate stale
   historical assumptions.
3. `#1118` should only get code work if validation shows `#1122` did **not**
   actually resolve it.
4. If `#1118` is already satisfied by merged code, close it instead of opening
   another code PR.

## Primary Targets

### `#1121` — branch-protection status reconciliation

Validate the current truth for `reviewing-changes`:

- is it branch-protection required right now?
- or advisory-only with respect to merge requirements?

Then reconcile the docs that disagree.

Likely files:

- `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`
- `docs/02_agent/CODEX_GITHUB_REVIEW.md`
- `.claude/rules/deferred/60_review_gate.md`

### `#1046` — clarify “advisory” terminology overlap

Make the docs explicit that:

- `reviewing-changes` may be advisory in the branch-protection sense
- while still belonging to the `review_gate` category in the three-category
  check model

Likely files:

- `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`
- `plans/agent_ops/0_bootstrap/checkpoints.md`

### `#1118` — validate-first close or fix

Validate whether merged `#1122` already removed:

- duplicate comment-author classification contract
- dead normalized comment path from the older `#1116` design

Likely validation files:

- `src/bid_euchre/ops/reviews.py`
- `scripts/internal/github_pr_state.py`

## Expected Output

- one small docs PR for `#1121` + `#1046`
- closure of `#1118` if validation confirms `#1122` resolved it
- or a separate tiny follow-up only if a real residual `#1118` gap remains

## Out of Scope

- new review-loop architecture work
- CI classifier changes
- hosted review experiments
- broad issue-sweep execution
- comment-ingestion redesign after `#1122`

## Suggested Validation

- targeted grep/diff review of all touched docs
- `make check-quiet`
- for `#1118` validation:
  - `rg -n "TRUSTED_BOT_LOGINS|classify_comment_author|_BOT_USER_TYPES|PRComment|get_pr_comments" src scripts/internal`

## Done When

- [ ] `#1121` is resolved with the docs aligned to actual branch-protection truth
- [ ] `#1046` is resolved with explicit terminology clarification
- [ ] `#1118` is either closed as already fixed by `#1122` or split into a tiny
      residual follow-up
- [ ] `make check-quiet` passes

## Outcome

(fill after implementation)
