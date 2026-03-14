"""
R1.5 action-value training pipeline.

Trains per-contract models on counterfactual action-value data.
Supports three model classes:
  - OLS (default): produces action_value_olsa_v1 artifacts for ActionValueBidder
  - GBT: produces action_value_gbt_v1 artifacts for GBTActionValueBidder
  - Two-stage: produces two_stage_action_value_v1 artifacts for TwoStageActionValueBidder

Four models:
  suit:  target ~ state features + bid_n + bid_n_sq
  high:  target ~ state features + bid_n + bid_n_sq
  low:   target ~ state features + bid_n + bid_n_sq
  pass:  target ~ state features (no action features)

Ablation parameters:
  --feature-set: "full" (52 state features), "r0" (39 R0 hand features only),
                 or "constrained" (per-contract locked features)
  --selection: "none" (default) or "forward" (forward feature selection)
  --target: "net_points" (default) or "tricks_won"
  --model-class: "ols" (default), "gbt", or "two-stage"

The two-stage model decomposes suit predictions:
  - P(make) via logistic regression
  - Conditional E[pts|make] and E[pts|set] via separate OLS models
  - Composite: P(make)*E[pts|make] + (1-P(make))*E[pts|set]
  High/low/pass use standard OLS (same as ActionValueBidder).

CLI usage:
    uv run python scripts/internal/train_action_value.py \\
        --seed 42 \\
        --dataset data/runs/action_value_smoke_42/datasets/action_value.parquet \\
        --output-dir data/runs/action_value_smoke_42 \\
        --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

    # GBT model:
    uv run python scripts/internal/train_action_value.py \\
        --seed 42 --model-class gbt \\
        --dataset data/runs/action_value_smoke_42/datasets/action_value.parquet \\
        --output-dir data/runs/action_value_smoke_42 \\
        --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

    # Two-stage model:
    uv run python scripts/internal/train_action_value.py \\
        --seed 42 --model-class two-stage \\
        --dataset data/runs/action_value_smoke_42/datasets/action_value.parquet \\
        --output-dir data/runs/action_value_smoke_42 \\
        --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from bid_euchre.core.time import utc_now_iso
from bid_euchre.models.train_olsa import _compute_metrics, _fit_ols
from bid_euchre.strategy.bidding import ACTION_FEATURE_NAMES, STATE_FEATURE_NAMES

# ── Constants ────────────────────────────────────────────────

METADATA_COLS = [
    "hand_id",
    "deal_id",
    "focal_seat",
    "action_type",
    "contract_family",
    "bid_n",
    "trump_suit",
]

TARGET_COL = "net_points"

# Number of R0 hand features (first 39 entries in STATE_FEATURE_NAMES)
_N_R0_HAND_FEATURES = 39

# Partner feature columns (positions 39-41 in STATE_FEATURE_NAMES)
_PARTNER_FEATURE_NAMES = ["partner_bid_level", "partner_passed", "partner_suit_match"]

# Interaction terms computed from existing columns (not stored in dataset).
# Each maps to (col_a, col_b) — the feature value is col_a * col_b.
INTERACTION_FEATURE_NAMES: list[str] = [
    "bowers_x_trump_count",
    "trump_count_sq",
    "bowers_sq",
]

_INTERACTION_FORMULAS: dict[str, tuple[str, str]] = {
    "bowers_x_trump_count": ("bowers", "trump_count"),
    "trump_count_sq": ("trump_count", "trump_count"),
    "bowers_sq": ("bowers", "bowers"),
}

# Per-contract locked features for the constrained feature set.
# These are the minimal features relevant to each contract family,
# enabling cross-lineage comparability with OLSa R0.
CONSTRAINED_FEATURES: dict[str, list[str]] = {
    "suit": ["bowers", "trump_count", "offsuit_aces"],
    "high": ["offsuit_aces", "quick_tricks"],
    "low": ["offsuit_tens_count", "quick_tricks"],
}

# Named feature sets for ablation experiments.
# Most entries are flat lists. "constrained" is a dict[str, list[str]]
# mapping contract_family -> features.
FEATURE_SETS: dict[str, list[str] | dict[str, list[str]]] = {
    "full": list(STATE_FEATURE_NAMES),  # 52 state features
    "r0": list(STATE_FEATURE_NAMES[:_N_R0_HAND_FEATURES]),  # 39 R0 hand features only
    "no-partner": list(
        STATE_FEATURE_NAMES
    ),  # 52 features, partner cols zeroed at training
    "interaction": list(STATE_FEATURE_NAMES)
    + INTERACTION_FEATURE_NAMES,  # 52 + 3 interaction
    "constrained": CONSTRAINED_FEATURES,  # per-contract locked features
}


def resolve_feature_names(
    feature_set: str,
    family: str,
) -> list[str]:
    """Resolve the state feature list for a given feature set and contract family.

    For flat feature sets (full, r0, etc.), returns the list as-is.
    For per-contract feature sets (constrained), returns the family-specific list.

    Args:
        feature_set: Name of the feature set (key in FEATURE_SETS).
        family: Contract family ("suit", "high", "low", or "pass").

    Returns:
        The resolved list of state feature names.
    """
    entry = FEATURE_SETS[feature_set]
    if isinstance(entry, dict):
        # Per-contract feature set — pass uses suit features as fallback
        effective_family = family if family in entry else "suit"
        return list(entry[effective_family])
    return list(entry)


# Feature sets that require zero-masking specific columns at training time.
# The model artifact retains all feature names (passes ActionValueBidder validation)
# but OLS learns zero coefficients for zeroed columns.
_ZERO_MASK_COLUMNS: dict[str, list[str]] = {
    "no-partner": _PARTNER_FEATURE_NAMES,
}

VALID_TARGETS = ("net_points", "tricks_won")

VALID_SELECTIONS = ("none", "forward")

# Gate X2 R² thresholds per contract family
GATE_X2_THRESHOLDS = {
    "suit": 0.05,
    "high": 0.05,
    "low": 0.05,
    "pass": 0.02,
}


# ── Data Loading ─────────────────────────────────────────────


def load_dataset(
    parquet_path: str,
    target_col: str = TARGET_COL,
    state_feature_names: list[str] | None = None,
) -> pd.DataFrame:
    """Load and validate the action-value parquet dataset.

    Args:
        parquet_path: Path to the parquet file.
        target_col: Target column name (must exist in dataset).
        state_feature_names: State feature names to validate. Defaults to
            full STATE_FEATURE_NAMES.
    """
    if state_feature_names is None:
        state_feature_names = STATE_FEATURE_NAMES

    df = pd.read_parquet(parquet_path)

    # Validate required columns (exclude computed features — they're derived
    # at matrix-build time, not stored in the parquet)
    computed = set(_INTERACTION_FORMULAS) | {"bid_n_sq"}
    required = (set(METADATA_COLS) | set(state_feature_names) | {target_col}) - computed
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {sorted(missing)}")

    return df


# ── Splitting ────────────────────────────────────────────────


def split_by_deal(
    df: pd.DataFrame,
    seed: int,
    train_frac: float = 0.8,
    val_frac: float = 0.1,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Three-way split by deal_id to prevent leakage.

    Each deal produces ~160 rows (4 seats × ~40 actions). Splitting by deal_id
    ensures no information from the same deal appears in train and val/test.

    Returns (train_df, val_df, test_df).
    """
    unique_deals = df["deal_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_deals)

    n = len(unique_deals)
    train_end = int(n * train_frac)
    val_end = train_end + int(n * val_frac)

    train_ids = set(unique_deals[:train_end])
    val_ids = set(unique_deals[train_end:val_end])
    test_ids = set(unique_deals[val_end:])

    train_df = df[df["deal_id"].isin(train_ids)].copy()
    val_df = df[df["deal_id"].isin(val_ids)].copy()
    test_df = df[df["deal_id"].isin(test_ids)].copy()

    return train_df, val_df, test_df


# ── Training ─────────────────────────────────────────────────


def train_family_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    family: str,
    state_feature_names: list[str] | None = None,
    target_col: str = TARGET_COL,
) -> dict:
    """Train OLS for one contract family (suit/high/low).

    Features: state features + bid_n + bid_n_sq.
    Target: configurable (default net_points).

    Args:
        state_feature_names: State features to use. Defaults to full
            STATE_FEATURE_NAMES (52 columns).
        target_col: Target column name.
    """
    if state_feature_names is None:
        state_feature_names = STATE_FEATURE_NAMES
    feature_names = list(state_feature_names) + list(ACTION_FEATURE_NAMES)

    # Filter to this contract family
    train_sub = train_df[train_df["contract_family"] == family]
    val_sub = val_df[val_df["contract_family"] == family]

    if len(train_sub) == 0:
        raise ValueError(f"No training rows for family '{family}'")

    # Build feature matrices — bid_n is already in the dataset,
    # bid_n_sq needs to be computed
    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[target_col].values

    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[target_col].values

    # Fit OLS
    weights, bias = _fit_ols(X_train, y_train)

    # Compute metrics on validation set
    y_pred_val = X_val @ weights + bias
    metrics = _compute_metrics(y_val, y_pred_val)

    return {
        "coefficients": weights.tolist(),
        "intercept": float(bias),
        "feature_names": feature_names,
        "r_squared": metrics["r2"],
        "mae": metrics["mae"],
        "n_train": len(train_sub),
        "n_val": len(val_sub),
    }


