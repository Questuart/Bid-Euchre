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
| r2_positive_constrained_ols_av_high | training | 0.3233 | 0.0000 | PASS | constrained_ols_av high R²=0.3233 |
| r2_positive_constrained_ols_av_low | training | 0.3244 | 0.0000 | PASS | constrained_ols_av low R²=0.3244 |
| r2_positive_constrained_ols_av_pass | training | 0.0058 | 0.0000 | PASS | constrained_ols_av pass R²=0.0058 |
| r2_positive_constrained_ols_av_suit | training | 0.5566 | 0.0000 | PASS | constrained_ols_av suit R²=0.5566 |
| r2_positive_full_ols_av_high | training | 0.3927 | 0.0000 | PASS | full_ols_av high R²=0.3927 |
| r2_positive_full_ols_av_low | training | 0.3934 | 0.0000 | PASS | full_ols_av low R²=0.3934 |
| r2_positive_full_ols_av_pass | training | 0.0224 | 0.0000 | PASS | full_ols_av pass R²=0.0224 |

*Full table omitted from markdown — see `tables/data_sanity.csv`*


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | high | 0.3233 | 4.6798 | 70104 | 8632 |
| constrained_ols_av | low | 0.3244 | 4.8255 | 70104 | 8632 |
| constrained_ols_av | pass | 0.0058 | 3.0882 | 8000 | 1000 |
| constrained_ols_av | suit | 0.5566 | 4.0877 | 280416 | 34528 |
| full_ols_av | high | 0.3927 | 4.3439 | 70104 | 8632 |
| full_ols_av | low | 0.3934 | 4.5288 | 70104 | 8632 |
| full_ols_av | pass | 0.0224 | 3.1345 | 8000 | 1000 |
| full_ols_av | suit | 0.5689 | 4.0247 | 280416 | 34528 |
| gbt_av | high | 0.4763 | 3.5679 | 70104 | 8632 |
| gbt_av | low | 0.4588 | 3.7535 | 70104 | 8632 |

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
| gbt_av | pooled | 2.1136 | 1.9932 | 2.2336 | 0.8520 | 0.9953 | -4.4528 | 1 |
| full_ols_av | pooled | 1.9720 | 1.8512 | 2.0920 | 0.9716 | 1.0000 | -4.4793 | 2 |
| constrained_ols_av | pooled | 1.8152 | 1.6904 | 1.9416 | 1.0000 | 1.0000 | -4.6880 | 3 |
| selected_two_stage_av | pooled | 1.7724 | 1.6452 | 1.8988 | 0.9256 | 0.9892 | -5.7130 | 4 |
| modeloespecifico | pooled | 1.6608 | 1.5008 | 1.8188 | 1.0000 | 0.9496 | -11.1120 | 5 |
| selected_ols_av | pooled | 1.4908 | 1.3604 | 1.6244 | 1.0000 | 0.9996 | -5.2560 | 6 |
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
| modeloespecifico | selected_two_stage_av | pooled | 0.9748 | 0.7896 | 1.1616 | 0.5716 | 2500 |
| modeloespecifico | selected_two_stage_av | suit | 0.9174 | 0.7147 | 1.1166 | 0.5658 | 2324 |
| modeloespecifico | selected_two_stage_av | high | 1.2857 | -0.1000 | 2.6286 | 0.6857 | 70 |
| modeloespecifico | selected_two_stage_av | low | 2.0283 | 1.0660 | 2.9245 | 0.6226 | 106 |
| selected_two_stage_av | modeloespecifico | pooled | -1.2060 | -1.3872 | -1.0176 | 0.2600 | 2500 |
| selected_two_stage_av | modeloespecifico | suit | -1.0890 | -1.2817 | -0.8968 | 0.2675 | 2325 |

*Full table omitted from markdown — see `tables/h2h_delta_matrix.csv`*


</details>


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | pass_rate | make_rate | cvar_5 | net_cvar_5 | mix_suit | mix_high | mix_low | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 1.6608 | 5.6320 | 1.0000 | 0.0000 | 0.9496 | -4.5120 | -11.1120 | 0.9400 | 0.0280 | 0.0320 | comparator |
| selected_two_stage_av | 1.7724 | 5.4876 | 0.9256 | 0.0744 | 0.9892 | 1.5652 | -5.7130 | 0.9740 | 0.0068 | 0.0192 | comparator |
| gbt_av | 2.1136 | 5.3012 | 0.8520 | 0.1480 | 0.9953 | 2.4057 | -4.4528 | 0.7740 | 0.0912 | 0.1348 | comparator |
| constrained_ols_av | 1.8152 | 5.9076 | 1.0000 | 0.0000 | 1.0000 | 2.6560 | -4.6880 | 0.9388 | 0.0164 | 0.0448 | comparator |
| selected_ols_av | 1.4908 | 5.7452 | 1.0000 | 0.0000 | 0.9996 | 2.3680 | -5.2560 | 0.9636 | 0.0160 | 0.0204 | comparator |
| full_ols_av | 1.9720 | 5.8440 | 0.9716 | 0.0284 | 1.0000 | 2.7603 | -4.4793 | 0.9624 | 0.0232 | 0.0144 | comparator |
| stricthellraiser | 0.1096 | 4.9284 | 1.0000 | 0.0000 | 0.9472 | -3.0000 | -11.2240 | 1.0000 | 0.0000 | 0.0000 | comparator |
| rankthetank | -9.6972 | -5.5808 | 1.0000 | 0.0000 | 0.1476 | -9.2480 | -15.0400 | 1.0000 | 0.0000 | 0.0000 | comparator |
| modeloespecifico | 4.6906 |  | 0.4880 | 0.5120 | 0.9287 | -3.2600 |  | 0.9400 | 0.0280 | 0.0320 | h2h_self_play |
| selected_two_stage_av | 4.7558 |  | 0.4936 | 0.5064 | 0.9384 | -2.5760 |  | 0.9740 | 0.0068 | 0.0192 | h2h_self_play |

*Full table omitted from markdown — see `tables/behavior_summary.csv`*


### Behavior by Contract

| model | contract | net_eppd | bid_rate | pass_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 1.6608 | 1.0000 | 0.0000 | 0.9496 | comparator |
| selected_two_stage_av | pooled | 1.7724 | 0.9256 | 0.0744 | 0.9892 | comparator |
| gbt_av | pooled | 2.1136 | 0.8520 | 0.1480 | 0.9953 | comparator |
| constrained_ols_av | pooled | 1.8152 | 1.0000 | 0.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 1.4908 | 1.0000 | 0.0000 | 0.9996 | comparator |
| full_ols_av | pooled | 1.9720 | 0.9716 | 0.0284 | 1.0000 | comparator |
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
| selected_two_stage_av | bid_rate_range | 0.9256 | 0.0500 | 0.9500 | PASS |
| selected_two_stage_av | make_rate_range | 0.9892 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 0.8520 | 0.0500 | 0.9500 | PASS |
| gbt_av | make_rate_range | 0.9953 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| constrained_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| selected_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_ols_av | make_rate_range | 0.9996 | 0.1000 | 1.0000 | PASS |

*Full table omitted from markdown — see `tables/sanity_bounds_check.csv`*


## Gate Status

gate_status: See `hypothesis_outcomes` table above and `evidence_manifest.json` for machine-readable gate evidence.
