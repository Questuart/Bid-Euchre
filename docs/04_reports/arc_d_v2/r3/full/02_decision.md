# Rung r3 (full) — Decision Report

## Advancement Decision

**ADVANCE**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2829 | 2.1948 | 2.3706 | 1 |
| gbt_av | 2.1024 | 2.0080 | 2.1967 | 2 |
| selected_two_stage_av | 1.9276 | 1.8339 | 2.0227 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.2519 | 0.4657 | 2 |
| anchor_hybrid_r0_full | heuristic | -0.4502 | 0.4135 | 1 |
| full_ols_av | smart | -0.9321 | 0.2807 | 1 |
| full_ols_av | anchor | 0.2124 | 0.4012 | 1 |
| full_ols_av | heuristic | -1.1068 | 0.2539 | 1 |
| gbt_av | smart | 1.6056 | 0.6426 | 2 |
| gbt_av | anchor | 0.9736 | 0.5528 | 1 |
| gbt_av | heuristic | 0.8150 | 0.5909 | 1 |
| modeloespecifico | smart | 0.7556 | 0.5241 | 2 |
| modeloespecifico | anchor | 0.3998 | 0.4741 | 1 |
| selected_two_stage_av | smart | 0.9012 | 0.5437 | 1 |
| selected_two_stage_av | anchor | 0.1699 | 0.4206 | 1 |
| selected_two_stage_av | heuristic | -0.4862 | 0.4133 | 1 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| hypothesis_id | description | status |
| --- | --- | --- |
| H1 | GBT pooled H2H delta vs anchor remains positive with expanded action space | PASS |
| H2 | GBT comparator net_eppd maintains above 2.0 with expanded action space | PASS |
| H3 | GBT bids at least 40% of the time in comparator | PASS |
| H4 | GBT R3 suit R-squared does not collapse below R0 baseline | PASS |
| H5 | Two-stage model gap vs GBT is within 1.0 net_eppd in comparator | PASS |
| H6 | All models bid at least half the time | PASS |
| H7 | GBT H2H win rate vs anchor exceeds 45% | PASS |
| H8 | GBT make rate stays above 50% in comparator | PASS |
| H9 | ModeloEspecifico heuristic is worst among trained models in comparator | PASS |


## Recommendation

All hypothesis checks passed. Evidence supports advancing — lineage complete.

## Supporting Evidence

- Chart 4: Comparator Ranking Bars
- Chart 6: H2H Delta by Contract
- Chart 7: H2H Heatmap
- Chart 5: Tail Risk Panel
- Chart 12: Bid and Make Rates
- Chart 23: Intelligence-Faceted H2H
- Full tables: `tables/comparator_rankings.csv`, `tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`
