# R1.5 Training Plan — Objective Alignment (Action-Value on Net Points)

**Date:** 2026-03-06
**Status:** DRAFT
**Prerequisites:** R1 concluded, baseline statement frozen at commit `73b3ef0`
**Governs:** R1.5 execution — action-value bidding on `net_points`

> **Document role:** This is the **R1.5 design specification** — state definition,
> counterfactual label generation, training pipeline, evaluation gates, and promotion
> contract. For the R1 closeout and root-cause analysis, see
> `docs/04_reports/r1/r1_baseline_statement.md`. For the R0-R5 ladder roadmap,
> see `plans/arc_d_execution_plan.md`.

---

## 1. Context and Motivation

### 1.1 R1 Concluded

R1 added auction-context data and coarse partner features (`partner_bid_level`,
`partner_passed`, `partner_suit_match`) to the R0 trick-target prediction
architecture. The training objective remained `tricks_won` with hand-coded utility
conversion to bidding decisions.

**Training layer improved:**
- Suit R^2 improved from ~0.25 (R0) to ~0.63 (R1) — Gate X2 passed (+0.40)
- Partner features dominated fit: `partner_bid_level` alone added +0.329 R^2

**Gameplay layer regressed:**
- Primary H2H delta: **-0.348 net_eppd** (R1 worse than R0)
- Suit regression: **-0.76 net_eppd** [CI: -0.99, -0.53] — significant
- High/low: CIs span zero (no significant change)
- Gate X3: **STOP** — R1 not promotable

### 1.2 Root Cause: Objective Mismatch

