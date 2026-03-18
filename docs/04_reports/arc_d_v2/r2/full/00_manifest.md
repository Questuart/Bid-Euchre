# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r2
**Provenance SHA:** `d3235c37b61ae91851c15623473ebec01fbb8c49`
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
| comparator_battery_r2_123 | arc_d_comparator_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/comparator_battery_r2_123.json` |
| comparator_battery_r2_42 | arc_d_comparator_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/comparator_battery_r2_42.json` |
| comparator_battery_r2_456 | arc_d_comparator_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/comparator_battery_r2_456.json` |
| comparator_cis_r2_123 | comparator_cis_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/comparator_cis_r2_123.json` |
| comparator_cis_r2_42 | comparator_cis_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/comparator_cis_r2_42.json` |
| comparator_cis_r2_456 | comparator_cis_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/comparator_cis_r2_456.json` |
| h2h_battery_full_123 | h2h_battery_v2 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/h2h_battery_full_123.json` |
| h2h_battery_full_42 | h2h_battery_v2 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/h2h_battery_full_42.json` |
| h2h_battery_full_456 | h2h_battery_v2 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/h2h_battery_full_456.json` |
| h2h_battery_quick_42 | h2h_battery_v2 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/h2h_battery_quick_42.json` |
| h2h_battery_smoke_42 | h2h_battery_v2 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/h2h_battery_smoke_42.json` |
| roster | roster_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/roster.json` |
| training_artifact_constrained_ols_av | action_value_olsa_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/training_artifact_constrained_ols_av.json` |
| training_artifact_full_ols_av | action_value_olsa_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/training_artifact_full_ols_av.json` |
| training_artifact_gbt_av | action_value_gbt_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/training_artifact_gbt_av.json` |
| training_artifact_selected_ols_av | action_value_olsa_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/training_artifact_selected_ols_av.json` |
| training_artifact_selected_two_stage_av | two_stage_action_value_v1 | `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author/data/artifacts/arc_d_v2/r2/training_artifact_selected_two_stage_av.json` |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 1,225 bytes |
| `behavior_by_bid_type.csv` | 587 bytes |
| `behavior_by_contract.csv` | 283 bytes |
| `behavior_summary.csv` | 902 bytes |
| `comparator_rankings.csv` | 328 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,010 bytes |
| `dataset_provenance.csv` | 1,056 bytes |
| `h2h_delta_matrix.csv` | 9,344 bytes |
| `h2h_tier_summary.csv` | 558 bytes |
| `hypothesis_outcomes.csv` | 48 bytes |
| `model_performance.csv` | 982 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,488 bytes |
| `seed_sanity.csv` | 2,139 bytes |

## Charts

| # | Title | File | Size | Status |
|---|-------|------|------|--------|
| 1 | Competitive Dashboard | `dashboard_competitive.png` | 210,740 bytes | present |
| 2 | Health Dashboard | `dashboard_health.png` | 147,241 bytes | present |
| 3 | Model Evaluation Dashboard | `dashboard_model_eval.png` | 111,902 bytes | present |
| 4 | Comparator Ranking Bars | `full_chart_suite/comparator_ranking_bars.png` | 25,619 bytes | present |
| 5 | Tail Risk Panel | `full_chart_suite/tail_risk_panel.png` | 26,262 bytes | present |
| 6 | H2H Delta by Contract | `full_chart_suite/delta_bars_by_contract.png` | 208,507 bytes | present |
| 7 | H2H Heatmap | `full_chart_suite/h2h_heatmap.png` | 64,673 bytes | present |
| 8 | H2H Ranking Scatter | `full_chart_suite/h2h_ranking_scatter.png` | 46,790 bytes | present |
| 9 | Outcome Distributions | `full_chart_suite/outcome_distributions.png` | 72,286 bytes | present |
| 10 | Seat Balance | `full_chart_suite/seat_balance.png` | - | absent |
| 11 | Contract Mix | `full_chart_suite/contract_mix_bars.png` | 27,378 bytes | present |
| 12 | Bid and Make Rates | `full_chart_suite/bid_behavior_panel.png` | 40,159 bytes | present |
| 13 | Bid Level Distribution | `full_chart_suite/bid_level_distribution.png` | 31,212 bytes | present |
| 14 | R-squared by Contract | `full_chart_suite/r2_by_contract.png` | 35,934 bytes | present |
| 15 | MAE by Contract | `full_chart_suite/mae_by_contract.png` | 36,745 bytes | present |
| 16 | Predicted vs Actual | `full_chart_suite/pred_vs_actual.png` | - | absent |
| 17 | Residual Distribution | `full_chart_suite/residual_distribution.png` | - | absent |
| 18 | Calibration Curve | `full_chart_suite/calibration_curve.png` | - | absent |
| 19 | Selection Path | `full_chart_suite/selection_path.png` | 82,582 bytes | present |
| 20 | Feature Importance | `full_chart_suite/feature_importance.png` | 104,763 bytes | present |
| 21 | Decision Agreement | `full_chart_suite/decision_agreement.png` | - | absent |
| 22 | Disagreement Outcomes | `full_chart_suite/disagreement_outcomes.png` | - | absent |
| 23 | Intelligence-Faceted H2H | `full_chart_suite/h2h_intelligence_faceted.png` | 42,241 bytes | present |
| - | full_chart_suite/outcome_summary.png | `full_chart_suite/outcome_summary.png` | 39,755 bytes | present |

## Chart Data

| Name | Size |
|------|------|
| `bid_levels.csv` | 159 bytes |
| `contract_mix.csv` | 520 bytes |
| `feature_importances.csv` | 10,218 bytes |
| `h2h_by_contract.csv` | 5,752 bytes |
| `outcome_distributions.csv` | 674 bytes |
| `outcome_summary.csv` | 893 bytes |
| `selection_paths.csv` | 12,514 bytes |
