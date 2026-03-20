# Session Plan: CI Efficiency Phase 1 Cleanup and Shadow Sharding Trial

**Date:** 2026-03-20

## Summary

Implement the low-risk CI efficiency changes that have clear upside and minimal
merge risk, then add a non-required 2-shard shadow pytest job so the team can
measure wall-clock savings before changing the required `tests` check.

## Goal

Reduce avoidable CI overhead now, preserve the current required `tests` branch
protection context, and create a safe measurement path for balanced sharding.
This session does not promote sharding to required, does not enable
`pytest-xdist`, and does not change push-path filtering.

## Baseline

- Required PR critical path is dominated by `make test` in
  `.github/workflows/ci.yml`; recent successful PR runs were roughly 8 minutes
  total with about 7.5 minutes in the `Tests (fast)` step.
- The dedicated Arc D v2 step reruns tests already covered by `make test`,
  costing extra time on Arc D-related PRs.
- `scripts/internal/deterministic_prechecks.py` runs with plain `python3`
  without a synced environment.
- `scripts/check_infra_pr_metadata.py` already runs with plain `python` in the
  governance workflow; governance is already mostly clean.
- `uv sync --frozen --all-extras` is fast but still installs an unused hosted
  extra on CI runners.
- The current required GitHub check is `tests`; do not rename it, matrix it, or
  otherwise change its status context in this session.

## Scope Boundary

### In Scope

- Remove the duplicate Arc D pytest lane from CI.
- Simplify deterministic prechecks to use plain `python3`.
- Narrow CI dependency sync from `--all-extras` to `--extra dev` in workflows
  that only need dev/test tooling.
- Add a non-required 2-way shadow sharding job for PR code changes.
- Commit a duration baseline artifact if the chosen sharding mechanism needs it.

### Out of Scope

- Promoting sharding to replace the required `tests` lane.
- Enabling `pytest-xdist`.
- Changing branch protection in GitHub.
- Adding push-path filtering for docs/plans-only merges.
- Refactoring the required `tests` job into a matrix.

## Decisions

1. Keep the existing required `tests` job unchanged.
   This avoids branch-protection churn during the measurement phase.

2. Prefer balanced sharding over `xdist` for the first experiment.
   The shadow job should isolate work across runners instead of introducing a
   new in-process parallel execution model into the required lane.

3. Prefer a duration-aware sharding mechanism.
   If a plugin is needed, use it only for the non-required shadow job and
   commit the duration baseline it needs so the first trial is informative.

4. Treat branch-protection migration as a follow-on step.
   If sharding is later promoted, add an aggregation job such as `tests-gate`
   and coordinate the required-check update atomically with the workflow change.

## Plan

### Step 0: Pre-change verification

1. Confirm there is no existing duration artifact for pytest sharding.
2. Confirm no hosted-package imports exist in `src/`, `tests/`, or `scripts/`.
3. Confirm the required `tests` job name and status context remain unchanged.

### Step 1: Remove duplicate Arc D CI work

1. Edit `.github/workflows/ci.yml`.
2. Remove the `Arc D v2 pipeline smoke` step.
3. Remove the `arc_d_v2` paths-filter block if it has no remaining consumers.
4. Update skip/setup condition comments so the workflow description matches the
   new logic.

**Success condition:** PR code changes still run the required `tests` lane, and
Arc D-specific test files are no longer invoked a second time by CI.

### Step 2: Simplify deterministic prechecks

1. Edit `.github/workflows/deterministic-prechecks.yml`.
2. Remove `actions/setup-python`, `astral-sh/setup-uv`, and `uv sync`.
3. Replace `uv run python` with `python3`.
4. Preserve the current output, blocking behavior, and `PYTHONPATH` setup.

**Success condition:** The workflow still reports the same findings, but no
longer builds a Python environment.

### Step 3: Narrow CI sync to dev tooling only

1. Replace `uv sync --frozen --all-extras` with
   `uv sync --frozen --extra dev` in workflows that only need dev/test tools.
2. Apply this to:
   - `.github/workflows/ci.yml`
   - `.github/workflows/bid_eval_tiny.yml`
   - `.github/workflows/dashboard.yml`
   - `.github/workflows/nightly_baseline_full.yml`
   - `.github/workflows/baseline_full_drift.yml`
3. Do not widen scope into workflows that do not use `uv sync`.

**Success condition:** CI workflows still install the toolchain they need, but
do not install the currently unused hosted extra.

### Step 4: Add a duration baseline for sharding

1. Choose a balanced sharding mechanism for the shadow job.
   Preferred: `pytest-split` with its duration baseline file.
2. If the mechanism requires a dev dependency, add it to `pyproject.toml`.
3. Generate and commit the duration artifact used by the chosen mechanism.
   If using `pytest-split`, prefer the plugin's default duration file and keep
   the workflow invocation explicit about the path if needed.

