# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r2
**Provenance SHA:** `fbba88b5aedd08bd6c22f56ad1ea884e30575892`
**Mode:** QUICK
**Seeds:** []
**Anchor:**

**Governing Plan:** `plans/arc_d_v2/r2/plan.md`

## Lifecycle Status

| Run | Status | Superseded By |
|-----|--------|---------------|
| `chart_data` | active | - |
| `charts` | active | - |
| `tables` | active | - |

## Artifacts

| Name | Schema | Path |
|------|--------|------|
| evidence_manifest | arc_d_evidence_manifest_v1 | `docs/04_reports/arc_d_v2/r2/quick/evidence_manifest.json` |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 1,135 bytes |
| `behavior_by_bid_type.csv` | 1,088 bytes |
| `behavior_by_contract.csv` | 499 bytes |
| `behavior_summary.csv` | 1,544 bytes |
| `comparator_rankings.csv` | 572 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,009 bytes |
| `dataset_provenance.csv` | 1,056 bytes |
| `h2h_delta_matrix.csv` | 20,637 bytes |
| `h2h_tier_summary.csv` | 1,074 bytes |
| `hypothesis_outcomes.csv` | 770 bytes |
| `model_performance.csv` | 933 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,887 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 297,511 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 180,180 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 90,317 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 42,202 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 39,771 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 623,357 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 131,140 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 56,536 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | - | absent |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | - | absent |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 38,418 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 49,461 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | - | absent |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 35,901 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 41,806 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | - | absent |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | - | absent |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | - | absent |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | - | absent |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | - | absent |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 56,251 bytes | present |
| - | full_chart_suite/outcome_summary.png | `full_chart_suite/outcome_summary.png` | 48,729 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `contract_mix.csv` | 857 bytes |
| `outcome_summary.csv` | 1,423 bytes |
