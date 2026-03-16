# Rung Results Report

Generated from canonical CSV tables and chart PNGs.

## Dashboards

### Competitive Dashboard

![Competitive Dashboard](charts/dashboard_competitive.png)

### Health Dashboard

![Health Dashboard](charts/dashboard_health.png)

### Model Evaluation Dashboard

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
| r2_positive_full_ols_av_suit | training | 0.8897 | 0.0000 | PASS | full_ols_av suit R²=0.8897 |
| r2_positive_gbt_av_high | training | 0.8633 | 0.0000 | PASS | gbt_av high R²=0.8633 |
| r2_positive_gbt_av_low | training | 0.8730 | 0.0000 | PASS | gbt_av low R²=0.8730 |
| r2_positive_gbt_av_pass | training | 0.0257 | 0.0000 | PASS | gbt_av pass R²=0.0257 |
| r2_positive_gbt_av_suit | training | 0.8986 | 0.0000 | PASS | gbt_av suit R²=0.8986 |
| r2_positive_selected_ols_av_high | training | 0.8556 | 0.0000 | PASS | selected_ols_av high R²=0.8556 |
| r2_positive_selected_ols_av_low | training | 0.8606 | 0.0000 | PASS | selected_ols_av low R²=0.8606 |
| r2_positive_selected_ols_av_pass | training | 0.0154 | 0.0000 | PASS | selected_ols_av pass R²=0.0154 |
| r2_positive_selected_ols_av_suit | training | 0.8842 | 0.0000 | PASS | selected_ols_av suit R²=0.8842 |
| r2_positive_selected_two_stage_av_high | training | 0.8556 | 0.0000 | PASS | selected_two_stage_av high R²=0.8556 |
| r2_positive_selected_two_stage_av_low | training | 0.8606 | 0.0000 | PASS | selected_two_stage_av low R²=0.8606 |
| r2_positive_selected_two_stage_av_pass | training | 0.0154 | 0.0000 | PASS | selected_two_stage_av pass R²=0.0154 |
| r2_positive_selected_two_stage_av_suit | training | 0.0000 | 0.0000 | WARN | selected_two_stage_av suit R²=0.0000 |


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
| gbt_av | pass | 0.0257 | 3.3002 | 8000 | 1000 |
| gbt_av | suit | 0.8986 | 3.0400 | 307748 | 38948 |
| selected_ols_av | high | 0.8556 | 3.6956 | 76937 | 9737 |
| selected_ols_av | low | 0.8606 | 3.7532 | 76937 | 9737 |
| selected_ols_av | pass | 0.0154 | 3.3357 | 8000 | 1000 |
| selected_ols_av | suit | 0.8842 | 3.5284 | 307748 | 38948 |
| selected_two_stage_av | high | 0.8556 | 3.6956 | 76937 | 9737 |
| selected_two_stage_av | low | 0.8606 | 3.7532 | 76937 | 9737 |
| selected_two_stage_av | pass | 0.0154 | 3.3357 | 8000 | 1000 |
| selected_two_stage_av | suit |  |  | 307748 | 38948 |


![r2_by_contract.png](charts/r2_by_contract.png)

![mae_by_contract.png](charts/mae_by_contract.png)


## 3. Offline Diagnostics

> [chart_name=pred_vs_actual.png] not yet generated

> [chart_name=residual_distribution.png] not yet generated

> [chart_name=calibration_curve.png] not yet generated


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


![comparator_ranking_bars.png](charts/comparator_ranking_bars.png)

![tail_risk_panel.png](charts/tail_risk_panel.png)


## 7. H2H Battery

