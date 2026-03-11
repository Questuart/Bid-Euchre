# R1.5.3: Alternative Model Approaches for Suit Regression

**Date:** 2026-03-11
**Arc:** D — OLSa-Hybrid Bidder
**Parent:** R1.5.2 diagnostic conclusions (PRs #595-#603)
**Decision tree:** [r1_5_forward_decision_tree.md](../r1_5_forward_decision_tree.md)
**Status:** PLANNED
**Blocking question:** Can we close the suit regression (-0.142 net_eppd) with a different model architecture?

## Background

The R1.5-v2 diagnostic campaign conclusively identified the root cause of
the suit regression: OLS predicts the mean of a bimodal make/set distribution,
producing suboptimal estimates for the argmax decision layer. Six hypotheses
were eliminated:

- Features (39->52): no effect (R^2 delta < 0.005)
- Interaction terms (3 bower products): no effect (R^2 delta < 0.001)
- Partner features: critical for action selection, not prediction accuracy
- Declare/defend regime split: gate FAILED (R^2 +0.01)
- Data source (counterfactual vs bidless): confounded with architecture
- Objective alignment: confirmed as key driver (already adopted)

The dataset confirms dramatic bimodality in declared outcomes:

| Regime | N | Mean net_pts | Std |
|--------|---|-------------|-----|
| Made (37%) | 148,209 | +2.29 | 3.64 |
| Set (63%) | 253,729 | -13.43 | 1.80 |

The two modes are ~15 points apart. Within each regime, the distribution is
unimodal and tight (set std=1.80). OLS's mean prediction falls between the
modes, producing estimates that match neither regime.

## Goal

Implement and evaluate three alternative model architectures, each addressing
the bimodal target from a different angle. All three reuse the existing
counterfactual dataset (`data/runs/action_value_quick_42_v2/datasets/action_value.parquet`,
468,388 rows) — no dataset regeneration required.

## Shared Infrastructure (Track 0)

Before implementing any track, add common infrastructure needed by all three.

### Step 0a: Derive `made_contract` target column

**File:** `scripts/internal/train_action_value.py`

Add target derivation in `load_dataset()`:

```python
# Derive binary "made" target from existing columns
# made = focal_declared AND (tricks_won >= bid_n)
if "focal_declared" in df.columns and "tricks_won" in df.columns:
    df["made_contract"] = df["focal_declared"] & (df["tricks_won"] >= df["bid_n"])
```

This enables both Track A (classification target) and Track B (conditional
regression target). No parquet regeneration — derived at load time from
existing `focal_declared`, `tricks_won`, and `bid_n` columns.

Add `"made_contract"` to `VALID_TARGETS`:

```python
VALID_TARGETS = ("net_points", "tricks_won", "made_contract")
```

### Step 0b: Add model-class extensibility to training CLI

**File:** `scripts/internal/train_action_value.py`

Add `--model-class` argument:

```python
parser.add_argument(
    "--model-class",
    choices=["ols", "logistic", "gbt"],
    default="ols",
    help="Model class: 'ols' (linear regression), 'logistic' (classification), 'gbt' (gradient boosted trees)",
)
```

This gates which `train_*` function is called without changing existing OLS
behavior.

### Step 0c: Separate bidder classes for alternative models

**File:** `src/bid_euchre/strategy/bidding.py`

The current `ActionValueBidder` hardcodes `predict_ols()` and validates
`schema_version == "action_value_olsa_v1"` with exact feature name
matching. Non-OLS artifacts (two-stage, GBT) will fail this validation
at load time (see IC-1 in Implementation Caveats).

**Resolution:** Create separate bidder classes rather than a dispatch
mechanism. Each class handles its own artifact schema:

- `TwoStageBidder(BiddingPolicy)` — loads `two_stage_v1` artifacts,
  calls `predict_two_stage()` for suit and standard OLS for high/low/pass
- `GBTBidder(BiddingPolicy)` — loads `gbt_v1` artifacts, deserializes
  pickled models, calls `predict_gbt()`
- `PolicyBidder(BiddingPolicy)` — loads `pairwise_policy_v1` artifacts,
  scores actions via dot product

`ActionValueBidder` remains unchanged (no regression risk). All new
classes must be registered in `BIDDING_POLICY_REGISTRY` and exported
from `strategy/__init__.py`.

### Step 0d: H2H evaluation config template

Create a reusable 4-bidder battery config for comparing all tracks:

- `action_value_v1` — AV OLS baseline (existing)
- `two_stage` — Track A model
- `gbt` — Track B model
- `hybrid_olsa_full_r0` — R0 baseline (existing)

16 matchups (4x4 including self-play), seed=42, n=2500 (QUICK).

**Acceptance:** Step 0 changes must pass `make check` and not break existing
OLS training or ActionValueBidder loading.

## Track A: Two-Stage Model (P(make) x E[points|regime])

### Rationale

Instead of predicting E[net_points] directly (which falls between bimodal
modes), decompose into:

```
EV(action) = P(make|state,action) x E[pts|make,state,action]
           + P(set|state,action)  x E[pts|set,state,action]
```

Each component targets a unimodal distribution. P(make) uses logistic
regression (binary classification). The conditional expectations use OLS on
regime-filtered subsets (made-only, set-only).

**Why this should work:** The Phase 2 regression approach failed because a
single OLS regressor can't learn the regime boundary. A dedicated classifier
should handle the boundary much better — the made/set split is a clean binary
target with 37%/63% class balance.

### Step A1: Train P(make) logistic classifier

**File:** `scripts/internal/train_action_value.py`

Add `train_family_classifier()` function:

```python
from sklearn.linear_model import LogisticRegression

def train_family_classifier(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    family: str,
    state_feature_names: list[str] | None = None,
) -> dict:
    """Train logistic P(make) classifier for one contract family."""
    if state_feature_names is None:
        state_feature_names = list(STATE_FEATURE_NAMES)

    feature_names = state_feature_names + list(ACTION_FEATURE_NAMES)

    # Filter to declared rows only (defenders can't make/set)
    train_fam = train_df[
        (train_df["contract_family"] == family) & train_df["focal_declared"]
    ]
    val_fam = val_df[
        (val_df["contract_family"] == family) & val_df["focal_declared"]
    ]

    X_train = _build_feature_matrix(train_fam, feature_names)
    y_train = (train_fam["tricks_won"] >= train_fam["bid_n"]).astype(float).values
    X_val = _build_feature_matrix(val_fam, feature_names)
    y_val = (val_fam["tricks_won"] >= val_fam["bid_n"]).astype(float).values

    clf = LogisticRegression(max_iter=1000, solver="lbfgs")
    clf.fit(X_train, y_train)

    return {
        "model_type": "logistic",
        "coefficients": clf.coef_[0].tolist(),
        "intercept": clf.intercept_[0],
        "feature_names": feature_names,
        "accuracy": clf.score(X_val, y_val),
        "n_train": len(train_fam),
        "n_val": len(val_fam),
        "class_balance": float(y_train.mean()),
    }
```

### Step A2: Train conditional E[pts|regime] OLS models

**File:** `scripts/internal/train_action_value.py`

Add `train_two_stage_model()` that trains 3 sub-models per family:

```python
def train_two_stage_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    family: str,
    state_feature_names: list[str] | None = None,
) -> dict:
    """Train two-stage model: P(make) + E[pts|make] + E[pts|set]."""
    classifier = train_family_classifier(
        train_df, val_df, family, state_feature_names
    )

    # Conditional OLS: filter to made-only and set-only subsets
    declared_train = train_df[
        (train_df["contract_family"] == family) & train_df["focal_declared"]
    ]
    made_mask = declared_train["tricks_won"] >= declared_train["bid_n"]

    made_train = declared_train[made_mask]
    set_train = declared_train[~made_mask]

    # ... similar for val_df ...
    # Train OLS on each subset using train_family_model() internals

    return {
        "model_type": "two_stage",
        "classifier": classifier,
        "made_model": made_ols,   # OLS on made-only subset
        "set_model": set_ols,     # OLS on set-only subset
        "feature_names": feature_names,
    }
```

### Step A3: Add `predict_two_stage()` to bidder

**File:** `src/bid_euchre/strategy/bidding.py`

```python
def predict_two_stage(model_dict: dict, features: np.ndarray) -> float:
    """Two-stage prediction: P(make) * E[pts|make] + P(set) * E[pts|set]."""
    classifier = model_dict["classifier"]
    # Logistic probability
    logit = np.dot(classifier["coefficients"], features) + classifier["intercept"]
    p_make = 1.0 / (1.0 + np.exp(-logit))

    ev_made = predict_ols(model_dict["made_model"], features)
    ev_set = predict_ols(model_dict["set_model"], features)

    return p_make * ev_made + (1 - p_make) * ev_set
```

### Step A4: Implement `TwoStageBidder`

Create `TwoStageBidder(BiddingPolicy)` in `bidding.py` per Step 0c
resolution. The bidder's `choose_bid()` follows the same enumerate-actions
+ argmax pattern as `ActionValueBidder`, but calls `predict_two_stage()`
for the family's model. Loads `two_stage_v1` schema artifacts with
nested `classifier`, `made_model`, `set_model` dicts per contract family.

### Step A5: Train + evaluate

```bash
# Train two-stage model
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class two-stage --feature-set full --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_two_stage_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
```

**Metrics to report:**
- P(make) accuracy and AUC per contract family
- Conditional R^2 (E[pts|made] and E[pts|set]) — expect high (unimodal targets)
- H2H vs AV v1 and R0 (primary: suit net_eppd delta)

**Success criterion:** Suit net_eppd regression improves by > 0.05
(from -0.142 to > -0.092).

## Track B: Gradient Boosted Trees (GBT)

### Rationale

GBT naturally handles:
- Non-linear feature interactions (no manual interaction terms needed)
- Bimodal target distributions (tree splits can separate regimes)
- Feature importance (built-in, no need for forward selection)

This is the "does a better model class fix it?" experiment. If GBT
substantially improves suit prediction, the problem is OLS linearity. If not,
the problem is deeper (decision layer, data quality, or fundamental
unpredictability).

### Step B1: Train GBT regressor

**File:** `scripts/internal/train_action_value.py`

```python
from sklearn.ensemble import GradientBoostingRegressor

def train_family_gbt(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    family: str,
    state_feature_names: list[str] | None = None,
    target_col: str = "net_points",
    seed: int = 42,
) -> dict:
    """Train GBT regressor for one contract family."""
    if state_feature_names is None:
        state_feature_names = list(STATE_FEATURE_NAMES)

    feature_names = state_feature_names + list(ACTION_FEATURE_NAMES)

    train_fam = train_df[train_df["contract_family"] == family]
    val_fam = val_df[val_df["contract_family"] == family]

    X_train = _build_feature_matrix(train_fam, feature_names)
    y_train = train_fam[target_col].values
    X_val = _build_feature_matrix(val_fam, feature_names)
    y_val = val_fam[target_col].values

    gbt = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=seed,
    )
    gbt.fit(X_train, y_train)

    y_pred = gbt.predict(X_val)
    ss_res = np.sum((y_val - y_pred) ** 2)
    ss_tot = np.sum((y_val - y_val.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot

    return {
        "model_type": "gbt",
        "feature_names": feature_names,
        "r_squared": r_squared,
        "n_train": len(train_fam),
        "n_val": len(val_fam),
        # Serialization: pickle the model, base64-encode, store as string
        "model_bytes": _serialize_gbt(gbt),
        "feature_importances": dict(
            zip(feature_names, gbt.feature_importances_.tolist())
        ),
    }
```

**Serialization note:** scikit-learn models aren't JSON-native. Options:
1. pickle + base64 — simplest, stores in existing JSON artifact schema
2. Coefficient extraction — not feasible for tree ensembles
3. Separate file — .pkl alongside .json metadata

Recommend option 1 for consistency with existing artifact schema. The base64
payload is ~50KB for 200 trees.

### Step B2: Add `predict_gbt()` to bidder

**File:** `src/bid_euchre/strategy/bidding.py`

```python
import base64
import pickle

def predict_gbt(model_dict: dict, features: np.ndarray) -> float:
    """GBT prediction from deserialized model."""
    if "_gbt_model" not in model_dict:
        # Lazy deserialization on first call
        model_bytes = base64.b64decode(model_dict["model_bytes"])
        model_dict["_gbt_model"] = pickle.loads(model_bytes)  # noqa: S301
    return float(model_dict["_gbt_model"].predict(features.reshape(1, -1))[0])
```

### Step B3: Train GBT pass model

Same as `train_family_gbt()` but state-only features (no action features),
trained on pass rows. Mirrors `train_pass_model()` structure.

### Step B4: Train + evaluate

```bash
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class gbt --feature-set full --target net_points \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_gbt_42 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
```

**Metrics to report:**
- R^2 per contract family (expect > 0.56 for suit if non-linearity matters)
- Feature importance ranking (do bower interactions rank high?)
- H2H vs AV v1 and R0

**Success criterion:** Suit R^2 > 0.60 (meaningful improvement over OLS
0.565) AND suit net_eppd regression improves by > 0.05.

**Risk:** GBT overfitting on QUICK-scale data (468K rows, but split by
family gives ~300K suit). Mitigate with subsample=0.8, max_depth=5, and
GroupKFold by hand_id for validation.

## Track C: Direct Policy Optimization

### Rationale

Tracks A and B improve prediction to improve decisions. Track C skips
prediction entirely and optimizes the decision directly. Instead of:

```
state -> predict E[pts] -> argmax over actions
```

Track C learns:

```
state -> score(action) -> argmax over actions
```

where `score()` is trained to maximize net_points of the *chosen* action,
not to predict net_points for *all* actions.

This is a contextual bandit / policy optimization approach. The key insight:
the OLS model's suit regression may stem not from bad predictions but from
the argmax decision layer converting slightly-off predictions into
systematically wrong bids (the "prediction->decision gap" from Q6).

### Design: Pairwise Policy Learning

Use the counterfactual dataset's paired structure. For each (deal,
focal_seat), we have net_points for every legal action. Train a model that,
given state, ranks the best action highest.

