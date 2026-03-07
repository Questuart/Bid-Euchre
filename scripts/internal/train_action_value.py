"""
R1.5 action-value OLS training pipeline.

Trains per-contract OLS models on counterfactual net_points data and
produces action_value_olsa_v1 artifacts for ActionValueBidder.

Four models:
  suit:  net_points ~ 52 state features + bid_n + bid_n_sq
  high:  net_points ~ 52 state features + bid_n + bid_n_sq
  low:   net_points ~ 52 state features + bid_n + bid_n_sq
  pass:  net_points ~ 52 state features (no action features)

CLI usage:
    uv run python scripts/internal/train_action_value.py \\
        --seed 42 \\
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

# Gate X2 R² thresholds per contract family
GATE_X2_THRESHOLDS = {
    "suit": 0.05,
    "high": 0.05,
    "low": 0.05,
    "pass": 0.02,
}


# ── Data Loading ─────────────────────────────────────────────


def load_dataset(parquet_path: str) -> pd.DataFrame:
    """Load and validate the action-value parquet dataset."""
    df = pd.read_parquet(parquet_path)

    # Validate required columns
    required = set(METADATA_COLS) | set(STATE_FEATURE_NAMES) | {TARGET_COL}
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
) -> dict:
    """Train OLS for one contract family (suit/high/low).

    Features: 52 state + bid_n + bid_n_sq = 54 columns.
    Target: net_points.
    """
    feature_names = STATE_FEATURE_NAMES + ACTION_FEATURE_NAMES

    # Filter to this contract family
    train_sub = train_df[train_df["contract_family"] == family]
    val_sub = val_df[val_df["contract_family"] == family]

    if len(train_sub) == 0:
        raise ValueError(f"No training rows for family '{family}'")

    # Build feature matrices — bid_n is already in the dataset,
    # bid_n_sq needs to be computed
    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[TARGET_COL].values

    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[TARGET_COL].values

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
) -> dict:
    """Train OLS for pass action.

    Features: 52 state columns only (no action features).
    Target: net_points.
    """
    feature_names = STATE_FEATURE_NAMES

    # Filter to pass rows
    train_sub = train_df[train_df["action_type"] == "pass"]
    val_sub = val_df[val_df["action_type"] == "pass"]

    if len(train_sub) == 0:
        raise ValueError("No training rows for pass action")

    X_train = _build_feature_matrix(train_sub, feature_names)
    y_train = train_sub[TARGET_COL].values

    X_val = _build_feature_matrix(val_sub, feature_names)
    y_val = val_sub[TARGET_COL].values

    # Fit OLS
    weights, bias = _fit_ols(X_train, y_train)

    # Compute metrics on validation set
    y_pred_val = X_val @ weights + bias
    metrics = _compute_metrics(y_val, y_pred_val)

    return {
        "coefficients": weights.tolist(),
        "intercept": float(bias),
        "feature_names": list(feature_names),
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
) -> dict:
    """Assemble the action_value_olsa_v1 artifact dict."""
    git_sha = _git_sha()

    return {
        "schema_version": "action_value_olsa_v1",
        "target": "net_points",
        "risk_mode": "neutral",
        "continuation_policy": Path(continuation_artifact).stem,
        "action_features": list(ACTION_FEATURE_NAMES),
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
    args = parser.parse_args()

    print("=== R1.5 Action-Value Training Pipeline ===")
    print(f"  Seed: {args.seed}")
    print(f"  Dataset: {args.dataset}")

    # Load dataset
    print("  Loading dataset...")
    df = load_dataset(args.dataset)
    n_deals = df["deal_id"].nunique()
    print(f"  Loaded {len(df)} rows, {n_deals} deals")

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
        models[family] = train_family_model(train_df, val_df, family)
        print(
            f"    R²={models[family]['r_squared']:.4f}, "
            f"MAE={models[family]['mae']:.3f}, "
            f"n_train={models[family]['n_train']}"
        )

    # Train pass model
    print("  Training pass model...")
    models["pass"] = train_pass_model(train_df, val_df)
    print(
        f"    R²={models['pass']['r_squared']:.4f}, "
        f"MAE={models['pass']['mae']:.3f}, "
        f"n_train={models['pass']['n_train']}"
    )

    # Build artifact
    artifact = build_artifact(models, args.seed, n_deals, args.continuation_artifact)

    # Validate
    if not args.skip_validation:
        print("  Running Gate X2 validation...")
        validate_gate_x2(artifact)

    # Write output
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "action_value_full.json"
    artifact_path.write_text(json.dumps(artifact, indent=2))

    print(f"\n  Artifact: {artifact_path}")
    print("  Done.")


if __name__ == "__main__":
    main()
