# Contract Selection Oracle Analysis

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Date:** 2026-03-01 (v1); 2026-03-03 (v2 update)
**Purpose:** Measure oracle contract mix and regret distribution to determine whether a calibrator for HIGH/LOW contract selection is warranted

---

## Executive Summary

The HybridOLSa bidder selects suit contracts 98.3% of the time. This analysis
measures the gap between the model's contract selection and a hindsight-optimal
oracle using 40,000 paired hands (QUICK mode, all 4 seats).

**V2 update:** With bid-level search (v2 policy), the model now bids on ~96%
of hands (up from ~20% in v1), fundamentally changing the regret decomposition.
Pass-threshold regret is no longer dominant; contract-selection regret is now
the primary source.

**Key findings:**

- **Oracle HIGH+LOW share: 31.9%** vs model's ~1.4% — HIGH/LOW remain
  massively under-selected
- **CS regret share: 90.9%** — contract-selection is now the dominant regret
  source (was 16.9% pre-v2)
- **Decision gate fires: CALIBRATOR_WARRANTED** — and the v2 regret
  decomposition now supports this: the model bids on most hands but picks
  the wrong contract

**V2 regret shift:** Bid-level search resolved the pass-threshold problem by
finding profitable bid levels for marginal hands. The remaining regret is
concentrated in contract mis-ranking — the model selects suit 98.3% of the
time while the oracle would select HIGH/LOW 31.9% of the time.

**Implication:** The dominant remaining regret source is feature poverty for
HIGH/LOW (1 feature each), which prevents the model from identifying hands
where non-suit contracts are optimal. R1 feature enrichment addresses this
directly.

**Note:** The v1 results below are retained for context. The v1 analysis
was conducted before bid-level search was adopted. The v2 CS regret share
of 90.9% supersedes the v1 decomposition for decision-making purposes.

---

## 1. Motivation

The R0 evaluation report ([model_arc_r0.md](model_arc_r0.md))
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
- **bid_n** — v2 uses bid-level search (compute_best_bid) to evaluate all
  legal bid levels and select the one maximizing expected utility; v1 used
  floor(mu)
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

*^A Contract rows: % among non-pass hands. PASS row: % among all hands.*

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

### 3.6 V2 Update: Bid-Level Search Impact

