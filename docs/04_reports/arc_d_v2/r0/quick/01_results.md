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
| comparator_bidders_present | comparator | 4.0000 | 2.0000 | PASS | 4 bidders in comparator |
| r2_positive_constrained_ols_av_suit | training | 0.5706 | 0.0000 | PASS | constrained_ols_av suit R²=0.5706 |
| r2_positive_constrained_ols_av_high | training | 0.4910 | 0.0000 | PASS | constrained_ols_av high R²=0.4910 |
| r2_positive_constrained_ols_av_low | training | 0.4609 | 0.0000 | PASS | constrained_ols_av low R²=0.4609 |
| r2_positive_constrained_ols_av_pass | training | -0.0238 | 0.0000 | WARN | constrained_ols_av pass R²=-0.0238 |
| r2_positive_full_ols_av_high | training | 0.5248 | 0.0000 | PASS | full_ols_av high R²=0.5248 |
| r2_positive_full_ols_av_low | training | 0.5092 | 0.0000 | PASS | full_ols_av low R²=0.5092 |
| r2_positive_full_ols_av_pass | training | 0.0147 | 0.0000 | PASS | full_ols_av pass R²=0.0147 |

*Full table omitted from markdown — see `tables/data_sanity.csv`*


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | suit | 0.5706 | 4.0174 | 2340 | 228 |
| constrained_ols_av | high | 0.4910 | 5.6478 | 585 | 57 |
| constrained_ols_av | low | 0.4609 | 5.0205 | 585 | 57 |
| constrained_ols_av | pass | -0.0238 | 4.5000 | 80 | 8 |
| full_ols_av | high | 0.5248 | 4.2199 | 1229966 | 153083 |
| full_ols_av | low | 0.5092 | 4.2467 | 1229966 | 153083 |
| full_ols_av | pass | 0.0147 | 3.6858 | 160000 | 20000 |
| full_ols_av | suit | 0.5563 | 4.0760 | 4919864 | 612332 |
| gbt_av | high | 0.5541 | 3.8115 | 1229966 | 153083 |
| gbt_av | low | 0.5389 | 3.8555 | 1229966 | 153083 |

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
| full_ols_av | pooled | 2.2980 | 2.2128 | 2.3852 | 1.0000 | 1.0000 | -4.3760 | 1 |
| selected_two_stage_av | pooled | 1.9540 | 1.8624 | 2.0478 | 1.0000 | 0.9960 | -5.0480 | 2 |
| gbt_av | pooled | 1.9390 | 1.8326 | 2.0434 | 0.9954 | 0.9739 | -8.1089 | 3 |
| modeloespecifico | pooled | 1.6044 | 1.4888 | 1.7198 | 1.0000 | 0.9468 | -11.1520 | 4 |


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
| modeloespecifico | modeloespecifico | bid_type:regular | -0.1724 | -0.3716 | 0.0256 | 0.4204 | 2500 |
| modeloespecifico | selected_two_stage_av | pooled | 0.0940 | -0.1084 | 0.2992 | 0.4340 | 2500 |
| modeloespecifico | selected_two_stage_av | suit | 0.0686 | -0.1453 | 0.2741 | 0.4291 | 2375 |
| modeloespecifico | selected_two_stage_av | high | -0.0377 | -1.6226 | 1.5283 | 0.5094 | 53 |
| modeloespecifico | selected_two_stage_av | low | 1.0278 | -0.3472 | 2.3611 | 0.5417 | 72 |
| modeloespecifico | selected_two_stage_av | bid_type:regular | 0.0940 | -0.1084 | 0.2992 | 0.4340 | 2500 |

*Full table omitted from markdown — see `tables/h2h_delta_matrix.csv`*


</details>


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | pass_rate | make_rate | cvar_5 | net_cvar_5 | mix_suit | mix_high | mix_low | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 1.6044 | 5.5928 | 1.0000 | 0.0000 | 0.9468 | -4.6120 | -11.1520 | 0.9400 | 0.0280 | 0.0320 | comparator |
| selected_two_stage_av | 1.9540 | 5.9654 | 1.0000 | 0.0000 | 0.9960 | 2.2440 | -5.0480 | 0.9692 | 0.0128 | 0.0180 | comparator |
| gbt_av | 1.9390 | 5.8238 | 0.9954 | 0.0046 | 0.9739 | -1.5282 | -8.1089 | 0.7308 | 0.1036 | 0.1656 | comparator |
| full_ols_av | 2.2980 | 6.1490 | 1.0000 | 0.0000 | 1.0000 | 2.8120 | -4.3760 | 0.7244 | 0.0916 | 0.1840 | comparator |
| modeloespecifico | 4.6906 |  | 0.4880 | 0.5120 | 0.9287 | -3.2600 |  | 0.9400 | 0.0280 | 0.0320 | h2h_self_play |
| selected_two_stage_av | 4.5978 |  | 0.5012 | 0.4988 | 0.9130 | -4.5880 |  | 0.9692 | 0.0128 | 0.0180 | h2h_self_play |
| gbt_av | 4.5882 |  | 0.5092 | 0.4908 | 0.9144 | -4.6480 |  | 0.7308 | 0.1036 | 0.1656 | h2h_self_play |
| constrained_ols_av | 4.9456 |  | 0.5028 | 0.4972 | 0.9841 | 0.3120 |  | 0.7748 | 0.0552 | 0.1700 | h2h_self_play |
| selected_ols_av | 4.9516 |  | 0.4988 | 0.5012 | 0.9832 | 0.3600 |  | 0.7680 | 0.0884 | 0.1436 | h2h_self_play |
| full_ols_av | 4.9574 |  | 0.4968 | 0.5032 | 0.9903 | 0.4880 |  | 0.7244 | 0.0916 | 0.1840 | h2h_self_play |

*Full table omitted from markdown — see `tables/behavior_summary.csv`*


### Behavior by Contract

| model | contract | net_eppd | bid_rate | pass_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 1.6044 | 1.0000 | 0.0000 | 0.9468 | comparator |
| selected_two_stage_av | pooled | 1.9540 | 1.0000 | 0.0000 | 0.9960 | comparator |
| gbt_av | pooled | 1.9390 | 0.9954 | 0.0046 | 0.9739 | comparator |
| full_ols_av | pooled | 2.2980 | 1.0000 | 0.0000 | 1.0000 | comparator |


### Chart 12. Bid and Make Rates

![Bid and Make Rates](charts/full_chart_suite/bid_behavior_panel.png)

### Chart 11. Contract Mix

![Contract Mix](charts/full_chart_suite/contract_mix_bars.png)


## 9. Sanity Bounds

| model | check_name | value | lower_bound | upper_bound | status |
| --- | --- | --- | --- | --- | --- |
| modeloespecifico | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| modeloespecifico | make_rate_range | 0.9468 | 0.1000 | 1.0000 | PASS |
| selected_two_stage_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_two_stage_av | make_rate_range | 0.9960 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 0.9954 | 0.0500 | 0.9500 | FAIL |
| gbt_av | make_rate_range | 0.9739 | 0.1000 | 1.0000 | PASS |
| full_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| full_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_suit | 0.5706 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_high | 0.4910 | 0.0000 | 1.0000 | PASS |

*Full table omitted from markdown — see `tables/sanity_bounds_check.csv`*


## 10. Data Quality Notes

- **Outcome distributions (Chart 9):** synthetic data — parquet-backed real distributions unavailable for this bundle
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.
- **Sanity: unknown** — failed. This may be expected for small sample sizes or early rungs.

<!-- gate_status: data sanity checks in §1 above -->
