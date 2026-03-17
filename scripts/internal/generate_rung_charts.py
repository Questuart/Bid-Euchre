#!/usr/bin/env python
"""Generate rung report charts from canonical CSV tables.

CSV-first chart generation for Arc D v2 reports. Reads from tables/*.csv
and produces PNGs to charts/ plus source data to chart_data/.

Usage:
    uv run python scripts/internal/generate_rung_charts.py \\
        --tables-dir /tmp/rung_report/tables \\
        --output-dir /tmp/rung_report/charts \\
        --chart-data-dir /tmp/rung_report/chart_data

Charts produced (Tier 1 + Tier 2 from §12.12):
  1.  comparator_ranking_bars.png    — from comparator_rankings.csv
  2.  delta_bars_by_contract.png     — from h2h_delta_matrix.csv
  3.  h2h_heatmap.png               — from h2h_delta_matrix.csv
  4.  tail_risk_panel.png            — from comparator_rankings.csv
  5.  bid_behavior_panel.png         — from behavior_by_contract.csv
  6.  contract_mix_bars.png          — from behavior_summary.csv
  7.  r2_by_contract.png             — from model_performance.csv
  8.  mae_by_contract.png            — from model_performance.csv
  9.  outcome_summary.png            — from chart_data/outcome_summary.csv
  10. seat_balance.png               — from chart_data/seat_balance.csv

Dashboard pages (composite multi-panel charts):
  11. dashboard_competitive.png      — rankings, H2H delta, heatmap, tail risk
  12. dashboard_health.png           — bid/make rate, contract mix, outcomes, bid-type
  13. dashboard_model_eval.png       — R², MAE, selection paths, cross-rung progression
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _save_chart(fig: plt.Figure, output_dir: Path, name: str, dpi: int = 150) -> None:
    """Save a chart and close the figure."""
    path = output_dir / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", path)


def _read_csv_safe(path: Path) -> pd.DataFrame | None:
    """Read CSV, returning None if missing or empty."""
    if not path.exists():
        logger.warning("CSV not found: %s", path)
        return None
    try:
        df = pd.read_csv(path)
        return df if len(df) > 0 else None
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


# ──────────────────────────────────────────────
#  Chart generators
# ──────────────────────────────────────────────


def generate_comparator_ranking_bars(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Horizontal bar chart of comparator rankings (pooled net_eppd)."""
    df = _read_csv_safe(tables_dir / "comparator_rankings.csv")
    if df is None:
        return False

    pooled = df[df["facet"] == "pooled"].sort_values("net_eppd", ascending=True)
    if len(pooled) == 0:
        return False

    fig, ax = plt.subplots(figsize=(8, max(3, len(pooled) * 0.5 + 1)))
    ax.barh(pooled["model"], pooled["net_eppd"], color="#4C72B0")

    # Add CI error bars if available
    if "ci_low" in pooled.columns and "ci_high" in pooled.columns:
        ci_low = pooled["net_eppd"] - pooled["ci_low"]
        ci_high = pooled["ci_high"] - pooled["net_eppd"]
        xerr = np.array(
            [
                np.maximum(ci_low.values, 0),
                np.maximum(ci_high.values, 0),
            ]
        )
        ax.errorbar(
            pooled["net_eppd"],
            pooled["model"],
            xerr=xerr,
            fmt="none",
            ecolor="black",
            capsize=3,
        )

    ax.set_xlabel("Net EPPD (pooled)")
    ax.set_title("Comparator Rankings")
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
    fig.tight_layout()
    _save_chart(fig, output_dir, "comparator_ranking_bars.png", dpi)
    return True