H10 confirmed analytically (PR #552): `_compute_ev_static()` EV is monotonically
non-increasing in `bid_n` for sigma > 0; `compute_best_bid(bid_level_search=True)`
always picks `min_legal`. The `bid_bonus=0.25` diagnostic probe reversed the
overall delta to +0.407 but the suit-specific deficit persisted (-0.456) — the
decision layer is a major bottleneck, not the sole cause.

The fundamental mismatch:
- **Train** on `tricks_won` (per-contract OLS)
- **Decide** with hand-coded Gaussian utility (sigma, risk_lambda, _compute_ev_static)
- **Evaluate** on `points_per_deal` (net_eppd)

R^2 improvement does not imply gameplay improvement because the hand-coded utility
layer severs the gradient from evaluation metric to training objective.

### 1.3 R1.5 Goal

Train directly on `net_points`, eliminating the hand-coded utility layer entirely.
The bidder selects actions by comparing predicted `E[net_points | state, action]`
across all legal actions. No `_compute_ev_static`, no Gaussian model, no sigma.

**Reference:** `docs/04_reports/r1/r1_baseline_statement.md` (commit `73b3ef0`)

---

## 2. Four Critical Design Questions (D1–D4)

### D1: Exact State Definition

**52 OLS columns** per observation:

| Group | Count | Features |
|-------|-------|----------|
| Hand features | 39 | From `hand_eval.py` (v7 schema) |
| Partner features | 3 | `partner_bid_level`, `partner_passed`, `partner_suit_match` |
| Current high bid | 1 | `current_high_bid` (integer, 0 = no bids yet) |
| Contract indicators | 2 | `is_high`, `is_low` (binary) |
| Trump dummies | 4 | `trump_C`, `trump_D`, `trump_H`, `trump_S` (one-hot) |
| Seat dummies | 3 | `seat_relative_to_dealer` (one-hot with 3 levels) |
| **Total** | **52** | |

**Encoding rules:**

- **No explicit "suit" dummy** — suit contract is the implicit reference level
  (`is_high=0`, `is_low=0`, at least one trump dummy = 1).
- **"none" state** (no bids yet): `is_high=0`, `is_low=0`, all trump dummies = 0.
- **Non-redundant:** A suit contract has exactly one trump dummy = 1. High/low/none
  contracts have all trump dummies = 0.

**Per-contract models** receive +2 action features:

| Feature | Description |
|---------|-------------|
| `bid_n` | The candidate bid level (integer) |
| `bid_n_sq` | `bid_n^2` (quadratic term for make/set kink) |

This gives **54 total columns per contract model** (suit, high, low).

**Constrained arm:** Locked base features (3/2/2 from R1) + 3 partner features +
10 legality/position features + `bid_n` + `bid_n_sq`.

**Full arm:** Forward-selected from all 52 state features + `bid_n` + `bid_n_sq`.

#### Scope Boundary

R1.5 uses ONLY minimal legality/position metadata (current_high_bid, seat dummies).
Richer auction transcript features are **OUT OF SCOPE**. They are not part of R1.6
(partner-semantics only) or R2 (opponent context only). Transcript enrichment would
need a ladder amendment.

### D1b: Legal Action Enumeration

Legal actions given `current_high_bid`:

```
legal_actions(current_high_bid) = {PASS} ∪ {(n, contract) : n > current_high_bid,
                                    n ∈ [1..10],
                                    contract ∈ {C, D, H, S, HIGH, LOW}}
```

**Key rules (from RULES.md SS3.3):**
- No contract precedence — strictly-increasing `tricks_bid` only
- Contract type is free choice at any legal bid level
- Ties are impossible (strictly increasing)

**Action counts:**
- `PASS` + `(10 - current_high_bid) * 6` non-pass actions
- At auction start (`current_high_bid=0`): 1 + 60 = **61 actions**
- After a bid of 5: 1 + 30 = **31 actions**
- After a bid of 10: 1 + 0 = **1 action** (PASS only)

**Canonical enumerator:** `enumerate_legal_actions(obs)` in
`src/bid_euchre/strategy/bidding.py`.
- Returns `List[BidAction]`
- Deterministic order: PASS first, then ascending by `(n, contract_code)`
- Used by BOTH the dataset generator and `ActionValueBidder.choose_bid()`
- New function to be implemented in Step 0

### D2: Counterfactual Label Generation

For each `(deal, focal_seat, legal_action)`:

1. Force `focal_seat` to take `legal_action`
2. Continue auction for remaining seats using **continuation policy**
3. Play out 10 tricks with `GluttonStrategy`
4. Record focal team's `net_points`

**Pass is NOT special** — it is just one of the legal actions. It gets its own
counterfactual label like any bid.

**Continuation policy v1:** R0 best incumbent (`hybrid_olsa_full_r0`).

#### Off-Policy Sensitivity Check

Compare mean action values across 3 continuation policies:

1. R0 best incumbent (v1 default)
2. R0 constrained (`hybrid_olsa_r0`)
3. Uniform-random bidder

**Materiality threshold:** If the mean difference in action values exceeds
**0.5 net_points** for any contract family between policies (1) and (2), the
off-policy bias is material and must be addressed before promotion.

### D2b: Pass Model Contract

Pass = single state-only OLS regressor (no `bid_n`).

| Property | Value |
|----------|-------|
| Input | 52 state columns only |
| Target | `net_points` when focal seat passes |
| Training data | All pass-action rows (one per deal x focal_seat) |
| Model class | OLS |

**Artifact structure:** `action_value_olsa_v1` has **FOUR** models:
`suit`, `high`, `low`, `pass`.

**Gate X2 for pass:** R^2 > 0.02 (lower than per-contract 0.05 threshold because
pass outcomes are noisier — they depend entirely on other players' bidding and play
decisions).

### D3: Cross-Contract Calibration

Per-contract models predict `E[net_points]`. Since the target scale is identical
across all models (`net_points` in the same units), predictions should be directly
comparable without explicit calibration.

**Gate X3-cal (state-matched calibration diagnostic):**

1. Mean absolute prediction gap <= 2.0 net_points vs empirical gap on matched
   states -> else FAIL
2. Top-1 agreement >= 60% on matched states (states where multiple contract
   families are legal) -> else FAIL

**Fallback cascade if X3-cal fails:**
- **Option B:** Explicit calibration layer (Platt scaling or isotonic regression
  on a held-out calibration set)
- **Option C:** Unified model (single OLS across all contracts with contract
  dummies, sacrificing per-contract specialization)

### D4: Risk Treatment

**R1.5 v1 is RISK-NEUTRAL** (`E[net_points]` maximization). This is a deliberate
simplification:

- R1 `risk_lambda` was already 0.0 (Track D: RETAIN decision)
- v1 can **ADVANCE** but **NOT PROMOTE** — risk treatment is required for promotion
- Step 7 adds risk treatment (threshold, CVaR penalty, or risk model)
- Step 8 promotion gate (`CI_low > 0.180` vs R0) applies to risk-treated v2 only

---

## 3. Open Questions — Baseline Positions

These questions were identified during design. Each has an explicit baseline
position; deviations require HITL approval.

| # | Question | Baseline Position | Rationale |
|---|----------|-------------------|-----------|
| Q1 | State representation | 52 OLS columns (see D1) | Extends R1 state with legality/position metadata |
| Q2 | Training data shape | Full counterfactual — one row per `(state, legal_action)`. ~6M rows FULL, ~250k QUICK. Deal-level splits required. | Need action-value estimates for all legal actions, not just chosen action |
| Q3 | Label generation | All action labels empirical via continuation rollout (see D2). Off-policy sensitivity check required. | Ground-truth counterfactuals avoid model-on-model bias |
| Q4 | Model architecture | Per-contract (3 models + pass) with calibration diagnostic (see D3) | Matches R0/R1 per-contract pattern; calibration gate catches drift |
| Q5 | Artifact schema | New `action_value_olsa_v1` extending `hybrid_olsa_v1` with `target: "net_points"`, `action_features`, `continuation_policy`, `risk_mode: "neutral"`, four model specs | Clean separation from trick-target artifacts |
| Q6 | Model complexity | OLS + quadratic `bid_n` is FIRST BASELINE, not recommended architecture. Must define "good enough" (R^2 threshold, residual diagnostics) and fallback (piecewise linear, interaction terms). | Start simple, gate on adequacy |
| Q7 | Evaluation pipeline | Three-layer: offline R^2 -> ranking top-1/regret -> gameplay H2H. Promotion = risk-treated v2 only. | Progressive confidence: cheap offline checks gate expensive gameplay runs |

---

## 4. New BiddingPolicy — ActionValueBidder

### 4.1 Location

`src/bid_euchre/strategy/bidding.py`

### 4.2 Class Design

```python
class ActionValueBidder(BiddingPolicy):
    """
    Action-value bidder: selects the legal action with highest
    predicted E[net_points].

    Uses per-contract OLS models (suit, high, low) plus a separate
    pass model. No hand-coded utility, no Gaussian EV, no sigma.
    """

    def __init__(self, artifact_path: str):
        artifact = load_artifact(artifact_path)
        self.models = {
            "suit": artifact["suit_model"],
            "high": artifact["high_model"],
            "low": artifact["low_model"],
        }
        self.pass_model = artifact["pass_model"]
        self.feature_names = artifact["feature_names"]
        self.context_features = artifact.get("context_features", [])

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        legal = enumerate_legal_actions(obs)
        state_features = extract_state_features(obs)  # 52 columns

        best_value = float("-inf")
        best_action = BidAction.pass_bid()

        for action in legal:
            if action.is_pass():
                value = self.pass_model.predict(state_features)
            else:
                contract_type, trump = action.to_contract_tuple()
                family = contract_type  # "suit", "high", or "low"
                features = extract_action_features(
                    obs, family, action.n
                )  # 54 columns
                value = self.models[family].predict(features)

            if value > best_value:
                best_value = value
                best_action = action

        return best_action
```

### 4.3 Key Differences from HybridOLSaBidder

| Aspect | HybridOLSaBidder (R0/R1) | ActionValueBidder (R1.5) |
|--------|--------------------------|--------------------------|
| Training target | `tricks_won` | `net_points` |
| Decision logic | `_compute_ev_static()` (Gaussian EV) | Direct `argmax(predicted_value)` |
| Action features | None (state-only prediction) | `bid_n` + `bid_n_sq` per action |
| Risk treatment | `sigma`, `risk_lambda` parameters | None in v1 (deferred to Step 7) |
| Models per artifact | 3 (suit, high, low) | 4 (suit, high, low, pass) |
| Pass handling | Implicit (pass if no bid exceeds threshold) | Explicit pass model |

### 4.4 Registration

Add to `src/bid_euchre/experiments/config.py`:

```python
BIDDING_POLICY_REGISTRY["ActionValueBidder"] = ActionValueBidder

BIDDING_REQUIRED_PARAMS["ActionValueBidder"] = ["artifact_path"]
```

---

## 5. Execution Steps (10-Step Pipeline)

### Overview

| Step | What | Gate | Blocked By |
|------|------|------|------------|
| 0 | Infrastructure: ActionValueBidder, artifact schema, configs | — | — |
| 1 | Counterfactual dataset generator (including pass values) | X1 | Step 0 |
| 2 | Training pipeline (dual-arm OLS on net_points, quadratic bid_n) | X2 | Step 1 |
| 3 | Offline + ranking eval + calibration diagnostic | X3 | Step 2 |
| 4 | Generate FULL dataset + train | — | Step 3 |
| 5 | 3-seed gameplay eval | No catastrophic behavior | Step 4 |
| 6 | H2H battery (QUICK) | X4 | Step 5 |
| 7 | Risk treatment design + sweep | Define risk approach based on v1 | Step 6 |
| 8 | H2H battery (FULL) + comparator | Promotion: CI_low > 0.180 | Step 7 |
| 9 | Ablation (constrained vs full, R1.5 vs R1) | — | Step 8 |
| 10 | Promotion decision + report | — | Step 9 |

### Step 0: Infrastructure

**Deliverables:**
- `ActionValueBidder` class in `bidding.py` (see Section 4)
- `enumerate_legal_actions(obs)` function in `bidding.py`
- `extract_state_features(obs)` and `extract_action_features(obs, family, bid_n)`
  helper functions
- Artifact schema `action_value_olsa_v1` (JSON spec extending `hybrid_olsa_v1`)
- YAML experiment configs for R1.5 arms
- Registry entry in `config.py`
- Unit tests for ActionValueBidder, enumerate_legal_actions, feature extraction

**Gate:** None (infrastructure only). Validated by unit tests passing.

### Step 1: Counterfactual Dataset Generator

**Script:** `scripts/internal/generate_action_value_dataset.py`

**For each (deal, focal_seat):**
1. Enumerate all legal actions at focal_seat's position in the auction
2. For each legal action:
   a. Force focal_seat to take the action
   b. Continue auction for remaining seats using continuation policy
   c. Play out 10 tricks with GluttonStrategy
   d. Record: state features (52 cols), action features (2 cols or 0 for pass),
      contract family, net_points (target)
3. Write to Parquet with columns: `hand_id`, `deal_id`, `focal_seat`, `action_type`
   (pass/bid), `contract_family`, `bid_n`, all 52 state features, `net_points`

**Data volume estimates:**
- SMOKE: ~500 deals x 4 seats x ~40 avg actions = ~80k rows
- QUICK: ~2,500 deals x 4 seats x ~40 avg actions = ~400k rows
- FULL: ~50,000 deals x 4 seats x ~40 avg actions = ~8M rows (OLS handles this)

**Deal-level splits required:** GroupKFold by `deal_id` to prevent leakage (same
deal appears in multiple rows with different focal_seats and actions).

**Gate X1 (dataset sanity):**
- Row count matches expected: `n_deals * 4 * mean_actions_per_seat` (+/- 10%)
- All contract families represented (suit, high, low, pass)
- `net_points` range is plausible (typically [-10, +10])
- Pass coverage: exactly one pass row per (deal, focal_seat) pair
- No NaN in features or target

### Step 2: Training Pipeline

**Script:** `scripts/internal/train_action_value.py`

**Dual-arm training** (matching R1 pattern):
- **Constrained arm:** Locked base features + partner + legality/position + bid_n + bid_n_sq
- **Full arm:** Forward-selected from all 52 state + bid_n + bid_n_sq

**Per-contract models (3 + pass):**
- **Suit model:** Trained on rows where `contract_family = "suit"`. Features: state (52 or constrained subset) + bid_n + bid_n_sq = 54 columns.
- **High model:** Same structure, `contract_family = "high"`.
- **Low model:** Same structure, `contract_family = "low"`.
- **Pass model:** Trained on rows where `action_type = "pass"`. Features: state only (52 or constrained subset). No action features.

**Feature selection:** Forward selection with GroupKFold (by `deal_id`), same
machinery as R1 (`src/bid_euchre/models/feature_selection.py`).

**Artifact output:** `action_value_olsa_v1` JSON with:
```json
{
  "schema_version": "action_value_olsa_v1",
  "target": "net_points",
  "risk_mode": "neutral",
  "continuation_policy": "hybrid_olsa_full_r0",
  "action_features": ["bid_n", "bid_n_sq"],
  "models": {
    "suit": { "coefficients": [...], "feature_names": [...], "r_squared": ... },
    "high": { "coefficients": [...], "feature_names": [...], "r_squared": ... },
    "low": { "coefficients": [...], "feature_names": [...], "r_squared": ... },
    "pass": { "coefficients": [...], "feature_names": [...], "r_squared": ... }
  },
  "metadata": {
    "n_deals": ...,
    "training_seed": ...,
    "arm": "full|constrained",
    "context_features": [...]
  }
}
```

**Gate X2 (training adequacy):**

| Model | Metric | Threshold | Action if FAIL |
|-------|--------|-----------|----------------|
| Suit | R^2 | > 0.05 | Non-linear model (piecewise linear, interaction terms) |
| High | R^2 | > 0.05 | Same fallback |
| Low | R^2 | > 0.05 | Same fallback |
| Pass | R^2 | > 0.02 | Acceptable noisiness; only fail if negative |

Additional diagnostics (non-gating):
- Residual plots by `bid_n` (check for make/set kink at `bid_n ~ expected_tricks`)
- Coefficient sign checks (higher hand quality -> higher EV)
- Per-seat residual balance (no seat bias)

### Step 3: Offline Evaluation + Ranking + Calibration

Three sub-gates, all must PASS:

#### Gate X3-rank: Ranking Accuracy

Compare `argmax(model prediction)` vs `argmax(oracle empirical mean)` across
all states in a held-out evaluation set.

| Scope | Metric | Threshold |
|-------|--------|-----------|
| Overall | Top-1 accuracy (model picks same action as oracle) | >= 40% |
| Per-family | Top-1 accuracy restricted to states where oracle picks that family | >= 30% per family |

**Top-1 definition:**
- For each state, the oracle's best action = the legal action with highest empirical
  mean net_points (averaged over continuation rollouts for that deal).
- The model's best action = the legal action with highest model prediction.
- Top-1 match = model and oracle agree on the same (n, contract) pair.

#### Gate X3-regret: Mean Regret

| Metric | Threshold |
|--------|-----------|
| Mean regret = `E[oracle_best_value - model_chosen_value]` | <= 1.5 net_points |

Regret is computed per-state, averaged across all states in the evaluation set.

#### Gate X3-cal: Cross-Contract Calibration

| Check | Threshold | Explanation |
|-------|-----------|-------------|
| Mean absolute prediction gap | <= 2.0 net_points | For states where multiple families are legal, compare `|model_gap - empirical_gap|` between family pairs |
| Top-1 agreement | >= 60% | On matched states, model and oracle agree on which family is best |

**Fallback cascade (if X3-cal fails):**
1. **Option B:** Explicit calibration — Platt scaling or isotonic regression per
   model on a held-out calibration split
2. **Option C:** Unified model — single OLS with contract dummies, sacrificing
   per-contract specialization

### Step 4: FULL Dataset + Train

Repeat Steps 1-2 at FULL scale (~50k deals, ~8M rows).

- Regenerate dataset with `--mode FULL`
- Retrain both arms (constrained + full) on FULL data
- Re-verify Gate X2 thresholds on FULL models

### Step 5: 3-Seed Gameplay Evaluation

Run self-play and basic H2H at 3 seeds to detect catastrophic behavior before
committing to the full battery.

**Success criteria:** No catastrophic behavior. Specifically:
- Self-play win rate within [40%, 60%] (not degenerate)
- No seed produces > 70% pass rate (not always-passing)
- No seed produces negative mean net_eppd in self-play (not systematically losing)

### Step 6: H2H Battery (QUICK)

Run the standard H2H battery at QUICK scale (~2,500 deals per matchup) across
the 6-bidder roster (3 R1.5 variants + 3 R0 baselines).

**Gate X4:**
- Primary delta (R1.5 full vs R0 full): > -0.10 net_eppd
- If delta < -0.10: STOP, diagnose before FULL battery
- If delta > 0.0: strong signal, proceed to FULL

### Step 7: Risk Treatment Design + Sweep

Based on v1 (risk-neutral) results, design and evaluate risk treatment options:

1. **Pass threshold:** Minimum EV gap required to bid (vs pass value)
2. **CVaR penalty:** Penalize high-variance bids using conditional tail risk
3. **Risk model:** Train a separate variance model for CVaR-weighted decisions

Sweep across parameter values using the v1 action-value models as base.
Select the best risk configuration for v2.

### Step 8: H2H Battery (FULL) + Comparator

Full-scale evaluation of risk-treated v2:

- H2H battery at FULL scale (~50k deals per matchup)
- Comparator battery (single-seat against GluttonStrategy)

**Promotion gate:**
- `CI_low > 0.180` (R1.5 v2 vs R0 best incumbent)
- This is the same gate threshold used for R0 promotion
- Both the point estimate and the lower bound of the 95% bootstrap CI must
  exceed the threshold

### Step 9: Ablation

Systematic ablation to quantify contribution of each R1.5 change:

1. **Constrained vs Full arm:** Attribute improvement to feature selection
2. **R1.5 vs R1:** Attribute improvement to objective change (tricks -> points)
3. **R1.5 vs R0:** Total improvement over pre-partner-context baseline

### Step 10: Promotion Decision + Report

Write the R1.5 promotion report following the standard format
(`docs/02_agent/EXPERIMENT_REPORTS.md`).

**Decision outcomes:**
- **PROMOTED:** R1.5 v2 passes all gates, becomes new incumbent
- **ADVANCED:** R1.5 v1 (risk-neutral) shows promise but v2 needs work
- **HALT:** Fundamental issues with action-value approach

---

## 6. Risk Analysis

### Risk 1: Low R^2 on net_points

**Likelihood:** Medium. `net_points` is noisier than `tricks_won` because it
includes bidding outcomes (make/set) and opponent play.

**Mitigation:** Gate X2 threshold is 0.05 (vs 0.25 for R1 tricks_won). If R^2
< 0.05, escalate to non-linear model (piecewise linear on `bid_n`, interaction
terms between hand features and `bid_n`).

### Risk 2: Off-policy bias in action labels

**Likelihood:** Medium. Continuation policy choices affect counterfactual outcomes.

**Mitigation:** Three-policy sensitivity check (D2). If mean difference > 0.5
net_points between policies (1) and (2), the bias is material and requires:
- Policy-weighted importance sampling
- Or training on multiple continuation policies and averaging

### Risk 3: Quadratic may miss make/set kink

**Likelihood:** Medium. The `net_points` function has a discontinuity at
`bid_n = tricks_won` (make vs set), which `bid_n + bid_n_sq` may not capture.

**Mitigation:** Residual diagnostics at `bid_n ~ expected_tricks`. If systematic
residual pattern detected, add piecewise linear terms or spline basis.

### Risk 4: Cross-contract calibration failure

**Likelihood:** Low. Per-contract models share the same target scale, but
different contract families may have different prediction error distributions.

**Mitigation:** Gate X3-cal catches this. Fallback cascade: Option B (explicit
calibration) -> Option C (unified model).

### Risk 5: No risk treatment in v1

**Likelihood:** Certain (by design). v1 is risk-neutral.

**Mitigation:** v1 can ADVANCE but not PROMOTE. Step 7 adds risk treatment.
This is a known limitation, not a surprise.

### Risk 6: Large dataset generation time

**Likelihood:** Medium. FULL dataset (~8M rows) requires ~50k deals x 4 seats x
~40 actions/seat = ~8M continuation rollouts.

**Mitigation:** OLS training is closed-form (no iteration), so training is fast.
Dataset generation is the bottleneck. Parallelize by deal_id if needed. QUICK
dataset (~400k rows) validates the pipeline before committing to FULL.

---

## 7. Code Changes Summary

> This section is a spec-only summary. Implementation happens in Step 0 and
> subsequent PRs.

### New Files

| File | Purpose |
|------|---------|
| `scripts/internal/generate_action_value_dataset.py` | Counterfactual dataset generator |
| `scripts/internal/train_action_value.py` | Dual-arm OLS training pipeline |
| `plans/r1_5_training_plan.md` | This document |
| `experiments/configs/r1_5_*.yaml` | Experiment configurations for R1.5 arms |

### Modified Files

| File | Change |
|------|--------|
| `src/bid_euchre/strategy/bidding.py` | Add `ActionValueBidder`, `enumerate_legal_actions()` |
| `src/bid_euchre/experiments/config.py` | Registry entry for `ActionValueBidder` |
| `src/bid_euchre/validation/arc_d_gate.py` | R1.5 gate definitions |
| `src/bid_euchre/validation/arc_d_bundle.py` | R1.5 bundle schema |

### Frozen Files (No Changes Permitted)

| File | Reason |
|------|--------|
| `src/bid_euchre/features/hand_eval.py` | Feature schema v7 is frozen |
| `src/bid_euchre/features/auction_context.py` | Partner features are frozen |
| `src/bid_euchre/scoring.py` | Scoring rules are frozen |
| `src/bid_euchre/sim/` | Simulation loop is frozen |
| `src/bid_euchre/core/` | Card primitives and rules are frozen |

---

## 8. Provenance

| Source | Reference |
|--------|-----------|
| R1 baseline statement | `docs/04_reports/r1/r1_baseline_statement.md` (commit `73b3ef0`) |
| R1 closeout reports | `docs/04_reports/r1/01_*.md`, `02_*.md`, `03_*.md` (concurrent PR) |
| R1 master plan | `plans/r1_master_plan.md` |
| H10 validation | PR #552 |
| bid_bonus sweep | PR #554 |
| Rung relabel | PR #555 |
| Game rules (bidding) | `docs/01_core/RULES.md` SS3.3 |
| Current bidding policies | `src/bid_euchre/strategy/bidding.py` |
| Strategy registry | `src/bid_euchre/experiments/config.py` |
| Feature registry | `docs/01_core/FEATURE_REGISTRY.md` (v7, 39 features) |
| Hyperparameter registry | `docs/01_core/HYPERPARAMETER_REGISTRY.md` |
