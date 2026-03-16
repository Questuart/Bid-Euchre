# Rung Manifest

**Lineage:** arc_d_v2
**Rung:** r2 (opponent context)
**Evidence tier:** QUICK
**Mode:** QUICK
**Seeds:** [42]
**Anchor:** anchor_hybrid_r0_full
**Governing plan:** `plans/arc_d_v2/lineage_plan.md`

## Reports

| File | Description |
|------|-------------|
| 00_manifest.md | This manifest |
| 01_results.md | Full results report (data sanity, model performance, comparator, H2H, behavior) |
| 02_decision.md | Decision report with hypothesis outcomes and advance decision |
| evidence_manifest.json | Machine-readable provenance and artifact index |

## Tables

| File | Description |
|------|-------------|
| artifact_inventory.csv | Training artifact inventory |
| behavior_by_contract.csv | Behavioral metrics by contract type |
| behavior_summary.csv | Pooled behavioral summary |
| comparator_rankings.csv | Comparator battery rankings |
| cross_rung_deltas.csv | Cross-rung GBT progression (R0-R2) |
| data_sanity.csv | Data sanity checks |
| dataset_provenance.csv | Dataset provenance metadata |
| h2h_delta_matrix.csv | Full H2H delta matrix (81 matchups) |
| hypothesis_outcomes.csv | Hypothesis test results from advance check |
| model_performance.csv | Offline model R-squared and MAE |
| rung_model_spec.csv | Model roster specification |
| sanity_bounds_check.csv | Sanity bounds validation |

## Charts

| File | Description |
|------|-------------|
| bid_behavior_panel.png | Bid rate and make rate panel |
| comparator_ranking_bars.png | Comparator net_eppd ranking bars |
| contract_mix_bars.png | Contract type distribution |
| delta_bars_by_contract.png | H2H delta by contract type |
| h2h_heatmap.png | H2H pairwise delta heatmap |
| mae_by_contract.png | MAE by contract type |
| r2_by_contract.png | R-squared by contract type |
| tail_risk_panel.png | CVaR tail risk panel |

## Model Roster

| Model | Trainable | Status |
|-------|-----------|--------|
| modeloespecifico | No | evaluated |
| selected_two_stage_av | Yes | evaluated |
| gbt_av | Yes | evaluated |
| constrained_ols_av | Yes | evaluated |
| selected_ols_av | Yes | evaluated |
| full_ols_av | Yes | evaluated |
| stricthellraiser | No | evaluated |
| rankthetank | No | evaluated |
