# Phase 0 Bidless Report — 2026-02-07

> **Snapshot date:** 2026-02-07
> **Canonical git SHA:** `57268db5c6bdaa3e1f0fd353033976107b672dab`
> **Seed:** 42
> **Total budget:** 5.1M hands across 5 canonical runs + 720K policy gate evidence (5.82M total)
> **Charts:** 16 production charts across 5 suites (feature_health, feature_outcome, distribution, strategy_matchup, contract_faceted)
> **Provenance:** [`phase0_bidless_20260207_provenance.json`](phase0_bidless_20260207_provenance.json)

---

## 1. Executive Summary

Phase 0 established the bidless data foundation for Bid Euchre AI research:

- **5.82M hands** collected across 6 artifacts: 5.1M in 5 canonical runs (3 datasets + 2 outcome matrices) plus 720K in the policy gate
- **Glutton frozen** as canonical play policy — PASS gate with +0.19 to +0.21 mean trick advantage; all 95% bootstrap CIs exclude zero across 3 seeds and both seat directions
- **All sanity gates pass** — zero FAIL counts across all canonical runs (self-play fairness, random dominance, rank stability, transitivity); per-contract self-play confirms fairness holds within every contract type
- **Diagnostic Ridge R² ~ 0.19–0.21** on tricks_won (exploratory, not production) — confirms hand features carry predictive signal for downstream bidding model development
- **Contract-faceted analysis** confirms suit-invariant hand evaluation: hand value variance is stable across trump suits (σ² range: 8321.9–8369.7), and feature-outcome correlations are consistent across contract types (r = 0.34–0.40)

---

## 2. Data Inventory

Six artifacts (5 canonical runs + 1 policy gate) were produced on 2026-02-04 at git SHA `ea55269`:

| Artifact | Run ID | Purpose | Hands | PASS | WARN | FAIL | SKIP |
|----------|--------|---------|-------|------|------|------|------|
| dataset_greedy | `canonical_bidless_dataset_greedy_42_20260204_221121` | ML training data (greedy play) | 300K | 1 | 0 | 0 | 3 |
| dataset_glutton | `canonical_bidless_dataset_glutton_42_20260204_222713` | ML training data (glutton play) | 300K | 1 | 0 | 0 | 3 |
| dataset_mixed_play | `canonical_bidless_dataset_mixed_play_42_20260204_221115` | Analysis/diagnostics (3 policies) | 900K | 3 | 0 | 0 | 1 |
| outcomes_matrix_shallow | `canonical_bidless_outcomes_matrix_shallow_42_20260204_220920` | Broad sanity (5x5 matrix) | 300K | 4 | 0 | 0 | 0 |
| outcomes_zoom | `canonical_bidless_outcomes_zoom_42_20260204_222712` | High-precision (11 matchups) | 3.3M | 4 | 0 | 0 | 0 |
| policy_gate | `play_policy_gate_aggregate_20260204_221656.json` | Glutton vs greedy freeze gate | 720K | — | — | — | — |

**SKIP counts** in dataset runs are expected: single-policy self-play runs skip outcome-based sanity tests (random dominance, rank stability, transitivity) because they contain only one strategy.

**Gate evidence:** Each run directory contains a `canonical_summary.json` artifact with gate_status, PASS/WARN/FAIL/SKIP counts, and metadata. The policy gate artifact aggregates per-seed, per-direction bootstrap results.

### Schema Notes

- **`bidless.parquet`** — Per-seat rows: `hand_id`, `seat`, `hand_features` (struct with 41 fields)
- **`bidless_outcomes.parquet`** — Per-hand rows: `hand_id`, `tricks_team0`, `tricks_team1`, `team0_win`, plus scenario metadata
- **Row ratio:** 4 feature rows per 1 outcome row (4 seats per hand)
- Join key: seats 0,2 = team 0; seats 1,3 = team 1

---

## 3. Run Health Summary

Before examining results, these charts confirm the simulation infrastructure is sound.

### Self-Play Fairness (Aggregate)

![Self-play control chart](assets/phase0_20260207/self_play_control.png)

All 5 strategies in self-play show |mean delta| < 0.025 tricks (threshold: 0.25). This confirms zero systematic team bias in the simulation engine.