def train_pass_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    state_feature_names: list[str] | None = None,
    target_col: str = TARGET_COL,
) -> dict:
    """Train OLS for pass action.

    Features: state features only (no action features).
    Target: configurable (default net_points).

    Args:
        state_feature_names: State features to use. Defaults to full
            STATE_FEATURE_NAMES (52 columns).
        target_col: Target column name.
    """
    if state_feature_names is None:
        state_feature_names = STATE_FEATURE_NAMES
    feature_names = list(state_feature_names)

    # Filter to pass rows
    train_sub = train_df[train_df["action_type"] == "pass"]
    val_sub = val_df[val_df["action_type"] == "pass"]

    if len(train_sub) == 0:
        raise ValueError("No training rows for pass action")

    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[target_col].values

    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[target_col].values

    # Fit OLS
    weights, bias = _fit_ols(X_train, y_train)

    # Compute metrics on validation set
    y_pred_val = X_val @ weights + bias
    metrics = _compute_metrics(y_val, y_pred_val)

    return {
        "coefficients": weights.tolist(),
        "intercept": float(bias),
        "feature_names": feature_names,
        "r_squared": metrics["r2"],
        "mae": metrics["mae"],
        "n_train": len(train_sub),
        "n_val": len(val_sub),
    }


def _build_feature_matrix(df: pd.DataFrame, feature_names: list[str]) -> np.ndarray:
    """Extract feature matrix from dataframe, computing derived features.

    Handles three types of computed features:
    - ``bid_n_sq``: square of ``bid_n`` (action feature)
    - Interaction terms from ``_INTERACTION_FORMULAS``: product of two columns
    - All other names: direct column lookup
    """
    cols = []
    for name in feature_names:
        if name == "bid_n_sq":
            cols.append(df["bid_n"].values ** 2)
        elif name in _INTERACTION_FORMULAS:
            col_a, col_b = _INTERACTION_FORMULAS[name]
            cols.append(df[col_a].values * df[col_b].values)
        else:
            cols.append(df[name].values)
    return np.column_stack(cols).astype(np.float64)


# ── Forward Selection ──────────────────────────────────────


def run_forward_selection(
    train_df: pd.DataFrame,
    feature_names: list[str],
    target_col: str,
    seed: int,
    cv_folds: int = 5,
) -> tuple[list[str], dict]:
    """Run forward feature selection on a training subset.

    Uses GroupKFold by hand_id to prevent leakage across folds.

    Args:
        train_df: Training dataframe (already filtered to relevant subset).
        feature_names: Candidate feature names.
        target_col: Target column name.
        seed: Random seed for reproducibility.
        cv_folds: Number of CV folds.

    Returns:
        (selected_feature_names, selection_log)
    """
    from bid_euchre.models.feature_selection import forward_select

    X = _build_feature_matrix(train_df, feature_names)
    y = train_df[target_col].values
    groups = train_df["hand_id"].values

    selected_names, selection_log = forward_select(
        X_train=X,
        y_train=y,
        candidate_names=list(feature_names),
        groups=groups,
        cv_folds=cv_folds,
        seed=seed,
    )
    return selected_names, selection_log