def generate_delta_bars_by_contract(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Bar chart of H2H deltas, grouped by model pair."""
    df = _read_csv_safe(tables_dir / "h2h_delta_matrix.csv")
    if df is None:
        return False

    # Filter out self-play
    cross = df[df["model_a"] != df["model_b"]].copy()
    if len(cross) == 0:
        return False

    cross["label"] = cross["model_a"] + " vs " + cross["model_b"]

    fig, ax = plt.subplots(figsize=(10, max(3, len(cross) * 0.4 + 1)))
    ax.barh(cross["label"], cross["net_eppd_delta"], color="#4C72B0")

    # Add CI error bars
    if "ci_low" in cross.columns and "ci_high" in cross.columns:
        ci_low = cross["net_eppd_delta"] - cross["ci_low"]
        ci_high = cross["ci_high"] - cross["net_eppd_delta"]
        xerr = np.array(
            [
                np.maximum(ci_low.values, 0),
                np.maximum(ci_high.values, 0),
            ]
        )
        ax.errorbar(
            cross["net_eppd_delta"],
            cross["label"],
            xerr=xerr,
            fmt="none",
            ecolor="black",
            capsize=3,
        )

    ax.set_xlabel("Net EPPD Delta (A - B)")
    ax.set_title("H2H Delta Bars")
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
    fig.tight_layout()
    _save_chart(fig, output_dir, "delta_bars_by_contract.png", dpi)
    return True


def generate_h2h_heatmap(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Heatmap of H2H delta matrix."""
    df = _read_csv_safe(tables_dir / "h2h_delta_matrix.csv")
    if df is None:
        return False

    # Build pivot table
    models = sorted(set(df["model_a"].tolist() + df["model_b"].tolist()))
    matrix = pd.DataFrame(0.0, index=models, columns=models)

    for _, row in df.iterrows():
        a = row["model_a"]
        b = row["model_b"]
        delta = row.get("net_eppd_delta")
        if delta is not None and pd.notna(delta):
            matrix.loc[a, b] = delta

    fig, ax = plt.subplots(figsize=(max(6, len(models) + 1), max(5, len(models))))
    im = ax.imshow(
        matrix.values,
        cmap="RdBu_r",
        aspect="auto",
        vmin=-max(abs(matrix.values.min()), abs(matrix.values.max())),
        vmax=max(abs(matrix.values.min()), abs(matrix.values.max())),
    )

    ax.set_xticks(range(len(models)))
    ax.set_yticks(range(len(models)))
    ax.set_xticklabels(models, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(models, fontsize=8)

    # Annotate cells
    for i in range(len(models)):
        for j in range(len(models)):
            val = matrix.values[i, j]
            if val != 0:
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=7)

    plt.colorbar(im, ax=ax, label="Net EPPD Delta")
    ax.set_title("H2H Delta Matrix")
    fig.tight_layout()
    _save_chart(fig, output_dir, "h2h_heatmap.png", dpi)
    return True


def generate_tail_risk_panel(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Bar chart of CVaR-5 for comparator rankings."""
    df = _read_csv_safe(tables_dir / "comparator_rankings.csv")
    if df is None:
        return False

    pooled = df[df["facet"] == "pooled"].sort_values("net_eppd", ascending=False)
    if len(pooled) == 0 or "net_cvar_5" not in pooled.columns:
        return False

    fig, ax = plt.subplots(figsize=(8, max(3, len(pooled) * 0.5 + 1)))
    ax.barh(pooled["model"], pooled["net_cvar_5"], color="#C44E52")
    ax.set_xlabel("Net CVaR-5% (pooled)")
    ax.set_title("Tail Risk: CVaR-5% by Model")
    ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
    fig.tight_layout()
    _save_chart(fig, output_dir, "tail_risk_panel.png", dpi)
    return True


def generate_bid_behavior_panel(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Multi-panel behavior chart (bid_rate, make_rate by contract type).

    Shows grouped bars with all contract types (suit/high/low/pooled) per model,
    preserving the contract-type faceting required by project conventions.
    """
    df = _read_csv_safe(tables_dir / "behavior_by_contract.csv")
    if df is None:
        return False

    if "contract" not in df.columns:
        return False

    models = sorted(df["model"].unique())
    contracts = sorted(df["contract"].unique())
    model_colors = _get_model_colors(models)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for panel_idx, (metric, title) in enumerate(
        [("bid_rate", "Bid Rate by Contract"), ("make_rate", "Make Rate by Contract")]
    ):
        ax = axes[panel_idx]
        if metric not in df.columns:
            _unavailable_panel(ax, title)
            continue
        x = np.arange(len(contracts))
        width = 0.8 / max(len(models), 1)
        for i, model in enumerate(models):
            vals = []
            for contract in contracts:
                sub = df[(df["model"] == model) & (df["contract"] == contract)]
                vals.append(sub[metric].iloc[0] if len(sub) > 0 else 0)
            offset = (i - len(models) / 2 + 0.5) * width
            ax.bar(x + offset, vals, width, label=model, color=model_colors[model])
        ax.set_xticks(x)
        ax.set_xticklabels(contracts, fontsize=8)
        ax.set_xlabel("Contract Type")
        ax.set_ylabel(metric.replace("_", " ").title())
        ax.set_title(title)
        ax.legend(fontsize=7, loc="best")

    fig.tight_layout()
    _save_chart(fig, output_dir, "bid_behavior_panel.png", dpi)
    return True


def generate_contract_mix_bars(
    tables_dir: Path,
    output_dir: Path,
    chart_data_dir: Path | None = None,
    dpi: int = 150,
) -> bool:
    """Bar chart of contract mix.

    Reads ``chart_data/contract_mix.csv`` when available (actual deal fractions
    by contract type). Falls back to ``behavior_summary.csv`` bid_rate if the
    dedicated contract_mix CSV is missing.
    """
    # Prefer contract_mix.csv from chart_data (actual mix fractions)
    mix_df = (
        _read_csv_safe(chart_data_dir / "contract_mix.csv") if chart_data_dir else None
    )
    if (
        mix_df is not None
        and "model" in mix_df.columns
        and "fraction" in mix_df.columns
    ):
        models = sorted(mix_df["model"].unique())
        contracts = sorted(mix_df["contract"].unique())
        mix_colors = {"suit": "#C44E52", "high": "#4C72B0", "low": "#55A868"}

        fig, ax = plt.subplots(figsize=(8, max(3, len(models) * 0.5 + 1)))
        x = np.arange(len(models))
        bottom = np.zeros(len(models))
        for contract in contracts:
            vals = []
            for model in models:
                sub = mix_df[
                    (mix_df["model"] == model) & (mix_df["contract"] == contract)
                ]
                vals.append(sub["fraction"].iloc[0] if len(sub) > 0 else 0)
            vals_arr = np.array(vals)
            ax.barh(
                x,
                vals_arr,
                left=bottom,
                label=contract.title(),
                color=mix_colors.get(contract, "#888888"),
            )
            bottom += vals_arr
        ax.set_yticks(x)
        ax.set_yticklabels(models, fontsize=8)
        ax.set_xlabel("Fraction of Deals")
        ax.set_title("Contract Mix by Model")
        ax.legend(fontsize=8)
        fig.tight_layout()
        _save_chart(fig, output_dir, "contract_mix_bars.png", dpi)
        return True

    # Fallback: bid_rate from behavior_summary.csv
    df = _read_csv_safe(tables_dir / "behavior_summary.csv")
    if df is None:
        return False

    comp = df[df["source"] == "comparator"] if "source" in df.columns else df
    if len(comp) == 0:
        comp = df

    fig, ax = plt.subplots(figsize=(8, max(3, len(comp) * 0.5 + 1)))
    ax.barh(comp["model"], comp["bid_rate"], color="#55A868", label="bid_rate")
    ax.set_xlabel("Bid Rate")
    ax.set_title("Bid Rate Summary (contract_mix.csv unavailable)")
    fig.tight_layout()
    _save_chart(fig, output_dir, "contract_mix_bars.png", dpi)
    return True


def generate_r2_by_contract(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Grouped bar chart of R² by contract and model."""
    df = _read_csv_safe(tables_dir / "model_performance.csv")
    if df is None:
        return False

    models = df["model"].unique()
    contracts = sorted(df["contract"].unique())

    x = np.arange(len(contracts))
    width = 0.8 / max(len(models), 1)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, model in enumerate(models):
        sub = df[df["model"] == model]
        r2_vals = []
        for c in contracts:
            csub = sub[sub["contract"] == c]
            r2_vals.append(csub["r_squared"].iloc[0] if len(csub) > 0 else 0)
        offset = (i - len(models) / 2 + 0.5) * width
        ax.bar(x + offset, r2_vals, width, label=model)

    ax.set_xlabel("Contract")
    ax.set_ylabel("R²")
    ax.set_title("R² by Contract and Model")
    ax.set_xticks(x)
    ax.set_xticklabels(contracts)
    ax.legend()
    ax.set_ylim(0, 1)
    fig.tight_layout()
    _save_chart(fig, output_dir, "r2_by_contract.png", dpi)
    return True


def generate_mae_by_contract(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Grouped bar chart of MAE by contract and model."""
    df = _read_csv_safe(tables_dir / "model_performance.csv")
    if df is None:
        return False

    models = df["model"].unique()
    contracts = sorted(df["contract"].unique())

    x = np.arange(len(contracts))
    width = 0.8 / max(len(models), 1)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, model in enumerate(models):
        sub = df[df["model"] == model]
        mae_vals = []
        for c in contracts:
            csub = sub[sub["contract"] == c]
            mae_vals.append(csub["mae"].iloc[0] if len(csub) > 0 else 0)
        offset = (i - len(models) / 2 + 0.5) * width
        ax.bar(x + offset, mae_vals, width, label=model)

    ax.set_xlabel("Contract")
    ax.set_ylabel("MAE")
    ax.set_title("MAE by Contract and Model")
    ax.set_xticks(x)
    ax.set_xticklabels(contracts)
    ax.legend()
    fig.tight_layout()
    _save_chart(fig, output_dir, "mae_by_contract.png", dpi)
    return True


def generate_outcome_summary(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Grouped bar chart of outcome summary metrics from chart_data CSV.

    This shows summary-level metrics (one value per model per contract facet),
    NOT per-deal distributions. The chart uses grouped bars with honest labeling.
    """
    df = _read_csv_safe(chart_data_dir / "outcome_summary.csv")
    if df is None:
        return False

    if (
        "model" not in df.columns
        or "contract" not in df.columns
        or "value" not in df.columns
    ):
        return False

    models = sorted(df["model"].unique())
    contracts = sorted(df["contract"].unique())
    model_colors = _get_model_colors(models)

    x = np.arange(len(contracts))
    width = 0.8 / max(len(models), 1)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, model in enumerate(models):
        vals = []
        for contract in contracts:
            sub = df[(df["model"] == model) & (df["contract"] == contract)]
            vals.append(sub["value"].iloc[0] if len(sub) > 0 else 0)
        offset = (i - len(models) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=model, color=model_colors[model])

    ax.set_xticks(x)
    ax.set_xticklabels(contracts, fontsize=9)
    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Metric Value")
    ax.set_title("Outcome Summary by Model and Contract")
    ax.legend(fontsize=8)
    ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    fig.tight_layout()
    _save_chart(fig, output_dir, "outcome_summary.png", dpi)
    return True


def generate_predictions_scatter(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Scatter plot of predicted vs actual values, faceted by contract.

    Reads chart_data/predictions.csv (columns: model, contract, prediction, actual).
    Produces charts/pred_vs_actual.png with 45-degree reference line.
    """
    df = _read_csv_safe(chart_data_dir / "predictions.csv")
    if df is None:
        return False

    required = {"model", "contract", "prediction", "actual"}
    if not required.issubset(df.columns):
        logger.warning(
            "predictions.csv missing required columns: %s", required - set(df.columns)
        )
        return False

    contracts = sorted(df["contract"].unique())
    n_contracts = max(len(contracts), 1)
    fig, axes = plt.subplots(
        1, n_contracts, figsize=(5 * n_contracts, 5), squeeze=False
    )

    for idx, contract in enumerate(contracts):
        ax = axes[0, idx]
        cdf = df[df["contract"] == contract]
        models = sorted(cdf["model"].unique())
        model_colors = _get_model_colors(models)

        for model in models:
            mdf = cdf[cdf["model"] == model]
            ax.scatter(
                mdf["actual"],
                mdf["prediction"],
                alpha=0.3,
                s=8,
                label=model,
                color=model_colors[model],
            )

        # 45-degree reference line
        all_vals = pd.concat([cdf["actual"], cdf["prediction"]])
        vmin, vmax = all_vals.min(), all_vals.max()
        ax.plot([vmin, vmax], [vmin, vmax], "k--", linewidth=0.8, alpha=0.5)
        ax.set_xlabel("Actual", fontsize=9)
        ax.set_ylabel("Predicted", fontsize=9)
        ax.set_title(f"{contract.title()}", fontsize=11)
        ax.legend(fontsize=7, loc="best")
        ax.set_aspect("equal", adjustable="box")

    fig.suptitle("Predicted vs Actual", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save_chart(fig, output_dir, "pred_vs_actual.png", dpi)
    return True


def generate_residuals_chart(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Histogram of residuals by contract type.

    Reads chart_data/residuals.csv (columns: model, contract, residual_bin, count).
    Produces charts/residual_distribution.png.
    """
    df = _read_csv_safe(chart_data_dir / "residuals.csv")
    if df is None:
        return False

    required = {"model", "contract", "residual_bin", "count"}
    if not required.issubset(df.columns):
        logger.warning(
            "residuals.csv missing required columns: %s", required - set(df.columns)
        )
        return False

    contracts = sorted(df["contract"].unique())
    n_contracts = max(len(contracts), 1)
    fig, axes = plt.subplots(
        1, n_contracts, figsize=(5 * n_contracts, 4), squeeze=False
    )

    for idx, contract in enumerate(contracts):
        ax = axes[0, idx]
        cdf = df[df["contract"] == contract]
        models = sorted(cdf["model"].unique())
        model_colors = _get_model_colors(models)

        for model in models:
            mdf = cdf[cdf["model"] == model].sort_values("residual_bin")
            ax.bar(
                mdf["residual_bin"],
                mdf["count"],
                width=(mdf["residual_bin"].diff().median() or 0.1) * 0.8,
                alpha=0.6,
                label=model,
                color=model_colors[model],
            )

        ax.set_xlabel("Residual (Pred - Actual)", fontsize=9)
        ax.set_ylabel("Count", fontsize=9)
        ax.set_title(f"{contract.title()}", fontsize=11)
        ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
        ax.legend(fontsize=7, loc="best")

    fig.suptitle("Residual Distribution", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save_chart(fig, output_dir, "residual_distribution.png", dpi)
    return True


def generate_calibration_curve(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Calibration curve (predicted vs actual mean) with 45-degree reference line.

    Reads chart_data/calibration_bins.csv
    (columns: model, contract, pred_bin, mean_pred, actual_mean, n_samples).
    Produces charts/calibration_curve.png.
    """
    df = _read_csv_safe(chart_data_dir / "calibration_bins.csv")
    if df is None:
        return False

    required = {"model", "contract", "mean_pred", "actual_mean"}
    if not required.issubset(df.columns):
        logger.warning(
            "calibration_bins.csv missing required columns: %s",
            required - set(df.columns),
        )
        return False

    contracts = sorted(df["contract"].unique())
    n_contracts = max(len(contracts), 1)
    fig, axes = plt.subplots(
        1, n_contracts, figsize=(5 * n_contracts, 5), squeeze=False
    )

    for idx, contract in enumerate(contracts):
        ax = axes[0, idx]
        cdf = df[df["contract"] == contract]
        models = sorted(cdf["model"].unique())
        model_colors = _get_model_colors(models)

        for model in models:
            mdf = cdf[cdf["model"] == model].sort_values("mean_pred")
            ax.plot(
                mdf["mean_pred"],
                mdf["actual_mean"],
                marker="o",
                markersize=4,
                label=model,
                color=model_colors[model],
            )

        # 45-degree reference line
        all_vals = pd.concat([cdf["mean_pred"], cdf["actual_mean"]])
        vmin, vmax = all_vals.min(), all_vals.max()
        ax.plot([vmin, vmax], [vmin, vmax], "k--", linewidth=0.8, alpha=0.5)
        ax.set_xlabel("Mean Predicted", fontsize=9)
        ax.set_ylabel("Mean Actual", fontsize=9)
        ax.set_title(f"{contract.title()}", fontsize=11)
        ax.legend(fontsize=7, loc="best")

    fig.suptitle("Calibration Curve", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save_chart(fig, output_dir, "calibration_curve.png", dpi)
    return True


def generate_feature_importance_chart(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Horizontal bar chart of top 15 features by importance.

    Reads chart_data/selection_paths.csv
    (columns: model, contract, rank, feature_name, importance).
    Produces charts/feature_importance.png.
    """
    df = _read_csv_safe(chart_data_dir / "selection_paths.csv")
    if df is None:
        return False

    required = {"model", "contract", "rank", "feature_name", "importance"}
    if not required.issubset(df.columns):
        logger.warning(
            "selection_paths.csv missing required columns: %s",
            required - set(df.columns),
        )
        return False

    # Aggregate across contracts: mean importance per feature per model
    models = sorted(df["model"].unique())
    n_models = max(len(models), 1)
    fig, axes = plt.subplots(1, n_models, figsize=(6 * n_models, 6), squeeze=False)

    for idx, model in enumerate(models):
        ax = axes[0, idx]
        mdf = df[df["model"] == model]

        # Aggregate: mean importance per feature across contracts
        agg = (
            mdf.groupby("feature_name")["importance"].mean().sort_values(ascending=True)
        )
        top = agg.tail(15)

        ax.barh(top.index, top.values, color="#4C72B0")
        ax.set_xlabel("Mean Importance", fontsize=9)
        ax.set_title(f"{model} — Top Features", fontsize=11)
        ax.tick_params(axis="y", labelsize=7)

    fig.suptitle("Feature Importance", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    _save_chart(fig, output_dir, "feature_importance.png", dpi)
    return True


def generate_seat_balance(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Seat balance chart from chart_data CSV."""
    df = _read_csv_safe(chart_data_dir / "seat_balance.csv")
    if df is None:
        return False

    fig, ax = plt.subplots(figsize=(8, 5))
    # Support both legacy schema (seat, value) and current schema
    # (seat, contract, mean_tricks, n_hands)
    value_col = None
    if "value" in df.columns:
        value_col = "value"
    elif "mean_tricks" in df.columns:
        value_col = "mean_tricks"

    if "seat" in df.columns and value_col is not None:
        seats = sorted(df["seat"].unique())
        data = [df[df["seat"] == s][value_col].values for s in seats]
        ax.boxplot(data, labels=[f"Seat {s}" for s in seats])
    else:
        ax.text(
            0.5,
            0.5,
            "Insufficient data for seat balance chart",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_ylabel("Value")
    ax.set_title("Seat Balance")
    fig.tight_layout()
    _save_chart(fig, output_dir, "seat_balance.png", dpi)
    return True


# ──────────────────────────────────────────────
#  Consistent color palette for models
# ──────────────────────────────────────────────

# Tableau-10 inspired palette for consistent model coloring across dashboards
_MODEL_COLORS = [
    "#4C72B0",
    "#DD8452",
    "#55A868",
    "#C44E52",
    "#8172B3",
    "#937860",
    "#DA8BC3",
    "#8C8C8C",
    "#CCB974",
    "#64B5CD",
]


def _get_model_colors(models: list[str]) -> dict[str, str]:
    """Return a consistent model-to-color mapping."""
    return {
        m: _MODEL_COLORS[i % len(_MODEL_COLORS)] for i, m in enumerate(sorted(models))
    }


def _unavailable_panel(ax: plt.Axes, label: str) -> None:
    """Render a 'data not available' placeholder in an axes."""
    ax.text(
        0.5,
        0.5,
        f"{label}\n\nData not available",
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=11,
        color="#888888",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


# ──────────────────────────────────────────────
#  Dashboard: Competitive
# ──────────────────────────────────────────────


def generate_dashboard_competitive(
    tables_dir: Path,
    output_dir: Path,
    chart_data_dir: Path | None = None,
    dpi: int = 150,
) -> bool:
    """Generate the competitive dashboard (2x2 grid).

    Panel 1: Comparator ranking bars with CIs
    Panel 2: H2H delta vs anchor by contract type
    Panel 3: H2H heatmap (model vs model win rates)
    Panel 4: Tail risk (CVaR by model)
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Competitive Dashboard", fontsize=16, fontweight="bold", y=0.98)

    # Panel 1: Comparator ranking bars with CIs
    ax = axes[0, 0]
    comp_df = _read_csv_safe(tables_dir / "comparator_rankings.csv")
    if comp_df is not None and "facet" in comp_df.columns:
        pooled = comp_df[comp_df["facet"] == "pooled"].sort_values(
            "net_eppd", ascending=True
        )
        if len(pooled) > 0:
            colors = _get_model_colors(pooled["model"].tolist())
            bar_colors = [colors[m] for m in pooled["model"]]
            ax.barh(pooled["model"], pooled["net_eppd"], color=bar_colors)
            if "ci_low" in pooled.columns and "ci_high" in pooled.columns:
                ci_low = pooled["net_eppd"] - pooled["ci_low"]
                ci_high = pooled["ci_high"] - pooled["net_eppd"]
                xerr = np.array(
                    [np.maximum(ci_low.values, 0), np.maximum(ci_high.values, 0)]
                )
                ax.errorbar(
                    pooled["net_eppd"],
                    pooled["model"],
                    xerr=xerr,
                    fmt="none",
                    ecolor="black",
                    capsize=3,
                )
            ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
            ax.set_xlabel("Net EPPD (pooled)", fontsize=9)
            ax.set_title("Comparator Rankings", fontsize=11)
        else:
            _unavailable_panel(ax, "Comparator Rankings")
    else:
        _unavailable_panel(ax, "Comparator Rankings")

    # Panel 2: H2H delta vs anchor by contract type
    ax = axes[0, 1]
    h2h_df = _read_csv_safe(tables_dir / "h2h_delta_matrix.csv")
    if h2h_df is not None and "facet" in h2h_df.columns:
        cross = h2h_df[h2h_df["model_a"] != h2h_df["model_b"]].copy()
        facets = [f for f in cross["facet"].unique() if f != "pooled"]
        if len(cross) > 0 and len(facets) > 0:
            models_in_data = sorted(cross["model_a"].unique())
            model_colors = _get_model_colors(models_in_data)
            x = np.arange(len(facets))
            width = 0.8 / max(len(models_in_data), 1)
            for i, model in enumerate(models_in_data):
                vals = []
                for facet in facets:
                    sub = cross[(cross["model_a"] == model) & (cross["facet"] == facet)]
                    vals.append(sub["net_eppd_delta"].mean() if len(sub) > 0 else 0)
                offset = (i - len(models_in_data) / 2 + 0.5) * width
                ax.bar(x + offset, vals, width, label=model, color=model_colors[model])
            ax.set_xticks(x)
            ax.set_xticklabels(facets, fontsize=8)
            ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
            ax.set_ylabel("Net EPPD Delta", fontsize=9)
            ax.set_title("H2H Delta by Contract", fontsize=11)
            ax.legend(fontsize=7, loc="best")
        else:
            _unavailable_panel(ax, "H2H Delta by Contract")
    else:
        _unavailable_panel(ax, "H2H Delta by Contract")

    # Panel 3: H2H heatmap
    ax = axes[1, 0]
    if h2h_df is not None:
        pooled_h2h = (
            h2h_df[h2h_df["facet"] == "pooled"] if "facet" in h2h_df.columns else h2h_df
        )
        models = sorted(
            set(pooled_h2h["model_a"].tolist() + pooled_h2h["model_b"].tolist())
        )
        if len(models) > 0:
            matrix = pd.DataFrame(0.0, index=models, columns=models)
            for _, row in pooled_h2h.iterrows():
                a, b = row["model_a"], row["model_b"]
                delta = row.get("net_eppd_delta")
                if delta is not None and pd.notna(delta):
                    matrix.loc[a, b] = delta
            vmax = max(abs(matrix.values.min()), abs(matrix.values.max()), 0.01)
            im = ax.imshow(
                matrix.values, cmap="RdBu_r", aspect="auto", vmin=-vmax, vmax=vmax
            )
            ax.set_xticks(range(len(models)))
            ax.set_yticks(range(len(models)))
            ax.set_xticklabels(models, rotation=45, ha="right", fontsize=7)
            ax.set_yticklabels(models, fontsize=7)
            for i in range(len(models)):
                for j in range(len(models)):
                    val = matrix.values[i, j]
                    if val != 0:
                        ax.text(
                            j, i, f"{val:.2f}", ha="center", va="center", fontsize=6
                        )
            plt.colorbar(im, ax=ax, label="Net EPPD Delta", shrink=0.8)
            ax.set_title("H2H Heatmap", fontsize=11)
        else:
            _unavailable_panel(ax, "H2H Heatmap")
    else:
        _unavailable_panel(ax, "H2H Heatmap")

    # Panel 4: Tail risk (CVaR by model)
    ax = axes[1, 1]
    if (
        comp_df is not None
        and "facet" in comp_df.columns
        and "net_cvar_5" in comp_df.columns
    ):
        pooled = comp_df[comp_df["facet"] == "pooled"].sort_values(
            "net_eppd", ascending=False
        )
        if len(pooled) > 0:
            colors = _get_model_colors(pooled["model"].tolist())
            bar_colors = [colors[m] for m in pooled["model"]]
            ax.barh(pooled["model"], pooled["net_cvar_5"], color=bar_colors)
            ax.axvline(x=0, color="gray", linestyle="--", linewidth=0.5)
            ax.set_xlabel("Net CVaR-5% (pooled)", fontsize=9)
            ax.set_title("Tail Risk: CVaR-5%", fontsize=11)
        else:
            _unavailable_panel(ax, "Tail Risk")
    else:
        _unavailable_panel(ax, "Tail Risk")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    _save_chart(fig, output_dir, "dashboard_competitive.png", dpi)
    return True


# ──────────────────────────────────────────────
#  Dashboard: Health
# ──────────────────────────────────────────────


def generate_dashboard_health(
    tables_dir: Path,
    output_dir: Path,
    chart_data_dir: Path | None = None,
    dpi: int = 150,
) -> bool:
    """Generate the health dashboard (2x2 grid).

    Panel 1: Bid rate / make rate by model
    Panel 2: Contract mix by model (mix_suit/high/low columns)
    Panel 3: Outcome distributions (if chart_data available)
    Panel 4: Bid-type breakdown (if behavior_by_bid_type.csv has data)
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Health Dashboard", fontsize=16, fontweight="bold", y=0.98)

    behavior_df = _read_csv_safe(tables_dir / "behavior_summary.csv")

    # Panel 1: Bid rate / make rate by model
    ax = axes[0, 0]
    if behavior_df is not None and "bid_rate" in behavior_df.columns:
        comp = (
            behavior_df[behavior_df["source"] == "comparator"]
            if "source" in behavior_df.columns
            else behavior_df
        )
        if len(comp) == 0:
            comp = behavior_df
        models = comp["model"].tolist()
        x = np.arange(len(models))
        width = 0.35
        bid_rates = comp["bid_rate"].values
        make_rates = (
            comp["make_rate"].values
            if "make_rate" in comp.columns
            else np.zeros(len(models))
        )
        ax.bar(x - width / 2, bid_rates, width, label="Bid Rate", color="#4C72B0")
        ax.bar(x + width / 2, make_rates, width, label="Make Rate", color="#55A868")
        ax.set_xticks(x)
        ax.set_xticklabels(models, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Rate", fontsize=9)
        ax.set_title("Bid Rate / Make Rate", fontsize=11)
        ax.legend(fontsize=8)
        ax.set_ylim(0, max(1.05, max(bid_rates.max(), make_rates.max()) * 1.05))
    else:
        _unavailable_panel(ax, "Bid Rate / Make Rate")

    # Panel 2: Contract mix by model
    ax = axes[0, 1]
    if behavior_df is not None:
        comp = (
            behavior_df[behavior_df["source"] == "comparator"]
            if "source" in behavior_df.columns
            else behavior_df
        )
        if len(comp) == 0:
            comp = behavior_df
        mix_cols = [c for c in ["mix_suit", "mix_high", "mix_low"] if c in comp.columns]
        if mix_cols:
            models = comp["model"].tolist()
            x = np.arange(len(models))
            mix_colors = {
                "mix_suit": "#C44E52",
                "mix_high": "#4C72B0",
                "mix_low": "#55A868",
            }
            bottom = np.zeros(len(models))
            for col in mix_cols:
                vals = comp[col].values
                label = col.replace("mix_", "").title()
                ax.bar(
                    x,
                    vals,
                    bottom=bottom,
                    label=label,
                    color=mix_colors.get(col, "#888888"),
                )
                bottom += vals
            ax.set_xticks(x)
            ax.set_xticklabels(models, rotation=45, ha="right", fontsize=7)
            ax.set_ylabel("Proportion", fontsize=9)
            ax.set_title("Contract Mix", fontsize=11)
            ax.legend(fontsize=8)
        else:
            _unavailable_panel(ax, "Contract Mix")
    else:
        _unavailable_panel(ax, "Contract Mix")

    # Panel 3: Outcome summary (grouped bar chart of summary metrics)
    ax = axes[1, 0]
    outcome_df = (
        _read_csv_safe(chart_data_dir / "outcome_summary.csv")
        if chart_data_dir
        else None
    )
    if (
        outcome_df is not None
        and "model" in outcome_df.columns
        and "contract" in outcome_df.columns
        and "value" in outcome_df.columns
    ):
        models = sorted(outcome_df["model"].unique())
        contracts = sorted(outcome_df["contract"].unique())
        model_colors = _get_model_colors(models)
        x = np.arange(len(contracts))
        width = 0.8 / max(len(models), 1)
        for i, model in enumerate(models):
            vals = []
            for contract in contracts:
                sub = outcome_df[
                    (outcome_df["model"] == model)
                    & (outcome_df["contract"] == contract)
                ]
                vals.append(sub["value"].iloc[0] if len(sub) > 0 else 0)
            offset = (i - len(models) / 2 + 0.5) * width
            ax.bar(x + offset, vals, width, label=model, color=model_colors[model])
        ax.set_xticks(x)
        ax.set_xticklabels(contracts, fontsize=8)
        ax.set_xlabel("Contract Type", fontsize=9)
        ax.set_ylabel("Metric Value", fontsize=9)
        ax.set_title("Outcome Summary", fontsize=11)
        ax.legend(fontsize=7, loc="best")
        ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.5)
    else:
        _unavailable_panel(ax, "Outcome Summary")

    # Panel 4: Bid-type breakdown
    # Filter to source == "comparator" to exclude h2h_self_play rows where
    # bid_rate is NaN (self-play data lacks meaningful bid_rate).
    ax = axes[1, 1]
    bid_type_df = _read_csv_safe(tables_dir / "behavior_by_bid_type.csv")
    if bid_type_df is not None and "bid_type" in bid_type_df.columns:
        if "source" in bid_type_df.columns:
            bid_type_df = bid_type_df[bid_type_df["source"] == "comparator"]
        if len(bid_type_df) == 0:
            _unavailable_panel(ax, "Bid-Type Breakdown")
        else:
            models = sorted(bid_type_df["model"].unique())
            bid_types = sorted(bid_type_df["bid_type"].unique())
            model_colors = _get_model_colors(models)
            x = np.arange(len(bid_types))
            width = 0.8 / max(len(models), 1)
            for i, model in enumerate(models):
                vals = []
                for bt in bid_types:
                    sub = bid_type_df[
                        (bid_type_df["model"] == model)
                        & (bid_type_df["bid_type"] == bt)
                    ]
                    val = (
                        sub["bid_rate"].iloc[0]
                        if len(sub) > 0 and "bid_rate" in sub.columns
                        else 0
                    )
                    # Handle NaN explicitly
                    vals.append(0 if pd.isna(val) else val)
                offset = (i - len(models) / 2 + 0.5) * width
                ax.bar(x + offset, vals, width, label=model, color=model_colors[model])
            ax.set_xticks(x)
            ax.set_xticklabels(bid_types, fontsize=8)
            ax.set_ylabel("Bid Rate", fontsize=9)
            ax.set_title("Bid-Type Breakdown (comparator)", fontsize=11)
            ax.legend(fontsize=7, loc="best")
    else:
        _unavailable_panel(ax, "Bid-Type Breakdown")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    _save_chart(fig, output_dir, "dashboard_health.png", dpi)
    return True


# ──────────────────────────────────────────────
#  Dashboard: Model Evaluation
# ──────────────────────────────────────────────


def generate_dashboard_model_eval(
    tables_dir: Path,
    output_dir: Path,
    chart_data_dir: Path | None = None,
    dpi: int = 150,
) -> bool:
    """Generate the model evaluation dashboard (2x2 grid).

    Panel 1: R-squared by model and contract
    Panel 2: MAE by model and contract
    Panel 3: Feature importance (from selection_paths.csv if available)
    Panel 4: Cross-rung progression (from cross_rung_deltas.csv if available)
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Model Evaluation Dashboard", fontsize=16, fontweight="bold", y=0.98)

    perf_df = _read_csv_safe(tables_dir / "model_performance.csv")

    # Panel 1: R-squared by model and contract
    ax = axes[0, 0]
    if perf_df is not None and "r_squared" in perf_df.columns:
        models = perf_df["model"].unique()
        contracts = sorted(perf_df["contract"].unique())
        model_colors = _get_model_colors(list(models))
        x = np.arange(len(contracts))
        width = 0.8 / max(len(models), 1)
        for i, model in enumerate(models):
            sub = perf_df[perf_df["model"] == model]
            r2_vals = []
            for c in contracts:
                csub = sub[sub["contract"] == c]
                r2_vals.append(csub["r_squared"].iloc[0] if len(csub) > 0 else 0)
            offset = (i - len(models) / 2 + 0.5) * width
            ax.bar(x + offset, r2_vals, width, label=model, color=model_colors[model])
        ax.set_xticks(x)
        ax.set_xticklabels(contracts, fontsize=8)
        ax.set_ylabel("R-squared", fontsize=9)
        ax.set_title("R-squared by Contract", fontsize=11)
        ax.legend(fontsize=7, loc="best")
        ax.set_ylim(0, 1)
    else:
        _unavailable_panel(ax, "R-squared by Contract")

    # Panel 2: MAE by model and contract
    ax = axes[0, 1]
    if perf_df is not None and "mae" in perf_df.columns:
        models = perf_df["model"].unique()
        contracts = sorted(perf_df["contract"].unique())
        model_colors = _get_model_colors(list(models))
        x = np.arange(len(contracts))
        width = 0.8 / max(len(models), 1)
        for i, model in enumerate(models):
            sub = perf_df[perf_df["model"] == model]
            mae_vals = []
            for c in contracts:
                csub = sub[sub["contract"] == c]
                mae_vals.append(csub["mae"].iloc[0] if len(csub) > 0 else 0)
            offset = (i - len(models) / 2 + 0.5) * width
            ax.bar(x + offset, mae_vals, width, label=model, color=model_colors[model])
        ax.set_xticks(x)
        ax.set_xticklabels(contracts, fontsize=8)
        ax.set_ylabel("MAE", fontsize=9)
        ax.set_title("MAE by Contract", fontsize=11)
        ax.legend(fontsize=7, loc="best")
    else:
        _unavailable_panel(ax, "MAE by Contract")

    # Panel 3: Feature importance / selection paths
    ax = axes[1, 0]
    sel_df = (
        _read_csv_safe(chart_data_dir / "selection_paths.csv")
        if chart_data_dir
        else None
    )
    if sel_df is not None and "step" in sel_df.columns and "oof_r2" in sel_df.columns:
        models = sorted(sel_df["model"].unique())
        for model in models:
            mdf = sel_df[sel_df["model"] == model]
            contracts = sorted(mdf["contract"].unique())
            for contract in contracts:
                cdf = mdf[mdf["contract"] == contract].sort_values("step")
                ax.plot(
                    cdf["step"],
                    cdf["oof_r2"],
                    marker="o",
                    markersize=3,
                    label=f"{model} ({contract})",
                )
        ax.set_xlabel("Features Added", fontsize=9)
        ax.set_ylabel("OOF R-squared", fontsize=9)
        ax.set_title("Selection Paths", fontsize=11)
        ax.legend(fontsize=6, loc="lower right")
        ax.grid(True, alpha=0.3)
    else:
        _unavailable_panel(ax, "Selection Paths")

    # Panel 4: Cross-rung progression
    ax = axes[1, 1]
    cross_rung_df = _read_csv_safe(tables_dir / "cross_rung_deltas.csv")
    if cross_rung_df is not None and "rung" in cross_rung_df.columns:
        metric_cols = [
            c
            for c in cross_rung_df.columns
            if c not in ("rung", "best_model", "advance_decision")
        ]
        if metric_cols:
            x = np.arange(len(cross_rung_df))
            rungs = cross_rung_df["rung"].tolist()
            key_metrics = [
                c
                for c in metric_cols
                if "h2h" in c or "comparator" in c or "win_rate" in c
            ][:4]
            if not key_metrics:
                key_metrics = metric_cols[:4]
            for metric in key_metrics:
                if metric in cross_rung_df.columns:
                    vals = pd.to_numeric(cross_rung_df[metric], errors="coerce")
                    ax.plot(x, vals, marker="o", label=metric, markersize=4)
            ax.set_xticks(x)
            ax.set_xticklabels(rungs, fontsize=8)
            ax.set_xlabel("Rung", fontsize=9)
            ax.set_ylabel("Value", fontsize=9)
            ax.set_title("Cross-Rung Progression", fontsize=11)
            ax.legend(fontsize=6, loc="best")
            ax.grid(True, alpha=0.3)
        else:
            _unavailable_panel(ax, "Cross-Rung Progression")
    else:
        _unavailable_panel(ax, "Cross-Rung Progression")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    _save_chart(fig, output_dir, "dashboard_model_eval.png", dpi)
    return True


def generate_all_charts(
    tables_dir: Path,
    output_dir: Path,
    chart_data_dir: Path | None = None,
    dpi: int = 150,
) -> list[str]:
    """Generate all rung report charts from canonical CSVs.

    Args:
        tables_dir: Path to CSV tables.
        output_dir: Path to write PNG charts.
        chart_data_dir: Path to chart data CSVs (optional).
        dpi: DPI for saved figures.

    Returns:
        List of generated chart filenames.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if chart_data_dir:
        chart_data_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    chart_generators = [
        (
            "comparator_ranking_bars.png",
            lambda: generate_comparator_ranking_bars(tables_dir, output_dir, dpi),
        ),
        (
            "delta_bars_by_contract.png",
            lambda: generate_delta_bars_by_contract(tables_dir, output_dir, dpi),
        ),
        ("h2h_heatmap.png", lambda: generate_h2h_heatmap(tables_dir, output_dir, dpi)),
        (
            "tail_risk_panel.png",
            lambda: generate_tail_risk_panel(tables_dir, output_dir, dpi),
        ),
        (
            "bid_behavior_panel.png",
            lambda: generate_bid_behavior_panel(tables_dir, output_dir, dpi),
        ),
        (
            "contract_mix_bars.png",
            lambda: generate_contract_mix_bars(
                tables_dir, output_dir, chart_data_dir, dpi
            ),
        ),
        (
            "r2_by_contract.png",
            lambda: generate_r2_by_contract(tables_dir, output_dir, dpi),
        ),
        (
            "mae_by_contract.png",
            lambda: generate_mae_by_contract(tables_dir, output_dir, dpi),
        ),
    ]

    for chart_name, gen_fn in chart_generators:
        try:
            if gen_fn():
                generated.append(chart_name)
        except Exception as e:
            logger.warning("Failed to generate %s: %s", chart_name, e)

    # Chart-data-dependent charts
    if chart_data_dir:
        chart_data_generators = [
            (
                "outcome_summary.png",
                lambda: generate_outcome_summary(chart_data_dir, output_dir, dpi),
            ),
            (
                "seat_balance.png",
                lambda: generate_seat_balance(chart_data_dir, output_dir, dpi),
            ),
            (
                "pred_vs_actual.png",
                lambda: generate_predictions_scatter(chart_data_dir, output_dir, dpi),
            ),
            (
                "residual_distribution.png",
                lambda: generate_residuals_chart(chart_data_dir, output_dir, dpi),
            ),
            (
                "calibration_curve.png",
                lambda: generate_calibration_curve(chart_data_dir, output_dir, dpi),
            ),
            (
                "feature_importance.png",
                lambda: generate_feature_importance_chart(
                    chart_data_dir, output_dir, dpi
                ),
            ),
        ]
        for chart_name, gen_fn in chart_data_generators:
            try:
                if gen_fn():
                    generated.append(chart_name)
            except Exception as e:
                logger.warning("Failed to generate %s: %s", chart_name, e)

    # Dashboard charts (composite multi-panel pages)
    dashboard_generators = [
        (
            "dashboard_competitive.png",
            lambda: generate_dashboard_competitive(
                tables_dir, output_dir, chart_data_dir, dpi
            ),
        ),
        (
            "dashboard_health.png",
            lambda: generate_dashboard_health(
                tables_dir, output_dir, chart_data_dir, dpi
            ),
        ),
        (
            "dashboard_model_eval.png",
            lambda: generate_dashboard_model_eval(
                tables_dir, output_dir, chart_data_dir, dpi
            ),
        ),
    ]
    for chart_name, gen_fn in dashboard_generators:
        try:
            if gen_fn():
                generated.append(chart_name)
        except Exception as e:
            logger.warning("Failed to generate %s: %s", chart_name, e)

    return generated


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate rung report charts from canonical CSV tables."
    )
    parser.add_argument(
        "--tables-dir",
        required=True,
        type=Path,
        help="Path to CSV tables directory",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write chart PNGs",
    )
    parser.add_argument(
        "--chart-data-dir",
        default=None,
        type=Path,
        help="Directory for chart source CSVs (optional)",
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

    generated = generate_all_charts(
        tables_dir=args.tables_dir,
        output_dir=args.output_dir,
        chart_data_dir=args.chart_data_dir,
        dpi=args.dpi,
    )
    logger.info("Generated %d charts: %s", len(generated), ", ".join(generated))


if __name__ == "__main__":
    main()
