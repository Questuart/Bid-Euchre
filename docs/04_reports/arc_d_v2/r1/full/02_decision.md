# Rung r1 (full) — Decision Report

## Advancement Decision

**ADVANCE**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2750 | 2.1875 | 2.3627 | 1 |
| gbt_av | 2.0091 | 1.9081 | 2.1084 | 2 |
| selected_two_stage_av | 1.9621 | 1.8688 | 2.0553 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.3048 | 0.4595 | 2 |
| anchor_hybrid_r0_full | heuristic | -0.4502 | 0.4135 | 1 |
| full_ols_av | smart | -1.2655 | 0.2519 | 1 |
| full_ols_av | anchor | 0.1747 | 0.3961 | 1 |
| full_ols_av | heuristic | -1.1054 | 0.2540 | 1 |
| gbt_av | smart | 1.5486 | 0.6561 | 2 |
| gbt_av | anchor | 1.0119 | 0.5723 | 1 |
| gbt_av | heuristic | 0.7879 | 0.6020 | 1 |
| modeloespecifico | smart | 0.6018 | 0.5103 | 2 |
| modeloespecifico | anchor | 0.3998 | 0.4741 | 1 |
| selected_two_stage_av | smart | 1.2424 | 0.5769 | 1 |
| selected_two_stage_av | anchor | 0.3275 | 0.4416 | 1 |
| selected_two_stage_av | heuristic | -0.1899 | 0.4443 | 1 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| hypothesis_id | description | status |
| --- | --- | --- |
| H1 | Partner context improves GBT pooled H2H delta vs anchor | PASS |
| H2 | GBT R1 suit H2H delta exceeds R0 suit delta (partner helps suit bidding) | PASS |
| H3 | GBT R1 suit R-squared exceeds R0 suit R-squared | PASS |
| H4 | Position features improve first-bidder accuracy (auction_position=0) | PASS |
| H5 | Two-stage model narrows gap vs GBT with partner context | PASS |
| H6 | All models bid at least half the time (no pathological passing) | PASS |
| H7 | GBT H2H win rate vs anchor exceeds 50% | PASS |
| H8 | Full OLS approximately equals constrained OLS (feature selection doesn't matter for OLS) | SKIP |
| H9 | ModeloEspecifico heuristic is worst among trained models (sanity check) | PASS |


## Recommendation

All evaluated hypothesis checks passed (1 skipped). Evidence supports advancing to the next rung.

## Supporting Evidence

- Chart 4: Comparator Ranking Bars
- Chart 6: H2H Delta by Contract
- Chart 7: H2H Heatmap
- Chart 5: Tail Risk Panel
- Chart 12: Bid and Make Rates
- Chart 23: Intelligence-Faceted H2H
- Full tables: `tables/comparator_rankings.csv`, `tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`

<!-- gate_status: data sanity checks in §1 above -->
