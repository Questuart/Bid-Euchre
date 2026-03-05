#!/usr/bin/env python
"""
Threshold sweep CLI: grid search over pass_threshold values.

Loads a model artifact and evaluation dataset, applies deal_partition
for train/val split, evaluates each threshold on the grid, selects
the best threshold from train, and validates on val.

Output: JSON artifact with grid results + selected threshold + validation metrics.

Usage:
    uv run python scripts/internal/run_threshold_sweep.py \
        --artifact-path data/artifacts/arc_d/r1/hybrid_r1_full.json \
        --data data/runs/canonical_auction_r1_42 \
        --grid "0.0,0.1,0.2,0.5,1.0,2.0,5.0" \
        --seed 42 \
        --output data/artifacts/arc_d/r1/threshold_sweep_r1.json
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from bid_euchre.analysis.sweep import compute_ev_vectorized, deal_partition
from bid_euchre.datasets.join import join_features_outcomes


def load_model_artifact(artifact_path):
    """Load and validate an OLSa/Hybrid model artifact.

    Normalizes artifact structure: hybrid artifacts use 'payoff_model'
    and top-level 'residual_variance'; this extracts per-family models
    with attached sigma (sqrt of residual variance).
    """
    with open(artifact_path) as f:
        artifact = json.load(f)

    artifact_type = artifact.get("artifact_type", "")
    if artifact_type not in ("olsa_v1", "hybrid_olsa_v1"):
        print(f"WARNING: Unexpected artifact_type={artifact_type!r}", file=sys.stderr)

    # Normalize: hybrid artifacts store models under 'payoff_model',
    # non-hybrid under 'models'. Extract to uniform 'models' dict.
    if "payoff_model" in artifact and "models" not in artifact:
        residual_variance = artifact.get("residual_variance", {})
        models = {}
        for cf, model in artifact["payoff_model"].items():
            model_copy = dict(model)
            # Compute sigma from residual_variance (matches HybridOLSaBidder._sigma).
            # Off/def artifacts store {"offensive": ..., "defensive": ...} per cf;
            # flat artifacts store a single float. Use offensive (declaring) for
            # threshold tuning since the bidder is choosing whether to declare.
            var = residual_variance.get(cf, 0.0)
            if isinstance(var, dict):
                var = var.get("offensive", 0.0)
            model_copy["sigma"] = math.sqrt(max(0.0, var))
            models[cf] = model_copy
        artifact["models"] = models

    return artifact


def predict_tricks(model, feature_names, df):
    """Predict tricks for a contract family using OLS weights.

    Returns mu (predicted tricks) as numpy array.
    """
    weights = np.array(model["weights"], dtype=np.float64)
    bias = float(model["bias"])
    X = df[feature_names].values.astype(np.float64)
    return X @ weights + bias


def evaluate_threshold(df, mu, sigma, threshold):
    """Evaluate a threshold value on the dataset.

    For each row, compute best_bid EV and check if EV > -threshold.
    Returns dict with net_eppd, bid_rate, make_rate, n_bid_hands.
    """
    # Bid level search: for each hand, find the best bid_n where EV > -threshold
    bid_n_best = np.zeros(len(mu), dtype=int)
    ev_best = np.full(len(mu), -np.inf)

    current_high_bid = 0  # Self-play: no prior bids
    for n in range(max(1, current_high_bid + 1), 11):
        ev_n = compute_ev_vectorized(mu, sigma, np.full(len(mu), n))
        better = ev_n > ev_best
        bid_n_best = np.where(better, n, bid_n_best)
        ev_best = np.where(better, ev_n, ev_best)

    # Apply threshold: bid if EV > -threshold
    would_bid = ev_best > -threshold
    n_total = len(df)
    n_bid = int(would_bid.sum())

    if n_bid == 0:
        return {
            "net_eppd": 0.0,
            "bid_rate": 0.0,
            "make_rate": 0.0,
            "n_bid_hands": 0,
            "n_total": n_total,
        }

    # For bidding hands, compute outcomes
    tricks_won = df["tricks_won"].values
    bid_levels = bid_n_best[would_bid]
    tricks_bid = tricks_won[would_bid]
    made = tricks_bid >= bid_levels

    # Bidder points: tricks_won if made, -bid if set
    bidder_pts = np.where(made, tricks_bid, -bid_levels.astype(float))
    # Opponent always gets their tricks (10 - tricks_won for bidder's team)
    opponent_tricks = 10.0 - tricks_bid
    net_pts = bidder_pts - opponent_tricks

    # Non-bidding hands: both teams get their tricks, net = tricks - (10 - tricks) = 2*tricks - 10
    no_bid_tricks = tricks_won[~would_bid]
    no_bid_net = 2.0 * no_bid_tricks - 10.0

    # Overall net_eppd: weighted average across all deals
    total_net = float(net_pts.sum() + no_bid_net.sum())
    net_eppd = total_net / n_total

    return {
        "net_eppd": net_eppd,
        "bid_rate": n_bid / n_total,
        "make_rate": float(made.mean()),
        "n_bid_hands": n_bid,
        "n_total": n_total,
    }


def run_sweep(artifact, df, grid, seed):
    """Run threshold sweep on train/val split.

    Returns (selected_threshold, train_results, val_result).
    """
    # Add partition column
    df = df.copy()
    df["_partition"] = df["deal_id"].apply(lambda d: deal_partition(str(d), seed))

    train_df = df[df["_partition"] == "train"]
    val_df = df[df["_partition"] == "val"]

    print(f"  Train: {len(train_df)} rows, Val: {len(val_df)} rows")

    # Determine which models to use (hybrid has 'suit', 'high', 'low')
    models = artifact.get("models", {})
    if not models:
        raise ValueError(
            "No model families found in artifact. "
            "Expected 'models' or 'payoff_model' with per-contract-family entries."
        )

    # Evaluate per contract family, then merge
    train_results = {}
    val_results = {}

    for threshold in grid:
        train_metrics_parts = []
        val_metrics_parts = []

        for cf, model in models.items():
            feature_names = model["feature_names"]
            sigma = model.get("sigma", 1.0)  # Default sigma if not in artifact

            for split_name, split_df, result_list in [
                ("train", train_df, train_metrics_parts),
                ("val", val_df, val_metrics_parts),
            ]:
                cf_df = split_df[split_df["contract_type"] == cf]
                if len(cf_df) == 0:
                    continue
                mu = predict_tricks(model, feature_names, cf_df)
                metrics = evaluate_threshold(cf_df, mu, sigma, threshold)
                result_list.append(
                    {"contract_type": cf, "n": len(cf_df), "metrics": metrics}
                )

        # Aggregate train results across contract families
        train_results[threshold] = _aggregate_metrics(train_metrics_parts)
        val_results[threshold] = _aggregate_metrics(val_metrics_parts)

    # Select best threshold from train (highest net_eppd)
    selected = max(train_results, key=lambda t: train_results[t].get("net_eppd", -999))

    return selected, train_results, val_results


def _aggregate_metrics(parts):
    """Aggregate metrics across contract families weighted by deal count."""
    if not parts:
        return {"net_eppd": 0.0, "bid_rate": 0.0, "make_rate": 0.0, "n_total": 0}

    total_n = sum(p["n"] for p in parts)
    if total_n == 0:
        return {"net_eppd": 0.0, "bid_rate": 0.0, "make_rate": 0.0, "n_total": 0}

    net_eppd = sum(p["metrics"]["net_eppd"] * p["n"] for p in parts) / total_n
    bid_rate = sum(p["metrics"]["bid_rate"] * p["n"] for p in parts) / total_n
    total_bids = sum(p["metrics"]["n_bid_hands"] for p in parts)
    total_made = sum(
        p["metrics"]["make_rate"] * p["metrics"]["n_bid_hands"] for p in parts
    )
    make_rate = total_made / total_bids if total_bids > 0 else 0.0

    return {
        "net_eppd": net_eppd,
        "bid_rate": bid_rate,
        "make_rate": make_rate,
        "n_total": total_n,
        "n_bid_hands": total_bids,
    }


def format_output(artifact_path, seed, grid, selected, train_results, val_results):
    """Format sweep results as JSON artifact."""
    grid_detail = {}
    for t in grid:
        grid_detail[str(t)] = {
            "train": train_results[t],
            "val": val_results.get(t, {}),
        }

    return {
        "schema": "threshold_sweep_v1",
        "artifact_path": str(artifact_path),
        "seed": seed,
        "grid": grid,
        "selected_threshold": selected,
        "selected_train_metrics": train_results[selected],
        "selected_val_metrics": val_results.get(selected, {}),
        "grid_results": grid_detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Threshold sweep for pass_threshold")
    parser.add_argument(
        "--artifact-path",
        required=True,
        help="Path to model artifact JSON",
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Run directory or path to bidless parquet",
    )
    parser.add_argument(
        "--grid",
        default="0.0,0.1,0.2,0.5,1.0,2.0,5.0",
        help="Comma-separated threshold grid (default: 0.0,...,5.0)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON path for sweep results",
    )
    args = parser.parse_args()

    grid = [float(x.strip()) for x in args.grid.split(",")]

    print("=== Threshold Sweep ===")
    print(f"  Artifact: {args.artifact_path}")
    print(f"  Grid: {grid}")
    print(f"  Seed: {args.seed}")

    # Load artifact
    artifact = load_model_artifact(args.artifact_path)

    # Load dataset
    data_path = Path(args.data)
    if data_path.is_dir():
        bidless_path = str(data_path / "datasets" / "bidless.parquet")
        outcomes_path = str(data_path / "datasets" / "bidless_outcomes.parquet")
    else:
        print("ERROR: --data must be a run directory", file=sys.stderr)
        sys.exit(1)

    df = join_features_outcomes(bidless_path, outcomes_path)
    print(f"  Dataset: {len(df)} rows")

    # Run sweep
    selected, train_results, val_results = run_sweep(artifact, df, grid, args.seed)

    print(f"\n  Selected threshold: {selected}")
    print(f"  Train net_eppd:    {train_results[selected]['net_eppd']:.4f}")
    if selected in val_results:
        print(f"  Val net_eppd:      {val_results[selected]['net_eppd']:.4f}")

    # Write output
    output = format_output(
        args.artifact_path, args.seed, grid, selected, train_results, val_results
    )
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Output: {args.output}")


if __name__ == "__main__":
    main()
