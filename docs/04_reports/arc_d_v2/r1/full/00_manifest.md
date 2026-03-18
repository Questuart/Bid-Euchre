# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r1
**Provenance SHA:** `b7976a3c8b8d5ac931ca8fae48afd9609a7e09db`
**Mode:** QUICK
**Seeds:** []
**Anchor:** anchor_hybrid_r0_full

## Model Roster

| Model | Class | Trainable | Status |
|-------|-------|-----------|--------|
| modeloespecifico | None | False | evaluated |
| selected_two_stage_av | None | True | evaluated |
| gbt_av | None | True | evaluated |
| constrained_ols_av | None | True | evaluated |
| selected_ols_av | None | True | evaluated |
| full_ols_av | None | True | evaluated |
| stricthellraiser | None | False | evaluated |
| rankthetank | None | False | evaluated |

## Artifacts

| Name | Schema | Path |
|------|--------|------|
| advance_check | advance_check_v1 | `data/artifacts/arc_d_v2/r1/advance_check.json` |
| comparator_battery_r1_123 | arc_d_comparator_v1 | `data/artifacts/arc_d_v2/r1/comparator_battery_r1_123.json` |
| comparator_battery_r1_42 | arc_d_comparator_v1 | `data/artifacts/arc_d_v2/r1/comparator_battery_r1_42.json` |
| comparator_battery_r1_456 | arc_d_comparator_v1 | `data/artifacts/arc_d_v2/r1/comparator_battery_r1_456.json` |
| comparator_cis_r1_123 | comparator_cis_v1 | `data/artifacts/arc_d_v2/r1/comparator_cis_r1_123.json` |
| comparator_cis_r1_42 | comparator_cis_v1 | `data/artifacts/arc_d_v2/r1/comparator_cis_r1_42.json` |
| comparator_cis_r1_456 | comparator_cis_v1 | `data/artifacts/arc_d_v2/r1/comparator_cis_r1_456.json` |
| h2h_battery_full_123 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r1/h2h_battery_full_123.json` |
| h2h_battery_full_42 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r1/h2h_battery_full_42.json` |
| h2h_battery_full_456 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r1/h2h_battery_full_456.json` |
| h2h_battery_quick_42 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r1/h2h_battery_quick_42.json` |
| h2h_battery_smoke_42 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r1/h2h_battery_smoke_42.json` |
| roster | roster_v1 | `data/artifacts/arc_d_v2/r1/roster.json` |
| training_artifact_constrained_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r1/training_artifact_constrained_ols_av.json` |
| training_artifact_full_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r1/training_artifact_full_ols_av.json` |
| training_artifact_gbt_av | action_value_gbt_v1 | `data/artifacts/arc_d_v2/r1/training_artifact_gbt_av.json` |
| training_artifact_selected_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r1/training_artifact_selected_ols_av.json` |
| training_artifact_selected_two_stage_av | two_stage_action_value_v1 | `data/artifacts/arc_d_v2/r1/training_artifact_selected_two_stage_av.json` |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 1,135 bytes |
| `behavior_by_bid_type.csv` | 1,072 bytes |
| `behavior_by_contract.csv` | 494 bytes |
| `behavior_summary.csv` | 1,535 bytes |
| `comparator_rankings.csv` | 567 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,008 bytes |
| `dataset_provenance.csv` | 1,011 bytes |
| `h2h_delta_matrix.csv` | 27,514 bytes |
| `h2h_tier_summary.csv` | 1,071 bytes |
| `hypothesis_outcomes.csv` | 48 bytes |
| `model_performance.csv` | 982 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,885 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 299,338 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 181,723 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 111,902 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 42,247 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 39,772 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 693,130 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 128,679 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 56,424 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | 79,771 bytes | present |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | - | absent |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 38,410 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 49,477 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | 39,728 bytes | present |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 35,934 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 36,745 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | - | absent |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | - | absent |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | - | absent |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | 82,582 bytes | present |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | 104,763 bytes | present |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 56,257 bytes | present |
| - | full_chart_suite/outcome_summary.png | `full_chart_suite/outcome_summary.png` | 48,720 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `bid_levels.csv` | 271 bytes |
| `contract_mix.csv` | 854 bytes |
| `feature_importances.csv` | 10,218 bytes |
| `h2h_by_contract.csv` | 16,336 bytes |
| `outcome_distributions.csv` | 995 bytes |
| `outcome_summary.csv` | 1,422 bytes |
| `selection_paths.csv` | 12,514 bytes |
