<!-- review-tier: small -->
# Session Plan: GitHub Issue Cleanup (#828, #842, #847, #860, #862)

**Date:** 2026-03-18
**Lane:** author-b
**Branch:** `codex/steward-author-b`
**Strategy:** Two PRs — one batch convention-followups, one CI poller fix

## Context

Triaged 14 open GitHub issues. Closed 7 (completed, duplicate, stale, won't-fix).
3 deferred (#829, #830 — low priority infra improvements). 4 fixable as a batch
convention PR, 1 as a separate CI poller PR.

## PR 1: Batch Convention Follow-Ups

**Closes:** #828, #842, #847, #860
**Branch:** `fix/issue-cleanup-batch`

### Fix 1: #828 — Update PV2 severity from P1 to P2 in docs + docstring

The code already uses P2 (review_driver.py line 477), but documentation is stale.

| File | Line | Change |
|------|------|--------|
| `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` | 107 | Change `(P1 — blocking)` to `(P2 — non-blocking)` |
| `scripts/internal/review_driver.py` | 419 | Change `(P1 if broken reference)` to `(P2 if broken reference — non-blocking)` |

### Fix 2: #842 — Clarify forward-progress timestamp semantics

Two findings from PR #841 review:

**Finding 1:** `.claude/runtime/task_state/README.md` line 110 says to update
`progress` when encountering a blocker — but encountering a blocker is not
forward progress and shouldn't refresh `last_forward_progress_at`.

| File | Line | Change |
|------|------|--------|
| `.claude/runtime/task_state/README.md` | 110-113 | Clarify: update `progress` object on blocker events, but only update `last_forward_progress_at` on actual forward progress (completed items, passed validation) |

**Finding 2:** `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` line 463-470 —
"Task Completion Requirements" applies unconditionally, but not all work creates
a task record. Fix: add qualifier "When a task record exists" prefix.

| File | Line | Change |
|------|------|--------|
| `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | 463 | Change heading to clarify scope: applies when a task record exists |

### Fix 3: #847 — Fix nonexistent pytest target in session plan

The session plan references a pytest target that doesn't exist.

| File | Line | Change |
|------|------|--------|
| `plans/sessions/2026-03-18_three-followup-fixes.md` | 79-80 | Replace nonexistent test targets with valid ones |

### Fix 4: #860 — Pass registry filenames to Python via argv

The inline Python in `steward-session.sh` uses shell variable interpolation
(`$f`, `$now`) which is fragile. Pass via `sys.argv` instead.

| File | Line | Change |
|------|------|--------|
| `.claude/tmux/steward-session.sh` | 71-82 | Rewrite inline Python to accept `$f` and `$now` as `sys.argv[1]` and `sys.argv[2]` |

### Dependencies

All 4 fixes are independent — they touch different files and have no
cross-dependencies. Can be committed in any order.

### Validation

- Tier 1: `uv run python -m pytest tests/unit/test_review_driver.py -x -q` (for #828)
- Shell syntax: `bash -n .claude/tmux/steward-session.sh` (for #860)
- Tier 2: `make check-quiet` before PR

---

## PR 2: CI Poller Merged-PR Detection

**Closes:** #862
**Branch:** `fix/ci-poller-merged-exit`

### Problem

The CI poller daemon doesn't detect when a PR has been merged or closed.
It continues polling until timeout (900s), then reports a false CI_TIMEOUT
failure to the next session.

### Fix

Add a PR state check at the start of each polling iteration in
`scripts/internal/ci_poller.sh`. If the PR is `MERGED` or `CLOSED`, exit
cleanly with status "merged" or "closed".

| File | Line | Change |
|------|------|--------|
| `scripts/internal/ci_poller.sh` | ~144 (start of while loop) | Add `gh pr view $PR_NUM --json state -q .state` check; exit 0 if MERGED or CLOSED |

### Validation

- Manual review of shell logic
- Shell syntax: `bash -n scripts/internal/ci_poller.sh`
- Tier 2: `make check-quiet` before PR (docs-only CI path since no Python changes)

---

## Execution Order

PR 1 and PR 2 are fully independent — different files, different branches.
They can be implemented and merged in parallel.

**Sequencing within PR 1:** Any order; I'll go 828 → 842 → 847 → 860
for logical grouping (review infra → docs → shell).

## Outcome

_To be filled after implementation._
