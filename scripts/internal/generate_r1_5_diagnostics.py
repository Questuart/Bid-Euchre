"""
R1.5-v2 calibration diagnostics — cross-rung analysis + bimodality tests.

Generates per-contract model diagnostic charts for R1.5 (action-value) and R0
(hybrid OLSa) models, plus training data distribution analysis.

Charts produced:
  1. R1.5 per-contract: predicted vs actual, residual distribution, calibration,
     heteroscedasticity, suit residuals by bower count
  2. R0 per-contract: same diagnostic suite (target is tricks_won, not net_points)
  3. Training data: contract-type distribution, net_points histograms, bimodality

CLI usage:
    uv run python scripts/internal/generate_r1_5_diagnostics.py \\
        --r15-artifact data/artifacts/arc_d/r1_5/action_value_full.json \\
        --r15-dataset data/runs/action_value_quick_42/datasets/action_value.parquet \\
        --r0-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \\
        --r0-eval-dir data/runs/arc_d_eval_r0_full_42_20260303_201732 \\
        --output-dir data/reports/arc_d/r1_5_v2/diagnostics \\
        --seed 42
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from bid_euchre.datasets.eval_dataset import build_eval_dataset  # noqa: E402
from bid_euchre.diagnostics.model_charts import (  # noqa: E402
    plot_calibration_curve,
    plot_model_diagnostics,
)
from bid_euchre.reporting.style import (  # noqa: E402
    apply_report_style,
    get_contract_color,
    get_contract_label,
)

_tav_spec = importlib.util.spec_from_file_location(
    "train_action_value",
    Path(__file__).resolve().parent / "train_action_value.py",
)
_tav_mod = importlib.util.module_from_spec(_tav_spec)  # type: ignore[arg-type]
_tav_spec.loader.exec_module(_tav_mod)  # type: ignore[union-attr]
_build_feature_matrix = _tav_mod._build_feature_matrix
split_by_deal = _tav_mod.split_by_deal

# ── Constants ────────────────────────────────────────────────

CONTRACT_FAMILIES = ["suit", "high", "low", "pass"]
CONTRACT_FAMILIES_BID = ["suit", "high", "low"]

# ── Bimodality ───────────────────────────────────────────────


def bimodality_test_gmm(
    data: np.ndarray,
    seed: int,
) -> dict:
    """Test for bimodality using Gaussian mixture BIC comparison.

    Fits 1-component and 2-component GMMs, returns BIC difference.
    A large negative delta_bic (2-component BIC << 1-component BIC) suggests
    bimodality. Convention: delta_bic = BIC_1 - BIC_2 (positive = bimodal
    evidence).

    Returns dict with bic_1, bic_2, delta_bic, bimodal_evidence.
    """
    from sklearn.mixture import GaussianMixture

    data = data.reshape(-1, 1)

    gmm1 = GaussianMixture(n_components=1, random_state=seed)
    gmm1.fit(data)
    bic1 = gmm1.bic(data)

    gmm2 = GaussianMixture(n_components=2, random_state=seed)
    gmm2.fit(data)
    bic2 = gmm2.bic(data)

    delta = bic1 - bic2  # positive = 2-component is better fit

    return {
        "bic_1_component": float(bic1),
        "bic_2_component": float(bic2),
        "delta_bic": float(delta),
        "bimodal_evidence": "strong"
        if delta > 10
        else ("weak" if delta > 2 else "none"),
    }


# ── R1.5 Diagnostics ────────────────────────────────────────


def load_r15_model(artifact_path: str) -> dict:
    """Load R1.5 action-value model artifact."""
    with open(artifact_path) as f:
        return json.load(f)


def compute_r15_predictions(
    model: dict,
    df: pd.DataFrame,
    family: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute R1.5 model predictions for a contract family.

    Returns (y_true, y_pred).
    """
    from bid_euchre.strategy.bidding import ACTION_FEATURE_NAMES, STATE_FEATURE_NAMES

    model_data = model["models"][family]
    coefficients = np.array(model_data["coefficients"])
    intercept = model_data["intercept"]

    if family == "pass":
        feature_names = list(STATE_FEATURE_NAMES)
        subset = df[df["action_type"] == "pass"].copy()
    else:
        feature_names = list(STATE_FEATURE_NAMES) + list(ACTION_FEATURE_NAMES)
        subset = df[df["contract_family"] == family].copy()

    if len(subset) == 0:
        return np.array([]), np.array([])

    X = _build_feature_matrix(subset, feature_names)
    y_true = subset["net_points"].values.astype(np.float64)
    y_pred = X @ coefficients + intercept

    return y_true, y_pred


