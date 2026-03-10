# R1.5-v2 Step 8: Suit Interaction Terms

**Date:** 2026-03-10
**Parent plan:** `plans/sessions/2026-03-10_r1-5-v2-partner-ablation.md` (Step 8)
**Status:** ACTIVE
**Answers:** Q5 (OLS linearity vs missing features)
**Diagnostic plan ref:** `plans/sessions/2026-03-09_r1-5-v2-diagnostic-plan.md` Phase 3

## Goal

Add interaction features to capture bower-specific non-linearities in the suit
model. The suit regression (-0.142 net_eppd) may stem from OLS missing
non-linear relationships between trump strength variables. Two interaction
terms already exist (`trump_count_x_void_count`, `trump_count_x_offsuit_ace`
at positions 36-37 of 39 hand features). This step adds three more targeting
bower-trump interactions.

## Design Decision: Training-Only vs Feature Expansion

### The Problem

ActionValueBidder validates `feature_names == STATE_FEATURE_NAMES +
ACTION_FEATURE_NAMES` exactly (line 1533 of `bidding.py`). Adding new features
to `_HAND_FEATURE_NAMES` would:
1. Break all existing AV artifacts (feature count mismatch)
2. Require regenerating the counterfactual dataset (new columns needed)
3. Change `STATE_FEATURE_NAMES` globally, affecting all downstream code

### Chosen Approach: Training-pipeline-only computed features

Compute interaction terms in `_build_feature_matrix()` of
`scripts/internal/train_action_value.py`, similar to how `bid_n_sq` is already
computed from `bid_n`. The interaction terms are derived from existing columns
in the parquet dataset (`bowers`, `trump_count`), so no dataset regeneration
is needed.

**Trade-off:** The artifact stores expanded `feature_names` (55+ elements), but
ActionValueBidder's strict validation requires updating the validation to accept
them. We create a new `InteractionValueBidder` subclass (or add a compatibility
path to `ActionValueBidder`) that handles the expanded feature vector at
inference time.

### Why not modify `hand_eval.py` / `STATE_FEATURE_NAMES`?

1. Changing `STATE_FEATURE_NAMES` breaks the dataset contract — existing parquet
   files lack the new columns, requiring full dataset regeneration
2. The counterfactual dataset is expensive to generate (Step 1, ~5 min at QUICK)
3. These interactions are diagnostic — if they don't help, we don't want to
   pollute the feature registry permanently
4. `bid_n_sq` already establishes the pattern of training-pipeline-computed features

## Plan

### Step 8a: Add interaction term computation to training pipeline

**File: `scripts/internal/train_action_value.py`**

1. Define the interaction terms as computed features:
   ```python
   # Interaction terms computed from existing columns (not in dataset)
   _INTERACTION_FEATURE_NAMES = [
       "bowers_x_trump_count",   # bowers * trump_count
       "trump_count_sq",         # trump_count ** 2
       "bowers_sq",              # bowers ** 2
   ]

   _INTERACTION_FORMULAS: dict[str, tuple[str, str, str]] = {
       # name -> (col_a, col_b, operation)
       "bowers_x_trump_count": ("bowers", "trump_count", "multiply"),
       "trump_count_sq": ("trump_count", "trump_count", "multiply"),
       "bowers_sq": ("bowers", "bowers", "multiply"),
   }
   ```

2. Add `"interaction"` to `FEATURE_SETS`:
   ```python
   FEATURE_SETS: dict[str, list[str]] = {
       "full": list(STATE_FEATURE_NAMES),
       "r0": list(STATE_FEATURE_NAMES[:_N_R0_HAND_FEATURES]),
       "no-partner": list(STATE_FEATURE_NAMES),
       "interaction": list(STATE_FEATURE_NAMES) + _INTERACTION_FEATURE_NAMES,
   }
   ```

3. Update `_build_feature_matrix()` (line 266) to compute interaction terms:
   ```python
   def _build_feature_matrix(df: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
       cols = []
       for name in feature_names:
           if name == "bid_n_sq":
               cols.append(df["bid_n"].values ** 2)
           elif name in _INTERACTION_FORMULAS:
               col_a, col_b, op = _INTERACTION_FORMULAS[name]
               if op == "multiply":
                   cols.append(df[col_a].values * df[col_b].values)
           else:
               cols.append(df[name].values)
       return np.column_stack(cols).astype(np.float64)
   ```

   This extends the existing `bid_n_sq` pattern — no API change needed.

### Step 8b: Update ActionValueBidder to support interaction features

**File: `src/bid_euchre/strategy/bidding.py`**

The strictest-change approach: add a `compute_interaction_features()` function
and update `ActionValueBidder` to compute interactions at inference time when
the artifact's `feature_names` includes interaction terms.

