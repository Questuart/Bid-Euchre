# R1.5-v2 Partner Feature Ablation + Phase 3 Interaction Terms

**Date:** 2026-03-10
**Parent plan:** `plans/sessions/2026-03-09_r1-5-v2-diagnostic-plan.md`
**Status:** ACTIVE
**Answers:** Q12 (partner features), Q5 (OLS linearity)

## Motivation

R1.5-v2 Phase 1 found that features are "irrelevant" (R² delta < 0.005 between
39 and 52 features). But this was an offline R² comparison — Cell A couldn't
load into ActionValueBidder for gameplay testing due to strict feature_names
validation.

**Missing experiment:** H2H comparison of AV v1 with partner features removed
vs R0. This isolates whether partner context helps, hurts, or is neutral for
gameplay — particularly for the suit regression (-0.142 net_eppd).

**Key distinction from Cell A:** The `"r0"` feature set (39 features) drops
partner features AND positional/contract indicators (current_high_bid, is_high,
is_low, trump dummies, seat dummies). A `"no-partner"` set keeps those
indicators, only removing the 3 auction-context features.

## Step 7b: Partner Feature Isolation H2H

**What:** Train ActionValueBidder with partner features zeroed out, then run
H2H against R0 and AV v1.

### Implementation: Zero-Mask Approach

Zero the 3 partner columns (`partner_bid_level`, `partner_passed`,
`partner_suit_match`) in the training DataFrame before fitting OLS. This
produces a model with:
- Standard 54-element `feature_names` (passes ActionValueBidder validation)
- Exactly-zero coefficients for partner columns (OLS property: zero input
  column → zero weight)
- Identical coefficients for non-partner features as training without those
  columns

**Why not drop columns?** ActionValueBidder validates `feature_names ==
STATE_FEATURE_NAMES + ACTION_FEATURE_NAMES` (54 features). A 51-feature model
won't load without bidder code changes.

**Why zero-masking is mathematically sound:** A column of all zeros in X has
zero covariance with Y and zero covariance with all other columns. `_fit_ols()`
(in `src/bid_euchre/models/train_olsa.py:50`) will hit `LinAlgError` from the
singular `XtX` matrix and fall back to `np.linalg.lstsq(rcond=None)`, which
handles rank deficiency correctly. The resulting coefficients for zero columns
are numerically zero (< 1e-30, at floating-point noise scale), and
non-zero-column coefficients are identical to the column-dropped regression.

### Code Changes

**File: `scripts/internal/train_action_value.py`**

1. Add `"no-partner"` to `FEATURE_SETS`:
   ```python
   # Partner feature column names (positions 39-41 in STATE_FEATURE_NAMES)
   _PARTNER_FEATURE_NAMES = ["partner_bid_level", "partner_passed", "partner_suit_match"]

   FEATURE_SETS: dict[str, list[str]] = {
       "full": list(STATE_FEATURE_NAMES),
       "r0": list(STATE_FEATURE_NAMES[:_N_R0_HAND_FEATURES]),
       "no-partner": list(STATE_FEATURE_NAMES),  # full features, zeroed at training
   }
   ```

2. Add `--mask-columns` logic in `load_dataset()` or after loading:
   ```python
   # Zero-mask partner features for "no-partner" ablation
   if feature_set == "no-partner":
       for col in _PARTNER_FEATURE_NAMES:
           df[col] = 0.0
   ```

3. No changes to `build_artifact()` — the artifact uses full `STATE_FEATURE_NAMES`
   and `ACTION_FEATURE_NAMES`, so it loads in ActionValueBidder as-is.

### Training Command

```bash
uv run python scripts/internal/train_action_value.py \
  --seed 42 --feature-set no-partner --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_no_partner_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --skip-validation  # pass R²=0.005 < gate threshold 0.02 (expected without partner context)
```

### H2H Config

3-bidder battery (9 matchups: 3 self-play + 6 cross-matchups with seat rotations):
- `action_value_v1` — full AV model (existing)
- `action_value_no_partner` — partner-zeroed AV model (new)
- `hybrid_olsa_full_r0` — R0 baseline (existing)

### Acceptance Criteria

**Sample size:** QUICK (2,500 deals per matchup, seed=42) — diagnostic ablation,
not promotion-gating. Sufficient for directional signal (prior ablation H2H used
same scale).

**Success criteria (directional, not threshold-gated):**
- R² comparison: no-partner vs full (expect delta < 0.01 given offline finding)
- H2H: no-partner vs R0 — does suit delta change vs full-AV vs R0?
- H2H: no-partner vs full-AV — direct partner feature value assessment
- If partner features are hurting suit (delta < -0.05): investigate further
- If neutral (|delta| < 0.05): proceed to Step 8 (interaction terms) with full features
- If helping (delta > 0.05): partner features are beneficial, proceed to Step 8 with full features

### Files Touched

- `scripts/internal/train_action_value.py` — add `"no-partner"` feature set + zero-mask logic
- `tests/unit/test_train_action_value.py` — test for no-partner feature set (zero-mask, artifact validation)

### Estimated Effort

1 PR: code change + training + H2H + report section in `v2_ablation_analysis.md`.

---

## Step 8: Suit Interaction Features (from parent plan)

**Answers:** Q5 (OLS linearity vs missing features)

**What:** Add interaction terms to the AV suit model only:
- `bowers × trump_count` — bower strength × trump length
- `trump_count × trump_count` — quadratic trump length (trump_count²)
- `bowers × bowers` — quadratic bower count (bowers²)

Note: `trump_count_x_offsuit_ace` (feature #36) already exists in the registry.
These new terms target bower-specific non-linearities that #36 doesn't capture.

### Implementation Approach

TBD — depends on Step 7b results. Two paths:
1. If partner features are neutral: add interaction terms to full feature set
2. If partner features hurt suit: add interaction terms to no-partner set

The interaction term implementation requires extending `extract_state_features()`
or adding a post-extraction feature augmentation step. The ActionValueBidder
feature validation must be updated to accept the augmented feature list.

### Estimated Effort

1-2 PRs depending on complexity.

---

## Step 9: Evaluation (from parent plan)

If interaction terms improve suit R² and/or H2H delta, run FULL evaluation.
Phase 2 was skipped, so "combined model" step simplifies to interaction terms
alone.

---

## PR Sequence

| PR | Content | Step |
|----|---------|------|
| 1 | Partner ablation: no-partner feature set + training + H2H + report | 7b |
| 2 | Interaction terms: feature engineering + suit retraining + H2H | 8 |
| 3 | FULL evaluation (conditional on Step 8 results) | 9 |

## Outcome

(To be filled after implementation)