def generate_r15_diagnostics(
    model: dict,
    test_df: pd.DataFrame,
    output_dir: Path,
    seed: int,
) -> dict:
    """Generate R1.5 model diagnostic charts and statistics.

    Returns dict of per-contract statistics.
    """
    results: dict = {}

    for family in CONTRACT_FAMILIES:
        y_true, y_pred = compute_r15_predictions(model, test_df, family)
        if len(y_true) == 0:
            print(f"  [R1.5] Skipping {family} — no test data")
            continue

        residuals = y_true - y_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        results[family] = {
            "n": len(y_true),
            "r2": float(r2),
            "mae": float(np.mean(np.abs(residuals))),
            "rmse": float(np.sqrt(np.mean(residuals**2))),
            "mean_residual": float(np.mean(residuals)),
            "std_residual": float(np.std(residuals)),
            "skewness": float(stats.skew(residuals)),
            "kurtosis": float(stats.kurtosis(residuals)),
        }

        # Bimodality test on residuals
        bimod = bimodality_test_gmm(residuals, seed)
        results[family]["bimodality"] = bimod

        print(
            f"  [R1.5] {family}: n={len(y_true)}, R²={r2:.4f}, "
            f"MAE={results[family]['mae']:.3f}, bimodal={bimod['bimodal_evidence']}"
        )

        # Contract-type array for chart functions
        ct_array = np.array([family] * len(y_true))

        # 1. Model diagnostics (pred vs actual, residuals, heteroscedasticity)
        fig = plot_model_diagnostics(
            y_true, y_pred, ct_array, title=f"R1.5 {family.title()} Model Diagnostics"
        )
        fig.savefig(
            output_dir / f"r15_{family}_diagnostics.png", dpi=150, bbox_inches="tight"
        )
        plt.close(fig)

        # 2. Calibration curve
        fig = plot_calibration_curve(
            y_true, y_pred, ct_array, title=f"R1.5 {family.title()} Calibration"
        )
        fig.savefig(
            output_dir / f"r15_{family}_calibration.png", dpi=150, bbox_inches="tight"
        )
        plt.close(fig)

        # 3. Suit-specific: residuals by bower count
        if family == "suit" and "bowers" in test_df.columns:
            _plot_residuals_by_bowers(
                test_df[test_df["contract_family"] == "suit"],
                residuals,
                output_dir,
                prefix="r15",
            )

    return results


def _plot_residuals_by_bowers(
    subset_df: pd.DataFrame,
    residuals: np.ndarray,
    output_dir: Path,
    prefix: str,
) -> None:
    """Plot residual distributions conditioned on bower count (0, 1, 2+)."""
    apply_report_style()

    bowers = subset_df["bowers"].values
    groups = {
        "0 bowers": residuals[bowers == 0],
        "1 bower": residuals[bowers == 1],
        "2+ bowers": residuals[bowers >= 2],
    }

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for (label, data), color in zip(groups.items(), colors):
        if len(data) > 0:
            ax.hist(
                data,
                bins=30,
                alpha=0.5,
                color=color,
                label=f"{label} (n={len(data)}, mean={np.mean(data):.2f})",
                edgecolor="black",
                linewidth=0.3,
            )

    ax.axvline(0, color="black", linestyle="-", linewidth=1.5)
    ax.set_xlabel("Residual (Actual - Predicted)")
    ax.set_ylabel("Count")
    ax.set_title(f"{prefix.upper()} Suit: Residuals by Bower Count")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(
        output_dir / f"{prefix}_suit_residuals_by_bowers.png",
        dpi=150,
        bbox_inches="tight",
    )
    plt.close(fig)


# ── R0 Diagnostics ───────────────────────────────────────────


