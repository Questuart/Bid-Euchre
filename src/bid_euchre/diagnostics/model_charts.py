"""Model diagnostic charts for Arc D evaluation.

Provides charts for analyzing model prediction quality, dual-arm comparisons,
and calibration from evaluation results. All functions return Figure objects.
"""

from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..reporting.style import (
    BASE_COLORS,
    FIGSIZE_COMPARISON,
    FIGSIZE_SINGLE_PLOT,
    apply_report_style,
    apply_seaborn_style,
    get_contract_color,
    get_contract_label,
)

try:
    import seaborn as sns  # noqa: F401

    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


def _cycle_base_colors(n: int) -> List[str]:
    """Cycle through BASE_COLORS to get n colors."""
    return [BASE_COLORS[i % len(BASE_COLORS)] for i in range(n)]


def _apply_style() -> None:
    if HAS_SEABORN:
        apply_seaborn_style()
    else:
        apply_report_style()


def plot_model_diagnostics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    contract_types: np.ndarray,
    figsize: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot model prediction diagnostics: scatter, residuals, heteroscedasticity.

    Creates a 1x3 figure assessing prediction quality per contract type.

    Parameters
    ----------
    y_true:
        Array of true values (e.g., tricks_won).
    y_pred:
        Array of predicted values (same length as y_true).
    contract_types:
        Array of contract type labels (same length as y_true).
    figsize:
        Figure size tuple. Defaults to ``FIGSIZE_COMPARISON``.
    title:
        Optional suptitle override.

    Returns
    -------
    plt.Figure
        A 1x3 figure with predicted vs actual scatter, residual distribution,
        and residuals vs predicted panels.
    """
    _apply_style()
    figsize = figsize or FIGSIZE_COMPARISON

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    contract_types = np.asarray(contract_types)

    fig, axes = plt.subplots(1, 3, figsize=figsize)

    if len(y_true) == 0:
        axes[0].text(
            0.5,
            0.5,
            "No data provided",
            ha="center",
            va="center",
            transform=axes[0].transAxes,
        )
        for ax in axes[1:]:
            ax.set_visible(False)
        plt.tight_layout()
        return fig

    residuals = y_true - y_pred
    unique_contracts = sorted(set(contract_types))
    contract_order = ["suit", "high", "low"]
    present = [ct for ct in contract_order if ct in unique_contracts]
    # Add any contract types not in the standard order
    for ct in unique_contracts:
        if ct not in present:
            present.append(ct)

    # ---- Panel 1: Predicted vs Actual scatter ----
    ax = axes[0]
    for ct in present:
        mask = contract_types == ct
        if not np.any(mask):
            continue
        color = get_contract_color(ct)
        label_str = get_contract_label(ct)

        # Compute R² for this contract
        yt = y_true[mask]
        yp = y_pred[mask]
        ss_res = np.sum((yt - yp) ** 2)
        ss_tot = np.sum((yt - np.mean(yt)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

        ax.scatter(
            yp,
            yt,
            alpha=0.3,
            s=10,
            c=color,
            label=f"{label_str} (R²={r2:.3f})",
        )

    # y = x reference line
    all_vals = np.concatenate([y_true, y_pred])
    val_min, val_max = np.min(all_vals), np.max(all_vals)
    margin = (val_max - val_min) * 0.05
    ax.plot(
        [val_min - margin, val_max + margin],
        [val_min - margin, val_max + margin],
        "k--",
        linewidth=1,
        alpha=0.5,
        label="y = x",
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title("Predicted vs Actual")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(True, alpha=0.3)

    # ---- Panel 2: Residual distribution histograms ----
    ax = axes[1]
    for ct in present:
        mask = contract_types == ct
        if not np.any(mask):
            continue
        color = get_contract_color(ct)
        label_str = get_contract_label(ct)
        ct_residuals = residuals[mask]

        ax.hist(
            ct_residuals,
            bins=30,
            alpha=0.5,
            color=color,
            label=f"{label_str} (mean={np.mean(ct_residuals):.2f})",
            edgecolor="black",
            linewidth=0.3,
        )

    ax.axvline(0, color="black", linestyle="-", linewidth=1.5)
    ax.set_xlabel("Residual (Actual - Predicted)")
    ax.set_ylabel("Count")
    ax.set_title("Residual Distribution")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3, axis="y")

    # ---- Panel 3: Residuals vs Predicted ----
    ax = axes[2]
    for ct in present:
        mask = contract_types == ct
        if not np.any(mask):
            continue
        color = get_contract_color(ct)
        label_str = get_contract_label(ct)

        ax.scatter(
            y_pred[mask],
            residuals[mask],
            alpha=0.3,
            s=10,
            c=color,
            label=label_str,
        )

    ax.axhline(0, color="black", linestyle="-", linewidth=1.5)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Residual (Actual - Predicted)")
    ax.set_title("Residuals vs Predicted")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    fig.suptitle(title or "Model Diagnostics", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig


def plot_dual_arm_comparison(
    metrics_dict: Dict[str, Dict[str, float]],
    figsize: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot dual-arm metric comparison for Arc D evaluation.

    Creates a 1x2 figure comparing key metrics across arms (e.g., OLSa vs OLSa_Full).

    Parameters
    ----------
    metrics_dict:
        Dict mapping arm name to a metrics dict. Example::

            {
                "OLSa": {"net_eppd": 1.6, "make_rate": 0.7, "r2_by_contract": {"suit": 0.3}},
                "OLSa_Full": {"net_eppd": 1.5, "make_rate": 0.72},
            }

        If a ``r2_by_contract`` key exists in any arm's metrics, Panel 2 shows
        per-contract R² comparison. Otherwise Panel 2 is hidden.
    figsize:
        Figure size tuple. Defaults to ``FIGSIZE_COMPARISON``.
    title:
        Optional suptitle override.

    Returns
    -------
    plt.Figure
        A 1x2 figure with grouped bar chart of key metrics and optional
        per-contract R² comparison.
    """
    _apply_style()
    figsize = figsize or FIGSIZE_COMPARISON

    if not metrics_dict:
        fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE_PLOT)
        ax.text(0.5, 0.5, "No metrics provided", ha="center", va="center")
        return fig

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    arms = list(metrics_dict.keys())
    arm_colors = _cycle_base_colors(len(arms))

    # ---- Panel 1: Grouped bar chart of scalar metrics ----
    ax = axes[0]

    # Collect all scalar metric keys (exclude r2_by_contract)
    all_metric_keys = set()
    for arm_metrics in metrics_dict.values():
        for k, v in arm_metrics.items():
            if k != "r2_by_contract" and isinstance(v, (int, float)):
                all_metric_keys.add(k)

    metric_keys = sorted(all_metric_keys)

    if metric_keys:
        n_metrics = len(metric_keys)
        n_arms = len(arms)
        bar_width = 0.8 / n_arms
        x = np.arange(n_metrics)

        for i, arm in enumerate(arms):
            arm_metrics = metrics_dict[arm]
            values = [arm_metrics.get(k, 0.0) for k in metric_keys]
            offset = (i - (n_arms - 1) / 2) * bar_width
            bars = ax.bar(
                x + offset,
                values,
                bar_width,
                label=arm,
                color=arm_colors[i],
                alpha=0.8,
            )
            # Annotate
            for bar, val in zip(bars, values):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{val:.3f}",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )

        ax.set_xticks(x)
        ax.set_xticklabels(metric_keys, rotation=45, ha="right")
        ax.set_ylabel("Value")
        ax.set_title("Metric Comparison")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")
    else:
        ax.text(
            0.5,
            0.5,
            "No scalar metrics found",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    # ---- Panel 2: Per-contract R² comparison (if available) ----
    ax = axes[1]
    has_r2 = any("r2_by_contract" in m for m in metrics_dict.values())

    if has_r2:
        # Collect all contract types
        all_contracts = set()
        for arm_metrics in metrics_dict.values():
            r2_dict = arm_metrics.get("r2_by_contract", {})
            all_contracts.update(r2_dict.keys())

        contract_order = ["suit", "high", "low"]
        contracts = [ct for ct in contract_order if ct in all_contracts]
        for ct in sorted(all_contracts):
            if ct not in contracts:
                contracts.append(ct)

        if contracts:
            n_contracts = len(contracts)
            bar_width = 0.8 / len(arms)
            x = np.arange(n_contracts)

            for i, arm in enumerate(arms):
                r2_dict = metrics_dict[arm].get("r2_by_contract", {})
                values = [r2_dict.get(ct, 0.0) for ct in contracts]
                offset = (i - (len(arms) - 1) / 2) * bar_width
                bars = ax.bar(
                    x + offset,
                    values,
                    bar_width,
                    label=arm,
                    color=arm_colors[i],
                    alpha=0.8,
                )
                for bar, val in zip(bars, values):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        f"{val:.3f}",
                        ha="center",
                        va="bottom",
                        fontsize=7,
                    )

            contract_labels = [get_contract_label(ct) for ct in contracts]
            ax.set_xticks(x)
            ax.set_xticklabels(contract_labels)
            ax.set_ylabel("R²")
            ax.set_title("R² by Contract Type")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3, axis="y")
        else:
            ax.set_visible(False)
    else:
        ax.set_visible(False)

    fig.suptitle(title or "Dual-Arm Comparison", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig


def plot_calibration_curve(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    contract_types: np.ndarray,
    n_bins: int = 10,
    figsize: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot calibration curve and prediction distribution.

    Creates a 1x2 figure assessing prediction calibration by comparing
    predicted vs actual means per bin.

    Parameters
    ----------
    y_true:
        Array of true values.
    y_pred:
        Array of predicted values (same length as y_true).
    contract_types:
        Array of contract type labels (same length as y_true).
    n_bins:
        Number of bins for the calibration curve (default 10).
    figsize:
        Figure size tuple. Defaults to ``FIGSIZE_COMPARISON``.
    title:
        Optional suptitle override.

    Returns
    -------
    plt.Figure
        A 1x2 figure with calibration curve and prediction distribution histogram.
    """
    _apply_style()
    figsize = figsize or FIGSIZE_COMPARISON

    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    contract_types = np.asarray(contract_types)

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    if len(y_true) == 0:
        axes[0].text(
            0.5,
            0.5,
            "No data provided",
            ha="center",
            va="center",
            transform=axes[0].transAxes,
        )
        axes[1].set_visible(False)
        plt.tight_layout()
        return fig

    unique_contracts = sorted(set(contract_types))
    contract_order = ["suit", "high", "low"]
    present = [ct for ct in contract_order if ct in unique_contracts]
    for ct in unique_contracts:
        if ct not in present:
            present.append(ct)

    # ---- Panel 1: Calibration curve ----
    ax = axes[0]

    for ct in present:
        mask = contract_types == ct
        if not np.any(mask):
            continue

        yt = y_true[mask]
        yp = y_pred[mask]
        color = get_contract_color(ct)
        label_str = get_contract_label(ct)

        if len(yp) < n_bins:
            # Too few points for binning; just plot overall mean
            ax.scatter(
                [np.mean(yp)],
                [np.mean(yt)],
                color=color,
                s=60,
                marker="D",
                label=label_str,
            )
            continue

        # Bin predictions and compute mean actual per bin
        try:
            bin_indices = pd.qcut(yp, q=n_bins, labels=False, duplicates="drop")
        except ValueError:
            # All predictions identical or insufficient unique values
            ax.scatter(
                [np.mean(yp)],
                [np.mean(yt)],
                color=color,
                s=60,
                marker="D",
                label=label_str,
            )
            continue

        bin_pred_means = []
        bin_true_means = []
        for b in sorted(set(bin_indices)):
            bin_mask = bin_indices == b
            bin_pred_means.append(np.mean(yp[bin_mask]))
            bin_true_means.append(np.mean(yt[bin_mask]))

        ax.plot(
            bin_pred_means,
            bin_true_means,
            "o-",
            color=color,
            linewidth=2,
            markersize=5,
            label=label_str,
        )

    # Reference line y = x
    all_vals = np.concatenate([y_true, y_pred])
    val_min, val_max = np.min(all_vals), np.max(all_vals)
    margin = (val_max - val_min) * 0.05
    ax.plot(
        [val_min - margin, val_max + margin],
        [val_min - margin, val_max + margin],
        "k--",
        linewidth=1,
        alpha=0.5,
        label="Perfect calibration",
    )
    ax.set_xlabel("Mean Predicted")
    ax.set_ylabel("Mean Actual")
    ax.set_title("Calibration Curve")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3)

    # ---- Panel 2: Prediction distribution histogram ----
    ax = axes[1]
    for ct in present:
        mask = contract_types == ct
        if not np.any(mask):
            continue
        color = get_contract_color(ct)
        label_str = get_contract_label(ct)

        ax.hist(
            y_pred[mask],
            bins=30,
            alpha=0.5,
            color=color,
            label=label_str,
            edgecolor="black",
            linewidth=0.3,
        )

    ax.set_xlabel("Predicted Value")
    ax.set_ylabel("Count")
    ax.set_title("Prediction Distribution")
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle(title or "Calibration Diagnostics", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig
