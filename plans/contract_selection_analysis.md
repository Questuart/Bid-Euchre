# Contract Selection Analysis: HIGH/LOW Under-Selection in OLSa

**Date:** 2026-02-28
**Status:** Plan document complete (v3), Step 0 execution NOT STARTED
**Context:** R0 eval data shows 98.3% suit / 0.9% low / 0.8% high contract selection.

---

## Problem Statement

The OLSa and HybridOLSa bidders almost never select HIGH or LOW contracts. The R0 eval report (`docs/04_reports/r0/model_arc_r0_20260224.md`) shows:

| Contract | Deals | Pct |
|----------|-------|-----|
| suit | 31,070 | 98.3% |
| low | 281 | 0.9% |
| high | 261 | 0.8% |

Whether this is a problem — and how large — depends on the **oracle contract mix**: the contract distribution that maximizes net EPPD when the same hand is evaluated under all 6 contracts. The oracle mix is currently unknown and must be measured empirically from paired data before setting a target. The 98.3/0.9/0.8 split may or may not be close to optimal; the goal is to measure the gap, not to assume one.

## Root Cause Hypotheses

Four potential compounding causes, ordered by estimated severity. **All require empirical validation** via the regret analysis in the next steps.

### 1. Multi-Candidate Selection Advantage for Suit (Structural — Hypothesized HIGH)

The bidder evaluates 6 candidates: C, D, H, S, HIGH, LOW, and picks the best. Suit contracts get **4 correlated-but-distinct evaluations** from a shared OLS model with different feature vectors (each suit produces different trump/bower/offsuit splits). HIGH and LOW each get **1 evaluation**. The max of 4 correlated draws tends to exceed the max of 1 draw, creating a structural advantage for suit selection.

**Caveat:** The 4 suit draws are highly correlated (same model, overlapping features), so the effect is weaker than 4 independent draws. The magnitude of this bias is unknown without measurement.

### 2. Feature Poverty in HIGH/LOW Models (Model Capacity — Hypothesized HIGH)

Forward feature selection (`feature_selection.py`, `min_improvement=0.005`) selected only:

| Contract | OLSa features | OLSa_Full features |
|----------|--------------|-------------------|
| suit | 3 (bowers, trump_count, offsuit_aces) | 3 (hand_value, quick_tricks, low_card_count) |
| high | 1 (offsuit_aces) | 2 (offsuit_non_ace_count, offsuit_best_rank_sum) |
| low | 1 (offsuit_tens_count) | 2 (offsuit_tens_count, offsuit_best_rank_sum) |

The HIGH model produces ~9 discrete μ values (one per ace count). It cannot distinguish "4 aces spread across 4 suits" (excellent for HIGH) from "4 aces concentrated in 1 suit" (better as suit). The suit model, with 3 features, produces a richer prediction surface and can spike higher for strong hands.

### 3. Higher Outcome Variance Penalizes HIGH/LOW (HybridOLSa — Hypothesized MEDIUM)

Outcome standard deviations from the R0 report:

| Contract | σ(tricks_won) |
|----------|--------------|
| suit | 2.50 |
| high | 3.14 |
| low | 3.21 |

For HybridOLSa specifically, this creates a **double penalty**:
- Larger residual σ → more probability mass below the make threshold → lower Gaussian EV
- Larger downside tail → higher CVaR₅% penalty × risk_lambda

Two contracts with identical μ and bid_n will produce different utilities, systematically favoring suit.

### 4. No Cross-Contract Calibration (Model Design — Hypothesized MEDIUM)

Each contract family's OLS model is trained independently on its own data. A μ=5.5 prediction from the suit model and μ=5.5 from the HIGH model are not trained to be comparable — they're predictions on different scales from models that never saw each other's data. The cross-contract comparison assumes commensurability that doesn't exist.

## Decision Objective Alignment

**Critical constraint:** Any contract selection improvement must align with the HybridOLSa runtime decision objective, which is **not** raw tricks but:

