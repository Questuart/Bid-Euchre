# Contract Selection Oracle Analysis

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Date:** 2026-03-01
**Purpose:** Measure oracle contract mix and regret distribution to determine whether a calibrator for HIGH/LOW contract selection is warranted

---

## Executive Summary

The HybridOLSa bidder selects suit contracts 98.3% of the time. This analysis
measures the gap between the model's contract selection and a hindsight-optimal
oracle using 40,000 paired hands (QUICK mode, all 4 seats).

**Key findings:**

- **Oracle HIGH+LOW share: 31.9%** vs model's 1.4% — HIGH/LOW are massively
  under-selected
- **Mean total regret: 3.92 utility** [3.89, 3.95] — far above the 0.1
  decision threshold
- **Decision gate fires: CALIBRATOR_WARRANTED** — but the regret decomposition
  reveals the dominant source is *not* contract selection

**Regret decomposition (the critical insight):**

| Category | % of hands | % of total regret | Interpretation |
|----------|-----------|-------------------|----------------|
| Pass-threshold | 73.2% | **81.9%** | Model passes; oracle would bid |
| Contract-selection | 11.9% | 16.9% | Both bid; model picks wrong contract |
| Over-bidding | 0.5% | 1.1% | Model bids; oracle would pass |

The model passes on **80.1%** of hands vs the oracle's **7.4%**. The primary
problem is model conservatism (negative predicted utility on hands that would
actually profit), not contract mis-ranking among biddable hands.

**Implication:** A calibrator that only re-ranks contracts (Option C from the
sub-plan) would address at most 17% of the regret. The dominant win comes from
improving model accuracy — particularly for HIGH/LOW, which have only 1 feature
each — or adjusting the pass/bid threshold.

---

## 1. Motivation

The R0 evaluation report ([model_arc_r0_20260224.md](model_arc_r0_20260224.md))
showed a stark contract distribution:

| Contract | Deals | Pct |
|----------|-------|-----|
| suit | 31,070 | 98.3% |
| low | 281 | 0.9% |
| high | 261 | 0.8% |

Whether this distribution is problematic depends on the **oracle contract mix**
— the distribution that maximizes net payoff when the same hand is evaluated
under all 6 contracts with hindsight. The sub-plan
(plans/contract_selection_analysis.md) identified four hypothesized root causes
and specified this Step 0 oracle/regret analysis as the prerequisite for any
corrective action.

The decision this analysis informs: should we build a calibration layer
(Steps 1-2) before finalizing R0 reports and beginning R1, or proceed with
the current model?

## 2. Methodology

### 2.1 Data Design

**Paired bidless dataset:** Each of 10,000 deals was played 6 times — once per
contract (suit-C, suit-D, suit-H, suit-S, HIGH, LOW) — with identical physical
hands across scenarios (`pair_deals: true`). All players use GluttonStrategy
(greedy play, no bidding). This yields 10,000 deals x 4 seats = 40,000
independent hand observations, each with 6 paired outcomes.

**Data source:** canonical_bidless_dataset_glutton_42_20260221_175752 (single-policy,
seed 42)

### 2.2 Construction Path

Following the 4-step construction path from the sub-plan:

1. **Filter:** Single-policy glutton run (eliminates strategy_id ambiguity)
2. **Join:** `join_features_outcomes()` from datasets/join.py — joins bidless
   features (per-seat) with outcomes (per-deal) on `(hand_id, contract_type,
   trump_suit)`, derives per-seat `tricks_won` via team membership
3. **Pivot:** Widen on `contract_key` → 6 outcome columns per `(deal_id, seat)`
4. **Validate:** Assert 6 rows per group pre-pivot; drop incomplete groups

### 2.3 Model Predictions

For each hand and each of the 6 contracts, compute:

- **mu** — OLS predicted tricks from the constrained-arm model (hybrid_r0.json)
- **bid_n** = floor(mu) — the bid the model would place
- **predicted_utility** = compute_ev(mu, sigma, bid_n) — Gaussian expected
  net-differential (matching bidding.py:910-952)

Since risk_lambda = 0 at R0, utility = EV (no CVaR penalty).

