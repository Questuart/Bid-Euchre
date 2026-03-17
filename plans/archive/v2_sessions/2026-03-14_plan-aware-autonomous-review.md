# Plan-Aware Autonomous Review Enforcement
**Date:** 2026-03-14
**Goal:** Tighten the existing autonomous PR review loop so it validates the PR's declared plan, detects scope drift against that plan, and leaves durable blocker feedback on the PR. Keep the core architecture local-first and status-driven; do not build repo-critical behavior around auth-file hacks.

## Review Amendments (2026-03-14)

Changes from the original plan based on code review of the existing infrastructure:

1. **Scope-drift severity downgraded to P2 (non-blocking).** Plans in this repo use `## Files` as aspirational, not contractual. Actual PRs routinely touch files beyond the plan (exports, conftest, transitive deps). Blocking on drift would produce excessive false positives. Scope drift is reported as a P2 warning with a PR comment; upgrade to P1 only after false-positive rate data proves it's reliable.

2. **"Minimum execution contract" replaced with concrete checks.** Three checks: (a) plan reference present in PR body (P2 if missing — some PRs are trivially N/A), (b) referenced plan file exists on disk (P1 if broken reference), (c) plan file has non-trivial content beyond template boilerplate (P2 if empty/skeleton). No section-structure enforcement.

3. **Plan/scope checks live in `review_driver.py`, not `deterministic_prechecks.py`.** Plan checks need PR body context (fetched from GitHub API), which doesn't fit the `check_file()`/`check_diff()` interface that operates on file content and changed-file lists. The driver gets a new `_validate_plan()` step called in `_step_pr_open()` before prechecks.

4. **New `get_pr_changed_files()` helper in `github_pr_state.py`.** Scope-drift needs the changed file list. Currently the driver gets this from `git diff` in `main()`. Centralizing it in the PR state module makes it reusable and testable.

## Plan
- Extend `PRMetadata` with `body` field and add `get_pr_body()` to retrieve it. Add `get_pr_changed_files()` helper.
- Add plan-reference parsing: extract the plan path from the PR body's `## Plan` section.
- Add plan validation in the driver (`_validate_plan()`): check plan reference present, file exists, file has content. Results stored as findings with appropriate severity (P1/P2).
- Add idempotent PR comment upsert (`upsert_review_comment()`) using a machine-owned marker and head SHA for deduplication.
- Add scope-drift check: compare changed files against the plan's `## Files` section. Report undeclared files as P2 warning in the PR comment.
- Add structured review summaries: format deterministic precheck failures and Codex findings into the PR comment body.
- Wire blocker comment posting into all terminal-failure paths in the driver.
- Make Codex CLI invocation configurable via `CODEX_REVIEW_CMD` env var, preserving the current preference chain as fallback.
- Back all new behavior with focused unit tests.
- Update `AUTONOMOUS_REVIEW_LOOP.md` and `CODEX_GITHUB_REVIEW.md`.

## Files
- `scripts/internal/github_pr_state.py` — add `body` to `PRMetadata`, add `get_pr_body()`, `get_pr_changed_files()`, `upsert_review_comment()`.
- `scripts/internal/review_driver.py` — add `_validate_plan()`, `_parse_plan_reference()`, `_check_scope_drift()`, wire into `_step_pr_open()`. Post blocker comments on stop paths.
- `scripts/internal/review_state.py` — add `plan_path` and `plan_findings` fields to `ReviewLoopState` if needed for persistence.
- `scripts/internal/codex_review_adapter.py` — add `CODEX_REVIEW_CMD` env-var support in `_resolve_codex_binary()`.
- `tests/unit/test_github_pr_state.py` (new) — PR body retrieval, changed files, comment upsert.
- `tests/unit/test_review_driver.py` (new) — plan validation, scope-drift, blocker comment publishing.
- `tests/unit/test_codex_review_adapter.py` — configurable launcher tests.
- `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` — document plan-aware enforcement, blocker comments, launcher contract.
- `docs/02_agent/CODEX_GITHUB_REVIEW.md` — align with new plan-enforcement and comment behavior.

## Validation
- `uv run python -m pytest tests/unit/test_github_pr_state.py`
- `uv run python -m pytest tests/unit/test_review_driver.py`
- `uv run python -m pytest tests/unit/test_codex_review_adapter.py`
- `uv run python -m pytest tests/unit/test_review_state.py`
- `uv run python -m pytest tests/unit/test_deterministic_prechecks.py`
- `make check-quiet`

## Sequencing
- PR 1: PR metadata enrichment + plan parsing + plan validation + unit tests.
- PR 2: Scope-drift detection + blocker comment upsert + review summary formatting + unit tests.
- PR 3: Configurable Codex launcher + documentation alignment.

## Non-Goals
- Do not move the review loop into GitHub Actions as the primary reviewer.
- Do not commit `.codex.json`, token refresh logic, or any machine-local auth artifacts.
- Do not rely on prompt wording alone for plan adherence when deterministic checks can enforce the contract.
- Do not expand the auto-fixer beyond safe mechanical edits as part of this change.
- Do not enforce specific plan section structure (e.g., requiring `## Validation` or `## Sequencing`).

## Risks
- Scope-drift detection can be noisy if the plan file format is too loose; this is mitigated by making it P2 (non-blocking) initially.
- PR comment upsert logic can spam if deduplication is weak; the implementation keys on a stable marker (`<!-- review-loop-comment -->`) plus head SHA.
- A configurable launcher can make failures less obvious if misconfigured; preserve clear error reporting when the custom command is absent or exits non-zero.
- Plan validation adds a GitHub API call to `_step_pr_open()` which could slow the loop or fail if `gh` auth is misconfigured; failures should be non-blocking (log + continue).

## Outcome
<!-- Filled after implementation -->
- PR:
- Notes:
