# Session Plan: Post-Merge Review Fixes Batch 6

**Date:** 2026-03-21
**Lane:** steward-author-c
**Scope:** Fix 4 unaddressed post-merge review findings

## Context

Post-merge review of PRs #1122–#1124 identified 4 unaddressed WARN-level
findings. This plan patches them in a single bounded PR.

## Findings

### Finding 1: `classify_fix_pr` unhandled `ValueError`
**Severity:** WARN | **Confidence:** HIGH | **Source PR:** #1124

In `scripts/internal/review_quality_audit.py`, the `fix(fix:` branch at
line 356 calls `title_lower.index(")")` without a try/except. If the title
has no closing paren (e.g. `"fix(fix:convention: missing paren"`), this
raises `ValueError`. The `fix(` branch at line 365 already has this guard.

**Fix:** Wrap line 356 in try/except matching the `fix(` pattern.
**Test:** Add `test_fix_fix_missing_paren` to `TestClassifyFixPr`.

### Finding 2: `SOURCE_TYPES` missing `"pr_comment"`
**Severity:** WARN | **Confidence:** HIGH | **Source PR:** #1122

PR #1122 added `"pr_comment"` to `ENTRY_TYPES` in
`src/bid_euchre/ops/index.py` (line 130) but did not add a corresponding
entry to `SOURCE_TYPES` (lines 108–117). While `SOURCE_TYPES` is not
runtime-enforced, the two sets form a parallel contract.

**Fix:** Add `"pr_comment"` to `SOURCE_TYPES`.

### Finding 3: "review loop" → "coordinator" terminology incomplete
**Severity:** WARN | **Confidence:** HIGH | **Source PR:** #1123

PR #1123 renamed the architecture to "local coordinator" but left stale
"review loop" references in three locations:

| Sub | File | Count | Fix |
|-----|------|-------|-----|
| 3a | `.claude/rules/deferred/60_review_gate.md` | 12 refs | Replace with "review coordinator" |
| 3b | `scripts/internal/review_driver.py` | 8 refs | Replace user-visible strings |
| 3c | `.vscode/tasks.json` | 1 ref | Update label |

**Fix:** Targeted string replacements in each file. Preserve "review loop"
only where it's a proper noun in historical notes (e.g. "PR #624" context).

### Finding 4: Inconsistent fallback values in review audit
**Severity:** INFO→WARN | **Confidence:** HIGH | **Source PR:** #1124

`_aggregate_codex` uses `"unstructured"` as the fallback for null check_id,
while `_aggregate_scoring` uses `"unknown"`. Since scoring operates on Codex
findings, filtered counts land on a different aggregate key than totals for
the same null-check_id finding.

**Fix:** Align `_aggregate_scoring` to use `"unstructured"` (matching
`_aggregate_codex` and `_aggregate_fixes`).

## Files Changed

| File | Finding | Change |
|------|---------|--------|
| `scripts/internal/review_quality_audit.py` | #1, #4 | try/except + fallback alignment |
| `tests/unit/test_review_quality_audit.py` | #1 | Add missing-paren test |
| `src/bid_euchre/ops/index.py` | #2 | Add `"pr_comment"` to SOURCE_TYPES |
| `.claude/rules/deferred/60_review_gate.md` | #3a | Terminology update |
| `scripts/internal/review_driver.py` | #3b | Terminology update |
| `.vscode/tasks.json` | #3c | Label update |

## Validation

- **Tier 1:** `uv run python -m pytest tests/unit/test_review_quality_audit.py -x -v`
- **Tier 1:** `uv run python -m pytest tests/unit/test_index.py -x -v`
- **Tier 2:** `make check-quiet` before PR

## Outcome

_To be filled after implementation._
