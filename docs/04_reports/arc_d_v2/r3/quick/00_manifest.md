# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r3 (moon/loner action space expansion)
**Evidence tier:** QUICK
**gate_status:** QUICK-COMPLETE (directional evidence — not a promotion gate)
**Provenance SHA:** `21c6762391ee414374f5a08dfcd45a0b337e5236`
**Mode:** QUICK
**Seeds:** [42]
**Anchor:** anchor_hybrid_r0_full
**Governing plan:** `plans/arc_d_v2/lineage_plan.md`

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
| comparator_battery_r3_42 | arc_d_comparator_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/comparator_battery_r3_42.json |
| comparator_cis_r3_42 | comparator_cis_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/comparator_cis_r3_42.json |
| h2h_battery_quick_42 | h2h_battery_v2 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/h2h_battery_quick_42.json |
| roster | roster_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/roster.json |
| training_artifact_constrained_ols_av | action_value_olsa_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/training_artifact_constrained_ols_av.json |
| training_artifact_full_ols_av | action_value_olsa_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json |
| training_artifact_gbt_av | action_value_gbt_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json |
| training_artifact_selected_ols_av | action_value_olsa_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/training_artifact_selected_ols_av.json |
| training_artifact_selected_two_stage_av | two_stage_action_value_v1 | /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/artifacts/arc_d_v2/r3/training_artifact_selected_two_stage_av.json |

## Tables

| Name | Size |
|------|------|
| `artifact_inventory.csv` | 1,135 bytes |
| `behavior_by_bid_type.csv` | 1,133 bytes |
| `behavior_by_contract.csv` | 454 bytes |
| `behavior_summary.csv` | 1,106 bytes |
| `comparator_rankings.csv` | 575 bytes |
| `cross_rung_deltas.csv` | 71 bytes |
| `data_sanity.csv` | 2,007 bytes |
| `dataset_provenance.csv` | 1,056 bytes |
| `h2h_delta_matrix.csv` | 29,552 bytes |
| `hypothesis_outcomes.csv` | 48 bytes |
| `model_performance.csv` | 928 bytes |
| `rung_model_spec.csv` | 440 bytes |
| `sanity_bounds_check.csv` | 1,885 bytes |

## Charts

| Name | Size |
|------|------|
| `bid_behavior_panel.png` | 43,743 bytes |
| `comparator_ranking_bars.png` | 42,261 bytes |
| `contract_mix_bars.png` | 37,314 bytes |
| `delta_bars_by_contract.png` | 717,564 bytes |
| `h2h_heatmap.png` | 130,127 bytes |
| `mae_by_contract.png` | 40,601 bytes |
| `r2_by_contract.png` | 38,196 bytes |
| `tail_risk_panel.png` | 39,766 bytes |
