# R1.6 Partner-Semantics Features on GBT

**Date:** 2026-03-13
**Arc:** D — Action-Value Bidder
**Rung:** R1.6 (partner context expansion)
**Parent spec:** `plans/archive/r1_master_plan.md` §10.3a
**Prerequisite:** GBT FULL validation (R1.5.3 Track A) — can develop in parallel

## Goal

Replace the coarse 3-feature partner context (`partner_bid_level`,
`partner_passed`, `partner_suit_match`) with **candidate-contract-relative**
partner features that capture Euchre-specific suit relationships. Train on GBT
(not OLS), which can exploit nonlinear interactions between partner signals and
hand strength.

**Prerequisite (PR A):** First refactor the bidder infrastructure to support
artifact-driven feature extraction, so v7 and v8 artifacts can coexist in the
same H2H battery.

## Motivation

The current `partner_suit_match` is binary — it can't distinguish between:
- Partner bid 7 in your exact suit (strong direct support — shared bowers)
- Partner bid 5 in same-color offsuit (moderate — left bower overlap)
- Partner bid 7 in opposite color (weak/negative — no bower overlap)

In Euchre, **same-color suits share a bower** (left bower of diamonds is J of
hearts). A partner bidding hearts when you're evaluating diamonds signals
strength in your left-bower suit. A partner bidding clubs when you have hearts
provides no bower support and may indicate competing suit preferences.

GBT can learn interaction effects (bid_level × suit_relation × hand_strength)
that OLS cannot. The R1.6 spec was designed for OLS; on GBT, these features
may have outsized impact.

## Feature Design

### New Features (suit contracts only)

| Feature | Definition | Euchre Semantics |
|---------|-----------|------------------|
| `partner_level_same_suit` | Max bid level partner made in candidate trump suit | Direct support — shared trump + right bower |
| `partner_level_same_color` | Max bid level partner made in same-color offsuit | Indirect support — left bower overlap |
| `partner_level_off_color` | Max bid level partner made in either off-color suit | Weak/competing — no bower connection |
| `partner_passed` | 1 if partner passed (retained from current) | Auction state signal |

**Color mapping** (from `src/bid_euchre/core/cards.py` `SAME_COLOR_SUIT`):
- H ↔ D (red), S ↔ C (black)

**Examples** (evaluating hearts as candidate trump):
- Partner bid 7H → `same_suit=7, same_color=0, off_color=0`
- Partner bid 5D → `same_suit=0, same_color=5, off_color=0`
- Partner bid 6S → `same_suit=0, same_color=0, off_color=6`
- Partner bid 3D then 7H → `same_suit=7, same_color=3, off_color=0`

### Replaced Features

| Removed | Reason |
|---------|--------|
| `partner_bid_level` | Subsumed by max of the three level channels |
| `partner_suit_match` | Subsumed by `partner_level_same_suit > 0` |

### High/Low Contract Handling

High and low contracts have no trump suit, so suit-relative features don't
apply. For high/low and pass:
- `partner_level_same_suit` = `partner_level_same_color` = `partner_level_off_color` = 0
- `partner_passed` = as computed

This is semantically clean — high/low have no bowers and no color semantics.
The zeroed channels let GBT learn that partner suit information is irrelevant
for these contract types.

## PR Structure

### PR A: Artifact-Driven Feature Extraction (refactor, no new features)

**Goal:** Make bidder classes drive feature extraction from the artifact's
stored `feature_names` rather than the global `STATE_FEATURE_NAMES` constant.
This fixes an architectural bug and enables v7/v8 artifact coexistence.

**Design principles:**
- Artifact declares `feature_names` (already stored in all artifacts)
- Bidder validates against what the artifact says it needs
- Inference extracts exactly those features, in that order
- `STATE_FEATURE_NAMES` becomes a default/canonical enumeration, not runtime truth

#### Changes

| File | Change |
|------|--------|
| `src/bid_euchre/strategy/bidding.py` | Add `partner_feature_names` param to `extract_state_features()`. Add `_infer_partner_features()` helper. Update `ActionValueBidder.__init__()` (line ~1678), `GBTActionValueBidder.__init__()` (line ~1814), `TwoStageActionValueBidder.__init__()` (line ~1960) to derive expected features from artifact's `feature_names` instead of global constant. Update all `choose_bid()` methods to pass `self._partner_feature_names`. |
| `tests/unit/test_action_value_bidder.py` | Update tests for parameterized extraction. Add test that v7 artifact loads correctly with new validation logic. |

#### Key implementation detail

```python
def _infer_partner_features(feature_names: list[str]) -> list[str]:
    """Extract partner feature subset from a full feature list.

    Partner features sit between hand features (39) and positional features.
    """
    hand_end = len(_HAND_FEATURE_NAMES)  # 39
    positional_start = feature_names.index("current_high_bid")
    return feature_names[hand_end:positional_start]
```

Bidder `__init__` changes from:
```python
expected_bid_features = STATE_FEATURE_NAMES + ACTION_FEATURE_NAMES
if list(model["feature_names"]) != expected_bid_features:
    raise ValueError(...)
```
To:
```python
artifact_feature_names = list(model["feature_names"])
self._partner_feature_names = _infer_partner_features(artifact_feature_names)
expected = _HAND_FEATURE_NAMES + self._partner_feature_names + _POSITIONAL_NAMES + ACTION_FEATURE_NAMES
if artifact_feature_names != expected:
    raise ValueError(...)
```