**Per-contract model specifications:**

| Contract | Features | sigma |
|----------|----------|-------|
| suit | bowers, trump_count, offsuit_aces (3) | 1.530 |
| high | offsuit_aces (1) | 1.697 |
| low | offsuit_tens_count (1) | 1.702 |

### 2.4 Oracle Definition

The oracle is a hindsight-optimal decision-maker:

1. For each contract, compute `actual_net` using the **model's bid_n** but
   **actual tricks won**:
   - Make (tricks >= bid_n): `net = 2 * tricks - 10`
   - Set (tricks < bid_n): `net = tricks - bid_n - 10`
2. Select the contract with highest `actual_net`
3. Pass if `max(actual_net) <= 0`

The oracle uses the model's bid levels (not optimal bids) to isolate
**contract selection** regret from **bid amount** regret.

### 2.5 Regret and Decomposition

**Regret** = oracle_actual_net - model_actual_net (per hand, always >= 0).

**3-way decomposition** classifies each hand by the (model passes?, oracle
passes?) matrix plus contract agreement:

| Model | Oracle | Category |
|-------|--------|----------|
| Pass | Pass | Correct (both pass) |
| Pass | Bid | Pass-threshold error |
| Bid | Pass | Over-bidding error |
| Bid (same) | Bid (same) | Correct (same contract) |
| Bid (X) | Bid (Y, Y!=X) | Contract-selection error |

### 2.6 Statistical Method

- **Bootstrap 95% CIs:** 10,000 resamples (seed 42) for mean regret and
  contract-selection-only regret
- **Sample size:** 40,000 hands (QUICK mode) — exceeds the 2,000 minimum for
  bias detection and the 1,000 minimum for group-level inference

## 3. Results

### 3.1 Regret Summary

| Metric | Value | 95% CI |
|--------|-------|--------|
| Mean total regret | 3.92 | [3.89, 3.95] |
| Median regret | 4.00 | — |
| P95 regret | 8.00 | — |
| Zero-regret hands | 16.2% | — |

### 3.2 Regret Decomposition

| Category | Hands | % Hands | Mean Regret | % Total Regret |
|----------|-------|---------|-------------|----------------|
| Pass-threshold | 29,277 | 73.2% | 4.39 | **81.9%** |
| Contract-selection | 4,760 | 11.9% | 5.57 | 16.9% |
| Correct (both pass) | 2,770 | 6.9% | 0.00 | 0.0% |
| Correct (same contract) | 2,989 | 7.5% | 0.00 | 0.0% |
| Over-bidding | 204 | 0.5% | 8.78 | 1.1% |

> See notebook 55_contract_selection_oracle, S4b for the full decomposition
> with exact counts.

### 3.3 Oracle Contract Mix

| Contract | Oracle % | Model % | Delta |
|----------|----------|---------|-------|
| suit | 68.1% | 98.6% | -30.5pp |
| high | 14.0% | 0.6% | +13.4pp |
| low | 17.9% | 0.8% | +17.1pp |
| PASS | 7.4% | 80.1% | -72.7pp |

**Oracle HIGH+LOW combined share: 31.9%** (among non-pass hands) vs model's
1.4%.

> See notebook 55_contract_selection_oracle, S7 bar chart for the visual
> comparison of oracle vs model contract mix.

### 3.4 Contract-Selection-Only Regret

Restricted to hands where both model and oracle bid (n = 7,749, 19.4% of total):

| Metric | Value | 95% CI |
|--------|-------|--------|
| Mean CS regret | 3.42 | [3.30, 3.54] |
| Wrong contract rate | 61.4% | — |

Even among hands where the model bids, it picks the wrong contract ~60% of
the time. However, this population is only ~20% of all hands; the other ~80%
never reach the contract comparison because the model passes.

### 3.5 Key Visualizations

> **Oracle Actual Net vs Model Predicted Utility (S7b):** Scatter plot showing
> the relationship between what the model predicts and what actually happens.
> The massive red cluster at predicted utility <= 0, oracle net >> 0 visualizes
> the pass-threshold population. The right panel zooms into the bidding region
> where contract-selection errors (orange) are visible.

