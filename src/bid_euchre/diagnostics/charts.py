"""Diagnostic chart functions for bidless simulation analysis.

Provides matplotlib/seaborn-based visualizations for exploring
bidless datasets. All functions return Figure objects for flexibility.
"""

from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Try to import seaborn, fall back gracefully
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


# Color schemes
SEAT_COLORS = ["#3498db", "#e74c3c", "#2ecc71", "#9b59b6"]  # Blue, Red, Green, Purple
CONTRACT_COLORS = {
    "suit": "#3498db",
    "high": "#e74c3c",
    "low": "#2ecc71",
}
TRUMP_COLORS = {
    "C": "#2c3e50",  # Clubs - dark gray
    "D": "#e67e22",  # Diamonds - orange
    "H": "#c0392b",  # Hearts - red
    "S": "#34495e",  # Spades - dark blue-gray
}


def plot_hand_value_by_seat(
    df: pd.DataFrame,
    figsize: Tuple[int, int] = (10, 6),
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot hand_value distribution by seat.

    Creates box plots showing hand_value distribution for each seat (0-3).
    Used to detect dealing bias or per-seat feature computation bugs.

    Args:
        df: DataFrame with 'seat' and 'feat_hand_value' columns
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if "feat_hand_value" not in df.columns:
        ax.text(0.5, 0.5, "feat_hand_value column not found",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    # Prepare data by seat
    seats = sorted(df["seat"].unique())
    data = [df[df["seat"] == s]["feat_hand_value"].values for s in seats]

    if HAS_SEABORN:
        sns.boxplot(data=df, x="seat", y="feat_hand_value", ax=ax, palette=SEAT_COLORS)
    else:
        bp = ax.boxplot(data, labels=[f"Seat {s}" for s in seats], patch_artist=True)
        for patch, color in zip(bp["boxes"], SEAT_COLORS):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

    ax.set_xlabel("Seat")
    ax.set_ylabel("Hand Value")
    ax.set_title(title or "Hand Value Distribution by Seat")
    ax.grid(True, alpha=0.3, axis="y")

    # Add mean markers
    means = [np.mean(d) for d in data]
    ax.scatter(range(len(means)), means, color="black", marker="D", s=50, zorder=5, label="Mean")
    ax.legend()

    plt.tight_layout()
    return fig


def plot_hand_value_by_contract(
    df: pd.DataFrame,
    figsize: Tuple[int, int] = (12, 6),
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot hand_value distribution by contract type.

    Creates box plots comparing hand_value across suit/high/low contracts.

    Args:
        df: DataFrame with 'contract_type' and 'feat_hand_value' columns
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if "feat_hand_value" not in df.columns or "contract_type" not in df.columns:
        ax.text(0.5, 0.5, "Required columns not found",
                ha="center", va="center", transform=ax.transAxes)
        return fig

    contracts = sorted(df["contract_type"].unique())
    colors = [CONTRACT_COLORS.get(c, "#95a5a6") for c in contracts]

    if HAS_SEABORN:
        sns.boxplot(
            data=df, x="contract_type", y="feat_hand_value", ax=ax,
            order=contracts, palette=colors
        )
    else:
        data = [df[df["contract_type"] == c]["feat_hand_value"].values for c in contracts]
        bp = ax.boxplot(data, labels=contracts, patch_artist=True)
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Hand Value")
    ax.set_title(title or "Hand Value Distribution by Contract Type")
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    return fig


def plot_feature_distributions(
    df: pd.DataFrame,
    features: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (14, 10),
    ncols: int = 3,
) -> plt.Figure:
    """Plot histograms of multiple features in a grid.

    Args:
        df: DataFrame with feat_* columns
        features: List of feature names (without feat_ prefix) to plot.
                  If None, plots top 9 features by variance.
        figsize: Figure size tuple
        ncols: Number of columns in grid

    Returns:
        matplotlib Figure
    """
    # Get feature columns
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    if not feat_cols:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No feature columns found", ha="center", va="center")
        return fig

    # Select features to plot
    if features:
        plot_cols = [f"feat_{f}" for f in features if f"feat_{f}" in df.columns]
    else:
        # Top 9 by variance
        variances = {c: df[c].var() for c in feat_cols if df[c].dtype in [np.float64, np.int64]}
        sorted_cols = sorted(variances, key=variances.get, reverse=True)
        plot_cols = sorted_cols[:9]

    if not plot_cols:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No numeric features to plot", ha="center", va="center")
        return fig

    nrows = (len(plot_cols) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    axes = np.atleast_2d(axes)

    for idx, col in enumerate(plot_cols):
        row, col_idx = idx // ncols, idx % ncols
        ax = axes[row, col_idx]

        values = df[col].dropna()
        ax.hist(values, bins=30, color="#3498db", alpha=0.7, edgecolor="black")
        ax.set_xlabel(col.replace("feat_", ""))
        ax.set_ylabel("Count")
        ax.axvline(values.mean(), color="red", linestyle="--", label=f"Mean: {values.mean():.2f}")
        ax.legend(fontsize=8)

    # Hide empty subplots
    for idx in range(len(plot_cols), nrows * ncols):
        row, col_idx = idx // ncols, idx % ncols
        axes[row, col_idx].set_visible(False)

    fig.suptitle("Feature Distributions", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig


def plot_feature_correlation(
    df: pd.DataFrame,
    features: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (10, 8),
) -> plt.Figure:
    """Plot feature correlation heatmap.

    Args:
        df: DataFrame with feat_* columns
        features: List of feature names to include (without feat_ prefix).
                  If None, uses top 10 features by variance.
        figsize: Figure size tuple

    Returns:
        matplotlib Figure
    """
    # Get feature columns
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    numeric_cols = [c for c in feat_cols if df[c].dtype in [np.float64, np.int64, np.float32, np.int32]]

    if not numeric_cols:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No numeric features found", ha="center", va="center")
        return fig

    # Select features
    if features:
        plot_cols = [f"feat_{f}" for f in features if f"feat_{f}" in numeric_cols]
    else:
        variances = {c: df[c].var() for c in numeric_cols}
        sorted_cols = sorted(variances, key=variances.get, reverse=True)
        plot_cols = sorted_cols[:10]

    if len(plot_cols) < 2:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "Need at least 2 features for correlation", ha="center", va="center")
        return fig

    # Compute correlation matrix
    corr = df[plot_cols].corr()

    fig, ax = plt.subplots(figsize=figsize)

    if HAS_SEABORN:
        sns.heatmap(
            corr, annot=True, fmt=".2f", cmap="coolwarm",
            center=0, ax=ax, vmin=-1, vmax=1,
            xticklabels=[c.replace("feat_", "") for c in plot_cols],
            yticklabels=[c.replace("feat_", "") for c in plot_cols],
        )
    else:
        im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1, aspect="auto")
        fig.colorbar(im, ax=ax, label="Correlation")

        # Labels
        labels = [c.replace("feat_", "") for c in plot_cols]
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)

        # Annotate
        for i in range(len(plot_cols)):
            for j in range(len(plot_cols)):
                val = corr.iloc[i, j]
                color = "white" if abs(val) > 0.5 else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=8)

    ax.set_title("Feature Correlation Matrix")
    plt.tight_layout()
    return fig


def plot_rolling_mean(
    df: pd.DataFrame,
    column: str = "feat_hand_value",
    window: int = 100,
    figsize: Tuple[int, int] = (12, 5),
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot rolling mean of a column over hand index.

    Used to detect drift over time in the dataset.

    Args:
        df: DataFrame sorted by hand_id
        column: Column to compute rolling mean for
        window: Rolling window size
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if column not in df.columns:
        ax.text(0.5, 0.5, f"Column '{column}' not found", ha="center", va="center")
        return fig

    # Sort by hand_id to ensure temporal order
    df_sorted = df.sort_values("hand_id") if "hand_id" in df.columns else df

    values = df_sorted[column].values
    rolling = pd.Series(values).rolling(window=window, min_periods=1).mean()

    ax.plot(rolling, color="#3498db", linewidth=1.5, label=f"Rolling mean (window={window})")
    ax.axhline(values.mean(), color="red", linestyle="--", label=f"Global mean: {values.mean():.3f}")

    ax.set_xlabel("Row Index")
    ax.set_ylabel(column.replace("feat_", ""))
    ax.set_title(title or f"Rolling Mean of {column.replace('feat_', '')}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def plot_feature_vs_label(
    df: pd.DataFrame,
    feature: str,
    label: str = "feat_hand_value",
    figsize: Tuple[int, int] = (10, 6),
) -> plt.Figure:
    """Plot scatter/binned boxplot of feature vs label.

    Args:
        df: DataFrame with feature columns
        feature: Feature column name (with or without feat_ prefix)
        label: Label column name (with or without feat_ prefix)
        figsize: Figure size tuple

    Returns:
        matplotlib Figure
    """
    # Normalize column names
    feat_col = feature if feature.startswith("feat_") else f"feat_{feature}"
    label_col = label if label.startswith("feat_") else f"feat_{label}"

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    if feat_col not in df.columns or label_col not in df.columns:
        axes[0].text(0.5, 0.5, "Required columns not found", ha="center", va="center")
        return fig

    # Left: Scatter plot
    ax = axes[0]
    ax.scatter(df[feat_col], df[label_col], alpha=0.3, s=10)
    ax.set_xlabel(feat_col.replace("feat_", ""))
    ax.set_ylabel(label_col.replace("feat_", ""))
    ax.set_title("Scatter Plot")

    # Add trend line
    if len(df) > 10:
        z = np.polyfit(df[feat_col], df[label_col], 1)
        p = np.poly1d(z)
        x_range = np.linspace(df[feat_col].min(), df[feat_col].max(), 100)
        ax.plot(x_range, p(x_range), color="red", linestyle="--", label="Trend")
        ax.legend()

    # Right: Binned boxplot
    ax = axes[1]
    # Create bins
    try:
        df["_bin"] = pd.qcut(df[feat_col], q=5, duplicates="drop")
        if HAS_SEABORN:
            sns.boxplot(data=df, x="_bin", y=label_col, ax=ax)
        else:
            bins = df.groupby("_bin")[label_col].apply(list).tolist()
            ax.boxplot(bins)
        df.drop("_bin", axis=1, inplace=True)
    except ValueError:
        # Not enough unique values for binning
        ax.text(0.5, 0.5, "Not enough unique values for binning", ha="center", va="center")

    ax.set_xlabel(feat_col.replace("feat_", "") + " (binned)")
    ax.set_ylabel(label_col.replace("feat_", ""))
    ax.set_title("Binned Box Plot")
    ax.tick_params(axis="x", rotation=45)

    fig.suptitle(f"{feat_col.replace('feat_', '')} vs {label_col.replace('feat_', '')}", fontsize=12, y=1.02)
    plt.tight_layout()
    return fig


def plot_feature_vs_outcome(
    df: pd.DataFrame,
    feature: str,
    outcome: str = "tricks_won",
    figsize: Tuple[int, int] = (12, 5),
) -> plt.Figure:
    """Plot scatter + binned boxplot for feature vs outcome with correlation.

    Creates a two-panel figure showing the relationship between a feature
    and an outcome variable (typically tricks_won from simulation).

    Args:
        df: DataFrame with feature columns and outcome column
        feature: Feature column name (with or without feat_ prefix)
        outcome: Outcome column name (default "tricks_won")
        figsize: Figure size tuple

    Returns:
        matplotlib Figure with correlation coefficient in title
    """
    # Normalize column name
    feat_col = feature if feature.startswith("feat_") else f"feat_{feature}"

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    if feat_col not in df.columns or outcome not in df.columns:
        axes[0].text(0.5, 0.5, f"Required columns not found\n({feat_col}, {outcome})",
                     ha="center", va="center")
        return fig

    # Compute correlation
    valid_mask = df[feat_col].notna() & df[outcome].notna()
    if valid_mask.sum() > 2:
        corr = df.loc[valid_mask, feat_col].corr(df.loc[valid_mask, outcome])
    else:
        corr = np.nan

    # Left: Scatter plot
    ax = axes[0]
    ax.scatter(df[feat_col], df[outcome], alpha=0.3, s=10, c="#3498db")
    ax.set_xlabel(feat_col.replace("feat_", ""))
    ax.set_ylabel(outcome.replace("_", " ").title())
    ax.set_title("Scatter Plot")

    # Add trend line
    if valid_mask.sum() > 10:
        z = np.polyfit(df.loc[valid_mask, feat_col], df.loc[valid_mask, outcome], 1)
        p = np.poly1d(z)
        x_range = np.linspace(df[feat_col].min(), df[feat_col].max(), 100)
        ax.plot(x_range, p(x_range), color="red", linestyle="--", linewidth=2, label="Trend")
        ax.legend()

    ax.grid(True, alpha=0.3)

    # Right: Binned boxplot
    ax = axes[1]
    try:
        df_copy = df[[feat_col, outcome]].copy()
        df_copy["_bin"] = pd.qcut(df_copy[feat_col], q=5, duplicates="drop")
        if HAS_SEABORN:
            sns.boxplot(data=df_copy, x="_bin", y=outcome, ax=ax)
        else:
            bins = df_copy.groupby("_bin")[outcome].apply(list).tolist()
            ax.boxplot(bins)
    except ValueError:
        ax.text(0.5, 0.5, "Not enough unique values for binning", ha="center", va="center")

    ax.set_xlabel(feat_col.replace("feat_", "") + " (binned)")
    ax.set_ylabel(outcome.replace("_", " ").title())
    ax.set_title("Binned Box Plot")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, axis="y", alpha=0.3)

    corr_str = f"r = {corr:.3f}" if not np.isnan(corr) else "r = N/A"
    fig.suptitle(f"{feat_col.replace('feat_', '')} vs {outcome} ({corr_str})", fontsize=12, y=1.02)
    plt.tight_layout()
    return fig


def plot_outcome_distributions(
    df: pd.DataFrame,
    outcome: str = "tricks_won",
    group_by: str = "contract_type",
    figsize: Tuple[int, int] = (10, 6),
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot violin/box plots of outcome distribution grouped by category.

    Args:
        df: DataFrame with outcome column and grouping column
        outcome: Outcome column name (default "tricks_won")
        group_by: Column to group by (default "contract_type")
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if outcome not in df.columns or group_by not in df.columns:
        ax.text(0.5, 0.5, f"Required columns not found\n({outcome}, {group_by})",
                ha="center", va="center")
        return fig

    groups = sorted(df[group_by].unique())

    if HAS_SEABORN:
        sns.violinplot(data=df, x=group_by, y=outcome, ax=ax, order=groups, inner="box")
    else:
        data = [df[df[group_by] == g][outcome].values for g in groups]
        bp = ax.boxplot(data, labels=groups, patch_artist=True)
        colors = plt.cm.tab10(np.linspace(0, 1, len(groups)))
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

    ax.set_xlabel(group_by.replace("_", " ").title())
    ax.set_ylabel(outcome.replace("_", " ").title())
    ax.set_title(title or f"{outcome.replace('_', ' ').title()} Distribution by {group_by.replace('_', ' ').title()}")
    ax.grid(True, axis="y", alpha=0.3)

    # Add mean markers
    means = [df[df[group_by] == g][outcome].mean() for g in groups]
    ax.scatter(range(len(means)), means, color="red", marker="D", s=50, zorder=5, label="Mean")
    ax.legend()

    plt.tight_layout()
    return fig


def plot_feature_outcome_correlation(
    df: pd.DataFrame,
    outcome: str = "tricks_won",
    features: Optional[List[str]] = None,
    top_n: int = 15,
    figsize: Tuple[int, int] = (10, 8),
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot horizontal bar chart of feature correlations with outcome.

    Creates a bar chart sorted by absolute correlation, with colors
    indicating positive (green) or negative (red) correlation.

    Args:
        df: DataFrame with feat_* columns and outcome column
        outcome: Outcome column name (default "tricks_won")
        features: Optional list of feature names to include (without feat_ prefix).
                  If None, uses all numeric feat_* columns.
        top_n: Maximum number of features to display (default 15)
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    fig, ax = plt.subplots(figsize=figsize)

    if outcome not in df.columns:
        ax.text(0.5, 0.5, f"Outcome column '{outcome}' not found", ha="center", va="center")
        return fig

    # Get feature columns
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    numeric_cols = [c for c in feat_cols if df[c].dtype in [np.float64, np.int64, np.float32, np.int32]]

    if features:
        numeric_cols = [f"feat_{f}" for f in features if f"feat_{f}" in numeric_cols]

    if not numeric_cols:
        ax.text(0.5, 0.5, "No numeric features found", ha="center", va="center")
        return fig

    # Compute correlations
    correlations = {}
    for col in numeric_cols:
        valid_mask = df[col].notna() & df[outcome].notna()
        if valid_mask.sum() > 2:
            corr = df.loc[valid_mask, col].corr(df.loc[valid_mask, outcome])
            if not np.isnan(corr):
                correlations[col] = corr

    if not correlations:
        ax.text(0.5, 0.5, "Could not compute correlations", ha="center", va="center")
        return fig

    # Sort by absolute correlation and take top N
    sorted_items = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
    sorted_items = list(reversed(sorted_items))  # Reverse for horizontal bar

    labels = [c.replace("feat_", "") for c, _ in sorted_items]
    values = [v for _, v in sorted_items]
    colors = ["#27ae60" if v > 0 else "#e74c3c" for v in values]

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=colors, alpha=0.8)

    ax.axvline(0, color="black", linestyle="-", linewidth=1)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel(f"Correlation with {outcome}")
    ax.set_ylabel("Feature")
    ax.set_title(title or f"Feature Correlation with {outcome.replace('_', ' ').title()}")
    ax.grid(True, axis="x", alpha=0.3)
    ax.set_xlim(-1.1, 1.1)

    # Annotate bars with values
    for bar, val in zip(bars, values):
        x_pos = val + 0.02 if val >= 0 else val - 0.02
        ha = "left" if val >= 0 else "right"
        ax.text(x_pos, bar.get_y() + bar.get_height() / 2, f"{val:.3f}",
                va="center", ha=ha, fontsize=8)

    plt.tight_layout()
    return fig
