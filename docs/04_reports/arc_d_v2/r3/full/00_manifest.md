# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r3
**Provenance SHA:** `7bf48a81c2e46028150a3eb6f8d2d2d3d7428475`
**Mode:** FULL
**Seeds:** [42]
**Anchor:** anchor_hybrid_r0_full

**Governing Plan:** `plans/arc_d_v2/r3/plan.md`

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
| `artifact_inventory.csv` | 854 bytes |
| `behavior_by_bid_type.csv` | 681 bytes |
| `behavior_by_contract.csv` | 1,569 bytes |
| `behavior_summary.csv` | 909 bytes |
| `comparator_rankings.csv` | 331 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 1,271 bytes |
| `dataset_provenance.csv` | 381 bytes |
| `h2h_delta_matrix.csv` | 10,594 bytes |
| `h2h_tier_summary.csv` | 559 bytes |
| `hypothesis_outcomes.csv` | 885 bytes |
| `model_performance.csv` | 593 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,058 bytes |
| `seed_sanity.csv` | 2,224 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 213,333 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 186,619 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 264,779 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 25,622 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 26,261 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 225,441 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 62,665 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 46,877 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | 67,716 bytes | present |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | 24,727 bytes | present |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 27,379 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 52,791 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | 42,155 bytes | present |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 30,959 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 32,600 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | 69,080 bytes | present |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | 35,859 bytes | present |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | 51,181 bytes | present |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | 69,011 bytes | present |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | 76,753 bytes | present |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 42,300 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `bid_levels.csv` | 844 bytes |
| `calibration_bins.csv` | 1,732 bytes |
| `contract_mix.csv` | 519 bytes |
| `feature_importances.csv` | 10,115 bytes |
| `h2h_by_contract.csv` | 5,760 bytes |
| `outcome_distributions.csv` | 1,555 bytes |
| `predictions.csv` | 540,219 bytes |
| `residuals.csv` | 2,724 bytes |
| `seat_balance.csv` | 332 bytes |
| `selection_paths.csv` | 11,955 bytes |
