#!/usr/bin/env python
"""
OLSa training pipeline: per-contract sparse OLS on tricks_won.

Trains 3 separate OLS models with sparse features:
  suit: tricks_won ~ intercept + bowers + trump_count + offsuit_aces
  high: tricks_won ~ intercept + offsuit_aces
  low:  tricks_won ~ intercept + offsuit_tens_count

Uses normal equation with lstsq fallback for robustness.

CLI usage (preferred):
    PYTHONPATH=src python scripts/train_olsa.py \
        --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
        --seed 42 --output /tmp/olsa_artifacts/
"""

import json
import logging
import os
import subprocess
from datetime import datetime, timezone

import numpy as np

from ..datasets.join import join_features_outcomes
from .splits import create_grouped_split

logger = logging.getLogger(__name__)

# Per-contract feature specs
CONTRACT_FEATURES = {
    "suit": ["bowers", "trump_count", "offsuit_aces"],
    "high": ["offsuit_aces"],
    "low": ["offsuit_tens_count"],
}


def _grouped_train_test_split(df, seed, train_frac=0.8):
    """Split by hand_id to prevent leakage."""
    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)
    split_idx = int(len(unique_ids) * train_frac)
    train_ids = set(unique_ids[:split_idx])
    train_mask = df["hand_id"].isin(train_ids)
    return df[train_mask], df[~train_mask]


def _fit_ols(X, y):
    """
    Fit OLS with intercept using normal equation.

    Falls back to lstsq on LinAlgError or ill-conditioning.
    Returns (weights, bias) where weights excludes intercept.
    """
    X_with_intercept = np.column_stack([np.ones(len(X)), X])
    XtX = X_with_intercept.T @ X_with_intercept
    Xty = X_with_intercept.T @ y

    try:
        beta = np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError:
        logger.warning("Normal equation failed, falling back to lstsq")
        beta, _, _, _ = np.linalg.lstsq(X_with_intercept, y, rcond=None)

    return beta[1:], beta[0]  # weights, bias