# ── GBT Training ────────────────────────────────────────────


def train_family_gbt(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    family: str,
    state_feature_names: list[str] | None = None,
    target_col: str = TARGET_COL,
    seed: int = 42,
) -> tuple[object, dict]:
    """Train GBT regressor for one contract family (suit/high/low).

    Returns (gbt_model, metadata_dict) where gbt_model is the fitted
    sklearn GradientBoostingRegressor and metadata_dict contains metrics
    and feature info for the artifact JSON.
    """
    from sklearn.ensemble import GradientBoostingRegressor

    if state_feature_names is None:
        state_feature_names = STATE_FEATURE_NAMES
    feature_names = list(state_feature_names) + list(ACTION_FEATURE_NAMES)

    train_sub = train_df[train_df["contract_family"] == family]
    val_sub = val_df[val_df["contract_family"] == family]

    if len(train_sub) == 0:
        raise ValueError(f"No training rows for family '{family}'")

    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[target_col].values
    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[target_col].values

    gbt = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=seed,
    )
    gbt.fit(X_train, y_train)

    y_pred_val = gbt.predict(X_val)
    metrics = _compute_metrics(y_val, y_pred_val)

    metadata = {
        "feature_names": feature_names,
        "r_squared": metrics["r2"],
        "mae": metrics["mae"],
        "n_train": len(train_sub),
        "n_val": len(val_sub),
        "feature_importances": dict(
            zip(feature_names, gbt.feature_importances_.tolist())
        ),
    }
    return gbt, metadata


def train_pass_gbt(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    state_feature_names: list[str] | None = None,
    target_col: str = TARGET_COL,
    seed: int = 42,
) -> tuple[object, dict]:
    """Train GBT regressor for pass action (state features only)."""
    from sklearn.ensemble import GradientBoostingRegressor

    if state_feature_names is None:
        state_feature_names = STATE_FEATURE_NAMES
    feature_names = list(state_feature_names)

    train_sub = train_df[train_df["action_type"] == "pass"]
    val_sub = val_df[val_df["action_type"] == "pass"]

    if len(train_sub) == 0:
        raise ValueError("No training rows for pass action")

    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[target_col].values
    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[target_col].values

    gbt = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=seed,
    )
    gbt.fit(X_train, y_train)

    y_pred_val = gbt.predict(X_val)
    metrics = _compute_metrics(y_val, y_pred_val)

    metadata = {
        "feature_names": feature_names,
        "r_squared": metrics["r2"],
        "mae": metrics["mae"],
        "n_train": len(train_sub),
        "n_val": len(val_sub),
        "feature_importances": dict(
            zip(feature_names, gbt.feature_importances_.tolist())
        ),
    }
    return gbt, metadata


# ── Two-Stage Training ───────────────────────────────────────


