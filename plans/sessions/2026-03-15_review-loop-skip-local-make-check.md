# Fix: Review Loop Skip Local `make check`

## Problem

The autonomous review loop (`review_driver.py`) fails at `make check` for all
recent PRs (#704-#709), never reaching Codex CLI review. State files show
`stopped_ci_failure` with reason "make check failed in initial validation".

### Root Cause

Two issues combine:

1. **Design flaw:** The review loop runs in the main checkout (triggered by
   PostToolUse hook), but PRs are created from worktrees. `run_make_check()`
   uses `Path.cwd()` = main checkout, which has dirty state (untracked files,
   modified plans, stale fixtures).

2. **Stale fixture (separate bug):** Recent PRs (#703-#707) added 19 new
   required columns to the action-value dataset schema but never regenerated
   `data/fixtures/smoke_action_value.parquet`. This causes test failures in
   any checkout.

## Fix

Remove local `make check` from the review loop. It's redundant with GitHub CI
(which runs on a clean checkout) and runs in the wrong directory.

### Changes

- `scripts/internal/review_driver.py` — Remove `make check` from `_step_pr_open()`
  and `_step_retesting()`. Both now transition directly to `WAITING_FOR_CI`.
- `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` — Update state machine diagram and
  add note explaining why local `make check` was removed.
- `.claude/rules/deferred/60_review_gate.md` — Update merge protocol steps and
  status table to reflect CI-only validation.

### Not Changed

- `run_make_check()` in `claude_fix_adapter.py` — Left in place as a utility
  function (no callers but may be useful for manual invocations).
- Stale fixture — Separate issue, should be fixed in a follow-up PR.

## Outcome

PR #TBD
