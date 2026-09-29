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
- `src/bid_euchre/arc_d_v2/report.py`, matching tests and affected report summaries — truthful status reporting (exact implementation scope verified during audit).
- `.claude/hooks/worktree-{guard,reminder}.sh`, `.claude/scripts/claude-worktree.sh`, `scripts/internal/overnight_full_orchestrator.sh` and regression tests — portable checkout discovery.
- `Bid-Euchre-agent-audit.code-workspace` — remove personal IDE state; retain generic `.vscode/tasks.json` and CI `.test_durations`.
- Preserve historical paths in model provenance and the Render retirement backup record.

- `notebooks/phase0_bidless/{10_feature_health_checks,30_feature_outcome_eval}.{py,ipynb}` and regression tests — discovered smoke-mode sample sizes were computed before Papermill parameter injection; defer derived settings until after injection.

- Independent engine audit expansion: correct all-pass trick aggregation, propagate logged deal seeds, preserve effective strategy/bidder parameters, and pass moon/loner auction context to learned bidders. Add regressions and rerun affected integration/full checks. Preserve published historical results; explain runtime compatibility changes and independent-hand dealer sampling.

## Test Criteria
- **Pass condition:** Status summaries retain WARN/FAIL/missing evidence and never claim universal PASS incorrectly; source metrics remain unchanged.
- **Verification command:** Targeted report regression tests; `make check`; `make notebook-run`.
- **Expected result:** Targeted tests and applicable repository gates pass; pre-existing or environment failures are isolated and documented.
- **Pass condition:** README commands execute and two runs with identical config/seed produce identical result JSONs.
- **Verification command:** Run `experiments/run_experiment.py` twice with `experiments/configs/quick_test.yaml`, `--seed 42 --n_per 5`; compare result files.
- **Expected result:** Identical stable metrics, with timestamp/timing metadata excluded.

- **Public hygiene:** Inspect tracked current-tree credential/backup patterns and operational absolute paths; run documentation path checks and local web startup with bundled artifacts. No full-history security audit or live Render availability claim.

## Outcome
- Completed locally on `share-readiness`; no push, PR, merge, deployment or visibility change.
- Full canonical test selection plus focused environment/test-fixture recovery: 12,930 passed, 59 skipped at the verification checkpoint. This was not one uninterrupted green `make check` invocation.
- Fresh review initially found three blockers: empty-sample comparisons, omitted matrix matchups in snapshots, and hosted dealer takeover application. Corrected all three with regressions; parent integrated follow-up: 3,645 passed, 14 skipped.
- Repository lint, Ruff, notebook hygiene, documentation gates, three notebook smoke executions, and repeated seeded result comparisons passed. Source CSVs, model snapshots and report manifests remain unchanged.
- Fresh read-only review of code at `992fef4` returned **ship** after 32 independent focused passes and an AI-dealer takeover check.
- Known non-blocking residual: unchanged comparison routines still accept exactly one observation, which can yield undefined effect size and inconsistent inferential output. Do not use single-observation runs for statistical conclusions. No general statistical-methodology audit, live deployment or visual browser review was performed.
