# Fix Post-Merge Review Scope Creep

**Date:** 2026-03-17
**Status:** COMPLETE
**PR:** (pending)

## Problem

Post-merge reviewer agents repeatedly escape their PR diff scope and produce
gap-analysis reports against plan documents instead of reviewing the actual
changes. Example: PR #800 changed 3 src files, but the reviewer read 9 files
including 4 not in the diff plus a plan document, then reported pre-existing
infrastructure gaps as CRITICAL/WARNING findings.

Root causes:
1. **Hook has no docs-only filter** — fires on every merge including docs/plans PRs
2. **Hook doesn't pass explicit file list** — agents must discover scope themselves
3. **Agent definitions use soft guidance** — "Focus on files in src/" is a suggestion
4. **No anti-pattern for plan gap analysis** — agents read plan docs and compare

## Plan

### Step 1: Add scope guards to hook (`post-merge-review.sh`)
- Compute changed file list via `git diff main~1...main --name-only`
- Filter for code paths: `src/`, `tests/`, `scripts/`, `experiments/`
- Skip entirely if no code files changed (docs-only PRs)
- Pass explicit file list in agent prompts
- Add scope constraint language: "ONLY review", "Do NOT read plan docs"

### Step 2: Add HARD SCOPE CONSTRAINT to all 3 reviewer agents
- `correctness-reviewer.md`: Only read diff files, no plan docs, no pre-existing issues
- `architecture-reviewer.md`: Same, with carve-out for checking callers of changed sigs
- `coverage-reviewer.md`: Same, with carve-out for reading corresponding test files

### Step 3: Add regression tests for hook
- Test docs-only PRs are skipped
- Test code PRs trigger review with file list
- Test scope constraint language is present in output
- Test non-merge commands are skipped
- Test dedup sentinel works

### Step 4: Validate and PR
- `ruff check` on test file
- Run test suite
- Open PR

## Outcome

PR #(pending) — 5 files changed:
- `.claude/hooks/post-merge-review.sh` — docs-only filter + file list + scope language
- `.claude/agents/correctness-reviewer.md` — hard scope constraint section
- `.claude/agents/architecture-reviewer.md` — hard scope constraint section
- `.claude/agents/coverage-reviewer.md` — hard scope constraint section
- `tests/unit/test_post_merge_review_hook.py` — 10 new tests