**Approach:** Pairwise ranking loss. For each deal, for each pair of actions
(a_i, a_j) where net_points(a_i) > net_points(a_j), train the model to
predict score(a_i) > score(a_j).

This naturally handles bimodality: the model doesn't need to predict the
*value* of each action, only the *ranking*. If suit-4 gives +3 (made) and
suit-5 gives -5 (set), the model just needs to rank suit-4 above suit-5.

### Step C1: Implement pairwise dataset construction

**File:** `scripts/internal/train_policy_model.py` (new file)

```python
def build_pairwise_dataset(
    df: pd.DataFrame,
    state_feature_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build pairwise ranking dataset from counterfactual data.

    For each (deal_id, focal_seat), extract all action pairs where
    net_points differs, and create (features_better, features_worse) pairs.

    Returns (X_better, X_worse, margin) arrays.
    """
    pairs_better = []
    pairs_worse = []
    margins = []

    for (deal_id, seat), group in df.groupby(["deal_id", "focal_seat"]):
        actions = group.sort_values("net_points", ascending=False)
        n = len(actions)
        for i in range(n):
            for j in range(i + 1, min(i + 3, n)):  # Top-3 pairs only
                if actions.iloc[i]["net_points"] > actions.iloc[j]["net_points"]:
                    feat_i = _extract_features(actions.iloc[i], state_feature_names)
                    feat_j = _extract_features(actions.iloc[j], state_feature_names)
                    pairs_better.append(feat_i)
                    pairs_worse.append(feat_j)
                    margins.append(
                        actions.iloc[i]["net_points"] - actions.iloc[j]["net_points"]
                    )

    return np.array(pairs_better), np.array(pairs_worse), np.array(margins)
```