| Strategy | Mean Delta | Std | N |
|----------|-----------|-----|---|
| always_highest | -0.0106 | 6.055 | 300,000 |
| always_lowest | -0.0072 | 4.299 | 300,000 |
| glutton | -0.0108 | 3.550 | 300,000 |
| greedy | -0.0202 | 3.878 | 300,000 |
| random_legal | -0.0151 | 3.967 | 300,000 |

### Self-Play Fairness (Per-Contract)

![Self-play by contract](assets/phase0_20260207/self_play_by_contract.png)

Self-play fairness holds within every contract type (NT:High, NT:Low, Trump-C, Trump-D, Trump-H, Trump-S). All bars cluster tightly around the 5.0 expected mean, with the green fairness band showing the ±0.25 threshold. No strategy shows contract-specific team bias.

### Seat Balance

![Hand value by seat](assets/phase0_20260207/hand_value_by_seat.png)

Hand value distributions are identical across seats 0–3, confirming fair deal generation with no seat bias.

---

## 4. Play Policy Gate: Glutton > Greedy

### 4.1 Methodology

- **Seeds:** 42, 43, 44
- **Hands per scenario:** 20,000 (120,000 per seed-direction)
- **Directions:** Both `glutton_vs_greedy` and `greedy_vs_glutton` (direction-invariant advantage)
- **Statistic:** Bootstrap 95% CI on mean glutton advantage (positive = glutton better)
- **Gate criterion:** PASS if all CIs exclude zero

### 4.2 Aggregate Results

| Seed | Direction | Advantage | CI Lower | CI Upper | N | Status |
|------|-----------|-----------|----------|----------|---|--------|
| 42 | glutton_vs_greedy | +0.2110 | +0.1879 | +0.2324 | 120,000 | PASS |
| 42 | greedy_vs_glutton | +0.1862 | +0.1639 | +0.2082 | 120,000 | PASS |
| 43 | glutton_vs_greedy | +0.1944 | +0.1711 | +0.2164 | 120,000 | PASS |
| 43 | greedy_vs_glutton | +0.2100 | +0.1873 | +0.2327 | 120,000 | PASS |
| 44 | glutton_vs_greedy | +0.1956 | +0.1725 | +0.2175 | 120,000 | PASS |
| 44 | greedy_vs_glutton | +0.2104 | +0.1877 | +0.2326 | 120,000 | PASS |

**All 6 CIs exclude zero.** Lowest CI lower bound: +0.1639 (seed 42, greedy_vs_glutton).

### 4.3 Per-Scenario Breakdown (Seed 42)

| Scenario | Advantage | CI Lower | CI Upper |
|----------|-----------|----------|----------|
| suit_S | +0.2731 | +0.2204 | +0.3276 |
| suit_C | +0.3103 | +0.2580 | +0.3642 |
| suit_D | +0.2734 | +0.2201 | +0.3279 |
| suit_H | +0.2258 | +0.1728 | +0.2787 |
| high | +0.1306 | +0.0820 | +0.1794 |
| low | +0.0526 | +0.0031 | +0.1008 |

Suit contracts show the strongest advantage (+0.23 to +0.31). HIGH is moderate (+0.13). LOW is statistically significant but marginal (+0.05, CI barely excludes zero).

### 4.4 Decision

**Glutton frozen as canonical play policy.** LOW's marginal significance is documented as a known caveat but does not affect the pooled gate decision. The overall advantage is robust and consistent across seeds and directions.

---

## 5. Strategy Sanity Tests (Zoom Run)

**Source:** `canonical_bidless_outcomes_zoom_42_20260204_222712` — 3.3M hands, 11 matchups, 5 strategies

### 5.1 Summary

| Test | Status | Key Metric |
|------|--------|------------|
| Self-play fairness | PASS | All |delta| < 0.025 |
| Random dominance | PASS | Glutton 77%, greedy 73% win rate vs random |
| Rank stability | PASS | Kendall tau = 1.0 across all contract families |
| Transitivity | PASS | Zero violations across 5 strategies |

### 5.2 Self-Play Fairness

See Section 3 above for full table. All 5 strategies pass with |mean delta| < 0.025 (threshold: 0.25).

