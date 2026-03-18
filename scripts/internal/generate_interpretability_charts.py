#!/usr/bin/env python
"""Generate interpretability charts from CSV data.

Reads interpretability CSVs from chart_data/ and produces PNG charts.

CLI:
    uv run python scripts/internal/generate_interpretability_charts.py \\
        --chart-data-dir /tmp/report/chart_data \\
        --output-dir /tmp/report/charts

Charts produced:
  - shap_summary.png          — horizontal bar of mean |SHAP| per feature, faceted by contract
  - shap_dependence_top5.png  — scatter plots of top-5 features vs SHAP values
  - selection_path.png        — line chart of R² vs features added (when selection_logs available)
  - feature_importance.png    — horizontal bar of feature importance by model/contract (fallback)
  - decision_agreement.png    — bar chart of pairwise agreement rates
  - disagreement_outcomes.png — bar chart of who wins in disagreements
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
        logger.info("CSV not found: %s", path)
        return None
    try:
        df = pd.read_csv(path)
        return df if len(df) > 0 else None
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def generate_shap_summary(ranking_df: pd.DataFrame, output_dir: Path) -> None:
    """Horizontal bar chart of mean |SHAP| per feature, faceted by contract."""
    contracts = sorted(ranking_df["contract"].unique())
    n_contracts = len(contracts)
    if n_contracts == 0:
        return

    fig, axes = plt.subplots(1, n_contracts, figsize=(5 * n_contracts, 8), sharey=False)
    if n_contracts == 1:
        axes = [axes]

    for ax, contract in zip(axes, contracts):
        cdf = ranking_df[ranking_df["contract"] == contract].copy()
        # Take top 15 features
        cdf = cdf.nsmallest(15, "rank")
        cdf = cdf.sort_values("mean_abs_shap", ascending=True)

        colors = ["#d73027" if d == "negative" else "#4575b4" for d in cdf["direction"]]
        ax.barh(cdf["feature"], cdf["mean_abs_shap"], color=colors)
        ax.set_xlabel("Mean |SHAP value|")
        ax.set_title(f"{contract}")

    fig.suptitle("SHAP Feature Importance by Contract", fontsize=14, y=1.02)
    fig.tight_layout()
    _save_chart(fig, output_dir, "shap_summary.png")


def generate_shap_dependence(dependence_df: pd.DataFrame, output_dir: Path) -> None:
    """Scatter plots of top-5 features vs SHAP values, faceted by contract."""
    contracts = sorted(dependence_df["contract"].unique())

    for contract in contracts:
        cdf = dependence_df[dependence_df["contract"] == contract]
        features = cdf["feature"].unique()[:5]
        n_features = len(features)
        if n_features == 0:
            continue

        fig, axes = plt.subplots(
            1, n_features, figsize=(4 * n_features, 4), squeeze=False
        )

        for i, feat in enumerate(features):
            ax = axes[0, i]
            fdf = cdf[cdf["feature"] == feat]
            ax.scatter(
                fdf["feature_value"],
                fdf["shap_value"],
                alpha=0.3,
                s=5,
                c="#4575b4",
            )
            ax.set_xlabel(feat)
            ax.set_ylabel("SHAP value" if i == 0 else "")
            ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")

        fig.suptitle(f"SHAP Dependence: {contract}", fontsize=12)
        fig.tight_layout()

    # Combine into single output
    if contracts:
        _save_chart(fig, output_dir, "shap_dependence_top5.png")


def _has_columns(df: pd.DataFrame, required: set[str]) -> bool:
    """Check whether *df* contains all *required* columns."""
    return required.issubset(df.columns)


# Column sets for the two selection_paths.csv schemas
_SELECTION_PATH_COLS = {"model", "step", "oof_r2"}
_FEATURE_IMPORTANCE_COLS = {"model", "contract", "rank", "feature_name", "importance"}


def generate_selection_path_chart(selection_df: pd.DataFrame, output_dir: Path) -> None:
    """Line chart of R² vs features added, one line per contract.

    Requires columns: model, contract, step, oof_r2.
    """
    models = sorted(selection_df["model"].unique())
    n_models = len(models)

    fig, axes = plt.subplots(
        1, max(n_models, 1), figsize=(6 * max(n_models, 1), 5), squeeze=False
    )

    for i, model in enumerate(models):
        ax = axes[0, i]
        mdf = selection_df[selection_df["model"] == model]
        contracts = sorted(mdf["contract"].unique())

        for contract in contracts:
            cdf = mdf[mdf["contract"] == contract].sort_values("step")
            ax.plot(
                cdf["step"], cdf["oof_r2"], marker="o", label=contract, markersize=4
            )

        ax.set_xlabel("Features Added")
        ax.set_ylabel("OOF R²")
        ax.set_title(f"Selection Path: {model}")
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_chart(fig, output_dir, "selection_path.png")


def generate_feature_importance_chart(
    importance_df: pd.DataFrame, output_dir: Path, *, top_n: int = 15
) -> None:
    """Horizontal bar chart of feature importance, faceted by model and contract.

    Requires columns: model, contract, rank, feature_name, importance.
    This is the fallback chart when forward-selection path data is unavailable
    and only static feature importances (e.g. GBT built-in) are present.
    """
    models = sorted(importance_df["model"].unique())
    contracts = sorted(importance_df["contract"].unique())
    n_cols = len(contracts)
    n_rows = len(models)
    if n_cols == 0 or n_rows == 0:
        return

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(5 * n_cols, max(4, 0.4 * top_n) * n_rows),
        squeeze=False,
    )

    for r, model in enumerate(models):
        mdf = importance_df[importance_df["model"] == model]
        for c, contract in enumerate(contracts):
            ax = axes[r, c]
            cdf = mdf[mdf["contract"] == contract].nsmallest(top_n, "rank")
            cdf = cdf.sort_values("importance", ascending=True)
            if cdf.empty:
                ax.set_visible(False)
                continue
            ax.barh(cdf["feature_name"], cdf["importance"], color="#4575b4")
            ax.set_xlabel("Importance")
            if c == 0:
                ax.set_ylabel(model)
            ax.set_title(f"{contract}")

    fig.suptitle("Feature Importance by Model and Contract", fontsize=14, y=1.02)
    fig.tight_layout()
    _save_chart(fig, output_dir, "feature_importance.png")


def generate_decision_agreement_chart(
    comparison_df: pd.DataFrame, output_dir: Path
) -> None:
    """Bar chart of pairwise agreement rates by contract."""
    if comparison_df.empty:
        return

    contracts = sorted(comparison_df["contract"].unique())

    fig, ax = plt.subplots(
        figsize=(max(6, 3 * len(comparison_df["model_a"].unique())), 5)
    )

    colors = {"suit": "#d73027", "high": "#4575b4", "low": "#91bfdb"}

    # Group by pair
    unique_pairs = comparison_df.apply(
        lambda r: f"{r['model_a']} vs {r['model_b']}", axis=1
    ).unique()

    bar_positions = []
    bar_values = []
    bar_colors = []
    bar_labels = []
    tick_positions = []
    tick_labels_list = []

    pos = 0
    for pair_name in unique_pairs:
        pair_start = pos
        for contract in contracts:
            mask = (
                comparison_df.apply(
                    lambda r: f"{r['model_a']} vs {r['model_b']}", axis=1
                )
                == pair_name
            ) & (comparison_df["contract"] == contract)
            rows = comparison_df[mask]
            if len(rows) > 0:
                bar_positions.append(pos)
                bar_values.append(rows.iloc[0]["agreement_rate"])
                bar_colors.append(colors.get(contract, "#999999"))
                bar_labels.append(contract)
                pos += 1
        tick_positions.append((pair_start + pos - 1) / 2)
        tick_labels_list.append(pair_name.replace(" vs ", "\nvs\n"))
        pos += 0.5

    ax.bar(bar_positions, bar_values, color=bar_colors, width=0.7)
    ax.set_ylabel("Agreement Rate")
    ax.set_title("Decision Agreement Between Models")
    ax.set_ylim(0, 1.05)

    if tick_positions:
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels_list, fontsize=8)

    # Legend for contracts
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=colors.get(c, "#999999"), label=c) for c in contracts
    ]
    ax.legend(handles=legend_elements, loc="lower left")

    fig.tight_layout()
    _save_chart(fig, output_dir, "decision_agreement.png")


def generate_disagreement_outcomes_chart(
    disagreement_df: pd.DataFrame, output_dir: Path
) -> None:
    """Stacked bar chart showing who wins in disagreements."""
    if disagreement_df.empty:
        return

    fig, ax = plt.subplots(figsize=(max(6, 2 * len(disagreement_df)), 5))

    labels = disagreement_df.apply(
        lambda r: f"{r['model_a']}\nvs {r['model_b']}\n({r['contract']})", axis=1
    )
    x = np.arange(len(labels))

    ax.bar(
        x,
        disagreement_df["a_better_pct"],
        label="Model A higher bid",
        color="#d73027",
    )
    ax.bar(
        x,
        disagreement_df["tie_pct"],
        bottom=disagreement_df["a_better_pct"],
        label="Tie",
        color="#ffffbf",
    )
    ax.bar(
        x,
        disagreement_df["b_better_pct"],
        bottom=disagreement_df["a_better_pct"] + disagreement_df["tie_pct"],
        label="Model B higher bid",
        color="#4575b4",
    )

    ax.set_ylabel("Proportion")
    ax.set_title("Disagreement Outcomes")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=0)
    ax.legend(loc="upper right")
    ax.set_ylim(0, 1.05)

    fig.tight_layout()
    _save_chart(fig, output_dir, "disagreement_outcomes.png")


def run(chart_data_dir: Path, output_dir: Path) -> list[str]:
    """Generate all interpretability charts from CSV data.

    Returns list of chart filenames generated.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    # SHAP summary
    ranking_df = _read_csv_safe(chart_data_dir / "shap_feature_ranking.csv")
    if ranking_df is not None:
        generate_shap_summary(ranking_df, output_dir)
        generated.append("shap_summary.png")

    # SHAP dependence
    dep_df = _read_csv_safe(chart_data_dir / "shap_dependence.csv")
    if dep_df is not None:
        generate_shap_dependence(dep_df, output_dir)
        generated.append("shap_dependence_top5.png")

    # Selection paths / feature importance
    # tables.py may write selection_paths.csv with either:
    #   (a) step/oof_r2 columns (forward-selection path) → line chart
    #   (b) rank/feature_name/importance columns (static importance) → bar chart
    # Also check feature_importances.csv (canonical name for schema b).
    sel_df = _read_csv_safe(chart_data_dir / "selection_paths.csv")
    fi_df = _read_csv_safe(chart_data_dir / "feature_importances.csv")

    if sel_df is not None and _has_columns(sel_df, _SELECTION_PATH_COLS):
        generate_selection_path_chart(sel_df, output_dir)
        generated.append("selection_path.png")
    elif fi_df is not None and _has_columns(fi_df, _FEATURE_IMPORTANCE_COLS):
        generate_feature_importance_chart(fi_df, output_dir)
        generated.append("feature_importance.png")
    elif sel_df is not None and _has_columns(sel_df, _FEATURE_IMPORTANCE_COLS):
        # selection_paths.csv contains importance data (legacy schema mismatch)
        generate_feature_importance_chart(sel_df, output_dir)
        generated.append("feature_importance.png")
    elif sel_df is not None:
        logger.warning(
            "selection_paths.csv has unexpected columns %s; skipping chart",
            list(sel_df.columns),
        )

    # Decision agreement
    comp_df = _read_csv_safe(chart_data_dir / "decision_comparison.csv")
    if comp_df is not None:
        generate_decision_agreement_chart(comp_df, output_dir)
        generated.append("decision_agreement.png")

    # Disagreement outcomes
    disagree_df = _read_csv_safe(chart_data_dir / "disagreement_outcomes.csv")
    if disagree_df is not None:
        generate_disagreement_outcomes_chart(disagree_df, output_dir)
        generated.append("disagreement_outcomes.png")

    return generated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate interpretability charts from CSV data"
    )
    parser.add_argument(
        "--chart-data-dir",
        type=Path,
        required=True,
        help="Directory containing interpretability CSVs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for chart PNGs",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    charts = run(args.chart_data_dir, args.output_dir)
    if charts:
        print(f"\nGenerated {len(charts)} charts:")
        for name in charts:
            print(f"  {name}")
    else:
        print("\nNo charts generated (missing CSV data)")


if __name__ == "__main__":
    main()