### Step C2: Train pairwise ranking model

**File:** `scripts/internal/train_policy_model.py`

Use a linear scoring function with pairwise hinge loss:

```python
def train_pairwise_policy(
    X_better: np.ndarray,
    X_worse: np.ndarray,
    margins: np.ndarray,
    seed: int = 42,
) -> dict:
    """Train linear scoring function via pairwise ranking loss.

    score(state, action) = w . features + b
    Loss: max(0, margin_threshold - (score(better) - score(worse)))
    """
    # Transform to difference: X_diff = X_better - X_worse
    # Binary classification: predict sign(diff) = 1
    X_diff = X_better - X_worse
    y = np.ones(len(X_diff))  # better always has label 1

    clf = LogisticRegression(max_iter=1000, solver="lbfgs", random_state=seed)
    clf.fit(X_diff, y)

    return {
        "model_type": "pairwise_policy",
        "coefficients": clf.coef_[0].tolist(),
        "intercept": clf.intercept_[0],
        "ranking_accuracy": clf.score(X_diff, y),
    }
```

**Why logistic on differences works:** If score(x) = w.x + b, then
score(better) > score(worse) iff w.(better - worse) > 0. Training a logistic
classifier on the difference vectors with label=1 learns the same weights.
This is equivalent to RankSVM with a linear kernel.

