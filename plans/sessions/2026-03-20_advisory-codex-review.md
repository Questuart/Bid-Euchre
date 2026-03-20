# Advisory Codex-Review CI Overlay

**Date:** 2026-03-20
**Branch:** `fix/review-gate-separation`
**Author lane:** steward-author-d

## Goal

Add a visible `codex-review` GitHub Actions PR check that is explicitly
advisory-only, compatible with the shipped `ci` / `review_gate` / `advisory`
three-category split from #1025 and #1030.

## Constraints

- `codex-review` must NOT be merge-blocking
- Must NOT affect `get_ci_status()` (allowlist-based, already safe)
- Must NOT affect `reviewing-changes` as the merge-relevant review gate
- Must NOT revive the old local Codex subprocess loop as primary review
- Workflow uses `openai/codex-action@v1` with `codex exec` and review prompt
- Requires `OPENAI_API_KEY` GitHub secret (API billing, not ChatGPT subscription)

## Implementation Steps

### 1. Add `codex-review` to `ADVISORY_CONTEXTS`

**File:** `src/bid_euchre/ops/__init__.py`

Add `"codex-review"` to `ADVISORY_CONTEXTS` tuple. This automatically:
- Makes `classify_check("codex-review")` return `"advisory"`
- Excludes it from CI aggregation in `_classify_ci_status()` (default path)
- Excludes it from CI aggregation in `poll_ci_status()` (default path)
- Keeps it out of `REVIEW_GATE_CONTEXTS`
- Includes it in `NON_CI_CONTEXTS` union

### 2. Create `.github/workflows/codex-review.yml`

Advisory-only workflow using `openai/codex-action@v1`:
- Trigger: `pull_request` (opened, synchronize, ready_for_review)
- Path filters: code paths only (src/, tests/, scripts/, experiments/)
- Permissions: `contents: read`, `pull-requests: write` (for comments)
- Cost cap: model `o3-mini`, max turns limited
- Posts review as PR comment (not a blocking status)
- `continue-on-error: true` so infra failure never poisons CI

### 3. Add tests

- `test_check_classifier.py`: `codex-review` classified as `advisory`
- `test_check_classifier.py`: `codex-review` in `ADVISORY_CONTEXTS`, in `NON_CI_CONTEXTS`
- `test_ops_ci.py`: `codex-review` failure excluded from CI status (default)
- `test_ops_reviews.py`: `codex-review` failure populates `advisory_status`, not CI
- `test_github_pr_state.py`: `codex-review` not in `_CI_CHECK_NAMES`

### 4. Validation

- Tier 1: `uv run pytest -q tests/unit/test_check_classifier.py tests/unit/test_ops_ci.py tests/unit/test_ops_reviews.py tests/unit/test_github_pr_state.py`
- Tier 2: `make check-quiet`

## Outcome

_To be filled after implementation._
