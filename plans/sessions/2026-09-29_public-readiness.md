# Public sharing readiness
**Date:** 2026-09-29
**Goal:** Make the repository understandable and reviewable for hiring teams, with truthful research summaries, portable entry points and verified local commands. Preserve metrics and historical provenance; do not publish or deploy.

## Plan
- Audit current main and the prior review leads in a dedicated worktree.
- Correct report-status generation and affected summaries with regression coverage.
- Improve the README, document the seeded research boundary, and remove personal workspace clutter.
- Fix confirmed operational path dependencies without rewriting historical artifacts.
- Install locked development dependencies; run focused tests, full checks, notebook smoke and repeated seeded experiments.
- Inspect the complete diff and obtain an independent read-only cold review.

## Files
- `README.md`, developer/reproducibility guidance — newcomer orientation and accurate commands.
- `scripts/internal/generate_rung_report.py`, matching tests and affected report summaries — truthful status reporting (exact implementation scope verified during audit).
- `.claude/hooks/worktree-{guard,reminder}.sh`, `.claude/scripts/claude-worktree.sh`, `scripts/internal/overnight_full_orchestrator.sh` and regression tests — portable checkout discovery.
- `Bid-Euchre-agent-audit.code-workspace` — remove personal IDE state; retain generic `.vscode/tasks.json` and CI `.test_durations`.
- Preserve historical paths in model provenance and the Render retirement backup record.

- `notebooks/phase0_bidless/{10_feature_health_checks,30_feature_outcome_eval}.{py,ipynb}` and regression tests — discovered smoke-mode sample sizes were computed before Papermill parameter injection; defer derived settings until after injection.

## Test Criteria
- **Pass condition:** Status summaries retain WARN/FAIL/missing evidence and never claim universal PASS incorrectly; source metrics remain unchanged.
- **Verification command:** Targeted report regression tests; `make check`; `make notebook-run`.
- **Expected result:** Targeted tests and applicable repository gates pass; pre-existing or environment failures are isolated and documented.
- **Pass condition:** README commands execute and two runs with identical config/seed produce identical result JSONs.
- **Verification command:** Run `experiments/run_experiment.py` twice with `experiments/configs/quick_test.yaml`, `--seed 42 --n_per 5`; compare result files.
- **Expected result:** Identical stable metrics, with timestamp/timing metadata excluded.

- **Public hygiene:** Inspect tracked current-tree credential/backup patterns and operational absolute paths; run documentation path checks and local web startup with bundled artifacts. No full-history security audit or live Render availability claim.

## Outcome
- In progress. No push, PR, merge, deployment or visibility change authorized.
