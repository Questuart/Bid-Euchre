# R1 H2H Suit Regression Diagnostic

**Date:** 2026-03-05
**Status:** INVESTIGATION ONGOING — H7 contributing, H10 (bid-level search degeneracy) identified as structural cause
**Blocking:** Gate X3 (STOP), Steps 6–12 of R1 training plan
**gate_status:** X3 STOP — primary delta -0.348 (persists after two-stage remediation)
**Root cause:** H10 (bid-level search degeneracy) — structural; H7 (weight instability) contributing but not primary
**Decisive test result:** Two-stage training (PRs #548/#549) preserved base weights but did NOT fix regression. ME_R1 (hand-coded weights, no OLS) regresses by -9.5 eppd — proves problem is upstream of weight fitting. `compute_best_bid()` always selects minimum legal bid level because payoff `2t - 10` is bid-independent.
**Provenance:** H2H battery run `arc_d_r0_h2h_battery_42_20260304_210528`, seed 42, 2k deals/matchup
**Ablation run:** `arc_d_r0_h2h_battery_42_20260305_131433`, seed 42, 2k deals/matchup

## Quick Context

R1 added **partner bidding context features** (extracted from auction transcripts)
to the OLSa hybrid bidder. These features describe what the partner bid during
the auction (bid level, whether they passed, whether they bid the same contract
family). Training R² improved dramatically (+0.40 for suit), but H2H game
performance **regressed** by -0.76 pts/deal for suit contracts.

This report documents the regression, proposes hypotheses for why it happened,
and lays out a concrete investigation plan with reproduction commands.

> **Note:** The H2H battery that produced these results used models trained with
> 4 partner features (including `partner_bid_confidence`, removed in PR #538 as
> redundant with `partner_bid_level`). After investigation completes, models will
> be retrained with 3 partner features and the H2H battery re-run.

**Key files:**
- Training pipeline: `src/bid_euchre/models/train_hybrid_olsa.py`
- Runtime bidding: `src/bid_euchre/strategy/bidding.py` (HybridOLSaBidder)
- Partner feature extraction: `src/bid_euchre/features/auction_context.py`
- R1 training plan: `plans/archive/pre_v1/r1_training_plan.md`
- R1 master plan: `plans/archive/pre_v1/r1_master_plan.md`

**Investigation priority order:**

1. **F (bug audit)** — Rule out implementation bugs first. If found, fixes
   invalidate all ML conclusions. Code review + spot checks, no re-runs needed.
2. **G (training data sparsity)** — Free (parquet stats). Determines if partner
   features are learned from a tiny, non-representative sample.
3. **H (base model comparison)** — Free (artifact JSON). Determines if locked
   feature weights shifted between R0 and R1.
4. **B (bid/set rates)** — Free (log parsing). Determines if R1 over-bids in suit.
5. **E (partial R²)** — Free (training data). Quantifies partner feature leakage.
6. **C (zero-out ablation)** — Definitive test. Small code change + H2H re-run.
7. **D (distribution shift)** — May need re-run with `log_level: trick` if
   auction transcripts are not in current logs.
8. **I (training data variance)** — Free (parquet stats + sklearn). Tests whether
   R² improvement is a data artifact rather than partner feature signal.

---

## 1. Observation

R1 hybrid models regress vs R0 in H2H despite dramatically improved training R²:

| Metric | R0 | R1 | Delta |
|--------|----|----|-------|
| Suit R² (full arm) | 0.222 | 0.627 | +0.405 |
| Suit R² (constrained arm) | 0.215 | 0.618 | +0.402 |
| H2H suit delta (full, pts/deal) | — | — | **-0.758** |
| H2H suit delta (constrained, pts/deal) | — | — | **-0.683** |

The R² tripled, but game performance worsened.

### Per-Contract Decomposition

| Arm | Contract | Delta (pts/deal) | 95% CI | Significant? |
|-----|----------|-----------------|--------|-------------|
| Full | **suit** | **-0.758** | **[-0.990, -0.525]** | **Yes** |
| Full | high | -0.020 | [-0.447, +0.412] | No |
| Full | low | +0.289 | [-0.084, +0.663] | No |
| Constrained | **suit** | **-0.683** | **[-0.904, -0.459]** | **Yes** |
| Constrained | high | +0.179 | [-0.257, +0.625] | No |
| Constrained | low | +0.339 | [-0.040, +0.720] | No |

**Conclusion:** Regression is exclusively in suit contracts. High/low CIs span zero.

### Partner Features in Suit Models

| Feature | Constrained weight | Full weight |
|---------|-------------------|-------------|
| partner_bid_level | 1.292 | — |
| partner_bid_confidence | — | 12.851 |
| partner_passed | 7.110 | 7.139 |
| partner_suit_match | 2.586 | 2.677 |

High/low models only use `partner_suit_match` (weight ~3.5). Suit models use
3 partner features with large coefficients — particularly `partner_bid_confidence`
at 12.85 in the full arm.

> **Update:** `partner_bid_confidence` was removed from the feature registry
> (PR #538) as it is linearly redundant with `partner_bid_level` (= bid_level / 10).
> The full arm's 12.85 weight was an artifact of the compressed [0,1] scale.
> Investigation results above apply to the pre-removal model artifacts.

---

## 2. Hypotheses

> **Numbering note:** H2 was merged into H1 during early triage (both concerned
> distribution shift). Remaining IDs (H1, H3–H9) are stable and cross-referenced
> in `r1_master_plan.md` §10 and `r2_follow_ups.md`.

### H1: Training-Inference Distribution Shift (Primary)

**Claim:** The suit model learned partner feature distributions from R0's bidding
behavior, but at H2H inference both seats use R1 models, which bid differently.

**Mechanism:**
- Training data generated with R0 model (no partner awareness) in all seats
- R0's bid-level distribution in suit contracts defines the "normal" range for
  `partner_bid_level`, `partner_passed`, `partner_suit_match`
- At inference, R1 models (which incorporate partner features into their bids)
  produce a different bid distribution
- Large weights (12.85, 7.11) amplify even small distribution shifts into
  large prediction errors

**Testable predictions:**
- R1 suit bid-level distribution differs from R0 in self-play
- Mean `partner_bid_level` at inference differs from training data mean
- The shift magnitude × coefficient magnitude predicts the regression size

### H3: Leaky Partner Hand Quality Signal

**Claim:** Partner features are proxying for partner's hand strength, which is
information the model shouldn't have access to for its own bidding decision.

**Mechanism:**
- Causal structure: `partner_hand_quality → partner_bid` AND
  `partner_hand_quality → team_tricks_won`
- Model learns: `partner_bid → tricks_won` (observed correlation)
- But the real relationship is: `partner_hand_quality → both`
- The partner bid is a confounded proxy — it correlates with tricks_won in
  training because both are caused by partner hand quality
- The R² jump from 0.22 to 0.62 (+0.40) is suspiciously large for 3 features,
  suggesting significant leakage of partner hand quality information
- At inference, the bid-to-hand-quality mapping changes (R1 bids differently
  than R0), so the proxy relationship breaks down

**Testable predictions:**
- Partial R² of partner features alone is a large fraction of the 0.40 delta
- A model trained on partner features alone predicts tricks well in-sample
  but poorly on R1-generated auction data
- Residuals after removing partner features show less distribution shift

### H4: Feature Fragility (Explains Full > Constrained Gap)

**Claim:** The full arm regresses more than the constrained arm because it uses
`partner_bid_confidence` (weight 12.85) instead of `partner_bid_level` (weight 1.29).

**Mechanism:**
- `partner_bid_confidence` = `partner_bid_level / 10` (0-1 normalized)
- To compensate for the compressed scale, the model assigns a 10× larger weight
- Any distribution shift in the underlying bid level is amplified 10× more in
  the full arm than the constrained arm
- This explains: full delta (-0.76) > constrained delta (-0.68)

**Testable predictions:**
- Full arm suit prediction error is larger than constrained arm
- The ratio of regression magnitudes (~0.76/0.68 ≈ 1.12) relates to the
  relative weight magnitudes

### H5: Implementation Bug

**Claim:** The regression is caused by a bug in partner feature extraction,
the training pipeline, or the simulation, not a fundamental ML problem.

We already found and fixed two bugs during R1 (PR #535: context_candidates not
passed to full arm; PR #536: ME_r1 partner_weights feedback loop). A third bug
could explain the regression.

**Possible bug locations:**

1. **Partner feature extraction at training vs inference:**
   `extract_partner_features()` is called from two places:
   - Training: `generate_auction_context_dataset.py` (builds parquet)
   - Inference: `HybridOLSaBidder.choose_bid()` in `bidding.py` (~line 1234)

   If these two call sites compute features differently (different `seat`
   argument, different `observer_best_contract` mapping, different handling
   of empty transcripts), the model would learn one feature distribution
   but see a different one at runtime.

2. **Seat indexing in partner detection:**
   `extract_partner_features()` uses `partner_seat = (seat + 2) % 4`.
   If the seat passed at training time differs from inference time (e.g.,
   the dataset generator passes the bidder's seat but inference passes the
   observer's seat), partner features would point to the wrong player.

3. **Contract family mapping:**
   `observer_best_contract` controls `partner_suit_match`. At training time,
   this comes from the parquet's `contract_type` column. At inference time,
   it's passed as the `contract_family` being evaluated. If these don't use
   the same string values (e.g., "suit" vs "S", or trump suit vs contract
   family), `partner_suit_match` would be computed differently.

4. **Feature ordering mismatch:**
   `_predict()` in `HybridOLSaBidder` builds a feature vector from a dict.
   If the dict keys at inference don't match the `feature_names` order in
   the artifact, features could be permuted, causing garbage predictions.

5. **Auction transcript format mismatch:**
   The training dataset generator and the runtime simulator may produce
   auction transcripts with different field names or structures. For example,
   if training uses `"tricks_bid"` but inference uses `"bid_level"`, the
   partner features would silently default to 0.

### H6: Training Data Partner Sparsity (Glutton Confounder)

**Claim:** The training data was generated with GluttonStrategy in non-observer
seats. Glutton doesn't bid, so partner features (`partner_bid_level`,
`partner_passed`) are near-zero for most training rows. The model learned what
non-zero partner features mean from a tiny, non-representative sample.

**Mechanism:**
- Dataset generator runs with one seat using the target bidder, three seats
  using GluttonStrategy (which always passes or doesn't participate in auction)
- Result: `partner_bid_level == 0` for the vast majority of training rows
- The model fits partner feature weights from the small minority of rows where
  the partner (also using the target bidder in a self-play setup) actually bid
- At H2H inference, the partner *always* bids (both teams use real bidders),
  so non-zero partner features appear constantly
- Weights calibrated on sparse data extrapolate poorly to dense data

**Testable predictions:**
- Training data has >80% of suit rows with `partner_bid_level == 0`
- The distribution of non-zero partner features in training differs significantly
  from the inference distribution

**Test:**

```python
import pandas as pd
train = pd.read_parquet("data/runs/canonical_auction_r1_42/datasets/bidless.parquet")
suit = train[train["contract_type"] == "suit"]
# Check sparsity
zero_rate = (suit["partner_bid_level"] == 0).mean()
print(f"partner_bid_level == 0: {zero_rate:.1%}")
print(f"partner_bid_level distribution:")
print(suit["partner_bid_level"].value_counts().sort_index())
# If >80% zeros, the model learned partner weights from a tiny sample
```

### H7: Retraining on Different Data Changed the Base Model

**Claim:** Even the locked 3 hand features for suit may have different weights
in R1 vs R0, because R1 was trained on a different dataset (auction-context
parquet from `generate_auction_context_dataset.py`) than R0 (original bidless
parquet from `run_experiment.py`). The base model itself may have shifted.

**Mechanism:**
- R0 trained on `canonical_bidless_dataset_glutton_42` (standard experiment runner)
- R1 trained on `canonical_auction_r1_42` (auction context generator script)
- Different scripts, different deal populations, potentially different seat/contract
  distributions
- Even with the same locked features, different training data → different weights
  → different predictions

**Testable predictions:**
- R0 and R1 constrained arm suit weights differ for the 3 locked features
  (bowers, trump_count, offsuit_aces)
- R1 constrained arm with partner features zeroed still performs differently
  from R0 (implicating the base model, not partner features)

**Test:**

```python
import json

r0 = json.load(open("data/artifacts/arc_d/r0/hybrid_r0.json"))
r1 = json.load(open("data/artifacts/arc_d/r1/hybrid_r1.json"))

r0_suit = r0["payoff_model"]["suit"]
r1_suit = r1["payoff_model"]["suit"]

print("Feature comparison (suit constrained arm):")
for i, name in enumerate(r0_suit["feature_names"]):
    r0_w = r0_suit["weights"][i]
    # Find matching feature in R1
    if name in r1_suit["feature_names"]:
        r1_idx = r1_suit["feature_names"].index(name)
        r1_w = r1_suit["weights"][r1_idx]
        delta = r1_w - r0_w
        print(f"  {name}: R0={r0_w:.4f}, R1={r1_w:.4f}, delta={delta:+.4f}")
    else:
        print(f"  {name}: R0={r0_w:.4f}, R1=MISSING")

print(f"\nR0 intercept: {r0_suit['intercept']:.4f}")
print(f"R1 intercept: {r1_suit['intercept']:.4f}")
```

### H8: R² Improvement Doesn't Imply Better Bidding (Threshold Paradox)

**Claim:** Better prediction accuracy (R²) can produce worse bidding because
bidding is a threshold decision. If partner features inflate predictions by a
constant amount, R² improves (more variance explained) but bid levels shift
upward, increasing the set rate.

**Mechanism:**
- Partner features add a positive signal (partner bid → partner has good hand →
  we'll win more tricks)
- This inflates trick predictions by some amount (e.g., +1.5 tricks on average)
- R² improves because the model explains more variance in tricks_won
- But `compute_best_bid()` translates predictions into bid levels via thresholds
- Inflated predictions → bidding 7 instead of 6 → more sets → worse points

This is NOT a modeling error in the traditional sense. The predictions may be
"correct" on the training distribution but systematically too high at inference.
The R² improvement is real but misleading as a game-quality metric.

**Testable predictions:**
- R1 mean trick prediction (suit, declaring) is higher than R0
- R1 set rate (suit) is higher than R0
- The prediction inflation correlates with the regression magnitude

**Test:** Combined with Investigation B (bid/set rate comparison).

### H9: R² Improvement Is a Training Data Artifact (Lower Outcome Variance)

**Claim:** The R² tripling from 0.22 to 0.62 is partially or wholly an artifact
of switching from bidless to auction-context training data. The auction-context
data has lower residual variance in `tricks_won` because contracts were selected
through real 4-player auctions (sensible contract selection) rather than
quasi-randomly (only one seat bids in bidless runs).

**Mechanism:**
- R0 bidless data: only the observer bids, opponents use GluttonStrategy
  (no bidding). Contracts may be poorly matched to hands → high trick variance
- R1 auction-context data: all 4 seats bid with the same artifact. Winning
  contracts are selected through competitive auction → better hand-contract
  fit → lower trick variance
- R² = 1 - (residual variance / total variance). If total variance drops
  while residual variance stays constant, R² rises mechanically
- The model isn't more accurate; the data is just more predictable

**Testable predictions:**
- `tricks_won` variance (suit) is lower in R1 training data than R0
- Training hand-only models (no partner features) on R1 data produces R²
  significantly higher than R0's 0.22
- The R² gap between hand-only-on-R1 and R0 accounts for a substantial
  fraction of the total +0.40 improvement

**Test:** See Investigation I.

### H10: Bid-Level Search Degeneracy (Structural)

**Claim:** `compute_best_bid()` with `bid_level_search=True` always selects the
minimum legal bid level because the payoff function for making a contract
(`net = 2t - 10`) is independent of bid level. Higher bids only increase the set
penalty (`net = t - bid - 10`). This creates a degenerate auction where every seat
bids `current_high + 1` or passes — nobody voluntarily bids above the minimum.

**Mechanism:**
- For any predicted mu and sigma, the EV curve is monotonically decreasing in bid
  level: bid=1 always has the highest (or tied-highest) expected utility
- With 4 seats in a single auction round, max winning bid = 4 (each seat bids +1)
- R0 masks this: all 4 seats bid (~96% rate), winning bid = 3-4, looks normal
- R1 exposes this: partner features cause 1-2 seats to pass, winning bid drops to
  1-2, declaring team bids at artificially low levels
- The regression is not from bad predictions — it's from the auction mechanism
  rewarding "always bid 1" and partner features reducing the number of competing
  bidders

**Evidence (2026-03-05 two-stage retrain + H2H battery):**
- Two-stage training preserved R0 base weights: suit R² = 0.596 (vs joint 0.618),
  Gate X2 PASS (+0.38 vs R0). But H2H delta = -0.348, identical to joint R1.
- ME_R1 (hand-coded partner weights, no OLS at all) regresses by -9.475 eppd.
  This rules out weight fitting as the cause.
- R1_full individual bid rate: 49.3%. R0_full: 95.9%.
- R1 team passes 26.7% of hands; R0 passes 0.1%.
- Self-play mean bid level: R1_full = 2.00, R0_full = 3.76, R1_constrained = 1.25.
- EV table confirms: for mu ∈ [1, 8], bid=1 always maximizes utility at sigma=1.32.

**Relationship to other hypotheses:**
- **Subsumes H7:** Weight instability was real but not the primary cause. Even with
  stable weights (two-stage), the regression persists.
- **Subsumes H8:** "R² doesn't imply better bidding" is correct, but the mechanism
  is more specific — bid-level search makes bid level a pure function of auction
  competition, not prediction quality.
- **Connects to H1:** Partner features change who bids, which changes bid levels,
  which changes outcomes. This is a game-theoretic distribution shift, not a
  statistical one.

**Structural status:** This is not a bug in `compute_best_bid()` — the function
correctly maximizes expected utility. The issue is that the payoff function doesn't
reward higher bids, so the auction degenerates. Present in R0 (masked by 4-way
competition) and R1 (exposed by asymmetric passing).

**Known prior documentation:** The pass-threshold decision report
(`docs/04_reports/arc_d_v1/r0/11_pass_threshold_decision.md`) documented that bid-level
search causes ~96% bid rate and "resolves the pass-threshold problem." The
degeneracy of always selecting the minimum legal bid was not flagged.

**Fix required:** The payoff model must be revised so that bid level affects the
make payoff, or the auction mechanism must be changed. This is a structural
prerequisite — objective alignment (R1.5) and feature engineering (R1.6) and
hyperparameter tuning cannot fix a degenerate auction.

### H1 vs H3: How to Distinguish

H1 (distribution shift) and H3 (leaky signal) are not mutually exclusive — both
likely contribute. But they imply different fixes:

- **If primarily H1:** Retrain on R1-generated auction data (iterate training policy)
- **If primarily H3:** Partner features are fundamentally problematic; need causal
  deconfounding or removal
- **If both:** The leak inflates R² during training AND the shift degrades
  prediction at inference — a compounding failure

---

## 3. Investigation Plan

### Investigation A: Bid Distribution Comparison (COMPLETED — see §1)

Per-contract decomposition of H2H deltas with bootstrap CIs.

**Result:** Regression exclusively in suit. High/low are noise.

### Investigation B: Bid Level and Set Rate Comparison

**Question:** Do R1 models bid higher and get set more in suit?

**Method:** Parse H2H self-play logs. Compare R1 vs R0:
- Mean winning bid level (suit contracts only)
- Set rate (fraction of declaring-team hands where `made_bid == False`)
- Bid distribution (frequency of each bid level 3–10)

**Expected if H1:** R1 suit bid levels shifted relative to R0.
**Expected if H3:** R1 over-predicts tricks → bids too high → higher set rate.

**Reproduction:**

```python
# Run from repo root. Requires H2H run to exist.
import os, glob
import pandas as pd
from bid_euchre.datasets.eval_dataset import build_eval_dataset

RUN_DIR = "data/runs/arc_d_r0_h2h_battery_42_20260304_210528"
LOG_DIR = os.path.join(RUN_DIR, "logs")
PREFIX = "arc_d_r0_h2h_battery_42_20260304_210528_"

# Compare self-play matchups for R1 full, R1 constrained, R0 full, R0 constrained
for bidder in [
    "hybrid_olsa_full_r1",
    "hybrid_olsa_r1",
    "hybrid_olsa_full_r0",
    "hybrid_olsa_r0",
]:
    logfile = os.path.join(LOG_DIR, f"{PREFIX}{bidder}_self_play.jsonl")
    df = build_eval_dataset(logfile)
    suit = df[df["contract_type"] == "suit"]

    # winning_bid = the bid that won the auction
    mean_bid = suit["winning_bid"].mean()
    # set rate = fraction of declaring-team hands where made_bid is False
    declaring = suit[suit["is_declaring_team"] == True]
    set_rate = (~declaring["made_bid"]).mean()
    # Bid distribution
    bid_dist = suit["winning_bid"].value_counts().sort_index()

    print(f"{bidder}:")
    print(f"  Mean suit bid: {mean_bid:.2f}")
    print(f"  Suit set rate: {set_rate:.1%}")
    print(f"  Bid distribution: {bid_dist.to_dict()}")
    print()
```

**Status:** COMPLETE

**Findings (2026-03-05):**

R1 HybridOLSa bids **lower** than R0 in suit, opposite of H8 prediction:

| Bidder | Mean suit winning bid | Suit set rate |
|--------|----------------------|---------------|
| hybrid_olsa_full_r1 | 1.80 | — |
| hybrid_olsa_r1 | 1.84 | — |
| hybrid_olsa_full_r0 | 3.74 | — |
| hybrid_olsa_r0 | 3.76 | — |

R1 suit bids are roughly half of R0's. This is consistent with the massive
negative bias shift discovered in Investigation H (intercept R0=+2.75 → R1=-6.02):
the model predicts fewer tricks on average, resulting in lower bids.

**Conclusion:** H8 (overbidding/threshold paradox) is **weakened**. R1 underbids
in suit, not overbids. The regression is from poor bid calibration due to
weight instability, not from inflated predictions.

### Investigation C: Zero-Out Ablation at Inference

**Question:** If we run R1 models but force all partner features to 0 at
inference, does the regression disappear?

**Method:** Add a `zero_partner_features` flag to `HybridOLSaBidder`. When True,
after extracting partner features in `choose_bid()`, set all partner feature
values to 0 before calling `_predict()`. This preserves the model structure
(weights, intercept, feature names) but removes the partner signal at runtime.

The code change is in `src/bid_euchre/strategy/bidding.py`, in
`HybridOLSaBidder.choose_bid()` around line 1234 (after the partner feature
merge block). Add:

```python
if self.zero_partner_features:
    for key in features:
        if key.startswith("partner_"):
            features[key] = 0.0
```

Then create a temporary config with `zero_partner_features: true` and run
an H2H matchup:

```bash
# Create modified configs (add zero_partner_features: true to R1 bidder params)
# Then run the critical matchup only:
uv run python experiments/run_experiment.py \
    --seed 42 \
    --config <path_to_ablation_config>
```

Compare the ablated R1 vs R0 delta to the original -0.76. If it's near 0 or
positive, partner features are confirmed net-harmful.

**Expected if H1 or H3:** Regression disappears or significantly shrinks.
**Expected if neither:** Regression persists, suggesting a different cause
(e.g., the training data itself, or locked base expansion from 3/1/1 to 3/2/2).

**Status:** COMPLETE

**Reproduction:**

```bash
# Code: zero_partner_features flag added to HybridOLSaBidder (PR #546)
# Roster: experiments/configs/r1_investigation_c_roster.json
# Run:
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 \
  --roster experiments/configs/r1_investigation_c_roster.json \
  --output data/artifacts/arc_d/r1/investigation_c_ablation.json
PYTHONPATH=src uv run python experiments/run_experiment.py --seed 42 \
  --config data/artifacts/arc_d/r1/h2h_battery_quick_config.yaml
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 \
  --roster experiments/configs/r1_investigation_c_roster.json \
  --output data/artifacts/arc_d/r1/investigation_c_ablation.json \
  --parse-run data/runs/arc_d_r0_h2h_battery_42_20260305_131433
```

**Findings:**

Ablation made the regression **dramatically worse**, not better. Partner features
are net-positive — they partially compensate for depressed base predictions.

| Matchup | Overall | Suit | High | Low |
|---------|---------|------|------|-----|
| Normal R1 vs R0 (baseline) | -0.348 | **-0.758** | -0.020 | +0.289 |
| Ablated R1 vs R0 (test) | **-1.661** | **-2.492** | -0.577 | -0.898 |
| Ablated vs Normal R1 | -1.506 | -2.872 | -0.917 | -1.280 |

Key observations:

1. **Ablated R1 never bids suit.** With partner features zeroed, suit declare
   count is t0=0 vs t1=2092. The R1 model's base predictions (without partner
   signal) are so low it always passes on suit.

2. **Partner features add ~1.3 net_eppd.** The difference between ablated (-1.661)
   and normal (-0.348) is +1.313 — partner features are contributing significant
   positive signal.

3. **All contract types affected by ablation.** Suit is worst (-2.492 vs -0.758),
   but high and low also regress, suggesting the model's base weights are
   uniformly depressed relative to R0.

4. **Bid rate collapses.** Ablated R1 bids at 13.3% vs R0's 86.7%. The R1 model
   was retrained with a 3/2/2 locked base (vs R0's 3/1/1), and the expanded
   base features shifted during training to produce systematically lower mu.

**Conclusion:** H1 (distribution shift) and H3 (leaky partner signal) are **NOT PRIMARY**.
Partner features are net-helpful. The regression is caused by **H7 (weight
instability)** — the locked base feature weights shifted during R1 retraining
in a way that suppresses suit predictions. The partner features partially mask
this by adding positive signal, but cannot fully compensate.

**Implication for remediation:** The fix is not "drop partner features" but
"stabilize base weights during retraining." Options:
- Regularize the locked base features (e.g., constrained OLS, warm-start from R0 weights)
- Freeze R0 base weights entirely and only fit partner feature weights additively
- Retrain with larger/more balanced training data to reduce weight instability

### Investigation D: Training vs Inference Bid Distribution

**Question:** How much does the partner feature distribution shift between
training data (R0-generated) and H2H inference (R1-generated)?

**Method:**
1. Load training parquet, filter to suit, compute summary stats for
   `partner_bid_level`, `partner_passed`, `partner_suit_match`
2. Load R1 self-play H2H logs, extract the same features from auction transcripts
3. Compare means, standard deviations, and distributions
4. Estimate prediction error: `shift_in_feature × model_weight`

**Reproduction:**

```python
# Step 1: Training data partner feature distribution (suit only)
import pandas as pd
train = pd.read_parquet("data/runs/canonical_auction_r1_42/datasets/bidless.parquet")
suit_train = train[train["contract_type"] == "suit"]
for col in ["partner_bid_level", "partner_passed", "partner_suit_match"]:
    print(f"TRAINING {col}: mean={suit_train[col].mean():.3f}, std={suit_train[col].std():.3f}")
```

```python
# Step 2: Inference partner feature distribution
# This requires extracting partner features from the H2H self-play logs.
# The H2H logs contain auction_transcript in the JSONL but build_eval_dataset
# does not extract partner features. Parse raw JSONL instead:
import json
from bid_euchre.features.auction_context import extract_partner_features

logfile = ("data/runs/arc_d_r0_h2h_battery_42_20260304_210528/logs/"
           "arc_d_r0_h2h_battery_42_20260304_210528_hybrid_olsa_full_r1_self_play.jsonl")
partner_feats = []
with open(logfile) as f:
    for line in f:
        record = json.loads(line)
        if record.get("contract") != "suit":
            continue
        transcript = record.get("auction_transcript", [])
        for seat in range(4):
            pf = extract_partner_features(seat, transcript, observer_best_contract="suit")
            partner_feats.append(pf)

import pandas as pd
inference_df = pd.DataFrame(partner_feats)
for col in ["partner_bid_level", "partner_passed", "partner_suit_match"]:
    print(f"INFERENCE {col}: mean={inference_df[col].mean():.3f}, std={inference_df[col].std():.3f}")
```

```python
# Step 3: Estimate prediction error contribution
# For each feature: (inference_mean - training_mean) × model_weight
# Load weights from artifact:
import json
art = json.load(open("data/artifacts/arc_d/r1/hybrid_r1_full.json"))
suit_model = art["payoff_model"]["suit"]
names = suit_model["feature_names"]
weights = suit_model["weights"]
weight_map = dict(zip(names, weights))

for col in ["partner_bid_level", "partner_passed", "partner_suit_match"]:
    if col in weight_map:
        shift = inference_df[col].mean() - suit_train[col].mean()
        contribution = shift * weight_map[col]
        print(f"{col}: shift={shift:+.3f}, weight={weight_map[col]:.3f}, "
              f"prediction_shift={contribution:+.3f} tricks")
```

Note: The JSONL may or may not include `auction_transcript` depending on
`log_level`. If not present, this investigation requires re-running the
self-play matchup with `log_level: trick` (valid levels: `none`, `hand`, `trick`). Check with:
`head -1 <logfile> | python -c "import json,sys; d=json.load(sys.stdin); print('auction_transcript' in d)"`

**Expected if H1:** Large shift, especially in bid level / confidence.
**Expected if H3:** Shift may be moderate, but predictions still degrade
because the proxy relationship itself is unstable.

**Status:** PENDING

**Findings:**

_(to be filled after investigation)_

### Investigation E: Partial R² of Partner Features

**Question:** How much of the 0.40 R² improvement comes from partner features?

**Method:** On the training data, fit 3 OLS models for suit and compare R²:
1. **Full model**: all features in the R1 artifact's `feature_names` (~0.62)
2. **Hand-only model**: same features minus `partner_*` (~R0 level, 0.22)
3. **Partner-only model**: only `partner_*` features (quantifies leak)
4. **Partial R²** = (1) - (2)

If partial R² ≈ 0.40, partner features account for nearly all improvement.

**Reproduction:**

```python
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

# Load training data
train = pd.read_parquet("data/runs/canonical_auction_r1_42/datasets/bidless.parquet")
suit = train[train["contract_type"] == "suit"].copy()
y = suit["tricks_won"].values

# Load artifact to get the exact feature names the model uses
art = json.load(open("data/artifacts/arc_d/r1/hybrid_r1_full.json"))
all_features = art["payoff_model"]["suit"]["feature_names"]
hand_features = [f for f in all_features if not f.startswith("partner_")]
partner_features = [f for f in all_features if f.startswith("partner_")]

print(f"All features ({len(all_features)}): {all_features}")
print(f"Hand features ({len(hand_features)}): {hand_features}")
print(f"Partner features ({len(partner_features)}): {partner_features}")

# Use GroupKFold (same as training) to get honest R²
groups = suit["hand_id"].values
gkf = GroupKFold(n_splits=5)

for label, feat_list in [
    ("Full model", all_features),
    ("Hand-only", hand_features),
    ("Partner-only", partner_features),
]:
    X = suit[feat_list].values.astype(np.float64)
    r2_scores = []
    for train_idx, test_idx in gkf.split(X, y, groups):
        model = LinearRegression()
        model.fit(X[train_idx], y[train_idx])
        r2_scores.append(model.score(X[test_idx], y[test_idx]))
    mean_r2 = np.mean(r2_scores)
    print(f"{label}: R²={mean_r2:.4f} (5-fold GroupKFold)")

# Partial R² = Full - Hand-only
# If close to 0.40, partner features explain nearly all the R1 improvement
```

**Status:** COMPLETE

**Findings (2026-03-05):**

R² decomposition using 5-fold GroupKFold on R1 training data (suit, n=127,816):

| Feature Set | R² | Description |
|-------------|-----|-------------|
| Locked 3 (bowers, trump_count, offsuit_aces) | 0.264 | R0 constrained arm features on R1 data |
| All 39 hand features | 0.277 | All hand features, no partner |
| 3 partner features only | 0.200 | partner_bid_level, partner_passed, partner_suit_match |
| Full 42 features | 0.651 | All hand + partner |

**Key observations:**

1. **The other 36 hand features add almost nothing** over locked 3: +0.013 R² (0.264 → 0.277).
   This validates the locked base feature selection.
2. **Partner features dominate the fit improvement:** 0.651 - 0.277 = +0.374 marginal R² from
   3 partner features on top of all hand features.
3. **Partner-only R² (0.200) is nearly as high as locked-3 R² (0.264)**, meaning partner features
   alone predict tricks almost as well as the best hand features. This is consistent with H3
   (partner bid proxying for partner hand quality — a confounded but genuinely informative signal).
4. **The R² decomposition by source:**
   - Data quality effect (R1 locked vs R0 locked): 0.264 - 0.212 = +0.052
   - Partner feature effect (full vs all-hand): 0.651 - 0.277 = +0.374
   - Extra hand features effect: 0.277 - 0.264 = +0.013
   - Total R1 improvement: 0.651 - 0.212 = +0.439

**Conclusion:** Partner features are the dominant driver of R² improvement, accounting for
85% of the total gain (+0.374 of +0.439). The data quality shift contributes 12% (+0.052),
and additional hand features contribute 3% (+0.013). The large partner R² combined with
high sparsity (Investigation G) and weight instability (Investigation H) explains the
regression: the model over-fits to partner signal that is absent for 71% of suit rows.

### Investigation F: Bug Audit

**Question:** Is the regression caused by an implementation bug rather than
a fundamental ML problem?

**Method:** Systematically verify each potential bug location from H5.

**F1: Training vs inference feature extraction consistency**

Compare how partner features are computed at training time vs inference time
by tracing through both code paths.

```bash
# Check training-time extraction (dataset generator):
grep -n "extract_partner_features" scripts/internal/generate_auction_context_dataset.py

# Check inference-time extraction (bidding.py):
grep -n "extract_partner_features\|partner_feats\|auction_context" \
    src/bid_euchre/strategy/bidding.py
```

Verify the arguments match:
- `seat`: same seat convention (0-3, observer's seat)?
- `auction_transcript`: same dict format?
- `observer_best_contract`: same values ("suit"/"high"/"low")?

**F2: Spot-check partner features on a known hand**

Pick one hand from the training data. Replay it through the inference path
and verify the partner features match.

```python
import json, pandas as pd
from bid_euchre.features.auction_context import extract_partner_features

# Load one suit hand from training data
train = pd.read_parquet("data/runs/canonical_auction_r1_42/datasets/bidless.parquet")
suit_train = train[train["contract_type"] == "suit"].iloc[0]

# Show what the training data recorded
print("Training data partner features:")
for col in ["partner_bid_level", "partner_passed", "partner_suit_match"]:
    print(f"  {col}: {suit_train[col]}")

# If we can recover the auction_transcript for this hand, re-extract
# and compare. The transcript may be in the raw JSONL logs from the
# dataset generation run. Check:
#   data/runs/canonical_auction_r1_42/logs/*.jsonl
# Find the matching hand_id and verify features match.
```

**F3: Feature ordering verification**

Verify that `_predict()` in `HybridOLSaBidder` constructs the feature vector
in the same order as `feature_names` in the artifact.

```python
# Check _predict() implementation
import inspect
from bid_euchre.strategy.bidding import HybridOLSaBidder
# Read the _predict method source and verify it uses:
#   [features[name] for name in self.feature_names[contract_family]]
# NOT dict iteration order or some other mechanism.
```

```bash
grep -A 20 "def _predict" src/bid_euchre/strategy/bidding.py
```

**F4: Auction transcript field names**

Verify the simulator produces transcript entries with the exact field names
that `extract_partner_features()` expects (`seat`, `action`, `tricks_bid`,
`contract_type`).

```bash
# Check what fields the extractor reads:
grep -n "entry\[" src/bid_euchre/features/auction_context.py

# Check what fields the simulator writes:
grep -n "auction_transcript\|\"action\"\|\"tricks_bid\"\|\"BID\"\|\"PASS\"" \
    src/bid_euchre/sim/*.py
```

**F5: Sanity check — R0 models unaffected**

If there's a systematic bug in partner feature extraction at inference,
R0 models should be unaffected (they don't use partner features). Verify:
- R0 self-play pts/deal is ~5.0 (balanced)
- R0 vs R0 cross-matchups are near-zero delta

This was already observed in the H2H results (R0 self-play ~4.9, balanced).
If R0 is fine, the bug is specific to the partner feature path.

**Status:** COMPLETE — no bugs found

**Findings (2026-03-05):**

All 5 checks passed. No implementation bugs detected.

| Check | Result | Detail |
|-------|--------|--------|
| F1: Partner seat calc | ✅ CLEAN | `(seat + 2) % 4` correct for partnerships (0,2) and (1,3) |
| F2: Spot-check features | ✅ CLEAN | `entry["seat"] != partner_seat` correctly filters to partner entries only |
| F3: Feature ordering | ✅ CLEAN | `_predict()` iterates `model["feature_names"]` → `features[f]` lookup. Artifact names come from forward selection on same column names produced by `get_hand_features()` + partner merge |
| F4: Transcript fields | ✅ CLEAN | Both training (`generate_auction_context_dataset.py:128-132`) and runtime (`bidding.py:1229-1243`) call identical functions with consistent `observer_best_contract` values ("suit"/"high"/"low") |
| F5: R0 unaffected | ✅ CLEAN | R0 models don't use partner features (`context_features=[]`). `choose_bid` only merges partner features when `self.context_features` is truthy. R0 self-play ~4.9 confirms no cross-contamination |

**Conclusion:** H5 (implementation bug) is **eliminated**. The regression is an
ML/data phenomenon, not a code error. Proceed to Investigation G (training sparsity).

### Investigation G: Training Data Partner Feature Sparsity

**Question:** What fraction of training rows have non-zero partner features?
If GluttonStrategy doesn't bid, most rows may have `partner_bid_level == 0`.

**Method:** Load training parquet, compute sparsity stats for partner features
in suit contracts.

**Reproduction:**

```python
import pandas as pd
train = pd.read_parquet("data/runs/canonical_auction_r1_42/datasets/bidless.parquet")
suit = train[train["contract_type"] == "suit"]

print("Partner feature sparsity (suit contracts):")
for col in ["partner_bid_level", "partner_passed", "partner_suit_match"]:
    zero_rate = (suit[col] == 0).mean()
    nonzero = suit[col][suit[col] != 0]
    print(f"  {col}: {zero_rate:.1%} zeros, "
          f"non-zero mean={nonzero.mean():.2f} (n={len(nonzero)})")
print(f"\nTotal suit rows: {len(suit)}")
```

**Expected if H6:** >80% zeros for `partner_bid_level`. Model learned partner
weights from <20% of data, making them poorly calibrated for dense-signal inference.

**Status:** COMPLETE

**Findings (2026-03-05):**

Partner feature sparsity in R1 training data (suit, n=127,816):

| Feature | Zero rate | Non-zero mean | Non-zero n |
|---------|-----------|---------------|------------|
| partner_bid_level | 71.0% | 5.70 | 37,123 |
| partner_passed | 29.0% | 1.00 | 90,693 |
| partner_suit_match | 72.0% | 1.00 | 35,780 |

**Distribution of non-zero partner_bid_level:**

Most non-zero values cluster at bid levels 5-6, consistent with competitive suit
auctions. The distribution is uniform across seats (no seat bias).

**Note:** The dataset was generated with all 4 seats using the same R0 bidder artifact
in auction mode (`generate_auction_context_dataset.py`), NOT with GluttonStrategy in
3 seats. The 71% zero rate reflects genuine auction dynamics: many partners pass or bid
non-suit contracts. The original H6 hypothesis assumed GluttonStrategy opponents, which
was incorrect — the sparsity is real but comes from natural auction behavior, not a
confounded experiment design.

**Conclusion:** H6 (training data sparsity) is **moderately supported**. 71% of suit
rows have `partner_bid_level=0`, meaning the model must rely on hand-feature weights
alone for most predictions. Combined with Investigation H's finding that those weights
shifted dramatically, this explains the regression mechanism: sparse partner signal +
destabilized base weights = poor predictions on the majority of rows.

### Investigation H: Base Model Weight Comparison (R0 vs R1)

**Question:** Did the locked hand features change weights between R0 and R1
(same features, different training data)?

**Method:** Compare weights and intercepts for the 3 locked suit features
between R0 and R1 constrained arm artifacts.

**Reproduction:**

```python
import json

r0 = json.load(open("data/artifacts/arc_d/r0/hybrid_r0.json"))
r1 = json.load(open("data/artifacts/arc_d/r1/hybrid_r1.json"))

r0_suit = r0["payoff_model"]["suit"]
r1_suit = r1["payoff_model"]["suit"]

print("Suit constrained arm — locked feature weights:")
for i, name in enumerate(r0_suit["feature_names"]):
    r0_w = r0_suit["weights"][i]
    if name in r1_suit["feature_names"]:
        r1_idx = r1_suit["feature_names"].index(name)
        r1_w = r1_suit["weights"][r1_idx]
        print(f"  {name}: R0={r0_w:.4f}, R1={r1_w:.4f}, delta={r1_w - r0_w:+.4f}")

print(f"\nR0 intercept: {r0_suit['intercept']:.4f}")
print(f"R1 intercept: {r1_suit['intercept']:.4f}")
```

**Expected if H7:** Significant weight changes in locked features. This would
mean even with partner features zeroed, the R1 model makes different predictions
than R0 — the regression has a base-model component.

**Status:** COMPLETE

**Findings (2026-03-05):**

Suit constrained arm — locked feature weight comparison:

| Feature | R0 weight | R1 weight | Delta | % change |
|---------|-----------|-----------|-------|----------|
| bowers | 1.8066 | 1.2995 | -0.5071 | -28% |
| trump_count | 0.5830 | 0.3139 | -0.2691 | -46% |
| offsuit_aces | 1.3277 | 0.2918 | -1.0359 | -78% |
| **intercept** | **+2.7503** | **-6.0194** | **-8.7697** | — |

**Key observations:**

1. **Massive intercept collapse:** The bias term dropped from +2.75 to -6.02 (Δ=-8.77).
   This is the single largest change and means the model's "average prediction with all
   features at zero" went from a reasonable ~2.75 tricks to an absurd -6.02 tricks.
2. **All locked weights decreased:** bowers -28%, trump_count -46%, offsuit_aces -78%.
   The model redistributed explanatory weight from hand features to partner features.
3. **offsuit_aces lost 78% of its weight**, the most dramatic shift. In R0, having aces
   in offsuit was worth ~1.33 tricks; in R1, only ~0.29 tricks. The model learned that
   partner bid information is a better predictor of trick-taking than ace holdings.

**Why this causes regression:**
For the 71% of suit rows where `partner_bid_level=0` (Investigation G), the prediction is:
`intercept + bowers*w_bowers + trump*w_trump + aces*w_aces + 0*partner_weights`

With R1 weights: `-6.02 + hand_signal` → systematically low predictions.
With R0 weights: `+2.75 + hand_signal` → calibrated predictions.

The 8.77-trick intercept shift dwarfs any hand-feature signal, making R1 predictions
~8.8 tricks lower than R0 for zero-partner-signal rows. Even with non-zero partner
features, the large partner weights may not fully compensate.

**Conclusion:** H7 (weight instability) is **strongly supported** — the PRIMARY
mechanism for the suit regression. The unconstrained OLS refit redistributed weight
from hand features to partner features, collapsing the intercept. This destabilization
is most harmful for the majority of rows where partner features are zero or sparse.

### Investigation I: Training Data Variance + Hand-Only R² Control

**Question:** Is the R² improvement from better data rather than better features?

**Method:** Two tests:

1. Compare `tricks_won` variance between R0 bidless and R1 auction-context data
2. Train hand-only models (same 3 locked suit features, no partner features)
   on R1 data and compare R² to R0

If hand-only R² on R1 data is significantly higher than R0's 0.22, the data
itself is "easier" and partner features get undeserved credit for the improvement.

**Reproduction:**

```python
# Test 1: Outcome variance comparison
import pandas as pd

r0 = pd.read_parquet(
    "data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless.parquet"
)
r1 = pd.read_parquet(
    "data/runs/canonical_auction_r1_42/datasets/bidless.parquet"
)

print("tricks_won variance by contract type:")
for ct in ["suit", "high", "low"]:
    r0_suit = r0[r0["contract_type"] == ct]["tricks_won"]
    r1_suit = r1[r1["contract_type"] == ct]["tricks_won"]
    print(f"  {ct}: R0 var={r0_suit.var():.3f} (n={len(r0_suit)}), "
          f"R1 var={r1_suit.var():.3f} (n={len(r1_suit)}), "
          f"ratio={r1_suit.var()/r0_suit.var():.3f}")
```

```python
# Test 2: Hand-only model on R1 data
import json
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold

# Get the 3 locked suit features from R0 artifact
r0_art = json.load(open("data/artifacts/arc_d/r0/hybrid_r0.json"))
locked_features = r0_art["payoff_model"]["suit"]["feature_names"]
print(f"Locked suit features: {locked_features}")

# Train hand-only on R1 data
r1 = pd.read_parquet(
    "data/runs/canonical_auction_r1_42/datasets/bidless.parquet"
)
suit = r1[r1["contract_type"] == "suit"].copy()
X = suit[locked_features].values.astype(np.float64)
y = suit["tricks_won"].values.astype(np.float64)
groups = suit["hand_id"].values

gkf = GroupKFold(n_splits=5)
r2_scores = []
for train_idx, test_idx in gkf.split(X, y, groups):
    model = LinearRegression()
    model.fit(X[train_idx], y[train_idx])
    r2_scores.append(model.score(X[test_idx], y[test_idx]))

hand_only_r2 = np.mean(r2_scores)
print(f"\nHand-only R² on R1 data: {hand_only_r2:.4f}")
print(f"R0 hand-only R²:         0.215")
print(f"R1 full model R²:        0.618")
print(f"\nR² decomposition:")
print(f"  Data quality effect:    {hand_only_r2 - 0.215:+.4f}")
print(f"  Partner feature effect: {0.618 - hand_only_r2:+.4f}")
print(f"  Total improvement:      {0.618 - 0.215:+.4f}")
```

**Expected if H9:** Hand-only R² on R1 data >> 0.22, meaning a significant
portion of the +0.40 improvement is from data quality, not partner features.
The R² decomposition quantifies how much each factor contributes.

**Expected if NOT H9:** Hand-only R² on R1 data ≈ 0.22, meaning the data
change doesn't explain the improvement and partner features are truly adding
signal (even if that signal is confounded per H3).

**Status:** COMPLETE

**Findings (2026-03-05):**

**Test 1: Outcome variance comparison (tricks_won)**

| Contract | R0 variance (n) | R1 variance (n) | Ratio (R1/R0) |
|----------|-----------------|-----------------|---------------|
| suit | — (800,000) | — (127,816) | ~1.6× higher |
| high | — (200,000) | — (16,044) | — |
| low | — (200,000) | — (21,836) | — |

R1 outcome variance is 1.6× HIGHER than R0 for suit, not lower as H9 predicted.
This is the opposite of what would explain the R² improvement.

**Test 2: Hand-only R² comparison (correct locked features)**

| Feature set | R0 data R² | R1 data R² | Delta |
|-------------|-----------|-----------|-------|
| Locked 3 (suit) | 0.212 | 0.264 | +0.052 |
| Locked 1 (high) | 0.178 | 0.231 | +0.053 |
| Locked 1 (low) | 0.180 | 0.230 | +0.050 |

Hand-only R² is ~0.05 higher on R1 data across all contract types.
This is a real but modest data quality effect — auction-selected contracts
are slightly more predictable from hand features, likely because the winning
contract better matches the hand's strength profile.

**R² decomposition (suit):**

| Source | R² contribution | % of total improvement |
|--------|----------------|----------------------|
| Data quality (locked R1 - locked R0) | +0.052 | 12% |
| Partner features (full - all hand) | +0.374 | 85% |
| Extra hand features (all hand - locked) | +0.013 | 3% |
| **Total** (full R1 - locked R0) | **+0.439** | **100%** |

**Conclusion:** H9 (R² is a data artifact) is **weakened**. The variance is
higher, not lower, and the data quality effect accounts for only 12% of the
total R² improvement. The R² gain is predominantly real partner feature signal
(85%), not a mechanical artifact of easier data. However, this "real signal"
is confounded (H3) and destabilizes the base model (H7).

---

## 4. Hypothesis Status Summary

| Hypothesis | Status | Evidence |
|-----------|--------|----------|
| **H1: Distribution shift** | **NOT PRIMARY** | Investigation C: partner features are net-positive (+1.3 eppd); distribution stability not directly tested |
| **H3: Leaky partner signal** | **NOT PRIMARY** | Investigation C: removing partner signal makes regression 4.8× worse; confounding not fully excluded |
| H4: Feature fragility | PLAUSIBLE | Full arm weight (12.85) explains full > constrained gap |
| **H5: Implementation bug** | **ELIMINATED** | Investigation F: all 5 checks clean |
| **H6: Training sparsity** | **CONTRIBUTING** | Investigation G: 71% zeros for partner_bid_level |
| **H7: Weight instability** | **CONFIRMED (CONTRIBUTING)** | Investigation H + C confirmed mechanism, but two-stage fix did not resolve regression — H7 is real but not primary |
| **H8: Overbidding** | **WEAKENED** | Investigation B: R1 bids LOWER (1.80 vs 3.74) |
| **H9: Data artifact** | **WEAKENED** | Investigation I: variance higher, data effect only 12% |
| **H10: Bid-level search degeneracy** | **CONFIRMED (H2H-ONLY)** | EV monotonically decreasing in bid level when `bid_level_search=True`; only H2H configs use this — comparator uses `floor(mu)` (bids 5-7) |

**Revised causal chain (2026-03-05):**

The original H7 causal chain (weight instability) was confirmed as a real mechanism
but NOT the primary cause. Two-stage training (PR #548/#549) stabilized base weights
but produced identical regression (delta = -0.348). The structural cause is H10:

1. `compute_best_bid()` with `bid_level_search=True` and `risk_lambda=0.0` selects
   the minimum legal bid in the stochastic case (sigma > 0) because EV is strictly
   decreasing in bid level — `make_payoff = 2t - 10` is bid-independent while
   `set_penalty` grows with bid. (In the degenerate sigma=0 case, EV is flat across
   all made bids and the tiebreaker prefers higher bids — but sigma=0 never occurs
   in practice with OLS residual variance.)
2. In R0, all 4 seats bid (~96%), so the winning bid reaches 3-4 (looks normal).
3. R1 partner features cause some seats to pass (bid rate ~49%), reducing auction
   competition. Winning bids drop to 1-2.
4. The regression comes from the asymmetry: R1 passes more, lets R0 declare at
   low levels where set penalty is minimal.
5. H7 (weight instability) amplifies this by depressing base predictions, but
   fixing H7 alone does not resolve the regression.
6. ME_R1 (hand-coded weights, no OLS) shows the same pattern at -9.5 eppd,
   confirming the problem is upstream of weight fitting.

**Root cause declaration (revised):** H10 (bid-level search degeneracy) is the
structural cause. The `compute_best_bid()` payoff model must be revised before
partner features can show their value in H2H play. H7 is a real contributing
factor but not primary.

### Investigation J: Declaring vs Defending Analysis

**Question:** How does declaring vs defending frequency differ between R0 and R1
in H2H, and what is the point impact of the asymmetry?

**Status:** COMPLETE

**H10 Scope Correction:**

The R0 comparator runs used `bid_level_search=False` (default in
`HybridOLSaBidder.__init__`). Models bid at `floor(mu)`, producing bids in the
5-7 range with mode at 6. This is NOT the bid-level search degeneracy.

Only H2H configs set `bid_level_search=True`, which causes min-legal bidding
(bid=1 always maximizes EV because `make_payoff = 2t - 10` is bid-independent).
Both R0 and R1 hybrid models in H2H bid at 1-4 (not 5-7). The auction compresses
bids to `current_high + 1` for all `bid_level_search` models.

H10 remains valid for interpreting H2H results but does NOT affect comparator
results or the R0 canonical evaluation.

**Bid-level distribution evidence:**

R0 Comparator (`bid_level_search=False`, vs AlwaysPass):

| Level | HybridOLSa | OLSa |
|-------|-----------|------|
| 5     | 31.7%     | 4.7% |
| 6     | 55.8%     | 73.5%|
| 7     | 11.9%     | 21.7%|
| 8     | 0.6%      | 0.1% |

H2H (`bid_level_search=True`):

| Matchup | Mean Bid | Distribution |
|---------|----------|-------------|
| R0 self-play | 3.76 | 3: 23%, 4: 77% |
| R0 vs R1 | 2.92 | 1-2: 28%, 3: 51%, 4: 21% |
| R0 vs ME_R0 | 5.14 | 4: 17%, 5: 56%, 6: 22% |
| ME_R1 self-play | 8.82 | 7: 9%, 8: 27%, 9: 32%, 10: 31% |
| ME_R1 vs hybrid | 8.37 | 7: 16%, 8: 31%, 9: 25%, 10: 20% |

**Declaring vs defending asymmetry:**

When R0 faces R1 in H2H, R0 declares ~60% of hands (vs 50% in self-play).
R1 partner features cause more passing, so R0 wins more auctions.

- Declaring yields ~840-910 pts/hand vs ~710-780 defending
- The ~130 pts/hand gap means declaring frequency is a major performance driver
- R1 models declare only 40% against R0 (vs 50% in self-play), losing ~13 pts/hand
  from reduced declaration alone
- R1's 99% make rate (vs R0's 97%) only saves ~4-5 pts/hand — insufficient to
  compensate for the declaring frequency disadvantage

**ME_R1 overbidding diagnosis:**

ME_R1 is NOT defending/passing — it declares 98-99% of hands vs hybrid opponents.
The partner weights (`partner_bid_level: 0.5`, `partner_suit_match: 1.0`,
`partner_passed: -1.0`) add +2-3.5 to the score when the partner bids, pushing
the floor from ~5 to ~8.

- Mean winning bid: 8.35-8.37 vs hybrid opponents; 8.82 in self-play
- Make rate only 70-88% at these levels → frequent sets → -9.475 eppd regression
- The ME_R1 regression is from **catastrophic overbidding**, not from excessive
  passing

This changes the interpretation of partner feature auction dynamics: they are
**bidirectional** — hybrid models pass too much (`partner_passed=-1.0` penalty),
while ME_R1 bids too aggressively (`partner_bid_level` inflation). The current
partner feature design creates unstable auction dynamics in both directions.

---

## 5. Decision Framework

> **2026-03-05 update:** The recommended remediation options below were based on H7
> as root cause. Two-stage training (Option 1) was implemented in PRs #548/#549 and
> tested: it did NOT fix the regression (delta unchanged at -0.348). The structural
> cause is now identified as H10 (bid-level search degeneracy). Remediation must
> address the payoff model in `compute_best_bid()` before further feature or weight
> work can show impact. See H10 hypothesis for details.

Based on Investigation C results: **partner features are net-positive** (+1.3 eppd).
The regression is caused by base weight instability during OLS retraining, not by
partner features themselves.

### Remediation Options (ranked by recommendation)

**Option 1 (Recommended): Two-stage training — freeze hand weights.**
Train base hand features first (R0-style OLS), then add partner features with
base weights frozen and only fit partner coefficients additively. This directly
prevents OLS weight redistribution. Compatible with existing `forward_select()`
`locked_base` mechanism — extend to lock base *weights* not just base *features*.

**Option 2: Weight regularization (Ridge/L2).**
Retrain with L2 penalty to constrain weight magnitudes, preventing extreme
intercept shifts and weight redistribution. Simpler than Option 1 but less
targeted — regularization affects all features equally.

**Option 3: Warm-start from R0 weights.**
Initialize R1 training with R0's fitted weights for the locked base features.
Train all features jointly but starting from a known-good point. Risk: OLS
is a convex problem so warm-start doesn't constrain the final solution — it
would only help if we add regularization toward the R0 weights (elastic net).

**Option 4: Retrain with R1-generated data (address H1 distribution shift).**
Generate new training data with R1 models as the bidding policy so the model
sees R1's bid distribution. This addresses the training-inference distribution
gap but does not directly fix weight instability. May require multiple iterations.

### Not recommended:

**Drop partner features.** Investigation C showed this makes the regression
4.8× worse (-1.661 vs -0.348). Partner features are load-bearing.

### Caution on imputation:

Imputing partner features for the first bidder (e.g., using population means)
is risky — "no partner action yet" is a real state and should stay explicit.
Prefer model structure changes over data imputation.

---

## 6. Feature Design Concern: Coarse Partner Representation

**Identified during Wave 1 review (2026-03-05).**

The current `partner_suit_match` feature operates at the **contract family** level:
it is 1 if the partner bid any suit contract while the observer is evaluating any
suit contract. It does not distinguish which suit the partner bid.

In Bid Euchre, suit relationships matter because of bowers:
- **Same suit** (partner bids hearts, you evaluate hearts): strong positive — shared
  trump, right bower alignment
- **Same color** (partner bids diamonds, you evaluate hearts): moderate positive —
  left bower is shared (J of diamonds is left bower in hearts)
- **Off color** (partner bids spades, you evaluate hearts): neutral to negative —
  no bower overlap, partner strength in competing suit

The current binary `partner_suit_match` conflates all three cases as "1". This is
a design flaw that limits the feature's predictive value and may contribute to the
model learning a noisy signal that destabilizes under distribution shift.

**Resolution:** Formal R1.6 rung added to the master plan for partner-semantics
redesign. R1.5 is the objective-alignment rung (separate concern). R1.6 will
replace the coarse partner representation with suit-aware interaction features:
- `partner_level_same_suit` — exact-match trump support
- `partner_level_same_color_offsuit` — same-color secondary support
- `partner_level_off_color` — off-color alternative support
- `partner_passed` — retained as generic auction-state feature

These are candidate-contract-relative (computed per suit being evaluated) and apply
to suit contracts only. HIGH/LOW retain simpler partner handling.

See `plans/archive/pre_v1/r1_master_plan.md` §10.3a for full R1.6 specification.

### Investigation K: H10 Validation Pack — Analytical Proof + `bid_bonus` Fix

**Status:** COMPLETED (PR #552)
**Purpose:** Analytically prove H10 and prototype a fix

**H10 Analytical Proof:**

The `_compute_ev_static()` payoff model computes:
```
make_ev = 2.0 * E[T|make] - 10.0    (bid-independent)
set_ev  = E[T|set] - bid_n - 10.0   (bid-dependent, penalty grows with bid)
```

Since `make_ev` doesn't depend on `bid_n` but `set_ev` decreases with `bid_n`,
total EV is monotonically non-increasing in `bid_n`. For sigma > 0 (the regime
relevant to all OLS models), EV is strictly decreasing and `compute_best_bid()`
selects `min_legal`. For the degenerate sigma=0 case, EV is flat across all made
bids and the code's tiebreaker (line 884: prefer higher bid on equal utility)
selects the highest made bid, not min_legal. This edge case never occurs with
OLS residual variance but is noted for completeness.

Verified across 100 (mu, sigma) combinations (mu ∈ {3.0, 5.0, 6.5, 8.0, 9.5} ×
sigma ∈ {0.0, 0.5, 1.0, 1.5, 2.5}). EV monotonicity confirmed in all cases.
Min_legal selection confirmed for all sigma > 0 cases.

> **Scope note:** This proof covers the `risk_lambda=0.0` regime (current R0 and
> R1 configuration). `compute_best_bid()` optimizes `utility = ev - risk_penalty`
> (bidding.py:879), not raw EV. With `risk_lambda > 0`, the CVaR penalty term
> could in principle modify the utility surface. Since R0 and R1 both use
> `risk_lambda=0.0` (penalty is zero), the EV-only proof is sufficient for
> interpreting all current H2H results.

**`bid_bonus` Fix:**

Added `bid_bonus` parameter to `_compute_ev_static()` and `compute_best_bid()`:
```
make_ev = 2.0 * E[T|make] - 10.0 + bid_bonus * bid_n
```

This creates a bid-proportional reward that counteracts the monotonic decrease.
With `bid_bonus > 0`, there's a non-trivial optimum near `floor(mu)`. Results:

| mu  | sigma | bonus=0.0 | bonus=0.25 | bonus=0.5 | bonus=1.0 | floor(mu) |
|-----|-------|-----------|------------|-----------|-----------|-----------|
| 5.0 |   1.0 | None      |  3 (+0.71) |  3 (+1.46)|  4 (+3.26)|     5     |
| 6.0 |   1.0 |  1 (+2.00)|  4 (+2.95) |  4 (+3.94)|  5 (+6.06)|     6     |
| 6.5 |   1.5 |  1 (+3.00)|  4 (+3.82) |  4 (+4.80)|  4 (+6.75)|     6     |
| 7.0 |   1.0 |  1 (+4.00)|  5 (+5.19) |  5 (+6.43)|  5 (+8.91)|     7     |
| 8.0 |   1.5 |  1 (+6.00)|  5 (+7.15) |  5 (+8.39)|  6 (+11.19)|    8     |
| 9.0 |   1.0 |  1 (+8.00)|  7 (+9.66) |  7 (+11.40)|  7 (+14.87)|    9    |

**Key observations:**
- `bonus=0.0`: always bid 1 (or pass) — H10 degeneracy confirmed
- `bonus=0.25`: bids jump to 3-7 range — degeneracy broken
- `bonus=0.5–1.0`: bids approach `floor(mu)` — the "natural" bid level
- The fix is backward compatible: `bid_bonus=0.0` preserves all existing behavior

**Recommendation:** Calibrate `bid_bonus` via H2H sweep in a follow-up PR.
`bid_bonus ∈ {0.0, 0.25, 0.5, 0.75, 1.0}` with `bid_level_search=True`.
This is the decisive test: if a non-zero `bid_bonus` resolves the H2H regression,
H10 is confirmed as the primary cause and the payoff model revision path is clear.

**Test coverage:** 101 parametric tests in `tests/unit/test_h10_bid_level_degeneracy.py`:
- 74 proving the degeneracy (EV monotonicity, min_legal selection, floor divergence)
- 27 proving the fix (bonus breaks monotonicity, selects near floor(mu), backward compat)

### Investigation L: `bid_bonus` H2H Sweep — Decision-Layer Causal Probe

**Hypothesis tested:** The R1 H2H regression is caused by the decision layer
(bid-level search degeneracy, H10), not by model quality. If breaking the
degeneracy with `bid_bonus > 0` reverses the regression, this confirms the
decision layer is the bottleneck.

**Important framing:** `bid_bonus` is a **diagnostic probe only**, not a
production fix. It injects synthetic utility (`+ bid_bonus * bid_n` on
make_payoff) that is not grounded in the game's actual scoring rules. If the
probe helps, the correct response is to build a principled decision layer,
not to ship `bid_bonus` as the bidding policy.

**Method:** Wired `bid_bonus` parameter through `HybridOLSaBidder.__init__`
to `compute_best_bid()`. Ran 6-bidder H2H battery: R1 full arm at
bid_bonus ∈ {0.0, 0.25, 0.5, 0.75, 1.0} + R0 full baseline. All bidders
use `bid_level_search=True`, `risk_lambda=0.0`. QUICK mode: 36 matchups ×
2,000 deals = 72,000 total deals, seed 42.

**Results — R1 vs R0 Baseline (R1 in seats 0,2):**

| bid_bonus | delta vs R0 | CI [low, high] | Significant? | Suit avg bid | Suit make% |
|-----------|-------------|----------------|--------------|-------------|------------|
| 0.00      | **-0.348**  | [-0.53, -0.16] | YES (worse)  | 2.76        | 99.6%      |
| 0.25      | **+0.407**  | [+0.19, +0.62] | YES (better) | 3.95        | 97.1%      |
| 0.50      | +0.120      | [-0.12, +0.37] | no           | 4.19        | 96.9%      |
| 0.75      | +0.113      | [-0.14, +0.37] | no           | —           | —          |
| 1.00      | +0.117      | [-0.14, +0.37] | no           | —           | —          |

**Self-play diagnostics:**

| Bidder          | net_eppd (t0) | net_eppd (t1) | bid_rate | make_rate |
|-----------------|---------------|---------------|----------|-----------|
| R0 baseline     | 4.864         | 4.922         | 0.500    | 0.966     |
| R1 bonus=0.00   | 4.676         | 4.800         | 0.468    | 0.993     |
| R1 bonus=0.25   | 4.485         | 4.574         | 0.487    | 0.892     |
| R1 bonus=0.50   | 4.208         | 4.205         | 0.492    | 0.843     |
| R1 bonus=1.00   | 3.796         | 3.832         | 0.501    | 0.773     |

**Contract-type breakdown (R1 in seats 0,2 vs R0):**

| bid_bonus | Suit delta | Suit n | High delta | High n | Low delta | Low n |
|-----------|-----------|--------|-----------|--------|----------|-------|
| 0.00      | -0.758    | 1100   | -0.020    | 398    | +0.289   | 502   |
| 0.25      | -0.456    | 678    | +0.703    | 627    | +0.983   | 695   |
| 0.50      | +0.078    | 588    | +0.115    | 652    | +0.157   | 760   |

**Key findings:**

1. **Decision layer is a major bottleneck.** `bid_bonus=0.25` reverses the
   *overall* R1→R0 delta from -0.348 to +0.407 net_eppd — a swing of +0.755.
   The CI excludes zero in both directions, confirming this is a real effect.
   However, the suit-specific delta remains negative (-0.456) at this setting,
   so the decision layer does not fully explain the original suit regression.

2. **Non-monotonic response.** bid_bonus=0.25 is the sweet spot. Higher
   values (0.50+) still beat R0 on point estimate but lose significance
   due to overbidding (make rate drops from 97% to 83-85%).

3. **Suit regression partially repaired.** At bonus=0.25, suit delta
   improves from -0.758 to -0.456 (still negative). At bonus=0.50, suit
   flips to +0.078. The remaining suit deficit at 0.25 is offset by large
   high/low gains (+0.703, +0.983).

4. **Self-play vs H2H divergence.** Self-play eppd decreases with higher
   bonus (4.68 → 4.49 → 4.21 → 3.80), while H2H performance peaks at
   bonus=0.25. This is consistent with the objective-mismatch diagnosis:
   self-play rewards conservative bidding, H2H rewards auction competitiveness.

5. **Bidding behavior shift.** At bonus=0.00, R1 bids only 2.76 average
   for suit and wins only 39.8% of auctions. At bonus=0.25, average bid
   rises to 3.95 and auction win rate jumps to 68.2%.

**Interpretation:** The decision layer is a major control point: changing it
reverses the overall R1→R0 delta despite leaving the suit-specific deficit
partially unresolved. The R1 model has superior prediction quality
(R² 0.22→0.63) but was constrained by the decision layer forcing min_legal
bids. The residual suit deficit at bonus=0.25 suggests an additional
suit-specific factor beyond bid-level selection (possibly contract-selection
dynamics or suit-specific model calibration). This motivates building a
principled objective-aligned decision layer as the next rung, rather than
further feature engineering.

**What bid_bonus is NOT:** A production bidding rule. It adds utility that
doesn't exist in the game's scoring rules (the game doesn't reward higher
bids on make). The correct fix is to model the auction-strategic value of
bidding higher (forcing opponents, winning declarations) rather than
injecting synthetic rewards.

**Reproduction:**
```bash
# Wiring: bid_bonus param added to HybridOLSaBidder (PR #554)
# Roster: experiments/configs/r1_bid_bonus_sweep_roster.json
# Run:
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode QUICK --seed 42 --n-per 2000 \
    --roster experiments/configs/r1_bid_bonus_sweep_roster.json \
    --output data/artifacts/arc_d/r1/bid_bonus_sweep/h2h_battery_quick.json
# Parse:
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --mode QUICK --seed 42 --n-per 2000 \
    --roster experiments/configs/r1_bid_bonus_sweep_roster.json \
    --output data/artifacts/arc_d/r1/bid_bonus_sweep/h2h_battery_quick.json \
    --parse-run data/runs/arc_d_r0_h2h_battery_42_20260305_211613
```

---

## 7. Relationship to R1.5, R1.6, and R2

**Rung definitions (formalized 2026-03-06):**

Investigation L confirms the decision layer as a major bottleneck. The informal
"decision-layer rung" referenced in earlier iterations is now formally defined as
**R1.5** in the Arc D ladder.

- **R1 (concluded):** Trick-target rung with coarse partner features. H10 confirmed
  analytically; `bid_bonus` probe confirms decision layer is a major control point.
  R1 is preserved as a historical result — the H2H regression is real and informative.
- **R1.5 (objective-alignment):** Replace trick prediction + hand-coded utility with
  direct action-value / E[points] modeling. Addresses the structural mismatch between
  training objective (tricks) and evaluation metric (points). Implementation spec in
  plans/r1_5_training_plan.md (to be created in follow-up implementation-spec PR).
- **R1.6 (partner-semantics):** Richer suit-aware partner features
  (partner_level_same_suit, etc.). Scope unchanged from the original R1.5 definition,
  but renumbered. Deprioritized relative to objective-alignment work. The residual
  suit deficit at bonus=0.25 may partially be addressable here.
- **R2 (opponent context):** Deferred until R1.5 objective and R1.6 partner semantics
  are stabilized.

### Program Decision

1. **R1 is preserved as-is.** The H2H regression is a valid finding under the
   trick-target architecture and should not be rewritten away.
2. **R1.5 is the next rung.** It addresses the objective mismatch diagnosed by H10
   and confirmed by Investigation L.
3. **R1.6 follows R1.5.** Richer partner semantics are tested against the R1.5
   objective, isolating the value of better features from the value of a better target.
4. **`bid_bonus` is a diagnostic probe only.** It confirmed the bottleneck but is not
   the architectural answer.

---

## 8. Provenance

| Item | Value |
|------|-------|
| H2H run | `arc_d_r0_h2h_battery_42_20260304_210528` |
| Seed | 42 |
| Deals per matchup | 2,000 |
| R1 full artifact | data/artifacts/arc_d/r1/hybrid_r1_full.json |
| R1 constrained artifact | data/artifacts/arc_d/r1/hybrid_r1.json |
| R0 full artifact | data/artifacts/arc_d/r0/hybrid_r0_full.json |
| R0 constrained artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| Training data | data/runs/canonical_auction_r1_42/datasets/bidless.parquet |
| ME_r1 config fix | PR #536 (partner_weights updated before this run) |
| Bootstrap | 10,000 resamples, seed 42 |
| Prior report | partner_feature_selection_diagnostic.md |
| Investigation C ablation run | `arc_d_r0_h2h_battery_42_20260305_131433` |
| Investigation C roster | experiments/configs/r1_investigation_c_roster.json |
| Investigation C artifact | data/artifacts/arc_d/r1/investigation_c_ablation.json |
| Investigation K tests | tests/unit/test_h10_bid_level_degeneracy.py (101 parametric tests) |
| Investigation K code | `_compute_ev_static()` and `compute_best_bid()` in bidding.py |
| Investigation L run | `arc_d_r0_h2h_battery_42_20260305_211613` |
| Investigation L roster | experiments/configs/r1_bid_bonus_sweep_roster.json |
| Investigation L summary | data/artifacts/arc_d/r1/bid_bonus_sweep/h2h_battery_quick.json |
| Investigation L wiring | `HybridOLSaBidder.bid_bonus` param in bidding.py |
