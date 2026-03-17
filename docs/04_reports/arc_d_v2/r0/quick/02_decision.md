# Rung ? (QUICK) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2560 | 2.1352 | 2.3792 | 1 |
| constrained_ols_av | 2.2040 | 2.0800 | 2.3288 | 2 |
| selected_ols_av | 2.1952 | 2.0696 | 2.3240 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.2691 | 0.4660 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.6060 | 0.6147 | 3 |
| constrained_ols_av | smart | -0.3497 | 0.3615 | 3 |
| constrained_ols_av | anchor | -0.0548 | 0.3684 | 1 |
| constrained_ols_av | heuristic | 3.4712 | 0.4940 | 3 |
| full_ols_av | smart | -0.3065 | 0.3667 | 3 |
| full_ols_av | anchor | 0.0056 | 0.3748 | 1 |
| full_ols_av | heuristic | 3.5141 | 0.4992 | 3 |
| gbt_av | smart | 1.0959 | 0.5829 | 4 |
| gbt_av | anchor | 0.8724 | 0.5264 | 1 |
| gbt_av | heuristic | 4.7984 | 0.6492 | 3 |
| modeloespecifico | smart | 0.8378 | 0.5666 | 4 |
| modeloespecifico | anchor | 0.2320 | 0.4548 | 1 |
| modeloespecifico | heuristic | 7.5360 | 0.7172 | 2 |
| rankthetank | smart | -10.5200 | 0.1024 | 4 |
| rankthetank | anchor | -10.4936 | 0.1024 | 1 |
| rankthetank | heuristic | 0.7938 | 0.5086 | 2 |
| selected_ols_av | smart | -0.2725 | 0.3708 | 3 |
| selected_ols_av | anchor | -0.0188 | 0.3740 | 1 |
| selected_ols_av | heuristic | 3.4897 | 0.4961 | 3 |
| selected_two_stage_av | smart | 0.6984 | 0.5537 | 3 |
| selected_two_stage_av | anchor | 0.0764 | 0.4160 | 1 |
| selected_two_stage_av | heuristic | 4.2585 | 0.5900 | 3 |
| stricthellraiser | smart | -2.0094 | 0.3967 | 4 |
| stricthellraiser | anchor | -4.5468 | 0.3080 | 1 |
| stricthellraiser | heuristic | -8.8300 | 0.2102 | 2 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

> No hypothesis outcomes available.


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
