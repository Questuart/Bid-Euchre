# Rung Results Report

<!-- gate_status: QUICK-COMPLETE -->

Generated from canonical CSV tables and chart PNGs.

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
| r2_positive_full_ols_av_high | training | 0.5314 | 0.0000 | PASS | full_ols_av high R²=0.5314 |
| r2_positive_full_ols_av_low | training | 0.5115 | 0.0000 | PASS | full_ols_av low R²=0.5115 |
| r2_positive_full_ols_av_pass | training | 0.0034 | 0.0000 | PASS | full_ols_av pass R²=0.0034 |
| r2_positive_full_ols_av_suit | training | 0.5613 | 0.0000 | PASS | full_ols_av suit R²=0.5613 |
| r2_positive_gbt_av_high | training | 0.5528 | 0.0000 | PASS | gbt_av high R²=0.5528 |
| r2_positive_gbt_av_low | training | 0.5324 | 0.0000 | PASS | gbt_av low R²=0.5324 |
| r2_positive_gbt_av_pass | training | -0.0371 | 0.0000 | WARN | gbt_av pass R²=-0.0371 |
| r2_positive_gbt_av_suit | training | 0.5884 | 0.0000 | PASS | gbt_av suit R²=0.5884 |
| r2_positive_selected_ols_av_high | training | 0.5308 | 0.0000 | PASS | selected_ols_av high R²=0.5308 |
| r2_positive_selected_ols_av_low | training | 0.5010 | 0.0000 | PASS | selected_ols_av low R²=0.5010 |
| r2_positive_selected_ols_av_pass | training | -0.0004 | 0.0000 | WARN | selected_ols_av pass R²=-0.0004 |
| r2_positive_selected_ols_av_suit | training | 0.5545 | 0.0000 | PASS | selected_ols_av suit R²=0.5545 |
| r2_positive_selected_two_stage_av_high | training | 0.5308 | 0.0000 | PASS | selected_two_stage_av high R²=0.5308 |
| r2_positive_selected_two_stage_av_low | training | 0.5010 | 0.0000 | PASS | selected_two_stage_av low R²=0.5010 |
| r2_positive_selected_two_stage_av_pass | training | -0.0004 | 0.0000 | WARN | selected_two_stage_av pass R²=-0.0004 |
| r2_positive_selected_two_stage_av_suit | training | 0.0000 | 0.0000 | WARN | selected_two_stage_av suit R²=0.0000 |


## 2. Offline Model Performance