**Success condition:** The shadow job can use a committed baseline rather than
an arbitrary alphabetical or file-count split.

### Step 5: Add a non-required 2-shard shadow job

1. Add a new job to `.github/workflows/ci.yml` for PR code changes only.
2. Keep it separate from the required `tests` job.
3. Use two shards with:
   - `continue-on-error: true`
   - `strategy.fail-fast: false`
4. Do not run the shadow job on push events.
5. Avoid relying on another job's step outputs; if needed, run a local
   `dorny/paths-filter` step inside the shadow job or use a small dedicated
   changes-detection job with explicit outputs.
6. Make the job name clearly non-required, for example
   `tests-shadow-shard (1/2)` and `tests-shadow-shard (2/2)`.
7. Log enough information to compare shard runtime and stability over several
   PRs.

**Success condition:** Code PRs show a non-blocking 2-shard shadow run without
changing the required `tests` status context.

## Files

- `.github/workflows/ci.yml` — remove Arc D duplicate lane; add non-required
  shadow sharding job; update sync command and comments.
- `.github/workflows/deterministic-prechecks.yml` — remove Python/uv bootstrap
  and switch to plain `python3`.
- `.github/workflows/bid_eval_tiny.yml` — narrow sync to `--extra dev`.
- `.github/workflows/dashboard.yml` — narrow sync to `--extra dev`.
- `.github/workflows/nightly_baseline_full.yml` — narrow sync to `--extra dev`.
- `.github/workflows/baseline_full_drift.yml` — narrow sync to `--extra dev`.
- `pyproject.toml` — add sharding plugin only if the chosen shadow-job
  mechanism requires it.
- Duration artifact file — commit the baseline required by the chosen sharding
  mechanism if applicable.

## Validation

### Local commands

1. Verify hosted imports remain absent:
   `rg -n "fastapi|uvicorn|sqlalchemy|psycopg|jinja2|httpx|python-multipart" src tests scripts`
2. Verify deterministic prechecks with system Python:
   `python3 -c "import sys; sys.path.insert(0, 'scripts/internal'); from deterministic_prechecks import check_diff, get_blocking_findings; f = check_diff(base='origin/main'); print(len(f), len(get_blocking_findings(f)))"`
3. Verify infra metadata script with system Python:
   `python3 scripts/check_infra_pr_metadata.py --pr-body 'test body' --changed-files .github/workflows/ci.yml`
4. Targeted tests:
   - `.venv/bin/python -m pytest -q tests/unit/test_deterministic_prechecks.py`
   - `.venv/bin/python -m pytest -q tests/unit/test_check_infra_pr_metadata.py`
   - `.venv/bin/python -m pytest -q tests/unit/test_lint_repo.py`
   - `.venv/bin/python -m pytest -q tests/unit/test_docs_freshness.py`
5. If a sharding plugin is added:
   - generate the duration baseline locally
   - run a smoke command proving each shard command starts correctly
6. YAML sanity check for changed workflow files using Python + `yaml.safe_load`.

### CI observation after merge of the patch

Track at least 5 normal code PRs and record:

- shadow shard elapsed times
- shard balance
- unexplained failures or collection issues
- whether the required `tests` lane remains stable and unchanged

## Trial Exit Criteria

The shadow sharding trial is successful only if all of the following hold:

1. The required `tests` job remains the only merge-blocking test context.
2. The shadow job runs on code PRs and is absent from non-code PRs.
3. Both shards complete on each trial PR even if one shard fails.
4. No unexplained shard-specific import or collection failures occur across at
   least 5 PRs.
5. Shard balance is good enough to justify promotion.
   Target: neither shard should regularly exceed roughly 60% of total shard
   wall-clock.

## Risks and Rollback

- If the shadow sharding mechanism proves brittle, keep it non-required and
  revert only the shadow-job portion in a follow-on patch.
- If narrowing sync to `--extra dev` exposes an implicit hosted dependency,
  restore `--all-extras` in the affected workflow only.
- If removing the Arc D lane hides a needed CI surface, restore it only with a
  genuinely disjoint trigger.

## Promotion Path (Deferred)

If the shadow sharding trial succeeds, a follow-on session should:

1. Convert the required lane to a promoted sharded implementation.
2. Add an aggregation job such as `tests-gate` that produces a single stable
   required context.
3. Coordinate the branch-protection update from `tests` to the new stable gate
   atomically with the workflow change.
4. Only after that, consider whether the old serial `tests` job should be
   removed.

## Handoff Notes

- This session plan is intended for implementation by another agent.
- The agent should refresh this plan before editing, keep scope limited to the
  steps above, and report validation results plus any deviations.
- If the chosen sharding mechanism forces materially broader repo changes than
  described here, stop and update the plan before proceeding.

## Outcome

<!-- Filled after implementation -->
- PR: TBD
- Notes: TBD
