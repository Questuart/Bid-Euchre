# Rung Results Report

<!-- gate_status: QUICK-COMPLETE -->

Generated from canonical CSV tables and chart PNGs.

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
| r2_positive_full_ols_av_suit | training | 0.5689 | 0.0000 | PASS | full_ols_av suit R²=0.5689 |
| r2_positive_gbt_av_high | training | 0.4763 | 0.0000 | PASS | gbt_av high R²=0.4763 |
| r2_positive_gbt_av_low | training | 0.4588 | 0.0000 | PASS | gbt_av low R²=0.4588 |
| r2_positive_gbt_av_pass | training | 0.0026 | 0.0000 | PASS | gbt_av pass R²=0.0026 |
| r2_positive_gbt_av_suit | training | 0.6208 | 0.0000 | PASS | gbt_av suit R²=0.6208 |
| r2_positive_selected_ols_av_high | training | 0.3841 | 0.0000 | PASS | selected_ols_av high R²=0.3841 |
| r2_positive_selected_ols_av_low | training | 0.3845 | 0.0000 | PASS | selected_ols_av low R²=0.3845 |
| r2_positive_selected_ols_av_pass | training | 0.0082 | 0.0000 | PASS | selected_ols_av pass R²=0.0082 |
| r2_positive_selected_ols_av_suit | training | 0.5553 | 0.0000 | PASS | selected_ols_av suit R²=0.5553 |
| r2_positive_selected_two_stage_av_high | training | 0.3841 | 0.0000 | PASS | selected_two_stage_av high R²=0.3841 |
| r2_positive_selected_two_stage_av_low | training | 0.3845 | 0.0000 | PASS | selected_two_stage_av low R²=0.3845 |
| r2_positive_selected_two_stage_av_pass | training | 0.0082 | 0.0000 | PASS | selected_two_stage_av pass R²=0.0082 |
| r2_positive_selected_two_stage_av_suit | training | 0.0000 | 0.0000 | WARN | selected_two_stage_av suit R²=0.0000 |


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
| gbt_av | pass | 0.0026 | 3.1941 | 8000 | 1000 |
| gbt_av | suit | 0.6208 | 3.4507 | 280416 | 34528 |
| selected_ols_av | high | 0.3841 | 4.3872 | 70104 | 8632 |
| selected_ols_av | low | 0.3845 | 4.5750 | 70104 | 8632 |
| selected_ols_av | pass | 0.0082 | 3.1110 | 8000 | 1000 |
| selected_ols_av | suit | 0.5553 | 4.0925 | 280416 | 34528 |
| selected_two_stage_av | high | 0.3841 | 4.3872 | 70104 | 8632 |
| selected_two_stage_av | low | 0.3845 | 4.5750 | 70104 | 8632 |
| selected_two_stage_av | pass | 0.0082 | 3.1110 | 8000 | 1000 |
| selected_two_stage_av | suit |  |  | 280416 | 34528 |


![r2_by_contract.png](charts/r2_by_contract.png)

![mae_by_contract.png](charts/mae_by_contract.png)


## 3. Offline Diagnostics

> [chart_name=pred_vs_actual_scatter.png] not yet generated

> [chart_name=residual_distribution.png] not yet generated

> [chart_name=calibration_curve.png] not yet generated


## 4. Model Interpretability

*Interpretability charts not yet generated (PR 3b).*


## 5. Cross-Model Decision Analysis

*Decision comparison analysis not yet generated (PR 3b).*

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


![comparator_ranking_bars.png](charts/comparator_ranking_bars.png)

![tail_risk_panel.png](charts/tail_risk_panel.png)


## 7. H2H Battery

