# Phase 3C: Review/CI Migration Surfaces

**Date:** 2026-03-18
**Lane:** author-c (`codex/steward-author-c`)
**Parent plan:** `plans/sessions/2026-03-18_pr3-operator-cli.md` section Phase 3C
**Governing plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` section PR-3

## Goal

Add two new ops surfaces — `reviews` and `ci` — that provide provider-neutral
PR review outcome aggregation and CI failure classification. Also create a
GitHub-hosted deterministic prechecks workflow.

## Design Principles

1. **GitHub is the source of truth** for PR review outcomes (online-first).
2. **No new dependencies on `.claude/runtime/review_loops/**`** — transitional only.
3. **CI classification is pure Python** — fully testable without GitHub.
4. **Import reuse** — `ops/reviews.py` imports from `scripts/internal/github_pr_state.py`.

## Files

| File | Action | Purpose |
|------|--------|---------|
| `src/bid_euchre/ops/reviews.py` | Create | Provider-neutral review outcome aggregation |
| `src/bid_euchre/ops/ci.py` | Create | CI failure classification (pure Python) |
| `tests/unit/test_ops_reviews.py` | Create | Review aggregation tests (mock `gh`) |
| `tests/unit/test_ops_ci.py` | Create | CI classification tests (pure Python) |
| `scripts/internal/ops.py` | Modify | Add `reviews` and `ci` subcommands |
| `tests/unit/test_ops_cli.py` | Modify | CLI tests for new subcommands |
| `.github/workflows/deterministic-prechecks.yml` | Create | GitHub-hosted prechecks workflow |

## Implementation Order

1. `ops/reviews.py` — ReviewOutcome dataclass, `get_open_pr_reviews()`, `get_pr_review_detail()`
2. `ops/ci.py` — 6 failure classes, CIFailureClassification, `classify_ci_failure()`, `poll_ci_status()`
3. `test_ops_reviews.py` + `test_ops_ci.py` — mock `gh` for reviews, pure Python for CI
4. CLI wiring — `ops.py reviews [--json]`, `ops.py ci [--pr N] [--json]`
5. CLI tests — extend `test_ops_cli.py`
6. `deterministic-prechecks.yml` — GitHub workflow
7. Validation — `make check-quiet`

## Key Design Decisions

### reviews.py

- `get_open_pr_reviews()` calls `gh pr list --json` to get open PRs, then
  enriches each with CI status and review status from existing
  `github_pr_state.get_ci_status()`.
- `get_pr_review_detail(pr_number)` returns a single `ReviewOutcome`.
- Review status comes from GitHub commit status API (`reviewing-changes` context).
- Deterministic prechecks status comes from GitHub checks API.
- Format functions: `format_reviews_text()`, `format_reviews_json()`.

### ci.py

- 6 failure classes with metadata (auto_remediable, max_retries):
  `lint_format`, `deterministic_test`, `missing_config`, `flaky_external`,
  `infra_auth`, `risky_destructive`.
- `classify_ci_failure(check_output)` — pure Python regex/keyword matching.
- `poll_ci_status(pr_number)` — wraps `gh pr checks` with per-check breakdown.
- `format_ci_text()`, `format_ci_json()`.

### GitHub Workflow

- Runs `deterministic_prechecks.py` via `check_diff()`.
- Fetch depth 0 (full history) to ensure `origin/main...HEAD` works.
- Triggered on PR events (opened, synchronize, reopened).
- Uses `uv run python` for consistent environment.

## Validation Plan

- Tier 1: `uv run python -m pytest tests/unit/test_ops_reviews.py tests/unit/test_ops_ci.py -v`
- Tier 2: `make check-quiet`
- Failure injection: test with malformed `gh` output, unknown check names
- CLI smoke: `ops.py reviews --json`, `ops.py ci --json`

## Out of Scope

- Doc updates to AUTONOMOUS_REVIEW_LOOP.md and CODEX_GITHUB_REVIEW.md (deferred to separate PR)
- Skill file updates for `/review-plan` (deferred)
- Watchdog extensions for CI stuck detection (Phase 3D)
- Retry/reroute policy (Phase 3D)

## Outcome

Implemented in PR #___ (pending). 8 files: 2 new source modules, 2 new test files,
1 new GitHub workflow, 1 session plan, 2 modified files (CLI + CLI tests).

- `ops/reviews.py`: ReviewOutcome dataclass, `get_open_pr_reviews()`, `get_pr_review_detail()`, text/JSON formatters
- `ops/ci.py`: 6 failure classes, CIFailureClassification, `classify_ci_failure()`, `poll_ci_status()`, text/JSON formatters
- CLI: `ops.py reviews [--pr N] [--json]`, `ops.py ci --pr N [--json]`
- GitHub workflow: `deterministic-prechecks.yml` — runs `deterministic_prechecks.py` on PR events
- 106 new tests (33 reviews + 58 CI + 15 CLI), 230 total ops tests, `make check-quiet` clean