def load_r0_model(artifact_path: str) -> dict:
    """Load R0 hybrid OLSa model artifact."""
    with open(artifact_path) as f:
        return json.load(f)


def compute_r0_predictions(
    model_data: dict,
    eval_df: pd.DataFrame,
    contract: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute R0 model predictions for a contract type.

    R0 model schema: payoff_model -> {contract} -> feature_names, weights, bias.
    Target: tricks_won.

    Returns (y_true, y_pred).
    """
    payoff = model_data.get("payoff_model", {})
    if contract not in payoff:
        return np.array([]), np.array([])

    model = payoff[contract]
    fnames = model.get("feature_names", [])
    weights = np.array(model.get("weights", []))
    bias = model.get("bias", 0.0)

    if not fnames or len(weights) == 0:
        return np.array([]), np.array([])

    feat_cols = [f"feat_{fn}" for fn in fnames]
    subset = eval_df[eval_df["contract_type"] == contract]
    missing = [c for c in feat_cols if c not in subset.columns]
    if missing or len(subset) == 0:
        return np.array([]), np.array([])

    X = subset[feat_cols].values.astype(np.float64)
    y_true = subset["tricks_won"].values.astype(np.float64)
    y_pred = X @ weights + bias

    return y_true, y_pred


def generate_r0_diagnostics(
    model_data: dict,
    eval_df: pd.DataFrame,
    output_dir: Path,
    seed: int,
) -> dict:
    """Generate R0 model diagnostic charts and statistics.

    Returns dict of per-contract statistics.
    """
    results: dict = {}

    for contract in CONTRACT_FAMILIES_BID:
        y_true, y_pred = compute_r0_predictions(model_data, eval_df, contract)
        if len(y_true) == 0:
            print(f"  [R0] Skipping {contract} — no data")
            continue

        residuals = y_true - y_pred
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        results[contract] = {
            "n": len(y_true),
            "r2": float(r2),
            "mae": float(np.mean(np.abs(residuals))),
            "rmse": float(np.sqrt(np.mean(residuals**2))),
            "mean_residual": float(np.mean(residuals)),
            "std_residual": float(np.std(residuals)),
            "skewness": float(stats.skew(residuals)),
            "kurtosis": float(stats.kurtosis(residuals)),
        }

        # Bimodality test on residuals
        bimod = bimodality_test_gmm(residuals, seed)
        results[contract]["bimodality"] = bimod

        print(
            f"  [R0] {contract}: n={len(y_true)}, R²={r2:.4f}, "
            f"MAE={results[contract]['mae']:.3f}, bimodal={bimod['bimodal_evidence']}"
        )

        ct_array = np.array([contract] * len(y_true))

        # 1. Model diagnostics
        fig = plot_model_diagnostics(
            y_true, y_pred, ct_array, title=f"R0 {contract.title()} Model Diagnostics"
        )
        fig.savefig(
            output_dir / f"r0_{contract}_diagnostics.png", dpi=150, bbox_inches="tight"
        )
        plt.close(fig)

        # 2. Calibration curve
        fig = plot_calibration_curve(
            y_true, y_pred, ct_array, title=f"R0 {contract.title()} Calibration"
        )
        fig.savefig(
            output_dir / f"r0_{contract}_calibration.png", dpi=150, bbox_inches="tight"
        )
        plt.close(fig)

        # 3. Suit-specific: residuals by bower count
        if contract == "suit":
            suit_subset = eval_df[eval_df["contract_type"] == "suit"]
            if "feat_bowers" in suit_subset.columns:
                bowers = suit_subset["feat_bowers"].values
                groups = {
                    "0 bowers": residuals[bowers == 0],
                    "1 bower": residuals[bowers == 1],
                    "2+ bowers": residuals[bowers >= 2],
                }
                _plot_residuals_by_bowers_r0(groups, output_dir)

    return results


def _plot_residuals_by_bowers_r0(
    groups: dict[str, np.ndarray],
    output_dir: Path,
) -> None:
    """Plot R0 suit residual distributions conditioned on bower count."""
    apply_report_style()

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    for (label, data), color in zip(groups.items(), colors):
        if len(data) > 0:
            ax.hist(
                data,
                bins=30,
                alpha=0.5,
                color=color,
                label=f"{label} (n={len(data)}, mean={np.mean(data):.2f})",
                edgecolor="black",
                linewidth=0.3,
            )

    ax.axvline(0, color="black", linestyle="-", linewidth=1.5)
    ax.set_xlabel("Residual (Actual - Predicted)")
    ax.set_ylabel("Count")
    ax.set_title("R0 Suit: Residuals by Bower Count")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(
        output_dir / "r0_suit_residuals_by_bowers.png", dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


# ── Training Data Analysis ───────────────────────────────────


def analyze_training_data(
    df: pd.DataFrame,
    output_dir: Path,
    seed: int,
) -> dict:
    """Analyze training data distributions.

    Returns dict of distribution statistics.
    """
    results: dict = {}

    # Contract family distribution
    family_counts = df["contract_family"].value_counts()
    action_counts = df["action_type"].value_counts()

    results["contract_distribution"] = {
        "family_counts": family_counts.to_dict(),
        "action_counts": action_counts.to_dict(),
        "total_rows": len(df),
    }

    # Add pass count from action_type
    pass_count = int(action_counts.get("pass", 0))
    print(f"  Contract distribution: {family_counts.to_dict()}, pass={pass_count}")

    # Per-contract net_points distribution
    for family in CONTRACT_FAMILIES_BID:
        subset = df[df["contract_family"] == family]
        if len(subset) == 0:
            continue

        values = subset["net_points"].values
        results[f"{family}_net_points"] = {
            "n": len(values),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "skewness": float(stats.skew(values)),
            "kurtosis": float(stats.kurtosis(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "median": float(np.median(values)),
        }

        # Bimodality test on net_points
        bimod = bimodality_test_gmm(values, seed)
        results[f"{family}_net_points"]["bimodality"] = bimod

        print(
            f"  {family} net_points: mean={np.mean(values):.2f}, "
            f"std={np.std(values):.2f}, bimodal={bimod['bimodal_evidence']}"
        )

    # Pass net_points
    pass_subset = df[df["action_type"] == "pass"]
    if len(pass_subset) > 0:
        values = pass_subset["net_points"].values
        results["pass_net_points"] = {
            "n": len(values),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "skewness": float(stats.skew(values)),
            "kurtosis": float(stats.kurtosis(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "median": float(np.median(values)),
        }
        bimod = bimodality_test_gmm(values, seed)
        results["pass_net_points"]["bimodality"] = bimod

    # Charts
    _plot_contract_distribution(df, output_dir)
    _plot_net_points_histograms(df, output_dir)

    return results


def _plot_contract_distribution(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot contract-type distribution (bar chart)."""
    apply_report_style()

    # Count by contract_family (suit/high/low) + pass from action_type
    families = df["contract_family"].value_counts()
    pass_count = (df["action_type"] == "pass").sum()

    labels = list(families.index) + ["pass"]
    counts = list(families.values) + [pass_count]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [get_contract_color(label) for label in labels]
    ax.bar(
        [get_contract_label(l) for l in labels],
        counts,
        color=colors,
        edgecolor="black",
        linewidth=0.5,
    )

    for i, (count, label) in enumerate(zip(counts, labels)):
        pct = 100 * count / len(df)
        ax.text(
            i,
            count + max(counts) * 0.01,
            f"{count}\n({pct:.1f}%)",
            ha="center",
            fontsize=8,
        )

    ax.set_ylabel("Count")
    ax.set_title("Training Data: Contract Family Distribution")
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(
        output_dir / "training_contract_distribution.png", dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_net_points_histograms(df: pd.DataFrame, output_dir: Path) -> None:
    """Plot net_points histograms per contract family."""
    apply_report_style()

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes_flat = axes.flatten()

    families_with_data = [
        ("suit", df[df["contract_family"] == "suit"]),
        ("high", df[df["contract_family"] == "high"]),
        ("low", df[df["contract_family"] == "low"]),
        ("pass", df[df["action_type"] == "pass"]),
    ]

    for ax, (family, subset) in zip(axes_flat, families_with_data):
        if len(subset) == 0:
            ax.text(0.5, 0.5, f"No {family} data", ha="center", va="center")
            continue

        values = subset["net_points"].values
        color = get_contract_color(family)
        ax.hist(
            values, bins=50, color=color, alpha=0.7, edgecolor="black", linewidth=0.3
        )
        ax.axvline(
            np.mean(values),
            color="red",
            linestyle="--",
            linewidth=1.5,
            label=f"mean={np.mean(values):.1f}",
        )
        ax.axvline(
            np.median(values),
            color="blue",
            linestyle=":",
            linewidth=1.5,
            label=f"median={np.median(values):.1f}",
        )
        ax.set_xlabel("net_points")
        ax.set_ylabel("Count")
        ax.set_title(f"{get_contract_label(family)} (n={len(values)})")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle("Training Data: net_points Distribution by Contract", fontsize=14)
    fig.tight_layout()
    fig.savefig(
        output_dir / "training_net_points_histograms.png", dpi=150, bbox_inches="tight"
    )
    plt.close(fig)


# ── Summary ──────────────────────────────────────────────────


def write_summary(
    r15_results: dict,
    r0_results: dict,
    training_results: dict,
    output_dir: Path,
) -> None:
    """Write JSON summary of all diagnostic results."""
    summary = {
        "r1_5": r15_results,
        "r0": r0_results,
        "training_data": training_results,
    }
    summary_path = output_dir / "diagnostic_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary written to {summary_path}")


# ── CLI ──────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R1.5-v2 calibration diagnostics — cross-rung analysis + bimodality tests"
    )
    parser.add_argument(
        "--r15-artifact",
        required=True,
        help="Path to R1.5 action-value model artifact JSON",
    )
    parser.add_argument(
        "--r15-dataset",
        required=True,
        help="Path to R1.5 action-value training parquet",
    )
    parser.add_argument(
        "--r0-artifact",
        required=True,
        help="Path to R0 hybrid OLSa model artifact JSON",
    )
    parser.add_argument(
        "--r0-eval-dir",
        required=True,
        help="Path to R0 eval run directory (containing logs/*.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for charts and summary JSON",
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Random seed for reproducibility (split, GMM)",
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== R1.5-v2 Calibration Diagnostics ===")
    print(f"  Seed: {args.seed}")

    # ── Step 0: R1.5 within-rung diagnostics ─────────────────
    print("\n--- R1.5 Model Diagnostics ---")
    r15_model = load_r15_model(args.r15_artifact)

    print("  Loading R1.5 dataset...")
    r15_df = pd.read_parquet(args.r15_dataset)
    print(f"  Loaded {len(r15_df)} rows, {r15_df['deal_id'].nunique()} deals")

    # Use test split only (same split logic as training pipeline)
    _, _, test_df = split_by_deal(r15_df, args.seed)
    print(f"  Test split: {len(test_df)} rows")

    r15_results = generate_r15_diagnostics(r15_model, test_df, output_dir, args.seed)

    # ── Step 0: R0 cross-rung comparison ─────────────────────
    print("\n--- R0 Model Diagnostics ---")
    r0_model = load_r0_model(args.r0_artifact)

    # Find JSONL log in eval dir
    r0_eval_dir = Path(args.r0_eval_dir)
    log_files = sorted(r0_eval_dir.glob("logs/*.jsonl"))
    if not log_files:
        print("  ERROR: No JSONL logs found in R0 eval dir")
        r0_results: dict = {}
    else:
        log_path = log_files[0]
        print(f"  Loading R0 eval data from {log_path.name}...")
        r0_eval_df = build_eval_dataset(log_path)
        print(
            f"  Loaded {len(r0_eval_df)} rows, {r0_eval_df['deal_id'].nunique()} deals"
        )

        r0_results = generate_r0_diagnostics(
            r0_model, r0_eval_df, output_dir, args.seed
        )

    # ── Step 1: Training data distribution ───────────────────
    print("\n--- Training Data Distribution ---")
    training_results = analyze_training_data(r15_df, output_dir, args.seed)

    # ── Summary ──────────────────────────────────────────────
    write_summary(r15_results, r0_results, training_results, output_dir)

    # Print chart inventory
    chart_files = sorted(output_dir.glob("*.png"))
    print(f"\n  Charts produced: {len(chart_files)}")
    for chart in chart_files:
        print(f"    {chart.name}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
