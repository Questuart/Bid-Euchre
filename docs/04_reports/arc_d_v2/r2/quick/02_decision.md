# Rung R2 (QUICK) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| gbt_av | 2.2548 | 2.1228 | 2.3884 | 1 |
| full_ols_av | 2.2432 | 2.1216 | 2.3672 | 2 |
| constrained_ols_av | 2.1976 | 2.0720 | 2.3240 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.3642 | 0.4604 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.6060 | 0.6147 | 3 |
| constrained_ols_av | smart | -0.1867 | 0.3909 | 3 |
| constrained_ols_av | anchor | -0.0540 | 0.3684 | 1 |
| constrained_ols_av | heuristic | 3.4661 | 0.4932 | 3 |
| full_ols_av | smart | -0.9748 | 0.2948 | 3 |
| full_ols_av | anchor | 0.0788 | 0.3836 | 1 |
| full_ols_av | heuristic | 3.5025 | 0.5148 | 3 |
| gbt_av | smart | 1.5201 | 0.6214 | 4 |
| gbt_av | anchor | 1.3020 | 0.5716 | 1 |
| gbt_av | heuristic | 4.6687 | 0.6736 | 3 |
| modeloespecifico | smart | 0.7526 | 0.5497 | 4 |
| modeloespecifico | anchor | 0.2320 | 0.4548 | 1 |
| modeloespecifico | heuristic | 7.5360 | 0.7172 | 2 |
| rankthetank | smart | -10.5200 | 0.1024 | 4 |
| rankthetank | anchor | -10.4936 | 0.1024 | 1 |
| rankthetank | heuristic | 0.7938 | 0.5086 | 2 |
| selected_ols_av | smart | -0.0717 | 0.4059 | 3 |
| selected_ols_av | anchor | 0.0956 | 0.3924 | 1 |
| selected_ols_av | heuristic | 3.6305 | 0.5049 | 3 |
| selected_two_stage_av | smart | 1.0547 | 0.5611 | 3 |
| selected_two_stage_av | anchor | 0.1980 | 0.4236 | 1 |
| selected_two_stage_av | heuristic | 4.2345 | 0.5860 | 3 |
| stricthellraiser | smart | -1.9986 | 0.3942 | 4 |
| stricthellraiser | anchor | -4.5468 | 0.3080 | 1 |
| stricthellraiser | heuristic | -8.8300 | 0.2102 | 2 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| description |
| --- |
| Opponent context improves GBT pooled H2H delta vs anchor |
| GBT R2 suit R-squared exceeds R1 suit R-squared |
| GBT R2 comparator net_eppd maintains or improves over R1 |
| GBT suit H2H delta vs anchor is positive |
| Two-stage model gap vs GBT narrows with richer context |
| All models bid at least half the time |
| GBT H2H win rate vs anchor exceeds 45% |
| Full OLS approximately equals constrained OLS |
| ModeloEspecifico heuristic is worst among trained models |


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
