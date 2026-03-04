#!/usr/bin/env python
"""
Train a unified cross-contract OLS model for Track F (OneModel protocol).

Pools all contract types (suit, high, low) into a single regression with
contract-type indicator variables (is_high, is_low; suit is reference).
Trump-specific features are masked to 0 for high/low contracts (already
the case in the feature extraction pipeline).

The unified model's coefficients are decomposed into per-contract-family
format that is loader-compatible with HybridOLSaBidder — no loader changes
needed.

Usage:
    uv run python scripts/internal/train_unified_model.py \
        --dataset-dir data/runs/canonical_bidless_dataset_glutton_42_20260221_175752 \
        --output data/artifacts/arc_d/r0/hybrid_r0_unified.json \
        --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from bid_euchre.datasets.join import join_features_outcomes
from bid_euchre.models.feature_selection import forward_select
from bid_euchre.models.freeze import freeze_artifact
from bid_euchre.models.train_olsa import _compute_metrics, _fit_ols

logger = logging.getLogger(__name__)

# Trump-specific features that are already 0 for high/low contracts
# (set by the feature extraction pipeline in hand_eval.py)
TRUMP_FEATURES = frozenset(
    {
        "bowers",
        "trump_count",
        "trump_rb_count",
        "trump_lb_count",
        "trump_ace_count",
        "trump_king_count",
        "trump_queen_count",
        "trump_ten_count",
        "highest_trump_rank",
        "second_highest_trump_rank",
        "third_highest_trump_rank",
        "trump_power_sum",
        "trump_duplicate_pairs",
        "trump_count_x_void_count",
        "trump_count_x_offsuit_ace",
    }
)

# Non-feature columns from the joined DataFrame
_NON_FEATURE_COLS = frozenset(
    {
        "hand_id",
        "seat",
        "dealer_seat",
        "deal_id",
        "contract_type",
        "trump_suit",
        "hand_cards",
        "hand_features",
        "hand_feature_schema_version",
        "tricks_won",
        "tricks_team0",
        "tricks_team1",
        "team0_win",
        "strategy_id",
        "play_strategy_id",
        "declaring",
        # Unified model indicator columns (added by us, not base features)
        "is_high",
        "is_low",
    }
)


def _get_all_feature_names(df: pd.DataFrame) -> list[str]:
    """Extract hand feature column names from the joined DataFrame."""
    numeric_cols = set(df.select_dtypes(include="number").columns)
    return sorted(
        c for c in df.columns if c not in _NON_FEATURE_COLS and c in numeric_cols
    )


def _deal_partition(deal_id: str, seed: int = 42) -> str:
    """Deterministic deal partition using protocol-specified hash.

    Protocol §2.3: hash = SHA256(f"{deal_id}:{seed}"), bucket = int(h[:8], 16) % 5
    Train if bucket < 3, else val.
    """
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"


def _git_sha() -> str:
    """Get current git HEAD SHA."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def train_unified_model(
    dataset_dir: str,
    output_path: str,
    seed: int = 42,
    max_features: int | None = None,
    min_improvement: float = 0.005,
    risk_lambda: float = 0.0,
    freeze: bool = True,
) -> dict:
    """Train a unified cross-contract OLS model.

    Args:
        dataset_dir: Path to canonical bidless dataset directory.
        output_path: Path to write the output artifact JSON.
        seed: Random seed for splitting and feature selection.
        max_features: Max features for forward selection (None = no limit).
        min_improvement: Min R² improvement for forward selection steps.
        risk_lambda: Risk penalty coefficient.
        freeze: Whether to freeze the artifact after writing.

    Returns:
        Dict with training summary including metrics and artifact path.
    """
    bidless_path = os.path.join(dataset_dir, "datasets", "bidless.parquet")
    outcomes_path = os.path.join(dataset_dir, "datasets", "bidless_outcomes.parquet")

    if not os.path.exists(bidless_path):
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not os.path.exists(outcomes_path):
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    logger.info("Loading data from %s", dataset_dir)
    df = join_features_outcomes(bidless_path, outcomes_path)
    logger.info("Joined: %d rows", len(df))

    # --- Data composition ---
    ct_counts = df["contract_type"].value_counts()
    logger.info("Contract type distribution:")
    for ct, count in ct_counts.items():
        logger.info("  %s: %d (%.1f%%)", ct, count, 100 * count / len(df))

    # --- Add contract-type indicators ---
    df["is_high"] = (df["contract_type"] == "high").astype(np.float64)
    df["is_low"] = (df["contract_type"] == "low").astype(np.float64)

    # --- Train/val split by deal_id using protocol-specified hash ---
    logger.info("Partitioning by deal_id (seed=%d)...", seed)
    deal_ids = df["deal_id"].unique()
    partitions = {did: _deal_partition(str(did), seed) for did in deal_ids}
    df["_partition"] = df["deal_id"].map(partitions)

    train_df = df[df["_partition"] == "train"].copy()
    val_df = df[df["_partition"] == "val"].copy()

    n_train_deals = train_df["deal_id"].nunique()
    n_val_deals = val_df["deal_id"].nunique()
    logger.info(
        "Split: %d train rows (%d deals), %d val rows (%d deals)",
        len(train_df),
        n_train_deals,
        len(val_df),
        n_val_deals,
    )

    # --- Feature selection ---
    base_features = _get_all_feature_names(train_df)
    # Add indicator features to the candidate set
    all_features = base_features + ["is_high", "is_low"]

    logger.info("Candidate features: %d (including 2 indicators)", len(all_features))

    X_train_all = train_df[all_features].values.astype(np.float64)
    y_train = train_df["tricks_won"].values.astype(np.float64)

    # GroupKFold by deal_id to prevent seat-level leakage
    groups = train_df["deal_id"].values

    logger.info("Running forward feature selection (grouped by deal_id)...")
    selected_names, fs_log = forward_select(
        X_train_all,
        y_train,
        candidate_names=all_features,
        groups=groups,
        max_features=max_features,
        min_improvement=min_improvement,
        seed=seed,
    )

    logger.info("Selected %d features: %s", len(selected_names), selected_names)

    # --- Fit unified OLS on selected features ---
    X_train = train_df[selected_names].values.astype(np.float64)
    X_val = val_df[selected_names].values.astype(np.float64)
    y_val = val_df["tricks_won"].values.astype(np.float64)

    weights, bias = _fit_ols(X_train, y_train)

    # --- Compute metrics ---
    y_pred_train = X_train @ weights + bias
    y_pred_val = X_val @ weights + bias

    metrics_train = _compute_metrics(y_train, y_pred_train)
    metrics_val = _compute_metrics(y_val, y_pred_val)

    logger.info(
        "Unified model: R²_train=%.4f, R²_val=%.4f",
        metrics_train["r2"],
        metrics_val["r2"],
    )
    logger.info(
        "Unified model: MAE_train=%.4f, MAE_val=%.4f",
        metrics_train["mae"],
        metrics_val["mae"],
    )

    # --- Per-contract residual variance (from training data) ---
    residual_variances = {}
    per_contract_metrics = {}

    for contract_family in ["suit", "high", "low"]:
        mask = train_df["contract_type"] == contract_family
        X_cf = train_df.loc[mask, selected_names].values.astype(np.float64)
        y_cf = train_df.loc[mask, "tricks_won"].values.astype(np.float64)
        y_pred_cf = X_cf @ weights + bias
        residuals = y_cf - y_pred_cf
        resid_var = float(np.var(residuals))

        # Runtime guard
        if not (0 < resid_var < 25):
            raise ValueError(
                f"Residual variance out of bounds for {contract_family}: "
                f"{resid_var:.4f} (expected 0 < sigma^2 < 25)"
            )

        residual_variances[contract_family] = resid_var

        # Per-contract validation metrics
        val_mask = val_df["contract_type"] == contract_family
        X_val_cf = val_df.loc[val_mask, selected_names].values.astype(np.float64)
        y_val_cf = val_df.loc[val_mask, "tricks_won"].values.astype(np.float64)
        y_pred_val_cf = X_val_cf @ weights + bias
        val_metrics_cf = _compute_metrics(y_val_cf, y_pred_val_cf)

        per_contract_metrics[contract_family] = {
            "n_train": int(mask.sum()),
            "n_val": int(val_mask.sum()),
            "r2_train": float(_compute_metrics(y_cf, y_pred_cf)["r2"]),
            "r2_val": float(val_metrics_cf["r2"]),
            "mae_train": float(_compute_metrics(y_cf, y_pred_cf)["mae"]),
            "mae_val": float(val_metrics_cf["mae"]),
            "residual_variance": resid_var,
        }

        logger.info(
            "  %s: R²_train=%.4f, R²_val=%.4f, sigma²=%.4f (n_train=%d, n_val=%d)",
            contract_family,
            per_contract_metrics[contract_family]["r2_train"],
            per_contract_metrics[contract_family]["r2_val"],
            resid_var,
            per_contract_metrics[contract_family]["n_train"],
            per_contract_metrics[contract_family]["n_val"],
        )

    # --- Decompose unified coefficients into per-family format ---
    # Build coefficient dict for easy lookup
    coeff_dict = {name: float(w) for name, w in zip(selected_names, weights)}
    unified_intercept = float(bias)

    logger.info("Unified intercept: %.6f", unified_intercept)
    logger.info("Unified coefficients:")
    for name, w in sorted(coeff_dict.items(), key=lambda x: abs(x[1]), reverse=True):
        logger.info("  %s: %.6f", name, w)

    # Per-family decomposition:
    # - suit: bias = intercept (is_high=0, is_low=0), weights = base feature coefficients
    # - high: bias = intercept + w_is_high, weights = base feature coefficients
    # - low:  bias = intercept + w_is_low, weights = base feature coefficients
    w_is_high = coeff_dict.pop("is_high", 0.0)
    w_is_low = coeff_dict.pop("is_low", 0.0)

    # Base feature names (excluding indicators)
    base_feature_names = [n for n in selected_names if n not in ("is_high", "is_low")]
    base_weights = [coeff_dict[n] for n in base_feature_names]

    payoff_model = {
        "suit": {
            "weights": base_weights,
            "bias": unified_intercept,
            "feature_names": base_feature_names,
        },
        "high": {
            "weights": base_weights,
            "bias": unified_intercept + w_is_high,
            "feature_names": base_feature_names,
        },
        "low": {
            "weights": base_weights,
            "bias": unified_intercept + w_is_low,
            "feature_names": base_feature_names,
        },
    }

    logger.info(
        "Decomposed biases: suit=%.6f, high=%.6f, low=%.6f",
        payoff_model["suit"]["bias"],
        payoff_model["high"]["bias"],
        payoff_model["low"]["bias"],
    )

    # --- Build artifact ---
    source_run_id = os.path.basename(dataset_dir)

    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "model_type": "unified",
        "schema_version": 1,
        "rung_id": "r0",
        "payoff_model": payoff_model,
        "residual_variance": residual_variances,
        "risk_lambda": risk_lambda,
        "context_features": [],
        "training_seed": seed,
        "training_run_id": source_run_id,
        "split_type": "hash_deal_id",
        "training_info": {
            "description": "Unified cross-contract OLS, decomposed to per-family format",
            "protocol": "r0_v2_onemodel_protocol.md",
            "unified_intercept": unified_intercept,
            "unified_coefficients": {
                **{n: float(w) for n, w in zip(base_feature_names, base_weights)},
                "is_high": w_is_high,
                "is_low": w_is_low,
            },
            "selected_features": selected_names,
            "feature_selection_log": fs_log,
            "per_contract_metrics": per_contract_metrics,
            "overall_metrics": {
                "r2_train": metrics_train["r2"],
                "r2_val": metrics_val["r2"],
                "mae_train": metrics_train["mae"],
                "mae_val": metrics_val["mae"],
                "n_train": len(train_df),
                "n_val": len(val_df),
                "n_train_deals": n_train_deals,
                "n_val_deals": n_val_deals,
            },
            "data_composition": {ct: int(count) for ct, count in ct_counts.items()},
            "git_sha": _git_sha(),
            "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "frozen_at": None,
        "artifact_sha256": None,
    }

    # --- Write artifact ---
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)

    logger.info("Artifact written to %s", output_path)

    if freeze:
        freeze_artifact(output_path)
        logger.info("Artifact frozen.")

    return {
        "artifact_path": output_path,
        "selected_features": selected_names,
        "feature_selection_log": fs_log,
        "unified_intercept": unified_intercept,
        "unified_coefficients": coeff_dict,
        "w_is_high": w_is_high,
        "w_is_low": w_is_low,
        "metrics_train": metrics_train,
        "metrics_val": metrics_val,
        "per_contract_metrics": per_contract_metrics,
        "residual_variances": residual_variances,
        "n_train": len(train_df),
        "n_val": len(val_df),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Train unified cross-contract OLS model (Track F)"
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Path to canonical bidless dataset directory",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output artifact JSON path",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--max-features",
        type=int,
        default=None,
        help="Max features for forward selection (default: no limit)",
    )
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=0.005,
        help="Min R² improvement for forward selection (default: 0.005)",
    )
    parser.add_argument(
        "--risk-lambda",
        type=float,
        default=0.0,
        help="Risk penalty coefficient (default: 0.0)",
    )
    parser.add_argument(
        "--no-freeze",
        action="store_true",
        help="Skip freezing the artifact",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    result = train_unified_model(
        dataset_dir=args.dataset_dir,
        output_path=args.output,
        seed=args.seed,
        max_features=args.max_features,
        min_improvement=args.min_improvement,
        risk_lambda=args.risk_lambda,
        freeze=not args.no_freeze,
    )

    print("\n" + "=" * 60)
    print("UNIFIED MODEL TRAINING SUMMARY")
    print("=" * 60)
    print(f"Features selected: {len(result['selected_features'])}")
    print(f"  {result['selected_features']}")
    print(f"Intercept: {result['unified_intercept']:.6f}")
    print(f"is_high coefficient: {result['w_is_high']:.6f}")
    print(f"is_low coefficient: {result['w_is_low']:.6f}")
    print(f"Overall R² (train): {result['metrics_train']['r2']:.4f}")
    print(f"Overall R² (val):   {result['metrics_val']['r2']:.4f}")
    print(f"Overall MAE (train): {result['metrics_train']['mae']:.4f}")
    print(f"Overall MAE (val):   {result['metrics_val']['mae']:.4f}")
    print()
    print("Per-contract metrics:")
    for cf, m in result["per_contract_metrics"].items():
        print(
            f"  {cf}: R²_train={m['r2_train']:.4f}, R²_val={m['r2_val']:.4f}, "
            f"σ²={m['residual_variance']:.4f}"
        )
    print()
    print("Residual variances:")
    for cf, rv in result["residual_variances"].items():
        print(f"  {cf}: {rv:.4f}")
    print()
    print(f"Artifact: {result['artifact_path']}")


if __name__ == "__main__":
    main()
