#!/usr/bin/env python
"""
Diagnostic Ridge regression on tricks_won from canonical bidless data.

Trains a full-feature Ridge model (41 features) on tricks_won using
standardized features. Reports overall and per-contract R²/MAE plus
top-10 standardized coefficients.

This is a DIAGNOSTIC evaluation — separate from the B0 hand-value
regression in train_b0.py. Coefficient ranking is exploratory only,
not definitive feature importance.

Usage:
    uv run python scripts/evaluate_diagnostic_tricks.py \
        --greedy-dir data/runs/canonical_bidless_dataset_greedy_42_20260204_221121 \
        --glutton-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
        --seed 42 --output docs/02_agent/DIAGNOSTIC_TRICKS_EVALUATION.md
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bid_euchre.analysis.models import SimpleRidge  # noqa: E402
from bid_euchre.datasets.join import join_features_outcomes  # noqa: E402

# Features to exclude from the feature matrix (metadata, not predictive)
EXCLUDE_COLS = {
    "hand_id",
    "seat",
    "dealer_seat",
    "deal_id",
    "hand_cards",
    "hand_feature_schema_version",
    "contract_type",
    "trump_suit",
    "tricks_won",
}

# OLSa candidate features to validate
OLSA_SUIT_FEATURES = {"bowers", "trump_count", "offsuit_aces"}
OLSA_HIGH_FEATURES = {"offsuit_aces"}
OLSA_LOW_FEATURES = {"offsuit_tens_count"}


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Get feature column names (all numeric columns except excluded)."""
    return [
        c
        for c in df.columns
        if c not in EXCLUDE_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]