| model | contract | r_squared | mae | n_train | n_val |
| --- | --- | --- | --- | --- | --- |
| constrained_ols_av | high | 0.5308 | 4.1849 | 60937 | 7737 |
| constrained_ols_av | low | 0.5014 | 4.2831 | 60937 | 7737 |
| constrained_ols_av | pass | 0.0027 | 3.5477 | 8000 | 1000 |
| constrained_ols_av | suit | 0.5548 | 4.1231 | 243748 | 30948 |
| full_ols_av | high | 0.5314 | 4.1808 | 60937 | 7737 |
| full_ols_av | low | 0.5115 | 4.2322 | 60937 | 7737 |
| full_ols_av | pass | 0.0034 | 3.5685 | 8000 | 1000 |
| full_ols_av | suit | 0.5613 | 4.0897 | 243748 | 30948 |
| gbt_av | high | 0.5528 | 3.8341 | 60937 | 7737 |
| gbt_av | low | 0.5324 | 3.8970 | 60937 | 7737 |
| gbt_av | pass | -0.0371 | 3.6949 | 8000 | 1000 |
| gbt_av | suit | 0.5884 | 3.6500 | 243748 | 30948 |
| selected_ols_av | high | 0.5308 | 4.1840 | 60937 | 7737 |
| selected_ols_av | low | 0.5010 | 4.2852 | 60937 | 7737 |
| selected_ols_av | pass | -0.0004 | 3.5653 | 8000 | 1000 |
| selected_ols_av | suit | 0.5545 | 4.1251 | 243748 | 30948 |
| selected_two_stage_av | high | 0.5308 | 4.1840 | 60937 | 7737 |
| selected_two_stage_av | low | 0.5010 | 4.2852 | 60937 | 7737 |
| selected_two_stage_av | pass | -0.0004 | 3.5653 | 8000 | 1000 |
| selected_two_stage_av | suit |  |  | 243748 | 30948 |


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
| full_ols_av | pooled | 2.2360 | 2.1144 | 2.3592 | 1.0000 | 1.0000 | -4.5440 | 1 |
| gbt_av | pooled | 2.2012 | 2.0684 | 2.3340 | 0.9112 | 0.9908 | -5.9204 | 2 |
| constrained_ols_av | pooled | 2.1976 | 2.0720 | 2.3240 | 1.0000 | 1.0000 | -4.5120 | 3 |
| selected_ols_av | pooled | 2.1944 | 2.0728 | 2.3200 | 1.0000 | 1.0000 | -4.4800 | 4 |
| selected_two_stage_av | pooled | 1.8792 | 1.7460 | 2.0116 | 1.0000 | 0.9976 | -5.0720 | 5 |
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
| modeloespecifico | selected_two_stage_av | pooled | 0.0856 | -0.1192 | 0.2932 | 0.4380 | 2500 |
| modeloespecifico | selected_two_stage_av | suit | 0.0565 | -0.1556 | 0.2673 | 0.4325 | 2372 |
| modeloespecifico | selected_two_stage_av | high | 0.2264 | -1.4151 | 1.7925 | 0.5472 | 53 |
| modeloespecifico | selected_two_stage_av | low | 0.9067 | -0.4000 | 2.1600 | 0.5333 | 75 |
| selected_two_stage_av | modeloespecifico | pooled | -0.2836 | -0.4852 | -0.0784 | 0.4356 | 2500 |
| selected_two_stage_av | modeloespecifico | suit | -0.2227 | -0.4350 | -0.0130 | 0.4417 | 2393 |
| selected_two_stage_av | modeloespecifico | high | -2.1778 | -3.7333 | -0.5778 | 0.2889 | 45 |
| selected_two_stage_av | modeloespecifico | low | -1.2581 | -2.5806 | 0.0806 | 0.3065 | 62 |
| modeloespecifico | gbt_av | pooled | -1.0592 | -1.2704 | -0.8480 | 0.3260 | 2500 |
| modeloespecifico | gbt_av | suit | -0.6173 | -0.8575 | -0.3751 | 0.3715 | 1965 |
| modeloespecifico | gbt_av | high | -2.5238 | -3.2762 | -1.7238 | 0.1810 | 210 |
| modeloespecifico | gbt_av | low | -2.7846 | -3.3354 | -2.2308 | 0.1446 | 325 |
| gbt_av | modeloespecifico | pooled | 0.6312 | 0.4152 | 0.8484 | 0.5492 | 2500 |
| gbt_av | modeloespecifico | suit | 0.3030 | 0.0576 | 0.5470 | 0.5066 | 1980 |
| gbt_av | modeloespecifico | high | 2.1386 | 1.3465 | 2.9010 | 0.7228 | 202 |
| gbt_av | modeloespecifico | low | 1.7170 | 1.0314 | 2.3742 | 0.7044 | 318 |
| modeloespecifico | constrained_ols_av | pooled | 1.1416 | 0.9580 | 1.3240 | 0.6172 | 2500 |
| modeloespecifico | constrained_ols_av | suit | 1.2263 | 1.0329 | 1.4174 | 0.6296 | 2214 |
| modeloespecifico | constrained_ols_av | high | -0.1000 | -1.2200 | 0.9900 | 0.5200 | 100 |
| modeloespecifico | constrained_ols_av | low | 0.8011 | 0.0753 | 1.5216 | 0.5215 | 186 |
| constrained_ols_av | modeloespecifico | pooled | -1.3736 | -1.5492 | -1.1916 | 0.2196 | 2500 |
| constrained_ols_av | modeloespecifico | suit | -1.3924 | -1.5830 | -1.2009 | 0.2085 | 2240 |
| constrained_ols_av | modeloespecifico | high | -1.6375 | -2.7750 | -0.5000 | 0.3125 | 80 |
| constrained_ols_av | modeloespecifico | low | -1.0222 | -1.7333 | -0.2722 | 0.3167 | 180 |
| modeloespecifico | selected_ols_av | pooled | 1.1372 | 0.9520 | 1.3220 | 0.6136 | 2500 |
| modeloespecifico | selected_ols_av | suit | 1.2194 | 1.0244 | 1.4166 | 0.6269 | 2211 |
| modeloespecifico | selected_ols_av | high | -0.5370 | -1.5648 | 0.4907 | 0.4722 | 108 |
| modeloespecifico | selected_ols_av | low | 1.1326 | 0.4309 | 1.8398 | 0.5359 | 181 |
| selected_ols_av | modeloespecifico | pooled | -1.3968 | -1.5720 | -1.2160 | 0.2152 | 2500 |
| selected_ols_av | modeloespecifico | suit | -1.4244 | -1.6109 | -1.2285 | 0.2021 | 2236 |
| selected_ols_av | modeloespecifico | high | -1.1667 | -2.2447 | -0.0667 | 0.3556 | 90 |
| selected_ols_av | modeloespecifico | low | -1.1609 | -1.9080 | -0.4023 | 0.3103 | 174 |
| modeloespecifico | full_ols_av | pooled | 1.0800 | 0.8960 | 1.2636 | 0.6100 | 2500 |
| modeloespecifico | full_ols_av | suit | 1.1367 | 0.9455 | 1.3307 | 0.6189 | 2238 |
| modeloespecifico | full_ols_av | high | 0.0860 | -1.0538 | 1.2043 | 0.5376 | 93 |
| modeloespecifico | full_ols_av | low | 0.8757 | 0.0710 | 1.6568 | 0.5325 | 169 |
| full_ols_av | modeloespecifico | pooled | -1.2244 | -1.4028 | -1.0380 | 0.2360 | 2500 |
| full_ols_av | modeloespecifico | suit | -1.2282 | -1.4165 | -1.0377 | 0.2265 | 2252 |
| full_ols_av | modeloespecifico | high | -1.5529 | -2.7647 | -0.3176 | 0.3294 | 85 |
| full_ols_av | modeloespecifico | low | -1.0000 | -1.7546 | -0.2147 | 0.3190 | 163 |
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
| selected_two_stage_av | selected_two_stage_av | pooled | 0.0492 | -0.1552 | 0.2504 | 0.4376 | 2500 |
| selected_two_stage_av | selected_two_stage_av | suit | 0.0367 | -0.1671 | 0.2413 | 0.4356 | 2424 |
| selected_two_stage_av | selected_two_stage_av | high | 0.1786 | -2.2857 | 2.6437 | 0.5000 | 28 |
| selected_two_stage_av | selected_two_stage_av | low | 0.6042 | -1.1458 | 2.3339 | 0.5000 | 48 |
| selected_two_stage_av | gbt_av | pooled | -0.9756 | -1.1800 | -0.7660 | 0.3232 | 2500 |
| selected_two_stage_av | gbt_av | suit | -0.6094 | -0.8383 | -0.3805 | 0.3628 | 1979 |
| selected_two_stage_av | gbt_av | high | -2.9246 | -3.5980 | -2.2010 | 0.1608 | 199 |
| selected_two_stage_av | gbt_av | low | -2.0217 | -2.6273 | -1.3944 | 0.1801 | 322 |
| gbt_av | selected_two_stage_av | pooled | 0.8172 | 0.6112 | 1.0260 | 0.5476 | 2500 |
| gbt_av | selected_two_stage_av | suit | 0.5176 | 0.2927 | 0.7445 | 0.5070 | 1992 |
| gbt_av | selected_two_stage_av | high | 2.6277 | 1.8456 | 3.4149 | 0.7766 | 188 |
| gbt_av | selected_two_stage_av | low | 1.6187 | 0.9344 | 2.2500 | 0.6656 | 320 |
| selected_two_stage_av | constrained_ols_av | pooled | 0.7912 | 0.6064 | 0.9708 | 0.5600 | 2500 |
| selected_two_stage_av | constrained_ols_av | suit | 0.9151 | 0.7244 | 1.1039 | 0.5781 | 2261 |
| selected_two_stage_av | constrained_ols_av | high | -1.3291 | -2.5190 | -0.1013 | 0.3291 | 79 |
| selected_two_stage_av | constrained_ols_av | low | 0.0875 | -0.5938 | 0.7750 | 0.4188 | 160 |
| constrained_ols_av | selected_two_stage_av | pooled | -0.9172 | -1.0988 | -0.7348 | 0.2812 | 2500 |
| constrained_ols_av | selected_two_stage_av | suit | -1.0110 | -1.1950 | -0.8236 | 0.2651 | 2267 |
| constrained_ols_av | selected_two_stage_av | high | 0.8111 | -0.3444 | 1.9889 | 0.5333 | 90 |
| constrained_ols_av | selected_two_stage_av | low | -0.5175 | -1.3566 | 0.3149 | 0.3776 | 143 |
| selected_two_stage_av | selected_ols_av | pooled | 0.7664 | 0.5828 | 0.9492 | 0.5560 | 2500 |
| selected_two_stage_av | selected_ols_av | suit | 0.9291 | 0.7392 | 1.1159 | 0.5753 | 2270 |
| selected_two_stage_av | selected_ols_av | high | -1.5263 | -2.5579 | -0.4316 | 0.3263 | 95 |
| selected_two_stage_av | selected_ols_av | low | -0.3556 | -1.1333 | 0.4222 | 0.3926 | 135 |
| selected_ols_av | selected_two_stage_av | pooled | -0.9020 | -1.0828 | -0.7164 | 0.2876 | 2500 |
| selected_ols_av | selected_two_stage_av | suit | -1.0039 | -1.1888 | -0.8195 | 0.2707 | 2283 |
| selected_ols_av | selected_two_stage_av | high | 0.9381 | -0.1959 | 2.0722 | 0.5567 | 97 |
| selected_ols_av | selected_two_stage_av | low | -0.4500 | -1.3833 | 0.4667 | 0.3917 | 120 |
| selected_two_stage_av | full_ols_av | pooled | 0.7464 | 0.5636 | 0.9240 | 0.5568 | 2500 |
| selected_two_stage_av | full_ols_av | suit | 0.8984 | 0.7071 | 1.0892 | 0.5761 | 2253 |
| selected_two_stage_av | full_ols_av | high | -1.1978 | -2.2747 | -0.0989 | 0.3516 | 91 |
| selected_two_stage_av | full_ols_av | low | -0.3141 | -0.9936 | 0.4103 | 0.3974 | 156 |
| full_ols_av | selected_two_stage_av | pooled | -0.8480 | -1.0304 | -0.6652 | 0.2948 | 2500 |
| full_ols_av | selected_two_stage_av | suit | -0.9406 | -1.1272 | -0.7519 | 0.2800 | 2257 |
| full_ols_av | selected_two_stage_av | high | 0.1222 | -1.0000 | 1.2222 | 0.4667 | 90 |
| full_ols_av | selected_two_stage_av | low | -0.0523 | -0.8693 | 0.7778 | 0.4118 | 153 |
| selected_two_stage_av | stricthellraiser | pooled | 2.5568 | 2.2848 | 2.8344 | 0.4228 | 2500 |
| selected_two_stage_av | stricthellraiser | suit | 2.5493 | 2.2767 | 2.8304 | 0.4214 | 2494 |
| selected_two_stage_av | stricthellraiser | high | 5.5000 | 4.5000 | 6.0000 | 1.0000 | 4 |
| selected_two_stage_av | stricthellraiser | low | 6.0000 | 6.0000 | 6.0000 | 1.0000 | 2 |
| stricthellraiser | selected_two_stage_av | pooled | -3.0608 | -3.3368 | -2.7900 | 0.3888 | 2500 |
| stricthellraiser | selected_two_stage_av | suit | -3.0597 | -3.3380 | -2.7823 | 0.3893 | 2494 |
| stricthellraiser | selected_two_stage_av | high | -6.0000 | -6.0000 | -6.0000 | 0.0000 | 1 |
| stricthellraiser | selected_two_stage_av | low | -3.0000 | -8.0000 | 4.2000 | 0.2000 | 5 |
| selected_two_stage_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_two_stage_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | selected_two_stage_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_two_stage_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| selected_two_stage_av | anchor_hybrid_r0_full | pooled | 0.1400 | -0.0648 | 0.3508 | 0.4212 | 2500 |
| selected_two_stage_av | anchor_hybrid_r0_full | suit | 0.1658 | -0.0604 | 0.3974 | 0.4314 | 2003 |
| selected_two_stage_av | anchor_hybrid_r0_full | high | 0.5747 | -0.2172 | 1.3891 | 0.4299 | 221 |
| selected_two_stage_av | anchor_hybrid_r0_full | low | -0.3949 | -1.0942 | 0.3080 | 0.3406 | 276 |
| anchor_hybrid_r0_full | selected_two_stage_av | pooled | -0.3880 | -0.5940 | -0.1824 | 0.4452 | 2500 |
| anchor_hybrid_r0_full | selected_two_stage_av | suit | -0.4196 | -0.6435 | -0.1951 | 0.4335 | 2014 |
| anchor_hybrid_r0_full | selected_two_stage_av | high | -0.2526 | -1.0825 | 0.5723 | 0.4897 | 194 |
| anchor_hybrid_r0_full | selected_two_stage_av | low | -0.2603 | -0.9384 | 0.4041 | 0.4966 | 292 |
| gbt_av | gbt_av | pooled | -0.1232 | -0.3440 | 0.0976 | 0.4420 | 2500 |
| gbt_av | gbt_av | suit | 0.0122 | -0.2333 | 0.2617 | 0.4454 | 1796 |
| gbt_av | gbt_av | high | -0.3237 | -1.0252 | 0.3957 | 0.4532 | 278 |
| gbt_av | gbt_av | low | -0.5634 | -1.1690 | 0.0376 | 0.4202 | 426 |
| gbt_av | constrained_ols_av | pooled | 1.3184 | 1.1328 | 1.5024 | 0.6024 | 2500 |
| gbt_av | constrained_ols_av | suit | 1.2743 | 1.0585 | 1.4838 | 0.5963 | 1761 |
| gbt_av | constrained_ols_av | high | 1.4762 | 0.8639 | 2.0714 | 0.6224 | 294 |
| gbt_av | constrained_ols_av | low | 1.3888 | 0.9034 | 1.8652 | 0.6135 | 445 |
| constrained_ols_av | gbt_av | pooled | -1.5264 | -1.7084 | -1.3388 | 0.2500 | 2500 |
| constrained_ols_av | gbt_av | suit | -1.3577 | -1.5758 | -1.1392 | 0.2622 | 1789 |
| constrained_ols_av | gbt_av | high | -2.2381 | -2.8022 | -1.6739 | 0.2198 | 273 |
| constrained_ols_av | gbt_av | low | -1.7717 | -2.2511 | -1.2785 | 0.2192 | 438 |
| gbt_av | selected_ols_av | pooled | 1.3164 | 1.1280 | 1.5012 | 0.6012 | 2500 |
| gbt_av | selected_ols_av | suit | 1.2843 | 1.0661 | 1.4941 | 0.5930 | 1769 |
| gbt_av | selected_ols_av | high | 1.3725 | 0.7582 | 1.9511 | 0.6111 | 306 |
| gbt_av | selected_ols_av | low | 1.4094 | 0.9105 | 1.9129 | 0.6282 | 425 |
| selected_ols_av | gbt_av | pooled | -1.4624 | -1.6464 | -1.2752 | 0.2548 | 2500 |
| selected_ols_av | gbt_av | suit | -1.2929 | -1.5067 | -1.0807 | 0.2661 | 1796 |
| selected_ols_av | gbt_av | high | -2.0214 | -2.5872 | -1.4342 | 0.2384 | 281 |
| selected_ols_av | gbt_av | low | -1.8109 | -2.3026 | -1.3026 | 0.2175 | 423 |
| gbt_av | full_ols_av | pooled | 1.2912 | 1.1044 | 1.4756 | 0.6036 | 2500 |
| gbt_av | full_ols_av | suit | 1.2482 | 1.0319 | 1.4633 | 0.5959 | 1757 |
| gbt_av | full_ols_av | high | 1.5327 | 0.9346 | 2.1209 | 0.6340 | 306 |
| gbt_av | full_ols_av | low | 1.2952 | 0.7986 | 1.7918 | 0.6133 | 437 |
| full_ols_av | gbt_av | pooled | -1.4972 | -1.6828 | -1.3096 | 0.2572 | 2500 |
| full_ols_av | gbt_av | suit | -1.3185 | -1.5349 | -1.1032 | 0.2694 | 1774 |
| full_ols_av | gbt_av | high | -2.2055 | -2.7398 | -1.6370 | 0.2260 | 292 |
| full_ols_av | gbt_av | low | -1.7512 | -2.2442 | -1.2557 | 0.2281 | 434 |
| gbt_av | stricthellraiser | pooled | 3.4764 | 3.1776 | 3.7636 | 0.5220 | 2500 |
| gbt_av | stricthellraiser | suit | 3.5574 | 3.2539 | 3.8588 | 0.5086 | 2379 |
| gbt_av | stricthellraiser | high | 3.1600 | 1.4200 | 4.6800 | 0.8800 | 50 |
| gbt_av | stricthellraiser | low | 0.9859 | -0.7887 | 2.6479 | 0.7183 | 71 |
| stricthellraiser | gbt_av | pooled | -4.0516 | -4.3452 | -3.7696 | 0.3272 | 2500 |
| stricthellraiser | gbt_av | suit | -4.1366 | -4.4332 | -3.8345 | 0.3361 | 2380 |
| stricthellraiser | gbt_av | high | -3.3077 | -4.8974 | -1.4615 | 0.1026 | 39 |
| stricthellraiser | gbt_av | low | -1.9136 | -3.3580 | -0.4074 | 0.1728 | 81 |
| gbt_av | rankthetank | pooled | 10.4140 | 10.1768 | 10.6468 | 0.8988 | 2500 |
| gbt_av | rankthetank | suit | 10.4478 | 10.2081 | 10.6801 | 0.8992 | 2479 |
| gbt_av | rankthetank | high | 9.7500 | 9.2500 | 10.0000 | 1.0000 | 8 |
| gbt_av | rankthetank | low | 4.3846 | -1.0000 | 9.3846 | 0.7692 | 13 |
| rankthetank | gbt_av | pooled | -10.4324 | -10.6656 | -10.1940 | 0.1032 | 2500 |
| rankthetank | gbt_av | suit | -10.4733 | -10.7021 | -10.2316 | 0.1031 | 2474 |
| rankthetank | gbt_av | high | -6.3684 | -8.7368 | -3.1579 | 0.1053 | 19 |
| rankthetank | gbt_av | low | -7.0000 | -10.0000 | -1.0000 | 0.1429 | 7 |
| gbt_av | anchor_hybrid_r0_full | pooled | 1.0608 | 0.8516 | 1.2808 | 0.5320 | 2500 |
| gbt_av | anchor_hybrid_r0_full | suit | 0.8761 | 0.6261 | 1.1250 | 0.5121 | 1824 |
| gbt_av | anchor_hybrid_r0_full | high | 1.8681 | 1.2082 | 2.5243 | 0.6007 | 288 |
| gbt_av | anchor_hybrid_r0_full | low | 1.3368 | 0.7047 | 1.9534 | 0.5777 | 386 |
| anchor_hybrid_r0_full | gbt_av | pooled | -1.3440 | -1.5588 | -1.1284 | 0.3472 | 2500 |
| anchor_hybrid_r0_full | gbt_av | suit | -1.0292 | -1.2804 | -0.7746 | 0.3719 | 1815 |
| anchor_hybrid_r0_full | gbt_av | high | -2.2455 | -2.8989 | -1.5776 | 0.2888 | 277 |
| anchor_hybrid_r0_full | gbt_av | low | -2.1642 | -2.7139 | -1.6019 | 0.2811 | 402 |
| constrained_ols_av | constrained_ols_av | pooled | -0.0736 | -0.2348 | 0.0904 | 0.4036 | 2500 |
| constrained_ols_av | constrained_ols_av | suit | -0.0359 | -0.2226 | 0.1481 | 0.4148 | 1837 |
| constrained_ols_av | constrained_ols_av | high | -0.4512 | -1.0791 | 0.1676 | 0.3628 | 215 |
| constrained_ols_av | constrained_ols_av | low | -0.0469 | -0.4443 | 0.3504 | 0.3772 | 448 |
| constrained_ols_av | selected_ols_av | pooled | -0.1724 | -0.3344 | -0.0132 | 0.3896 | 2500 |
| constrained_ols_av | selected_ols_av | suit | -0.0897 | -0.2655 | 0.0946 | 0.4028 | 1872 |
| constrained_ols_av | selected_ols_av | high | -0.5419 | -1.1630 | 0.0573 | 0.3524 | 227 |
| constrained_ols_av | selected_ols_av | low | -0.3491 | -0.7706 | 0.0599 | 0.3491 | 401 |
| selected_ols_av | constrained_ols_av | pooled | 0.0480 | -0.1152 | 0.2132 | 0.4200 | 2500 |
| selected_ols_av | constrained_ols_av | suit | 0.1065 | -0.0856 | 0.2879 | 0.4318 | 1869 |
| selected_ols_av | constrained_ols_av | high | -0.3891 | -1.0317 | 0.2534 | 0.3846 | 221 |
| selected_ols_av | constrained_ols_av | low | 0.0171 | -0.4024 | 0.4317 | 0.3854 | 410 |
| constrained_ols_av | full_ols_av | pooled | -0.1068 | -0.2656 | 0.0544 | 0.4032 | 2500 |
| constrained_ols_av | full_ols_av | suit | -0.0485 | -0.2362 | 0.1382 | 0.4157 | 1816 |
| constrained_ols_av | full_ols_av | high | -0.1807 | -0.7605 | 0.3951 | 0.3908 | 238 |
| constrained_ols_av | full_ols_av | low | -0.3049 | -0.7041 | 0.0942 | 0.3587 | 446 |
| full_ols_av | constrained_ols_av | pooled | -0.0728 | -0.2348 | 0.0944 | 0.4056 | 2500 |
| full_ols_av | constrained_ols_av | suit | -0.0139 | -0.1998 | 0.1725 | 0.4151 | 1797 |
| full_ols_av | constrained_ols_av | high | -0.5142 | -1.0810 | 0.0526 | 0.3765 | 247 |
| full_ols_av | constrained_ols_av | low | -0.0658 | -0.4759 | 0.3333 | 0.3838 | 456 |
| constrained_ols_av | stricthellraiser | pooled | 1.2884 | 1.0580 | 1.5216 | 0.3604 | 2500 |
| constrained_ols_av | stricthellraiser | suit | 1.2637 | 1.0298 | 1.4996 | 0.3563 | 2484 |
| constrained_ols_av | stricthellraiser | high | 5.3333 | 2.0000 | 10.0000 | 1.0000 | 3 |
| constrained_ols_av | stricthellraiser | low | 5.0769 | 3.8462 | 6.4615 | 1.0000 | 13 |
| stricthellraiser | constrained_ols_av | pooled | -1.6560 | -1.8932 | -1.4196 | 0.4000 | 2500 |
| stricthellraiser | constrained_ols_av | suit | -1.6495 | -1.8889 | -1.4169 | 0.4016 | 2485 |
| stricthellraiser | constrained_ols_av | high | 4.0000 | -4.0000 | 12.0000 | 0.5000 | 2 |
| stricthellraiser | constrained_ols_av | low | -3.7692 | -6.0038 | -0.6923 | 0.0769 | 13 |
| constrained_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| constrained_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | constrained_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | constrained_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| constrained_ols_av | anchor_hybrid_r0_full | pooled | -0.0540 | -0.2524 | 0.1528 | 0.3684 | 2500 |
| constrained_ols_av | anchor_hybrid_r0_full | suit | -0.0935 | -0.3206 | 0.1287 | 0.3636 | 1903 |
| constrained_ols_av | anchor_hybrid_r0_full | high | 0.2398 | -0.5656 | 1.0680 | 0.4027 | 221 |
| constrained_ols_av | anchor_hybrid_r0_full | low | -0.0266 | -0.5851 | 0.5452 | 0.3723 | 376 |
| anchor_hybrid_r0_full | constrained_ols_av | pooled | -0.2380 | -0.4368 | -0.0340 | 0.4736 | 2500 |
| anchor_hybrid_r0_full | constrained_ols_av | suit | -0.1519 | -0.3757 | 0.0725 | 0.4825 | 1890 |
| anchor_hybrid_r0_full | constrained_ols_av | high | -0.4141 | -1.1454 | 0.2996 | 0.4493 | 227 |
| anchor_hybrid_r0_full | constrained_ols_av | low | -0.5587 | -1.1175 | -0.0208 | 0.4439 | 383 |
| selected_ols_av | selected_ols_av | pooled | -0.0624 | -0.2276 | 0.1028 | 0.4060 | 2500 |
| selected_ols_av | selected_ols_av | suit | 0.0389 | -0.1429 | 0.2191 | 0.4193 | 1903 |
| selected_ols_av | selected_ols_av | high | -0.4872 | -1.1154 | 0.1368 | 0.3761 | 234 |
| selected_ols_av | selected_ols_av | low | -0.3196 | -0.7632 | 0.1157 | 0.3554 | 363 |
| selected_ols_av | full_ols_av | pooled | 0.0060 | -0.1560 | 0.1692 | 0.4196 | 2500 |
| selected_ols_av | full_ols_av | suit | 0.0850 | -0.0991 | 0.2692 | 0.4328 | 1846 |
| selected_ols_av | full_ols_av | high | -0.0894 | -0.6707 | 0.5042 | 0.4146 | 246 |
| selected_ols_av | full_ols_av | low | -0.2941 | -0.6985 | 0.1299 | 0.3627 | 408 |
| full_ols_av | selected_ols_av | pooled | -0.1888 | -0.3508 | -0.0252 | 0.3888 | 2500 |
| full_ols_av | selected_ols_av | suit | -0.0964 | -0.2800 | 0.0855 | 0.3981 | 1836 |
| full_ols_av | selected_ols_av | high | -0.6941 | -1.2392 | -0.1333 | 0.3608 | 255 |
| full_ols_av | selected_ols_av | low | -0.2885 | -0.7164 | 0.1443 | 0.3643 | 409 |
| selected_ols_av | stricthellraiser | pooled | 1.3196 | 1.0904 | 1.5548 | 0.3596 | 2500 |
| selected_ols_av | stricthellraiser | suit | 1.2954 | 1.0616 | 1.5324 | 0.3557 | 2485 |
| selected_ols_av | stricthellraiser | high | 5.0000 | 3.5000 | 6.7500 | 1.0000 | 8 |
| selected_ols_av | stricthellraiser | low | 5.7143 | 4.0000 | 7.7143 | 1.0000 | 7 |
| stricthellraiser | selected_ols_av | pooled | -1.6300 | -1.8684 | -1.3936 | 0.4040 | 2500 |
| stricthellraiser | selected_ols_av | suit | -1.6153 | -1.8535 | -1.3791 | 0.4060 | 2485 |
| stricthellraiser | selected_ols_av | high | -3.2000 | -4.8000 | -1.6000 | 0.0000 | 5 |
| stricthellraiser | selected_ols_av | low | -4.5000 | -7.4000 | -0.5000 | 0.1000 | 10 |
| selected_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| selected_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | selected_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | selected_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| selected_ols_av | anchor_hybrid_r0_full | pooled | -0.0364 | -0.2376 | 0.1716 | 0.3716 | 2500 |
| selected_ols_av | anchor_hybrid_r0_full | suit | -0.0697 | -0.2903 | 0.1551 | 0.3673 | 1922 |
| selected_ols_av | anchor_hybrid_r0_full | high | 0.3142 | -0.5045 | 1.1283 | 0.4071 | 226 |
| selected_ols_av | anchor_hybrid_r0_full | low | -0.0795 | -0.6818 | 0.5199 | 0.3722 | 352 |
| anchor_hybrid_r0_full | selected_ols_av | pooled | -0.2012 | -0.4000 | 0.0068 | 0.4776 | 2500 |
| anchor_hybrid_r0_full | selected_ols_av | suit | -0.1025 | -0.3269 | 0.1303 | 0.4877 | 1903 |
| anchor_hybrid_r0_full | selected_ols_av | high | -0.4957 | -1.2132 | 0.2130 | 0.4391 | 230 |
| anchor_hybrid_r0_full | selected_ols_av | low | -0.5286 | -1.1035 | 0.0245 | 0.4496 | 367 |
| full_ols_av | full_ols_av | pooled | -0.1144 | -0.2764 | 0.0476 | 0.4032 | 2500 |
| full_ols_av | full_ols_av | suit | -0.0531 | -0.2394 | 0.1353 | 0.4150 | 1788 |
| full_ols_av | full_ols_av | high | -0.2852 | -0.8137 | 0.2624 | 0.3840 | 263 |
| full_ols_av | full_ols_av | low | -0.2584 | -0.6526 | 0.1381 | 0.3675 | 449 |
| full_ols_av | stricthellraiser | pooled | 1.2908 | 1.0612 | 1.5220 | 0.3648 | 2500 |
| full_ols_av | stricthellraiser | suit | 1.2569 | 1.0282 | 1.4893 | 0.3605 | 2483 |
| full_ols_av | stricthellraiser | high | 6.3333 | 4.0000 | 8.3333 | 1.0000 | 6 |
| full_ols_av | stricthellraiser | low | 6.1818 | 4.5455 | 7.8182 | 1.0000 | 11 |
| stricthellraiser | full_ols_av | pooled | -1.5848 | -1.8180 | -1.3532 | 0.3984 | 2500 |
| stricthellraiser | full_ols_av | suit | -1.5658 | -1.8027 | -1.3339 | 0.4007 | 2483 |
| stricthellraiser | full_ols_av | high | -1.5000 | -7.0000 | 7.5000 | 0.2500 | 4 |
| stricthellraiser | full_ols_av | low | -5.2308 | -6.9231 | -3.5385 | 0.0000 | 13 |
| full_ols_av | rankthetank | pooled | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| full_ols_av | rankthetank | suit | 10.4836 | 10.2476 | 10.7120 | 0.8996 | 2500 |
| rankthetank | full_ols_av | pooled | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| rankthetank | full_ols_av | suit | -10.5200 | -10.7516 | -10.2816 | 0.1024 | 2500 |
| full_ols_av | anchor_hybrid_r0_full | pooled | 0.0080 | -0.1904 | 0.2160 | 0.3764 | 2500 |
| full_ols_av | anchor_hybrid_r0_full | suit | -0.0501 | -0.2766 | 0.1817 | 0.3730 | 1855 |
| full_ols_av | anchor_hybrid_r0_full | high | 0.3872 | -0.3872 | 1.1787 | 0.4043 | 235 |
| full_ols_av | anchor_hybrid_r0_full | low | 0.0537 | -0.4757 | 0.5878 | 0.3756 | 410 |
| anchor_hybrid_r0_full | full_ols_av | pooled | -0.2796 | -0.4800 | -0.0704 | 0.4680 | 2500 |
| anchor_hybrid_r0_full | full_ols_av | suit | -0.1746 | -0.4097 | 0.0616 | 0.4816 | 1850 |
| anchor_hybrid_r0_full | full_ols_av | high | -0.3197 | -1.0205 | 0.3525 | 0.4508 | 244 |
| anchor_hybrid_r0_full | full_ols_av | low | -0.7340 | -1.2587 | -0.2192 | 0.4163 | 406 |
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
| selected_two_stage_av | 1.8792 | 5.9320 | 1.0000 | 0.9976 | 2.3120 | -5.0720 | comparator |
| gbt_av | 2.2012 | 5.6152 | 0.9112 | 0.9908 | 1.1239 | -5.9204 | comparator |
| constrained_ols_av | 2.1976 | 6.0988 | 1.0000 | 1.0000 | 2.7440 | -4.5120 | comparator |
| selected_ols_av | 2.1944 | 6.0972 | 1.0000 | 1.0000 | 2.7600 | -4.4800 | comparator |
| full_ols_av | 2.2360 | 6.1180 | 1.0000 | 1.0000 | 2.7280 | -4.5440 | comparator |
| stricthellraiser | 0.1096 | 4.9284 | 1.0000 | 0.9472 | -3.0000 | -11.2240 | comparator |
| rankthetank | -9.6972 | -5.5808 | 1.0000 | 0.1476 | -9.2480 | -15.0400 | comparator |
| modeloespecifico | 4.6906 |  | 0.4880 | 0.9287 | -3.2600 |  | h2h_self_play |
| selected_two_stage_av | 4.6178 |  | 0.5076 | 0.9165 | -4.3120 |  | h2h_self_play |
| gbt_av | 4.5768 |  | 0.4884 | 0.9124 | -4.7760 |  | h2h_self_play |
| constrained_ols_av | 4.9528 |  | 0.4932 | 0.9862 | 0.4080 |  | h2h_self_play |
| selected_ols_av | 4.9400 |  | 0.4940 | 0.9789 | 0.2120 |  | h2h_self_play |
| full_ols_av | 4.9592 |  | 0.4880 | 0.9877 | 0.4880 |  | h2h_self_play |
| stricthellraiser | 2.2032 |  | 0.5072 | 0.4306 | -6.0000 |  | h2h_self_play |
| rankthetank | -1.6218 |  | 0.4756 | 0.1102 | -9.5160 |  | h2h_self_play |
| anchor_hybrid_r0_full | 3.5846 |  | 0.4024 | 0.8539 | -5.9080 |  | h2h_self_play |


