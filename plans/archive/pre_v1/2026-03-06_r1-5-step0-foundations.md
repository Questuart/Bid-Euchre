# R1.5 Step 0 — Foundations PR Session Plan

**Date:** 2026-03-06
**Task:** #1 — PR-1: R1.5 Step 0 foundations
**Governs:** `enumerate_legal_actions`, `ActionValueBidder` skeleton, artifact contract, unit tests
**Design spec:** `plans/r1_5_training_plan.md` (Section 4 + Step 0)

---

## Scope

One PR. Infrastructure only — no training pipeline, no dataset generator.

### Deliverables

| # | File | Change |
|---|------|--------|
| 1 | `src/bid_euchre/strategy/bidding.py` | Add `enumerate_legal_actions(obs)`, `ActionValueBidder`, `predict_ols()`, `extract_state_features()`, `extract_action_features()` |
| 2 | `src/bid_euchre/strategy/__init__.py` | Export `ActionValueBidder`, `enumerate_legal_actions` |
| 3 | `src/bid_euchre/experiments/config.py` | Register `ActionValueBidder` in `BIDDING_POLICY_REGISTRY` + `BIDDING_REQUIRED_PARAMS` |
| 4 | `experiments/configs/r1_5_action_value_full.yaml` | YAML config for full arm |
| 5 | `experiments/configs/r1_5_action_value_constrained.yaml` | YAML config for constrained arm |
| 6 | `tests/unit/test_action_value_bidder.py` | Unit tests for all new functions |

### Not in scope

- Training pipeline (`train_action_value.py`)
- Dataset generator (`generate_action_value_dataset.py`)
- Gate definitions in `arc_d_gate.py` / `arc_d_bundle.py` (deferred to training PR)
- Modifications to any frozen files (hand_eval.py, auction_context.py, scoring.py, core/, sim/)

---

## Implementation Details

### 1. `enumerate_legal_actions(obs: BiddingObservation) -> List[BidAction]`

**Location:** `bidding.py`, module-level function near BidAction class.

**Algorithm:**
```python
def enumerate_legal_actions(obs: BiddingObservation) -> list[BidAction]:
    actions = [BidAction.pass_bid()]
    for n in range(obs.current_high_bid + 1, 11):
        for contract in obs.allowed_contracts:  # ("C","D","H","S","HIGH","LOW")
            actions.append(BidAction.bid(n, contract))
    return actions
```

**Canonical order:** PASS first, then ascending by `(n, contract)` where contract order follows `allowed_contracts` tuple (default: C, D, H, S, HIGH, LOW).

**Edge cases:**
- `current_high_bid == 0`: 1 + 60 = 61 actions
- `current_high_bid == 10`: 1 action (PASS only)
- `current_high_bid == 9`: 1 + 6 = 7 actions
- Custom `allowed_contracts` (subset): fewer actions per level

### 2. `predict_ols(model_dict, features) -> float`

**Location:** `bidding.py`, module-level function near ActionValueBidder.

```python
def predict_ols(model_dict: dict, features: np.ndarray) -> float:
    return float(np.dot(model_dict["coefficients"], features) + model_dict.get("intercept", 0.0))
```

**Note:** R1.5 artifact schema uses `"coefficients"` + `"intercept"` (not `"weights"` + `"bias"` from hybrid_olsa_v1). This is a deliberate schema break — new artifact type.

### 3. `extract_state_features(obs, contract_family, trump_suit) -> np.ndarray`

52 columns per the design spec (D1):
- 39 hand features from `get_hand_features(obs.hand, contract_type, trump_suit)`
- 3 partner features from `extract_partner_features(obs.seat, obs.auction_transcript, contract_family)`
- 1 `current_high_bid` (integer)
- 2 contract indicators: `is_high`, `is_low`
- 4 trump dummies: `trump_C`, `trump_D`, `trump_H`, `trump_S`
- 3 seat dummies: `seat_relative_to_dealer` (one-hot, 3 levels, dealer=reference)

**Key design decision:** State features depend on the candidate contract (hand features change by contract_type/trump). So `extract_state_features` takes `contract_family` and `trump_suit` as parameters — it's called once per candidate action, not once per observation.

**Seat encoding:**
```python
relative_seat = (obs.seat - obs.dealer_seat) % 4  # 0=dealer, 1=left, 2=partner, 3=right
# One-hot with dealer (0) as reference level → 3 dummies for seats 1, 2, 3
```

### 4. `extract_action_features(bid_n) -> np.ndarray`

2 columns: `[bid_n, bid_n_sq]` where `bid_n_sq = bid_n ** 2`.

### 5. `ActionValueBidder` class

