# Session Plan: Automate CI Shadow Shard Trial Reporting

**Date:** 2026-03-20

## Goal

Automatically record the serial-vs-sharded CI timing data for the shadow shard
trial so the repo no longer depends on manual inspection of GitHub Actions
runs. The automation should publish the current PR's CI timing data and a
rolling summary from recent PR runs without changing required checks.

## Plan

1. Add a stdlib-only reporter script that reads a completed `workflow_run`
   event, fetches CI job timing data from the GitHub Actions API, computes the
   current PR's serial/shard metrics, and builds a rolling summary from recent
   successful PR runs of the same workflow.
2. Add unit tests for the reporter's data extraction, summary math, and
   markdown rendering.
3. Add a new `workflow_run` workflow that runs after `CI` completes on PRs,
   invokes the reporter, and upserts a machine-owned PR comment.
4. Keep the automation non-invasive:
   - no change to required checks
   - no dependency on `uv sync`
   - no manual operator step
5. Validate with targeted unit tests plus workflow YAML parsing.

## Files

- `.github/workflows/ci_shadow_trial_report.yml` — post-CI workflow that runs
  on completed `CI` workflow runs for PRs and invokes the reporter script.
- `scripts/internal/ci_shadow_trial_report.py` — stdlib-only reporter that
  fetches run/job data, computes metrics, and upserts a PR comment.
- `tests/unit/test_ci_shadow_trial_report.py` — unit tests for summary math,
  job extraction, and comment rendering.

## Outcome

<!-- Filled after implementation -->
- PR: TBD
- Notes: TBD
