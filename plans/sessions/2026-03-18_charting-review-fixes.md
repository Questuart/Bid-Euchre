# Charting Infrastructure Review Fixes

**Date:** 2026-03-18
**Source:** Post-merge review findings from PRs #877 and #881
**Scope:** 2 code fixes + report bundle metadata/text corrections

## Findings Triage

| ID | Finding | Severity | Action |
|----|---------|----------|--------|
| F1 | CDF/CCDF tail panel not faceted by contract | P2 | Fix |
| F2 | Missing pass_rate in health dashboard rate panel | P2 | Fix |
| F3 | Charts 16-18 say "source data absent" but PNGs exist | P1 | Fix |
| F4 | Chart 9 note says "synthetic data" but real data exists | P2 | Fix |
| F5 | evidence_manifest.json marks charts 10/16/17/18 as absent | P1 | Fix |
| F6 | 00_manifest.md marks charts as absent | P1 | Fix |
| F7 | artifact_inventory.csv uses absolute paths | P1 | Fix |
| F8 | R2/R3 quick 02_decision.md says "all checks passed" but FAILs exist | P2 | **False positive** |
| F9 | Feature importances rank ordering for OLS models | P2 | **False positive** |

### F8 False Positive Rationale

The decision generator (report.py:559-566) reads `data_sanity.csv`, not
`sanity_bounds_check.csv`. R2/R3 quick `data_sanity.csv` has zero FAIL rows (confirmed).
The FAILs in `sanity_bounds_check.csv` are bid_rate_range checks for aggressive bidders,
documented in Data Quality Notes in 01_results.md. The decision report text "all checks
passed" is technically correct for its data source.

**Follow-up (separate PR):** The generator could be improved to also check
sanity_bounds_check.csv, but this is scope expansion beyond the review findings.

### F9 False Positive Rationale

The review claims rank 1 has the smallest importance value for OLS models. Investigation
of `_extract_feature_importance()` (tables.py:1246-1293) shows:
- **OLS models:** Uses forward-selection `step` number as rank, cumulative R² as importance
- **GBT models:** Sorts by gini importance descending, rank 1 = highest

For OLS, rank 1 = "first feature selected" = most impactful single feature. The cumulative
R² naturally increases with each added feature. The rank IS correct. No fix needed.

## PR Structure

