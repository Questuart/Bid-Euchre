# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r0
**Provenance SHA:** `b8d211997eb644df43102d8f497df0e5ad5ef38e`
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
| comparator_battery_r0_42 | arc_d_comparator_v1 | `data/artifacts/arc_d_v2/r0/comparator_battery_r0_42.json` |
| comparator_cis_r0_42 | comparator_cis_v1 | `data/artifacts/arc_d_v2/r0/comparator_cis_r0_42.json` |
| h2h_battery_quick_42 | h2h_battery_v2 | `data/artifacts/arc_d_v2/r0/h2h_battery_quick_42.json` |
| roster | roster_v1 | `data/artifacts/arc_d_v2/r0/roster.json` |
| training_artifact_constrained_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r0/training_artifact_constrained_ols_av.json` |
| training_artifact_full_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r0/training_artifact_full_ols_av.json` |
| training_artifact_gbt_av | action_value_gbt_v1 | `data/artifacts/arc_d_v2/r0/training_artifact_gbt_av.json` |
| training_artifact_selected_ols_av | action_value_olsa_v1 | `data/artifacts/arc_d_v2/r0/training_artifact_selected_ols_av.json` |
| training_artifact_selected_two_stage_av | two_stage_action_value_v1 | `data/artifacts/arc_d_v2/r0/training_artifact_selected_two_stage_av.json` |

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

| Name | Size |
|------|------|
| `bid_behavior_panel.png` | 43,740 bytes |
| `comparator_ranking_bars.png` | 42,230 bytes |
| `contract_mix_bars.png` | 37,313 bytes |
| `dashboard_competitive.png` | 217,457 bytes |
| `dashboard_health.png` | 124,596 bytes |
| `dashboard_model_eval.png` | 73,819 bytes |
| `delta_bars_by_contract.png` | 628,011 bytes |
| `h2h_heatmap.png` | 131,083 bytes |
| `mae_by_contract.png` | 41,802 bytes |
| `outcome_distributions.png` | 25,184 bytes |
| `r2_by_contract.png` | 35,844 bytes |
| `tail_risk_panel.png` | 39,768 bytes |

## Chart Data

| Name | Size |
|------|------|
| `contract_mix.csv` | 859 bytes |
| `outcome_distributions.csv` | 1,423 bytes |
