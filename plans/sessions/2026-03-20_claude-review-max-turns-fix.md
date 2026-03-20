# Fix Claude Review Max-Turns Failures

**Date:** 2026-03-20
**Author:** author-b
**Branch:** `fix/claude-review-max-turns`
**Status:** PLANNING

## Problem Statement

The `claude-code-review.yml` GitHub Action workflow has a **60% failure rate**
(18 failures / 30 recent runs). Every failure creates a spam GitHub issue via
the infra-failure classifier, producing 14+ open noise issues.

### Root Cause Analysis

Two compounding problems:

1. **`allowed_tools` input is dead code.** The `anthropics/claude-code-action@v1`
   action does not accept an `allowed_tools` input. GitHub Actions warns but ignores
   it silently. The reviewer retains access to all tools and wastes 1-2 turns on
   permission-denied write operations (Edit, Write, git push).

2. **`--max-turns 5` is too tight.** With 1-2 turns wasted on denials, only 3-4
   effective turns remain. That's insufficient for: read diff + inspect files +
   post comments. The action exits with `error_max_turns`.

3. **Infra-failure classifier creates issues for max-turns exits.** The action
   does NOT set the `execution_file` output when exiting via `error_max_turns`.
   The classifier sees a blank `EXECUTION_FILE`, classifies it as
   `missing_execution_file`, and creates a noise issue.

### Evidence

```
# Failed run 23361490206:
"subtype": "error_max_turns",
"num_turns": 6,
"permission_denials_count": 2

# Classifier env in infra-failure step:
EXECUTION_FILE:     # <-- empty, action didn't set it

# Result: issue created with title "claude-review infra failure (missing_execution_file)"
```

GitHub Actions warning on every run:
```
##[warning]Unexpected input(s) 'allowed_tools', valid inputs are [...]
```

## Plan

### Step 1: Remove broken `allowed_tools` input

**File:** `.github/workflows/claude-code-review.yml`

Remove the `allowed_tools` block (lines 53-66 in current file). This input is
silently ignored by the action — it provides no tool restriction and adds
confusion. The `contents: read` GitHub permission already prevents actual repo
modifications.

### Step 2: Raise `--max-turns` from 5 to 10

**File:** `.github/workflows/claude-code-review.yml`

Change `claude_args: "--max-turns 5"` to `claude_args: "--max-turns 10"`.

Rationale: Successful runs complete in 3-5 turns. With 10 turns, even 2-3
permission denials leave 7-8 effective turns — more than enough. This should
bring the failure rate near zero.

### Step 3: Update infra-failure classifier to filter max-turns exits

**File:** `.github/workflows/claude-code-review.yml`

Two changes to the classifier:

a. When `EXECUTION_FILE` is blank (the most common failure path), emit a
   warning annotation but **do not create a GitHub issue**. The action does not
   set `execution_file` on `error_max_turns` exits, so blank means "probably
   max-turns" — not an infra failure.

b. When `EXECUTION_FILE` exists and `SUBTYPE` is `error_max_turns`, emit a
   warning annotation but **do not create a GitHub issue**. Max-turns is a
   normal operational boundary, not an infra failure.

Issue creation is preserved for genuine infra failures: `execution_file_not_found`,
`unparseable_execution_file`, `unknown`, and any other unexpected subtypes.

### Step 4: Update regression tests

**File:** `tests/unit/test_claude_review_workflow.py`

| Test | Change |
|------|--------|
| `test_max_turns_value` | Assert `--max-turns 10` (was 5) |
| `test_has_allowed_tools` | Remove — input does not exist in the action |
| `test_allowed_tools_includes_read_tools` | Remove — dead code |
| `test_allowed_tools_excludes_write_tools` | Remove — dead code |
| `test_allowed_tools_includes_pr_comment` | Remove — dead code |
| `_allowed_tools_set` helper | Remove — unused after above |
| `test_has_infra_failure_flag_step` | Update docstring — issue creation is now conditional, not universal |
| `test_classifier_handles_missing_execution_file` | Update — assert early exit (no `gh issue create`) on blank path |
| (new) `test_classifier_suppresses_max_turns` | Add — assert `error_max_turns` path exits without issue creation |

### Step 5: Batch-close spam issues

Close all 14 open "claude-review infra failure" issues with a comment linking
to this PR as the fix. This is a manual cleanup step after the PR merges, or
can be done as part of PR validation.

### Step 6: Validation

- `uv run python -m pytest tests/unit/test_claude_review_workflow.py` — targeted
- `make check-quiet` — full pre-PR validation

## Parallelism Assessment

This is a **single-file-pair change** (workflow + test file). No parallelism
needed — all changes are tightly coupled and touch overlapping code.

## Risks

- **Max-turns 10 may increase cost per review.** Acceptable — the action runs
  on Claude Code OAuth (subscription), not API billing.
- **Blank `EXECUTION_FILE` could indicate a real crash, not max-turns.** Risk is
  low — the warning annotation preserves visibility. If real crashes become
  frequent, we can add log parsing in a follow-up. Known gap: OOM or token-expiry
  crashes also produce blank `EXECUTION_FILE` and would be silently downgraded
  to a warning. A future follow-up could add threshold-based alerting
  (e.g., >N blank-file failures per week triggers escalation).

## Outcome

_To be filled after implementation._