```
utility = EV(mu, sigma, bid_n) - CVaR_penalty(mu, sigma, bid_n)
```

Where EV uses the asymmetric net-differential payoff:
- **Make** (tricks >= bid): `net = 2 * tricks - 10`
- **Set** (tricks < bid): `net = tricks - bid - 10`

And the bidder **passes** if `best_utility <= 0` (`bidding.py:1043`).

This means:
- Maximizing "most tricks" can **hurt** net EPPD if it increases set frequency
- The calibrator/regret analysis must target **utility** (or net EPPD), not raw tricks
- "Pass" must be a valid action in the selection model — not just "which contract" but "should we bid at all under this contract"

## Possible Solutions

Three architectural options were evaluated:

### Option A: Best-Contract Classifier

- **Approach:** Single classifier predicting `P(best_contract | hand)` from contract-agnostic features
- **Training label:** Which contract maximizes utility (requires paired data + utility computation)
- **Pros:** Directly optimizes contract selection; eliminates multi-candidate bias
- **Cons:** Loses trick-count prediction (can't determine bid amount); doesn't capture margin of advantage; must handle "pass" as an action class
- **Invasiveness:** Full rewrite of bidding pipeline

### Option B: Unified Regression (Contract as Feature)

- **Approach:** Single OLS model with contract type encoded as input features + interaction terms
- **Called 6 times** per hand (once per candidate contract), outputs comparable μ values
- **Pros:** Inherently calibrated; one model learns when HIGH/LOW beats suit; still outputs tricks
- **Cons:** Single linear model may lack capacity for 3 very different contract dynamics (bowers/ruffing vs no-trump)
- **Invasiveness:** Moderate rewrite of training + bidding

### Option C: Per-Contract Models + Calibration Layer

- **Approach:** Keep existing 3 OLS models, add a learned calibration layer that transforms 6 raw μ values (+ σ, bid_n) into comparable utility scores
- **Training data:** Paired outcomes from canonical single-policy runs (same hand under all 6 contracts)
- **Pros:** Preserves existing models (proven, interpretable); calibration layer handles cross-contract comparison
- **Cons:** Two-stage training; calibrator limited by what per-contract models provide; requires decisions on tie-handling, pass action, and bid-level coupling (see Open Design Questions below)
- **Invasiveness:** Additive new component, but non-trivial integration with existing `choose_bid()` logic

## Recommendation

**Start with the regret/oracle analysis (Step 0), then evaluate Option C.**

The analysis is prerequisite because:
1. We don't know the oracle contract mix — the problem may be smaller (or larger) than assumed
2. Regret faceted by `(chosen, oracle_best)` quantifies exactly where tricks are lost
3. The regret distribution informs whether a calibrator has enough signal to improve on argmax

## Data Scope and Join Specification

Paired data must come from **canonical single-policy runs only** to avoid confounding play quality with contract selection.

- **Source config:** `canonical_bidless_dataset_glutton.yaml` (single-policy, `pair_deals: true`)
- **NOT** mixed-play configs (`canonical_bidless_dataset_mixed_play.yaml`), which carry multiple `strategy_id`/`matchup_id` values per deal

### Schema Reality

The two dataset tables have **complementary but non-overlapping key columns:**

| Column | `bidless.parquet` | `bidless_outcomes.parquet` |
|--------|:-:|:-:|
| `hand_id` | yes | yes |
| `deal_id` | yes | yes |
| `seat` | yes | **no** |
| `strategy_id` | **no** | yes |
| `contract_type` | yes | yes |
| `trump_suit` | yes | yes |
| `tricks_team0/1` | **no** | yes |
| `hand_features` | yes | **no** |

This means a single direct join on `(deal_id, seat, strategy_id)` is **not possible**. The construction path must be:

### Step 0 Construction Path

```
1. FILTER: Use only the canonical single-policy glutton run directory.
   This ensures a single strategy_id, eliminating mixed-policy ambiguity
   without needing strategy_id as a join key.

2. JOIN (existing): Use join_features_outcomes() from datasets/join.py.
   This joins bidless (per-seat) ↔ outcomes (per-hand) on
   (hand_id, contract_type, trump_suit), deduplicates outcomes,
   and derives per-seat tricks_won from team membership:
     seats 0,2 → tricks_team0
     seats 1,3 → tricks_team1
   Output: one row per (hand_id, seat) with contract_type, features, tricks_won.

3. PIVOT: Widen the joined table on (contract_type, trump_suit).
   Group by (deal_id, seat), pivot tricks_won into 6 columns:
     tricks_suit_C, tricks_suit_D, tricks_suit_H, tricks_suit_S,
     tricks_HIGH, tricks_LOW
   This produces one row per (deal_id, seat) with all 6 outcomes.

4. VALIDATE: Assert each (deal_id, seat) group has exactly 6 rows
   pre-pivot (one per scenario). Drop incomplete groups with a warning.
```

**Why this works:** The canonical glutton config is single-policy, so the `join.py` dedup on `(hand_id, contract_type, trump_suit)` is unambiguous — there's only one strategy producing outcomes. The `pair_deals: true` setting ensures deal_id 0 across all 6 scenarios received identical physical hands, making the pivot semantically valid.

## Open Design Questions

These must be resolved before prototyping a calibrator:

1. **Tie-handling for oracle best_contract:** When two contracts yield the same tricks_won, which is "best"? Options: (a) any is acceptable (multi-label), (b) prefer suit (conservative), (c) prefer higher utility after EV computation.

2. **Pass as an action:** The calibrator must integrate with the `utility <= 0 → pass` gate. Should the calibrator output a utility that feeds into the existing pass gate, or should it have its own pass decision?

3. **Bid-level coupling:** The calibrator sees μ values, but bid_n = floor(μ) and utility depends on bid_n. If the calibrator re-ranks contracts, the bid amount must be re-derived. A contract switch from suit (μ=5.8, bid 5) to HIGH (μ=5.5, bid 5) has different EV profiles.

4. **Auction context:** `current_high_bid` constrains which contracts can even be selected (bid_n must exceed it). The calibrator must respect this filter, not override it.

## Acceptance Gates

### Step 0: Oracle/Regret Analysis (offline)

**Pass criteria:**
- Oracle contract mix computed from ≥50,000 paired hands
- Regret distribution reported: mean, P50, P95, faceted by `(chosen, oracle_best)`
- If oracle mix shows HIGH/LOW < 3% combined, the problem is smaller than hypothesized — document and reassess

### Step 1: Calibrator Prototype (offline)

**Pass criteria:**
- Calibrator trained on 80% of paired data, evaluated on held-out 20%
- **Non-regression:** calibrator-selected contracts must achieve net EPPD ≥ current argmax net EPPD on held-out data (within bootstrap 95% CI)
- **Contract mix shift:** calibrator must produce a measurably different contract distribution (chi-squared test, p < 0.05)
- **Pass rate stability:** pass rate within ±2pp of current OLSa pass rate
- Unit tests for tie-handling, pass integration, and auction-context filtering

### Step 2: H2H Validation (online)

**Pass criteria:**
- H2H battery: calibrated bidder vs uncalibrated bidder, ≥2,000 deals per matchup
- Net EPPD delta ≥ 0 (non-negative, bootstrap 95% CI excludes large negative values)
- Make rate within ±3pp of baseline
- Contract mix reported alongside net EPPD for interpretability

## Suggested Next Steps

1. **Oracle/regret analysis (Step 0)** — Follow the construction path in §Data Scope: filter to canonical glutton run, join via `join_features_outcomes()`, pivot wide on contract_type. Compute oracle `best_contract` per hand (by utility, not raw tricks). Measure regret. Report oracle contract mix. This determines whether the problem warrants further investment.

2. **Feature selection review** — If Step 0 confirms a meaningful gap, consider lowering `min_improvement` threshold for HIGH/LOW, or using AIC/BIC instead of R² delta, to allow more features into those models. This is independent of and complementary to a calibrator.

3. **Calibrator prototype (Step 1)** — If Step 0 shows mean regret > 0.1 utility (NOT tricks — see §Decision Objective Alignment), train a calibrator on paired outcomes using μ-values + σ + bid_n as input, targeting utility-maximizing contract. Resolve open design questions first.

4. **H2H validation (Step 2)** — Wire calibrator into `HybridOLSaBidder.choose_bid()` and run H2H battery against uncalibrated baseline.

## Key Files

| File | Relevance |
|------|-----------|
| `src/bid_euchre/strategy/bidding.py` | All bidder implementations; `OLSaBidder` (L691), `HybridOLSaBidder` (L778), utility/pass logic (L1027–1046) |
| `src/bid_euchre/features/hand_eval.py` | Feature extraction (`get_hand_features`, 39 features) |
| `src/bid_euchre/models/feature_selection.py` | Forward selection with GroupKFold, `min_improvement=0.005` |
| `src/bid_euchre/models/train_hybrid_olsa.py` | OLSa training pipeline, per-contract split |
| `src/bid_euchre/datasets/bidless_outcomes.py` | Outcome dataset with `strategy_id`/`matchup_id` columns (L85–88) |
| `src/bid_euchre/datasets/join.py` | Feature-outcome join with dedup logic (L48–52) |
| `experiments/configs/canonical_bidless_dataset_glutton.yaml` | Training data config, `pair_deals: true`, single-policy |
| `experiments/run_experiment.py` | Deal pairing logic (L755–760) |
| `src/bid_euchre/sim/deals.py` | Deterministic deal generation (`seed * 1_000_003 + deal_id`) |
| `docs/04_reports/r0/model_arc_r0_20260224.md` | R0 report with contract selection frequencies |

## Review Log

| Date | Reviewer | Findings | Resolution |
|------|----------|----------|------------|
| 2026-02-28 | Agent review | 6 findings (2×P1, 4×P2) | v2: all addressed — see below |
| 2026-02-28 | Human review | 1 finding: join key spec not realizable | v3: construction path rewritten — see below |

**v2 changes (addressing review findings):**
- **[P1-1] Decision objective mismatch:** Added "Decision Objective Alignment" section. Reframed regret/calibration target from raw tricks to utility (`EV - CVaR_penalty`). Pass action explicitly included.
- **[P1-2] Join spec under-constrained:** Added "Data Scope and Join Specification" section. Locked to canonical single-policy runs. Required join keys include `strategy_id`. Referenced existing dedup logic in `join.py`.
- **[P2-1] "Independent draws" overstated:** Reworded root cause #1 to "correlated-but-distinct evaluations" with explicit caveat that magnitude is unknown without measurement.
- **[P2-2] 10–20% target ungrounded:** Removed the asserted target. Reframed problem statement around measuring the oracle mix empirically. Step 0 must establish the baseline before claiming a gap.
- **[P2-3] Option C complexity understated:** Added "Open Design Questions" section covering tie-handling, pass integration, bid-level coupling, and auction context. Removed "least invasive" and "no training pipeline changes" language.
- **[P2-4] Missing acceptance gates:** Added "Acceptance Gates" section with quantified pass/fail criteria for each step (oracle analysis, calibrator prototype, H2H validation). Includes non-regression thresholds, statistical tests, and test plan requirements.

**v3 changes (addressing human review):**
- **Join key spec not realizable:** `bidless_outcomes` has no `seat` column; `bidless` has no `strategy_id`. Replaced the impossible `(deal_id, seat, strategy_id)` join spec with a concrete 4-step construction path: (1) filter to single-policy run, (2) use existing `join_features_outcomes()` to get per-seat tricks_won, (3) pivot wide on contract_type, (4) validate 6-row completeness per group. Added schema comparison table showing which columns live where.