### 5.3 Random Dominance

| Strategy | Matchup | Win Rate | N |
|----------|---------|----------|---|
| glutton | glutton_vs_random_legal | 76.72% | 300,000 |
| glutton | random_legal_vs_glutton | 76.93% | 300,000 |
| greedy | greedy_vs_random_legal | 72.88% | 300,000 |
| greedy | random_legal_vs_greedy | 73.12% | 300,000 |

All intelligent strategies beat random_legal well above the 52% threshold. Direction-invariance confirmed (< 0.3% spread).

### 5.4 Rank Stability

| Family Pair | Kendall Tau | p-value |
|-------------|------------|---------|
| high vs low | 1.00 | 0.017 |
| high vs suit | 1.00 | 0.017 |
| low vs suit | 1.00 | 0.017 |

Strategy rankings are perfectly consistent across all contract families.

### 5.5 Transitivity

Zero violations detected across all 5 strategies. The competitive ordering is fully transitive.

### 5.6 Strategy Landscape

![Win rate heatmap](assets/phase0_20260207/win_rate_heatmap.png)

![Matchup summary](assets/phase0_20260207/matchup_summary.png)

### 5.7 Tricks Distribution by Matchup

![Tricks distribution by matchup](assets/phase0_20260207/tricks_distribution.png)

Violin plots show trick distributions for Team 0 across all 11 matchups. Self-play matchups (diagonal entries) center on 5.0 as expected. Cross-play matchups show clear distributional shifts — glutton vs weaker opponents shows a rightward shift (more high-trick outcomes), consistent with the win rate heatmap above.

---

## 6. Diagnostic Feature Evaluation

**Source:** Greedy + glutton datasets (300K hands each), 80/20 grouped split by `hand_id`, Ridge regression (alpha=1.0) with standardized features.

### 6.1 Overall Model Performance

| Policy | R² (test) | MAE (test) | N (test hands) | Intercept |
|--------|-----------|------------|----------------|-----------|
| greedy | 0.2088 | 1.3777 | 60,000 | 5.0000 |
| glutton | 0.1928 | 1.2867 | 60,000 | 5.0000 |

### 6.2 Per-Contract Breakdown

**Greedy:**

| Contract | R² (test) | MAE (test) | N (test rows) | OLSa Validation |
|----------|-----------|------------|---------------|-----------------|
| high | 0.2043 | 1.2807 | 40,000 | OK |
| low | 0.2133 | 1.2881 | 40,000 | OK |
| suit | 0.2295 | 1.4033 | 160,000 | WARN: `trump_count`, `offsuit_aces` not in top 10 |

**Glutton:**

| Contract | R² (test) | MAE (test) | N (test rows) | OLSa Validation |
|----------|-----------|------------|---------------|-----------------|
| high | 0.1893 | 1.3426 | 40,000 | OK |
| low | 0.1949 | 1.3511 | 40,000 | OK |
| suit | 0.2353 | 1.2189 | 160,000 | WARN: `trump_count`, `offsuit_aces` not in top 10 |

### 6.3 Top-10 Standardized Coefficients

**Greedy:**

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `highest_trump_rank` | -0.4468 |
| 2 | `rank_sum` | +0.4115 |
| 3 | `trump_rb_count` | +0.3632 |
| 4 | `trump_power_avg` | -0.3610 |
| 5 | `second_highest_trump_rank` | -0.3419 |
| 6 | `trump_count_x_void_count` | +0.3050 |
| 7 | `bowers` | +0.2695 |
| 8 | `hand_value` | +0.2679 |
| 9 | `offsuit_tens_count` | +0.2415 |
| 10 | `max_suit_len` | -0.1870 |

**Glutton:**

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `trump_power_avg` | -0.6148 |
| 2 | `rank_sum` | +0.3992 |
| 3 | `trump_count_x_void_count` | +0.2562 |
| 4 | `offsuit_tens_count` | +0.2277 |
| 5 | `trump_rb_count` | +0.2157 |
| 6 | `fourth_suit_len` | +0.1902 |
| 7 | `hand_value` | +0.1868 |
| 8 | `bowers` | +0.1826 |
| 9 | `trump_count_x_offsuit_ace` | -0.1774 |
| 10 | `void_count` | +0.1591 |