> **Regret Heatmap (S7c):** Confusion-matrix heatmaps of mean regret and total
> regret contribution by (model family -> oracle family). The pass->suit and
> pass->high cells dominate the total regret heatmap, confirming the
> decomposition numerically.

> **Regret Distribution (S7):** Bimodal histogram — a spike at zero (correct
> hands) and a broad distribution centered around 4-6 utility (error hands).
> The non-zero regret panel shows the error population in isolation.

## 4. Interpretation

### 4.1 The Model Is Too Conservative, Not Wrong About Contracts

The dominant finding is **not** that the model mis-ranks contracts. It is that
the model declines to bid on 80% of hands where the oracle would profit. This
is a model-accuracy problem, not a contract-comparison problem.

The mechanism: when the OLS model predicts mu = 3.5 for a hand, the Gaussian
EV computation at bid_n = 3 with sigma ~1.6 yields negative utility (the
probability mass below the make threshold is too large). The model passes. But
the actual outcome might be 5 or 6 tricks — well above the bid. The model's
**trick predictions are systematically low** for hands it declines.

### 4.2 Feature Poverty Is the Proximate Cause

The HIGH model has 1 feature (offsuit_aces), producing ~9 discrete mu values.
The LOW model has 1 feature (offsuit_tens_count), similarly constrained. These
models cannot distinguish:

- "4 aces across 4 suits" (excellent for HIGH) from "4 aces in one suit"
  (better as suit)
- "Strong low cards with distributional advantage" from "scattered low cards"

The suit model (3 features) is somewhat better but still produces low mu
predictions for many hands that would actually make their contract.

### 4.3 Multi-Candidate Advantage Is Real But Secondary