def train_two_stage_suit_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    state_feature_names: list[str] | None = None,
    target_col: str = TARGET_COL,
) -> dict:
    """Train two-stage suit model: P(make) logistic + conditional payoff OLS.

    Stage 1: Logistic regression on made_bid = (net_points >= 2*bid_n - 10)
    Stage 2: Separate OLS for make/set subsets
    Composite: P(make)*E[pts|make] + (1-P(make))*E[pts|set]

    Args:
        train_df: Training data (all families — will be filtered to suit).
        val_df: Validation data (all families — will be filtered to suit).
        state_feature_names: State features to use.
        target_col: Target column name.

    Returns:
        Dict with logistic, make_model, set_model, and composite metrics.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    if state_feature_names is None:
        state_feature_names = STATE_FEATURE_NAMES
    feature_names = list(state_feature_names) + list(ACTION_FEATURE_NAMES)

    # Filter to suit family
    train_sub = train_df[train_df["contract_family"] == "suit"]
    val_sub = val_df[val_df["contract_family"] == "suit"]

    if len(train_sub) == 0:
        raise ValueError("No training rows for family 'suit'")

    # Derive made_bid binary target: net_points >= 2*bid_n - 10
    train_made = train_sub[target_col].values >= 2 * train_sub["bid_n"].values - 10
    val_made = val_sub[target_col].values >= 2 * val_sub["bid_n"].values - 10

    # Build feature matrices
    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[target_col].values
    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[target_col].values

    # Stage 1: Logistic regression on P(make)
    lr = LogisticRegression(max_iter=5000, solver="lbfgs")
    lr.fit(X_train, train_made.astype(int))
    p_make_val = lr.predict_proba(X_val)[:, 1]
    auc = float(roc_auc_score(val_made.astype(int), p_make_val))

    # Stage 2: Separate OLS for make/set subsets
    make_mask = train_made
    set_mask = ~train_made

    X_train_make = X_train[make_mask]
    y_train_make = y_train[make_mask]
    X_train_set = X_train[set_mask]
    y_train_set = y_train[set_mask]

    w_make, b_make = _fit_ols(X_train_make, y_train_make)
    w_set, b_set = _fit_ols(X_train_set, y_train_set)

    # Per-regime validation metrics
    make_metrics = (
        _compute_metrics(y_val[val_made], X_val[val_made] @ w_make + b_make)
        if val_made.sum() > 0
        else {"r2": float("nan"), "mae": float("nan")}
    )
    set_metrics = (
        _compute_metrics(y_val[~val_made], X_val[~val_made] @ w_set + b_set)
        if (~val_made).sum() > 0
        else {"r2": float("nan"), "mae": float("nan")}
    )

    # Composite prediction on ALL validation rows using logistic probabilities
    e_make_val = X_val @ w_make + b_make
    e_set_val = X_val @ w_set + b_set
    y_pred_composite = p_make_val * e_make_val + (1 - p_make_val) * e_set_val
    composite_metrics = _compute_metrics(y_val, y_pred_composite)

    return {
        "logistic": {
            "coefficients": lr.coef_[0].tolist(),
            "intercept": float(lr.intercept_[0]),
            "auc": auc,
        },
        "make_model": {
            "coefficients": w_make.tolist(),
            "intercept": float(b_make),
            "r_squared": float(make_metrics["r2"]),
            "mae": float(make_metrics["mae"]),
            "n_train": int(make_mask.sum()),
        },
        "set_model": {
            "coefficients": w_set.tolist(),
            "intercept": float(b_set),
            "r_squared": float(set_metrics["r2"]),
            "mae": float(set_metrics["mae"]),
            "n_train": int(set_mask.sum()),
        },
        "feature_names": feature_names,
        "composite_r_squared": float(composite_metrics["r2"]),
        "composite_mae": float(composite_metrics["mae"]),
        "auc": auc,
        "make_rate": float(train_made.mean()),
        "n_train": len(train_sub),
        "n_val": len(val_sub),
    }


def build_two_stage_artifact(
    suit_result: dict,
    high_model: dict,
    low_model: dict,
    pass_model: dict,
    seed: int,
    n_deals: int,
    continuation_artifact: str,
    feature_set: str = "full",
    target_col: str = TARGET_COL,
    dataset_path: str | None = None,
    dataset_sha256: str | None = None,
    continuation_artifact_sha256: str | None = None,
) -> dict:
    """Assemble the two_stage_action_value_v1 artifact dict.

    Suit model uses three-component structure (logistic + make_model + set_model).
    High/low/pass use standard OLS format (same as action_value_olsa_v1).
    """
    git_sha = _git_sha()

    metadata: dict = {
        "n_deals": n_deals,
        "training_seed": seed,
        "arm": feature_set,
        "context_features": [],
        "git_sha": git_sha,
        "created_at_utc": utc_now_iso(),
        "model_class": "two-stage",
        "continuation_artifact_path": continuation_artifact,
    }
    if dataset_path is not None:
        metadata["dataset_path"] = dataset_path
    if dataset_sha256 is not None:
        metadata["dataset_sha256"] = dataset_sha256
    if continuation_artifact_sha256 is not None:
        metadata["continuation_artifact_sha256"] = continuation_artifact_sha256

    return {
        "schema_version": "two_stage_action_value_v1",
        "target": target_col,
        "risk_mode": "neutral",
        "continuation_policy": Path(continuation_artifact).stem,
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": feature_set,
        "models": {
            "suit": suit_result,
            "high": high_model,
            "low": low_model,
            "pass": pass_model,
        },
        "metadata": metadata,
    }


# ── Artifact ─────────────────────────────────────────────────


def build_artifact(
    models: dict[str, dict],
    seed: int,
    n_deals: int,
    continuation_artifact: str,
    feature_set: str = "full",
    target_col: str = TARGET_COL,
    dataset_path: str | None = None,
    dataset_sha256: str | None = None,
    continuation_artifact_sha256: str | None = None,
) -> dict:
    """Assemble the action_value_olsa_v1 artifact dict.

    Args:
        feature_set: Name of the feature set used ("full" or "r0").
        target_col: Name of the target column used for training.
        dataset_path: Path to training dataset (provenance).
        dataset_sha256: SHA-256 of the training dataset file.
        continuation_artifact_sha256: Content hash of the continuation artifact.
    """
    git_sha = _git_sha()

    metadata: dict = {
        "n_deals": n_deals,
        "training_seed": seed,
        "arm": feature_set,
        "context_features": [],
        "git_sha": git_sha,
        "created_at_utc": utc_now_iso(),
        "model_class": "ols",
        "continuation_artifact_path": continuation_artifact,
    }
    if dataset_path is not None:
        metadata["dataset_path"] = dataset_path
    if dataset_sha256 is not None:
        metadata["dataset_sha256"] = dataset_sha256
    if continuation_artifact_sha256 is not None:
        metadata["continuation_artifact_sha256"] = continuation_artifact_sha256

    return {
        "schema_version": "action_value_olsa_v1",
        "target": target_col,
        "risk_mode": "neutral",
        "continuation_policy": Path(continuation_artifact).stem,
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": feature_set,
        "models": models,
        "metadata": metadata,
    }


def build_gbt_artifact(
    gbt_models: dict[str, object],
    model_metadata: dict[str, dict],
    output_dir: Path,
    seed: int,
    n_deals: int,
    continuation_artifact: str,
    feature_set: str = "full",
    target_col: str = TARGET_COL,
    dataset_path: str | None = None,
    dataset_sha256: str | None = None,
    continuation_artifact_sha256: str | None = None,
) -> dict:
    """Build action_value_gbt_v1 artifact: JSON metadata + joblib model files.

    Saves each GBT model as a .joblib file in output_dir and returns the
    artifact dict with relative file references.

    Args:
        dataset_path: Path to training dataset (provenance).
        dataset_sha256: SHA-256 of the training dataset file.
        continuation_artifact_sha256: Content hash of the continuation artifact.
    """
    import joblib

    git_sha = _git_sha()
    output_dir.mkdir(parents=True, exist_ok=True)

    models_section = {}
    for family, gbt_model in gbt_models.items():
        model_file = f"gbt_{family}.joblib"
        joblib.dump(gbt_model, output_dir / model_file)
        models_section[family] = {
            "model_file": model_file,
            **model_metadata[family],
        }

    metadata: dict = {
        "n_deals": n_deals,
        "training_seed": seed,
        "arm": feature_set,
        "context_features": [],
        "git_sha": git_sha,
        "created_at_utc": utc_now_iso(),
        "model_class": "gbt",
        "continuation_artifact_path": continuation_artifact,
    }
    if dataset_path is not None:
        metadata["dataset_path"] = dataset_path
    if dataset_sha256 is not None:
        metadata["dataset_sha256"] = dataset_sha256
    if continuation_artifact_sha256 is not None:
        metadata["continuation_artifact_sha256"] = continuation_artifact_sha256

    return {
        "schema_version": "action_value_gbt_v1",
        "target": target_col,
        "risk_mode": "neutral",
        "continuation_policy": Path(continuation_artifact).stem,
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": feature_set,
        "models": models_section,
        "metadata": metadata,
    }


def _git_sha() -> str:
    """Get current git HEAD SHA."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _compute_provenance_hashes(
    dataset_path: str,
    continuation_artifact_path: str,
) -> tuple[str, str | None]:
    """Compute SHA-256 hashes for dataset and continuation artifact.

    Returns (dataset_sha256, continuation_content_hash).
    The continuation hash uses content_hash() (excluding freeze fields) so
    the hash remains stable regardless of whether the artifact is frozen.
    """
    from bid_euchre.models.freeze import content_hash as compute_content_hash
    from bid_euchre.models.freeze import sha256_file

    dataset_sha = sha256_file(dataset_path)

    cont_sha = None
    cont_path = Path(continuation_artifact_path)
    if cont_path.exists() and cont_path.suffix == ".json":
        with open(cont_path) as f:
            cont_artifact = json.load(f)
        cont_sha = compute_content_hash(cont_artifact)

    return dataset_sha, cont_sha