Notable differences: `trump_power_avg` is much more dominant under glutton (-0.61 vs -0.36), while `highest_trump_rank` and `second_highest_trump_rank` drop out of glutton's top 10 entirely.

### 6.4 Feature-Outcome Visualizations

![Feature-outcome correlation](assets/phase0_20260207/feature_outcome_correlation.png)

![Outcome distributions](assets/phase0_20260207/outcome_distributions.png)

### 6.5 Feature Signal by Contract Type

![Feature vs outcome by contract](assets/phase0_20260207/feature_vs_outcome_by_contract.png)

The top-correlated feature (hand_value) shows a positive relationship with tricks_won across all three contract types. Pearson correlations are strongest for suit contracts (r = 0.400), with HIGH (r = 0.344) and LOW (r = 0.345) showing similar but slightly weaker signal. The binned-mean trend lines confirm a monotonic positive relationship in all cases — hand_value is a reliable predictor regardless of contract type.

### 6.6 Caveats

- Coefficients are standardized (z-scored features) and **exploratory only**
- Correlated features share variance; coefficients do not imply causal importance
- Grouped train/test split by `hand_id` prevents leakage across 4 seat rows per hand
- No bootstrap CIs on R² or MAE (acceptable for exploratory diagnostics)
- This diagnostic is separate from the B0 hand-value regression in `train_b0.py`

---

## 7. Feature and Distribution Health

![Hand value by contract](assets/phase0_20260207/hand_value_by_contract.png)

Hand value distributions vary appropriately by contract type. Suit contracts show higher hand values on average (trump power contributes), while HIGH and LOW contracts show more symmetric distributions. This confirms the hand evaluator is well-calibrated to contract structure.

![CDF of tricks by contract](assets/phase0_20260207/cdf.png)

CDF curves show distinct shapes by contract type. Suit contracts have heavier right tails (more high-trick outcomes due to trump advantage). HIGH and LOW contracts are more symmetric around 5 tricks. The smooth, monotonic CDFs confirm adequate sample sizes with no discretization artifacts.

![CCDF (tail distribution) by contract](assets/phase0_20260207/ccdf.png)

The complementary CDF (log-scale) reveals tail behavior more clearly. Suit contracts maintain higher P(X > x) through the upper range — roughly 10% probability of winning 7+ tricks, compared to ~8% for NT contracts. All three contract types converge near 10 tricks (~1% probability), confirming the discrete distribution has no anomalous tail spikes.

---

## 8. Contract-Faceted Analysis

This section examines whether the hand evaluator and outcome distributions are invariant across trump suits, a key assumption for pooled modeling.

**Source:** Greedy dataset (300K hands), joined features + outcomes.

### 8.1 Hand Value by Trump Suit

![Hand value by trump suit](assets/phase0_20260207/hand_value_by_trump.png)

Hand value distributions are nearly identical across all four trump suits (C, D, H, S). Means cluster tightly around ~497, and per-suit variances range from σ² = 8321.9 (C) to σ² = 8369.7 (H) — a spread of less than 0.6% relative to the overall variance (σ² = 8349.2). This confirms the hand evaluator is trump-suit-invariant.

### 8.2 Tricks Won by Trump Suit

![Tricks won by trump suit](assets/phase0_20260207/outcome_by_trump.png)

Tricks-won distributions (violin plots) are symmetric around the mean of 5.0 for all four trump suits, with identical multimodal structure. No suit shows a systematic advantage or disadvantage in trick production. This validates that simulation outcomes are trump-suit-neutral.

### 8.3 Feature Means by Trump Suit

![Feature heatmap by trump suit](assets/phase0_20260207/feature_heatmap_by_suit.png)

The Z-score normalized heatmap reveals that while aggregate features (hand_value, trump_power_sum, rank_sum) show zero variation across suits (z = 0.00), trump-specific interaction features show natural suit-level variation. For example:

