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
| r2_positive_constrained_ols_av_suit | training | 0.5706 | 0.0000 | PASS | constrained_ols_av suit R²=0.5706 |
| r2_positive_constrained_ols_av_high | training | 0.4910 | 0.0000 | PASS | constrained_ols_av high R²=0.4910 |
| r2_positive_constrained_ols_av_low | training | 0.4609 | 0.0000 | PASS | constrained_ols_av low R²=0.4609 |
| r2_positive_constrained_ols_av_pass | training | -0.0238 | 0.0000 | WARN | constrained_ols_av pass R²=-0.0238 |
| r2_positive_full_ols_av_suit | training | 0.5182 | 0.0000 | PASS | full_ols_av suit R²=0.5182 |
| r2_positive_full_ols_av_high | training | 0.6489 | 0.0000 | PASS | full_ols_av high R²=0.6489 |
| r2_positive_full_ols_av_low | training | 0.4766 | 0.0000 | PASS | full_ols_av low R²=0.4766 |

*Full table omitted from markdown — see `tables/data_sanity.csv`*


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | suit | 0.5706 | 4.0174 | 2340 | 228 |
| constrained_ols_av | high | 0.4910 | 5.6478 | 585 | 57 |
| constrained_ols_av | low | 0.4609 | 5.0205 | 585 | 57 |
| constrained_ols_av | pass | -0.0238 | 4.5000 | 80 | 8 |
| full_ols_av | suit | 0.5182 | 4.2393 | 2340 | 228 |
| full_ols_av | high | 0.6489 | 4.6689 | 585 | 57 |
| full_ols_av | low | 0.4766 | 4.9754 | 585 | 57 |
| full_ols_av | pass | -0.0392 | 4.0691 | 80 | 8 |
| gbt_av | suit | 0.3681 | 4.4430 | 2340 | 228 |
| gbt_av | high | 0.5055 | 5.0822 | 585 | 57 |

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
| selected_ols_av | pooled | 1.7200 | 0.8800 | 2.5600 | 1.0000 | 1.0000 | -4.0000 | 1 |
| constrained_ols_av | pooled | 1.6000 | 0.7600 | 2.4000 | 1.0000 | 1.0000 | -4.0000 | 2 |
| full_ols_av | pooled | 1.4800 | 0.5200 | 2.5610 | 0.9800 | 1.0000 | -6.0000 | 3 |
| selected_two_stage_av | pooled | 1.2400 | 0.1000 | 2.4000 | 0.9600 | 0.9583 | -11.0000 | 4 |
| modeloespecifico | pooled | 0.7800 | -0.5800 | 2.0000 | 1.0000 | 0.9000 | -11.0000 | 5 |
| stricthellraiser | pooled | 0.1400 | -1.0600 | 1.2605 | 1.0000 | 0.9200 | -11.5000 | 6 |
| gbt_av | pooled | -1.2200 | -3.0200 | 0.5000 | 0.9800 | 0.7551 | -13.0000 | 7 |
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
| modeloespecifico | selected_two_stage_av | pooled | -0.4000 | -1.8600 | 1.1600 | 0.3600 | 50 |
| modeloespecifico | selected_two_stage_av | suit | 0.0455 | -1.5682 | 1.7278 | 0.4091 | 44 |
| modeloespecifico | selected_two_stage_av | high | -4.6667 | -6.0000 | -2.0000 | 0.0000 | 3 |
| modeloespecifico | selected_two_stage_av | low | -2.6667 | -4.0000 | -2.0000 | 0.0000 | 3 |
| modeloespecifico | selected_two_stage_av | bid_type:regular | -0.4000 | -1.8600 | 1.1600 | 0.3600 | 50 |
| selected_two_stage_av | modeloespecifico | pooled | -0.9000 | -2.3000 | 0.4400 | 0.4200 | 50 |

*Full table omitted from markdown — see `tables/h2h_delta_matrix.csv`*


</details>


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | pass_rate | make_rate | cvar_5 | net_cvar_5 | mix_suit | mix_high | mix_low | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 0.7800 | 4.9600 | 1.0000 | 0.0000 | 0.9000 | -5.5000 | -11.0000 | 0.9800 | 0.0000 | 0.0200 | comparator |
| selected_two_stage_av | 1.2400 | 5.2600 | 0.9600 | 0.0400 | 0.9583 | -4.5000 | -11.0000 | 0.7800 | 0.1000 | 0.1200 | comparator |
| gbt_av | -1.2200 | 3.1400 | 0.9800 | 0.0200 | 0.7551 | -7.0000 | -13.0000 | 0.3000 | 0.3000 | 0.4000 | comparator |
| constrained_ols_av | 1.6000 | 5.8000 | 1.0000 | 0.0000 | 1.0000 | 3.0000 | -4.0000 | 0.8600 | 0.0800 | 0.0600 | comparator |
| selected_ols_av | 1.7200 | 5.8600 | 1.0000 | 0.0000 | 1.0000 | 3.0000 | -4.0000 | 0.3800 | 0.3600 | 0.2600 | comparator |
| full_ols_av | 1.4800 | 5.6400 | 0.9800 | 0.0200 | 1.0000 | 2.0000 | -6.0000 | 0.3200 | 0.3600 | 0.3200 | comparator |
| stricthellraiser | 0.1400 | 4.8800 | 1.0000 | 0.0000 | 0.9200 | -3.0000 | -11.5000 | 1.0000 | 0.0000 | 0.0000 | comparator |
| rankthetank | -11.3000 | -6.8600 | 1.0000 | 0.0000 | 0.0600 | -9.5000 | -15.0000 | 1.0000 | 0.0000 | 0.0000 | comparator |
| modeloespecifico | 4.8000 |  | 0.4800 | 0.5200 | 0.9167 | -1.4000 |  | 0.9800 | 0.0000 | 0.0200 | h2h_self_play |
| selected_two_stage_av | 4.1900 |  | 0.5200 | 0.4800 | 0.8077 | -6.0000 |  | 0.7800 | 0.1000 | 0.1200 | h2h_self_play |

*Full table omitted from markdown — see `tables/behavior_summary.csv`*


### Behavior by Contract

| model | contract | net_eppd | bid_rate | pass_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 0.7800 | 1.0000 | 0.0000 | 0.9000 | comparator |
| selected_two_stage_av | pooled | 1.2400 | 0.9600 | 0.0400 | 0.9583 | comparator |
| gbt_av | pooled | -1.2200 | 0.9800 | 0.0200 | 0.7551 | comparator |
| constrained_ols_av | pooled | 1.6000 | 1.0000 | 0.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 1.7200 | 1.0000 | 0.0000 | 1.0000 | comparator |
| full_ols_av | pooled | 1.4800 | 0.9800 | 0.0200 | 1.0000 | comparator |
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
| selected_two_stage_av | bid_rate_range | 0.9600 | 0.0500 | 0.9500 | FAIL |
| selected_two_stage_av | make_rate_range | 0.9583 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 0.9800 | 0.0500 | 0.9500 | FAIL |
| gbt_av | make_rate_range | 0.7551 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| constrained_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| selected_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |

*Full table omitted from markdown — see `tables/sanity_bounds_check.csv`*

<\!-- gate_status: data sanity checks in §1 above -->
