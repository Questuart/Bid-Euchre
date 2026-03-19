<!-- review-tier: small -->
# Session Plan: Fix PR-Scope Leaks in Review Driver Prechecks

**Date:** 2026-03-18
**Lane:** author-b
**Branch:** `fix/issue-cleanup-batch`

## Problem

Two scope leaks cause the review driver to run prechecks against local
worktree state instead of the actual PR diff:

1. Mode initialization uses local `git diff origin/main...HEAD`
2. `check_diff()` discovers files via local git diff, ignoring PR-scoped
   files available at the call site

## Changes

| File | Change |
|------|--------|
| `scripts/internal/deterministic_prechecks.py` | Add `changed_files` param to `check_diff()` |
| `scripts/internal/review_driver.py` | Thread PR files into prechecks + mode init |
| `tests/unit/test_deterministic_prechecks.py` | 4 new tests for `check_diff(changed_files=...)` |
| `tests/unit/test_review_driver.py` | 1 new test for mode classification |

## Outcome

Merged as part of PR #875. Scope fix + convention follow-ups shipped together.
Follow-up PR addresses F1-F7 review findings.
