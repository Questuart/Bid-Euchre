# Rung r0 (full) — Decision Report

## Advancement Decision

**ADVANCE**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| full_ols_av | 2.2778 | 2.1913 | 2.3653 | 1 |
| selected_two_stage_av | 1.9621 | 1.8688 | 2.0553 | 2 |
| gbt_av | 1.9548 | 1.8509 | 2.0577 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.1653 | 0.4685 | 2 |
| anchor_hybrid_r0_full | heuristic | -0.4502 | 0.4135 | 1 |
| full_ols_av | smart | -0.8316 | 0.2844 | 1 |
| full_ols_av | anchor | 0.0503 | 0.3799 | 1 |
| full_ols_av | heuristic | -1.0983 | 0.2526 | 1 |
| gbt_av | smart | 1.1086 | 0.6044 | 2 |
| gbt_av | anchor | 0.7028 | 0.5309 | 1 |
| gbt_av | heuristic | 0.5318 | 0.5568 | 1 |
| modeloespecifico | smart | 0.6116 | 0.5209 | 2 |
| modeloespecifico | anchor | 0.3998 | 0.4741 | 1 |
| selected_two_stage_av | smart | 0.7891 | 0.5471 | 1 |
| selected_two_stage_av | anchor | 0.1845 | 0.4244 | 1 |
| selected_two_stage_av | heuristic | -0.2179 | 0.4311 | 1 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| hypothesis_id | description | status |
| --- | --- | --- |
| H1 | GBT outperforms anchor on suit contract delta (H2H) | PASS |
| H2 | GBT outperforms anchor on pooled net_eppd (H2H) | PASS |
| H3 | GBT high-contract delta is positive vs anchor (H2H) | PASS |
| H4 | GBT low-contract delta is non-negative vs anchor (H2H) | PASS |
| H5 | GBT suit R-squared exceeds selected OLS suit R-squared | SKIP |
| H6 | All models bid at least half the time (no pathological passing) | PASS |
| H7 | GBT H2H win rate vs anchor exceeds 50% | PASS |
| H8 | Two-stage model does not regress vs selected OLS on pooled net_eppd | SKIP |
| H9 | ModeloEspecifico heuristic is worst on pooled net_eppd (sanity check) | PASS |


## Recommendation

All evaluated hypothesis checks passed (2 skipped). Evidence supports advancing to the next rung.

## Supporting Evidence

- Chart 4: Comparator Ranking Bars
- Chart 6: H2H Delta by Contract
- Chart 7: H2H Heatmap
- Chart 5: Tail Risk Panel
- Chart 12: Bid and Make Rates
- Chart 23: Intelligence-Faceted H2H
- Full tables: `tables/comparator_rankings.csv`, `tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`

<!-- gate_status: data sanity checks in Evidence Summary above -->