def _build_behavioral_provenance(report: dict) -> dict:
    """Extract behavioral validation summary for artifact provenance metadata."""
    stats = report.get("behavioral_stats", {})
    return {
        "passed": True,
        "avg_bid": stats.get("avg_bid"),
        "pass_rate": stats.get("pass_rate"),
        "bid_10_rate": stats.get("bid_10_rate"),
        "contract_diversity": stats.get("contract_diversity"),
        "n_observations": stats.get("n_observations"),
        "validated_at_utc": utc_now_iso(),
    }


# ── Gate X2 ──────────────────────────────────────────────────


def validate_gate_x2(artifact: dict) -> None:
    """Gate X2: check R² thresholds per model.

    Raises AssertionError if any model fails its threshold.
    """
    models = artifact["models"]

    for family, threshold in GATE_X2_THRESHOLDS.items():
        model = models[family]
        r2 = model["r_squared"]
        assert r2 > threshold, f"Gate X2 FAIL: {family} R²={r2:.4f} <= {threshold}"

    print(
        f"  Gate X2 PASS: "
        f"suit R²={models['suit']['r_squared']:.4f}, "
        f"high R²={models['high']['r_squared']:.4f}, "
        f"low R²={models['low']['r_squared']:.4f}, "
        f"pass R²={models['pass']['r_squared']:.4f}"
    )


# ── CLI ──────────────────────────────────────────────────────


def _artifact_filename(feature_set: str) -> str:
    """Compute output filename based on feature set.

    "full" → "action_value_full.json" (backward compatible)
    "r0"   → "action_value_r0_features.json"
    """
    if feature_set == "full":
        return "action_value_full.json"
    return f"action_value_{feature_set}_features.json"


VALID_MODEL_CLASSES = ("ols", "gbt", "two-stage")


def _run_behavioral_validation(artifact_path: str) -> dict:
    """Run behavioral validation on a freshly trained artifact.

    Imports the validator lazily to avoid circular dependency at module level.
    Returns the validation report dict on success.
    Raises AssertionError if the artifact fails behavioral checks.
    """
    # Import here to keep module-level imports lean (this module is also
    # imported by tests that don't need the validator).
    from validate_action_value_artifact import validate_artifact

    passed, report = validate_artifact(artifact_path)

    stats = report.get("behavioral_stats", {})
    print(
        f"    avg_bid={stats.get('avg_bid', '?'):.2f}, "
        f"pass_rate={stats.get('pass_rate', '?'):.3f}, "
        f"bid_10_rate={stats.get('bid_10_rate', '?'):.3f}, "
        f"contract_diversity={stats.get('contract_diversity', '?')}, "
        f"bid_level_std={stats.get('bid_level_std', '?'):.3f}"
    )

    if not passed:
        failures = []
        for section in ("structural", "quality", "behavioral"):
            section_data = report.get(section, {})
            for failure in section_data.get("failures", []):
                failures.append(f"{failure['name']}: {failure['detail']}")
        failure_msg = "\n    ".join(failures)
        raise AssertionError(
            f"Behavioral validation FAILED:\n    {failure_msg}\n"
            "Use --skip-validation to bypass."
        )

    print("  Behavioral validation PASS")
    return report


