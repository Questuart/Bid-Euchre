# Sync SKIPPED CI handling to ops helpers

**Date:** 2026-03-21
**Issue:** #1191
**Parent PR:** #1190 (merged)
**Goal:** Align the 4 remaining CI-status aggregation sites with the fix from #1190 so operator-facing tools report consistent status for path-filtered PRs.

## Context

PR #1190 fixed `get_ci_status()` (in `scripts/internal/github_pr_state.py`) and the bash merge guard to treat `SKIPPED` CI checks as terminal-success. Four other aggregation sites in `src/bid_euchre/ops/` still use `all(s == "SUCCESS")` and will report `unknown` for the same PRs that the merge gate already passed.

## Scope

### Files to change

| File | Line | Function | Fix |
|------|------|----------|-----|
| `src/bid_euchre/ops/reviews.py` | 168 | `_classify_ci_status()` | `all(s == "SUCCESS")` → `all(s in ("SUCCESS", "SKIPPED"))` |
| `src/bid_euchre/ops/reviews.py` | 203 | `_get_review_status()` | Same pattern — but **verify first**: review-gate checks probably don't emit SKIPPED. If so, skip this one. |
| `src/bid_euchre/ops/reviews.py` | 244 | `_get_advisory_status()` | Same — verify whether advisory checks can be SKIPPED. |
| `src/bid_euchre/ops/ci.py` | 319 | `get_ci_status()` (the ops version) | `all(c.state == "SUCCESS")` → `all(c.state in ("SUCCESS", "SKIPPED"))` |

### Test files

| Test file | What to add |
|-----------|-------------|
| `tests/unit/test_ops_reviews.py` | Test `_classify_ci_status()` returns `"success"` for SUCCESS+SKIPPED mix |
| `tests/unit/test_ops_ci.py` | Test `get_ci_status()` returns `"success"` for SUCCESS+SKIPPED mix |

### Explicitly out of scope

- `scripts/internal/github_pr_state.py` — already fixed in #1190
- `.claude/hooks/pre-merge-review-guard.sh` — already fixed in #1190
- `scripts/internal/review_driver.py` — already fixed in #1190

## Implementation guidance

1. **Start with `_classify_ci_status()` (reviews.py:168) and `get_ci_status()` (ci.py:319)** — these are the CI aggregators and definitely see SKIPPED states from path-filtered jobs.

2. **Evaluate `_get_review_status()` and `_get_advisory_status()`** — these aggregate review-gate and advisory checks respectively (e.g., `reviewing-changes`, `claude-review`). GitHub status checks (commit statuses) don't have a SKIPPED state — only check runs (Actions jobs) do. If these functions only see commit statuses, the fix is unnecessary. Add it defensively if uncertain, or document why it's skipped.

3. **Follow the test patterns** already in `test_ops_reviews.py` and `test_ops_ci.py` — they mock `subprocess.run` with check JSON payloads. Add cases mirroring the 4 tests from `test_github_pr_state.py::TestGetCIStatus`:
   - SUCCESS + SKIPPED → success
   - All SKIPPED → success
   - FAILURE + SKIPPED → failure
   - PENDING + SKIPPED → pending

## Validation

```bash
uv run python -m pytest -q tests/unit/test_ops_reviews.py tests/unit/test_ops_ci.py
make check-quiet
```

## PR notes

- Reference #1191 in the PR body
- This is a consistency follow-up to #1190, not a new feature
- Suggested commit: `fix: sync SKIPPED CI handling to ops helpers (#1191)`

## Outcome

PR #1192 — `fix: sync SKIPPED CI handling to ops helpers`
- 4 source sites fixed (3 in reviews.py, 1 in ci.py)
- 10 new test cases added across both test files
- 181 tests pass, `make check-quiet` clean