#### Validation
- All existing tests pass (v7 artifacts load identically)
- `make check-quiet` passes
- No new features, no schema change, no dataset regeneration

### PR B: R1.6 Partner Features (new features + training + eval)

**Depends on:** PR A merged.

#### Step 1: Feature Extraction (`auction_context.py`)

Add `extract_partner_features_v2(seat, auction_transcript, candidate_trump_suit)`:
- Uses `SAME_COLOR_SUIT` from `src/bid_euchre/core/cards.py` for color mapping
- Returns dict with 4 features (3 level channels + passed)
- Add `PARTNER_FEATURE_NAMES_V2` constant
- Register v2 feature set in `bidding.py` `_PARTNER_FEATURE_SETS` registry

**Tests** (`tests/unit/test_auction_context.py`):
- All 4 color combinations (same suit, same color, off color × 2)
- Multi-bid transcripts (partner bids multiple times)
- High/low bids in transcript (trump=None → no channel contribution)
- Empty transcript (all zeros)

#### Step 2: Feature Integration (`bidding.py`)

Update `extract_state_features()` to dispatch to v2 when `partner_feature_names`
matches `PARTNER_FEATURE_NAMES_V2`. The dispatch is already enabled by PR A's
parameterized extraction — PR B adds the v2 branch.

Net feature count change: 52 → 53 state features (3 partner → 4 partner).

#### Step 3: Dataset Regeneration

The counterfactual dataset generator (`scripts/internal/generate_action_value_dataset.py`)
calls `extract_state_features()` — pass the v2 feature names to generate v8 data.

- **Must regenerate training data** after feature schema change
- New schema version: v8 (currently v7)
- Generate: SMOKE (sanity), QUICK (training)

#### Step 4: Training

Train GBT with new features:
- `--model-class gbt --feature-set full`
- Artifact stores v8 `feature_names` automatically (training records whatever
  columns the dataset has)
- Add `"feature_schema_version": "v8"` to artifact metadata

#### Step 5: H2H Evaluation

- **QUICK screen:** 3-bidder battery (GBT-v2, GBT-v1, R0), N=2000 paired deals, seed 42
- GBT-v1 loads its v7 artifact with v7 feature extraction (enabled by PR A)
- GBT-v2 loads its v8 artifact with v8 feature extraction
- Per-contract breakdown mandatory (suit is the target)
- **Success criteria:** GBT-v2 suit delta > GBT-v1 suit delta (vs R0)
- **If QUICK passes:** FULL confirmation (N=50000, 3 seeds) for promotion

## Files Modified (both PRs combined)

| File | PR | Change |
|------|-----|--------|
| `src/bid_euchre/strategy/bidding.py` | A+B | Parameterize extraction (A), add v2 dispatch (B) |
| `src/bid_euchre/features/auction_context.py` | B | Add `extract_partner_features_v2`, `PARTNER_FEATURE_NAMES_V2` |
| `scripts/internal/generate_action_value_dataset.py` | B | Pass v8 feature names to extraction |
| `scripts/internal/train_action_value.py` | B | Store `feature_schema_version` in artifact metadata |
| `tests/unit/test_auction_context.py` | B | v2 extraction tests |
| `tests/unit/test_action_value_bidder.py` | A+B | Artifact-driven validation tests (A), v8 loading tests (B) |
| `docs/01_core/FEATURE_REGISTRY.md` | B | Update to v8 schema |

## Gates

| Gate | Criterion | Threshold |
|------|-----------|-----------|
| X0 | PR A: all existing tests pass, v7 artifacts load | `make check-quiet` PASS |
| X1 | Training completes, R² not regressed | suit R² ≥ 0.59 (GBT-v1 baseline) |
| X2 | H2H suit delta improvement over GBT-v1 | > 0 |
| X3 | Pooled H2H vs R0 not regressed from GBT-v1 | ≥ +1.0 |

## Schema Compatibility

**The core problem:** Current bidder classes validate loaded artifacts against
the global `STATE_FEATURE_NAMES` constant. Changing this constant from 52→53
features breaks all existing v7 artifacts.

**Solution (PR A):** Make bidders artifact-driven:
- Bidder reads `feature_names` from the artifact
- Infers which partner feature set to use via `_infer_partner_features()`
- Validates structural consistency (hand + partner + positional + action = total)
- Passes `partner_feature_names` to `extract_state_features()`
- `STATE_FEATURE_NAMES` becomes the v7 canonical default, not runtime truth

**Result:** v7 and v8 artifacts coexist in the same H2H battery. Each bidder
extracts features matching its own artifact's schema.

## Risk Assessment

- **Low risk:** PR A is a pure refactor — no new features, no schema change
- **Low risk:** Feature extraction is straightforward (color mapping already exists in `SAME_COLOR_SUIT`)
- **Medium risk:** Feature count change (52→53) requires dataset regeneration
  and careful alignment between training and inference
- **Key assumption:** GBT can exploit suit-relative partner signals. If partner
  context is noise relative to hand strength, all three channels will have
  near-zero importance (detectable via GBT feature importances)

## Outcome

_To be filled after implementation._
