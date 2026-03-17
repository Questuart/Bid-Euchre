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
| r2_positive_constrained_ols_av_high | training | 0.8556 | 0.0000 | PASS | constrained_ols_av high R²=0.8556 |
| r2_positive_constrained_ols_av_low | training | 0.8607 | 0.0000 | PASS | constrained_ols_av low R²=0.8607 |
| r2_positive_constrained_ols_av_pass | training | 0.0027 | 0.0000 | PASS | constrained_ols_av pass R²=0.0027 |
| r2_positive_constrained_ols_av_suit | training | 0.8860 | 0.0000 | PASS | constrained_ols_av suit R²=0.8860 |
| r2_positive_full_ols_av_high | training | 0.8567 | 0.0000 | PASS | full_ols_av high R²=0.8567 |
| r2_positive_full_ols_av_low | training | 0.8646 | 0.0000 | PASS | full_ols_av low R²=0.8646 |
| r2_positive_full_ols_av_pass | training | 0.0235 | 0.0000 | PASS | full_ols_av pass R²=0.0235 |

*Full table omitted from markdown — see `tables/data_sanity.csv`*


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | high | 0.8556 | 3.6967 | 76937 | 9737 |
| constrained_ols_av | low | 0.8607 | 3.7520 | 76937 | 9737 |
| constrained_ols_av | pass | 0.0027 | 3.5477 | 8000 | 1000 |
| constrained_ols_av | suit | 0.8860 | 3.4919 | 307748 | 38948 |
| full_ols_av | high | 0.8567 | 3.6800 | 76937 | 9737 |
| full_ols_av | low | 0.8646 | 3.7047 | 76937 | 9737 |
| full_ols_av | pass | 0.0235 | 3.3015 | 8000 | 1000 |
| full_ols_av | suit | 0.8897 | 3.4599 | 307748 | 38948 |
| gbt_av | high | 0.8633 | 3.4129 | 76937 | 9737 |
| gbt_av | low | 0.8730 | 3.3928 | 76937 | 9737 |

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
| gbt_av | pooled | 2.3048 | 2.1668 | 2.4424 | 0.9276 | 0.9940 | -5.1478 | 1 |
| full_ols_av | pooled | 2.2496 | 2.1256 | 2.3728 | 1.0000 | 1.0000 | -4.4960 | 2 |
| constrained_ols_av | pooled | 2.1664 | 2.0448 | 2.2944 | 1.0000 | 1.0000 | -4.5120 | 3 |
| selected_ols_av | pooled | 2.0832 | 1.9576 | 2.2112 | 1.0000 | 1.0000 | -4.5600 | 4 |
| selected_two_stage_av | pooled | 1.8676 | 1.7328 | 1.9988 | 1.0000 | 0.9944 | -5.2880 | 5 |
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
| modeloespecifico | modeloespecifico | bid_type:regular | -0.1724 | -0.3716 | 0.0256 | 0.4204 | 2500 |
| modeloespecifico | selected_two_stage_av | pooled | 0.2856 | 0.0724 | 0.5044 | 0.4380 | 2500 |
| modeloespecifico | selected_two_stage_av | suit | 0.2343 | 0.0149 | 0.4537 | 0.4307 | 2352 |
| modeloespecifico | selected_two_stage_av | high | 1.1458 | -0.6042 | 2.8125 | 0.6667 | 48 |
| modeloespecifico | selected_two_stage_av | low | 1.0800 | 0.0297 | 2.1100 | 0.5000 | 100 |
| modeloespecifico | selected_two_stage_av | bid_type:regular | 0.2856 | 0.0724 | 0.5044 | 0.4380 | 2500 |

*Full table omitted from markdown — see `tables/h2h_delta_matrix.csv`*


</details>


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | pass_rate | make_rate | cvar_5 | net_cvar_5 | mix_suit | mix_high | mix_low | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 1.6608 | 5.6320 | 1.0000 | 0.0000 | 0.9496 | -4.5120 | -11.1120 | 0.9400 | 0.0280 | 0.0320 | comparator |
| selected_two_stage_av | 1.8676 | 5.9184 | 1.0000 | 0.0000 | 0.9944 | 2.0480 | -5.2880 | 0.9704 | 0.0068 | 0.0228 | comparator |
| gbt_av | 2.3048 | 5.7972 | 0.9276 | 0.0724 | 0.9940 | 2.0087 | -5.1478 | 0.7008 | 0.0844 | 0.2148 | comparator |
| constrained_ols_av | 2.1664 | 6.0832 | 1.0000 | 0.0000 | 1.0000 | 2.7440 | -4.5120 | 0.7524 | 0.0656 | 0.1820 | comparator |
| selected_ols_av | 2.0832 | 6.0416 | 1.0000 | 0.0000 | 1.0000 | 2.7200 | -4.5600 | 0.7432 | 0.0872 | 0.1696 | comparator |
| full_ols_av | 2.2496 | 6.1248 | 1.0000 | 0.0000 | 1.0000 | 2.7520 | -4.4960 | 0.2904 | 0.1812 | 0.5284 | comparator |
| stricthellraiser | 0.1096 | 4.9284 | 1.0000 | 0.0000 | 0.9472 | -3.0000 | -11.2240 | 1.0000 | 0.0000 | 0.0000 | comparator |
| rankthetank | -9.6972 | -5.5808 | 1.0000 | 0.0000 | 0.1476 | -9.2480 | -15.0400 | 1.0000 | 0.0000 | 0.0000 | comparator |
| modeloespecifico | 4.6906 |  | 0.4880 | 0.5120 | 0.9287 | -3.2600 |  | 0.9400 | 0.0280 | 0.0320 | h2h_self_play |
| selected_two_stage_av | 4.5946 |  | 0.4892 | 0.5108 | 0.9068 | -4.7160 |  | 0.9704 | 0.0068 | 0.0228 | h2h_self_play |

*Full table omitted from markdown — see `tables/behavior_summary.csv`*


### Behavior by Contract

| model | contract | net_eppd | bid_rate | pass_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 1.6608 | 1.0000 | 0.0000 | 0.9496 | comparator |
| selected_two_stage_av | pooled | 1.8676 | 1.0000 | 0.0000 | 0.9944 | comparator |
| gbt_av | pooled | 2.3048 | 0.9276 | 0.0724 | 0.9940 | comparator |
| constrained_ols_av | pooled | 2.1664 | 1.0000 | 0.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 2.0832 | 1.0000 | 0.0000 | 1.0000 | comparator |
| full_ols_av | pooled | 2.2496 | 1.0000 | 0.0000 | 1.0000 | comparator |
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
| selected_two_stage_av | make_rate_range | 0.9944 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 0.9276 | 0.0500 | 0.9500 | PASS |
| gbt_av | make_rate_range | 0.9940 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| constrained_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| selected_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |

*Full table omitted from markdown — see `tables/sanity_bounds_check.csv`*


## Gate Status

gate_status: See `hypothesis_outcomes` table above and `evidence_manifest.json` for machine-readable gate evidence.