| model_a | model_b | facet | net_eppd_delta | ci_low | ci_high | win_rate_a | deals_total |
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
| selected_two_stage_av | modeloespecifico | high | -2.8657 | -3.9403 | -1.7612 | 0.1642 | 67 |
| selected_two_stage_av | modeloespecifico | low | -2.6944 | -3.5558 | -1.7870 | 0.1574 | 108 |
| modeloespecifico | gbt_av | pooled | 0.2496 | 0.0492 | 0.4580 | 0.4976 | 2500 |
| modeloespecifico | gbt_av | suit | 0.6563 | 0.4338 | 0.8715 | 0.5384 | 2086 |
| modeloespecifico | gbt_av | high | -1.8889 | -2.7121 | -1.0455 | 0.2727 | 198 |
| modeloespecifico | gbt_av | low | -1.7176 | -2.4583 | -0.9769 | 0.3102 | 216 |
| gbt_av | modeloespecifico | pooled | -0.4248 | -0.6256 | -0.2240 | 0.3676 | 2500 |
| gbt_av | modeloespecifico | suit | -0.8381 | -1.0519 | -0.6218 | 0.3220 | 2118 |
| gbt_av | modeloespecifico | high | 2.0212 | 1.1958 | 2.8201 | 0.6667 | 189 |
| gbt_av | modeloespecifico | low | 1.7150 | 0.9119 | 2.5233 | 0.5751 | 193 |
| modeloespecifico | constrained_ols_av | pooled | 1.7664 | 1.5912 | 1.9348 | 0.6832 | 2500 |
| modeloespecifico | constrained_ols_av | suit | 1.7564 | 1.5799 | 1.9378 | 0.6843 | 2233 |
| modeloespecifico | constrained_ols_av | high | 1.1765 | -0.0588 | 2.3529 | 0.6941 | 85 |
| modeloespecifico | constrained_ols_av | low | 2.1648 | 1.5495 | 2.7527 | 0.6648 | 182 |
| constrained_ols_av | modeloespecifico | pooled | -1.9376 | -2.1092 | -1.7664 | 0.1316 | 2500 |
| constrained_ols_av | modeloespecifico | suit | -1.8666 | -2.0416 | -1.6837 | 0.1294 | 2257 |
| constrained_ols_av | modeloespecifico | high | -3.1757 | -4.1351 | -2.1351 | 0.1351 | 74 |
| constrained_ols_av | modeloespecifico | low | -2.3432 | -3.0118 | -1.6450 | 0.1598 | 169 |
| modeloespecifico | selected_ols_av | pooled | 1.8248 | 1.6536 | 1.9924 | 0.6880 | 2500 |
| modeloespecifico | selected_ols_av | suit | 1.8300 | 1.6533 | 2.0063 | 0.6911 | 2224 |
| modeloespecifico | selected_ols_av | high | 1.0930 | -0.1279 | 2.2558 | 0.6860 | 86 |
| modeloespecifico | selected_ols_av | low | 2.0947 | 1.5104 | 2.6737 | 0.6526 | 190 |
| selected_ols_av | modeloespecifico | pooled | -1.9796 | -2.1484 | -1.8112 | 0.1260 | 2500 |
| selected_ols_av | modeloespecifico | suit | -1.9165 | -2.0928 | -1.7358 | 0.1226 | 2252 |
| selected_ols_av | modeloespecifico | high | -2.6875 | -3.6878 | -1.6375 | 0.1750 | 80 |
| selected_ols_av | modeloespecifico | low | -2.4881 | -3.1548 | -1.8036 | 0.1488 | 168 |
| modeloespecifico | full_ols_av | pooled | 1.7448 | 1.5736 | 1.9160 | 0.6820 | 2500 |
| modeloespecifico | full_ols_av | suit | 1.7211 | 1.5355 | 1.9061 | 0.6826 | 2237 |
| modeloespecifico | full_ols_av | high | 1.0110 | -0.1099 | 2.1099 | 0.6484 | 91 |
| modeloespecifico | full_ols_av | low | 2.4419 | 1.8547 | 3.0407 | 0.6919 | 172 |
| full_ols_av | modeloespecifico | pooled | -1.8980 | -2.0680 | -1.7264 | 0.1348 | 2500 |
| full_ols_av | modeloespecifico | suit | -1.8342 | -2.0151 | -1.6503 | 0.1321 | 2256 |
| full_ols_av | modeloespecifico | high | -2.1932 | -3.1818 | -1.1591 | 0.2273 | 88 |
| full_ols_av | modeloespecifico | low | -2.6538 | -3.3077 | -1.9615 | 0.1218 | 156 |
| modeloespecifico | stricthellraiser | pooled | 4.5912 | 4.2820 | 4.9000 | 0.5348 | 2500 |
| modeloespecifico | stricthellraiser | suit | 4.5897 | 4.2772 | 4.8901 | 0.5335 | 2493 |
| modeloespecifico | stricthellraiser | high | 6.0000 | 2.0000 | 10.0000 | 1.0000 | 3 |
| modeloespecifico | stricthellraiser | low | 4.5000 | 3.0000 | 6.0000 | 1.0000 | 4 |
| stricthellraiser | modeloespecifico | pooled | -5.2608 | -5.5596 | -4.9592 | 0.3436 | 2500 |
| stricthellraiser | modeloespecifico | suit | -5.2651 | -5.5716 | -4.9639 | 0.3446 | 2493 |
| stricthellraiser | modeloespecifico | high | -3.0000 | -4.0000 | -2.0000 | 0.0000 | 2 |
| stricthellraiser | modeloespecifico | low | -4.0000 | -7.2000 | -0.8000 | 0.0000 | 5 |
| modeloespecifico | rankthetank | pooled | 10.4808 | 10.2456 | 10.7100 | 0.8996 | 2500 |
| modeloespecifico | rankthetank | suit | 10.4808 | 10.2456 | 10.7100 | 0.8996 | 2500 |
| rankthetank | modeloespecifico | pooled | -10.5044 | -10.7368 | -10.2652 | 0.1024 | 2500 |
| rankthetank | modeloespecifico | suit | -10.5044 | -10.7368 | -10.2652 | 0.1024 | 2500 |
| modeloespecifico | anchor_hybrid_r0_full | pooled | 0.2320 | 0.0248 | 0.4452 | 0.4548 | 2500 |
| modeloespecifico | anchor_hybrid_r0_full | suit | 0.3443 | 0.1282 | 0.5646 | 0.4735 | 2129 |
| modeloespecifico | anchor_hybrid_r0_full | high | -0.4150 | -1.4694 | 0.6735 | 0.3605 | 147 |
| modeloespecifico | anchor_hybrid_r0_full | low | -0.4107 | -1.2366 | 0.4421 | 0.3393 | 224 |
| anchor_hybrid_r0_full | modeloespecifico | pooled | -0.5584 | -0.7636 | -0.3456 | 0.3988 | 2500 |
| anchor_hybrid_r0_full | modeloespecifico | suit | -0.6416 | -0.8642 | -0.4214 | 0.3751 | 2157 |
| anchor_hybrid_r0_full | modeloespecifico | high | -0.1857 | -1.2643 | 0.8357 | 0.5214 | 140 |
| anchor_hybrid_r0_full | modeloespecifico | low | 0.0690 | -0.7931 | 0.9458 | 0.5665 | 203 |
| selected_two_stage_av | selected_two_stage_av | pooled | -0.0500 | -0.2304 | 0.1304 | 0.4064 | 2500 |
| selected_two_stage_av | selected_two_stage_av | suit | -0.0583 | -0.2431 | 0.1273 | 0.4041 | 2435 |
| selected_two_stage_av | selected_two_stage_av | high | -1.2941 | -4.2353 | 1.5294 | 0.4706 | 17 |
| selected_two_stage_av | selected_two_stage_av | low | 0.8125 | -0.8125 | 2.4375 | 0.5000 | 48 |
| selected_two_stage_av | gbt_av | pooled | -0.6220 | -0.8084 | -0.4332 | 0.3576 | 2500 |
| selected_two_stage_av | gbt_av | suit | -0.2123 | -0.4097 | -0.0173 | 0.3971 | 2138 |
| selected_two_stage_av | gbt_av | high | -3.3333 | -4.1348 | -2.4681 | 0.1064 | 141 |
| selected_two_stage_av | gbt_av | low | -2.8552 | -3.5249 | -2.1765 | 0.1357 | 221 |
| gbt_av | selected_two_stage_av | pooled | 0.6368 | 0.4476 | 0.8264 | 0.4744 | 2500 |
| gbt_av | selected_two_stage_av | suit | 0.2151 | 0.0191 | 0.4075 | 0.4257 | 2152 |
| gbt_av | selected_two_stage_av | high | 3.1745 | 2.3356 | 3.9732 | 0.7852 | 149 |
| gbt_av | selected_two_stage_av | low | 3.2965 | 2.6231 | 3.9447 | 0.7688 | 199 |
| selected_two_stage_av | constrained_ols_av | pooled | 1.0784 | 0.9124 | 1.2440 | 0.5712 | 2500 |
| selected_two_stage_av | constrained_ols_av | suit | 1.1726 | 1.0128 | 1.3375 | 0.5793 | 2427 |
| selected_two_stage_av | constrained_ols_av | high | -2.7692 | -4.7692 | -0.6154 | 0.2692 | 26 |
| selected_two_stage_av | constrained_ols_av | low | -1.6596 | -3.1489 | -0.0851 | 0.3191 | 47 |
| constrained_ols_av | selected_two_stage_av | pooled | -1.2732 | -1.4340 | -1.1100 | 0.2284 | 2500 |
| constrained_ols_av | selected_two_stage_av | suit | -1.3611 | -1.5218 | -1.1970 | 0.2168 | 2426 |
| constrained_ols_av | selected_two_stage_av | high | 1.6923 | -1.0000 | 4.2308 | 0.6154 | 26 |
| constrained_ols_av | selected_two_stage_av | low | 1.5625 | -0.2083 | 3.2917 | 0.6042 | 48 |
| selected_two_stage_av | selected_ols_av | pooled | 1.2220 | 1.0636 | 1.3788 | 0.5824 | 2500 |
| selected_two_stage_av | selected_ols_av | suit | 1.3215 | 1.1647 | 1.4800 | 0.5910 | 2423 |
| selected_two_stage_av | selected_ols_av | high | -2.4688 | -4.3438 | -0.4688 | 0.2812 | 32 |
| selected_two_stage_av | selected_ols_av | low | -1.5111 | -3.0667 | 0.1333 | 0.3333 | 45 |
| selected_ols_av | selected_two_stage_av | pooled | -1.4392 | -1.5984 | -1.2828 | 0.2136 | 2500 |
| selected_ols_av | selected_two_stage_av | suit | -1.5325 | -1.6842 | -1.3766 | 0.2001 | 2419 |
| selected_ols_av | selected_two_stage_av | high | 1.7222 | -0.2778 | 3.6681 | 0.6667 | 36 |
| selected_ols_av | selected_two_stage_av | low | 1.0444 | -0.8444 | 2.8889 | 0.5778 | 45 |
| selected_two_stage_av | full_ols_av | pooled | 1.1040 | 0.9452 | 1.2636 | 0.5692 | 2500 |
| selected_two_stage_av | full_ols_av | suit | 1.1930 | 1.0365 | 1.3529 | 0.5787 | 2414 |
| selected_two_stage_av | full_ols_av | high | -1.9773 | -3.4091 | -0.4318 | 0.2273 | 44 |
| selected_two_stage_av | full_ols_av | low | -0.7857 | -2.5238 | 0.9762 | 0.3810 | 42 |
| full_ols_av | selected_two_stage_av | pooled | -1.2824 | -1.4388 | -1.1248 | 0.2352 | 2500 |
| full_ols_av | selected_two_stage_av | suit | -1.3859 | -1.5404 | -1.2240 | 0.2198 | 2402 |
| full_ols_av | selected_two_stage_av | high | 1.9825 | 0.5263 | 3.2982 | 0.7193 | 57 |
| full_ols_av | selected_two_stage_av | low | 0.2439 | -1.5610 | 2.0488 | 0.4634 | 41 |
| selected_two_stage_av | stricthellraiser | pooled | 2.5208 | 2.2488 | 2.7948 | 0.3860 | 2500 |
| selected_two_stage_av | stricthellraiser | suit | 2.5162 | 2.2325 | 2.7892 | 0.3848 | 2495 |
| selected_two_stage_av | stricthellraiser | high | 6.0000 | 6.0000 | 6.0000 | 1.0000 | 2 |
| selected_two_stage_av | stricthellraiser | low | 4.0000 | 2.0000 | 6.0000 | 1.0000 | 3 |
| stricthellraiser | selected_two_stage_av | pooled | -2.9104 | -3.1856 | -2.6400 | 0.4004 | 2500 |
| stricthellraiser | selected_two_stage_av | suit | -2.9038 | -3.1812 | -2.6275 | 0.4014 | 2494 |
| stricthellraiser | selected_two_stage_av | high | -5.0000 | -6.0000 | -4.0000 | 0.0000 | 2 |
| stricthellraiser | selected_two_stage_av | low | -6.0000 | -8.5000 | -4.0000 | 0.0000 | 4 |
| selected_two_stage_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_two_stage_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | selected_two_stage_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_two_stage_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| selected_two_stage_av | anchor_hybrid_r0_full | pooled | -0.1196 | -0.3204 | 0.0864 | 0.3700 | 2500 |
| selected_two_stage_av | anchor_hybrid_r0_full | suit | 0.0570 | -0.1498 | 0.2643 | 0.3931 | 2157 |
| selected_two_stage_av | anchor_hybrid_r0_full | high | -0.8836 | -1.9863 | 0.2534 | 0.2397 | 146 |
| selected_two_stage_av | anchor_hybrid_r0_full | low | -1.4873 | -2.4112 | -0.5127 | 0.2132 | 197 |
| anchor_hybrid_r0_full | selected_two_stage_av | pooled | -0.1488 | -0.3504 | 0.0600 | 0.4744 | 2500 |
| anchor_hybrid_r0_full | selected_two_stage_av | suit | -0.2948 | -0.5021 | -0.0838 | 0.4440 | 2171 |
| anchor_hybrid_r0_full | selected_two_stage_av | high | 0.9925 | -0.1278 | 2.0451 | 0.6767 | 133 |
| anchor_hybrid_r0_full | selected_two_stage_av | low | 0.7083 | -0.2604 | 1.6510 | 0.6875 | 192 |
| gbt_av | gbt_av | pooled | -0.0564 | -0.2436 | 0.1324 | 0.4152 | 2500 |
| gbt_av | gbt_av | suit | 0.0171 | -0.1861 | 0.2191 | 0.4134 | 1935 |
| gbt_av | gbt_av | high | -0.3596 | -1.1009 | 0.3772 | 0.4518 | 228 |
| gbt_av | gbt_av | low | -0.2730 | -0.8487 | 0.3116 | 0.4006 | 337 |
| gbt_av | constrained_ols_av | pooled | 1.6908 | 1.5352 | 1.8452 | 0.6100 | 2500 |
| gbt_av | constrained_ols_av | suit | 1.3752 | 1.2096 | 1.5379 | 0.5818 | 2047 |
| gbt_av | constrained_ols_av | high | 3.6181 | 2.9722 | 4.2639 | 0.7708 | 144 |
| gbt_av | constrained_ols_av | low | 2.8835 | 2.4078 | 3.3366 | 0.7217 | 309 |
| constrained_ols_av | gbt_av | pooled | -1.7452 | -1.9036 | -1.5852 | 0.2224 | 2500 |
| constrained_ols_av | gbt_av | suit | -1.4138 | -1.5837 | -1.2463 | 0.2414 | 2030 |
| constrained_ols_av | gbt_av | high | -3.6867 | -4.3800 | -2.9733 | 0.1267 | 150 |
| constrained_ols_av | gbt_av | low | -2.9375 | -3.4062 | -2.4625 | 0.1469 | 320 |
| gbt_av | selected_ols_av | pooled | 1.9136 | 1.7620 | 2.0620 | 0.6360 | 2500 |
| gbt_av | selected_ols_av | suit | 1.6044 | 1.4403 | 1.7651 | 0.6093 | 2035 |
| gbt_av | selected_ols_av | high | 3.5695 | 2.9402 | 4.1854 | 0.7815 | 151 |
| gbt_av | selected_ols_av | low | 3.1210 | 2.6783 | 3.5382 | 0.7389 | 314 |
| selected_ols_av | gbt_av | pooled | -1.9352 | -2.0884 | -1.7796 | 0.2056 | 2500 |
| selected_ols_av | gbt_av | suit | -1.6296 | -1.7913 | -1.4645 | 0.2211 | 2017 |
| selected_ols_av | gbt_av | high | -3.5123 | -4.1667 | -2.8395 | 0.1420 | 162 |
| selected_ols_av | gbt_av | low | -3.0592 | -3.5203 | -2.5732 | 0.1402 | 321 |
| gbt_av | full_ols_av | pooled | 1.9496 | 1.8032 | 2.0956 | 0.6312 | 2500 |
| gbt_av | full_ols_av | suit | 1.6635 | 1.5012 | 1.8217 | 0.6052 | 1991 |
| gbt_av | full_ols_av | high | 2.9235 | 2.2882 | 3.5412 | 0.7059 | 170 |
| gbt_av | full_ols_av | low | 3.1416 | 2.7434 | 3.5428 | 0.7463 | 339 |
| full_ols_av | gbt_av | pooled | -1.9332 | -2.0836 | -1.7840 | 0.1996 | 2500 |
| full_ols_av | gbt_av | suit | -1.6153 | -1.7795 | -1.4501 | 0.2154 | 1973 |
| full_ols_av | gbt_av | high | -2.9719 | -3.6292 | -2.2978 | 0.1966 | 178 |
| full_ols_av | gbt_av | low | -3.2006 | -3.6189 | -2.7937 | 0.1117 | 349 |
| gbt_av | stricthellraiser | pooled | 2.1528 | 1.9152 | 2.3948 | 0.4768 | 2500 |
| gbt_av | stricthellraiser | suit | 2.0779 | 1.8235 | 2.3354 | 0.4505 | 2311 |
| gbt_av | stricthellraiser | high | 2.5455 | 1.3182 | 3.6705 | 0.7955 | 88 |
| gbt_av | stricthellraiser | low | 3.5248 | 2.5743 | 4.3765 | 0.8020 | 101 |
| stricthellraiser | gbt_av | pooled | -2.2352 | -2.4852 | -1.9916 | 0.3396 | 2500 |
| stricthellraiser | gbt_av | suit | -2.1886 | -2.4480 | -1.9244 | 0.3620 | 2290 |
| stricthellraiser | gbt_av | high | -2.1444 | -3.2111 | -0.9667 | 0.1111 | 90 |
| stricthellraiser | gbt_av | low | -3.1917 | -4.0750 | -2.2500 | 0.0833 | 120 |
| gbt_av | rankthetank | pooled | 10.3692 | 10.1248 | 10.6048 | 0.8960 | 2500 |
| gbt_av | rankthetank | suit | 10.4369 | 10.2001 | 10.6688 | 0.8979 | 2479 |
| gbt_av | rankthetank | high | 0.7000 | -5.7000 | 6.9000 | 0.6000 | 10 |
| gbt_av | rankthetank | low | 3.9091 | -2.0000 | 9.6364 | 0.7273 | 11 |
| rankthetank | gbt_av | pooled | -10.4628 | -10.6984 | -10.2212 | 0.1036 | 2500 |
| rankthetank | gbt_av | suit | -10.4867 | -10.7158 | -10.2435 | 0.1035 | 2484 |
| rankthetank | gbt_av | high | -6.9000 | -9.4000 | -2.7000 | 0.1000 | 10 |
| rankthetank | gbt_av | low | -6.5000 | -10.0000 | 0.5000 | 0.1667 | 6 |
| gbt_av | anchor_hybrid_r0_full | pooled | 0.4900 | 0.2888 | 0.6984 | 0.4396 | 2500 |
| gbt_av | anchor_hybrid_r0_full | suit | 0.2704 | 0.0433 | 0.4923 | 0.4211 | 1938 |
| gbt_av | anchor_hybrid_r0_full | high | 1.3777 | 0.5751 | 2.1888 | 0.5279 | 233 |
| gbt_av | anchor_hybrid_r0_full | low | 1.1765 | 0.5201 | 1.8421 | 0.4954 | 323 |
| anchor_hybrid_r0_full | gbt_av | pooled | -0.6948 | -0.9032 | -0.4792 | 0.4160 | 2500 |
| anchor_hybrid_r0_full | gbt_av | suit | -0.4048 | -0.6341 | -0.1769 | 0.4292 | 1927 |
| anchor_hybrid_r0_full | gbt_av | high | -1.6432 | -2.4405 | -0.8238 | 0.3744 | 227 |
| anchor_hybrid_r0_full | gbt_av | low | -1.7329 | -2.3798 | -1.0949 | 0.3798 | 337 |
| constrained_ols_av | constrained_ols_av | pooled | -0.0112 | -0.1676 | 0.1496 | 0.4220 | 2500 |
| constrained_ols_av | constrained_ols_av | suit | -0.0017 | -0.1619 | 0.1611 | 0.4205 | 2347 |
| constrained_ols_av | constrained_ols_av | high | 0.0976 | -1.7073 | 1.9024 | 0.4878 | 41 |
| constrained_ols_av | constrained_ols_av | low | -0.2500 | -1.1964 | 0.7143 | 0.4286 | 112 |
| constrained_ols_av | selected_ols_av | pooled | 0.4984 | 0.3428 | 0.6556 | 0.4804 | 2500 |
| constrained_ols_av | selected_ols_av | suit | 0.4754 | 0.3200 | 0.6333 | 0.4766 | 2375 |
| constrained_ols_av | selected_ols_av | high | -0.0811 | -2.1622 | 2.0270 | 0.4865 | 37 |
| constrained_ols_av | selected_ols_av | low | 1.3636 | 0.2500 | 2.4091 | 0.5795 | 88 |
| selected_ols_av | constrained_ols_av | pooled | -0.5196 | -0.6748 | -0.3636 | 0.3604 | 2500 |
| selected_ols_av | constrained_ols_av | suit | -0.4987 | -0.6564 | -0.3394 | 0.3583 | 2372 |
| selected_ols_av | constrained_ols_av | high | 0.5778 | -1.0667 | 2.2222 | 0.5333 | 45 |
| selected_ols_av | constrained_ols_av | low | -1.7108 | -2.8675 | -0.5542 | 0.3253 | 83 |
| constrained_ols_av | full_ols_av | pooled | 0.7268 | 0.5796 | 0.8732 | 0.4956 | 2500 |
| constrained_ols_av | full_ols_av | suit | 0.7003 | 0.5544 | 0.8478 | 0.4933 | 2372 |
| constrained_ols_av | full_ols_av | high | -0.8000 | -2.2400 | 0.7200 | 0.3400 | 50 |
| constrained_ols_av | full_ols_av | low | 2.5128 | 1.4872 | 3.5128 | 0.6667 | 78 |
| full_ols_av | constrained_ols_av | pooled | -0.7424 | -0.8876 | -0.5928 | 0.3228 | 2500 |
| full_ols_av | constrained_ols_av | suit | -0.7553 | -0.9010 | -0.6075 | 0.3165 | 2354 |
| full_ols_av | constrained_ols_av | high | 1.8000 | 0.4667 | 3.1000 | 0.6833 | 60 |
| full_ols_av | constrained_ols_av | low | -2.1628 | -3.1860 | -1.0930 | 0.2442 | 86 |
| constrained_ols_av | stricthellraiser | pooled | 0.5644 | 0.3604 | 0.7728 | 0.3500 | 2500 |
| constrained_ols_av | stricthellraiser | suit | 0.5448 | 0.3408 | 0.7531 | 0.3477 | 2491 |
| constrained_ols_av | stricthellraiser | high | 7.3333 | 6.0000 | 10.0000 | 1.0000 | 3 |
| constrained_ols_av | stricthellraiser | low | 5.3333 | 3.3333 | 7.3333 | 1.0000 | 6 |
| stricthellraiser | constrained_ols_av | pooled | -0.9228 | -1.1316 | -0.7148 | 0.4116 | 2500 |
| stricthellraiser | constrained_ols_av | suit | -0.9048 | -1.1193 | -0.6972 | 0.4133 | 2490 |
| stricthellraiser | constrained_ols_av | high | -5.0000 | -6.0000 | -4.0000 | 0.0000 | 2 |
| stricthellraiser | constrained_ols_av | low | -5.5000 | -7.5000 | -3.5000 | 0.0000 | 8 |
| constrained_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| constrained_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | constrained_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | constrained_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| constrained_ols_av | anchor_hybrid_r0_full | pooled | -0.0968 | -0.2940 | 0.1080 | 0.3652 | 2500 |
| constrained_ols_av | anchor_hybrid_r0_full | suit | 0.0742 | -0.1329 | 0.2789 | 0.3862 | 2144 |
| constrained_ols_av | anchor_hybrid_r0_full | high | -1.0414 | -2.1172 | 0.0690 | 0.2276 | 145 |
| constrained_ols_av | anchor_hybrid_r0_full | low | -1.1848 | -2.0664 | -0.2796 | 0.2464 | 211 |
| anchor_hybrid_r0_full | constrained_ols_av | pooled | -0.1632 | -0.3612 | 0.0448 | 0.4796 | 2500 |
| anchor_hybrid_r0_full | constrained_ols_av | suit | -0.3097 | -0.5157 | -0.1051 | 0.4498 | 2170 |
| anchor_hybrid_r0_full | constrained_ols_av | high | 1.2698 | 0.1270 | 2.3889 | 0.7063 | 126 |
| anchor_hybrid_r0_full | constrained_ols_av | low | 0.5098 | -0.4314 | 1.4412 | 0.6569 | 204 |
| selected_ols_av | selected_ols_av | pooled | -0.0044 | -0.1592 | 0.1500 | 0.4192 | 2500 |
| selected_ols_av | selected_ols_av | suit | -0.0129 | -0.1673 | 0.1411 | 0.4159 | 2409 |
| selected_ols_av | selected_ols_av | high | 0.8500 | -1.0000 | 2.7000 | 0.5750 | 40 |
| selected_ols_av | selected_ols_av | low | -0.2745 | -1.9216 | 1.3725 | 0.4510 | 51 |
| selected_ols_av | full_ols_av | pooled | 0.2440 | 0.0932 | 0.3948 | 0.4360 | 2500 |
| selected_ols_av | full_ols_av | suit | 0.2360 | 0.0888 | 0.3820 | 0.4337 | 2398 |
| selected_ols_av | full_ols_av | high | -0.6538 | -2.1154 | 0.8077 | 0.3654 | 52 |
| selected_ols_av | full_ols_av | low | 1.5600 | 0.0800 | 3.0400 | 0.6200 | 50 |
| full_ols_av | selected_ols_av | pooled | -0.1816 | -0.3276 | -0.0328 | 0.3884 | 2500 |
| full_ols_av | selected_ols_av | suit | -0.2113 | -0.3618 | -0.0612 | 0.3811 | 2385 |
| full_ols_av | selected_ols_av | high | 2.2414 | 0.9310 | 3.5172 | 0.7414 | 58 |
| full_ols_av | selected_ols_av | low | -1.4035 | -2.8079 | 0.0351 | 0.3333 | 57 |
| selected_ols_av | stricthellraiser | pooled | 0.4420 | 0.2432 | 0.6428 | 0.3500 | 2500 |
| selected_ols_av | stricthellraiser | suit | 0.4181 | 0.2201 | 0.6161 | 0.3474 | 2490 |
| selected_ols_av | stricthellraiser | high | 7.3333 | 6.0000 | 10.0000 | 1.0000 | 3 |
| selected_ols_av | stricthellraiser | low | 6.0000 | 4.0000 | 8.0000 | 1.0000 | 7 |
| stricthellraiser | selected_ols_av | pooled | -0.8172 | -1.0216 | -0.6144 | 0.4108 | 2500 |
| stricthellraiser | selected_ols_av | suit | -0.7941 | -0.9996 | -0.5923 | 0.4129 | 2487 |
| stricthellraiser | selected_ols_av | high | -5.0000 | -6.0000 | -4.0000 | 0.0000 | 2 |
| stricthellraiser | selected_ols_av | low | -5.2727 | -7.0909 | -3.4545 | 0.0000 | 11 |
| selected_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | selected_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| selected_ols_av | anchor_hybrid_r0_full | pooled | -0.2012 | -0.3980 | -0.0016 | 0.3524 | 2500 |
| selected_ols_av | anchor_hybrid_r0_full | suit | -0.0588 | -0.2614 | 0.1466 | 0.3707 | 2142 |
| selected_ols_av | anchor_hybrid_r0_full | high | -0.7400 | -1.8133 | 0.3867 | 0.2533 | 150 |
| selected_ols_av | anchor_hybrid_r0_full | low | -1.2788 | -2.1635 | -0.3653 | 0.2356 | 208 |
| anchor_hybrid_r0_full | selected_ols_av | pooled | 0.0024 | -0.1940 | 0.2068 | 0.4988 | 2500 |
| anchor_hybrid_r0_full | selected_ols_av | suit | -0.1108 | -0.3167 | 0.0928 | 0.4723 | 2166 |
| anchor_hybrid_r0_full | selected_ols_av | high | 1.1212 | 0.0076 | 2.2045 | 0.6894 | 132 |
| anchor_hybrid_r0_full | selected_ols_av | low | 0.4851 | -0.4653 | 1.4158 | 0.6584 | 202 |
| full_ols_av | full_ols_av | pooled | 0.0100 | -0.1316 | 0.1552 | 0.4088 | 2500 |
| full_ols_av | full_ols_av | suit | -0.0096 | -0.1513 | 0.1309 | 0.4048 | 2406 |
| full_ols_av | full_ols_av | high | 0.6207 | -0.7931 | 1.9655 | 0.5345 | 58 |
| full_ols_av | full_ols_av | low | 0.3333 | -1.5000 | 2.1111 | 0.4722 | 36 |
| full_ols_av | stricthellraiser | pooled | 0.3460 | 0.1576 | 0.5348 | 0.3620 | 2500 |
| full_ols_av | stricthellraiser | suit | 0.2786 | 0.0942 | 0.4716 | 0.3534 | 2462 |
| full_ols_av | stricthellraiser | high | 4.8750 | 3.0417 | 6.3333 | 0.9583 | 24 |
| full_ols_av | stricthellraiser | low | 4.4286 | 2.8571 | 6.0000 | 0.8571 | 14 |
| stricthellraiser | full_ols_av | pooled | -0.6660 | -0.8604 | -0.4732 | 0.4056 | 2500 |
| stricthellraiser | full_ols_av | suit | -0.6151 | -0.8112 | -0.4247 | 0.4113 | 2463 |
| stricthellraiser | full_ols_av | high | -3.4737 | -5.0526 | -1.3684 | 0.0526 | 19 |
| stricthellraiser | full_ols_av | low | -4.6667 | -6.1111 | -3.2222 | 0.0000 | 18 |
| full_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| full_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | full_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | full_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| full_ols_av | anchor_hybrid_r0_full | pooled | -0.1752 | -0.3712 | 0.0268 | 0.3512 | 2500 |
| full_ols_av | anchor_hybrid_r0_full | suit | -0.0463 | -0.2515 | 0.1608 | 0.3675 | 2139 |
| full_ols_av | anchor_hybrid_r0_full | high | -0.1856 | -1.1916 | 0.8503 | 0.3234 | 167 |
| full_ols_av | anchor_hybrid_r0_full | low | -1.5876 | -2.5258 | -0.6082 | 0.1959 | 194 |
| anchor_hybrid_r0_full | full_ols_av | pooled | -0.1832 | -0.3820 | 0.0196 | 0.4768 | 2500 |
| anchor_hybrid_r0_full | full_ols_av | suit | -0.3459 | -0.5526 | -0.1416 | 0.4456 | 2168 |
| anchor_hybrid_r0_full | full_ols_av | high | 0.7222 | -0.3333 | 1.7569 | 0.6389 | 144 |
| anchor_hybrid_r0_full | full_ols_av | low | 1.0000 | 0.0053 | 1.9468 | 0.7128 | 188 |
| stricthellraiser | stricthellraiser | pooled | -0.2352 | -0.6036 | 0.1284 | 0.4912 | 2500 |
| stricthellraiser | stricthellraiser | suit | -0.2352 | -0.6036 | 0.1284 | 0.4912 | 2500 |
| stricthellraiser | rankthetank | pooled | -12.3992 | -12.6684 | -12.1260 | 0.0768 | 2500 |
| stricthellraiser | rankthetank | suit | -12.3992 | -12.6684 | -12.1260 | 0.0768 | 2500 |
| rankthetank | stricthellraiser | pooled | 12.0920 | 11.8064 | 12.3776 | 0.9148 | 2500 |
| rankthetank | stricthellraiser | suit | 12.0920 | 11.8064 | 12.3776 | 0.9148 | 2500 |
| stricthellraiser | anchor_hybrid_r0_full | pooled | -4.5468 | -4.8464 | -4.2556 | 0.3080 | 2500 |
| stricthellraiser | anchor_hybrid_r0_full | suit | -4.6230 | -4.9183 | -4.3199 | 0.3096 | 2448 |
| stricthellraiser | anchor_hybrid_r0_full | high | -1.1818 | -3.5909 | 1.5909 | 0.1818 | 22 |
| stricthellraiser | anchor_hybrid_r0_full | low | -0.8000 | -3.4667 | 2.1000 | 0.2667 | 30 |
| anchor_hybrid_r0_full | stricthellraiser | pooled | 3.9140 | 3.6212 | 4.2080 | 0.5460 | 2500 |
| anchor_hybrid_r0_full | stricthellraiser | suit | 3.9522 | 3.6540 | 4.2553 | 0.5413 | 2448 |
| anchor_hybrid_r0_full | stricthellraiser | high | 2.1250 | -0.6250 | 4.6667 | 0.7500 | 24 |
| anchor_hybrid_r0_full | stricthellraiser | low | 2.1071 | 0.0714 | 3.7857 | 0.7857 | 28 |
| rankthetank | rankthetank | pooled | 0.4572 | -0.0144 | 0.9180 | 0.5192 | 2500 |
| rankthetank | rankthetank | suit | 0.4572 | -0.0144 | 0.9180 | 0.5192 | 2500 |
| rankthetank | anchor_hybrid_r0_full | pooled | -10.4936 | -10.7268 | -10.2544 | 0.1024 | 2500 |
| rankthetank | anchor_hybrid_r0_full | suit | -10.4962 | -10.7263 | -10.2565 | 0.1024 | 2499 |
| rankthetank | anchor_hybrid_r0_full | high | -4.0000 | -4.0000 | -4.0000 | 0.0000 | 1 |
| anchor_hybrid_r0_full | rankthetank | pooled | 10.4624 | 10.2252 | 10.6928 | 0.8992 | 2500 |
| anchor_hybrid_r0_full | rankthetank | suit | 10.4624 | 10.2252 | 10.6928 | 0.8992 | 2500 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | pooled | -0.2452 | -0.4540 | -0.0252 | 0.3652 | 2500 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | suit | -0.2403 | -0.5244 | 0.0426 | 0.4412 | 1598 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | high | -0.5468 | -1.4532 | 0.3892 | 0.4138 | 203 |
| anchor_hybrid_r0_full | anchor_hybrid_r0_full | low | -0.4245 | -1.2122 | 0.3669 | 0.4460 | 278 |