| model_a | model_b | facet | net_eppd_delta | ci_low | ci_high | win_rate_a | deals_total |
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
| selected_two_stage_av | modeloespecifico | pooled | -0.6264 | -0.8308 | -0.4172 | 0.4144 | 2500 |
| selected_two_stage_av | modeloespecifico | suit | -0.5583 | -0.7732 | -0.3404 | 0.4223 | 2368 |
| selected_two_stage_av | modeloespecifico | high | -3.4894 | -4.6383 | -2.2979 | 0.1489 | 47 |
| selected_two_stage_av | modeloespecifico | low | -0.9412 | -2.0118 | 0.1176 | 0.3412 | 85 |
| selected_two_stage_av | modeloespecifico | bid_type:regular | -0.6264 | -0.8308 | -0.4172 | 0.4144 | 2500 |
| modeloespecifico | gbt_av | pooled | -1.0384 | -1.2728 | -0.8024 | 0.3156 | 2500 |
| modeloespecifico | gbt_av | suit | -0.7866 | -1.0344 | -0.5414 | 0.3509 | 1921 |
| modeloespecifico | gbt_av | high | -2.3058 | -3.3786 | -1.2379 | 0.1893 | 206 |
| modeloespecifico | gbt_av | low | -1.6354 | -2.4021 | -0.8712 | 0.2038 | 373 |
| modeloespecifico | gbt_av | bid_type:regular | -0.9521 | -1.1695 | -0.7278 | 0.3156 | 2484 |
| modeloespecifico | gbt_av | bid_type:moon | 0.9000 | -11.7000 | 13.5000 | 0.5000 | 10 |
| modeloespecifico | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 6 |
| gbt_av | modeloespecifico | pooled | 0.6716 | 0.4336 | 0.9148 | 0.5564 | 2500 |
| gbt_av | modeloespecifico | suit | 0.4097 | 0.1558 | 0.6568 | 0.5187 | 1926 |
| gbt_av | modeloespecifico | high | 1.2908 | 0.0612 | 2.4745 | 0.6684 | 196 |
| gbt_av | modeloespecifico | low | 1.6852 | 0.8968 | 2.4868 | 0.6905 | 378 |
| gbt_av | modeloespecifico | bid_type:regular | 0.5924 | 0.3710 | 0.8185 | 0.5557 | 2485 |
| gbt_av | modeloespecifico | bid_type:moon | -4.1429 | -17.0000 | 13.7143 | 0.4286 | 7 |
| gbt_av | modeloespecifico | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| modeloespecifico | constrained_ols_av | pooled | 1.1732 | 0.9900 | 1.3556 | 0.6192 | 2500 |
| modeloespecifico | constrained_ols_av | suit | 1.2510 | 1.0519 | 1.4451 | 0.6312 | 2215 |
| modeloespecifico | constrained_ols_av | high | 0.0879 | -1.0879 | 1.2527 | 0.5495 | 91 |
| modeloespecifico | constrained_ols_av | low | 0.7938 | 0.0876 | 1.4897 | 0.5155 | 194 |
| modeloespecifico | constrained_ols_av | bid_type:regular | 1.1732 | 0.9900 | 1.3556 | 0.6192 | 2500 |
| constrained_ols_av | modeloespecifico | pooled | -1.4124 | -1.5876 | -1.2312 | 0.2124 | 2500 |
| constrained_ols_av | modeloespecifico | suit | -1.4260 | -1.6187 | -1.2307 | 0.2012 | 2237 |
| constrained_ols_av | modeloespecifico | high | -1.8052 | -3.0133 | -0.6231 | 0.2987 | 77 |
| constrained_ols_av | modeloespecifico | low | -1.0860 | -1.8226 | -0.3495 | 0.3118 | 186 |
| constrained_ols_av | modeloespecifico | bid_type:regular | -1.4124 | -1.5876 | -1.2312 | 0.2124 | 2500 |
| modeloespecifico | selected_ols_av | pooled | 1.1156 | 0.9280 | 1.3048 | 0.6008 | 2500 |
| modeloespecifico | selected_ols_av | suit | 1.2311 | 1.0243 | 1.4235 | 0.6192 | 2177 |
| modeloespecifico | selected_ols_av | high | -0.4348 | -1.5217 | 0.6174 | 0.4696 | 115 |
| modeloespecifico | selected_ols_av | low | 0.7644 | 0.0817 | 1.4471 | 0.4808 | 208 |
| modeloespecifico | selected_ols_av | bid_type:regular | 1.1156 | 0.9280 | 1.3048 | 0.6008 | 2500 |
| selected_ols_av | modeloespecifico | pooled | -1.4548 | -1.6304 | -1.2708 | 0.2224 | 2500 |
| selected_ols_av | modeloespecifico | suit | -1.4980 | -1.6865 | -1.3094 | 0.2067 | 2201 |
| selected_ols_av | modeloespecifico | high | -1.1456 | -2.1845 | -0.0874 | 0.3592 | 103 |
| selected_ols_av | modeloespecifico | low | -1.1327 | -1.8265 | -0.4388 | 0.3265 | 196 |
| selected_ols_av | modeloespecifico | bid_type:regular | -1.4548 | -1.6304 | -1.2708 | 0.2224 | 2500 |
| modeloespecifico | full_ols_av | pooled | 1.0696 | 0.8836 | 1.2576 | 0.5940 | 2500 |
| modeloespecifico | full_ols_av | suit | 1.1872 | 0.9878 | 1.3796 | 0.6204 | 2131 |
| modeloespecifico | full_ols_av | high | -0.1982 | -1.2793 | 0.8829 | 0.4685 | 111 |
| modeloespecifico | full_ols_av | low | 0.6434 | -0.0078 | 1.3023 | 0.4302 | 258 |
| modeloespecifico | full_ols_av | bid_type:regular | 1.0696 | 0.8836 | 1.2576 | 0.5940 | 2500 |
| full_ols_av | modeloespecifico | pooled | -1.1860 | -1.3680 | -0.9992 | 0.2444 | 2500 |
| full_ols_av | modeloespecifico | suit | -1.2823 | -1.4788 | -1.0863 | 0.2175 | 2143 |
| full_ols_av | modeloespecifico | high | -1.4536 | -2.5155 | -0.3608 | 0.3093 | 97 |
| full_ols_av | modeloespecifico | low | -0.2923 | -0.9346 | 0.3462 | 0.4423 | 260 |
| full_ols_av | modeloespecifico | bid_type:regular | -1.1860 | -1.3680 | -0.9992 | 0.2444 | 2500 |
| modeloespecifico | stricthellraiser | pooled | 4.5912 | 4.2820 | 4.9000 | 0.5348 | 2500 |
| modeloespecifico | stricthellraiser | suit | 4.5897 | 4.2772 | 4.8901 | 0.5335 | 2493 |
| modeloespecifico | stricthellraiser | high | 6.0000 | 2.0000 | 10.0000 | 1.0000 | 3 |
| modeloespecifico | stricthellraiser | low | 4.5000 | 3.0000 | 6.0000 | 1.0000 | 4 |
| modeloespecifico | stricthellraiser | bid_type:regular | 4.5912 | 4.2820 | 4.9000 | 0.5348 | 2500 |
| stricthellraiser | modeloespecifico | pooled | -5.2608 | -5.5596 | -4.9592 | 0.3436 | 2500 |
| stricthellraiser | modeloespecifico | suit | -5.2651 | -5.5716 | -4.9639 | 0.3446 | 2493 |
| stricthellraiser | modeloespecifico | high | -3.0000 | -4.0000 | -2.0000 | 0.0000 | 2 |
| stricthellraiser | modeloespecifico | low | -4.0000 | -7.2000 | -0.8000 | 0.0000 | 5 |
| stricthellraiser | modeloespecifico | bid_type:regular | -5.2608 | -5.5596 | -4.9592 | 0.3436 | 2500 |
| modeloespecifico | rankthetank | pooled | 10.4808 | 10.2456 | 10.7100 | 0.8996 | 2500 |
| modeloespecifico | rankthetank | suit | 10.4808 | 10.2456 | 10.7100 | 0.8996 | 2500 |
| modeloespecifico | rankthetank | bid_type:regular | 10.4808 | 10.2456 | 10.7100 | 0.8996 | 2500 |
| rankthetank | modeloespecifico | pooled | -10.5044 | -10.7368 | -10.2652 | 0.1024 | 2500 |
| rankthetank | modeloespecifico | suit | -10.5044 | -10.7368 | -10.2652 | 0.1024 | 2500 |
| rankthetank | modeloespecifico | bid_type:regular | -10.5044 | -10.7368 | -10.2652 | 0.1024 | 2500 |
| modeloespecifico | anchor_hybrid_r0_full | pooled | 0.2320 | 0.0248 | 0.4452 | 0.4548 | 2500 |
| modeloespecifico | anchor_hybrid_r0_full | suit | 0.3443 | 0.1282 | 0.5646 | 0.4735 | 2129 |
| modeloespecifico | anchor_hybrid_r0_full | high | -0.4150 | -1.4694 | 0.6735 | 0.3605 | 147 |
| modeloespecifico | anchor_hybrid_r0_full | low | -0.4107 | -1.2366 | 0.4421 | 0.3393 | 224 |
| modeloespecifico | anchor_hybrid_r0_full | bid_type:regular | 0.2320 | 0.0248 | 0.4452 | 0.4548 | 2500 |
| anchor_hybrid_r0_full | modeloespecifico | pooled | -0.5584 | -0.7636 | -0.3456 | 0.3988 | 2500 |
| anchor_hybrid_r0_full | modeloespecifico | suit | -0.6416 | -0.8642 | -0.4214 | 0.3751 | 2157 |
| anchor_hybrid_r0_full | modeloespecifico | high | -0.1857 | -1.2643 | 0.8357 | 0.5214 | 140 |
| anchor_hybrid_r0_full | modeloespecifico | low | 0.0690 | -0.7931 | 0.9458 | 0.5665 | 203 |
| anchor_hybrid_r0_full | modeloespecifico | bid_type:regular | -0.5584 | -0.7636 | -0.3456 | 0.3988 | 2500 |
| selected_two_stage_av | selected_two_stage_av | pooled | -0.0260 | -0.2312 | 0.1784 | 0.4188 | 2500 |
| selected_two_stage_av | selected_two_stage_av | suit | -0.0379 | -0.2486 | 0.1711 | 0.4176 | 2426 |
| selected_two_stage_av | selected_two_stage_av | high | 0.7647 | -2.2941 | 3.8235 | 0.4706 | 17 |
| selected_two_stage_av | selected_two_stage_av | low | 0.2456 | -1.1930 | 1.7018 | 0.4561 | 57 |
| selected_two_stage_av | selected_two_stage_av | bid_type:regular | -0.0260 | -0.2312 | 0.1784 | 0.4188 | 2500 |
| selected_two_stage_av | gbt_av | pooled | -1.3928 | -1.6144 | -1.1644 | 0.2808 | 2500 |
| selected_two_stage_av | gbt_av | suit | -1.2119 | -1.4419 | -0.9825 | 0.3014 | 1944 |
| selected_two_stage_av | gbt_av | high | -2.7764 | -3.9753 | -1.6149 | 0.1739 | 161 |
| selected_two_stage_av | gbt_av | low | -1.7190 | -2.4228 | -1.0000 | 0.2228 | 395 |
| selected_two_stage_av | gbt_av | bid_type:regular | -1.2990 | -1.5071 | -1.0897 | 0.2809 | 2485 |
| selected_two_stage_av | gbt_av | bid_type:moon | -1.5556 | -15.3333 | 12.3333 | 0.4444 | 9 |
| selected_two_stage_av | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 6 |
| gbt_av | selected_two_stage_av | pooled | 1.1476 | 0.9148 | 1.3836 | 0.5792 | 2500 |
| gbt_av | selected_two_stage_av | suit | 0.9790 | 0.7479 | 1.2142 | 0.5475 | 1956 |
| gbt_av | selected_two_stage_av | high | 1.9375 | 0.5563 | 3.3002 | 0.7438 | 160 |
| gbt_av | selected_two_stage_av | low | 1.6771 | 0.9167 | 2.4505 | 0.6719 | 384 |
| gbt_av | selected_two_stage_av | bid_type:regular | 1.0813 | 0.8680 | 1.2951 | 0.5789 | 2484 |
| gbt_av | selected_two_stage_av | bid_type:moon | -6.6250 | -18.1250 | 9.3750 | 0.3750 | 8 |
| gbt_av | selected_two_stage_av | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| selected_two_stage_av | constrained_ols_av | pooled | 0.5060 | 0.3308 | 0.6788 | 0.5124 | 2500 |
| selected_two_stage_av | constrained_ols_av | suit | 0.6959 | 0.5127 | 0.8796 | 0.5390 | 2243 |
| selected_two_stage_av | constrained_ols_av | high | -1.8261 | -2.9710 | -0.6518 | 0.2464 | 69 |
| selected_two_stage_av | constrained_ols_av | low | -0.9043 | -1.5532 | -0.2766 | 0.2926 | 188 |
| selected_two_stage_av | constrained_ols_av | bid_type:regular | 0.5060 | 0.3308 | 0.6788 | 0.5124 | 2500 |
| constrained_ols_av | selected_two_stage_av | pooled | -0.6128 | -0.7900 | -0.4324 | 0.3184 | 2500 |
| constrained_ols_av | selected_two_stage_av | suit | -0.7852 | -0.9688 | -0.5999 | 0.2962 | 2272 |
| constrained_ols_av | selected_two_stage_av | high | 1.9701 | 0.7164 | 3.2388 | 0.6418 | 67 |
| constrained_ols_av | selected_two_stage_av | low | 0.7453 | 0.0248 | 1.4596 | 0.4969 | 161 |
| constrained_ols_av | selected_two_stage_av | bid_type:regular | -0.6128 | -0.7900 | -0.4324 | 0.3184 | 2500 |
| selected_two_stage_av | selected_ols_av | pooled | 0.7336 | 0.5560 | 0.9088 | 0.5344 | 2500 |
| selected_two_stage_av | selected_ols_av | suit | 0.9748 | 0.7874 | 1.1614 | 0.5667 | 2225 |
| selected_two_stage_av | selected_ols_av | high | -1.8019 | -2.6038 | -0.9434 | 0.2170 | 106 |
| selected_two_stage_av | selected_ols_av | low | -0.8521 | -1.4615 | -0.2426 | 0.3077 | 169 |
| selected_two_stage_av | selected_ols_av | bid_type:regular | 0.7336 | 0.5560 | 0.9088 | 0.5344 | 2500 |
| selected_ols_av | selected_two_stage_av | pooled | -0.8888 | -1.0692 | -0.7092 | 0.2928 | 2500 |
| selected_ols_av | selected_two_stage_av | suit | -1.0621 | -1.2452 | -0.8763 | 0.2694 | 2272 |
| selected_ols_av | selected_two_stage_av | high | 1.7590 | 0.7711 | 2.7470 | 0.6265 | 83 |
| selected_ols_av | selected_two_stage_av | low | 0.3103 | -0.4966 | 1.0828 | 0.4690 | 145 |
| selected_ols_av | selected_two_stage_av | bid_type:regular | -0.8888 | -1.0692 | -0.7092 | 0.2928 | 2500 |
| selected_two_stage_av | full_ols_av | pooled | 0.9088 | 0.7420 | 1.0756 | 0.5396 | 2500 |
| selected_two_stage_av | full_ols_av | suit | 1.3720 | 1.1882 | 1.5613 | 0.6014 | 1844 |
| selected_two_stage_av | full_ols_av | high | -0.4674 | -1.1033 | 0.1630 | 0.3859 | 184 |
| selected_two_stage_av | full_ols_av | low | -0.3644 | -0.7564 | 0.0403 | 0.3581 | 472 |
| selected_two_stage_av | full_ols_av | bid_type:regular | 0.9088 | 0.7420 | 1.0756 | 0.5396 | 2500 |
| full_ols_av | selected_two_stage_av | pooled | -0.9788 | -1.1512 | -0.8072 | 0.2800 | 2500 |
| full_ols_av | selected_two_stage_av | suit | -1.4218 | -1.6099 | -1.2316 | 0.2149 | 1861 |
| full_ols_av | selected_two_stage_av | high | 0.5632 | -0.0862 | 1.2241 | 0.4770 | 174 |
| full_ols_av | selected_two_stage_av | low | 0.2172 | -0.2215 | 0.6581 | 0.4667 | 465 |
| full_ols_av | selected_two_stage_av | bid_type:regular | -0.9788 | -1.1512 | -0.8072 | 0.2800 | 2500 |
| selected_two_stage_av | stricthellraiser | pooled | 2.5132 | 2.2376 | 2.7880 | 0.4164 | 2500 |
| selected_two_stage_av | stricthellraiser | suit | 2.5118 | 2.2365 | 2.7831 | 0.4162 | 2499 |
| selected_two_stage_av | stricthellraiser | low | 6.0000 | 6.0000 | 6.0000 | 1.0000 | 1 |
| selected_two_stage_av | stricthellraiser | bid_type:regular | 2.5132 | 2.2376 | 2.7880 | 0.4164 | 2500 |
| stricthellraiser | selected_two_stage_av | pooled | -2.9464 | -3.2232 | -2.6728 | 0.3972 | 2500 |
| stricthellraiser | selected_two_stage_av | suit | -2.9424 | -3.2226 | -2.6713 | 0.3975 | 2498 |
| stricthellraiser | selected_two_stage_av | low | -8.0000 | -10.0000 | -6.0000 | 0.0000 | 2 |
| stricthellraiser | selected_two_stage_av | bid_type:regular | -2.9464 | -3.2232 | -2.6728 | 0.3972 | 2500 |
| selected_two_stage_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_two_stage_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_two_stage_av | rankthetank | bid_type:regular | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | selected_two_stage_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_two_stage_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_two_stage_av | bid_type:regular | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| selected_two_stage_av | anchor_hybrid_r0_full | pooled | 0.0096 | -0.1884 | 0.2196 | 0.4008 | 2500 |
| selected_two_stage_av | anchor_hybrid_r0_full | suit | -0.1918 | -0.4320 | 0.0581 | 0.3818 | 1773 |
| selected_two_stage_av | anchor_hybrid_r0_full | high | 0.8952 | 0.3353 | 1.4611 | 0.5000 | 334 |
| selected_two_stage_av | anchor_hybrid_r0_full | low | 0.1654 | -0.3588 | 0.6921 | 0.4020 | 393 |
| selected_two_stage_av | anchor_hybrid_r0_full | bid_type:regular | 0.0096 | -0.1884 | 0.2196 | 0.4008 | 2500 |
| anchor_hybrid_r0_full | selected_two_stage_av | pooled | -0.3312 | -0.5328 | -0.1196 | 0.4528 | 2500 |
| anchor_hybrid_r0_full | selected_two_stage_av | suit | -0.1593 | -0.4106 | 0.0847 | 0.4762 | 1783 |
| anchor_hybrid_r0_full | selected_two_stage_av | high | -0.7532 | -1.3038 | -0.2025 | 0.3829 | 316 |
| anchor_hybrid_r0_full | selected_two_stage_av | low | -0.7631 | -1.2918 | -0.2519 | 0.4040 | 401 |
| anchor_hybrid_r0_full | selected_two_stage_av | bid_type:regular | -0.3312 | -0.5328 | -0.1196 | 0.4528 | 2500 |
| gbt_av | gbt_av | pooled | -0.1348 | -0.4048 | 0.1364 | 0.4420 | 2500 |
| gbt_av | gbt_av | suit | -0.1667 | -0.4349 | 0.0965 | 0.4338 | 1752 |
| gbt_av | gbt_av | high | -0.7156 | -2.1659 | 0.7110 | 0.4265 | 211 |
| gbt_av | gbt_av | low | 0.1974 | -0.5345 | 0.9107 | 0.4749 | 537 |
| gbt_av | gbt_av | bid_type:regular | -0.1277 | -0.3589 | 0.1022 | 0.4412 | 2466 |
| gbt_av | gbt_av | bid_type:moon | 1.1579 | -8.0000 | 10.2632 | 0.5263 | 19 |
| gbt_av | gbt_av | bid_type:loner | -2.9333 | -24.2667 | 18.4000 | 0.4667 | 15 |
| gbt_av | constrained_ols_av | pooled | 1.6660 | 1.4584 | 1.8676 | 0.6304 | 2500 |
| gbt_av | constrained_ols_av | suit | 1.4879 | 1.2838 | 1.6855 | 0.6247 | 1857 |
| gbt_av | constrained_ols_av | high | 2.0041 | 1.0702 | 2.8926 | 0.6860 | 242 |
| gbt_av | constrained_ols_av | low | 2.2868 | 1.6683 | 2.9451 | 0.6234 | 401 |
| gbt_av | constrained_ols_av | bid_type:regular | 1.5940 | 1.4096 | 1.7735 | 0.6302 | 2485 |
| gbt_av | constrained_ols_av | bid_type:moon | -4.5714 | -17.4286 | 13.7143 | 0.4286 | 7 |
| gbt_av | constrained_ols_av | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| constrained_ols_av | gbt_av | pooled | -1.8936 | -2.0940 | -1.6936 | 0.2048 | 2500 |
| constrained_ols_av | gbt_av | suit | -1.7130 | -1.9135 | -1.5114 | 0.2080 | 1885 |
| constrained_ols_av | gbt_av | high | -2.6197 | -3.5684 | -1.6795 | 0.1838 | 234 |
| constrained_ols_av | gbt_av | low | -2.3412 | -3.0000 | -1.7270 | 0.2021 | 381 |
| constrained_ols_av | gbt_av | bid_type:regular | -1.8074 | -1.9831 | -1.6257 | 0.2039 | 2482 |
| constrained_ols_av | gbt_av | bid_type:moon | 2.9091 | -8.7273 | 14.6364 | 0.5455 | 11 |
| constrained_ols_av | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 7 |
| gbt_av | selected_ols_av | pooled | 1.7420 | 1.5288 | 1.9512 | 0.6428 | 2500 |
| gbt_av | selected_ols_av | suit | 1.6227 | 1.4133 | 1.8333 | 0.6413 | 1829 |
| gbt_av | selected_ols_av | high | 1.9887 | 1.1132 | 2.8679 | 0.7019 | 265 |
| gbt_av | selected_ols_av | low | 2.1182 | 1.4877 | 2.7809 | 0.6108 | 406 |
| gbt_av | selected_ols_av | bid_type:regular | 1.6704 | 1.4829 | 1.8543 | 0.6427 | 2485 |
| gbt_av | selected_ols_av | bid_type:moon | -4.5714 | -17.4286 | 13.7143 | 0.4286 | 7 |
| gbt_av | selected_ols_av | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| selected_ols_av | gbt_av | pooled | -2.0600 | -2.2556 | -1.8612 | 0.1900 | 2500 |
| selected_ols_av | gbt_av | suit | -1.8937 | -2.0982 | -1.6896 | 0.1867 | 1843 |
| selected_ols_av | gbt_av | high | -2.6544 | -3.5038 | -1.8309 | 0.1985 | 272 |
| selected_ols_av | gbt_av | low | -2.4364 | -3.0935 | -1.8182 | 0.2000 | 385 |
| selected_ols_av | gbt_av | bid_type:regular | -1.9750 | -2.1507 | -1.7929 | 0.1890 | 2482 |
| selected_ols_av | gbt_av | bid_type:moon | 2.9091 | -8.7273 | 14.6364 | 0.5455 | 11 |
| selected_ols_av | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 7 |
| gbt_av | full_ols_av | pooled | 1.7980 | 1.5972 | 1.9996 | 0.6376 | 2500 |
| gbt_av | full_ols_av | suit | 1.9001 | 1.6951 | 2.1016 | 0.6610 | 1702 |
| gbt_av | full_ols_av | high | 2.0070 | 1.1818 | 2.7937 | 0.6748 | 286 |
| gbt_av | full_ols_av | low | 1.3418 | 0.7969 | 1.9161 | 0.5391 | 512 |
| gbt_av | full_ols_av | bid_type:regular | 1.7268 | 1.5517 | 1.9006 | 0.6374 | 2485 |
| gbt_av | full_ols_av | bid_type:moon | -4.5714 | -17.4286 | 13.7143 | 0.4286 | 7 |
| gbt_av | full_ols_av | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| full_ols_av | gbt_av | pooled | -2.1016 | -2.2936 | -1.9084 | 0.1920 | 2500 |
| full_ols_av | gbt_av | suit | -2.2266 | -2.4237 | -2.0252 | 0.1460 | 1664 |
| full_ols_av | gbt_av | high | -2.2812 | -3.0833 | -1.5139 | 0.2396 | 288 |
| full_ols_av | gbt_av | low | -1.6277 | -2.1405 | -1.1168 | 0.3066 | 548 |
| full_ols_av | gbt_av | bid_type:regular | -2.0072 | -2.1780 | -1.8385 | 0.1913 | 2483 |
| full_ols_av | gbt_av | bid_type:moon | 1.0000 | -11.8000 | 13.8000 | 0.5000 | 10 |
| full_ols_av | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 7 |
| gbt_av | stricthellraiser | pooled | 3.3184 | 2.9928 | 3.6384 | 0.5564 | 2500 |
| gbt_av | stricthellraiser | suit | 3.8173 | 3.4973 | 4.1397 | 0.5408 | 2184 |
| gbt_av | stricthellraiser | high | 0.6250 | -5.3133 | 6.5000 | 0.6875 | 32 |
| gbt_av | stricthellraiser | low | -0.2148 | -1.3029 | 0.8979 | 0.6620 | 284 |
| gbt_av | stricthellraiser | bid_type:regular | 3.2488 | 2.9404 | 3.5519 | 0.5556 | 2484 |
| gbt_av | stricthellraiser | bid_type:moon | -1.2500 | -16.6250 | 14.5000 | 0.5000 | 8 |
| gbt_av | stricthellraiser | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| stricthellraiser | gbt_av | pooled | -3.6772 | -3.9924 | -3.3552 | 0.3280 | 2500 |
| stricthellraiser | gbt_av | suit | -4.2357 | -4.5536 | -3.9127 | 0.3313 | 2164 |
| stricthellraiser | gbt_av | high | -2.1591 | -6.2500 | 1.9318 | 0.2273 | 44 |
| stricthellraiser | gbt_av | low | 0.2329 | -0.8082 | 1.2637 | 0.3185 | 292 |
| stricthellraiser | gbt_av | bid_type:regular | -3.6178 | -3.9235 | -3.3061 | 0.3278 | 2483 |
| stricthellraiser | gbt_av | bid_type:moon | 2.7273 | -8.7273 | 14.1818 | 0.5455 | 11 |
| stricthellraiser | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 6 |
| gbt_av | rankthetank | pooled | 10.3592 | 10.0980 | 10.6184 | 0.8924 | 2500 |
| gbt_av | rankthetank | suit | 10.4192 | 10.1783 | 10.6519 | 0.8972 | 2462 |
| gbt_av | rankthetank | high | 3.9412 | -7.2956 | 15.1176 | 0.5882 | 17 |
| gbt_av | rankthetank | low | 8.5238 | -0.2381 | 17.4762 | 0.5714 | 21 |
| gbt_av | rankthetank | bid_type:regular | 10.2779 | 10.0258 | 10.5211 | 0.8930 | 2476 |
| gbt_av | rankthetank | bid_type:moon | 11.6000 | 3.0000 | 20.0000 | 0.8000 | 15 |
| gbt_av | rankthetank | bid_type:loner | 30.6667 | 12.0000 | 40.0000 | 0.8889 | 9 |
| rankthetank | gbt_av | pooled | -10.3460 | -10.6004 | -10.0836 | 0.1100 | 2500 |
| rankthetank | gbt_av | suit | -10.4085 | -10.6573 | -10.1622 | 0.1053 | 2460 |
| rankthetank | gbt_av | high | -6.6364 | -14.5000 | 1.3182 | 0.3182 | 22 |
| rankthetank | gbt_av | low | -6.3333 | -16.1667 | 2.8889 | 0.5000 | 18 |
| rankthetank | gbt_av | bid_type:regular | -10.3164 | -10.5570 | -10.0665 | 0.1084 | 2481 |
| rankthetank | gbt_av | bid_type:moon | 0.8333 | -9.7500 | 11.5000 | 0.5000 | 12 |
| rankthetank | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 7 |
| gbt_av | anchor_hybrid_r0_full | pooled | 1.2156 | 0.9812 | 1.4584 | 0.5448 | 2500 |
| gbt_av | anchor_hybrid_r0_full | suit | 0.8639 | 0.6143 | 1.1087 | 0.5180 | 1859 |
| gbt_av | anchor_hybrid_r0_full | high | 1.8316 | 0.9439 | 2.7298 | 0.6070 | 285 |
| gbt_av | anchor_hybrid_r0_full | low | 2.5807 | 1.7846 | 3.3966 | 0.6402 | 353 |
| gbt_av | anchor_hybrid_r0_full | bid_type:regular | 1.1093 | 0.8887 | 1.3262 | 0.5440 | 2480 |
| gbt_av | anchor_hybrid_r0_full | bid_type:moon | 5.7778 | -8.4444 | 20.0000 | 0.6667 | 9 |
| gbt_av | anchor_hybrid_r0_full | bid_type:loner | 29.5000 | 8.5000 | 40.0000 | 0.8750 | 8 |
| anchor_hybrid_r0_full | gbt_av | pooled | -1.5164 | -1.7496 | -1.2840 | 0.3324 | 2500 |
| anchor_hybrid_r0_full | gbt_av | suit | -1.2408 | -1.4837 | -0.9958 | 0.3412 | 1902 |
| anchor_hybrid_r0_full | gbt_av | high | -2.2022 | -3.1192 | -1.3104 | 0.3213 | 277 |
| anchor_hybrid_r0_full | gbt_av | low | -2.6063 | -3.4190 | -1.8063 | 0.2952 | 315 |
| anchor_hybrid_r0_full | gbt_av | bid_type:regular | -1.4018 | -1.6111 | -1.1827 | 0.3340 | 2479 |
| anchor_hybrid_r0_full | gbt_av | bid_type:moon | -4.5000 | -14.8750 | 10.8750 | 0.3750 | 8 |
| anchor_hybrid_r0_full | gbt_av | bid_type:loner | -40.0000 | -40.0000 | -40.0000 | 0.0000 | 7 |
| constrained_ols_av | constrained_ols_av | pooled | -0.0348 | -0.1940 | 0.1292 | 0.4076 | 2500 |
| constrained_ols_av | constrained_ols_av | suit | -0.0149 | -0.1935 | 0.1654 | 0.4168 | 1881 |
| constrained_ols_av | constrained_ols_av | high | -0.1585 | -0.8293 | 0.5427 | 0.3780 | 164 |
| constrained_ols_av | constrained_ols_av | low | -0.0725 | -0.4637 | 0.3231 | 0.3802 | 455 |
| constrained_ols_av | constrained_ols_av | bid_type:regular | -0.0348 | -0.1940 | 0.1292 | 0.4076 | 2500 |
| constrained_ols_av | selected_ols_av | pooled | 0.1484 | -0.0152 | 0.3068 | 0.4316 | 2500 |
| constrained_ols_av | selected_ols_av | suit | 0.2438 | 0.0589 | 0.4266 | 0.4480 | 1866 |
| constrained_ols_av | selected_ols_av | high | 0.0591 | -0.6158 | 0.7094 | 0.4138 | 203 |
| constrained_ols_av | selected_ols_av | low | -0.2227 | -0.6381 | 0.1856 | 0.3689 | 431 |
| constrained_ols_av | selected_ols_av | bid_type:regular | 0.1484 | -0.0152 | 0.3068 | 0.4316 | 2500 |
| selected_ols_av | constrained_ols_av | pooled | -0.2628 | -0.4252 | -0.1004 | 0.3836 | 2500 |
| selected_ols_av | constrained_ols_av | suit | -0.2566 | -0.4437 | -0.0695 | 0.3903 | 1855 |
| selected_ols_av | constrained_ols_av | high | -0.5846 | -1.2104 | 0.0410 | 0.3538 | 195 |
| selected_ols_av | constrained_ols_av | low | -0.1489 | -0.5467 | 0.2556 | 0.3689 | 450 |
| selected_ols_av | constrained_ols_av | bid_type:regular | -0.2628 | -0.4252 | -0.1004 | 0.3836 | 2500 |
| constrained_ols_av | full_ols_av | pooled | 0.6416 | 0.4792 | 0.7952 | 0.4928 | 2500 |
| constrained_ols_av | full_ols_av | suit | 1.6105 | 1.4165 | 1.8038 | 0.6143 | 1330 |
| constrained_ols_av | full_ols_av | high | -0.5034 | -1.0276 | 0.0207 | 0.3862 | 290 |
| constrained_ols_av | full_ols_av | low | -0.4455 | -0.7341 | -0.1545 | 0.3443 | 880 |
| constrained_ols_av | full_ols_av | bid_type:regular | 0.6416 | 0.4792 | 0.7952 | 0.4928 | 2500 |
| full_ols_av | constrained_ols_av | pooled | -0.6000 | -0.7568 | -0.4404 | 0.3304 | 2500 |
| full_ols_av | constrained_ols_av | suit | -1.5660 | -1.7615 | -1.3781 | 0.2132 | 1304 |
| full_ols_av | constrained_ols_av | high | 0.2868 | -0.2574 | 0.8051 | 0.4375 | 272 |
| full_ols_av | constrained_ols_av | low | 0.5022 | 0.2219 | 0.7781 | 0.4643 | 924 |
| full_ols_av | constrained_ols_av | bid_type:regular | -0.6000 | -0.7568 | -0.4404 | 0.3304 | 2500 |
| constrained_ols_av | stricthellraiser | pooled | 1.2788 | 1.0472 | 1.5104 | 0.3612 | 2500 |
| constrained_ols_av | stricthellraiser | suit | 1.2478 | 1.0145 | 1.4827 | 0.3566 | 2482 |
| constrained_ols_av | stricthellraiser | high | 6.0000 | 3.0000 | 9.0000 | 1.0000 | 4 |
| constrained_ols_av | stricthellraiser | low | 5.4286 | 4.0000 | 6.8571 | 1.0000 | 14 |
| constrained_ols_av | stricthellraiser | bid_type:regular | 1.2788 | 1.0472 | 1.5104 | 0.3612 | 2500 |
| stricthellraiser | constrained_ols_av | pooled | -1.6488 | -1.8856 | -1.4120 | 0.4004 | 2500 |
| stricthellraiser | constrained_ols_av | suit | -1.6420 | -1.8816 | -1.4051 | 0.4023 | 2483 |
| stricthellraiser | constrained_ols_av | high | 4.0000 | -4.0000 | 12.0000 | 0.5000 | 2 |
| stricthellraiser | constrained_ols_av | low | -3.5333 | -5.6000 | -0.8667 | 0.0667 | 15 |
| stricthellraiser | constrained_ols_av | bid_type:regular | -1.6488 | -1.8856 | -1.4120 | 0.4004 | 2500 |
| constrained_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| constrained_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| constrained_ols_av | rankthetank | bid_type:regular | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | constrained_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | constrained_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | constrained_ols_av | bid_type:regular | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| constrained_ols_av | anchor_hybrid_r0_full | pooled | -0.0516 | -0.2500 | 0.1572 | 0.3680 | 2500 |
| constrained_ols_av | anchor_hybrid_r0_full | suit | -0.0839 | -0.3069 | 0.1411 | 0.3636 | 1906 |
| constrained_ols_av | anchor_hybrid_r0_full | high | 0.2297 | -0.5766 | 1.0631 | 0.4009 | 222 |
| constrained_ols_av | anchor_hybrid_r0_full | low | -0.0538 | -0.6210 | 0.5242 | 0.3710 | 372 |
| constrained_ols_av | anchor_hybrid_r0_full | bid_type:regular | -0.0516 | -0.2500 | 0.1572 | 0.3680 | 2500 |
| anchor_hybrid_r0_full | constrained_ols_av | pooled | -0.2348 | -0.4348 | -0.0308 | 0.4740 | 2500 |
| anchor_hybrid_r0_full | constrained_ols_av | suit | -0.1413 | -0.3663 | 0.0852 | 0.4839 | 1889 |
| anchor_hybrid_r0_full | constrained_ols_av | high | -0.4141 | -1.1454 | 0.2996 | 0.4493 | 227 |
| anchor_hybrid_r0_full | constrained_ols_av | low | -0.5885 | -1.1354 | -0.0391 | 0.4401 | 384 |
| anchor_hybrid_r0_full | constrained_ols_av | bid_type:regular | -0.2348 | -0.4348 | -0.0308 | 0.4740 | 2500 |
| selected_ols_av | selected_ols_av | pooled | -0.1232 | -0.2896 | 0.0396 | 0.4044 | 2500 |
| selected_ols_av | selected_ols_av | suit | -0.0597 | -0.2438 | 0.1286 | 0.4177 | 1858 |
| selected_ols_av | selected_ols_av | high | -0.3165 | -0.9266 | 0.2844 | 0.3853 | 218 |
| selected_ols_av | selected_ols_av | low | -0.3019 | -0.7052 | 0.0967 | 0.3561 | 424 |
| selected_ols_av | selected_ols_av | bid_type:regular | -0.1232 | -0.2896 | 0.0396 | 0.4044 | 2500 |
| selected_ols_av | full_ols_av | pooled | 0.5300 | 0.3660 | 0.6908 | 0.4792 | 2500 |
| selected_ols_av | full_ols_av | suit | 1.4713 | 1.2594 | 1.6741 | 0.5998 | 1307 |
| selected_ols_av | full_ols_av | high | -0.8374 | -1.3495 | -0.3149 | 0.3460 | 289 |
| selected_ols_av | full_ols_av | low | -0.3938 | -0.6814 | -0.1095 | 0.3473 | 904 |
| selected_ols_av | full_ols_av | bid_type:regular | 0.5300 | 0.3660 | 0.6908 | 0.4792 | 2500 |
| full_ols_av | selected_ols_av | pooled | -0.5520 | -0.7092 | -0.3912 | 0.3360 | 2500 |
| full_ols_av | selected_ols_av | suit | -1.5425 | -1.7449 | -1.3377 | 0.2162 | 1235 |
| full_ols_av | selected_ols_av | high | 0.6053 | 0.1118 | 1.1020 | 0.4836 | 304 |
| full_ols_av | selected_ols_av | low | 0.3548 | 0.0916 | 0.6171 | 0.4433 | 961 |
| full_ols_av | selected_ols_av | bid_type:regular | -0.5520 | -0.7092 | -0.3912 | 0.3360 | 2500 |
| selected_ols_av | stricthellraiser | pooled | 1.5688 | 1.3292 | 1.8180 | 0.3516 | 2500 |
| selected_ols_av | stricthellraiser | suit | 1.5651 | 1.3228 | 1.8090 | 0.3508 | 2497 |
| selected_ols_av | stricthellraiser | high | 4.0000 | 4.0000 | 4.0000 | 1.0000 | 2 |
| selected_ols_av | stricthellraiser | low | 6.0000 | 6.0000 | 6.0000 | 1.0000 | 1 |
| selected_ols_av | stricthellraiser | bid_type:regular | 1.5688 | 1.3292 | 1.8180 | 0.3516 | 2500 |
| stricthellraiser | selected_ols_av | pooled | -1.8556 | -2.1028 | -1.6092 | 0.4108 | 2500 |
| stricthellraiser | selected_ols_av | suit | -1.8514 | -2.0986 | -1.6010 | 0.4115 | 2496 |
| stricthellraiser | selected_ols_av | high | -1.0000 | -2.0000 | 0.0000 | 0.0000 | 2 |
| stricthellraiser | selected_ols_av | low | -8.0000 | -10.0000 | -6.0000 | 0.0000 | 2 |
| stricthellraiser | selected_ols_av | bid_type:regular | -1.8556 | -2.1028 | -1.6092 | 0.4108 | 2500 |
| selected_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_ols_av | rankthetank | bid_type:regular | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | selected_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_ols_av | bid_type:regular | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| selected_ols_av | anchor_hybrid_r0_full | pooled | 0.0456 | -0.1544 | 0.2528 | 0.3876 | 2500 |
| selected_ols_av | anchor_hybrid_r0_full | suit | 0.0074 | -0.2119 | 0.2341 | 0.3832 | 1897 |
| selected_ols_av | anchor_hybrid_r0_full | high | 0.3036 | -0.4777 | 1.1071 | 0.4152 | 224 |
| selected_ols_av | anchor_hybrid_r0_full | low | 0.0844 | -0.4724 | 0.6544 | 0.3931 | 379 |
| selected_ols_av | anchor_hybrid_r0_full | bid_type:regular | 0.0456 | -0.1544 | 0.2528 | 0.3876 | 2500 |
| anchor_hybrid_r0_full | selected_ols_av | pooled | -0.3396 | -0.5396 | -0.1308 | 0.4648 | 2500 |
| anchor_hybrid_r0_full | selected_ols_av | suit | -0.2397 | -0.4704 | -0.0075 | 0.4778 | 1873 |
| anchor_hybrid_r0_full | selected_ols_av | high | -0.2915 | -1.0269 | 0.4484 | 0.4664 | 223 |
| anchor_hybrid_r0_full | selected_ols_av | low | -0.8292 | -1.3639 | -0.3069 | 0.4035 | 404 |
| anchor_hybrid_r0_full | selected_ols_av | bid_type:regular | -0.3396 | -0.5396 | -0.1308 | 0.4648 | 2500 |
| full_ols_av | full_ols_av | pooled | 0.0256 | -0.1380 | 0.1888 | 0.4132 | 2500 |
| full_ols_av | full_ols_av | suit | 0.0634 | -0.2452 | 0.3719 | 0.4270 | 726 |
| full_ols_av | full_ols_av | high | -0.0486 | -0.4460 | 0.3532 | 0.4172 | 453 |
| full_ols_av | full_ols_av | low | 0.0303 | -0.1953 | 0.2468 | 0.4042 | 1321 |
| full_ols_av | full_ols_av | bid_type:regular | 0.0256 | -0.1380 | 0.1888 | 0.4132 | 2500 |
| full_ols_av | stricthellraiser | pooled | 1.3152 | 1.0868 | 1.5520 | 0.3828 | 2500 |
| full_ols_av | stricthellraiser | suit | 1.2937 | 1.0531 | 1.5314 | 0.3608 | 2356 |
| full_ols_av | stricthellraiser | high | 4.2727 | 0.8182 | 6.5455 | 0.9091 | 11 |
| full_ols_av | stricthellraiser | low | 1.4511 | 0.3308 | 2.5338 | 0.7293 | 133 |
| full_ols_av | stricthellraiser | bid_type:regular | 1.3152 | 1.0868 | 1.5520 | 0.3828 | 2500 |
| stricthellraiser | full_ols_av | pooled | -1.5288 | -1.7584 | -1.2988 | 0.3860 | 2500 |
| stricthellraiser | full_ols_av | suit | -1.4887 | -1.7252 | -1.2484 | 0.4020 | 2351 |
| stricthellraiser | full_ols_av | high | -4.2667 | -5.2000 | -3.3333 | 0.0000 | 15 |
| stricthellraiser | full_ols_av | low | -1.9254 | -2.9104 | -0.8881 | 0.1493 | 134 |
| stricthellraiser | full_ols_av | bid_type:regular | -1.5288 | -1.7584 | -1.2988 | 0.3860 | 2500 |
| full_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| full_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| full_ols_av | rankthetank | bid_type:regular | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | full_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | full_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | full_ols_av | bid_type:regular | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| full_ols_av | anchor_hybrid_r0_full | pooled | 0.0960 | -0.1000 | 0.3000 | 0.3876 | 2500 |
| full_ols_av | anchor_hybrid_r0_full | suit | -0.2123 | -0.4563 | 0.0266 | 0.3482 | 1729 |
| full_ols_av | anchor_hybrid_r0_full | high | 0.9663 | 0.3926 | 1.5460 | 0.4969 | 326 |
| full_ols_av | anchor_hybrid_r0_full | low | 0.6562 | 0.1551 | 1.1596 | 0.4607 | 445 |
| full_ols_av | anchor_hybrid_r0_full | bid_type:regular | 0.0960 | -0.1000 | 0.3000 | 0.3876 | 2500 |
| anchor_hybrid_r0_full | full_ols_av | pooled | -0.3632 | -0.5632 | -0.1552 | 0.4664 | 2500 |
| anchor_hybrid_r0_full | full_ols_av | suit | -0.0876 | -0.3435 | 0.1583 | 0.5105 | 1712 |
| anchor_hybrid_r0_full | full_ols_av | high | -0.8667 | -1.4349 | -0.3048 | 0.3683 | 315 |
| anchor_hybrid_r0_full | full_ols_av | low | -1.0254 | -1.4969 | -0.5517 | 0.3721 | 473 |
| anchor_hybrid_r0_full | full_ols_av | bid_type:regular | -0.3632 | -0.5632 | -0.1552 | 0.4664 | 2500 |
| stricthellraiser | stricthellraiser | pooled | -0.2352 | -0.6036 | 0.1284 | 0.4912 | 2500 |
| stricthellraiser | stricthellraiser | suit | -0.2352 | -0.6036 | 0.1284 | 0.4912 | 2500 |
| stricthellraiser | stricthellraiser | bid_type:regular | -0.2352 | -0.6036 | 0.1284 | 0.4912 | 2500 |
| stricthellraiser | rankthetank | pooled | -12.3992 | -12.6684 | -12.1260 | 0.0768 | 2500 |
| stricthellraiser | rankthetank | suit | -12.3992 | -12.6684 | -12.1260 | 0.0768 | 2500 |
| stricthellraiser | rankthetank | bid_type:regular | -12.3992 | -12.6684 | -12.1260 | 0.0768 | 2500 |
| rankthetank | stricthellraiser | pooled | 12.0920 | 11.8064 | 12.3776 | 0.9148 | 2500 |
| rankthetank | stricthellraiser | suit | 12.0920 | 11.8064 | 12.3776 | 0.9148 | 2500 |
| rankthetank | stricthellraiser | bid_type:regular | 12.0920 | 11.8064 | 12.3776 | 0.9148 | 2500 |
| stricthellraiser | anchor_hybrid_r0_full | pooled | -4.5468 | -4.8464 | -4.2556 | 0.3080 | 2500 |
| stricthellraiser | anchor_hybrid_r0_full | suit | -4.6230 | -4.9183 | -4.3199 | 0.3096 | 2448 |
| stricthellraiser | anchor_hybrid_r0_full | high | -1.1818 | -3.5909 | 1.5909 | 0.1818 | 22 |
| stricthellraiser | anchor_hybrid_r0_full | low | -0.8000 | -3.4667 | 2.1000 | 0.2667 | 30 |
| stricthellraiser | anchor_hybrid_r0_full | bid_type:regular | -4.5468 | -4.8464 | -4.2556 | 0.3080 | 2500 |
| anchor_hybrid_r0_full | stricthellraiser | pooled | 3.9140 | 3.6212 | 4.2080 | 0.5460 | 2500 |
| anchor_hybrid_r0_full | stricthellraiser | suit | 3.9522 | 3.6540 | 4.2553 | 0.5413 | 2448 |
| anchor_hybrid_r0_full | stricthellraiser | high | 2.1250 | -0.6250 | 4.6667 | 0.7500 | 24 |
| anchor_hybrid_r0_full | stricthellraiser | low | 2.1071 | 0.0714 | 3.7857 | 0.7857 | 28 |
| anchor_hybrid_r0_full | stricthellraiser | bid_type:regular | 3.9140 | 3.6212 | 4.2080 | 0.5460 | 2500 |
| rankthetank | rankthetank | pooled | 0.4572 | -0.0144 | 0.9180 | 0.5192 | 2500 |
| rankthetank | rankthetank | suit | 0.4572 | -0.0144 | 0.9180 | 0.5192 | 2500 |
| rankthetank | rankthetank | bid_type:regular | 0.4572 | -0.0144 | 0.9180 | 0.5192 | 2500 |
| rankthetank | anchor_hybrid_r0_full | pooled | -10.4936 | -10.7268 | -10.2544 | 0.1024 | 2500 |
| rankthetank | anchor_hybrid_r0_full | suit | -10.4962 | -10.7263 | -10.2565 | 0.1024 | 2499 |
| rankthetank | anchor_hybrid_r0_full | high | -4.0000 | -4.0000 | -4.0000 | 0.0000 | 1 |
| rankthetank | anchor_hybrid_r0_full | bid_type:regular | -10.4936 | -10.7268 | -10.2544 | 0.1024 | 2500 |
| anchor_hybrid_r0_full | rankthetank | pooled | 10.4624 | 10.2252 | 10.6928 | 0.8992 | 2500 |
| anchor_hybrid_r0_full | rankthetank | suit | 10.4624 | 10.2252 | 10.6928 | 0.8992 | 2500 |
| anchor_hybrid_r0_full | rankthetank | bid_type:regular | 10.4624 | 10.2252 | 10.6928 | 0.8992 | 2500 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | pooled | -0.2452 | -0.4540 | -0.0252 | 0.3652 | 2500 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | suit | -0.2403 | -0.5244 | 0.0426 | 0.4412 | 1598 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | high | -0.5468 | -1.4532 | 0.3892 | 0.4138 | 203 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | low | -0.4245 | -1.2122 | 0.3669 | 0.4460 | 278 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | bid_type:regular | -0.2949 | -0.5536 | -0.0370 | 0.4392 | 2079 |


