#!/usr/bin/env python3
"""Generate rung report charts from eval data and model artifacts.

Produces 11 chart PNGs that the Arc D rung report generator embeds inline
when ``chart_dir`` is provided.

Usage:
    uv run python scripts/internal/generate_rung_charts.py \
      --rung r0 \
      --eval-dir data/runs/arc_d_eval_r0_42_20260221_180253 \
      --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
      --output-dir data/reports/arc_d/r0/charts/

Charts produced (matching filenames expected by ``arc_d_report.py``):
  1. seat_balance_boxplot.png    — hand_value by seat
  2. hand_value_by_contract.png  — hand_value by contract type
  3. tricks_won_histogram.png    — outcome distribution by contract
  4. cdf_by_contract.png         — CDF of hand_value by contract
  5. auction_health.png          — contract selection, bid dist, auction length
  6. bidder_performance.png      — make rate, calibration, overbid
  7. coefficient_heatmap.png     — standardized coefficients by contract
  8. pred_vs_actual_scatter.png  — prediction diagnostics (3-panel)
  9. residual_distribution.png   — residual histogram (alias for panel 2 of #8)
 10. dual_arm_comparison.png     — metric comparison across arms
 11. calibration_curve.png       — prediction calibration curve
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for script use
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Data loading helpers
# ──────────────────────────────────────────────


def _load_eval_df(eval_dir: Path) -> pd.DataFrame:
    """Load eval DataFrame from JSONL logs in the eval run directory."""
    from bid_euchre.datasets.eval_dataset import build_eval_dataset

    log_dir = eval_dir / "logs"
    if not log_dir.exists():
        logger.error("Log directory not found: %s", log_dir)
        sys.exit(1)

    jsonl_files = sorted(log_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.error("No JSONL files in: %s", log_dir)
        sys.exit(1)

    # Use the first (usually only) JSONL file
    log_path = jsonl_files[0]
    logger.info("Loading eval data from: %s", log_path)
    return build_eval_dataset(log_path)


def _load_model_artifact(artifact_path: Path) -> dict | None:
    """Load a model artifact JSON, returning None on failure."""
    if not artifact_path.exists():
        logger.warning("Model artifact not found: %s", artifact_path)
        return None
    try:
        with open(artifact_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load model artifact %s: %s", artifact_path, e)
        return None


def _extract_coefs_by_contract(model_data: dict) -> dict:
    """Extract coefficient dict from model artifact for heatmap."""
    payoff = model_data.get("payoff_model", {})
    coefs_by_contract = {}
    for contract, model in payoff.items():
        fnames = model.get("feature_names", [])
        weights = model.get("weights", [])
        if fnames and weights:
            coefs_by_contract[contract] = dict(zip(fnames, weights))
    return coefs_by_contract


def _compute_predictions(
    model_data: dict, eval_df: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute model predictions on eval data.

    Returns (y_true, y_pred, contract_types) arrays.
    """
    payoff = model_data.get("payoff_model", {})
    all_y: list[float] = []
    all_pred: list[float] = []
    all_contracts: list[str] = []

    for contract, model in sorted(payoff.items()):
        fnames = model.get("feature_names", [])
        weights = np.array(model.get("weights", []))
        bias = model.get("bias", 0.0)

        if not fnames or len(weights) == 0:
            continue

        feat_cols = [f"feat_{fn}" for fn in fnames]
        subset = eval_df[eval_df["contract_type"] == contract]
        missing = [c for c in feat_cols if c not in subset.columns]
        if missing or len(subset) == 0:
            continue

        X = subset[feat_cols].values.astype(np.float64)
        y = subset["tricks_won"].values.astype(np.float64)
        y_pred = X @ weights + bias

        all_y.extend(y.tolist())
        all_pred.extend(y_pred.tolist())
        all_contracts.extend([contract] * len(y))

    return (
        np.array(all_y),
        np.array(all_pred),
        np.array(all_contracts),
    )