The sub-plan hypothesized that suit gets a structural advantage from having 4
correlated evaluations vs 1 for HIGH/LOW (hypothesis #1). The oracle mix
confirms this gap exists (suit oracle share is 68% vs 98.6% model share), but
the *primary* mechanism suppressing HIGH/LOW is not that suit out-competes them
in utility ranking — it's that HIGH/LOW utilities are almost always negative,
so they never even enter the competition.

### 4.4 Calibrator Alone Is Insufficient

A calibrator (Option C from the sub-plan) re-ranks contracts among the 6
candidates at bid time. But if all 6 predicted utilities are <= 0, the model
passes regardless of ranking. The calibrator would address at most the 17%
contract-selection slice. The 82% pass-threshold slice requires either:

1. **Better models:** More features for HIGH/LOW (and possibly suit) to produce
   higher, more accurate mu predictions
2. **Threshold adjustment:** Lowering the utility <= 0 pass gate
3. **Both:** Better predictions + recalibrated threshold

### 4.5 Limitations and Caveats

**Auction independence:** The oracle evaluates each seat independently, assuming it
can unilaterally declare any contract. In actual play, only one team wins the auction
per deal, and the winning bid must exceed the current high bid. The oracle does not
model auction competition — it asks "if this seat could declare, which contract
maximizes net payoff?" not "would this seat win the auction?" Consequences:

- The oracle's 7.4% pass rate is per-seat. In actual play, the effective pass rate
  would be higher because some profitable hands lose the auction to opponents.
- The 82% pass-threshold regret is therefore an **upper bound** on recoverable
  regret — even with a perfect model, some of those hands would not win the auction.
- Two seats on the same team may receive different oracle recommendations. The oracle
  does not model intra-team bid coordination.

This simplification is deliberate: it isolates contract selection quality from auction
dynamics, which is the specific question Step 0 was designed to answer. An
auction-aware oracle would require a full game simulation with strategic bidding,
which would conflate contract choice regret with auction strategy regret.

**Sample size:** The analysis uses QUICK mode (40,000 hands = 10,000 deals × 4
seats). The sub-plan acceptance gate specified ≥50,000 paired hands. The shortfall
does not affect the decision: mean regret is 3.92 with 95% CI [3.89, 3.95] — the
signal is 40× above the 0.1 decision threshold, so additional samples would narrow
an already-tight CI without changing the conclusion. A FULL-mode run (200,000 hands)
can be produced for archival purposes if desired.

## 5. Impact & Decisions

### 5.1 Decision Gate Result

**Formal gate: CALIBRATOR_WARRANTED** (mean regret 3.92 >> 0.1 threshold).

However, the regret decomposition fundamentally changes the interpretation.
The plan assumed the regret — if large — would come from contract mis-ranking,
motivating a calibrator. Instead, 82% comes from the pass threshold. The gate
result is technically correct but the prescribed remedy (calibrator) addresses
only the minority of the problem.

### 5.2 Recommendation for Phase B

Three paths forward, presented for decision-maker review:

**Path A — Build calibrator anyway (original plan B1-B2):**
- Addresses 17% of regret
- Delays R0 finalization and R1 start
- Risk: effort may be disproportionate to gain

**Path B — Skip calibrator, finalize R0, address in R1:**
- Accept current contract selection for R0
- R1 feature enrichment (already planned) addresses HIGH/LOW feature poverty
- Pass-threshold tuning can happen independently
- Fastest path to R1

**Path C — Targeted pass-threshold analysis (new intermediate step):**
- Investigate whether threshold tuning alone (e.g., utility <= -X instead of
  <= 0) captures a meaningful share of the 82% pass-threshold regret
- Quick analysis (~1 notebook), doesn't require new models
- If threshold tuning captures significant value, implement as a targeted fix
  before R0 finalization

### 5.3 Impact on R1 Design

Regardless of Phase B path, R1 feature design should prioritize:

- **HIGH/LOW feature enrichment:** The 1-feature models are clearly
  insufficient. `min_improvement` threshold in feature selection may need
  lowering for non-suit contracts.
- **Cross-contract calibration:** A unified regression (Option B from the
  sub-plan) may be worth revisiting in R1, since the feature poverty and
  calibration problems interact.

## 6. Arc Context

```
R0 training (#396)
  |
  +---> Model eval report (model_arc_r0_20260224.md)
  |       98.3% suit / 0.9% low / 0.8% high observed
  |
  +---> Contract selection oracle (this report)
  |       Oracle H+L: 31.9%, mean regret: 3.92
  |       Pass-threshold dominates (82% of regret)
  |
  +---> Phase B decision (pending)
  |       Path A: calibrator → re-runs → finalize R0
  |       Path B: skip calibrator → finalize R0 → R1
  |       Path C: threshold analysis → decide → finalize R0
  |
  +---> R1 training cycle (PR-R1a)
          Feature enrichment for HIGH/LOW
```

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A (diagnostic analysis; informs Phase B decision) |
| Notebook | notebooks/arc_d/r0/55_contract_selection_oracle.py |
| Model artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| Dataset | canonical_bidless_dataset_glutton_42_20260221_175752 |
| Git SHA | 81d96bfb8f2702651c4eb1331a31c7d4a1ef8f2f |
| Seed | 42 (dataset generation) |
| n_hands | ~40,000 (QUICK mode: 10k deals x 4 seats) |
| Bootstrap | 10,000 resamples, seed 42 |
| Sub-plan | plans/contract_selection_analysis.md (v3) |
| PR | #472 |

## 8. Reproduction

```bash
# Sync notebook from .py source
uv run jupytext --to ipynb --output \
  notebooks/arc_d/r0/55_contract_selection_oracle.ipynb \
  notebooks/arc_d/r0/55_contract_selection_oracle.py

# Run in QUICK mode (40k hands, ~2 min)
uv run papermill \
  notebooks/arc_d/r0/55_contract_selection_oracle.ipynb \
  /dev/null -p MODE QUICK

# Run in FULL mode (200k hands, ~10 min) — for production-grade CIs
uv run papermill \
  notebooks/arc_d/r0/55_contract_selection_oracle.ipynb \
  /dev/null -p MODE FULL
```

**Data prerequisite:** The paired bidless dataset must exist at
data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/.
This is generated by the canonical bidless experiment config
(experiments/configs/canonical_bidless_dataset_glutton.yaml) with seed 42.