![delta_bars_by_contract.png](charts/delta_bars_by_contract.png)

![h2h_heatmap.png](charts/h2h_heatmap.png)


## 8. Behavioral Analysis

### Pooled Behavior Summary

| model | net_eppd | eppd | bid_rate | make_rate | cvar_5 | net_cvar_5 | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| modeloespecifico | 1.6608 | 5.6320 | 1.0000 | 0.9496 | -4.5120 | -11.1120 | comparator |
| selected_two_stage_av | 1.7724 | 5.4876 | 0.9256 | 0.9892 | 1.5652 | -5.7130 | comparator |
| gbt_av | 2.1136 | 5.3012 | 0.8520 | 0.9953 | 2.4057 | -4.4528 | comparator |
| constrained_ols_av | 1.8152 | 5.9076 | 1.0000 | 1.0000 | 2.6560 | -4.6880 | comparator |
| selected_ols_av | 1.4908 | 5.7452 | 1.0000 | 0.9996 | 2.3680 | -5.2560 | comparator |
| full_ols_av | 1.9720 | 5.8440 | 0.9716 | 1.0000 | 2.7603 | -4.4793 | comparator |
| stricthellraiser | 0.1096 | 4.9284 | 1.0000 | 0.9472 | -3.0000 | -11.2240 | comparator |
| rankthetank | -9.6972 | -5.5808 | 1.0000 | 0.1476 | -9.2480 | -15.0400 | comparator |
| modeloespecifico | 4.6906 |  | 0.4880 | 0.9287 | -3.2600 |  | h2h_self_play |
| selected_two_stage_av | 4.7558 |  | 0.4936 | 0.9384 | -2.5760 |  | h2h_self_play |
| gbt_av | 4.8606 |  | 0.4972 | 0.9654 | -1.2040 |  | h2h_self_play |
| constrained_ols_av | 4.9980 |  | 0.5044 | 0.9984 | 1.1760 |  | h2h_self_play |
| selected_ols_av | 4.9914 |  | 0.4944 | 0.9960 | 1.1040 |  | h2h_self_play |
| full_ols_av | 4.9982 |  | 0.5064 | 0.9984 | 1.4240 |  | h2h_self_play |
| stricthellraiser | 2.2032 |  | 0.5072 | 0.4306 | -6.0000 |  | h2h_self_play |
| rankthetank | -1.6218 |  | 0.4756 | 0.1102 | -9.5160 |  | h2h_self_play |
| anchor_hybrid_r0_full | 3.5846 |  | 0.4024 | 0.8539 | -5.9080 |  | h2h_self_play |