With bid-level search (v2 policy, PR #497), the regret decomposition shifts
fundamentally:

- **Model bid_rate:** ~96% (up from ~20% in v1) — bid-level search finds
  profitable bid levels for most hands
- **CS regret share: 90.9%** — contract-selection is now the dominant regret
  source (was 16.9% in v1)
- **Pass-threshold regret:** No longer dominant — bid-level search resolved
  the model conservatism problem identified in v1

The v2 oracle confirms that the remaining regret is concentrated in contract
mis-ranking: the model still selects suit 98.3% of the time, while the oracle
would select HIGH/LOW for 31.9% of biddable hands. This shifts the R1 priority
from "bid more hands" to "bid the right contract type."

## 4. Interpretation

### 4.1 V2 Context: Contract Selection Is Now the Binding Constraint

With v2 bid-level search, the model now bids on ~96% of hands — the
pass-threshold problem identified in v1 is largely resolved by finding
profitable bid levels for marginal hands. The dominant remaining problem
is contract mis-ranking: the model selects suit for nearly all hands while
the oracle would select HIGH/LOW for 31.9% of biddable hands.

The mechanism: the HIGH model has 1 feature (offsuit_aces) and the LOW model
has 1 feature (offsuit_tens_count). These sparse specifications produce
utility predictions that rarely compete with the 3-feature suit model,
even when HIGH/LOW would actually be the better contract. The remaining
regret is a **feature poverty problem**, addressable through R1 feature
enrichment.

**V1 context (retained):** Before bid-level search, the dominant finding was
that the model declined to bid on 80% of hands where the oracle would profit.
This was a model-accuracy problem manifesting as pass-threshold regret (81.9%).
Bid-level search resolved this by finding profitable bid levels at lower bid
amounts (e.g., bidding 5 instead of passing when floor(mu)=4 yields negative
utility but bid_n=5 yields positive utility at a lower bid).

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

### 4.4 Calibrator Alone Is Insufficient (V1 Analysis)

**Note:** This section reflects the v1 analysis. In v2, bid-level search
resolved the pass-threshold problem, and the CS regret share rose to 90.9%.
A calibrator addressing contract mis-ranking is now more relevant than in v1,
though the root cause remains feature poverty for HIGH/LOW.

A calibrator (Option C from the sub-plan) re-ranks contracts among the 6
candidates at bid time. In v1, if all 6 predicted utilities were <= 0, the
model passed regardless of ranking, and the calibrator would address at most
the 17% contract-selection slice. In v2, the model bids on ~96% of hands, so
the calibrator would address the 90.9% CS regret share — but the underlying
feature poverty means re-ranking alone cannot produce accurate HIGH/LOW
predictions. Better features (R1) remain the primary remedy.

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

### 5.2 Decision: Path B + B0 Threshold Tuning

**Selected:** Path B (skip calibrator) + Path C sidecar (threshold tuning).
Decision made 2026-03-01; see `plans/MASTER_PLAN.md` Phase B.

**Path B — Skip calibrator, finalize R0, address in R1:**
- Calibrator addresses only 17% of regret → disproportionate effort
- R1 feature enrichment addresses the dominant regret source (feature poverty)
- Fastest path to R1

**B0 — Pass-threshold tuning (added as pre-registered protocol):**
- A pre-registered sweep of the pass threshold `t` (where `utility <= -t → pass`)
  on the existing oracle data, split 60/40 by deal_id
- Protocol: `plans/r0_pass_threshold_protocol.md` (v1)
- Quick analysis (~1 notebook), doesn't require new models
- If meaningful improvement found (SESOI = 0.05 net_diff), threshold is adopted
  as an R0 hyperparameter before report finalization

### 5.3 Impact on R1 Design

With v2 bid-level search resolving the pass-threshold problem, R1 feature
design should prioritize:

- **HIGH/LOW feature enrichment:** The 1-feature models are clearly
  insufficient. The CS regret share of 90.9% is now almost entirely
  attributable to HIGH/LOW feature poverty. `min_improvement` threshold in
  feature selection may need lowering for non-suit contracts.
- **Cross-contract calibration:** A unified regression (Option B from the
  sub-plan) may be worth revisiting in R1, since the feature poverty and
  calibration problems interact.
- **Normalizer interaction:** The normalizer screen (NO_GO_DEFER_R1) found
  +4% accuracy but -0.269 net_eppd. With richer R1 features, normalization
  may become beneficial. See [normalizer_offline_screen.md](normalizer_offline_screen.md).

## 6. Arc Context

```
R0 training (#396)
  |
  +---> Model eval report (model_arc_r0.md)
  |       98.3% suit / 0.9% low / 0.8% high observed
  |
  +---> Contract selection oracle (this report, #472)
  |       Oracle H+L: 31.9%, mean regret: 3.92
  |       Pass-threshold dominates (82% of regret)
  |
  +---> Phase B decision: Path B + B0
  |       B0: threshold tuning (pre-registered protocol)
  |       B1: SKIPPED (calibrator addresses only 17%)
  |       B3: R0 report finalization (after B0 resolves)
  |
  +---> R1 training cycle (PR-R1a)
          Feature enrichment for HIGH/LOW
          Re-tune threshold t per-rung
```

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A (diagnostic analysis; informs Phase B decision) |
| Notebook | notebooks/arc_d/r0/55_contract_selection_oracle.py |
| Model artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| Dataset | canonical_bidless_dataset_glutton_42_20260221_175752 |
| Git SHA (v1) | 81d96bfb8f2702651c4eb1331a31c7d4a1ef8f2f |
| Seed | 42 (dataset generation) |
| n_hands | ~40,000 (QUICK mode: 10k deals x 4 seats) |
| Bootstrap | 10,000 resamples, seed 42 |
| Sub-plan | plans/contract_selection_analysis.md (v3) |
| PR (v1) | #472 |
| V2 update | PR #497 (bid-level search in oracle), CS regret share 90.9% |

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