def grouped_train_test_split(
    df: pd.DataFrame, seed: int, train_frac: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split by hand_id to prevent leakage across 4 seat rows per hand.

    Returns (train_df, test_df).
    """
    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)
    split_idx = int(len(unique_ids) * train_frac)
    train_ids = set(unique_ids[:split_idx])
    train_mask = df["hand_id"].isin(train_ids)
    return df[train_mask].copy(), df[~train_mask].copy()


def train_and_evaluate(
    df: pd.DataFrame,
    feature_cols: list[str],
    seed: int,
    label: str,
) -> dict:
    """
    Train standardized Ridge on tricks_won. Return metrics + coefficients.

    Features are z-scored before fitting so coefficients are comparable.
    """
    train_df, test_df = grouped_train_test_split(df, seed)

    X_train = train_df[feature_cols].values.astype(np.float64)
    y_train = train_df["tricks_won"].values.astype(np.float64)
    X_test = test_df[feature_cols].values.astype(np.float64)
    y_test = test_df["tricks_won"].values.astype(np.float64)

    # Standardize features (z-score)
    means = X_train.mean(axis=0)
    stds = X_train.std(axis=0)
    # Avoid division by zero for constant columns
    stds[stds == 0] = 1.0

    X_train_std = (X_train - means) / stds
    X_test_std = (X_test - means) / stds

    # Fit Ridge
    model = SimpleRidge(alpha=1.0)
    model.fit(X_train_std, y_train)

    # Evaluate
    y_pred_train = model.predict(X_train_std)
    y_pred_test = model.predict(X_test_std)

    ss_res_train = np.sum((y_train - y_pred_train) ** 2)
    ss_tot_train = np.sum((y_train - y_train.mean()) ** 2)
    r2_train = 1 - ss_res_train / ss_tot_train

    ss_res_test = np.sum((y_test - y_pred_test) ** 2)
    ss_tot_test = np.sum((y_test - y_test.mean()) ** 2)
    r2_test = 1 - ss_res_test / ss_tot_test

    mae_train = np.mean(np.abs(y_train - y_pred_train))
    mae_test = np.mean(np.abs(y_test - y_pred_test))

    # Coefficient ranking (standardized)
    coef_ranking = sorted(
        zip(feature_cols, model.coef_),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    return {
        "label": label,
        "n_train_hands": len(train_df["hand_id"].unique()),
        "n_test_hands": len(test_df["hand_id"].unique()),
        "n_train_rows": len(train_df),
        "n_test_rows": len(test_df),
        "r2_train": r2_train,
        "r2_test": r2_test,
        "mae_train": mae_train,
        "mae_test": mae_test,
        "coef_ranking": coef_ranking,
        "intercept": model.intercept_,
    }


def per_contract_metrics(
    df: pd.DataFrame,
    feature_cols: list[str],
    seed: int,
) -> list[dict]:
    """Train and evaluate per contract_type."""
    results = []
    for ct in sorted(df["contract_type"].unique()):
        sub = df[df["contract_type"] == ct]
        if len(sub) < 100:
            continue
        result = train_and_evaluate(sub, feature_cols, seed, f"contract={ct}")
        result["contract_type"] = ct
        results.append(result)
    return results


def validate_olsa_features(coef_ranking: list, contract_type: str) -> str:
    """Check if OLSa candidate features rank in top 10."""
    top10_features = {name for name, _ in coef_ranking[:10]}

    if contract_type == "suit":
        target = OLSA_SUIT_FEATURES
    elif contract_type == "high":
        target = OLSA_HIGH_FEATURES
    elif contract_type == "low":
        target = OLSA_LOW_FEATURES
    else:
        return "N/A"

    found = target & top10_features
    missing = target - top10_features
    if missing:
        return f"WARN: {missing} not in top 10"
    return f"OK: {found} all in top 10"


def format_report(
    overall_results: list[dict],
    per_contract_results: dict[str, list[dict]],
) -> str:
    """Format results as markdown."""
    lines = [
        "# Diagnostic Tricks-Model Evaluation",
        "",
        "> **Purpose:** Full-feature Ridge regression on `tricks_won` from canonical bidless data.",
        "> Coefficients are standardized and exploratory. Correlated features share variance.",
        "> This diagnostic is separate from the B0 hand-value regression in `train_b0.py`.",
        "",
        "## Methodology",
        "",
        "- **Model:** Ridge regression (alpha=1.0) with standardized features (z-scored)",
        "- **Target:** `tricks_won` (per-seat, derived from team trick counts)",
        "- **Split:** Grouped by `hand_id` (80/20 train/test) to prevent leakage across 4 seat rows",
        "- **Features:** All 41 hand features from `get_hand_features()`",
        "",
    ]

    for result in overall_results:
        lines.extend(
            [
                f"## {result['label']}",
                "",
                f"- **Training:** {result['n_train_hands']:,} hands ({result['n_train_rows']:,} seat-rows)",
                f"- **Test:** {result['n_test_hands']:,} hands ({result['n_test_rows']:,} seat-rows)",
                f"- **R² (train):** {result['r2_train']:.4f}",
                f"- **R² (test):** {result['r2_test']:.4f}",
                f"- **MAE (train):** {result['mae_train']:.4f}",
                f"- **MAE (test):** {result['mae_test']:.4f}",
                f"- **Intercept:** {result['intercept']:.4f}",
                "",
                "### Top 10 Standardized Coefficients",
                "",
                "| Rank | Feature | Coefficient |",
                "|------|---------|-------------|",
            ]
        )
        for rank, (feat, coef) in enumerate(result["coef_ranking"][:10], 1):
            lines.append(f"| {rank} | `{feat}` | {coef:+.4f} |")
        lines.append("")

    # Per-contract results
    for dataset_label, contract_results in per_contract_results.items():
        lines.extend(
            [
                f"## Per-Contract Breakdown: {dataset_label}",
                "",
                "| Contract | R² (test) | MAE (test) | N (test rows) | OLSa Feature Validation |",
                "|----------|-----------|------------|---------------|------------------------|",
            ]
        )
        for cr in contract_results:
            olsa_status = validate_olsa_features(
                cr["coef_ranking"], cr["contract_type"]
            )
            lines.append(
                f"| {cr['contract_type']} | {cr['r2_test']:.4f} | "
                f"{cr['mae_test']:.4f} | {cr['n_test_rows']:,} | {olsa_status} |"
            )
        lines.append("")

        # Show top 5 coefficients per contract
        for cr in contract_results:
            lines.extend(
                [
                    f"### {dataset_label} — contract={cr['contract_type']} top 5",
                    "",
                    "| Rank | Feature | Coefficient |",
                    "|------|---------|-------------|",
                ]
            )
            for rank, (feat, coef) in enumerate(cr["coef_ranking"][:5], 1):
                lines.append(f"| {rank} | `{feat}` | {coef:+.4f} |")
            lines.append("")

    lines.extend(
        [
            "## Caveats",
            "",
            "- Coefficients are standardized (z-scored features) and exploratory only",
            "- Correlated features share variance; coefficients do not imply causal importance",
            "- This diagnostic is separate from the B0 hand-value regression pipeline",
            "- Use Ridge (not raw OLS) for 40+ correlated features to avoid numerical instability",
            "",
        ]
    )

    return "\n".join(lines)


def process_dataset(run_dir: str, seed: int, label: str) -> tuple[dict, list[dict]]:
    """Load one dataset, train overall + per-contract, return results."""
    bidless_path = os.path.join(run_dir, "datasets", "bidless.parquet")
    outcomes_path = os.path.join(run_dir, "datasets", "bidless_outcomes.parquet")

    if not os.path.exists(bidless_path):
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not os.path.exists(outcomes_path):
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    print(f"Loading {label} data...")
    df = join_features_outcomes(bidless_path, outcomes_path)
    feature_cols = get_feature_columns(df)
    print(f"  Joined: {len(df):,} rows, {len(feature_cols)} features")

    print("  Training overall model...")
    overall = train_and_evaluate(df, feature_cols, seed, label)

    print("  Training per-contract models...")
    per_contract = per_contract_metrics(df, feature_cols, seed)

    # Free memory before returning
    del df

    return overall, per_contract


def main():
    parser = argparse.ArgumentParser(description="Diagnostic tricks-model evaluation")
    parser.add_argument(
        "--greedy-dir", required=True, help="Path to greedy canonical run"
    )
    parser.add_argument(
        "--glutton-dir", required=True, help="Path to glutton canonical run"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", required=True, help="Output markdown path")
    parser.add_argument(
        "--per-contract-json",
        default=None,
        help="Output per-contract coefficients as JSON for heatmap generation",
    )
    args = parser.parse_args()

    overall_results = []
    per_contract_results = {}

    # Process greedy dataset
    overall, per_contract = process_dataset(
        args.greedy_dir, args.seed, "Greedy Play Policy"
    )
    overall_results.append(overall)
    per_contract_results["Greedy"] = per_contract

    # Process glutton dataset
    overall, per_contract = process_dataset(
        args.glutton_dir, args.seed, "Glutton Play Policy"
    )
    overall_results.append(overall)
    per_contract_results["Glutton"] = per_contract

    # Generate report
    report = format_report(overall_results, per_contract_results)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    print(f"\nReport written to {args.output}")
    print(
        f"Overall R² — Greedy: {overall_results[0]['r2_test']:.4f}, Glutton: {overall_results[1]['r2_test']:.4f}"
    )

    # Write per-contract coefficients JSON for heatmap generation
    if args.per_contract_json:
        coef_json = {}
        for dataset_label, contract_results in per_contract_results.items():
            coef_json[dataset_label.lower()] = {}
            for cr in contract_results:
                ct = cr["contract_type"]
                coef_json[dataset_label.lower()][ct] = {
                    feat: float(coef) for feat, coef in cr["coef_ranking"]
                }
        os.makedirs(
            os.path.dirname(os.path.abspath(args.per_contract_json)), exist_ok=True
        )
        with open(args.per_contract_json, "w") as f:
            json.dump(coef_json, f, indent=2)
        print(f"Per-contract coefficients written to {args.per_contract_json}")


if __name__ == "__main__":
    main()
