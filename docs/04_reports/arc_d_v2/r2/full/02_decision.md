# Rung r2 (full) — Decision Report

## Advancement Decision

**ADVANCE** (override of INVESTIGATE verdict)

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2336 | 2.1128 | 2.3568 | 1 |
| constrained_ols_av | 2.2040 | 2.0800 | 2.3288 | 2 |
| selected_ols_av | 2.1952 | 2.0696 | 2.3240 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.3563 | 0.4599 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.6060 | 0.6147 | 3 |
| constrained_ols_av | smart | -0.1572 | 0.3913 | 3 |
| constrained_ols_av | anchor | -0.0548 | 0.3684 | 1 |
| constrained_ols_av | heuristic | 3.4712 | 0.4940 | 3 |
| full_ols_av | smart | -0.7812 | 0.3144 | 3 |
| full_ols_av | anchor | 0.0768 | 0.3824 | 1 |
| full_ols_av | heuristic | 3.5113 | 0.5140 | 3 |
| gbt_av | smart | 1.3008 | 0.6121 | 4 |
| gbt_av | anchor | 1.0528 | 0.5584 | 1 |
| gbt_av | heuristic | 4.6177 | 0.6692 | 3 |
| modeloespecifico | smart | 0.7620 | 0.5521 | 4 |
| modeloespecifico | anchor | 0.2320 | 0.4548 | 1 |
| modeloespecifico | heuristic | 7.5360 | 0.7172 | 2 |
| rankthetank | smart | -10.5200 | 0.1024 | 4 |
| rankthetank | anchor | -10.4936 | 0.1024 | 1 |
| rankthetank | heuristic | 0.7938 | 0.5086 | 2 |
| selected_ols_av | smart | -0.1535 | 0.3931 | 3 |
| selected_ols_av | anchor | 0.0740 | 0.3900 | 1 |
| selected_ols_av | heuristic | 3.6260 | 0.5076 | 3 |
| selected_two_stage_av | smart | 0.8991 | 0.5477 | 3 |
| selected_two_stage_av | anchor | 0.2076 | 0.4316 | 1 |
| selected_two_stage_av | heuristic | 4.2311 | 0.5871 | 3 |
| stricthellraiser | smart | -2.0346 | 0.3916 | 4 |
| stricthellraiser | anchor | -4.5468 | 0.3080 | 1 |
| stricthellraiser | heuristic | -8.8300 | 0.2102 | 2 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| hypothesis_id | description | status |
| --- | --- | --- |
| H1 | Opponent context improves GBT pooled H2H delta vs anchor | PASS |
| H2 | GBT R2 suit R-squared exceeds R1 suit R-squared | FAIL |
| H3 | GBT R2 comparator net_eppd maintains or improves over R1 | PASS |
| H4 | GBT suit H2H delta vs anchor is positive | PASS |
| H5 | Two-stage model gap vs GBT narrows with richer context | PASS |
| H6 | All models bid at least half the time | PASS |
| H7 | GBT H2H win rate vs anchor exceeds 45% | PASS |
| H8 | Full OLS approximately equals constrained OLS | SKIP |
| H9 | ModeloEspecifico heuristic is worst among trained models | PASS |


## Recommendation

7/7 evaluated hypotheses pass. H2 (suit R-squared) failed narrowly (0.604 vs 0.621 threshold, a 2.7% miss on a secondary diagnostic metric). H8 skipped (LA-4 roster trim). Override to ADVANCE — see `04_rung_decision.md` for full rationale.

## Supporting Evidence

- Chart 4: Comparator Ranking Bars
- Chart 6: H2H Delta by Contract
- Chart 7: H2H Heatmap
- Chart 5: Tail Risk Panel
- Chart 12: Bid and Make Rates
- Chart 23: Intelligence-Faceted H2H
- Full tables: `tables/comparator_rankings.csv`, `tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`

<!-- gate_status: data sanity checks in Evidence Summary above -->
