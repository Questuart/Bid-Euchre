# Safe Issue Work During Review Transition

**Date:** 2026-03-20
**Status:** proposed
**Goal:** Let issue-work continue while the local review-architecture reset and
other bridge changes are in flight, without creating overlap or churn on the
review-transition write scope.

## Context

The repo currently has:

- a reconciled open-issue triage plan in
  `plans/sessions/2026-03-20_issue-triage.md`
- active bridge work around:
  - filesystem boundary
  - PR comment ingestion
  - docs/checklist sync
  - local review-architecture reset

That means not every triaged batch is safe to execute right now. This plan
defines the current low-overlap subset that is worth doing while the review
transition lands.

## Decisions Locked By This Plan

1. Prefer issues with isolated write scopes and low coordination overhead.
2. Avoid anything that touches review truth, PR-state plumbing, or bridge-owned
   files.
3. Close stale / already-fixed / won’t-fix issues when validation confirms that
   code work is not warranted.
4. Use a small agent swarm only if write scopes are clearly disjoint.

## Active PR Constraints

At the time of this plan refresh, these open PRs constrain the safe queue:

- `#1122` — comment-ingestion bridge consolidation
  - touches `scripts/internal/ops.py`
  - touches `src/bid_euchre/ops/events.py`
  - touches `src/bid_euchre/ops/index.py`
  - touches `src/bid_euchre/ops/reviews.py`
  - touches `tests/unit/test_ops_cli.py`
  - touches `tests/unit/test_ops_index.py`
  - touches `tests/unit/test_ops_reviews.py`
  - touches `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`
  - touches `plans/agent_ops/0_bootstrap/checkpoints.md`
  - touches `plans/agent_ops/governing_plan.md`

- `#1116` — older comment-ingestion bridge PR
  - still open but superseded in practice by `#1122`
  - overlapping files should still be treated as unsafe until `#1122` lands and
    `#1116` is closed

## Unsafe While Transition Is In Flight

These should wait:

### Batch 2 — `index.py` correctness/performance

Defer while the PR comment ingestion bridge is active because that lane owns:

- `src/bid_euchre/ops/index.py`

### Batch 3 — ops bugs

Defer while filesystem-boundary/comment bridge work is active because this batch
touches likely overlap areas such as:

- `scripts/internal/ops.py`
- event-related code
- compaction / archive paths adjacent to bridge-control work

### Batch 4 — CI/process

Defer while review/CI transition work is active because classifier and workflow
surfaces are part of the current review simplification effort.

### Batch 7 — review infra

Defer entirely until the review reset lands because it touches review-driver /
review-adapter infrastructure directly.

### Docs/checklist/governing files touched by `#1122`

Defer while `#1122` is open:

- `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`
- `plans/agent_ops/0_bootstrap/checkpoints.md`
- `plans/agent_ops/governing_plan.md`

This means issues such as `#1121` and `#1046` are not safe in the current
window even though they are docs-only.

### Arc D v2 report/data work requiring regeneration or frozen-lineage judgment

- `#921` is not a “safe now” implementation item; prior session notes classify
  it as a data-regeneration problem that may require reruns.
- `#1003` should be treated as validate-first close/defer work, not assumed code
  work.

## Safe Now

The earlier safe queue from this plan was already completed. The remaining safe
work now comes from the revised live issue set.

### Safe Batch A — `fs_boundary.py` hardening

Issues:

- `#1119` fail loud when repo boundary discovery cannot find a repo root
- `#1120` add direct coverage for `check_path()` / `require_path()` wrappers

Why safe:

- isolated to `src/bid_euchre/ops/fs_boundary.py` and its tests
- no overlap with the current comment-ingestion bridge PRs

### Safe Batch B — `status.py` hardening

Issues:

- `#1101` liveness probe edge cases: clock skew and stale-candidate priority
- `#1055` stale lane timestamps should ignore non-progress events

Why safe:

- isolated to `src/bid_euchre/ops/status.py` and related tests
- does not overlap the current comment-ingestion bridge PRs

### Safe Batch C — `skill_promotion.py` fixes

Issues:

- `#1060` atomic write in `_save_candidate()`
- `#1077` block the HTML5 `--!>` comment terminator too

Why safe:

- isolated to `src/bid_euchre/ops/skill_promotion.py` and related tests
- no overlap with active bridge files

### Safe Batch D — isolated ops bugs

Issues:

- `#1107` `scope.py` `**` glob handling
- `#1081` `scheduler.py` non-dict event guard

Why safe:

- separate write scopes in `scope.py` and `scheduler.py`
- no overlap with the comment-ingestion bridge or review reset

### Safe Batch E — flaky test fix

Issue:

- `#1105` stabilize `test_max_age_filter` in `tests/unit/test_ops_retries.py`

