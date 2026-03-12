# R1.5 Step 2 — Training Pipeline Session Plan

**Date:** 2026-03-06
**Task:** #4 — PR-3: R1.5 Step 2 training pipeline
**Governs:** `scripts/internal/train_action_value.py` + unit tests
**Design spec:** `plans/r1_5_training_plan.md` (Section 5, Step 2)

---

## Scope

One PR. Training script + unit tests for Gate X2 validation.

### Deliverables

| # | File | Change |
|---|------|--------|
| 1 | `scripts/internal/train_action_value.py` | New: action-value OLS training pipeline |
| 2 | `tests/unit/test_train_action_value.py` | New: unit tests for training pipeline |

### Not in scope

- Offline evaluation (Step 3, separate task)
- Modifications to any frozen files
- Changes to ActionValueBidder (done in Step 0)
- Dataset generator changes (done in Step 1)

---

## Architecture

### Why a new training script?

The existing `train_hybrid_olsa.py` trains on `tricks_won` from bidless run data via `join_features_outcomes()`. The action-value pipeline trains on `net_points` from counterfactual parquet datasets with a fundamentally different schema (rows = (state, action) pairs, not (hand, contract) outcomes). Reuse of `_fit_ols()` and `_compute_metrics()` from `train_olsa.py` is appropriate; the orchestration is different.

### Data flow

```
Input: data/runs/<run_id>/datasets/action_value.parquet
  ↓
Split by deal_id (GroupKFold, 80/10/10 three-way)
  ↓
For each contract family (suit, high, low):
  filter rows where contract_family == family
  X = state_features (52 cols) + action_features (bid_n, bid_n_sq)
  y = net_points
  Fit OLS: _fit_ols(X, y) → (weights, bias)
  Compute R² on test set
  ↓
For pass:
  filter rows where action_type == "pass"
  X = state_features (52 cols)
  y = net_points
  Fit OLS: _fit_ols(X, y) → (weights, bias)
  Compute R² on test set
  ↓
Output: action_value_olsa_v1 JSON artifact
```

### Key design decisions

1. **Split by deal_id not hand_id:** The counterfactual dataset has `deal_id` as the natural grouping unit (each deal produces 4×~40 rows). Split manifest uses `deal_id` column instead of `hand_id`.

2. **Full arm only (v1):** Per the design spec, v1 uses all 52 state features + 2 action features. The constrained arm is deferred — adding it later requires only feature subsetting.

3. **Three-way split:** train/val/test (80/10/10). Validation set used for Gate X2 R² reporting. Test set reserved for offline eval (Step 3).

4. **Reuse `_fit_ols()`:** Same normal-equation OLS from `train_olsa.py`. No ridge in v1.

5. **Artifact schema:** `action_value_olsa_v1` with `coefficients` (not `weights`), `feature_names`, `r_squared`. This matches `ActionValueBidder.__init__()` expectations at `bidding.py:1508-1548`.

6. **Feature names in artifact:** Required by `ActionValueBidder` for runtime validation. Bid models get `STATE_FEATURE_NAMES + ACTION_FEATURE_NAMES` (54 names). Pass model gets `STATE_FEATURE_NAMES` (52 names).

### Functions

```python
def load_dataset(parquet_path: str) -> pd.DataFrame:
    """Load and validate the action-value parquet."""

def split_by_deal(
    df: pd.DataFrame, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Three-way split by deal_id. Returns (train, val, test)."""

def train_family_model(
    train_df: pd.DataFrame, val_df: pd.DataFrame,
    family: str, feature_names: list[str]
) -> dict:
    """Train OLS for one contract family. Returns model dict."""

def train_pass_model(
    train_df: pd.DataFrame, val_df: pd.DataFrame,
    feature_names: list[str]
) -> dict:
    """Train OLS for pass action. Returns model dict."""

def build_artifact(
    models: dict, metadata: dict
) -> dict:
    """Assemble the action_value_olsa_v1 artifact."""

def validate_gate_x2(artifact: dict, min_r2: dict) -> None:
    """Gate X2: check R² thresholds per model."""

def main():
    """CLI entry point."""
```

### CLI interface

```bash
uv run python scripts/internal/train_action_value.py \
    --seed 42 \
    --dataset data/runs/action_value_smoke_42/datasets/action_value.parquet \
    --output-dir data/runs/action_value_smoke_42 \
    --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
```

### Artifact output schema

```json
{
  "schema_version": "action_value_olsa_v1",
  "target": "net_points",
  "risk_mode": "neutral",
  "continuation_policy": "hybrid_r0_full",
  "action_features": ["bid_n", "bid_n_sq"],
  "models": {
    "suit": {
      "coefficients": [...],
      "feature_names": [...],
      "r_squared": 0.XX,
      "n_train": NNN,
      "n_val": NNN
    },
    "high": { ... },
    "low": { ... },
    "pass": {
      "coefficients": [...],
      "feature_names": [...],
      "r_squared": 0.XX,
      "n_train": NNN,
      "n_val": NNN
    }
  },
  "metadata": {
    "n_deals": 500,
    "training_seed": 42,
    "arm": "full",
    "context_features": [],
    "git_sha": "...",
    "created_at_utc": "..."
  }
}
```

---

## Gate X2 Validation

| Model | Metric | Threshold | Action if FAIL |
|-------|--------|-----------|----------------|
| Suit | R² | > 0.05 | Investigate; try interaction terms |
| High | R² | > 0.05 | Same |
| Low | R² | > 0.05 | Same |
| Pass | R² | > 0.02 | Acceptable noisiness |

---

## Unit Tests

| Test | What it validates |
|------|-------------------|
| `test_load_dataset` | Loads parquet, validates required columns |
| `test_split_by_deal_sizes` | 80/10/10 proportions, no deal leakage |
| `test_split_by_deal_determinism` | Same seed → same split |
| `test_train_family_model_shape` | Coefficients length = 54 (52 state + 2 action) |
| `test_train_pass_model_shape` | Coefficients length = 52 (state only) |
| `test_train_family_model_r2` | R² is a float in [0, 1] |
| `test_build_artifact_schema` | Has all required keys for action_value_olsa_v1 |
| `test_build_artifact_feature_names` | Bid models have 54 names, pass has 52 |
| `test_gate_x2_passes` | Valid artifact passes gate |
| `test_gate_x2_fails_low_r2` | Low R² triggers assertion |
| `test_artifact_loadable_by_bidder` | ActionValueBidder can load the produced artifact |
| `test_end_to_end_smoke` | Full pipeline on SMOKE dataset → valid artifact |

---

## Implementation Order

1. `load_dataset()` + `split_by_deal()`
2. `train_family_model()` + `train_pass_model()` (using `_fit_ols`)
3. `build_artifact()` + `validate_gate_x2()`
4. CLI wrapper (`main()`)
5. Unit tests
6. `make check`

---

## Outcome

COMPLETE. PR #567 merged 2026-03-07.

- Training pipeline (`scripts/internal/train_action_value.py`)
- 29 unit tests, Gate X2 validation built in
- Feature sets: full (52), r0 (39), no-partner, interaction
