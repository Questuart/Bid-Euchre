# Rung Results Report

Generated from canonical CSV tables and chart PNGs.

## Dashboards

### Chart 1. Competitive Dashboard

![Competitive Dashboard](charts/dashboard_competitive.png)

### Chart 2. Health Dashboard

![Health Dashboard](charts/dashboard_health.png)

### Chart 3. Model Evaluation Dashboard

![Model Evaluation Dashboard](charts/dashboard_model_eval.png)


## 1. Data Sanity

| check_name | scope | value | threshold | status | detail |
| --- | --- | --- | --- | --- | --- |
| h2h_cells_populated | h2h | 81.0000 | 81.0000 | PASS | 81/81 cells have metrics |
| h2h_min_deals | h2h | 50.0000 | 10.0000 | PASS | Minimum deals across cells: 50 |
| comparator_bidders_present | comparator | 8.0000 | 2.0000 | PASS | 8 bidders in comparator |
| r2_positive_constrained_ols_av_suit | training | 0.5345 | 0.0000 | PASS | constrained_ols_av suit R²=0.5345 |
| r2_positive_constrained_ols_av_high | training | 0.3601 | 0.0000 | PASS | constrained_ols_av high R²=0.3601 |
| r2_positive_constrained_ols_av_low | training | 0.1855 | 0.0000 | PASS | constrained_ols_av low R²=0.1855 |
| r2_positive_constrained_ols_av_pass | training | -0.1923 | 0.0000 | WARN | constrained_ols_av pass R²=-0.1923 |
| r2_positive_full_ols_av_suit | training | 0.3912 | 0.0000 | PASS | full_ols_av suit R²=0.3912 |
| r2_positive_full_ols_av_high | training | 0.2936 | 0.0000 | PASS | full_ols_av high R²=0.2936 |
| r2_positive_full_ols_av_low | training | -0.1678 | 0.0000 | WARN | full_ols_av low R²=-0.1678 |

*Full table omitted from markdown — see `tables/data_sanity.csv`*


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | suit | 0.5345 | 4.7733 | 2400 | 280 |
| constrained_ols_av | high | 0.3601 | 5.7471 | 600 | 70 |
| constrained_ols_av | low | 0.1855 | 6.6246 | 600 | 70 |
| constrained_ols_av | pass | -0.1923 | 4.8548 | 80 | 8 |
| full_ols_av | suit | 0.3912 | 5.5614 | 2400 | 280 |
| full_ols_av | high | 0.2936 | 6.6438 | 600 | 70 |
| full_ols_av | low | -0.1678 | 8.5602 | 600 | 70 |
| full_ols_av | pass | -1.0305 | 7.1442 | 80 | 8 |
| gbt_av | suit | 0.3359 | 5.2664 | 2400 | 280 |
| gbt_av | high | 0.4812 | 4.4355 | 600 | 70 |

*Full table omitted from markdown — see `tables/model_performance.csv`*


### Chart 14. R-squared by Contract

![R-squared by Contract](charts/full_chart_suite/r2_by_contract.png)

### Chart 15. MAE by Contract

![MAE by Contract](charts/full_chart_suite/mae_by_contract.png)


## 3. Offline Diagnostics

### Chart 16. Predicted vs Actual

*Chart not available — source data absent.*

### Chart 17. Residual Distribution

*Chart not available — source data absent.*

### Chart 18. Calibration Curve

*Chart not available — source data absent.*

### Chart 20. Feature Importance

![Feature Importance](charts/full_chart_suite/feature_importance.png)


## 4. Model Interpretability

### Chart 19. Selection Path

![Selection Path](charts/full_chart_suite/selection_path.png)


## 5. Cross-Model Decision Analysis

*Decision comparison analysis not yet generated.*


## 6. Comparator Rankings

| model | facet | net_eppd | ci_low | ci_high | bid_rate | make_rate | net_cvar_5 | rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gbt_av | pooled | 3.1200 | 2.0000 | 4.1605 | 1.0000 | 0.9600 | -11.0000 | 1 |
| full_ols_av | pooled | 1.9600 | 1.0000 | 2.9200 | 0.9000 | 1.0000 | -4.0000 | 2 |
| selected_ols_av | pooled | 1.9200 | 1.1190 | 2.7600 | 0.9200 | 1.0000 | -4.0000 | 3 |
| selected_two_stage_av | pooled | 1.8000 | 0.6400 | 2.8805 | 0.9000 | 0.9556 | -11.0000 | 4 |
| constrained_ols_av | pooled | 1.7200 | 0.9200 | 2.5210 | 1.0000 | 1.0000 | -4.0000 | 5 |
| modeloespecifico | pooled | 0.7800 | -0.5800 | 2.0000 | 1.0000 | 0.9000 | -11.0000 | 6 |
| stricthellraiser | pooled | 0.1400 | -1.0600 | 1.2605 | 1.0000 | 0.9200 | -11.5000 | 7 |
| rankthetank | pooled | -11.3000 | -12.3600 | -9.9190 | 1.0000 | 0.0600 | -15.0000 | 8 |


### Chart 4. Comparator Ranking Bars

![Comparator Ranking Bars](charts/full_chart_suite/comparator_ranking_bars.png)

### Chart 5. Tail Risk Panel

![Tail Risk Panel](charts/full_chart_suite/tail_risk_panel.png)


## 7. H2H Battery

### Chart 6. H2H Delta by Contract

![H2H Delta by Contract](charts/full_chart_suite/delta_bars_by_contract.png)

### Chart 7. H2H Heatmap

![H2H Heatmap](charts/full_chart_suite/h2h_heatmap.png)


<details><summary>Full H2H Delta Matrix (click to expand)</summary>