1. Add the interaction computation function:
   ```python
   _INTERACTION_FEATURES: dict[str, tuple[int, int]] = {
       # name -> (index_a, index_b) in STATE_FEATURE_NAMES
       "bowers_x_trump_count": (0, 1),  # bowers=0, trump_count=1
       "trump_count_sq": (1, 1),
       "bowers_sq": (0, 0),
   }

   def compute_interaction_features(state: np.ndarray) -> np.ndarray:
       """Compute interaction terms from a 52-element state vector."""
       interactions = []
       for name, (idx_a, idx_b) in _INTERACTION_FEATURES.items():
           interactions.append(state[idx_a] * state[idx_b])
       return np.array(interactions, dtype=np.float64)
   ```

2. Update `ActionValueBidder.__init__()` validation (line 1523):
   - Detect if artifact uses interaction features by checking
     `artifact.get("feature_set") == "interaction"`
   - If so, validate against `STATE_FEATURE_NAMES + _INTERACTION_FEATURE_NAMES + ACTION_FEATURE_NAMES`
     for bid models, `STATE_FEATURE_NAMES + _INTERACTION_FEATURE_NAMES` for pass
   - Store `self._has_interactions = True`

3. Update `choose_bid()` (line 1550):
   ```python
   state = extract_state_features(obs, family, trump_suit)
   if self._has_interactions:
       interactions = compute_interaction_features(state)
       state = np.concatenate([state, interactions])
   action_feats = extract_action_features(action.n)
   features = np.concatenate([state, action_feats])
   ```

### Step 8c: Train interaction model + R² comparison

**Command:**
```bash
uv run python scripts/internal/train_action_value.py \
  --seed 42 --feature-set interaction --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_interaction_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
```

**Expected R² comparison:**
| Contract | Full (AV v1) | Interaction | Delta |
|----------|-------------|-------------|-------|
| suit | 0.565 | TBD | target: > +0.01 |
| high | 0.533 | ~same | ~0 (no bower interactions for high) |
| low | 0.514 | ~same | ~0 (no bower interactions for low) |

Note: interaction terms are only meaningful for suit contracts (bowers and
trump_count are zero for high/low). High/low should show negligible R² change.

### Step 8d: H2H gameplay evaluation

**Config:** 3-bidder battery (9 matchups, seed=42, n=2500):
- `action_value_v1` — full AV model (existing)
- `action_value_interaction` — AV model with interaction terms (new)
- `hybrid_olsa_full_r0` — R0 baseline (existing)

**Success criteria (directional):**
- Primary: suit net_eppd delta vs R0 (target: closer to 0 or positive)
- Secondary: pooled net_eppd delta vs R0 (target: >= +0.152 baseline)
- If suit delta improves by > 0.05 net_eppd: interaction terms are working
- If no improvement: Q5 answered — OLS linearity is not the issue, the problem
  is in the bimodal target distribution (confirming Phase 2 findings)

### Step 8e: Update reports

- Add Section 6 to `docs/04_reports/r1_5/v2_ablation_analysis.md`: interaction
  term results (R², H2H, suit delta comparison)
- Update Q5 in `docs/04_reports/r1_5/r1_5_questions.md` from PLANNED to ANSWERED
- Fill Outcome section in this plan

## Files Touched

| File | Change |
|------|--------|
| `scripts/internal/train_action_value.py` | Add `_INTERACTION_FEATURE_NAMES`, `_INTERACTION_FORMULAS`, `"interaction"` feature set, update `_build_feature_matrix()` |
| `src/bid_euchre/strategy/bidding.py` | Add `_INTERACTION_FEATURES`, `compute_interaction_features()`, update `ActionValueBidder` validation + `choose_bid()` |
| `tests/unit/test_train_action_value.py` | Tests for interaction feature set, computed features in `_build_feature_matrix()` |
| `tests/unit/test_bidding.py` | Tests for `compute_interaction_features()`, interaction-aware `ActionValueBidder` loading |
| `docs/04_reports/r1_5/v2_ablation_analysis.md` | New section with results |
| `docs/04_reports/r1_5/r1_5_questions.md` | Q5 updated |

## Acceptance Criteria

**Sample size:** QUICK (2,500 deals per matchup, seed=42) — diagnostic,
not promotion-gating.

**R² gate:** No formal threshold. Interaction terms are diagnostic. Even a
small R² improvement on suit (> +0.005) is informative.

**H2H gate:** Directional — does suit net_eppd improve vs R0? Any improvement
> 0.05 in the suit component is meaningful given the -0.142 deficit.

## PR Sequence

Single PR containing all steps 8a-8e. The interaction term feature set is
self-contained (training script + bidder inference + tests + report).

## Estimated Effort

1 PR: ~5 files changed, moderate complexity (bidder validation update is the
main risk area).

## Outcome

**Result: No effect. Q5 answered — OLS linearity is NOT the problem.**

- R² delta < 0.001 for all contracts (interaction terms near-collinear with existing features)
- H2H: interaction vs AV v1 = +0.002 pts/deal (noise)
- H2H: interaction vs R0 = +0.165 (identical to AV v1 vs R0 = +0.165)
- The suit regression (-0.142 net_eppd) is structural — bimodal target, not missing features
- Steps 8c-8e completed. Step 9 (FULL evaluation) not needed — no improvement to scale up.
- PR: #TBD
