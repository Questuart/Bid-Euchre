# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r0
**Provenance SHA:** `fbba88b5aedd08bd6c22f56ad1ea884e30575892`
**Mode:** QUICK
**Seeds:** []
**Anchor:**

**Governing Plan:** `plans/arc_d_v2/r0/plan.md`

## Lifecycle Status

| Run | Status | Superseded By |
|-----|--------|---------------|
| `chart_data` | active | - |
| `charts` | active | - |
| `tables` | active | - |

## Artifacts

| Name | Schema | Path |
|------|--------|------|
| evidence_manifest | arc_d_evidence_manifest_v1 | `docs/04_reports/arc_d_v2/r0/quick/evidence_manifest.json` |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 1,135 bytes |
| `behavior_by_bid_type.csv` | 1,087 bytes |
| `behavior_by_contract.csv` | 499 bytes |
| `behavior_summary.csv` | 1,545 bytes |
| `comparator_rankings.csv` | 569 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,013 bytes |
| `dataset_provenance.csv` | 1,056 bytes |
| `h2h_delta_matrix.csv` | 20,701 bytes |
| `h2h_tier_summary.csv` | 1,071 bytes |
| `hypothesis_outcomes.csv` | 834 bytes |
| `model_performance.csv` | 931 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,889 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 294,385 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 180,175 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 90,298 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 42,230 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 39,768 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 628,011 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 131,083 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 54,869 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | - | absent |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | - | absent |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 38,398 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 49,485 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | - | absent |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 35,844 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 41,802 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | - | absent |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | - | absent |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | - | absent |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | - | absent |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | - | absent |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 56,365 bytes | present |
| - | full_chart_suite/outcome_summary.png | `full_chart_suite/outcome_summary.png` | 48,758 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `contract_mix.csv` | 859 bytes |
| `outcome_summary.csv` | 1,423 bytes |
