"""
R1.5 action-value OLS training pipeline.

Trains per-contract OLS models on counterfactual action-value data and
produces action_value_olsa_v1 artifacts for ActionValueBidder.

Four models:
  suit:  target ~ state features + bid_n + bid_n_sq
  high:  target ~ state features + bid_n + bid_n_sq
  low:   target ~ state features + bid_n + bid_n_sq
  pass:  target ~ state features (no action features)

Ablation parameters:
  --feature-set: "full" (52 state features) or "r0" (39 R0 hand features only)
  --target: "net_points" (default) or "tricks_won"

CLI usage:
    uv run python scripts/internal/train_action_value.py \\
        --seed 42 \\
        --dataset data/runs/action_value_smoke_42/datasets/action_value.parquet \\
        --output-dir data/runs/action_value_smoke_42 \\
        --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

    # R0-only features ablation:
    uv run python scripts/internal/train_action_value.py \\
        --seed 42 --feature-set r0 \\
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

# Named feature sets for ablation experiments
FEATURE_SETS: dict[str, list[str]] = {
    "full": list(STATE_FEATURE_NAMES),  # 52 state features
    "r0": list(STATE_FEATURE_NAMES[:_N_R0_HAND_FEATURES]),  # 39 R0 hand features only
    "no-partner": list(
        STATE_FEATURE_NAMES
    ),  # 52 features, partner cols zeroed at training
}

# Feature sets that require zero-masking specific columns at training time.
# The model artifact retains all feature names (passes ActionValueBidder validation)
# but OLS learns zero coefficients for zeroed columns.
_ZERO_MASK_COLUMNS: dict[str, list[str]] = {
    "no-partner": _PARTNER_FEATURE_NAMES,
}

VALID_TARGETS = ("net_points", "tricks_won")

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

    # Validate required columns
    required = set(METADATA_COLS) | set(state_feature_names) | {target_col}
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
    """Extract feature matrix from dataframe, computing bid_n_sq if needed."""
    cols = []
    for name in feature_names:
        if name == "bid_n_sq":
            cols.append(df["bid_n"].values ** 2)
        else:
            cols.append(df[name].values)
    return np.column_stack(cols).astype(np.float64)


# ── Artifact ─────────────────────────────────────────────────


def build_artifact(
    models: dict[str, dict],
    seed: int,
    n_deals: int,
    continuation_artifact: str,
    feature_set: str = "full",
    target_col: str = TARGET_COL,
) -> dict:
    """Assemble the action_value_olsa_v1 artifact dict.

    Args:
        feature_set: Name of the feature set used ("full" or "r0").
        target_col: Name of the target column used for training.
    """
    git_sha = _git_sha()

    return {
        "schema_version": "action_value_olsa_v1",
        "target": target_col,
        "risk_mode": "neutral",
        "continuation_policy": Path(continuation_artifact).stem,
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": feature_set,
        "models": models,
        "metadata": {
            "n_deals": n_deals,
            "training_seed": seed,
            "arm": "full",
            "context_features": [],
            "git_sha": git_sha,
            "created_at_utc": utc_now_iso(),
        },
    }


def _git_sha() -> str:
    """Get current git HEAD SHA."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


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


def main():
    parser = argparse.ArgumentParser(
        description="Train action-value OLS models for R1.5"
    )
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
        help="Feature set: 'full' (52 state), 'r0' (39 hand), 'no-partner' (52 state, partner cols zeroed)",
    )
    parser.add_argument(
        "--target",
        choices=list(VALID_TARGETS),
        default="net_points",
        help="Target column: 'net_points' (default) or 'tricks_won'",
    )
    args = parser.parse_args()

    state_feature_names = FEATURE_SETS[args.feature_set]
    target_col = args.target

    print("=== R1.5 Action-Value Training Pipeline ===")
    print(f"  Seed: {args.seed}")
    print(f"  Dataset: {args.dataset}")
    print(
        f"  Feature set: {args.feature_set} ({len(state_feature_names)} state features)"
    )
    print(f"  Target: {target_col}")

    # Load dataset
    print("  Loading dataset...")
    df = load_dataset(
        args.dataset,
        target_col=target_col,
        state_feature_names=state_feature_names,
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

    # Train per-family models
    models = {}
    for family in ("suit", "high", "low"):
        print(f"  Training {family} model...")
        models[family] = train_family_model(
            train_df,
            val_df,
            family,
            state_feature_names=state_feature_names,
            target_col=target_col,
        )
        print(
            f"    R²={models[family]['r_squared']:.4f}, "
            f"MAE={models[family]['mae']:.3f}, "
            f"n_train={models[family]['n_train']}"
        )

    # Train pass model
    print("  Training pass model...")
    models["pass"] = train_pass_model(
        train_df,
        val_df,
        state_feature_names=state_feature_names,
        target_col=target_col,
    )
    print(
        f"    R²={models['pass']['r_squared']:.4f}, "
        f"MAE={models['pass']['mae']:.3f}, "
        f"n_train={models['pass']['n_train']}"
    )

    # Build artifact
    artifact = build_artifact(
        models,
        args.seed,
        n_deals,
        args.continuation_artifact,
        feature_set=args.feature_set,
        target_col=target_col,
    )

    # Validate
    if not args.skip_validation:
        print("  Running Gate X2 validation...")
        validate_gate_x2(artifact)

    # Write output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / _artifact_filename(args.feature_set)
    artifact_path.write_text(json.dumps(artifact, indent=2))

    print(f"\n  Artifact: {artifact_path}")
    print("  Done.")


if __name__ == "__main__":
    main()