def main():
    parser = argparse.ArgumentParser(description="Train action-value models for R1.5")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to action_value.parquet",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for artifact",
    )
    parser.add_argument(
        "--continuation-artifact",
        required=True,
        help="Path to continuation policy artifact (for provenance)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip Gate X2 validation",
    )
    parser.add_argument(
        "--feature-set",
        choices=sorted(FEATURE_SETS.keys()),
        default="full",
        help="Feature set: 'full' (52 state), 'r0' (39 hand), 'no-partner' (52 state, partner cols zeroed), 'interaction' (52 + 3 interaction terms)",
    )
    parser.add_argument(
        "--target",
        choices=list(VALID_TARGETS),
        default="net_points",
        help="Target column: 'net_points' (default) or 'tricks_won'",
    )
    parser.add_argument(
        "--model-class",
        choices=list(VALID_MODEL_CLASSES),
        default="ols",
        help="Model class: 'ols' (default), 'gbt' (gradient boosted trees), or 'two-stage' (logistic + conditional OLS for suit)",
    )
    parser.add_argument(
        "--selection",
        choices=list(VALID_SELECTIONS),
        default="none",
        help=(
            "Feature selection: 'none' (default, use all features in --feature-set) "
            "or 'forward' (stepwise forward selection with GroupKFold by hand_id). "
            "Not compatible with --model-class gbt."
        ),
    )
    args = parser.parse_args()

    # Validate: forward selection is not compatible with GBT
    if args.selection == "forward" and args.model_class == "gbt":
        parser.error(
            "--selection forward is not compatible with --model-class gbt. "
            "GBT handles feature selection internally via tree splits."
        )

    feature_set_entry = FEATURE_SETS[args.feature_set]
    target_col = args.target
    model_class = args.model_class
    is_per_contract = isinstance(feature_set_entry, dict)

    # For per-contract feature sets, compute the union of all features for
    # dataset validation, but resolve per-family at training time.
    if is_per_contract:
        all_features_union = sorted(set().union(*feature_set_entry.values()))
        feature_count_desc = ", ".join(
            f"{k}: {len(v)}" for k, v in feature_set_entry.items()
        )
    else:
        all_features_union = list(feature_set_entry)
        feature_count_desc = f"{len(feature_set_entry)} state features"

    print("=== R1.5 Action-Value Training Pipeline ===")
    print(f"  Seed: {args.seed}")
    print(f"  Dataset: {args.dataset}")
    print(f"  Feature set: {args.feature_set} ({feature_count_desc})")
    print(f"  Target: {target_col}")
    print(f"  Model class: {model_class}")
    print(f"  Selection: {args.selection}")

    # Load dataset — validate that all features used exist in the parquet
    print("  Loading dataset...")
    df = load_dataset(
        args.dataset,
        target_col=target_col,
        state_feature_names=all_features_union,
    )
    n_deals = df["deal_id"].nunique()
    print(f"  Loaded {len(df)} rows, {n_deals} deals")

    # Zero-mask columns for ablation feature sets (e.g., "no-partner")
    mask_cols = _ZERO_MASK_COLUMNS.get(args.feature_set, [])
    if mask_cols:
        for col in mask_cols:
            df[col] = 0.0
        print(f"  Zero-masked columns: {mask_cols}")

    # Split
    print("  Splitting by deal_id (80/10/10)...")
    train_df, val_df, test_df = split_by_deal(df, args.seed)
    print(
        f"  Train: {len(train_df)} rows, "
        f"Val: {len(val_df)} rows, "
        f"Test: {len(test_df)} rows"
    )

    output_dir = Path(args.output_dir)

    if model_class == "gbt":
        state_feature_names = (
            resolve_feature_names(args.feature_set, "suit")
            if is_per_contract
            else list(feature_set_entry)
        )
        _train_gbt_pipeline(
            train_df,
            val_df,
            state_feature_names,
            target_col,
            output_dir,
            args,
            n_deals,
        )
    elif model_class == "two-stage":
        _train_two_stage_pipeline(
            train_df,
            val_df,
            feature_set_entry if is_per_contract else list(feature_set_entry),
            target_col,
            output_dir,
            args,
            n_deals,
        )
    else:
        _train_ols_pipeline(
            train_df,
            val_df,
            feature_set_entry if is_per_contract else list(feature_set_entry),
            target_col,
            output_dir,
            args,
            n_deals,
        )


def _train_ols_pipeline(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    state_feature_names: list[str] | dict[str, list[str]],
    target_col: str,
    output_dir: Path,
    args: argparse.Namespace,
    n_deals: int,
) -> None:
    """OLS training pipeline (original behavior).

    Args:
        state_feature_names: Either a flat list of state features (for uniform
            feature sets) or a dict mapping contract_family -> feature list
            (for per-contract feature sets like "constrained").
    """
    is_per_contract = isinstance(state_feature_names, dict)
    selection = getattr(args, "selection", "none")

    # Compute provenance hashes
    print("  Computing provenance hashes...")
    dataset_sha, cont_sha = _compute_provenance_hashes(
        args.dataset, args.continuation_artifact
    )
    print(f"    dataset_sha256={dataset_sha[:12]}...")
    if cont_sha:
        print(f"    continuation_sha256={cont_sha[:12]}...")

    selection_logs: dict[str, dict] = {}
    models = {}
    for family in ("suit", "high", "low"):
        family_features = (
            resolve_feature_names(args.feature_set, family)
            if is_per_contract
            else list(state_feature_names)
        )

        # Forward selection: reduce feature set before training
        if selection == "forward":
            print(f"  Running forward selection for {family}...")
            train_sub = train_df[train_df["contract_family"] == family]
            all_features = list(family_features) + list(ACTION_FEATURE_NAMES)
            selected, sel_log = run_forward_selection(
                train_sub, all_features, target_col, seed=args.seed
            )
            selection_logs[family] = sel_log
            # Split selected back into state vs action features
            action_set = set(ACTION_FEATURE_NAMES)
            family_features = [f for f in selected if f not in action_set]
            print(
                f"    Selected {len(selected)} features "
                f"(state: {len(family_features)}, "
                f"R²={sel_log['final_r2']})"
            )

        print(f"  Training {family} OLS model...")
        models[family] = train_family_model(
            train_df,
            val_df,
            family,
            state_feature_names=family_features,
            target_col=target_col,
        )
        print(
            f"    R²={models[family]['r_squared']:.4f}, "
            f"MAE={models[family]['mae']:.3f}, "
            f"n_train={models[family]['n_train']}"
        )

    # Pass model: use suit features for per-contract sets
    pass_features = (
        resolve_feature_names(args.feature_set, "pass")
        if is_per_contract
        else list(state_feature_names)
    )

    if selection == "forward":
        print("  Running forward selection for pass...")
        train_pass_sub = train_df[train_df["action_type"] == "pass"]
        selected, sel_log = run_forward_selection(
            train_pass_sub, list(pass_features), target_col, seed=args.seed
        )
        selection_logs["pass"] = sel_log
        pass_features = selected
        print(f"    Selected {len(selected)} features (R²={sel_log['final_r2']})")

    print("  Training pass OLS model...")
    models["pass"] = train_pass_model(
        train_df,
        val_df,
        state_feature_names=pass_features,
        target_col=target_col,
    )
    print(
        f"    R²={models['pass']['r_squared']:.4f}, "
        f"MAE={models['pass']['mae']:.3f}, "
        f"n_train={models['pass']['n_train']}"
    )

    artifact = build_artifact(
        models,
        args.seed,
        n_deals,
        args.continuation_artifact,
        feature_set=args.feature_set,
        target_col=target_col,
        dataset_path=args.dataset,
        dataset_sha256=dataset_sha,
        continuation_artifact_sha256=cont_sha,
    )

    # Record selection metadata
    if selection != "none":
        artifact["metadata"]["selection"] = selection
        artifact["metadata"]["selection_logs"] = selection_logs

    if not args.skip_validation:
        print("  Running Gate X2 validation...")
        validate_gate_x2(artifact)

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / _artifact_filename(args.feature_set)
    artifact_path.write_text(json.dumps(artifact, indent=2))

    if not args.skip_validation:
        print("  Running behavioral validation...")
        report = _run_behavioral_validation(str(artifact_path))

        print("  Freezing artifact with provenance...")
        from bid_euchre.models.freeze import freeze_with_provenance

        provenance = {
            "behavioral_validation": _build_behavioral_provenance(report),
        }
        frozen = freeze_with_provenance(str(artifact_path), provenance)
        print(f"    artifact_sha256={frozen['artifact_sha256'][:12]}...")

    print(f"\n  Artifact: {artifact_path}")
    print("  Done.")