### Step C3: Add `PolicyBidder` class

**File:** `src/bid_euchre/strategy/bidding.py`

```python
class PolicyBidder(BiddingPolicy):
    """Bidder that uses a learned scoring function to rank actions."""

    def __init__(self, artifact_path: str, name: str = "policy"):
        super().__init__(name=name)
        with open(artifact_path) as f:
            artifact = json.load(f)
        self.model = artifact["model"]

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        legal_actions = enumerate_legal_actions(obs)
        best_action = BidAction.pass_bid()
        best_score = float("-inf")

        for action in legal_actions:
            if action.is_pass():
                state = extract_state_features(obs, "none", None)
                features = state  # No action features for pass
            else:
                contract_type, trump_suit = action.to_contract_tuple()
                state = extract_state_features(obs, contract_type, trump_suit)
                action_feats = extract_action_features(action.n)
                features = np.concatenate([state, action_feats])

            score = (
                np.dot(self.model["coefficients"], features)
                + self.model["intercept"]
            )
            if score > best_score:
                best_score = score
                best_action = action

        return best_action
```

### Step C4: Register PolicyBidder in config

**File:** `src/bid_euchre/experiments/config.py`

Add to `BIDDING_POLICY_REGISTRY` (line 49) and `BIDDING_REQUIRED_PARAMS`
(line 66) with `["artifact_path"]`. See IC-3 in Implementation Caveats.