Why safe:

- test-only change
- isolated write scope

### Safe Docs Subset — isolated docs / session-note cleanup

Issues:

- `#1110`
- `#1109`
- `#1108`
- `#1100`
- `#1097`
- `#1047`
- `#1076`

Why safe:

- these do not require editing the current `#1122` files
- they are mostly session-plan, report, or secondary-doc cleanup

## Revalidate Before Acting

### `#1001` evidence-manifest `governing_plan` backfill

Do not patch this speculatively. There is conflicting prior guidance:

- one triage note proposes backfilling manifests
- an earlier review batch says the lineage is frozen and retroactive backfill
  risks inaccuracy

Required handling:

- validate current evidence first
- either defer/close with explanation or take a separate explicitly justified PR
- do not bundle it automatically into the safe convention batch

### `#1121` and `#1046` review/checklist terminology docs

These are not safe while `#1122` is open because they overlap:

- `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md`
- `plans/agent_ops/0_bootstrap/checkpoints.md`

Re-check after `#1122` lands.

## Suggested Swarm Shape

If the coordinator decides a swarm is worthwhile, keep it small:

1. **Coordinator lane**
   - validates current issue state
   - owns the session plan/task list
   - handles ambiguous defer/close issues
   - integrates final PR sequence

2. **Worker 1**
   - Safe Batch A (`fs_boundary.py`)

3. **Worker 2**
   - Safe Batch B (`status.py`)

4. **Worker 3**
   - Safe Batch C (`skill_promotion.py`)

Optional follow-on local work after the first three workers launch:

- Safe Batch D (`scope.py` + `scheduler.py`) if kept as separate small commits
- Safe Batch E (`test_ops_retries.py`)
- Safe Docs Subset if no active doc PR overlaps the chosen files

The coordinator should keep ambiguous validation/deferral items local:

- `#1001`
- `#1003`
- `#1121`
- `#1046`

## Expected Outputs

- one PR per isolated write scope or tightly related batch
- explicit issue closures/comments for validated stale / deferred items
- deferred note for anything found to overlap active bridge/review-transition
  work

## Out of Scope

- review-driver or review-adapter changes
- PR-state / GitHub classifier changes
- `ops/index.py` changes
- `scripts/internal/ops.py` changes
- event/comment-ingestion bridge work
- filesystem-boundary work
- data-regeneration/report-rerun work for Arc D
- docs currently overlapped by `#1122`

## Done When

- [ ] safe isolated issues have either landed or been queued into clean,
      non-overlapping PRs
- [ ] no active bridge/review-transition files were touched
- [ ] any ambiguous issues were validated first and then deferred or closed
- [ ] each PR ran targeted validation plus `make check-quiet`

## Suggested Validation

- Safe Batch A:
  - targeted `fs_boundary.py` tests
  - `make check-quiet`
- Safe Batch B:
  - targeted `status.py` tests
  - `make check-quiet`
- Safe Batch C:
  - targeted `skill_promotion.py` tests
  - `make check-quiet`
- Safe Batch D / E:
  - targeted file-specific tests
  - `make check-quiet`
- Safe Docs Subset:
  - targeted grep/diff review
  - `make check-quiet` if the PR mixes doc and code/test changes

## Outcome

**Status:** COMPLETE — 2026-03-20

### Issue Queue Validation

All 11 issues in the original safe queue were already closed by prior sessions:

| Issue | Status | Reason |
|-------|--------|--------|
| #950 | CLOSED | COMPLETED |
| #951 | CLOSED | COMPLETED |
| #1002 | CLOSED | COMPLETED |
| #955 | CLOSED | COMPLETED |
| #946 | CLOSED | COMPLETED |
| #995 | CLOSED | COMPLETED |
| #958 | CLOSED | COMPLETED |
| #963 | CLOSED | NOT_PLANNED |
| #936 | CLOSED | NOT_PLANNED |
| #1001 | CLOSED | COMPLETED |
| #1003 | CLOSED | NOT_PLANNED |

### Dashboard CI Discovery

During validation, discovered dashboard CI failure (run 23367182804):
- **Root cause:** `stefanzweifel/git-auto-commit-action` can't push to branch-protected main (GH006)
- **Fix:** Switched to `peter-evans/create-pull-request` in `.github/workflows/dashboard.yml`
- Also committed orphaned deterministic precheck improvements (C5, T1) and regenerated dashboard PNG

### PR

- [#1126](https://github.com/Questuart/Bid-Euchre/pull/1126) — fix: commit orphaned changes — dashboard CI, prechecks C5/T1

### Validation

- 118 targeted tests passed
- 5143/5148 tests passed in `make check-quiet` (5 pre-existing matplotlib font failures)
- No overlap with review-transition files
