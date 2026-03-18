# Phase E: QUICK Bundle Cleanup & Closure

**Date:** 2026-03-17
**Author:** steward-author-b
**Type:** Session plan (standalone)
**Parent:** Arc D v2 lineage — Phase E from MEMORY.md

## Context

Phase E was defined as "Regenerate QUICK bundles (R0-R3)" after the chart suite
PRs (#768, #769, #771, #775) merged. The bundles needed regeneration because
they were originally produced with pre-chart-suite code.

**PR #802** (merged 2026-03-17) already committed 412 report files covering
R0-R3 for `canonical/`, `quick/`, and `full/` (R0 only) modes. These bundles
were generated AFTER all chart suite PRs and PR #800 (report generation fixes)
merged, meaning they already use the new 23-chart registry, 3x2 dashboard
layouts, and intelligence-faceted H2H charts.

## Current State Audit

### Bundle inventory (per rung, `quick/` mode):
- 14 canonical CSVs in `tables/`
- 7 chart_data CSVs in `chart_data/`
- 3 dashboard PNGs in `charts/`
- 15 standalone PNGs in `charts/full_chart_suite/`
- 3 markdown reports (00_manifest, 01_results, 02_decision)
- 1 evidence_manifest.json

### Chart coverage: 17/23 present, 6 absent (all `required: false`)

| # | Chart | Status | Missing source CSV | Why absent |
|---|-------|--------|--------------------|------------|
| 10 | seat_balance.png | ABSENT | seat_balance.csv | No QUICK parquet on disk |
| 16 | pred_vs_actual.png | ABSENT | predictions.csv | No QUICK parquet + joblib models not reachable |
| 17 | residual_distribution.png | ABSENT | residuals.csv | Same as #16 |
| 18 | calibration_curve.png | ABSENT | calibration_bins.csv | Same as #16 |
| 21 | decision_agreement.png | ABSENT | decision_comparison.csv | No QUICK parquet |
| 22 | disagreement_outcomes.png | ABSENT | disagreement_outcomes.csv | No QUICK parquet |

All 6 absent charts require `action_value.parquet` data from `data/runs/`.
The QUICK parquet was not preserved after training (only SMOKE parquet exists
in `base_datasets/pre_r3/smoke/`). Generating these charts would require
re-running step 1 (5,000-deal dataset generation) — out of scope for this PR.

### Anomalies found:

1. **`outcome_summary.png`** exists in all bundles but is NOT in the 23-chart
   registry. It was superseded by chart #9 (`outcome_distributions.png`). The
   report markdown does not reference it. The evidence manifest does not track it.

2. **`canonical/` directories** contain SMOKE-tier outputs (25 deals, ~50 per
   H2H cell). These are debug-level quality, not citable as evidence. However,
   they were intentionally committed in PR #802 as archival records of the
   SMOKE pipeline output.

## Plan

### Step 1: Remove stale `outcome_summary.png` from all bundles

Delete `outcome_summary.png` from `charts/full_chart_suite/` across all committed
report bundles. It's not in the registry, not referenced in reports, and
clutters the chart suite directory.

**Files to delete (8 files):**
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/canonical/charts/full_chart_suite/outcome_summary.png`
- `docs/04_reports/arc_d_v2/r{0,1,2,3}/quick/charts/full_chart_suite/outcome_summary.png`

Also delete from `r0/full/` if present.

### Step 2: Remove `outcome_summary.png` generation from chart pipeline

In `scripts/internal/generate_rung_charts.py`, the `generate_outcome_summary()`
function and its invocation in the standalone chart loop produce a chart that
the registry doesn't track. Options:

- **(A) Remove the generator entirely.** Clean break — no orphan charts.
- **(B) Guard with registry check.** Keep the generator but skip if not in registry.

**Recommendation: (A)** — Remove both the function and its call site. The
dashboard already has outcome distribution panels via `outcome_distributions.csv`,
and chart #9 (`outcome_distributions.png`) covers the same ground with
per-model faceting. `outcome_summary.csv` extraction in tables.py should be
kept (it feeds the dashboard fallback path), but the standalone chart is dead code.

### Step 3: Run `make check` to validate

Ensure lint, tests, and docs-check all pass after removals.

### Step 4: Commit and PR

Single-concept PR: "Remove stale outcome_summary chart + close Phase E."

## Out of Scope

- Removing `canonical/` (SMOKE) directories — separate decision, not Phase E
- Generating the 6 absent optional charts — requires QUICK parquet regeneration
- FULL bundle regeneration (separate runbook task, R1/R2 still running)
- Option B refactor (subdir field) — separate task post-Phase E

## Acceptance Criteria

- [ ] `outcome_summary.png` deleted from all committed bundles
- [ ] `generate_outcome_summary()` removed from chart generator
- [ ] `outcome_summary.csv` extraction preserved (dashboard fallback)
- [ ] `make check` passes
- [ ] No broken image links in any `01_results.md`

## Outcome

PR #TBD — removed 9 stale `outcome_summary.png` files, updated 9 `00_manifest.md`
and 9 `evidence_manifest.json` files, and deleted the `generate_outcome_summary()`
function + call site from `generate_rung_charts.py`. `outcome_summary.csv` extraction
preserved in `tables.py` for dashboard fallback. Phase E complete.
