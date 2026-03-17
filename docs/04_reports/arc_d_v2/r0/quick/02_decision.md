# Rung R0 (QUICK) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2360 | 2.1144 | 2.3592 | 1 |
| gbt_av | 2.2012 | 2.0684 | 2.3340 | 2 |
| constrained_ols_av | 2.1976 | 2.0720 | 2.3240 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.2767 | 0.4661 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.6060 | 0.6147 | 3 |
| constrained_ols_av | smart | -0.3988 | 0.3580 | 3 |
| constrained_ols_av | anchor | -0.0540 | 0.3684 | 1 |
| constrained_ols_av | heuristic | 3.4661 | 0.4932 | 3 |
| full_ols_av | smart | -0.3699 | 0.3631 | 3 |
| full_ols_av | anchor | 0.0080 | 0.3764 | 1 |
| full_ols_av | heuristic | 3.5167 | 0.5001 | 3 |
| gbt_av | smart | 1.1858 | 0.5887 | 4 |
| gbt_av | anchor | 1.0608 | 0.5320 | 1 |
| gbt_av | heuristic | 4.8405 | 0.6567 | 3 |
| modeloespecifico | smart | 0.8611 | 0.5697 | 4 |
| modeloespecifico | anchor | 0.2320 | 0.4548 | 1 |
| modeloespecifico | heuristic | 7.5360 | 0.7172 | 2 |
| rankthetank | smart | -10.5200 | 0.1024 | 4 |
| rankthetank | anchor | -10.4936 | 0.1024 | 1 |
| rankthetank | heuristic | 0.7938 | 0.5086 | 2 |
| selected_ols_av | smart | -0.2827 | 0.3757 | 3 |
| selected_ols_av | anchor | -0.0364 | 0.3716 | 1 |
| selected_ols_av | heuristic | 3.4688 | 0.4915 | 3 |
| selected_two_stage_av | smart | 0.7680 | 0.5576 | 3 |
| selected_two_stage_av | anchor | 0.1400 | 0.4212 | 1 |
| selected_two_stage_av | heuristic | 4.2523 | 0.5860 | 3 |
| stricthellraiser | smart | -1.9829 | 0.3978 | 4 |
| stricthellraiser | anchor | -4.5468 | 0.3080 | 1 |
| stricthellraiser | heuristic | -8.8300 | 0.2102 | 2 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| description |
| --- |
| GBT outperforms anchor on suit contract delta (H2H) |
| GBT outperforms anchor on pooled net_eppd (H2H) |
| GBT high-contract delta is positive vs anchor (H2H) |
| GBT low-contract delta is non-negative vs anchor (H2H) |
| GBT suit R-squared exceeds selected OLS suit R-squared |
| All models bid at least half the time (no pathological passing) |
| GBT H2H win rate vs anchor exceeds 50% |
| Two-stage model does not regress vs selected OLS on pooled net_eppd |
| ModeloEspecifico heuristic is worst on pooled net_eppd (sanity check) |


## Recommendation

Hypothesis outcomes not yet available. Run the advance check pipeline to populate results.

## Supporting Evidence

- Chart 4: Comparator Ranking Bars
- Chart 6: H2H Delta by Contract
- Chart 7: H2H Heatmap
- Chart 5: Tail Risk Panel
- Chart 12: Bid and Make Rates
- Chart 23: Intelligence-Faceted H2H
- Full tables: `tables/comparator_rankings.csv`, `tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`

## Gate Status

gate_status: See `hypothesis_outcomes` table above and `evidence_manifest.json` for machine-readable gate evidence.