### Behavior by Contract

| model | contract | net_eppd | bid_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 1.6608 | 1.0000 | 0.9496 | comparator |
| selected_two_stage_av | pooled | 1.7724 | 0.9256 | 0.9892 | comparator |
| gbt_av | pooled | 2.1136 | 0.8520 | 0.9953 | comparator |
| constrained_ols_av | pooled | 1.8152 | 1.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 1.4908 | 1.0000 | 0.9996 | comparator |
| full_ols_av | pooled | 1.9720 | 0.9716 | 1.0000 | comparator |
| stricthellraiser | pooled | 0.1096 | 1.0000 | 0.9472 | comparator |
| rankthetank | pooled | -9.6972 | 1.0000 | 0.1476 | comparator |


![bid_behavior_panel.png](charts/bid_behavior_panel.png)

![contract_mix_bars.png](charts/contract_mix_bars.png)


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
| full_ols_av | bid_rate_range | 0.9716 | 0.0500 | 0.9500 | FAIL |
| full_ols_av | make_rate_range | 1.0000 | 0.1000 | 1.0000 | PASS |
| stricthellraiser | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| stricthellraiser | make_rate_range | 0.9472 | 0.1000 | 1.0000 | PASS |
| rankthetank | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| rankthetank | make_rate_range | 0.1476 | 0.1000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_high | 0.3233 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_low | 0.3244 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_pass | 0.0058 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_suit | 0.5566 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_high | 0.3927 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_low | 0.3934 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_pass | 0.0224 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_suit | 0.5689 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_high | 0.4763 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_low | 0.4588 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_pass | 0.0026 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_suit | 0.6208 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_high | 0.3841 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_low | 0.3845 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_pass | 0.0082 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_suit | 0.5553 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_high | 0.3841 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_low | 0.3845 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_pass | 0.0082 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_suit | 0.0000 | 0.0000 | 1.0000 | FAIL |
