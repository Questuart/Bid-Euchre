# R1 H2H Suit Regression Diagnostic

**Date:** 2026-03-05
**Status:** IN PROGRESS — hypotheses documented, investigations pending
**Blocking:** Gate X3 (STOP), Steps 6–12 of R1 training plan
**Provenance:** H2H battery run `arc_d_r0_h2h_battery_42_20260304_210528`, seed 42, 2k deals/matchup

## Quick Context

R1 added 4 **partner bidding context features** (extracted from auction transcripts)
to the OLSa hybrid bidder. These features describe what the partner bid during
the auction (bid level, whether they passed, whether they bid the same contract
family). Training R² improved dramatically (+0.40 for suit), but H2H game
performance **regressed** by -0.76 pts/deal for suit contracts.

This report documents the regression, proposes hypotheses for why it happened,
and lays out a concrete investigation plan with reproduction commands.

**Key files:**
- Training pipeline: `src/bid_euchre/models/train_hybrid_olsa.py`
- Runtime bidding: `src/bid_euchre/strategy/bidding.py` (HybridOLSaBidder)
- Partner feature extraction: `src/bid_euchre/features/auction_context.py`
- R1 training plan: `plans/r1_training_plan.md`
- R1 master plan: `plans/r1_master_plan.md`

**Investigation priority order:**

1. **F (bug audit)** — Rule out implementation bugs first. If found, fixes
   invalidate all ML conclusions. Code review + spot checks, no re-runs needed.
2. **B (bid/set rates)** — Free (log parsing). Determines if R1 over-bids in suit.
3. **E (partial R²)** — Free (training data). Quantifies partner feature leakage.
4. **C (zero-out ablation)** — Definitive test. Small code change + H2H re-run.
5. **D (distribution shift)** — May need re-run with `log_level: full` if
   auction transcripts are not in current logs.

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

---

## 2. Hypotheses

### H1: Training-Inference Distribution Shift (Primary)

**Claim:** The suit model learned partner feature distributions from R0's bidding
behavior, but at H2H inference both seats use R1 models, which bid differently.

**Mechanism:**
- Training data generated with R0 model (no partner awareness) in all seats
- R0's bid-level distribution in suit contracts defines the "normal" range for
  `partner_bid_level`, `partner_passed`, `partner_bid_confidence`
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

**Status:** PENDING

**Findings:**

_(to be filled after investigation)_

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

**Status:** PENDING

**Findings:**

_(to be filled after investigation)_

### Investigation D: Training vs Inference Bid Distribution

**Question:** How much does the partner feature distribution shift between
training data (R0-generated) and H2H inference (R1-generated)?

**Method:**
1. Load training parquet, filter to suit, compute summary stats for
   `partner_bid_level`, `partner_passed`, `partner_suit_match`, `partner_bid_confidence`
2. Load R1 self-play H2H logs, extract the same features from auction transcripts
3. Compare means, standard deviations, and distributions
4. Estimate prediction error: `shift_in_feature × model_weight`

**Reproduction:**

```python
# Step 1: Training data partner feature distribution (suit only)
import pandas as pd
train = pd.read_parquet("data/training/r1/canonical_auction_context_42.parquet")
suit_train = train[train["contract_type"] == "suit"]
for col in ["partner_bid_level", "partner_passed", "partner_suit_match", "partner_bid_confidence"]:
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
        if record.get("contract_type") != "suit":
            continue
        transcript = record.get("auction_transcript", [])
        for seat in range(4):
            pf = extract_partner_features(seat, transcript, observer_best_contract="suit")
            partner_feats.append(pf)

import pandas as pd
inference_df = pd.DataFrame(partner_feats)
for col in ["partner_bid_level", "partner_passed", "partner_suit_match", "partner_bid_confidence"]:
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

for col in ["partner_bid_confidence", "partner_passed", "partner_suit_match"]:
    if col in weight_map:
        shift = inference_df[col].mean() - suit_train[col].mean()
        contribution = shift * weight_map[col]
        print(f"{col}: shift={shift:+.3f}, weight={weight_map[col]:.3f}, "
              f"prediction_shift={contribution:+.3f} tricks")
```

Note: The JSONL may or may not include `auction_transcript` depending on
`log_level`. If not present, this investigation requires re-running the
self-play matchup with `log_level: full` or a modified logger. Check with:
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
train = pd.read_parquet("data/training/r1/canonical_auction_context_42.parquet")
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

**Status:** PENDING

**Findings:**

_(to be filled after investigation)_

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
train = pd.read_parquet("data/training/r1/canonical_auction_context_42.parquet")
suit_train = train[train["contract_type"] == "suit"].iloc[0]

# Show what the training data recorded
print("Training data partner features:")
for col in ["partner_bid_level", "partner_passed", "partner_suit_match", "partner_bid_confidence"]:
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

**Status:** PENDING — should be investigated BEFORE the ML hypotheses (B, E)
since a bug would invalidate all ML conclusions.

**Findings:**

_(to be filled after investigation)_

---

## 4. Decision Framework

Based on investigation results, the following actions are possible:

### If partner features are net-harmful (C confirms):

**Option 1: Drop partner features for R1 suit models.**
Re-run with `context_candidates=None` for suit, keep `partner_suit_match` for
high/low (where it's neutral/positive). Accept R0-level suit R².

**Option 2: Iterate training policy (address H1).**
Generate new training data with R1 models as the bidding policy. Retrain on
R1-generated auctions so the model sees R1's bid distribution. Risk: this
may require multiple iterations to converge, and H3 leakage persists.

**Option 3: Restrict to robust features only.**
Keep only `partner_suit_match` (selected by high/low, moderate weight ~2.6-3.5)
and drop the bid-level features. This limits exposure while retaining the
contract-family signal.

### If partner features are helpful but miscalibrated (C shows partial improvement):

**Option 4: Weight regularization.**
Retrain with L2 penalty to shrink partner feature weights, reducing sensitivity
to distribution shift.

**Option 5: Clip partner features at inference.**
Cap partner_bid_level/confidence to training-data range to prevent extrapolation.

---

## 5. Relationship to R2 Protocol

The pre-registered R2 context-feature protocol (plans/r2_follow_ups.md §F1)
already calls for rebalanced training and forced-inclusion sensitivity analysis.
The suit regression findings here may accelerate or redirect that protocol.

If partner features are dropped for R1 suit, the R2 protocol should investigate:
- Whether rebalanced data (≥10k suit hands) changes selection
- Whether iterative training policy converges
- Whether causal deconfounding (e.g., residualizing partner bid on partner hand
  quality) produces a usable signal

---

## 6. Provenance

| Item | Value |
|------|-------|
| H2H run | `arc_d_r0_h2h_battery_42_20260304_210528` |
| Seed | 42 |
| Deals per matchup | 2,000 |
| R1 full artifact | data/artifacts/arc_d/r1/hybrid_r1_full.json |
| R1 constrained artifact | data/artifacts/arc_d/r1/hybrid_r1.json |
| R0 full artifact | data/artifacts/arc_d/r0/hybrid_r0_full.json |
| R0 constrained artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| Training data | data/training/r1/canonical_auction_context_42.parquet |
| ME_r1 config fix | PR #536 (partner_weights updated before this run) |
| Bootstrap | 10,000 resamples, seed 42 |
| Prior report | partner_feature_selection_diagnostic.md |
