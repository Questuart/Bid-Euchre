#!/usr/bin/env python
"""Generate rung report charts from canonical CSV tables.

CSV-first chart generation for Arc D v2 reports. Reads from tables/*.csv
and produces PNGs to charts/ plus source data to chart_data/.

This is the v2 chart generator that reads canonical CSVs instead of raw
run artifacts. The original generate_rung_charts.py reads eval JSONL and
model artifacts directly — that one remains available for legacy reports.

Usage:
    uv run python scripts/internal/generate_rung_charts_v2.py \\
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
  9.  outcome_distributions.png      — from chart_data/outcome_distributions.csv
  10. seat_balance.png               — from chart_data/seat_balance.csv
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
    """Multi-panel behavior chart (bid_rate, make_rate by contract)."""
    df = _read_csv_safe(tables_dir / "behavior_by_contract.csv")
    if df is None:
        return False

    models = df["model"].unique()
    fig, axes = plt.subplots(1, 2, figsize=(12, max(3, len(models) * 0.5 + 1)))

    # Bid rate panel
    ax = axes[0]
    for model in models:
        sub = df[df["model"] == model]
        ax.barh(model, sub["bid_rate"].iloc[0] if len(sub) > 0 else 0)
    ax.set_xlabel("Bid Rate")
    ax.set_title("Bid Rate by Model")

    # Make rate panel
    ax = axes[1]
    for model in models:
        sub = df[df["model"] == model]
        ax.barh(model, sub["make_rate"].iloc[0] if len(sub) > 0 else 0)
    ax.set_xlabel("Make Rate")
    ax.set_title("Make Rate by Model")

    fig.tight_layout()
    _save_chart(fig, output_dir, "bid_behavior_panel.png", dpi)
    return True


def generate_contract_mix_bars(
    tables_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Bar chart of contract mix from behavior summary."""
    df = _read_csv_safe(tables_dir / "behavior_summary.csv")
    if df is None:
        return False

    # Use comparator-sourced data
    comp = df[df["source"] == "comparator"]
    if len(comp) == 0:
        comp = df

    fig, ax = plt.subplots(figsize=(8, max(3, len(comp) * 0.5 + 1)))
    ax.barh(comp["model"], comp["bid_rate"], color="#55A868", label="bid_rate")
    ax.set_xlabel("Bid Rate")
    ax.set_title("Contract Mix / Bid Rate Summary")
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


def generate_outcome_distributions(
    chart_data_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> bool:
    """Outcome distribution chart from chart_data CSV."""
    df = _read_csv_safe(chart_data_dir / "outcome_distributions.csv")
    if df is None:
        return False

    fig, ax = plt.subplots(figsize=(10, 5))
    if "contract" in df.columns and "value" in df.columns:
        for contract in sorted(df["contract"].unique()):
            sub = df[df["contract"] == contract]
            ax.hist(sub["value"], bins=20, alpha=0.5, label=contract, density=True)
        ax.legend()
    else:
        ax.hist(df.iloc[:, 0], bins=20, alpha=0.7)

    ax.set_xlabel("Outcome Value")
    ax.set_ylabel("Density")
    ax.set_title("Outcome Distributions")
    fig.tight_layout()
    _save_chart(fig, output_dir, "outcome_distributions.png", dpi)
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
    if "seat" in df.columns and "value" in df.columns:
        seats = sorted(df["seat"].unique())
        data = [df[df["seat"] == s]["value"].values for s in seats]
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
            lambda: generate_contract_mix_bars(tables_dir, output_dir, dpi),
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
                "outcome_distributions.png",
                lambda: generate_outcome_distributions(chart_data_dir, output_dir, dpi),
            ),
            (
                "seat_balance.png",
                lambda: generate_seat_balance(chart_data_dir, output_dir, dpi),
            ),
        ]
        for chart_name, gen_fn in chart_data_generators:
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
