# Chart Suite Cleanup — Fix Codex Findings + Layout Restructure

<!-- review-tier: medium -->

> **ARCHIVED:** Superseded by PR #775 (chart suite cleanup). Moved 2026-03-18.

**Date:** 2026-03-17
**Status:** PROPOSED
**Scope:** Single PR fixing all remaining gaps from Codex review of PRs #768/#769/#771, plus chart directory restructuring
**Depends on:** PRs #768, #769, #771 (all must merge first, or this PR rebases on their combined state)

---

## 1. Objective

Deliver one cleanup PR that:
- fixes the 5 Codex findings (1 CRITICAL, 4 WARNING)
- restructures the chart directory layout for better reviewability
- does NOT regenerate bundles (that's Phase E, separate PR)

## 2. Non-Goals

- Do not regenerate R0-R3 QUICK bundles (Phase E, separate)
- Do not add new chart types beyond what's already implemented
- Do not change chart_data extraction logic except for outcome_distributions
- Do not touch orchestration.py or experiment configs

## 3. Findings To Fix

### F1 (CRITICAL): outcome_distributions.csv semantics

**Problem:** Current extractor in `tables.py:_extract_outcome_distributions()` synthesizes histogram bins from summary metrics. The fallback path writes a single bin at `mean_tricks_won` with `fraction=1.0`. This is not true distribution data.

**Required:** Per-deal outcome distribution rows suitable for histogram/CDF rendering. The H2H battery JSON contains `cells[matchup].deals_total` and `by_contract` summary data, but NOT per-deal `tricks_won` arrays.

**Fix approach:** The H2H battery does not store raw per-deal data. True distributions require the action-value parquet from `data/runs/`. Two options:

- **Option A (preferred):** If `data/runs/av_r{N}_quick_{seed}/datasets/action_value.parquet` exists, extract actual `tricks_won` histogram from the parquet (groupby model × contract × tricks_won → count). This gives real distribution data.
- **Option B (fallback):** If parquet is unavailable, emit a clearly-labeled `outcome_distributions.csv` with `source=synthetic` column and a comment in the CSV header noting it's interpolated. Do NOT pretend summary metrics are distributions.

**Files:** `src/bid_euchre/arc_d_v2/tables.py`

### F2 (WARNING): 02_decision.md wrong chart numbers

**Problem:** PR #769's `generate_decision_report()` hardcodes chart references that don't match the registry:
- Says "Chart 1 (Comparator Ranking Bars)" — registry says Chart 1 = Competitive Dashboard
- Says "Chart 4 (Tail Risk Panel)" — registry says Chart 4 = Comparator Ranking Bars, Chart 5 = Tail Risk

**Fix:** Import `chart_registry.get_chart_by_filename()` and look up numbers dynamically instead of hardcoding. Reference:
- `dashboard_competitive.png` → Chart 1
- `dashboard_health.png` → Chart 2
- `dashboard_model_eval.png` → Chart 3
- `comparator_ranking_bars.png` → Chart 4
- `h2h_heatmap.png` → Chart 7

**Files:** `src/bid_euchre/arc_d_v2/report.py`

### F3 (WARNING): h2h_intelligence_faceted.png not in registry

**Problem:** PR #769 added `generate_intelligence_faceted_h2h()` but the chart is not in the 22-chart registry. It's invisible to the numbered manifest/report contract.

**Fix:** Add chart 23 to the registry:
```python
ChartEntry(23, "h2h_intelligence_faceted.png", "Intelligence-Faceted H2H", False,
           "tables/h2h_tier_summary.csv")
```

**Files:** `src/bid_euchre/arc_d_v2/chart_registry.py`

### F4 (WARNING): Competitive dashboard panel 6 wrong content

**Problem:** Panel 6 shows cross-rung progression. The plan requires intelligence-faceted H2H summary in the competitive dashboard.

**Fix:** Swap panel 6: replace cross-rung progression with intelligence-faceted H2H (grouped bar by tier). Move cross-rung progression to a standalone chart (it's already chart-registered or can be an unnumbered supporting chart).

**Files:** `scripts/internal/generate_rung_charts.py`

### F5 (WARNING): Health dashboard still 2×2

**Problem:** Health dashboard omits seat_balance. Plan allowed 3×2 and explicitly called for seat_balance or richer health coverage.

**Fix:** Expand health dashboard to 3×2:
- Panel 1: Bid rate / pass rate / make rate (existing)
- Panel 2: Contract mix (existing)
- Panel 3: True outcome distributions (existing, with F1 fix)
- Panel 4: Bid-level distribution (existing)
- Panel 5: Seat balance (from chart_data/seat_balance.csv)
- Panel 6: Bid-type breakdown (from behavior_by_bid_type.csv, if present; placeholder otherwise)

**Files:** `scripts/internal/generate_rung_charts.py`

## 4. Chart Directory Layout Restructure

### Current layout
```
charts/
  dashboard_competitive.png
  dashboard_health.png
  dashboard_model_eval.png
  comparator_ranking_bars.png
  tail_risk_panel.png
  ... (all 22+ PNGs flat)
```

### Target layout
```
charts/
  dashboard_competitive.png       # Charts 1-3: dashboards at top level
  dashboard_health.png
  dashboard_model_eval.png
  full_chart_suite/
    comparator_ranking_bars.png   # Charts 4-23: numbered evidence suite
    tail_risk_panel.png
    delta_bars_by_contract.png
    h2h_heatmap.png
    h2h_ranking_scatter.png
    outcome_distributions.png
    seat_balance.png
    contract_mix_bars.png
    bid_behavior_panel.png
    bid_level_distribution.png
    r2_by_contract.png
    mae_by_contract.png
    pred_vs_actual.png
    residual_distribution.png
    calibration_curve.png
    selection_path.png
    feature_importance.png
    decision_agreement.png
    disagreement_outcomes.png
    h2h_intelligence_faceted.png
```

### Files to update for layout change
- `src/bid_euchre/arc_d_v2/chart_registry.py` — Store relative path (e.g., `full_chart_suite/comparator_ranking_bars.png` for charts 4+, just filename for charts 1-3)
- `src/bid_euchre/arc_d_v2/report.py` — Embed using registry path, not just filename
- `src/bid_euchre/arc_d_v2/manifest.py` — Inventory both `charts/` and `charts/full_chart_suite/`
- `scripts/internal/generate_rung_charts.py` — Write dashboards to `charts/`, standalone to `charts/full_chart_suite/`

## 5. Required Code Changes

| File | Changes |
|------|---------|
| `src/bid_euchre/arc_d_v2/tables.py` | F1: Rewrite `_extract_outcome_distributions()` to use parquet when available |
| `src/bid_euchre/arc_d_v2/report.py` | F2: Use registry lookups for chart numbers in decision report |
| `src/bid_euchre/arc_d_v2/chart_registry.py` | F3: Add chart 23, update paths for layout restructure |
| `scripts/internal/generate_rung_charts.py` | F4: Swap competitive panel 6, F5: Expand health to 3×2, Layout: write to subdirs |
| `src/bid_euchre/arc_d_v2/manifest.py` | Layout: Inventory both chart locations |

## 6. Testing Requirements

- `outcome_distributions.csv` has true distribution rows when parquet exists (>1 bin per contract)
- `outcome_distributions.csv` fallback path is clearly labeled synthetic
- Decision report chart numbers match registry lookups
- Chart 23 exists in registry with correct metadata
- Competitive dashboard panel 6 is intelligence-faceted H2H
- Health dashboard is 3×2 with seat_balance panel
- Chart generators write to correct subdirectories (dashboards vs full_chart_suite)
- Report embeds reference correct relative paths
- Manifest inventories both locations with numbering

## 7. Acceptance Criteria

1. All 5 Codex findings resolved
2. Charts 1-3 in `charts/`, Charts 4-23 in `charts/full_chart_suite/`
3. All existing tests pass (no regressions)
4. New tests cover the fixes
5. `make lint` passes

## Outcome

_To be filled after implementation._