def _train_gbt_pipeline(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    state_feature_names: list[str],
    target_col: str,
    output_dir: Path,
    args: argparse.Namespace,
    n_deals: int,
) -> None:
    """GBT training pipeline."""
    # Compute provenance hashes
    print("  Computing provenance hashes...")
    dataset_sha, cont_sha = _compute_provenance_hashes(
        args.dataset, args.continuation_artifact
    )
    print(f"    dataset_sha256={dataset_sha[:12]}...")
    if cont_sha:
        print(f"    continuation_sha256={cont_sha[:12]}...")

    gbt_models = {}
    model_metadata = {}

    for family in ("suit", "high", "low"):
        print(f"  Training {family} GBT model...")
        gbt_model, meta = train_family_gbt(
            train_df,
            val_df,
            family,
            state_feature_names=state_feature_names,
            target_col=target_col,
            seed=args.seed,
        )
        gbt_models[family] = gbt_model
        model_metadata[family] = meta
        print(
            f"    R²={meta['r_squared']:.4f}, "
            f"MAE={meta['mae']:.3f}, "
            f"n_train={meta['n_train']}"
        )

    print("  Training pass GBT model...")
    pass_model, pass_meta = train_pass_gbt(
        train_df,
        val_df,
        state_feature_names=state_feature_names,
        target_col=target_col,
        seed=args.seed,
    )
    gbt_models["pass"] = pass_model
    model_metadata["pass"] = pass_meta
    print(
        f"    R²={pass_meta['r_squared']:.4f}, "
        f"MAE={pass_meta['mae']:.3f}, "
        f"n_train={pass_meta['n_train']}"
    )

    artifact = build_gbt_artifact(
        gbt_models,
        model_metadata,
        output_dir,
        args.seed,
        n_deals,
        args.continuation_artifact,
        feature_set=args.feature_set,
        target_col=target_col,
        dataset_path=args.dataset,
        dataset_sha256=dataset_sha,
        continuation_artifact_sha256=cont_sha,
    )

    if not args.skip_validation:
        print("  Running Gate X2 validation...")
        validate_gate_x2(artifact)

    artifact_path = output_dir / "action_value_gbt.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))

    if not args.skip_validation:
        print("  Running behavioral validation...")
        report = _run_behavioral_validation(str(artifact_path))

        print("  Freezing artifact with provenance...")
        from bid_euchre.models.freeze import freeze_with_provenance

        provenance = {
            "behavioral_validation": _build_behavioral_provenance(report),
        }
        frozen = freeze_with_provenance(str(artifact_path), provenance)
        print(f"    artifact_sha256={frozen['artifact_sha256'][:12]}...")

    print(f"\n  Artifact: {artifact_path}")
    print(f"  Model files: {output_dir}/gbt_*.joblib")
    print("  Done.")


