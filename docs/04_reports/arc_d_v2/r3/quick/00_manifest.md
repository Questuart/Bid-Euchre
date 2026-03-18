# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r3
**Provenance SHA:** `a090bcebbba05ee8cd27ae773567eb8ba28f75a9`
**Mode:** quick
**Seeds:** [42]
**Anchor:** anchor_hybrid_r0_full

## Model Roster

| Model | Class | Trainable | Status |
|-------|-------|-----------|--------|
| modeloespecifico | ModeloEspecifico | False | evaluated |
| selected_two_stage_av | TwoStageActionValueBidder | True | evaluated |
| gbt_av | GBTActionValueBidder | True | evaluated |
| constrained_ols_av | ActionValueBidder | True | evaluated |
| selected_ols_av | ActionValueBidder | True | evaluated |
| full_ols_av | ActionValueBidder | True | evaluated |
| stricthellraiser | StrictHellRaiser | False | evaluated |
| rankthetank | RanktheTank | False | evaluated |

## Artifacts

| Name | Schema | Path |
|------|--------|------|
| comparator_battery_r3_42 | arc_d_comparator_v1 | `data/artifacts/arc_d_v2/r3/comparator_battery_r3_42.json` |
| comparator_cis_r3_42 | comparator_cis_v1 | `data/artifacts/arc_d_v2/r3/comparator_cis_r3_42.json` |
| h2h_battery_quick_42 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r3/h2h_battery_quick_42.json` |
| h2h_battery_smoke_42 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r3/h2h_battery_smoke_42.json` |
| roster | roster_v1 | `data/artifacts/arc_d_v2/r3/roster.json` |
| training_artifact_constrained_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r3/training_artifact_constrained_ols_av.json` |
| training_artifact_full_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json` |
| training_artifact_gbt_av | action_value_gbt_v1 | `data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json` |
| training_artifact_selected_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r3/training_artifact_selected_ols_av.json` |
| training_artifact_selected_two_stage_av | two_stage_action_value_v1 | `data/artifacts/arc_d_v2/r3/training_artifact_selected_two_stage_av.json` |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 793 bytes |
| `behavior_by_bid_type.csv` | 1,118 bytes |
| `behavior_by_contract.csv` | 494 bytes |
| `behavior_summary.csv` | 1,533 bytes |
| `comparator_rankings.csv` | 567 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,004 bytes |
| `dataset_provenance.csv` | 966 bytes |
| `h2h_delta_matrix.csv` | 29,450 bytes |
| `h2h_tier_summary.csv` | 1,068 bytes |
| `hypothesis_outcomes.csv` | 48 bytes |
| `model_performance.csv` | 955 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,879 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 300,289 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 183,093 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 117,564 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 42,217 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 39,768 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 717,660 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 125,912 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 55,295 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | 89,308 bytes | present |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | - | absent |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 38,419 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 49,469 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | 42,031 bytes | present |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 38,198 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 40,605 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | - | absent |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | - | absent |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | - | absent |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | 89,282 bytes | present |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | 86,332 bytes | present |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 56,067 bytes | present |
| - | Feature Importance | `feature_importance.png` | 257,924 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `bid_levels.csv` | 268 bytes |
| `contract_mix.csv` | 855 bytes |
| `feature_importances.csv` | 10,202 bytes |
| `h2h_by_contract.csv` | 16,337 bytes |
| `outcome_distributions.csv` | 995 bytes |
| `outcome_summary.csv` | 1,427 bytes |
| `selection_paths.csv` | 12,843 bytes |