| team0 | team1 | facet | net_eppd_delta | ci_low | ci_high | win_rate_a | deals_total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | modeloespecifico | pooled | -1.1200 | -2.3200 | 0.1000 | 0.3600 | 50 |
| modeloespecifico | modeloespecifico | suit | -1.2653 | -2.4694 | -0.1020 | 0.3469 | 49 |
| modeloespecifico | modeloespecifico | low | 6.0000 | 6.0000 | 6.0000 | 1.0000 | 1 |
| modeloespecifico | modeloespecifico | bid_type:regular | -1.1200 | -2.3200 | 0.1000 | 0.3600 | 50 |
| modeloespecifico | selected_two_stage_av | pooled | 0.2600 | -1.3000 | 1.8200 | 0.5400 | 50 |
| modeloespecifico | selected_two_stage_av | suit | 0.3953 | -1.2326 | 1.9773 | 0.5814 | 43 |
| modeloespecifico | selected_two_stage_av | high | -6.0000 | -6.0000 | -6.0000 | 0.0000 | 1 |
| modeloespecifico | selected_two_stage_av | low | 0.3333 | -4.6667 | 6.0000 | 0.3333 | 6 |
| modeloespecifico | selected_two_stage_av | bid_type:regular | 0.2600 | -1.3000 | 1.8200 | 0.5400 | 50 |
| selected_two_stage_av | modeloespecifico | pooled | -1.5000 | -2.8600 | -0.1000 | 0.3600 | 50 |

*Full table omitted from markdown — see `tables/h2h_delta_matrix.csv`*


</details>


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | pass_rate | make_rate | cvar_5 | net_cvar_5 | mix_suit | mix_high | mix_low | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 0.7800 | 4.9600 | 1.0000 | 0.0000 | 0.9000 | -5.5000 | -11.0000 | 0.9800 | 0.0000 | 0.0200 | comparator |
| selected_two_stage_av | 1.8000 | 5.2400 | 0.9000 | 0.1000 | 0.9556 | -4.5000 | -11.0000 | 0.7200 | 0.0200 | 0.2600 | comparator |
| gbt_av | 3.1200 | 6.3600 | 1.0000 | 0.0000 | 0.9600 | -5.5000 | -11.0000 | 0.4000 | 0.2400 | 0.3600 | comparator |
| constrained_ols_av | 1.7200 | 5.8600 | 1.0000 | 0.0000 | 1.0000 | 3.0000 | -4.0000 | 0.7000 | 0.1000 | 0.2000 | comparator |
| selected_ols_av | 1.9200 | 5.5600 | 0.9200 | 0.0800 | 1.0000 | 3.0000 | -4.0000 | 0.6600 | 0.0800 | 0.2600 | comparator |
| full_ols_av | 1.9600 | 5.4800 | 0.9000 | 0.1000 | 1.0000 | 3.0000 | -4.0000 | 1.0000 | 0.0000 | 0.0000 | comparator |
| stricthellraiser | 0.1400 | 4.8800 | 1.0000 | 0.0000 | 0.9200 | -3.0000 | -11.5000 | 1.0000 | 0.0000 | 0.0000 | comparator |
| rankthetank | -11.3000 | -6.8600 | 1.0000 | 0.0000 | 0.0600 | -9.5000 | -15.0000 | 1.0000 | 0.0000 | 0.0000 | comparator |
| modeloespecifico | 4.8000 |  | 0.4800 | 0.5200 | 0.9167 | -1.4000 |  | 0.9800 | 0.0000 | 0.0200 | h2h_self_play |
| selected_two_stage_av | 4.7200 |  | 0.6800 | 0.3200 | 0.9118 | -3.2000 |  | 0.7200 | 0.0200 | 0.2600 | h2h_self_play |

*Full table omitted from markdown — see `tables/behavior_summary.csv`*


### Behavior by Contract

| model | contract | net_eppd | bid_rate | pass_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 0.7800 | 1.0000 | 0.0000 | 0.9000 | comparator |
| selected_two_stage_av | pooled | 1.8000 | 0.9000 | 0.1000 | 0.9556 | comparator |
| gbt_av | pooled | 3.1200 | 1.0000 | 0.0000 | 0.9600 | comparator |
| constrained_ols_av | pooled | 1.7200 | 1.0000 | 0.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 1.9200 | 0.9200 | 0.0800 | 1.0000 | comparator |
| full_ols_av | pooled | 1.9600 | 0.9000 | 0.1000 | 1.0000 | comparator |
| stricthellraiser | pooled | 0.1400 | 1.0000 | 0.0000 | 0.9200 | comparator |
| rankthetank | pooled | -11.3000 | 1.0000 | 0.0000 | 0.0600 | comparator |


### Chart 12. Bid and Make Rates

![Bid and Make Rates](charts/full_chart_suite/bid_behavior_panel.png)

### Chart 11. Contract Mix

![Contract Mix](charts/full_chart_suite/contract_mix_bars.png)


## 9. Sanity Bounds

| model | check_name | value | lower_bound | upper_bound | status |
| --- | --- | --- | --- | --- | --- |
| modeloespecifico | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| modeloespecifico | make_rate_range | 0.9000 | 0.1000 | 1.0000 | PASS |
| selected_two_stage_av | bid_rate_range | 0.9000 | 0.0500 | 0.9500 | PASS |
| selected_two_stage_av | make_rate_range | 0.9556 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| gbt_av | make_rate_range | 0.9600 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| constrained_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| selected_ols_av | bid_rate_range | 0.9200 | 0.0500 | 0.9500 | PASS |
| selected_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |

*Full table omitted from markdown — see `tables/sanity_bounds_check.csv`*
