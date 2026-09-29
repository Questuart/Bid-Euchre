# Rung r1 (canonical) — Decision Report

## Advancement Decision

**PRELIMINARY**

## Evidence Summary

### Comparator Standing

| model | net_eppd | ci_low | ci_high | rank |
| --- | --- | --- | --- | --- |
| gbt_av | 3.1200 | 2.0000 | 4.1605 | 1 |
| full_ols_av | 1.9600 | 1.0000 | 2.9200 | 2 |
| selected_ols_av | 1.9200 | 1.1190 | 2.7600 | 3 |


See Chart 4 (Comparator Ranking Bars) and Chart 5 (Tail Risk Panel) for visual context.

### Head-to-Head Performance

| team0_model | tier | mean_delta | mean_win_rate | n_opponents |
| --- | --- | --- | --- | --- |
| anchor_hybrid_r0_full | smart | -0.7600 | 0.4400 | 4 |
| anchor_hybrid_r0_full | heuristic | 4.1933 | 0.6200 | 3 |
| constrained_ols_av | smart | 0.4600 | 0.4533 | 3 |
| constrained_ols_av | anchor | -1.6200 | 0.2400 | 1 |
| constrained_ols_av | heuristic | 2.9600 | 0.4800 | 3 |
| full_ols_av | smart | 0.5800 | 0.5667 | 3 |
| full_ols_av | anchor | -1.6200 | 0.3800 | 1 |
| full_ols_av | heuristic | 1.3533 | 0.5600 | 3 |
| gbt_av | smart | -0.9150 | 0.5800 | 4 |
| gbt_av | anchor | -2.3200 | 0.5000 | 1 |
| gbt_av | heuristic | 3.8267 | 0.6867 | 3 |
| modeloespecifico | smart | 0.1400 | 0.4900 | 4 |
| modeloespecifico | anchor | -1.1800 | 0.3600 | 1 |
| modeloespecifico | heuristic | 6.9300 | 0.7000 | 2 |
| rankthetank | smart | -10.0800 | 0.1150 | 4 |
| rankthetank | anchor | -11.3400 | 0.0600 | 1 |
| rankthetank | heuristic | -0.3500 | 0.4600 | 2 |
| selected_ols_av | smart | -1.3667 | 0.3267 | 3 |
| selected_ols_av | anchor | -2.1400 | 0.2600 | 1 |
| selected_ols_av | heuristic | 2.6733 | 0.5333 | 3 |
| selected_two_stage_av | smart | -0.9067 | 0.3467 | 3 |
| selected_two_stage_av | anchor | -2.4200 | 0.2600 | 1 |
| selected_two_stage_av | heuristic | 2.7467 | 0.5333 | 3 |
| stricthellraiser | smart | -1.5650 | 0.3650 | 4 |
| stricthellraiser | anchor | -6.2800 | 0.2000 | 1 |
| stricthellraiser | heuristic | -9.3100 | 0.1800 | 2 |


See Chart 7 (H2H Heatmap), Chart 6 (H2H Delta by Contract), and Chart 23 (Intelligence-Faceted H2H) for tier-level analysis.

### Hypothesis Outcomes

> No hypothesis outcomes available.

### Data Quality Status

- Data sanity: **WARN** — 7 WARN, 16 PASS across 23 checks
- Sanity bounds: **FAIL** — 13 FAIL, 23 PASS across 36 checks

The WARNs identify non-positive model R² checks for pass contracts, the full OLS low-contract model, and the selected two-stage suit model. The FAILs identify bid rates above the 0.95 upper bound, RankTheTank's 0.06 make rate below the 0.10 lower bound, and the same values failing the positive-R² requirement.

These screening statuses are reported separately from the formal hypothesis outcome above. See `tables/data_sanity.csv` and `tables/sanity_bounds_check.csv` for individual checks.


## Recommendation

**PRELIMINARY — formal advance-check evidence absent**

Data-driven triage based on available canonical evidence:

- **gbt_av** net_eppd = 3.120
- **full_ols_av** net_eppd = 1.960
- **selected_ols_av** net_eppd = 1.920
- Best H2H win rate: **modeloespecifico** (70.0% vs heuristic tier)
- Data sanity: **WARN** — 7 WARN, 16 PASS across 23 checks
- Sanity bounds: **FAIL** — 13 FAIL, 23 PASS across 36 checks

**Watch items / caveats:**

- Formal hypothesis tests not yet executed
- Canonical sample sizes (single seed) may be insufficient for tail analysis
- Run the advance-check pipeline (`--mode FULL`) for definitive evidence

## Supporting Evidence

- Chart 4: Comparator Ranking Bars
- Chart 6: H2H Delta by Contract
- Chart 7: H2H Heatmap
- Chart 5: Tail Risk Panel
- Chart 12: Bid and Make Rates
- Chart 23: Intelligence-Faceted H2H
- Full tables: `tables/comparator_rankings.csv`, `tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`

<!-- gate_status: data sanity checks in Evidence Summary above -->