### Behavior by Contract

| model | contract | net_eppd | bid_rate | make_rate | source |
| --- | --- | --- | --- | --- | --- |
| modeloespecifico | pooled | 1.6608 | 1.0000 | 0.9496 | comparator |
| selected_two_stage_av | pooled | 1.8792 | 1.0000 | 0.9976 | comparator |
| gbt_av | pooled | 2.2012 | 0.9112 | 0.9908 | comparator |
| constrained_ols_av | pooled | 2.1976 | 1.0000 | 1.0000 | comparator |
| selected_ols_av | pooled | 2.1944 | 1.0000 | 1.0000 | comparator |
| full_ols_av | pooled | 2.2360 | 1.0000 | 1.0000 | comparator |
| stricthellraiser | pooled | 0.1096 | 1.0000 | 0.9472 | comparator |
| rankthetank | pooled | -9.6972 | 1.0000 | 0.1476 | comparator |


![bid_behavior_panel.png](charts/bid_behavior_panel.png)

![contract_mix_bars.png](charts/contract_mix_bars.png)


## 9. Sanity Bounds

| model | check_name | value | lower_bound | upper_bound | status |
| --- | --- | --- | --- | --- | --- |
| modeloespecifico | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| modeloespecifico | make_rate_range | 0.9496 | 0.1000 | 1.0000 | PASS |
| selected_two_stage_av | bid_rate_range | 1.0000 | 0.0500 | 0.9500 | FAIL |
| selected_two_stage_av | make_rate_range | 0.9976 | 0.1000 | 1.0000 | PASS |
| gbt_av | bid_rate_range | 0.9112 | 0.0500 | 0.9500 | PASS |
| gbt_av | make_rate_range | 0.9908 | 0.1000 | 1.0000 | PASS |
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
| constrained_ols_av | r2_positive_high | 0.5308 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_low | 0.5014 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_pass | 0.0027 | 0.0000 | 1.0000 | PASS |
| constrained_ols_av | r2_positive_suit | 0.5548 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_high | 0.5314 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_low | 0.5115 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_pass | 0.0034 | 0.0000 | 1.0000 | PASS |
| full_ols_av | r2_positive_suit | 0.5613 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_high | 0.5528 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_low | 0.5324 | 0.0000 | 1.0000 | PASS |
| gbt_av | r2_positive_pass | -0.0371 | 0.0000 | 1.0000 | FAIL |
| gbt_av | r2_positive_suit | 0.5884 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_high | 0.5308 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_low | 0.5010 | 0.0000 | 1.0000 | PASS |
| selected_ols_av | r2_positive_pass | -0.0004 | 0.0000 | 1.0000 | FAIL |
| selected_ols_av | r2_positive_suit | 0.5545 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_high | 0.5308 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_low | 0.5010 | 0.0000 | 1.0000 | PASS |
| selected_two_stage_av | r2_positive_pass | -0.0004 | 0.0000 | 1.0000 | FAIL |
| selected_two_stage_av | r2_positive_suit | 0.0000 | 0.0000 | 1.0000 | FAIL |