def _build_dual_arm_metrics(
    bundle: dict, eval_df: pd.DataFrame, base_dir: Path
) -> dict[str, dict]:
    """Build metrics dict for dual-arm comparison chart."""
    metrics_dict: dict[str, dict] = {}

    for arm_name, arm_label in [("olsa", "OLSa"), ("olsa_full", "OLSa_Full")]:
        arm = bundle.get(arm_name, {})
        artifact_path = arm.get("artifact_path")
        if not artifact_path:
            continue

        model_data = _load_model_artifact(base_dir / artifact_path)
        if model_data is None:
            continue

        y_true, y_pred, contract_types = _compute_predictions(model_data, eval_df)
        if len(y_true) == 0:
            continue

        # Overall R2
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        overall_r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        overall_mae = np.mean(np.abs(y_true - y_pred))

        # Per-contract R2
        r2_by_contract = {}
        for ct in sorted(set(contract_types)):
            mask = contract_types == ct
            y_ct = y_true[mask]
            p_ct = y_pred[mask]
            ss_r = np.sum((y_ct - p_ct) ** 2)
            ss_t = np.sum((y_ct - y_ct.mean()) ** 2)
            r2_by_contract[ct] = 1 - ss_r / ss_t if ss_t > 0 else float("nan")

        # Get eval metrics if available
        eval_path = arm.get("eval_seed42")
        eval_metrics: dict = {}
        if eval_path:
            em = _load_model_artifact(base_dir / eval_path)
            if em:
                eval_metrics = em

        arm_dict: dict = {
            "overall_r2": overall_r2,
            "overall_mae": overall_mae,
            "r2_by_contract": r2_by_contract,
        }
        # Add eval metrics if available
        for key in (
            "net_expected_points_per_deal",
            "make_rate",
            "bid_rate",
            "expected_points_per_deal",
        ):
            val = eval_metrics.get(key)
            if val is not None:
                # Use short aliases
                alias_map = {
                    "net_expected_points_per_deal": "net_eppd",
                    "expected_points_per_deal": "eppd",
                    "make_rate": "make_rate",
                    "bid_rate": "bid_rate",
                }
                arm_dict[alias_map.get(key, key)] = val

        metrics_dict[arm_label] = arm_dict

    return metrics_dict


# ──────────────────────────────────────────────
#  Chart generation functions
# ──────────────────────────────────────────────


def _save_chart(fig: plt.Figure, output_dir: Path, name: str, dpi: int = 150) -> None:
    """Save a chart and close the figure."""
    path = output_dir / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", path)