**File:** `src/bid_euchre/strategy/__init__.py`

Export `PolicyBidder`.

### Step C5: Train + evaluate

```bash
uv run python scripts/internal/train_policy_model.py \
  --seed 42 --feature-set full \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_policy_42
```

**Metrics to report:**
- Pairwise ranking accuracy (expect > 60% — random is 50%)
- Top-1 accuracy: how often does the model pick the action with highest net_points?
- H2H vs AV v1 and R0

**Success criterion:** H2H suit net_eppd regression improves by > 0.05.

**Risk:** Pairwise dataset is large (O(n_deals x actions^2)). May need
sampling. Top-3 pairs per deal should keep it manageable (~30K deals x
~3 pairs = ~90K).

## Evaluation Plan

### Phase 1: Train all models (Steps A1-A5, B1-B4, C1-C5)

All three tracks train independently on the same dataset with seed=42. No
dataset regeneration needed.

### Phase 2: QUICK H2H battery

4-bidder battery (AV v1, two-stage, GBT, R0 baseline):
- 16 matchups, seed=42, n=2500
- Primary metric: suit net_eppd delta vs R0
- Secondary: pooled net_eppd delta vs R0

### Phase 3: Triage

Based on QUICK results, decide which track(s) to advance to FULL (50K deals).
Criteria:
- ADVANCE if suit net_eppd delta improves by > 0.05 vs AV v1
- HALT if no improvement
- At most 2 tracks advance to FULL (avoid resource waste)

### Phase 4: FULL evaluation (conditional)

50K deals x 16 matchups for advancing track(s). Formal promotion gate:
- CI_low for delta vs R0 must exceed delta_floor (0.180)
- Suit regression must be < -0.05 (improved from -0.142)

## Files Touched

| File | Change | Track |
|------|--------|-------|
| `scripts/internal/train_action_value.py` | `made_contract` derivation, `--model-class` arg, `train_family_classifier()`, `train_two_stage_model()`, `train_family_gbt()`, serialization | 0, A, B |
| `scripts/internal/train_policy_model.py` | **New file:** pairwise dataset construction, pairwise policy training | C |
| `src/bid_euchre/strategy/bidding.py` | `TwoStageBidder`, `GBTBidder`, `PolicyBidder` classes + `predict_two_stage()`, `predict_gbt()` helpers | A, B, C |
| `src/bid_euchre/strategy/__init__.py` | Export `TwoStageBidder`, `GBTBidder`, `PolicyBidder` | A, B, C |
| `src/bid_euchre/experiments/config.py` | Register all 3 new bidders in `BIDDING_POLICY_REGISTRY` + `BIDDING_REQUIRED_PARAMS` | A, B, C |
| `tests/unit/test_train_action_value.py` | Tests for classifier, two-stage, GBT training | A, B |
| `tests/unit/test_train_policy_model.py` | Tests for pairwise dataset, policy training | C |
| `tests/unit/test_bidding.py` | Tests for `TwoStageBidder`, `GBTBidder`, `PolicyBidder` | A, B, C |
| `docs/04_reports/r1_5/v2_conclusion.md` | Final diagnostic summary + results | All |

