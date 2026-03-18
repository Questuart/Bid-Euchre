# Rung r3 (quick) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2816 | 2.1592 | 2.4032 | 1 |
| constrained_ols_av | 2.1944 | 2.0728 | 2.3192 | 2 |
| selected_ols_av | 2.0784 | 1.9528 | 2.2048 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.3206 | 0.4638 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.6060 | 0.6147 | 3 |
| constrained_ols_av | smart | 0.0943 | 0.4208 | 3 |
| constrained_ols_av | anchor | -0.0500 | 0.3684 | 1 |
| constrained_ols_av | heuristic | 3.4328 | 0.4901 | 3 |
| full_ols_av | smart | -1.1136 | 0.2700 | 3 |
| full_ols_av | anchor | 0.0916 | 0.3864 | 1 |
| full_ols_av | heuristic | 3.4955 | 0.5020 | 3 |
| gbt_av | smart | 1.4621 | 0.6185 | 4 |
| gbt_av | anchor | 0.5788 | 0.5072 | 1 |
| gbt_av | heuristic | 4.5083 | 0.6640 | 3 |
| modeloespecifico | smart | 0.8945 | 0.5658 | 4 |
| modeloespecifico | anchor | 0.2320 | 0.4548 | 1 |
| modeloespecifico | heuristic | 7.5360 | 0.7172 | 2 |
| rankthetank | smart | -10.5200 | 0.1024 | 4 |
| rankthetank | anchor | -10.4936 | 0.1024 | 1 |
| rankthetank | heuristic | 0.7938 | 0.5086 | 2 |
| selected_ols_av | smart | 0.0228 | 0.4115 | 3 |
| selected_ols_av | anchor | 0.0240 | 0.3808 | 1 |
| selected_ols_av | heuristic | 3.5601 | 0.4935 | 3 |
| selected_two_stage_av | smart | 0.8437 | 0.5493 | 3 |
| selected_two_stage_av | anchor | 0.1140 | 0.4144 | 1 |
| selected_two_stage_av | heuristic | 4.2125 | 0.5795 | 3 |
| stricthellraiser | smart | -2.0023 | 0.3979 | 4 |
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

<!-- gate_status: data sanity checks in §1 above -->
