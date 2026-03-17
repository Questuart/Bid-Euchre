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
| h2h_min_deals | h2h | 2500.0000 | 10.0000 | PASS | Minimum deals across cells: 2500 |
| comparator_bidders_present | comparator | 8.0000 | 2.0000 | PASS | 8 bidders in comparator |
| r2_positive_constrained_ols_av_high | training | 0.5308 | 0.0000 | PASS | constrained_ols_av high R²=0.5308 |
| r2_positive_constrained_ols_av_low | training | 0.5014 | 0.0000 | PASS | constrained_ols_av low R²=0.5014 |
| r2_positive_constrained_ols_av_pass | training | 0.0027 | 0.0000 | PASS | constrained_ols_av pass R²=0.0027 |
| r2_positive_constrained_ols_av_suit | training | 0.5548 | 0.0000 | PASS | constrained_ols_av suit R²=0.5548 |
| r2_positive_full_ols_av_high | training | 0.5335 | 0.0000 | PASS | full_ols_av high R²=0.5335 |
| r2_positive_full_ols_av_low | training | 0.5159 | 0.0000 | PASS | full_ols_av low R²=0.5159 |
| r2_positive_full_ols_av_pass | training | 0.0235 | 0.0000 | PASS | full_ols_av pass R²=0.0235 |

*Full table omitted from markdown — see `tables/data_sanity.csv`*


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | high | 0.5308 | 4.1849 | 60937 | 7737 |
| constrained_ols_av | low | 0.5014 | 4.2831 | 60937 | 7737 |
| constrained_ols_av | pass | 0.0027 | 3.5477 | 8000 | 1000 |
| constrained_ols_av | suit | 0.5548 | 4.1231 | 243748 | 30948 |
| full_ols_av | high | 0.5335 | 4.1697 | 60937 | 7737 |
| full_ols_av | low | 0.5159 | 4.2263 | 60937 | 7737 |
| full_ols_av | pass | 0.0235 | 3.3015 | 8000 | 1000 |
| full_ols_av | suit | 0.5705 | 4.0535 | 243748 | 30948 |
| gbt_av | high | 0.5513 | 3.8435 | 60937 | 7737 |
| gbt_av | low | 0.5406 | 3.8595 | 60937 | 7737 |

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

*Chart not available — source data absent.*


## 4. Model Interpretability

*Interpretability charts not yet generated.*


## 5. Cross-Model Decision Analysis

*Decision comparison analysis not yet generated.*


## 6. Comparator Rankings

| model | facet | net_eppd | ci_low | ci_high | bid_rate | make_rate | net_cvar_5 | rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gbt_av | pooled | 2.2548 | 2.1228 | 2.3884 | 0.9256 | 0.9922 | -5.5565 | 1 |
| full_ols_av | pooled | 2.2432 | 2.1216 | 2.3672 | 1.0000 | 1.0000 | -4.4960 | 2 |
| constrained_ols_av | pooled | 2.1976 | 2.0720 | 2.3240 | 1.0000 | 1.0000 | -4.5120 | 3 |
| selected_ols_av | pooled | 2.1928 | 2.0704 | 2.3192 | 1.0000 | 1.0000 | -4.4960 | 4 |
| selected_two_stage_av | pooled | 1.8756 | 1.7412 | 2.0100 | 1.0000 | 0.9980 | -5.0320 | 5 |
| modeloespecifico | pooled | 1.6608 | 1.5008 | 1.8188 | 1.0000 | 0.9496 | -11.1120 | 6 |
| stricthellraiser | pooled | 0.1096 | -0.0440 | 0.2648 | 1.0000 | 0.9472 | -11.2240 | 7 |
| rankthetank | pooled | -9.6972 | -9.9576 | -9.4316 | 1.0000 | 0.1476 | -15.0400 | 8 |


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
| modeloespecifico | modeloespecifico | pooled | -0.1724 | -0.3716 | 0.0256 | 0.4204 | 2500 |
| modeloespecifico | modeloespecifico | suit | -0.1600 | -0.3681 | 0.0438 | 0.4209 | 2350 |
| modeloespecifico | modeloespecifico | high | -0.6000 | -1.9714 | 0.8000 | 0.4429 | 70 |
| modeloespecifico | modeloespecifico | low | -0.1625 | -1.4125 | 1.0500 | 0.3875 | 80 |
| modeloespecifico | selected_two_stage_av | pooled | -0.0056 | -0.2148 | 0.2076 | 0.4236 | 2500 |
| modeloespecifico | selected_two_stage_av | suit | -0.0237 | -0.2427 | 0.1924 | 0.4186 | 2365 |
| modeloespecifico | selected_two_stage_av | high | -0.1765 | -1.9216 | 1.6275 | 0.5294 | 51 |
| modeloespecifico | selected_two_stage_av | low | 0.6071 | -0.6310 | 1.8452 | 0.5000 | 84 |
| selected_two_stage_av | modeloespecifico | pooled | -0.3428 | -0.5492 | -0.1348 | 0.4408 | 2500 |
| selected_two_stage_av | modeloespecifico | suit | -0.2842 | -0.4966 | -0.0705 | 0.4463 | 2382 |