- **Clubs (C):** High trump_count_x_void_count (+1.64) and second_highest_trump_rank (+1.58) — club trump hands tend to have more voids alongside trump strength
- **Diamonds (D):** High offsuit_secondbest_rank_sum (+1.42) but low offsuit_best_rank_sum (-1.16) — diamond trump hands concentrate offsuit strength in secondary cards
- **Hearts (H):** Uniformly below-average on most interaction features — suggests hearts hands have less extreme feature combinations
- **Spades (S):** High third_highest_trump_rank (+1.57) and offsuit_best_rank_sum (+1.39) — spade trump hands tend to have deeper trump holdings

These variations reflect natural combinatorial differences in how trump suit choice interacts with the deal, not bias in the simulation engine. The zero-variation on aggregate features confirms the evaluator is suit-neutral at the summary level.

### 8.4 Hand Value Variance by Trump Suit

![Suit variance summary](assets/phase0_20260207/suit_variance_summary.png)

All four suits track the overall variance (σ² = 8349.2, dashed red line) to within 0.6%. This confirms that modeling variance assumptions hold uniformly across trump suits — no suit requires variance-specific treatment in downstream models.

---

## 9. Known Limitations

1. **No bootstrap CIs on diagnostic R²/MAE** — The diagnostic evaluation reports point estimates only. Acceptable for exploratory analysis; production models will require bootstrapped confidence intervals.

2. **SKIP counts in dataset runs** — Single-policy self-play runs skip outcome-based sanity tests (random dominance, rank stability, transitivity) because they contain only one strategy. This is expected behavior, not a deficiency.

3. **LOW contract marginal significance** — The glutton advantage in LOW contracts is statistically significant but marginal (CI barely excludes zero in seed 42). Pooled gate is robust.

4. **Chart normalization gap** — The `feature_health` and `feature_outcome` chart suites do not apply `_normalize_for_diagnostics()`, causing 3 charts (feature_distributions, feature_correlation, feature_vs_outcome) to render as placeholders when run via chart_runner. The underlying data is sound; only the column-prefix convention is mismatched. The `contract_faceted` suite handles this correctly.

---

## 10. Reproduction Commands

### Play Policy Gate
```bash
PYTHONPATH=src uv run python scripts/play_policy_gate.py \
  --seeds 42,43,44 --n-per 20000
```

### Diagnostic Evaluation
```bash
uv run python scripts/evaluate_diagnostic_tricks.py \
  --greedy-dir data/runs/canonical_bidless_dataset_greedy_42_20260204_221121 \
  --glutton-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
  --seed 42 --output /tmp/diagnostic_tricks_evaluation.md
```

### Notebook Execution (Smoke)
```bash
make notebook-run
```

### Notebook Execution (Quick)
```bash
make notebook-run-full
```

### Chart Generation
```bash
# Greedy run charts (feature_health, feature_outcome, distribution, contract_faceted)
PYTHONPATH=src uv run python -m bid_euchre.reporting.chart_runner \
  --run-dir data/runs/canonical_bidless_dataset_greedy_42_20260204_221121 \
  --output-dir <out> --suite all --dpi 150

# Zoom run charts (strategy_matchup incl. self_play_by_contract)
PYTHONPATH=src uv run python -m bid_euchre.reporting.chart_runner \
  --run-dir data/runs/canonical_bidless_outcomes_zoom_42_20260204_222712 \
  --output-dir <out> --suite strategy_matchup --dpi 150
```

### Full Validation
```bash
make check
```

---

## 11. References

- [GLUTTON_VS_GREEDY_EVALUATION.md](../02_agent/GLUTTON_VS_GREEDY_EVALUATION.md) — Detailed glutton vs greedy head-to-head analysis
- [DIAGNOSTIC_TRICKS_EVALUATION.md](../02_agent/DIAGNOSTIC_TRICKS_EVALUATION.md) — Full diagnostic Ridge regression results
- [PLAY_POLICY_FREEZE.md](../02_agent/PLAY_POLICY_FREEZE.md) — Play policy freeze gate methodology
- [CANONICAL_BIDLESS.md](../02_agent/CANONICAL_BIDLESS.md) — Canonical bidless experiment workflow
- [CANONICAL_BIDLESS_RUNS.md](../02_agent/CANONICAL_BIDLESS_RUNS.md) — Blessed runs registry with promotion history
