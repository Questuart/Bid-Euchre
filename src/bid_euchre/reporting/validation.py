"""
Validation plot generation for Arc B training and evaluation.

Provides automated diagnostic charts during bidless dataset collection
and B0 value model training runs.
"""

import os
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np

from .style import (
    CONTRACT_COLORS,
    CONTRACT_LABELS,
    FIGSIZE_MATRIX,
    FIGSIZE_SINGLE_PLOT,
    apply_report_style,
)


def plot_feature_distributions(
    features_by_contract: Dict[str, List[Dict[str, Any]]],
    output_dir: str,
    feature_keys: Optional[List[str]] = None,
) -> str:
    """
    Plot feature distributions by contract type.

    Args:
        features_by_contract: Dict mapping contract key (e.g., "suit_H", "high")
                              to list of feature dicts
        output_dir: Directory to save plots
        feature_keys: Specific features to plot (default: trump_count, offsuit_aces)

    Returns:
        Path to generated plot
    """
    apply_report_style()
    os.makedirs(output_dir, exist_ok=True)

    if feature_keys is None:
        feature_keys = ["trump_count", "offsuit_aces", "hand_value"]

    n_features = len(feature_keys)

    fig, axes = plt.subplots(
        n_features, 1,
        figsize=(FIGSIZE_SINGLE_PLOT[0], 4 * n_features),
        squeeze=False
    )

    for i, feature in enumerate(feature_keys):
        ax = axes[i, 0]

        for contract_key, features_list in features_by_contract.items():
            values = [f.get(feature, 0) for f in features_list]
            if not values:
                continue

            label = CONTRACT_LABELS.get(contract_key, contract_key)
            color = CONTRACT_COLORS.get(contract_key, "#95a5a6")

            ax.hist(
                values,
                bins=20,
                alpha=0.5,
                label=label,
                color=color,
                density=True,
            )

        ax.set_xlabel(feature.replace("_", " ").title())
        ax.set_ylabel("Density")
        ax.set_title(f"Distribution of {feature.replace('_', ' ').title()}")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = os.path.join(output_dir, "feature_distributions.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


def plot_feature_correlation(
    features: List[Dict[str, Any]],
    output_dir: str,
    feature_keys: Optional[List[str]] = None,
) -> str:
    """
    Plot feature correlation heatmap.

    Args:
        features: List of feature dicts
        output_dir: Directory to save plots
        feature_keys: Features to include (default: all numeric)

    Returns:
        Path to generated plot
    """
    apply_report_style()
    os.makedirs(output_dir, exist_ok=True)

    if not features:
        return ""

    # Auto-detect numeric features if not specified
    if feature_keys is None:
        sample = features[0]
        feature_keys = [
            k for k, v in sample.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]

    if len(feature_keys) < 2:
        return ""

    # Build data matrix
    n_samples = len(features)
    n_features = len(feature_keys)
    data = np.zeros((n_samples, n_features))

    for i, f in enumerate(features):
        for j, key in enumerate(feature_keys):
            data[i, j] = f.get(key, 0)

    # Compute correlation matrix
    corr = np.corrcoef(data, rowvar=False)

    # Plot heatmap
    fig, ax = plt.subplots(figsize=FIGSIZE_MATRIX)

    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1, aspect="auto")
    fig.colorbar(im, ax=ax, label="Correlation")

    # Labels
    labels = [k.replace("_", "\n") for k in feature_keys]
    ax.set_xticks(range(n_features))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(n_features))
    ax.set_yticklabels(labels)

    # Annotate with values
    for i in range(n_features):
        for j in range(n_features):
            val = corr[i, j]
            color = "white" if abs(val) > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=8)

    ax.set_title("Feature Correlation Matrix")
    plt.tight_layout()

    output_path = os.path.join(output_dir, "feature_correlation.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


def plot_hand_value_by_contract(
    features_by_contract: Dict[str, List[Dict[str, Any]]],
    output_dir: str,
    value_key: str = "hand_value",
) -> str:
    """
    Plot hand value distribution by contract type.

    Args:
        features_by_contract: Dict mapping contract key to feature dicts
        output_dir: Directory to save plots
        value_key: Key for hand value in feature dict

    Returns:
        Path to generated plot
    """
    apply_report_style()
    os.makedirs(output_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=FIGSIZE_SINGLE_PLOT)

    box_data = []
    labels = []
    colors = []

    for contract_key, features_list in sorted(features_by_contract.items()):
        values = [f.get(value_key, 0) for f in features_list]
        if values:
            box_data.append(values)
            labels.append(CONTRACT_LABELS.get(contract_key, contract_key))
            colors.append(CONTRACT_COLORS.get(contract_key, "#95a5a6"))

    if not box_data:
        plt.close(fig)
        return ""

    bp = ax.boxplot(box_data, labels=labels, patch_artist=True)

    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Hand Value")
    ax.set_title("Hand Value Distribution by Contract Type")
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    output_path = os.path.join(output_dir, "hand_value_by_contract.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


def generate_validation_plots(
    features_by_contract: Dict[str, List[Dict[str, Any]]],
    output_dir: str,
) -> Dict[str, str]:
    """
    Generate all validation plots for a dataset.

    Args:
        features_by_contract: Dict mapping contract key to list of feature dicts
        output_dir: Directory to save plots

    Returns:
        Dict mapping plot name to output path
    """
    os.makedirs(output_dir, exist_ok=True)

    # Flatten features for correlation plot
    all_features = []
    for features_list in features_by_contract.values():
        all_features.extend(features_list)

    plots = {}

    # Feature distributions
    path = plot_feature_distributions(features_by_contract, output_dir)
    if path:
        plots["feature_distributions"] = path

    # Feature correlation
    path = plot_feature_correlation(all_features, output_dir)
    if path:
        plots["feature_correlation"] = path

    # Hand value by contract
    path = plot_hand_value_by_contract(features_by_contract, output_dir)
    if path:
        plots["hand_value_by_contract"] = path

    return plots