*Full table omitted from markdown — see `tables/h2h_delta_matrix.csv`*


</details>


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | pass_rate | make_rate | cvar_5 | net_cvar_5 | mix_suit | mix_high | mix_low | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 1.6608 | 5.6320 | 1.0000 | 0.0000 | 0.9496 | -4.5120 | -11.1120 | 0.9400 | 0.0280 | 0.0320 | comparator |
| selected_two_stage_av | 1.8756 | 5.9316 | 1.0000 | 0.0000 | 0.9980 | 2.3600 | -5.0320 | 0.9572 | 0.0132 | 0.0296 | comparator |
| gbt_av | 2.2548 | 5.7228 | 0.9256 | 0.0744 | 0.9922 | 1.5130 | -5.5565 | 0.7052 | 0.1008 | 0.1940 | comparator |
| constrained_ols_av | 2.1976 | 6.0988 | 1.0000 | 0.0000 | 1.0000 | 2.7440 | -4.5120 | 0.7348 | 0.0860 | 0.1792 | comparator |
| selected_ols_av | 2.1928 | 6.0964 | 1.0000 | 0.0000 | 1.0000 | 2.7520 | -4.4960 | 0.7236 | 0.0888 | 0.1876 | comparator |
| full_ols_av | 2.2432 | 6.1216 | 1.0000 | 0.0000 | 1.0000 | 2.7520 | -4.4960 | 0.2580 | 0.1804 | 0.5616 | comparator |
| stricthellraiser | 0.1096 | 4.9284 | 1.0000 | 0.0000 | 0.9472 | -3.0000 | -11.2240 | 1.0000 | 0.0000 | 0.0000 | comparator |
| rankthetank | -9.6972 | -5.5808 | 1.0000 | 0.0000 | 0.1476 | -9.2480 | -15.0400 | 1.0000 | 0.0000 | 0.0000 | comparator |
| modeloespecifico | 4.6906 |  | 0.4880 | 0.5120 | 0.9287 | -3.2600 |  | 0.9400 | 0.0280 | 0.0320 | h2h_self_play |
| selected_two_stage_av | 4.6178 |  | 0.5128 | 0.4872 | 0.9150 | -4.3640 |  | 0.9572 | 0.0132 | 0.0296 | h2h_self_play |

*Full table omitted from markdown — see `tables/behavior_summary.csv`*


### Behavior by Contract

| model | contract | net_eppd | bid_rate | pass_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 1.6608 | 1.0000 | 0.0000 | 0.9496 | comparator |
| selected_two_stage_av | pooled | 1.8756 | 1.0000 | 0.0000 | 0.9980 | comparator |
| gbt_av | pooled | 2.2548 | 0.9256 | 0.0744 | 0.9922 | comparator |
| constrained_ols_av | pooled | 2.1976 | 1.0000 | 0.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 2.1928 | 1.0000 | 0.0000 | 1.0000 | comparator |
| full_ols_av | pooled | 2.2432 | 1.0000 | 0.0000 | 1.0000 | comparator |
| stricthellraiser | pooled | 0.1096 | 1.0000 | 0.0000 | 0.9472 | comparator |
| rankthetank | pooled | -9.6972 | 1.0000 | 0.0000 | 0.1476 | comparator |


### Chart 12. Bid and Make Rates

![Bid and Make Rates](charts/full_chart_suite/bid_behavior_panel.png)

### Chart 11. Contract Mix

![Contract Mix](charts/full_chart_suite/contract_mix_bars.png)


## 9. Sanity Bounds

| model | check_name | value | lower_bound | upper_bound | status |
| --- | --- | --- | --- | --- | --- |
| modeloespecifico | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| modeloespecifico | make_rate_range | 0.9496 | 0.1000 | 1.0000 | PASS |
| selected_two_stage_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_two_stage_av | make_rate_range | 0.9980 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 0.9256 | 0.0500 | 0.9500 | PASS |
| gbt_av | make_rate_range | 0.9922 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| constrained_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| selected_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |

*Full table omitted from markdown — see `tables/sanity_bounds_check.csv`*


## Gate Status

gate_status: See `hypothesis_outcomes` table above and `evidence_manifest.json` for machine-readable gate evidence.