def generate_charts(
    eval_df: pd.DataFrame,
    bundle: dict,
    base_dir: Path,
    output_dir: Path,
    *,
    charts: list[str] | None = None,
    dpi: int = 150,
) -> list[str]:
    """Generate all rung report charts.

    Args:
        eval_df: Per-seat evaluation DataFrame from build_eval_dataset.
        bundle: Loaded rung bundle dict.
        base_dir: Base directory for resolving artifact paths.
        output_dir: Directory to write PNG files.
        charts: Optional list of specific chart names to generate.
            If None, generates all charts.
        dpi: DPI for saved figures.

    Returns:
        List of generated chart filenames.
    """
    from bid_euchre.diagnostics.auction_charts import (
        plot_auction_health,
        plot_bidder_performance,
    )
    from bid_euchre.diagnostics.charts import (
        plot_cdf,
        plot_coefficient_heatmap,
        plot_hand_value_by_contract,
        plot_hand_value_by_seat,
        plot_outcome_distributions,
    )
    from bid_euchre.diagnostics.model_charts import (
        plot_calibration_curve,
        plot_dual_arm_comparison,
        plot_model_diagnostics,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    def _should_generate(name: str) -> bool:
        return charts is None or name in charts

    # --- Charts that only need eval_df ---

    # 1. Seat balance boxplot
    if _should_generate("seat_balance_boxplot"):
        try:
            fig = plot_hand_value_by_seat(eval_df)
            _save_chart(fig, output_dir, "seat_balance_boxplot.png", dpi)
            generated.append("seat_balance_boxplot.png")
        except Exception as e:
            logger.warning("Failed to generate seat_balance_boxplot: %s", e)

    # 2. Hand value by contract
    if _should_generate("hand_value_by_contract"):
        try:
            fig = plot_hand_value_by_contract(eval_df)
            _save_chart(fig, output_dir, "hand_value_by_contract.png", dpi)
            generated.append("hand_value_by_contract.png")
        except Exception as e:
            logger.warning("Failed to generate hand_value_by_contract: %s", e)

    # 3. Tricks won histogram
    if _should_generate("tricks_won_histogram"):
        try:
            fig = plot_outcome_distributions(eval_df)
            _save_chart(fig, output_dir, "tricks_won_histogram.png", dpi)
            generated.append("tricks_won_histogram.png")
        except Exception as e:
            logger.warning("Failed to generate tricks_won_histogram: %s", e)

    # 4. CDF by contract
    if _should_generate("cdf_by_contract"):
        try:
            fig = plot_cdf(
                eval_df,
                column="feat_hand_value",
                group_by="contract_type",
                title="Hand Value CDF by Contract Type",
            )
            _save_chart(fig, output_dir, "cdf_by_contract.png", dpi)
            generated.append("cdf_by_contract.png")
        except Exception as e:
            logger.warning("Failed to generate cdf_by_contract: %s", e)

    # 5. Auction health
    if _should_generate("auction_health"):
        try:
            fig = plot_auction_health(eval_df)
            _save_chart(fig, output_dir, "auction_health.png", dpi)
            generated.append("auction_health.png")
        except Exception as e:
            logger.warning("Failed to generate auction_health: %s", e)

    # 6. Bidder performance
    if _should_generate("bidder_performance"):
        try:
            fig = plot_bidder_performance(eval_df)
            _save_chart(fig, output_dir, "bidder_performance.png", dpi)
            generated.append("bidder_performance.png")
        except Exception as e:
            logger.warning("Failed to generate bidder_performance: %s", e)

    # --- Charts that need model artifacts ---

    # Use OLSa_Full (promotional arm) as primary for coefficient/prediction charts
    primary_arm = "olsa_full"
    primary_artifact_path = bundle.get(primary_arm, {}).get("artifact_path")
    primary_model = None
    if primary_artifact_path:
        primary_model = _load_model_artifact(base_dir / primary_artifact_path)

    # 7. Coefficient heatmap
    if _should_generate("coefficient_heatmap") and primary_model:
        try:
            coefs = _extract_coefs_by_contract(primary_model)
            if coefs:
                fig = plot_coefficient_heatmap(
                    coefs, title="Coefficient Heatmap: OLSa_Full"
                )
                _save_chart(fig, output_dir, "coefficient_heatmap.png", dpi)
                generated.append("coefficient_heatmap.png")
        except Exception as e:
            logger.warning("Failed to generate coefficient_heatmap: %s", e)

    # 8. Pred vs actual scatter (from plot_model_diagnostics panel 1)
    if _should_generate("pred_vs_actual_scatter") and primary_model:
        try:
            y_true, y_pred, ct = _compute_predictions(primary_model, eval_df)
            if len(y_true) > 0:
                fig = plot_model_diagnostics(
                    y_true, y_pred, ct, title="Model Diagnostics: OLSa_Full"
                )
                _save_chart(fig, output_dir, "pred_vs_actual_scatter.png", dpi)
                generated.append("pred_vs_actual_scatter.png")
        except Exception as e:
            logger.warning("Failed to generate pred_vs_actual_scatter: %s", e)

    # 9. Residual distribution (separate figure for residuals only)
    if _should_generate("residual_distribution") and primary_model:
        try:
            y_true, y_pred, ct = _compute_predictions(primary_model, eval_df)
            if len(y_true) > 0:
                residuals = y_true - y_pred
                fig, ax = plt.subplots(figsize=(8, 5))
                for contract in sorted(set(ct)):
                    mask = ct == contract
                    ax.hist(
                        residuals[mask],
                        bins=30,
                        alpha=0.5,
                        label=contract,
                        density=True,
                    )
                ax.set_xlabel("Residual (actual - predicted)")
                ax.set_ylabel("Density")
                ax.set_title("Residual Distribution by Contract Type")
                ax.legend()
                _save_chart(fig, output_dir, "residual_distribution.png", dpi)
                generated.append("residual_distribution.png")
        except Exception as e:
            logger.warning("Failed to generate residual_distribution: %s", e)

    # 10. Dual arm comparison
    if _should_generate("dual_arm_comparison"):
        try:
            metrics = _build_dual_arm_metrics(bundle, eval_df, base_dir)
            if metrics:
                fig = plot_dual_arm_comparison(metrics)
                _save_chart(fig, output_dir, "dual_arm_comparison.png", dpi)
                generated.append("dual_arm_comparison.png")
        except Exception as e:
            logger.warning("Failed to generate dual_arm_comparison: %s", e)

    # 11. Calibration curve
    if _should_generate("calibration_curve") and primary_model:
        try:
            y_true, y_pred, ct = _compute_predictions(primary_model, eval_df)
            if len(y_true) > 0:
                fig = plot_calibration_curve(
                    y_true, y_pred, ct, title="Calibration Curve: OLSa_Full"
                )
                _save_chart(fig, output_dir, "calibration_curve.png", dpi)
                generated.append("calibration_curve.png")
        except Exception as e:
            logger.warning("Failed to generate calibration_curve: %s", e)

    return generated


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate rung report charts from eval data and model artifacts."
    )
    parser.add_argument(
        "--rung",
        required=True,
        help="Rung identifier (e.g., r0, r1)",
    )
    parser.add_argument(
        "--eval-dir",
        required=True,
        type=Path,
        help="Path to eval run directory containing logs/*.jsonl",
    )
    parser.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="Path to rung_bundle_r{N}.json",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write chart PNGs",
    )
    parser.add_argument(
        "--chart",
        action="append",
        dest="charts",
        help="Generate only specific chart(s). Can be repeated.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI for saved figures (default: 150)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load bundle
    if not args.bundle.exists():
        logger.error("Bundle not found: %s", args.bundle)
        sys.exit(1)

    with open(args.bundle) as f:
        bundle = json.load(f)

    # Determine base_dir for resolving artifact paths
    # Bundle paths are repo-root-relative, so base_dir should be repo root
    # Convention: bundle is at data/artifacts/arc_d/r{N}/rung_bundle_r{N}.json
    # so repo root is 5 levels up
    base_dir = args.bundle.resolve().parent
    while base_dir != base_dir.parent:
        if (base_dir / "pyproject.toml").exists():
            break
        base_dir = base_dir.parent
    else:
        # Fallback: use CWD
        base_dir = Path.cwd()

    logger.info("Rung: %s", args.rung)
    logger.info("Eval dir: %s", args.eval_dir)
    logger.info("Bundle: %s", args.bundle)
    logger.info("Base dir: %s", base_dir)
    logger.info("Output dir: %s", args.output_dir)

    # Load eval data
    eval_df = _load_eval_df(args.eval_dir)
    logger.info("Loaded %d rows from eval data", len(eval_df))

    # Generate charts
    generated = generate_charts(
        eval_df,
        bundle,
        base_dir,
        args.output_dir,
        charts=args.charts,
        dpi=args.dpi,
    )

    logger.info("Generated %d charts: %s", len(generated), ", ".join(generated))


if __name__ == "__main__":
    main()
