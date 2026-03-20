# Session Plan: Promote Sharded CI to Required `tests` Context

**Date:** 2026-03-20

## Goal

Promote the validated 2-way pytest shard split into the required CI merge path
so normal code PRs get the measured wall-clock savings, while preserving the
existing required `tests` status context and the current fast path for
docs/plans-only PRs.

## Decision

Keep the required GitHub status context named `tests` and repurpose that job as
an aggregation gate. This avoids a branch-protection migration.

Current `main` branch protection already requires:
- `tests`
- `governance`

The promotion should keep that contract unchanged unless GitHub check naming
proves incompatible in practice.

## Plan

1. Add CI workflow regression coverage before changing the workflow shape.
   - Add or update a unit test that loads `.github/workflows/ci.yml` and checks
     the promoted structure.
   - Cover the stable required context requirement:
     - a non-matrix `tests` job still exists
     - `tests` is the aggregation job, not the shard matrix job
     - the shard job remains 2-way and uses `pytest-split`
   - Cover the docs/plans-only behavior:
     - the required `tests` job can succeed when heavy jobs are skipped

2. Refactor `.github/workflows/ci.yml` into separate lanes plus a stable gate.
   - Keep the existing `changes` job.
   - Move the current non-pytest checks out of the monolithic `tests` job into
     a dedicated `checks` job:
     - checkout
     - Python setup
     - `uv` setup
     - `uv sync --frozen --extra dev`
     - repo linter
     - config validation
     - docs freshness
     - Ruff
     - skip notice for docs/plans-only PRs
   - Promote the current advisory shard matrix into the real code-test lane as
     `tests-shard`:
     - 2 shards
     - `fail-fast: false`
     - runs on push and on PRs with code changes
     - uses committed `.test_durations`
   - Move notebook work into its own `notebooks` job:
     - notebook hygiene
     - notebook smoke execution
     - runs on push and notebook PRs
   - Move the existing label-driven promotion check into its own
     `promotion-gate` job so it can participate in the aggregation result.
   - Add a new non-matrix `tests` aggregation job that preserves the required
     check context and evaluates upstream lane results.

3. Define the `tests` aggregation semantics explicitly.
   - `tests` must run with `if: always()` so a required status is always posted.
   - `tests` should `needs` the jobs that represent CI outcomes:
     - `changes`
     - `checks`
     - `tests-shard`
     - `notebooks`
     - `promotion-gate`
   - `tests` must fail if any applicable upstream lane is `failure`,
     `cancelled`, or otherwise non-successful.
   - `tests` must accept `skipped` for lanes that do not apply to the current
     PR or push.
   - On docs/plans-only PRs, `tests` should pass quickly after seeing all heavy
     lanes skipped.

4. Remove the now-obsolete shadow trial machinery in the same PR.
   - Delete `.github/workflows/ci_shadow_trial_report.yml`.
   - Delete `scripts/internal/ci_shadow_trial_report.py`.
   - Delete `tests/unit/test_ci_shadow_trial_report.py`.
   - Remove the `ci_shadow_trial_report.py` entry from
     `docs/01_core/ARCHITECTURE.md`.
   - Keep historical session plans in `plans/sessions/`.

5. Validate locally before shipping.
   - Run targeted unit tests for:
     - the CI workflow regression test added for this change
     - `.test_durations` baseline tests
   - Run:
     - `make repo-lint`
     - `make docs-check`
   - Parse changed workflow YAML files with `yaml.safe_load`.
   - If practical, run one shard smoke command locally to confirm the promoted
     shard invocation still resolves.

6. Verify the promoted behavior on the PR before merge.
   - Confirm the PR still publishes a required-looking `tests` check context.
   - Confirm code PRs show:
     - `checks`
     - `tests-shard (1)`
     - `tests-shard (2)`
     - `tests`
   - Confirm docs/plans-only PRs keep a fast green `tests` status.
   - Confirm no manual branch-protection edit is needed.

## Files

- `.github/workflows/ci.yml` — promote the shard matrix and add the stable
  `tests` aggregation job
- `.github/workflows/ci_shadow_trial_report.yml` — remove the now-obsolete trial
  reporter workflow
- `scripts/internal/ci_shadow_trial_report.py` — remove the trial reporter
  script
- `tests/unit/test_ci_shadow_trial_report.py` — remove the trial reporter tests
- `tests/unit/test_ci_shard_baseline.py` — keep passing; update only if needed
- `tests/unit/test_ci_workflow.py` — add workflow-structure regression coverage
- `docs/01_core/ARCHITECTURE.md` — remove the retired script entry

## Rollout Notes

- Preferred path: preserve the existing required `tests` context and avoid any
  branch-protection change.
- Fallback path: if GitHub does not expose the aggregation job as the same
  `tests` check context, stop and switch to a two-step `tests-gate` migration
  with an explicit branch-protection update.
- Remove the shadow reporter in the same PR as promotion so it does not keep
  posting obsolete or misleading summaries after the job names change.

## Outcome

- PR: #1086 (feat/promote-ci-sharding)
- `tests` context preserved as aggregation gate — no branch-protection migration needed
- Shadow trial machinery removed (workflow, script, tests, ARCHITECTURE.md entry)
- 9 workflow regression tests + 6 shard baseline tests pass
- Repo-lint and docs-check pass