def _train_two_stage_pipeline(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    state_feature_names: list[str] | dict[str, list[str]],
    target_col: str,
    output_dir: Path,
    args: argparse.Namespace,
    n_deals: int,
) -> None:
    """Two-stage training pipeline: P(make) logistic + conditional OLS for suit.

    Args:
        state_feature_names: Either a flat list or a per-contract dict.
    """
    is_per_contract = isinstance(state_feature_names, dict)
    selection = getattr(args, "selection", "none")

    # Compute provenance hashes
    print("  Computing provenance hashes...")
    dataset_sha, cont_sha = _compute_provenance_hashes(
        args.dataset, args.continuation_artifact
    )
    print(f"    dataset_sha256={dataset_sha[:12]}...")
    if cont_sha:
        print(f"    continuation_sha256={cont_sha[:12]}...")

    selection_logs: dict[str, dict] = {}

    # Resolve suit features
    suit_features = (
        resolve_feature_names(args.feature_set, "suit")
        if is_per_contract
        else list(state_feature_names)
    )

    # Forward selection for two-stage suit: run separately on each sub-model
    if selection == "forward":
        print("  Running forward selection for suit two-stage sub-models...")
        train_suit = train_df[train_df["contract_family"] == "suit"]
        all_suit_features = list(suit_features) + list(ACTION_FEATURE_NAMES)

        # P(make) logistic — use same candidate features
        selected_logistic, log_logistic = run_forward_selection(
            train_suit, all_suit_features, target_col, seed=args.seed
        )
        # E[pts|make] OLS
        made_mask = train_suit[target_col].values >= 2 * train_suit["bid_n"].values - 10
        if made_mask.sum() > 0:
            train_make = train_suit[made_mask]
            selected_make, log_make = run_forward_selection(
                train_make, all_suit_features, target_col, seed=args.seed
            )
        else:
            selected_make, log_make = all_suit_features, {"steps": [], "final_r2": None}
        # E[pts|set] OLS
        if (~made_mask).sum() > 0:
            train_set = train_suit[~made_mask]
            selected_set, log_set = run_forward_selection(
                train_set, all_suit_features, target_col, seed=args.seed
            )
        else:
            selected_set, log_set = all_suit_features, {"steps": [], "final_r2": None}

        selection_logs["suit_logistic"] = log_logistic
        selection_logs["suit_make"] = log_make
        selection_logs["suit_set"] = log_set

        # Use union of all selected features for the suit two-stage model
        # (the model uses all features; selection is informational for now)
        action_set = set(ACTION_FEATURE_NAMES)
        all_selected = set(selected_logistic) | set(selected_make) | set(selected_set)
        suit_features = [
            f for f in all_suit_features if f in all_selected and f not in action_set
        ]
        print(
            f"    Suit two-stage: logistic={len(selected_logistic)}, "
            f"make={len(selected_make)}, set={len(selected_set)} features"
        )

    # Train suit model with two-stage decomposition
    print("  Training suit two-stage model...")
    suit_result = train_two_stage_suit_model(
        train_df,
        val_df,
        state_feature_names=suit_features,
        target_col=target_col,
    )
    print(
        f"    P(make) AUC={suit_result['auc']:.4f}, "
        f"composite R²={suit_result['composite_r_squared']:.4f}, "
        f"composite MAE={suit_result['composite_mae']:.3f}"
    )
    print(
        f"    make_rate={suit_result['make_rate']:.3f}, "
        f"make R²={suit_result['make_model']['r_squared']:.4f}, "
        f"set R²={suit_result['set_model']['r_squared']:.4f}"
    )

    if suit_result["auc"] < 0.70:
        print(
            f"  WARNING: P(make) AUC={suit_result['auc']:.4f} < 0.70 — "
            "logistic stage may be weak"
        )

    # Train high/low with standard OLS
    models_ols = {}
    for family in ("high", "low"):
        family_features = (
            resolve_feature_names(args.feature_set, family)
            if is_per_contract
            else list(state_feature_names)
        )

        if selection == "forward":
            print(f"  Running forward selection for {family}...")
            train_sub = train_df[train_df["contract_family"] == family]
            all_features = list(family_features) + list(ACTION_FEATURE_NAMES)
            selected, sel_log = run_forward_selection(
                train_sub, all_features, target_col, seed=args.seed
            )
            selection_logs[family] = sel_log
            action_set = set(ACTION_FEATURE_NAMES)
            family_features = [f for f in selected if f not in action_set]
            print(
                f"    Selected {len(selected)} features "
                f"(state: {len(family_features)}, "
                f"R²={sel_log['final_r2']})"
            )

        print(f"  Training {family} OLS model...")
        models_ols[family] = train_family_model(
            train_df,
            val_df,
            family,
            state_feature_names=family_features,
            target_col=target_col,
        )
        print(
            f"    R²={models_ols[family]['r_squared']:.4f}, "
            f"MAE={models_ols[family]['mae']:.3f}, "
            f"n_train={models_ols[family]['n_train']}"
        )

    # Train pass with standard OLS
    pass_features = (
        resolve_feature_names(args.feature_set, "pass")
        if is_per_contract
        else list(state_feature_names)
    )

    if selection == "forward":
        print("  Running forward selection for pass...")
        train_pass_sub = train_df[train_df["action_type"] == "pass"]
        selected, sel_log = run_forward_selection(
            train_pass_sub, list(pass_features), target_col, seed=args.seed
        )
        selection_logs["pass"] = sel_log
        pass_features = selected
        print(f"    Selected {len(selected)} features (R²={sel_log['final_r2']})")

    print("  Training pass OLS model...")
    pass_model = train_pass_model(
        train_df,
        val_df,
        state_feature_names=pass_features,
        target_col=target_col,
    )
    print(
        f"    R²={pass_model['r_squared']:.4f}, "
        f"MAE={pass_model['mae']:.3f}, "
        f"n_train={pass_model['n_train']}"
    )

    artifact = build_two_stage_artifact(
        suit_result,
        models_ols["high"],
        models_ols["low"],
        pass_model,
        args.seed,
        n_deals,
        args.continuation_artifact,
        feature_set=args.feature_set,
        target_col=target_col,
        dataset_path=args.dataset,
        dataset_sha256=dataset_sha,
        continuation_artifact_sha256=cont_sha,
    )

    # Record selection metadata
    if selection != "none":
        artifact["metadata"]["selection"] = selection
        artifact["metadata"]["selection_logs"] = selection_logs

    # Gate X2 for high/low/pass (suit uses composite R² instead)
    if not args.skip_validation:
        print("  Running Gate X2 validation (high/low/pass)...")
        for family in ("high", "low"):
            r2 = models_ols[family]["r_squared"]
            threshold = GATE_X2_THRESHOLDS[family]
            assert r2 > threshold, f"Gate X2 FAIL: {family} R²={r2:.4f} <= {threshold}"
        r2_pass = pass_model["r_squared"]
        threshold_pass = GATE_X2_THRESHOLDS["pass"]
        assert (
            r2_pass > threshold_pass
        ), f"Gate X2 FAIL: pass R²={r2_pass:.4f} <= {threshold_pass}"
        # Suit uses composite R² with same threshold
        r2_suit = suit_result["composite_r_squared"]
        threshold_suit = GATE_X2_THRESHOLDS["suit"]
        assert (
            r2_suit > threshold_suit
        ), f"Gate X2 FAIL: suit composite R²={r2_suit:.4f} <= {threshold_suit}"
        print(
            f"  Gate X2 PASS: "
            f"suit composite R²={r2_suit:.4f}, "
            f"high R²={models_ols['high']['r_squared']:.4f}, "
            f"low R²={models_ols['low']['r_squared']:.4f}, "
            f"pass R²={pass_model['r_squared']:.4f}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "action_value_two_stage.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))

    if not args.skip_validation:
        print("  Running behavioral validation...")
        report = _run_behavioral_validation(str(artifact_path))

        print("  Freezing artifact with provenance...")
        from bid_euchre.models.freeze import freeze_with_provenance

        provenance = {
            "behavioral_validation": _build_behavioral_provenance(report),
        }
        frozen = freeze_with_provenance(str(artifact_path), provenance)
        print(f"    artifact_sha256={frozen['artifact_sha256'][:12]}...")

    print(f"\n  Artifact: {artifact_path}")
    print("  Done.")


if __name__ == "__main__":
    main()