```python
class ActionValueBidder(BiddingPolicy):
    def __init__(self, artifact_path: str, name: str = "action_value"):
        super().__init__(name=name)
        with open(artifact_path) as f:
            artifact = json.load(f)
        if artifact.get("schema_version") != "action_value_olsa_v1":
            raise ValueError(
                f"Expected action_value_olsa_v1, got {artifact.get('schema_version')}"
            )
        models = artifact["models"]
        self.models = {
            "suit": models["suit"],
            "high": models["high"],
            "low": models["low"],
        }
        self.pass_model = models["pass"]
        self.context_features = artifact.get("metadata", {}).get("context_features", [])

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        legal = enumerate_legal_actions(obs)
        best_value = float("-inf")
        best_action = BidAction.pass_bid()

        for action in legal:
            if action.is_pass():
                # Pass model uses state features for a neutral context
                # Use "high" contract (no trump) as reference for hand features
                state = extract_state_features(obs, "high", None)
                value = predict_ols(self.pass_model, state)
            else:
                contract_type, trump_suit = action.to_contract_tuple()
                family = contract_type  # "suit", "high", or "low"
                state = extract_state_features(obs, family, trump_suit)
                action_feats = extract_action_features(action.n)
                features = np.concatenate([state, action_feats])
                value = predict_ols(self.models[family], features)

            if value > best_value:
                best_value = value
                best_action = action

        return best_action
```

**Pass state features question:** The pass model needs state features but pass has no contract. Use `"high"` as reference (no trump dependency) with `is_high=0, is_low=0, all trump dummies=0` → the "none" state encoding from D1.

Wait — re-reading D1 more carefully: the "none" state has `is_high=0, is_low=0, all trump dummies=0`. This means pass features should NOT use any specific contract's hand features. But `get_hand_features()` requires a `contract_type`. Resolution: call with `contract_type="high"` (no trump effects) and set `is_high=0` manually to produce the "none" encoding. The hand features for "high" vs "low" differ only in which features are populated — for pass, the absolute values matter less than consistency. **This matches the design spec's "none" state definition.**

### 6. Registry entry

In `config.py`:
```python
BIDDING_POLICY_REGISTRY["ActionValueBidder"] = ActionValueBidder
BIDDING_REQUIRED_PARAMS["ActionValueBidder"] = ["artifact_path"]
```

### 7. Artifact schema contract

The `action_value_olsa_v1` schema is documented in the design spec (Section 5, Step 2). For Step 0, we only need to define what ActionValueBidder expects to load — the training pipeline will produce it. Key fields:

```json
{
  "schema_version": "action_value_olsa_v1",
  "models": {
    "suit": { "coefficients": [...], "intercept": 0.0, "feature_names": [...], "r_squared": ... },
    "high": { ... },
    "low": { ... },
    "pass": { ... }
  },
  "metadata": {
    "context_features": [...],
    "arm": "full|constrained"
  }
}
```

### 8. YAML configs

Placeholder configs referencing `ActionValueBidder` with `artifact_path` pointing to expected training output locations. These can't run until training artifacts exist, but they lock the config contract.

---

## Unit Tests

| Test | What it validates |
|------|-------------------|
| `test_enumerate_legal_actions_opening` | 61 actions at current_high_bid=0 |
| `test_enumerate_legal_actions_after_bid_5` | 31 actions at current_high_bid=5 |
| `test_enumerate_legal_actions_after_bid_10` | 1 action (PASS only) at current_high_bid=10 |
| `test_enumerate_legal_actions_order` | PASS first, then ascending (n, contract) |
| `test_enumerate_legal_actions_custom_contracts` | Subset of allowed_contracts |
| `test_predict_ols_basic` | Dot product + intercept matches expected |
| `test_extract_state_features_shape` | Returns 52-element array |
| `test_extract_state_features_encoding` | Seat dummies, contract indicators, trump dummies correct |
| `test_extract_action_features` | Returns [bid_n, bid_n_sq] |
| `test_action_value_bidder_loads_artifact` | Loads mock artifact, doesn't crash |
| `test_action_value_bidder_chooses_bid` | Returns valid BidAction from mock artifact |
| `test_action_value_bidder_pass_when_best` | Returns pass when pass model predicts highest |

---

## Implementation Order

1. `enumerate_legal_actions()` + its tests (standalone, no dependencies)
2. `predict_ols()` + test
3. `extract_state_features()` + `extract_action_features()` + tests
4. `ActionValueBidder` class + tests (depends on 1-3)
5. Registry entry in `config.py`
6. YAML configs
7. `make check`

---

## Outcome

COMPLETE. PR #560 merged 2026-03-07.

- `enumerate_legal_actions()`, `ActionValueBidder`, `extract_state_features()` (52-col),
  `predict_ols()`, feature_names validation, pass proxy encoding
- Registered in `config.py` as `ActionValueBidder`
- 119 tests passing
