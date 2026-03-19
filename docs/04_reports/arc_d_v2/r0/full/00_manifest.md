# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r0
**Provenance SHA:** `e3f1db3bba1ddc97b144c0b087b1acf3e270a17f`
**Mode:** FULL
**Seeds:** [123, 42, 456]
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
| advance_check | advance_check_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/advance_check.json` |
| comparator_battery_r0_123 | arc_d_comparator_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/comparator_battery_r0_123.json` |
| comparator_battery_r0_42 | arc_d_comparator_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/comparator_battery_r0_42.json` |
| comparator_battery_r0_456 | arc_d_comparator_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/comparator_battery_r0_456.json` |
| comparator_cis_r0_123 | comparator_cis_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/comparator_cis_r0_123.json` |
| comparator_cis_r0_42 | comparator_cis_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/comparator_cis_r0_42.json` |
| comparator_cis_r0_456 | comparator_cis_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/comparator_cis_r0_456.json` |
| h2h_battery_full_123 | h2h_battery_v2 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/h2h_battery_full_123.json` |
| h2h_battery_full_42 | h2h_battery_v2 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/h2h_battery_full_42.json` |
| h2h_battery_full_456 | h2h_battery_v2 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/h2h_battery_full_456.json` |
| h2h_battery_quick_42 | h2h_battery_v2 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/h2h_battery_quick_42.json` |
| h2h_battery_smoke_42 | h2h_battery_v2 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/h2h_battery_smoke_42.json` |
| roster | roster_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/roster.json` |
| training_artifact_constrained_ols_av | action_value_olsa_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/training_artifact_constrained_ols_av.json` |
| training_artifact_full_ols_av | action_value_olsa_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/training_artifact_full_ols_av.json` |
| training_artifact_gbt_av | action_value_gbt_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/training_artifact_gbt_av.json` |
| training_artifact_selected_ols_av | action_value_olsa_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/training_artifact_selected_ols_av.json` |
| training_artifact_selected_two_stage_av | two_stage_action_value_v1 | `../Bid-Euchre/data/artifacts/arc_d_v2/r0/training_artifact_selected_two_stage_av.json` |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 854 bytes |
| `behavior_by_bid_type.csv` | 589 bytes |
| `behavior_by_contract.csv` | 886 bytes |
| `behavior_summary.csv` | 901 bytes |
| `comparator_rankings.csv` | 327 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,013 bytes |
| `dataset_provenance.csv` | 422 bytes |
| `h2h_delta_matrix.csv` | 9,361 bytes |
| `h2h_tier_summary.csv` | 560 bytes |
| `hypothesis_outcomes.csv` | 982 bytes |
| `model_performance.csv` | 935 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,489 bytes |
| `seed_sanity.csv` | 2,877 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 208,797 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 176,177 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 341,222 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 25,614 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 26,261 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 209,361 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 65,627 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 45,732 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | 64,211 bytes | present |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | 24,493 bytes | present |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 27,378 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 43,273 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | 44,495 bytes | present |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 35,910 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 34,173 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | 409,929 bytes | present |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | 80,850 bytes | present |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | 126,455 bytes | present |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | 99,004 bytes | present |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | 103,181 bytes | present |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 41,632 bytes | present |
| - | Feature Importance | `feature_importance.png` | 272,842 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `bid_levels.csv` | 873 bytes |
| `calibration_bins.csv` | 7,564 bytes |
| `contract_mix.csv` | 520 bytes |
| `feature_importances.csv` | 8,040 bytes |
| `h2h_by_contract.csv` | 5,759 bytes |
| `outcome_distributions.csv` | 1,592 bytes |
| `predictions.csv` | 2,999,926 bytes |
| `residuals.csv` | 11,945 bytes |
| `seat_balance.csv` | 347 bytes |
| `selection_paths.csv` | 8,040 bytes |
