# Full Chart Suite Implementation Plan

<!-- review-tier: medium -->

> **ARCHIVED:** Superseded by reporting refactor PRs #834–#848. Moved 2026-03-18.

**Date:** 2026-03-17
**Status:** PROPOSED
**Scope:** Close all remaining gaps between current main and `reporting_pr_scope_full_chart_suite.md`
**Depends on:** PRs #759, #764, #767 (all merged)
**Data tiers:** Generate `_quick` artifacts now from QUICK data; generate `_full` variants after FULL backfill completes

---

## 1. Reconciled Gap Analysis

Source: cross-referenced Claude session analysis against Codex CLI review on main (post-#767).

### Code Gaps (need new code)

| # | Gap | Plan §ref | Severity |
|---|-----|-----------|----------|
| G1 | Chart numbering system (22-chart registry constant, numbered headings in reports/manifest) | §4.2, §6.4 | WARNING |
| G2 | `h2h_ranking_scatter.png` generator | §4.2 chart 8 | WARNING |
| G3 | Intelligence-faceted H2H view (dashboard panel + standalone using `h2h_tier_summary.csv`) | §4.3, §6.3 | WARNING |
| G4 | `team0`/`team1` labeling in H2H report tables and chart captions | §4.2.1, §5.1 | WARNING |
| G5 | `dashboard_model_eval.png` expansion: 2×2 → 3×2+ with prediction diagnostics and decision analysis | §4.3 | WARNING |
| G6 | `dashboard_health.png`: replace `outcome_summary` panel with true outcome distribution | §4.3 | WARNING |
| G7 | `dashboard_competitive.png`: add H2H ranking scatter + intelligence-faceted summary + cross-rung progression | §4.3 | WARNING |
| G8 | True `outcome_distributions.csv`: actual distribution rows for histogram/CDF, not summary metrics | §5.1 | WARNING |
| G9 | `decision_agreement.png` + `disagreement_outcomes.png` chart generators | §4.2 charts 21-22 | MINOR |
| G10 | `02_decision.md` generation from advance-check + tables | §4.2.1 | WARNING |
| G11 | Long table handling in `01_results.md` (truncate/summarize >12 rows) | §4.2.2 | MINOR |
| G12 | `selection_path.png` generator (distinct from `feature_importance.png`) | §4.2 chart 19 | MINOR |
| G13 | `bid_level_distribution.png` (filename alignment with chart 13) | §4.2 chart 13 | MINOR |
| G14 | `feature_importances.csv` (separate from `selection_paths.csv` per §5) | §5 | MINOR |
| G15 | Manifest chart inventory with number, title, byte size, presence/absence | §4.2.1 | WARNING |

### Regeneration Gaps (code exists, need pipeline run)

| # | Gap | Notes |
|---|-----|-------|
| R1 | Committed R0-R3 `quick/` bundles stale vs merged code | chart_data only has contract_mix.csv and outcome_summary.csv |
| R2 | Standalone diagnostic PNGs (pred_vs_actual, residuals, calibration, feature_importance) not in bundles | Generators exist in #764, never run against artifacts |
| R3 | `02_decision.md` absent from all committed bundles | Needs generation logic (G10) first |

## 2. Implementation Phases

### Phase A: Chart Registry + Report Contract (G1, G4, G11, G15)

**Purpose:** Establish the numbered chart contract that all subsequent work renders into.

**Deliverables:**
- `src/bid_euchre/arc_d_v2/chart_registry.py` — Shared constant defining the 22-chart registry (number, filename, title, required/optional, source CSV)
- Update `src/bid_euchre/arc_d_v2/report.py`:
  - Render chart headings as `### Chart <n>. <Title>`
  - Emit numbered placeholders for missing optional charts
  - Truncate/summarize tables >12 rows with "Full table: see `tables/<name>.csv`"
  - Use `team0`/`team1` labels in H2H tables and captions
- Update `src/bid_euchre/arc_d_v2/manifest.py`:
  - Inventory charts with number, title, byte size, presence/absence
  - Inventory `chart_data/*.csv` with status

**Tests:**
- Chart registry numbering is stable
- Report placeholders preserve numbers for missing charts
- Long table truncation
- team0/team1 labels in H2H

### Phase B: Missing Chart Generators (G2, G8, G9, G12, G13, G14)

**Purpose:** Add all missing standalone chart generators and chart_data extractions.

**Deliverables:**
- `scripts/internal/generate_rung_charts.py`:
  - `generate_h2h_ranking_scatter()` — scatter of model rank vs net_eppd, color-coded by intelligence tier (chart 8)
  - `generate_outcome_distributions_chart()` — histogram/CDF from true distribution rows (chart 9)
  - `generate_bid_level_distribution()` — bar chart of bid level frequencies (chart 13, filename `bid_level_distribution.png`)
  - `generate_selection_path_chart()` — multi-line OOF R² vs step (chart 19)
  - `generate_decision_agreement_chart()` — agreement matrix heatmap (chart 21)
  - `generate_disagreement_outcomes_chart()` — divergence analysis (chart 22)
- `src/bid_euchre/arc_d_v2/tables.py`:
  - Fix `outcome_distributions.csv` to emit actual distribution rows (tricks_won histogram bins by model/contract) from H2H game-level data, not summary metrics
  - Add `feature_importances.csv` extraction (distinct from `selection_paths.csv`)

**Data tier handling:**
- Charts that can render from QUICK single-seed data: generate now, place in `_quick/` bundles
- Charts that require multi-seed or FULL data: stub with placeholder, generate later into `_full/`

**Tests:**
- Each generator produces PNG from fixture data
- Graceful degradation when CSV missing
- outcome_distributions.csv has distribution-shaped rows (not summary)

### Phase C: Dashboard Expansion (G5, G6, G7)

**Purpose:** Expand dashboards from 2×2 to the scoped compositions.

**Deliverables:**
- `dashboard_model_eval.png` → 3×2 (or 2×3):
  - R² by contract
  - MAE by contract
  - Predicted vs actual (from predictions.csv)
  - Residual distribution (from residuals.csv)
  - Calibration curve (from calibration_bins.csv)
  - Feature importance or selection path (from selection_paths.csv)
- `dashboard_health.png` → 2×2 (updated panels):
  - Bid rate / pass rate / make rate
  - Contract mix
  - **True outcome distributions** (replaces outcome_summary)
  - Bid-level distribution or seat balance
- `dashboard_competitive.png` → 3×2:
  - Comparator ranking bars
  - Tail risk
  - H2H delta by contract
  - H2H heatmap
  - **H2H ranking scatter** (new)
  - **Intelligence-faceted H2H summary** (new)

**Tests:**
- Dashboards render with expanded panels
- Graceful degradation when optional CSVs missing

### Phase D: Intelligence-Faceted H2H + Decision Report (G3, G10)

**Purpose:** Complete the H2H storytelling and generate 02_decision.md.

**Deliverables:**
- Intelligence-faceted H2H standalone chart using `h2h_tier_summary.csv` (smart/anchor/heuristic tiers)
- `02_decision.md` generator:
  - Pulls hypothesis outcomes from advance-check
  - Cites numbered charts
  - References concise supporting tables
  - Uses team0/team1 naming

**Tests:**
- Intelligence-faceted view uses tier taxonomy
- 02_decision.md references chart numbers
- 02_decision.md cites key metrics with CIs

### Phase E: Regenerate Canonical Bundles (R1, R2, R3)

**Purpose:** Run the updated pipeline against QUICK artifacts for R0-R3.

**Actions:**
- Run table generation + chart_data extraction + chart generation + report rendering for each rung
- Verify committed bundles match the 22-chart contract
- Label these as `_quick` tier outputs
- Mark placeholders for charts that need FULL data

**Validation:**
- Each `quick/` bundle has chart_data inventory in manifest
- Each `01_results.md` uses numbered chart headings
- Each `02_decision.md` exists and references charts
- No notebooks created

## 3. PR Structure

| PR | Phases | Est. LOC | Dependencies |
|----|--------|----------|--------------|
| PR-A | Phase A (registry + report contract) | ~400 | None |
| PR-B | Phase B (chart generators) + Phase C (dashboard expansion) | ~600 | PR-A |
| PR-C | Phase D (H2H intel + decision report) + Phase E (bundle regeneration) | ~300 + regen | PR-B |

## 4. Data Tier Handling

Charts that can be generated from QUICK data (single seed, 2500 deals):
- All 22 charts in the registry can produce _quick variants
- Quality is sufficient for structural review but CIs will be wider

Charts that benefit from FULL data (3 seeds, 50K deals):
- Comparator rankings with pooled CIs
- Cross-rung progression with error bars
- Seed stability overlay (FULL-only)
- QUICK→FULL shrinkage comparison (FULL-only)

**Convention:**
- Current `docs/04_reports/arc_d_v2/<rung>/quick/` = QUICK-tier bundles (generated now)
- Future `docs/04_reports/arc_d_v2/<rung>/full/` = FULL-tier bundles (after FULL backfill)
- Both follow the same 22-chart contract

## 5. Acceptance Criteria

Matches §8 of `reporting_pr_scope_full_chart_suite.md` — all 15 criteria must pass.

## 6. Verification

```bash
# Full test suite
uv run python -m pytest tests/unit/test_rung_tables.py tests/unit/test_rung_charts.py tests/unit/test_rung_report.py tests/unit/test_reporting_pipeline_smoke.py -x -q

# Lint
make lint

# Verify chart numbering in committed reports
grep -c "### Chart" docs/04_reports/arc_d_v2/r0/quick/01_results.md

# Verify 02_decision.md exists
ls docs/04_reports/arc_d_v2/*/quick/02_decision.md
```

## Outcome

_To be filled after implementation._
