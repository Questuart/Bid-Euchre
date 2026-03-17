# Rung R1 (QUICK) — Decision Report

## Advancement Decision

**PENDING**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| gbt_av | 2.1136 | 1.9932 | 2.2336 | 1 |
| full_ols_av | 1.9720 | 1.8512 | 2.0920 | 2 |
| constrained_ols_av | 1.8152 | 1.6904 | 1.9416 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.1232 | 0.4824 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.6060 | 0.6147 | 3 |
| constrained_ols_av | smart | -0.0160 | 0.4015 | 3 |
| constrained_ols_av | anchor | -0.0968 | 0.3652 | 1 |
| constrained_ols_av | heuristic | 3.0368 | 0.4604 | 3 |
| full_ols_av | smart | -0.7355 | 0.3155 | 3 |
| full_ols_av | anchor | -0.1752 | 0.3512 | 1 |
| full_ols_av | heuristic | 2.9772 | 0.4655 | 3 |
| gbt_av | smart | 1.5477 | 0.5879 | 4 |
| gbt_av | anchor | 0.4900 | 0.4396 | 1 |
| gbt_av | heuristic | 4.0324 | 0.5801 | 3 |
| modeloespecifico | smart | 1.5777 | 0.6562 | 4 |
| modeloespecifico | anchor | 0.2320 | 0.4548 | 1 |
| modeloespecifico | heuristic | 7.5360 | 0.7172 | 2 |
| rankthetank | smart | -10.5200 | 0.1024 | 4 |
| rankthetank | anchor | -10.4936 | 0.1024 | 1 |
| rankthetank | heuristic | 0.7938 | 0.5086 | 2 |
| selected_ols_av | smart | -0.5716 | 0.3367 | 3 |
| selected_ols_av | anchor | -0.2012 | 0.3524 | 1 |
| selected_ols_av | heuristic | 2.9820 | 0.4585 | 3 |
| selected_two_stage_av | smart | 1.1348 | 0.5743 | 3 |
| selected_two_stage_av | anchor | -0.1196 | 0.3700 | 1 |
| selected_two_stage_av | heuristic | 3.9328 | 0.5152 | 3 |
| stricthellraiser | smart | -1.3291 | 0.4071 | 4 |
| stricthellraiser | anchor | -4.5468 | 0.3080 | 1 |
| stricthellraiser | heuristic | -8.8300 | 0.2102 | 2 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

| description |
| --- |
| Partner context improves GBT pooled H2H delta vs anchor |
| GBT R1 suit H2H delta exceeds R0 suit delta (partner helps suit bidding) |
| GBT R1 suit R-squared exceeds R0 suit R-squared |
| Position features improve first-bidder accuracy (auction_position=0) |
| Two-stage model narrows gap vs GBT with partner context |
| All models bid at least half the time (no pathological passing) |
| GBT H2H win rate vs anchor exceeds 50% |
| Full OLS approximately equals constrained OLS (feature selection doesn't matter for OLS) |
| ModeloEspecifico heuristic is worst among trained models (sanity check) |


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