## PR Sequence

| PR | Content | Dependencies |
|----|---------|-------------|
| PR-1 | Track 0: shared infrastructure (Steps 0a-0d) | None |
| PR-2 | Track A: two-stage model (Steps A1-A5) | PR-1 |
| PR-3 | Track B: GBT model (Steps B1-B4) | PR-1 |
| PR-4 | Track C: policy model (Steps C1-C5) | PR-1 |
| PR-5 | Evaluation: QUICK H2H battery + triage decision | PR-2, PR-3, PR-4 |
| PR-6 | FULL evaluation (conditional on triage) | PR-5 |

PRs 2-4 are independent and can be developed in parallel after PR-1 merges.

## Implementation Caveats

Three implementation issues identified during plan review that must be
resolved in Track 0 (PR-1):

### IC-1: Schema Validation Conflict

`ActionValueBidder.__init__()` (line 1536) hardcodes
`schema_version == "action_value_olsa_v1"` and validates `feature_names`
against the exact OLS feature list. Two-stage artifacts (with nested
`classifier`, `made_model`, `set_model`) and GBT artifacts (with
`model_bytes`) will fail validation at load time before `choose_bid()`
is ever called.

**Resolution:** Create separate bidder classes per model type:
- `TwoStageBidder(BiddingPolicy)` for Track A
- `GBTBidder(BiddingPolicy)` for Track B
- `PolicyBidder(BiddingPolicy)` for Track C (already planned)

Each handles its own artifact schema validation. This follows the existing
pattern where `ActionValueBidder` and `HybridOLSaBidder` are separate
classes. The `predict_from_model()` dispatch (Step 0c) becomes unnecessary
— remove it and keep per-class prediction methods instead.

### IC-2: PolicyBidder Pass Feature Asymmetry

`PolicyBidder.choose_bid()` uses state-only features (52 dims) for pass
actions but state+action features (54 dims) for bid actions. The pairwise
scoring function `w . features` cannot compare pass vs bid on the same
scale when feature vectors have different lengths.

**Resolution:** Pad pass features with zero-valued action features
(`bid_n=0`, `bid_n_sq=0`) to produce a uniform 54-dim vector. This is
the same approach `ActionValueBidder` uses — see `extract_state_features()`
+ `extract_action_features()` in `choose_bid()`. The pairwise training
dataset (Step C1) must also use this padding.

### IC-3: Registration Mechanism

The plan incorrectly references `StrategyConfig.create_strategy`. The
actual pattern is:
- `BIDDING_POLICY_REGISTRY` dict (line 49 of `config.py`) — maps class
  name string to class
- `BIDDING_REQUIRED_PARAMS` dict (line 66) — maps class name to required
  params list
- `BiddingPolicyConfig.create_bidding_policy()` (line 105) — instantiates
  from registry

All new bidder classes (`TwoStageBidder`, `GBTBidder`, `PolicyBidder`)
must be added to both dictionaries with `["artifact_path"]` as required
params, and exported from `src/bid_euchre/strategy/__init__.py`.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| GBT overfitting on QUICK data | subsample=0.8, max_depth=5, GroupKFold by hand_id |
| GBT serialization bloat | base64 pickle ~50KB per model, 4 models = ~200KB total |
| Pairwise dataset too large | Top-3 pairs per deal, ~90K pairs total |
| All tracks fail | Confirms prediction->decision gap is fundamental; next step is hybrid routing or end-to-end RL |
| pickle security | Only load artifacts from trusted sources (same as current JSON loading) |
| Schema validation conflict | Separate bidder classes per track (IC-1) |
| Pass feature asymmetry | Zero-pad action features for pass (IC-2) |

## Outcome

_To be filled after evaluation._

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — plan document |
| Decision tree | `plans/r1_5_forward_decision_tree.md` Phase 2 |
| Governing retrospective | `docs/04_reports/r1_5/post_r1_retro.md` |
| Hypothesis tested | H12 (bimodal target), model capacity, prediction->decision gap |
| Seed | 42 |
| Scale | QUICK (2,500 deals for H2H) → FULL (50k, conditional) |
| analysis_base_sha | f74ff62 |
