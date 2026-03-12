# R1.5.3: Alternative Model Approaches for Suit Regression

**Date:** 2026-03-12 (revised)
**Arc:** D — OLSa-Hybrid Bidder
**Parent:** R1.5.2 diagnostic conclusions (PRs #595-#603)
**Decision tree:** [r1_5_forward_decision_tree.md](../r1_5_forward_decision_tree.md)
**Status:** ACTIVE (Step 0 complete, Step 0.5 next)
**Blocking question:** Can we close the suit regression (-0.142 net_eppd) with a different model architecture?

## Background

The R1.5.2 diagnostic campaign eliminated six hypotheses about the suit
regression but did not prove the mechanism. The **leading working hypothesis**
is H12: OLS predicts the mean of a bimodal make/set target distribution,
producing suboptimal suit bid decisions via the argmax decision layer.

Evidence supporting H12:
- Bimodality confirmed: suit GMM delta_BIC = 4,081
- OLS predictions cluster between the two modes (mean residual +0.087)
- Suit has the best R^2 (0.557) but the worst gameplay delta (-0.142)
- Six alternative explanations eliminated (features, linearity, interaction
  terms, regime split, data source, partner features)

Evidence H12 **does not yet provide:**
- Decision-level proof that between-mode predictions cause bad bids
- Error taxonomy: is the suit loss from over-bidding, wrong contract
  selection, wrong bid level, or a combination?
- Whether the costly errors are concentrated near the make/set boundary
  or spread across calibration failures
- Whether R0 avoids these errors or simply makes different errors that
  happen to cancel

The dataset shows dramatic bimodality in declared suit outcomes:

| Regime | N | Mean net_pts | Std |
|--------|---|-------------|-----|
| Made (37%) | 148,209 | +2.29 | 3.64 |
| Set (63%) | 253,729 | -13.43 | 1.80 |

The two modes are ~15 points apart. Within each regime, the distribution is
unimodal and tight (set std=1.80). OLS's mean prediction falls between the
modes, producing estimates that match neither regime. But whether this is the
**primary cause** of the -0.142 suit deficit, or merely a contributing factor,
has not been tested at the decision level.

## Goal

Understand the mechanism of the suit regression at the decision level, then
implement and evaluate the most appropriate model architecture to address it.
Sequence: diagnose first, treat second, one track at a time.

All analysis reuses the existing counterfactual dataset
(`data/runs/action_value_quick_42_v2/datasets/action_value.parquet`, 468,388
rows) and FULL H2H game logs (50K deals from PR #582).

## Step 0: Decision-Level Suit Diagnostic

**Goal:** Build a suit-error taxonomy that decomposes the -0.142 net_eppd
deficit into specific decision failure modes. This diagnostic determines
which treatment track to pursue and sets quantitative expectations for its
impact.

**Data sources:**
- FULL H2H game logs (50K deals, `data/runs/` from PR #582)
- Counterfactual dataset (468K rows, action-value parquet)
- Optional: small repeated-rollout subset (see below)

### Analysis 1: Error Taxonomy

Classify every suit-related hand in H2H logs where AV v1's decision differs
from R0's decision. Categorize errors by type:

| Error Type | Definition | Example |
|------------|-----------|---------|
| **Over-bid suit** | AV v1 bids suit, should have passed | OLS suit EV slightly positive, but actual outcome is set |
| **Under-bid suit** | AV v1 passes, should have bid suit | OLS suit EV slightly negative, but actually makeable |
| **Wrong contract** | AV v1 bids suit, better option was high/low | Suit EV highest by argmax, but high/low would yield more |
| **Wrong bid level** | AV v1 bids suit-4, different level better | Always-bid-4 leaves value on table (H13) |
| **Correct disagreement** | AV v1 differs from R0 and AV v1 is right | AV v1 correctly identifies better action |

For each error type, compute:
- Frequency (what fraction of suit deficit comes from this error type?)
- Cost (average net_eppd loss per error)
- Cumulative contribution to the -0.142 deficit

### Analysis 2: Disagreement State Analysis

On hands where AV v1 and R0 disagree on suit decisions:
- What does each bidder choose?
- Under the counterfactual outcomes available, which side wins?
- Are the disagreements concentrated in specific hand configurations
  (e.g., marginal bower hands, hands near the make/set boundary)?

### Analysis 3: Make/Set Boundary Behavior

For suit-declared hands in the counterfactual dataset:
- Where does the OLS prediction fall relative to the make/set boundary?
- Are costly errors concentrated near P(make) ~ 0.4-0.6 (boundary region)
  or are they spread across the full P(make) range?
- How does the OLS prediction correlate with actual P(make)?

This directly tests H12's mechanism: if errors are concentrated at the
boundary, a classifier (Track A) should help. If they're spread broadly,
the problem may be more fundamental.

### Analysis 4: Bid-Level Headroom (H13)

AV v1 bids at level 4 on ~57% of hands. Is this leaving value on the table?

- Among hands where AV v1 bids suit-4: what's the counterfactual outcome
  for suit-5, suit-6, etc.?
- How often would a higher bid increase net_points?
- What's the total headroom from bid-level optimization?

This folds H13 into the diagnostic rather than treating it as a separate
open question.

### Optional: Targeted Repeated-Rollout Subset

Single-rollout counterfactual outcomes are noisy. For the disagreement
states identified in Analysis 2, a small repeated-rollout subset (e.g.,
100-200 hands x 20 rollouts each) would give cleaner reads on whether
the apparent suit failures are real policy errors or single-rollout luck.

This is a targeted data investment, not a full dataset regeneration.
Decision on whether to pursue depends on how noisy the single-rollout
disagreement analysis looks.

### Step 0 Deliverables

1. **Committed JSON artifact:** `data/artifacts/r1_5_3/suit_error_taxonomy.json`
   with per-error-type frequencies, costs, and cumulative contributions
2. **Diagnostic report:** `docs/04_reports/r1_5/suit_decision_diagnostic.md`
3. **Gate decision:** which track to pursue based on error taxonomy results

### Step 0 Gate Criteria

| Diagnostic Finding | Implied Track |
|--------------------|--------------|
| Errors concentrated near make/set boundary (>60% of deficit) | Track A (two-stage model) — boundary classification is the right fix |
| Errors spread across calibration range, non-linear patterns | Track B (GBT) — nonlinear model may capture what OLS misses |
| Errors are mostly wrong-contract (suit vs high/low), not within-suit | Re-examine contract selection mechanism, possibly new direction |
| Errors are mostly bid-level (H13 matters significantly) | Bid-level optimization (lighter-weight fix than full model change) |
| Single-rollout noise dominates disagreement analysis | Repeated-rollout subset needed before any treatment |

### Step 0 Result (PR #610)

**Gate decision: Track B (GBT) or further investigation.**

- Boundary errors = 28.5% of deficit (< 60% Track A threshold)
- Clear-set region dominates at 43.0% of absolute residual
- Wrong contract: 26.5% (< 30% new-direction threshold)
- H13 answered: bid-level headroom irrelevant (2.3% improvable)
- Under-bid analysis: 62.7% noise-dominated (not actionable without repeated rollouts)

Track A is deprioritized — boundary is not where errors concentrate.
Track B is the primary next step, with a play-policy sanity check first.

## Step 0.5: Play-Policy Sanity Check

**Goal:** Confirm that GluttonStrategy (used to generate counterfactual
labels) is not systematically biasing suit outcomes before investing in
model architecture changes.

**Motivation:** The counterfactual dataset (`action_value.parquet`) uses
GluttonStrategy for all trick play during rollout. If Glutton introduces
systematic label bias — particularly for suit contracts — then model
improvements would be addressing a data problem with architecture changes.

**Prior probability: LOW.** GluttonStrategy is contract-agnostic (same play
logic for suit/high/low). High (+0.430) and low (+0.495) contracts show
strong improvement under the same Glutton-generated labels. If Glutton
were the primary confounder, all contract types would regress, not just suit.
The suit regression is more naturally explained by H12 (OLS on bimodal target).

**Method:** Run the existing `play_policy_gate.py`:

```bash
uv run python scripts/internal/play_policy_gate.py \
  --seeds 42,43,44 \
  --n-per 20000 \
  --seed 42
```

**Gate logic:**
- **PASS** (CI lower > 0): Glutton significantly better than Greedy.
  Labels are adequate. Proceed to Track B.
- **WARN** (CI crosses 0): Inconclusive. Note in decision tree but
  proceed to Track B — the weak prior plus high/low success argues
  against Glutton as primary confounder.
- **FAIL** (CI upper < 0): Greedy significantly better. STOP.
  Investigate label generation before model changes. Design targeted
  policy-sensitivity experiment (Phase 2 below).

**If FAIL — Phase 2 (designed only on demand):**
A controlled label audit would compare counterfactual net_points under
Glutton vs Greedy vs RandomLegal for a fixed set of deals. This requires
making play policy configurable in `generate_action_value_dataset.py`
(currently hardcoded). Scope and design to be determined if triggered.

**Deliverable:** Gate verdict logged in the decision tree. No separate
report unless FAIL.

### Step 0.5 Result

**Gate: PASS.** Glutton significantly outperforms Greedy across all 3 seeds,
both directions, and all 6 scenarios. Mean advantage: +0.20 tricks
(CI well above zero, all p < 0.0001). Suit scenarios show the **strongest**
Glutton advantage (+0.23 to +0.31 tricks), ruling out Glutton as a
suit-specific label confounder.

Play-policy confound hypothesis rejected. Proceed to Track B.

## Track A: Two-Stage Model (Deprioritized — Step 0 gate did not support)

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

**Why this is the best first treatment:** It is the most interpretable
approach and directly tests H12. If the two-stage model fixes the suit
regression, we have causal evidence that bimodal-target decomposition was
the missing piece. If it fails, we learn that the problem is not simply
between-mode averaging — which redirects the search.

**Implementation approach:** Minimal suit-only prototype. No shared
infrastructure, no new bidder base classes, no registry plumbing. The
prototype should be as narrow as possible — a modified `ActionValueBidder`
that uses `predict_two_stage()` for suit and standard `predict_ols()` for
high/low/pass.

### Step A1: Train P(make) logistic classifier (suit only)

**File:** `scripts/internal/train_action_value.py`

Add `train_family_classifier()` function. Derive `made_contract` target
at load time from existing `focal_declared`, `tricks_won`, and `bid_n`
columns — no parquet regeneration needed.

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

### Step A2: Train conditional E[pts|regime] OLS models (suit only)

**File:** `scripts/internal/train_action_value.py`

Add `train_two_stage_model()` that trains 3 sub-models for suit:

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

### Step A3: Add `predict_two_stage()` helper

**File:** `src/bid_euchre/strategy/bidding.py`

```python
def predict_two_stage(model_dict: dict, features: np.ndarray) -> float:
    """Two-stage prediction: P(make) * E[pts|make] + P(set) * E[pts|set]."""
    classifier = model_dict["classifier"]
    logit = np.dot(classifier["coefficients"], features) + classifier["intercept"]
    p_make = 1.0 / (1.0 + np.exp(-logit))

    ev_made = predict_ols(model_dict["made_model"], features)
    ev_set = predict_ols(model_dict["set_model"], features)

    return p_make * ev_made + (1 - p_make) * ev_set
```

### Step A4: Minimal prototype bidder

Modify `ActionValueBidder` (or create a minimal subclass) to use
`predict_two_stage()` for suit models and standard `predict_ols()` for
high/low/pass. No new bidder classes, no registry changes — just a
narrow prototype to test whether two-stage prediction moves the suit
delta.

The schema validation in `ActionValueBidder.__init__()` will need a
small adjustment to accept `two_stage_v1` artifacts for the suit model
while keeping `action_value_olsa_v1` validation for other models. This
is intentionally minimal — proper bidder class separation (IC-1) only
happens if the prototype succeeds.

### Step A5: Train + evaluate (suit only)

```bash
# Train two-stage model (suit family only)
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class two-stage --family suit \
  --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
  --output-dir data/runs/av_two_stage_suit_42
```

**Metrics to report:**
- P(make) accuracy and AUC for suit
- Conditional R^2 (E[pts|made] and E[pts|set]) — expect high (unimodal)
- H2H vs AV v1 and R0 (primary: suit net_eppd delta)

**Success criterion:** Suit net_eppd regression improves by > 0.05
(from -0.142 to > -0.092).

### If Track A succeeds

Extend to all contract families, create proper `TwoStageBidder` class,
register in config, run FULL evaluation. This is where the shared
infrastructure (IC-1 resolution, registry plumbing) gets built — but only
after the approach is validated.

### If Track A fails

Track A failure provides important information: the two-stage decomposition
does not fix the suit regression, meaning the problem is not simply
between-mode prediction. Move to Track B.

## Track B: Gradient Boosted Trees (Fallback)

### Rationale

GBT offers nonlinear feature boundaries that OLS cannot represent. This
is the "does a more flexible model class fix it?" experiment.

**Important caveat:** A GBT regressor still learns a conditional mean
under the same noisy single-rollout labels. It does **not** handle
bimodality natively in the way that a classifier + conditional regression
(Track A) does. A GBT may help because of nonlinear decision boundaries
between hand configurations, but it is not a clean test of the
bimodal-regime hypothesis. If Track A fails and Track B succeeds, the
diagnosis shifts from "bimodal target" to "nonlinear feature interactions."

### Step B1: Train GBT regressor (per-contract)

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
        "model_bytes": _serialize_gbt(gbt),
        "feature_importances": dict(
            zip(feature_names, gbt.feature_importances_.tolist())
        ),
    }
```

### Step B2: Minimal prototype + evaluate

Same approach as Track A: narrow prototype, no shared infra. Modify
`ActionValueBidder` to use GBT predictions for suit (or all contracts).

**Metrics:**
- R^2 per contract family (meaningful improvement over OLS 0.557 for suit?)
- Feature importance ranking (do bower interactions rank high?)
- H2H vs AV v1 and R0

**Success criterion:** Suit net_eppd regression improves by > 0.05.

**Risk:** GBT overfitting on QUICK-scale data. Mitigate with
subsample=0.8, max_depth=5, GroupKFold by hand_id.

### If Track B succeeds

Build proper `GBTBidder`, serialization infrastructure, FULL evaluation.

### If Track B fails

Track B failure, combined with Track A failure, indicates that neither
linear decomposition nor nonlinear boundaries fix the suit regression
on these features and labels. This does **not** prove a fundamental
prediction→decision gap — it rules out these specific model families on
this data/label setup. Next steps would be reassessed based on cumulative
evidence:
- Track C (policy optimization) as a qualitatively different approach
- Hybrid routing as a pragmatic promotion path
- Richer features or data (R1.5.4 partner context)

## Track C: Pairwise Policy Optimization (Deferred)

### Rationale

Track C bypasses prediction entirely and optimizes action ranking directly.
It is deferred because:

1. **Worst for understanding.** It changes the learning objective, making
   failures hard to interpret. If it works, we learn "ranking loss helps"
   but not *why* — we don't know whether the improvement came from avoiding
   bimodal prediction, from handling nonlinear feature interactions, or from
   the ranking objective itself.

2. **Amplifies label noise.** Single-rollout net_points are noisy. Pairwise
   construction amplifies this: each deal generates multiple comparison pairs,
   all derived from the same noisy rollout outcome. An action that looks
   better by +0.1 in one rollout might be worse in expectation.

3. **Later-stage option.** Policy optimization is appropriate after
   interpretable prediction-side fixes (Tracks A and B) have been exhausted.
   It has the highest ceiling but the least diagnostic value.

### Design (preserved for reference when activated)

Pairwise ranking loss on counterfactual data. For each (deal, focal_seat),
train a linear scoring function to rank the action with highest net_points
above alternatives. Equivalent to RankSVM with a linear kernel.

See IC-2 (pass feature asymmetry) for the zero-padding requirement.

### Activation Trigger

Track C is activated only after Tracks A and B have both failed or
produced inconclusive results, AND the diagnostic evidence suggests
that prediction-side improvements are insufficient.

## Hybrid Routing (Benchmark)

Use AV v1 for high/low, R0 for suit. This is a **benchmark upper bound**,
not a research success criterion.

Expected pooled delta: approximately the high/low gains (+0.43/+0.49)
with no suit penalty. This tells us how much value is available if we
could perfectly fix the suit regression without harming high/low.

Hybrid routing delivers promotion but does not advance understanding
of the suit mechanism. It remains available as a pragmatic fallback if
the research direction stalls and promotion pressure becomes urgent, but
it is explicitly marked as a fallback, not a mainline fix.

## PR Sequence

| PR | Content | Dependencies | Status |
|----|---------|-------------|--------|
| PR-1 | Step 0: Decision-level suit diagnostic | None | **DONE** (PR #610) |
| PR-2 | Step 0.5: Play-policy sanity check + plan updates | PR-1 | **DONE** (PR #TBD) |
| PR-3 | Track B: GBT prototype | PR-2 (if gate passes) | **NEXT** |
| PR-4 | Track A: two-stage prototype (fallback) | PR-3 (if Track B fails) | Deprioritized |
| PR-5 | FULL evaluation of winning track | PR-3 or PR-4 | Waiting |

**Revised from original plan:** Step 0 gate deprioritized Track A (boundary
errors = 28.5%, below 60% threshold). Track B is now the primary next step.
Step 0.5 (play-policy check) added as a lightweight pre-Track-B sanity gate.
PRs remain sequential — each depends on the previous outcome.

## Implementation Caveats

### IC-1: Schema Validation Conflict (deferred)

`ActionValueBidder.__init__()` hardcodes `schema_version ==
"action_value_olsa_v1"`. Non-OLS artifacts will fail validation.

**Resolution (when needed):** Create a separate bidder class for the
winning track. This is deferred until a track succeeds — building
`TwoStageBidder`, `GBTBidder`, and `PolicyBidder` classes upfront
is premature when we don't know which (if any) will be needed. For
prototyping, a minimal schema check adjustment or subclass is sufficient.

### IC-2: PolicyBidder Pass Feature Asymmetry (deferred with Track C)

Pass actions use 52-dim features, bid actions use 54-dim. Zero-pad pass
features with `bid_n=0, bid_n_sq=0` for uniform vectors. Only relevant
if Track C is activated.

### IC-3: Registration Mechanism (deferred)

The actual pattern uses `BIDDING_POLICY_REGISTRY` + `BIDDING_REQUIRED_PARAMS`
+ `BiddingPolicyConfig.create_bidding_policy()` in `config.py`. New bidder
classes must be added to both dictionaries. Only needed for the winning
track's production bidder class, not for prototyping.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Step 0 diagnostic is inconclusive | Use optional repeated-rollout subset for cleaner signal |
| Track A prototype too narrow to be valid | Suit is the problem contract; suit-only test directly addresses the deficit |
| GBT overfitting on QUICK data | subsample=0.8, max_depth=5, GroupKFold by hand_id |
| All tracks fail | Does NOT prove fundamental limit — rules out these model families on this data. Reassess with cumulative evidence. |
| Single-rollout noise masks real signal | Repeated-rollout subset for disagreement states |

## Outcome

_To be filled after evaluation._

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — plan document |
| Decision tree | `plans/r1_5_forward_decision_tree.md` |
| Governing retrospective | `docs/04_reports/r1_5/post_r1_retro.md` |
| Hypothesis tested | H12 (working hypothesis), H13 (bid-level headroom) |
| Seed | 42 |
| Scale | QUICK (2,500 deals for H2H) → FULL (50k, conditional) |
| analysis_base_sha | 4a2b5b5 |
