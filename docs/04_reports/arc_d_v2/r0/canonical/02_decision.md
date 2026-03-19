# Rung ? (QUICK) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| selected_ols_av | 1.7200 | 0.8800 | 2.5600 | 1 |
| constrained_ols_av | 1.6000 | 0.7600 | 2.4000 | 2 |
| full_ols_av | 1.4800 | 0.5200 | 2.5610 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.7650 | 0.4300 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.1933 | 0.6200 | 3 |
| constrained_ols_av | smart | -0.4867 | 0.3733 | 3 |
| constrained_ols_av | anchor | -1.4600 | 0.2600 | 1 |
| constrained_ols_av | heuristic | 3.0400 | 0.4867 | 3 |
| full_ols_av | smart | -1.6400 | 0.3733 | 3 |
| full_ols_av | anchor | -1.9800 | 0.2600 | 1 |
| full_ols_av | heuristic | 2.2133 | 0.5067 | 3 |
| gbt_av | smart | -4.2300 | 0.4050 | 4 |
| gbt_av | anchor | -5.4600 | 0.2800 | 1 |
| gbt_av | heuristic | 1.7000 | 0.5667 | 3 |
| modeloespecifico | smart | -0.0600 | 0.4650 | 4 |
| modeloespecifico | anchor | -1.1800 | 0.3600 | 1 |
| modeloespecifico | heuristic | 6.9300 | 0.7000 | 2 |
| rankthetank | smart | -11.3700 | 0.0650 | 4 |
| rankthetank | anchor | -11.3400 | 0.0600 | 1 |
| rankthetank | heuristic | -0.3500 | 0.4600 | 2 |
| selected_ols_av | smart | -0.4267 | 0.4200 | 3 |
| selected_ols_av | anchor | -1.7400 | 0.2400 | 1 |
| selected_ols_av | heuristic | 2.6733 | 0.5133 | 3 |
| selected_two_stage_av | smart | -0.4800 | 0.4733 | 3 |
| selected_two_stage_av | anchor | -1.9000 | 0.2600 | 1 |
| selected_two_stage_av | heuristic | 3.6200 | 0.6000 | 3 |
| stricthellraiser | smart | -3.1750 | 0.3500 | 4 |
| stricthellraiser | anchor | -6.2800 | 0.2000 | 1 |
| stricthellraiser | heuristic | -9.3100 | 0.1800 | 2 |


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

<\!-- gate_status: data sanity checks in Evidence Summary above -->
