# Rung ? (QUICK) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| gbt_av | 3.7000 | 2.3990 | 5.0605 | 1 |
| full_ols_av | 1.8400 | 1.0000 | 2.6800 | 2 |
| constrained_ols_av | 1.6800 | 0.8400 | 2.5200 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.8500 | 0.4500 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.1933 | 0.6200 | 3 |
| constrained_ols_av | smart | 0.3067 | 0.4867 | 3 |
| constrained_ols_av | anchor | -1.6200 | 0.2400 | 1 |
| constrained_ols_av | heuristic | 2.9600 | 0.4800 | 3 |
| full_ols_av | smart | 0.0200 | 0.5333 | 3 |
| full_ols_av | anchor | -1.8400 | 0.3800 | 1 |
| full_ols_av | heuristic | 2.6467 | 0.6067 | 3 |
| gbt_av | smart | -0.5800 | 0.5450 | 4 |
| gbt_av | anchor | -1.3400 | 0.5600 | 1 |
| gbt_av | heuristic | 3.8400 | 0.6933 | 3 |
| modeloespecifico | smart | 0.2150 | 0.4850 | 4 |
| modeloespecifico | anchor | -1.1800 | 0.3600 | 1 |
| modeloespecifico | heuristic | 6.9300 | 0.7000 | 2 |
| rankthetank | smart | -10.8250 | 0.0850 | 4 |
| rankthetank | anchor | -11.3400 | 0.0600 | 1 |
| rankthetank | heuristic | -0.3500 | 0.4600 | 2 |
| selected_ols_av | smart | -1.1000 | 0.3467 | 3 |
| selected_ols_av | anchor | -1.6400 | 0.3000 | 1 |
| selected_ols_av | heuristic | 2.9200 | 0.5800 | 3 |
| selected_two_stage_av | smart | -0.7133 | 0.3733 | 3 |
| selected_two_stage_av | anchor | -2.0200 | 0.3200 | 1 |
| selected_two_stage_av | heuristic | 2.9333 | 0.6000 | 3 |
| stricthellraiser | smart | -1.5100 | 0.3700 | 4 |
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

<\!-- gate_status: data sanity checks in §1 above -->