def _compute_metrics(y_true, y_pred):
    """Compute R² and MAE."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    mae = np.mean(np.abs(y_true - y_pred))
    return {"r2": float(r2), "mae": float(mae)}


def train_olsa(run_dir, seed, split_manifest_dir=None, split_type="two_way"):
    """
    Train OLSa models from a canonical bidless run directory.

    Args:
        run_dir: Path to canonical bidless run.
        seed: Random seed for splitting and reproducibility.
        split_manifest_dir: If given, write split_manifest.json per contract here.
        split_type: "two_way" or "three_way" (three_way required for promotion).

    Returns the artifact dict and per-contract metrics.
    """
    bidless_path = os.path.join(run_dir, "datasets", "bidless.parquet")
    outcomes_path = os.path.join(run_dir, "datasets", "bidless_outcomes.parquet")

    if not os.path.exists(bidless_path):
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not os.path.exists(outcomes_path):
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    logger.info("Loading data from %s", run_dir)
    df = join_features_outcomes(bidless_path, outcomes_path)
    logger.info("Joined: %d rows", len(df))

    source_run_id = os.path.basename(run_dir)

    models = {}
    training_metrics = {}

    for contract_family, feature_names in CONTRACT_FEATURES.items():
        # Filter to matching contract_type
        sub = df[df["contract_type"] == contract_family]
        if len(sub) == 0:
            logger.warning("No data for contract_type=%s, skipping", contract_family)
            continue

        train_df, val_df, test_df, manifest = create_grouped_split(
            sub, seed,
            source_run_id=source_run_id,
            source_parquet_path=bidless_path,
            split_type=split_type,
        )

        # Persist manifest if requested
        if split_manifest_dir:
            manifest_path = os.path.join(
                split_manifest_dir, f"split_manifest_{contract_family}.json"
            )
            manifest.save(manifest_path)
            logger.info("  Split manifest: %s", manifest_path)

        X_train = train_df[feature_names].values.astype(np.float64)
        y_train = train_df["tricks_won"].values.astype(np.float64)
        X_test = test_df[feature_names].values.astype(np.float64)
        y_test = test_df["tricks_won"].values.astype(np.float64)

        weights, bias = _fit_ols(X_train, y_train)

        # Evaluate
        y_pred_train = X_train @ weights + bias
        y_pred_test = X_test @ weights + bias

        metrics_train = _compute_metrics(y_train, y_pred_train)
        metrics_test = _compute_metrics(y_test, y_pred_test)

        models[contract_family] = {
            "weights": [float(w) for w in weights],
            "bias": float(bias),
            "feature_names": feature_names,
        }

        training_metrics[contract_family] = {
            "r2_train": metrics_train["r2"],
            "r2_test": metrics_test["r2"],
            "mae_train": metrics_train["mae"],
            "mae_test": metrics_test["mae"],
            "n_train": len(train_df),
            "n_test": len(test_df),
        }

        logger.info(
            "  %s: R²=%.4f (test), MAE=%.4f, weights=%s, bias=%.4f",
            contract_family,
            metrics_test["r2"],
            metrics_test["mae"],
            [f"{w:.4f}" for w in weights],
            bias,
        )

    # Get git SHA
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_sha = "unknown"

    artifact = {
        "schema_version": "1",
        "artifact_type": "olsa_v1",
        "models": models,
        "metadata": {
            "training_seed": seed,
            "canonical_run_id": os.path.basename(run_dir),
            "git_sha": git_sha,
            "training_timestamp": datetime.now(timezone.utc).isoformat(),
            "training_metrics": training_metrics,
        },
    }

    return artifact, training_metrics


def save_artifacts(artifact, training_metrics, output_dir):
    """Save OLSa artifact and summary to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    # Save artifact
    artifact_path = os.path.join(output_dir, "olsa_v1.json")
    with open(artifact_path, "w") as f:
        json.dump(artifact, f, indent=2)
    logger.info("Artifact saved to %s", artifact_path)

    # Save training metrics
    metrics_path = os.path.join(output_dir, "training_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(training_metrics, f, indent=2)

    # Save human-readable summary
    summary_path = os.path.join(output_dir, "training_summary.md")
    lines = [
        "# OLSa Training Summary",
        "",
        f"- **Seed:** {artifact['metadata']['training_seed']}",
        f"- **Source:** {artifact['metadata']['canonical_run_id']}",
        f"- **Git SHA:** {artifact['metadata']['git_sha']}",
        f"- **Timestamp:** {artifact['metadata']['training_timestamp']}",
        "",
        "## Per-Contract Results",
        "",
        "| Contract | R² (test) | MAE (test) | N (test) | Weights | Bias |",
        "|----------|-----------|------------|----------|---------|------|",
    ]
    for cf, model in artifact["models"].items():
        m = training_metrics[cf]
        weights_str = ", ".join(f"{w:.4f}" for w in model["weights"])
        lines.append(
            f"| {cf} | {m['r2_test']:.4f} | {m['mae_test']:.4f} | "
            f"{m['n_test']:,} | [{weights_str}] | {model['bias']:.4f} |"
        )
    lines.append("")
    lines.append("## Feature Specs")
    lines.append("")
    for cf, model in artifact["models"].items():
        lines.append(f"- **{cf}:** {', '.join(model['feature_names'])}")
    lines.append("")

    with open(summary_path, "w") as f:
        f.write("\n".join(lines))

    return artifact_path


if __name__ == "__main__":
    import argparse
    import warnings

    warnings.warn(
        "Direct execution of this module is deprecated. "
        "Use: PYTHONPATH=src python scripts/train_olsa.py",
        DeprecationWarning,
        stacklevel=1,
    )

    parser = argparse.ArgumentParser(description="Train OLSa models")
    parser.add_argument("--run-dir", required=True, help="Canonical bidless run directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True, help="Output directory for artifacts")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    artifact, metrics = train_olsa(args.run_dir, args.seed)
    artifact_path = save_artifacts(artifact, metrics, args.output)
    print(f"\nOLSa artifact: {artifact_path}")