![delta_bars_by_contract.png](charts/delta_bars_by_contract.png)

![h2h_heatmap.png](charts/h2h_heatmap.png)


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
| gbt_av | 4.4098 |  | 0.5012 | 0.4988 | 0.8707 | -7.0120 |  | 0.7008 | 0.0844 | 0.2148 | h2h_self_play |
| constrained_ols_av | 4.9566 |  | 0.4940 | 0.5060 | 0.9887 | 0.4800 |  | 0.7524 | 0.0656 | 0.1820 | h2h_self_play |
| selected_ols_av | 4.9224 |  | 0.4968 | 0.5032 | 0.9678 | -0.1400 |  | 0.7432 | 0.0872 | 0.1696 | h2h_self_play |
| full_ols_av | 4.9704 |  | 0.5048 | 0.4952 | 0.9881 | 0.4400 |  | 0.2904 | 0.1812 | 0.5284 | h2h_self_play |
| stricthellraiser | 2.2032 |  | 0.5072 | 0.4928 | 0.4306 | -6.0000 |  | 1.0000 | 0.0000 | 0.0000 | h2h_self_play |
| rankthetank | -1.6218 |  | 0.4756 | 0.5244 | 0.1102 | -9.5160 |  | 1.0000 | 0.0000 | 0.0000 | h2h_self_play |
| anchor_hybrid_r0_full | 3.5846 |  | 0.4024 | 0.5976 | 0.8539 | -5.9080 |  | 0.7686 | 0.0976 | 0.1337 | h2h_self_play |


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


![bid_behavior_panel.png](charts/bid_behavior_panel.png)

![contract_mix_bars.png](charts/contract_mix_bars.png)


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
| full_ols_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| full_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| stricthellraiser | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| stricthellraiser | make_rate_range | 0.9472 | 0.1000 | 1.0000 | PASS |
| rankthetank | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| rankthetank | make_rate_range | 0.1476 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_high | 0.8556 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_low | 0.8607 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_pass | 0.0027 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_suit | 0.8860 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_high | 0.8567 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_low | 0.8646 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_pass | 0.0235 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_suit | 0.8897 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_high | 0.8633 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_low | 0.8730 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_pass | 0.0257 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_suit | 0.8986 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_high | 0.8556 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_low | 0.8606 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_pass | 0.0154 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_suit | 0.8842 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_high | 0.8556 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_low | 0.8606 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_pass | 0.0154 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_suit | 0.0000 | 0.0000 | 1.0000 | FAIL |
