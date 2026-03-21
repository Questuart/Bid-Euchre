# Auto-Merge Retry Follow-up Handoff

**Lane Direction:** Use a free `author-*` lane after PR5 lands. Keep this PR tightly bounded to the GitHub-side unattended merge retry path. Do **not** reintroduce merge authority into `review_driver.py`, and do not touch the local merge guard or review-queue substrate.

**Date:** 2026-03-21
**Dependencies:** PR5 docs cleanup may land first, but this follow-up is runtime behavior and should be its own PR.
**Goal:** Ensure owner-authored PRs that miss the initial GitHub auto-merge enablement attempt get another GitHub-side chance to queue auto-merge after they actually become mergeable.

## Why This PR Exists

Current behavior is split:

- `.github/workflows/auto-merge.yml` attempts `gh pr merge --auto --squash` only on PR `opened` / `reopened`
- `review_driver.py` intentionally no longer calls `enable_auto_merge()`
- the local merge guard remains the authoritative steward-side enforcement path for `gh pr merge`

This leaves a workflow gap:

- some PRs queue auto-merge successfully at open and merge later
- some PRs miss that window and then sit clean-but-unmerged unless a human or lane merges them manually

This is not a merge-safety blocker, but it is friction and defeats unattended merge as the normal success path.

## Scope

Ship only the bounded follow-up for:

- `.github/workflows/auto-merge.yml`

Optional only if needed to keep the workflow readable/testable:

- one small helper script under `scripts/internal/` used only by the workflow

If you add a helper script, include focused tests for that helper. Otherwise keep the PR workflow-only.

## Explicitly Out Of Scope

Do not include:

- `scripts/internal/review_driver.py`
- `scripts/internal/github_pr_state.py`
- `.claude/hooks/pre-merge-review-guard.sh`
- `src/bid_euchre/ops/review_queue.py`
- `src/bid_euchre/ops/reviews.py`
- docs updates already covered by PR5
- branch-protection changes
- `SendMessage` or lane-notification work

## Required Behavior

### 1. Keep merge authority where it is now

Do **not** put `enable_auto_merge()` back into `review_driver.py`.

That removal was intentional and is covered by tests. This PR should preserve:

- queue-backed verdict truth
- local merge-guard enforcement for steward-driven merges
- GitHub auto-merge as a convenience layer, not the source of review truth

### 2. Give GitHub auto-merge another chance after mergeability changes

The workflow should re-attempt `gh pr merge --auto --squash` after the PR becomes more likely to be mergeable, not only at open time.

Acceptable trigger shapes:

- `check_suite: completed`
- another GitHub-native trigger that gives a later retry opportunity keyed to PR mergeability

Preferred approach:

- keep the existing `pull_request` trigger
- add a later retry trigger
- resolve the affected PR from the event payload / head SHA
- rerun `gh pr merge --auto --squash` only for eligible PRs

### 3. Make the workflow safe to retry

The retry path must be idempotent enough for repeated GitHub events.

Required properties:

- ignore closed / merged PRs
- only operate on PRs targeting `main`
- only operate on PRs authored by the repo owner (same current rule)
- tolerate “already enabled” / already mergeable cases without turning them into failures that confuse operators

## Implementation Guidance

1. Start from `.github/workflows/auto-merge.yml`.
2. Preserve the current owner-only behavior.
3. Add a second event source that can fire after CI/review state changes.
4. If the event is not a direct PR event, resolve the candidate PR(s) from the head SHA or event metadata.
5. Re-attempt `gh pr merge --auto --squash`.
6. Keep the workflow simple. If the YAML becomes too contorted, extract the decision logic into one tiny helper script and test that helper.

## Validation

Minimum:

- inspect the workflow diff carefully
- confirm the workflow still scopes to owner PRs on `main`
- confirm the retry path cannot target arbitrary PRs

If a helper script is added:

- add focused unit coverage for the PR-selection / retry decision logic

Manual smoke test required:

1. use a real owner-authored PR that does **not** merge immediately at open
2. let CI / review settle
3. verify the later workflow trigger re-attempts auto-merge
4. confirm the PR queues or merges without a local manual `gh pr merge`

Bonus smoke:

- verify the workflow is harmless when auto-merge was already enabled on the initial attempt

## PR Notes

The PR body should call out:

- this is an unattended-merge ergonomics fix, not a review-truth redesign
- `review_driver.py` intentionally remains out of merge authority
- the local merge guard still governs steward CLI merges
- GitHub auto-merge is being made retryable, not authoritative

Suggested commit message:

- `ci: retry auto-merge after PR becomes mergeable`

## Exit Criteria

- one bounded follow-up PR is opened
- GitHub auto-merge gets a later retry opportunity after PR open
- `review_driver.py` still does not call `enable_auto_merge()`
- owner-authored clean PRs no longer get stranded simply because the first auto-merge attempt fired too early