Single PR — all fixes address "charting infrastructure review findings" as one concept.
Code fixes (F1, F2) improve the chart generator. Report fixes (F3-F7) correct stale
metadata in committed bundles. Both are review follow-ups from the same PRs (#877, #881).

**PR:** `fix/charting-review-findings`
**Files:**
- `scripts/internal/generate_rung_charts.py` (code: F1, F2)
- `src/bid_euchre/arc_d_v2/tables.py` (code: F7 root cause)
- `docs/04_reports/arc_d_v2/{r0,r1,r2}/full/` (report bundles: F3-F7)
- `docs/04_reports/arc_d_v2/r3/canonical/tables/artifact_inventory.csv` (F7)

## Implementation Plan

### PR 1: Chart Generation Code Fixes

#### Task 1A: Contract-faceted CDF/CCDF panel (F1)
**File:** `scripts/internal/generate_rung_charts.py` lines 1683-1709
**Current:** Pools all contracts into one CDF curve per model
**Fix:** When `outcome_distributions.csv` has a `contract` column, generate
separate CDF curves per contract (using color for model, linestyle for contract),
or produce a 2×2 sub-panel. Simplest correct fix: filter by contract, add
contract to legend label.

**Approach:** If contract column exists, loop over contracts within each model,
using linestyle variation. If no contract column, fall back to current behavior.

#### Task 1B: Add pass_rate to rate panel (F2)
**File:** `scripts/internal/generate_rung_charts.py` lines 1786-1800
**Current:** Only plots bid_rate and make_rate as grouped bars
**Fix:** Add a third bar group for pass_rate when available. Adjust bar width
from 0.35 to 0.25, position three groups. Update title from "Bid / Make Rates"
to "Bid / Pass / Make Rates".

#### Task 1C: Targeted tests
Run chart generation tests to verify no regressions.

### PR 2: Report Bundle Corrections

#### Dependency graph
```
F7 (artifact_inventory paths) ──┐
F3 (charts 16-18 text)       ──┤
F4 (Chart 9 synthetic note)  ──┼── All independent, parallelizable per rung
F5 (evidence_manifest.json)  ──┤
F6 (00_manifest.md)           ──┤
F8 (decision sanity claims)  ──┘
```

All fixes are independent text/data edits. No ordering constraint.
Can batch all rung edits per finding type.

#### Task 2A: Fix artifact_inventory.csv absolute paths (F7)
**Files (4):**
- `docs/04_reports/arc_d_v2/r0/full/tables/artifact_inventory.csv`
- `docs/04_reports/arc_d_v2/r1/full/tables/artifact_inventory.csv`
- `docs/04_reports/arc_d_v2/r2/full/tables/artifact_inventory.csv`
- `docs/04_reports/arc_d_v2/r3/canonical/tables/artifact_inventory.csv`

**Fix:** Replace `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/` with
`data/` (repo-relative paths). R3 quick already has correct paths (confirmed).

**Also fix generator:** `tables.py:generate_artifact_inventory()` — convert
`rung_dir` to repo-relative path before embedding. Use `Path.relative_to()` or
strip the repo root prefix.

#### Task 2B: Fix Charts 16-18 "source data absent" text (F3)
**Files (3):** `docs/04_reports/arc_d_v2/{r0,r1,r2}/full/01_results.md`
**Fix:** Replace placeholder text with image references:
- Chart 16: `![Predicted vs Actual](charts/full_chart_suite/pred_vs_actual.png)`
- Chart 17: `![Residual Distribution](charts/full_chart_suite/residual_distribution.png)`
- Chart 18: `![Calibration Curve](charts/full_chart_suite/calibration_curve.png)`

PNGs confirmed to exist in all three rung bundles.

#### Task 2C: Fix Chart 10 (Seat Balance) text (part of F3/F6)
**Check:** Does `seat_balance.png` exist in R0/R1/R2 full bundles? Confirmed yes.
**Fix:** If `seat_balance.png` exists in R0/R1/R2, update 01_results.md and
manifests accordingly. (If no text placeholder exists for Chart 10, only manifest
fixes needed.)

#### Task 2D: Fix Chart 9 synthetic data note (F4)
**Files (3):** `docs/04_reports/arc_d_v2/{r0,r1,r2}/full/01_results.md`
**Fix:** In Section 10 "Data Quality Notes", replace:
```
- **Outcome distributions (Chart 9):** synthetic data — parquet-backed real distributions unavailable for this bundle
```
With:
```
- **Outcome distributions (Chart 9):** parquet-backed real distributions
```

#### Task 2E: Fix evidence_manifest.json (F5)
**Files (3):** `docs/04_reports/arc_d_v2/{r0,r1,r2}/full/evidence_manifest.json`
**Fix:** For charts 10, 16, 17, 18 — set `"present": true`, add actual
`"size_bytes"` and `"path"` values by checking the actual PNG files.

#### Task 2F: Fix 00_manifest.md (F6)
**Files (3):** `docs/04_reports/arc_d_v2/{r0,r1,r2}/full/00_manifest.md`
**Fix:** Change chart entries from `absent` to `present` with correct file paths.

#### Task 2G: Fix artifact_inventory generator (F7 root cause)
**File:** `src/bid_euchre/arc_d_v2/tables.py` lines 726-764
**Fix:** Make `rung_dir` paths repo-relative before embedding in CSV.
Detect repo root (find `.git` directory ancestor) and use `Path.relative_to()`.

## Execution Order

```
Code fixes (independent):       Report bundle fixes (independent):
  1A (CDF faceting) ──┐           2A (inventory paths) ──┐
  1B (pass_rate)    ──┤           2B (charts 16-18)    ──┤
  2G (generator)    ──┘           2C (chart 10)        ──┼── all parallel
                                  2D (chart 9 note)    ──┤
                                  2E (manifest json)   ──┤
                                  2F (manifest md)     ──┘
```

All tasks are independent — no ordering constraint between any of them.

## Validation

- `uv run python -m pytest tests/ -k "chart" --no-header -q` (chart-related tests)
- `make check-quiet` (full validation)
- `grep -r '/Users/' docs/04_reports/` (verify no absolute paths remain)

## Outcome

_To be filled after implementation._
