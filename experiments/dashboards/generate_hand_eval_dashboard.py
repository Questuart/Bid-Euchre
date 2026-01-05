#!/usr/bin/env python3
"""
Hand Evaluation Dashboard Generator for Bid Euchre Simulations.

Analyzes hand evaluation features and their relationship to trick-taking performance:
- Feature importance (correlations with tricks won)
- Feature distributions by contract type
- Hand score calibration
- Feature interactions

Usage:
    PYTHONPATH=src python experiments/generate_hand_eval_dashboard.py \\
        --run-dir data/runs/<run_id>
"""

import os
import sys
import json
import argparse
from glob import glob
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats as scipy_stats

# Import reporting framework
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bid_euchre.reporting import (
    apply_report_style, get_report_paths,
    ensure_dir, copy_to_latest, write_latest_pointer,
)

# Apply report styling
apply_report_style()

# Feature groups for analysis
FEATURE_GROUPS = {
    "trump_strength": ["bowers", "trump_count", "top_trump_count", "trump_power_sum", "highest_trump_rank"],
    "offsuit_control": ["offsuit_aces", "offsuit_king_count_total", "offsuit_suits_with_ace", "high_offsuit"],
    "distribution": ["void_count", "max_suit_len", "num_singletons", "num_doubletons"],
    "high_low": ["high_card_count", "low_card_count", "double_ten_jack_count"],
}

# Top features to focus on (from experience)
TOP_FEATURES = [
    "bowers", "trump_count", "offsuit_aces", "high_offsuit", 
    "top_trump_count", "trump_power_sum", "void_count",
    "offsuit_suits_with_ace", "high_card_count", "rank_sum"
]


# ============================================================================
# Data Loading
# ============================================================================

def load_hand_records(run_dir: str) -> List[Dict]:
    """Load hand-level records from JSONL logs."""
    paths = get_report_paths(run_dir)
    logs_dir = paths.logs_dir
    
    if not os.path.exists(logs_dir):
        return []
    
    hand_records = []
    for jsonl_file in glob(os.path.join(logs_dir, "*.jsonl")):
        with open(jsonl_file) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    hand_records.append(record)
    
    return hand_records


# ============================================================================
# Feature Analysis
# ============================================================================

def compute_feature_correlations(hand_records: List[Dict]) -> Dict[str, Tuple[float, int]]:
    """Compute Pearson correlation between each feature and team tricks."""
    if not hand_records:
        return {}
    
    feature_data = defaultdict(lambda: {"feature_vals": [], "trick_vals": []})
    
    for record in hand_records:
        features_list = record.get("features", [])
        t0 = record.get("t0", 5)
        t1 = record.get("t1", 5)
        
        for player_idx, player_features in enumerate(features_list):
            if not isinstance(player_features, dict):
                continue
                
            team_tricks = t0 if player_idx in (0, 2) else t1
            
            for fname, fval in player_features.items():
                if isinstance(fval, (int, float)):
                    feature_data[fname]["feature_vals"].append(fval)
                    feature_data[fname]["trick_vals"].append(team_tricks)
    
    correlations = {}
    for fname, data in feature_data.items():
        fvals = np.array(data["feature_vals"])
        tvals = np.array(data["trick_vals"])
        total_n = len(fvals)
        
        if total_n > 10 and np.std(fvals) > 0:
            corr, _ = scipy_stats.pearsonr(fvals, tvals)
            correlations[fname] = (np.clip(corr, -1, 1), total_n)
        else:
            correlations[fname] = (0.0, total_n)
    
    return correlations


def group_hands_by_contract(hand_records: List[Dict]) -> Dict[str, List[Dict]]:
    """Group hand records by contract type."""
    by_contract = defaultdict(list)
    
    for record in hand_records:
        contract_type = record.get("contract_type", "unknown")
        trump_suit = record.get("trump_suit")
        
        if contract_type == "suit" and trump_suit:
            key = "suit"
        else:
            key = contract_type
        
        by_contract[key].append(record)
    
    return dict(by_contract)


def extract_feature_by_contract(hand_records: List[Dict], feature_name: str) -> Dict[str, List[float]]:
    """Extract a specific feature grouped by contract type."""
    by_contract = defaultdict(list)
    
    for record in hand_records:
        contract_type = record.get("contract_type", "unknown")
        trump_suit = record.get("trump_suit")
        
        if contract_type == "suit" and trump_suit:
            key = "Suit"
        elif contract_type == "high":
            key = "High"
        elif contract_type == "low":
            key = "Low"
        else:
            continue
        
        features_list = record.get("features", [])
        for player_features in features_list:
            if isinstance(player_features, dict) and feature_name in player_features:
                value = player_features[feature_name]
                if isinstance(value, (int, float)):
                    by_contract[key].append(value)
    
    return dict(by_contract)


# ============================================================================
# Plotting Functions
# ============================================================================

def plot_feature_importance(ax, correlations: Dict[str, Tuple[float, int]], top_n: int = 15):
    """Bar chart of top features by correlation with tricks."""
    if not correlations:
        ax.text(0.5, 0.5, "No feature data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Feature Importance")
        return
    
    # Sort by absolute correlation
    sorted_features = sorted(correlations.items(), key=lambda x: -abs(x[1][0]))[:top_n]
    
    features = [f[0] for f in sorted_features]
    corrs = [f[1][0] for f in sorted_features]
    
    # Color by direction
    colors = ['#2ecc71' if c > 0 else '#e74c3c' for c in corrs]
    
    y = np.arange(len(features))
    ax.barh(y, corrs, color=colors, alpha=0.8, edgecolor="white")
    ax.axvline(x=0, color="#2c3e50", linewidth=1.5)
    ax.set_yticks(y)
    ax.set_yticklabels(features, fontsize=8)
    ax.set_xlabel("Pearson Correlation (r)", fontsize=10)
    ax.set_title(f"Top {top_n} Features by Importance", fontsize=11, fontweight="bold", pad=10)
    ax.set_xlim(-0.6, 0.6)
    
    # Add correlation values
    for i, c in enumerate(corrs):
        ha = "left" if c >= 0 else "right"
        offset = 0.02 if c >= 0 else -0.02
        ax.text(c + offset, i, f"{c:.3f}", va="center", ha=ha, fontsize=7, fontweight="bold")
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='Positive (more tricks)'),
        Patch(facecolor='#e74c3c', label='Negative (fewer tricks)')
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=7)


def plot_feature_by_contract_violin(ax, hand_records: List[Dict], feature_name: str):
    """Violin plot of a feature distribution by contract type."""
    by_contract = extract_feature_by_contract(hand_records, feature_name)
    
    if not by_contract:
        ax.text(0.5, 0.5, f"No data for {feature_name}", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{feature_name} by Contract")
        return
    
    # Order: High, Low, Suit
    contract_order = ["High", "Low", "Suit"]
    sorted_contracts = [c for c in contract_order if c in by_contract and len(by_contract[c]) > 10]
    
    if not sorted_contracts:
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{feature_name} by Contract")
        return
    
    positions = list(range(len(sorted_contracts)))
    data_for_violin = [by_contract[c] for c in sorted_contracts]
    
    # Create violin plots
    parts = ax.violinplot(data_for_violin, positions=positions,
                          showmeans=True, showmedians=True, widths=0.7)
    
    # Color by contract type
    colors_map = {"High": "#e74c3c", "Low": "#3498db", "Suit": "#2ecc71"}
    for i, (pc, contract) in enumerate(zip(parts['bodies'], sorted_contracts)):
        color = colors_map.get(contract, "#95a5a6")
        pc.set_facecolor(color)
        pc.set_alpha(0.6)
        pc.set_edgecolor('#2c3e50')
    
    parts['cmeans'].set_color('#2c3e50')
    parts['cmeans'].set_linewidth(2)
    parts['cmedians'].set_color('#e74c3c')
    parts['cmedians'].set_linewidth(1.5)
    
    # Add statistics
    for pos, (contract, data) in enumerate(zip(sorted_contracts, data_for_violin)):
        n = len(data)
        mean = np.mean(data)
        ax.text(pos, max(data) * 1.05, f"μ={mean:.1f}\nn={n:,}", 
               ha="center", fontsize=6, color="black")
    
    ax.set_xticks(positions)
    ax.set_xticklabels(sorted_contracts, fontsize=9, fontweight="bold")
    ax.set_ylabel(f"{feature_name}", fontsize=9)
    ax.set_title(f"{feature_name} Distribution", fontsize=10, fontweight="bold", pad=10)


def plot_hand_score_calibration(ax, hand_records: List[Dict]):
    """Scatter plot of hand score vs actual tricks (with regression)."""
    scores = []
    tricks = []
    
    for record in hand_records:
        score_list = record.get("scores", [])
        t0 = record.get("t0", 5)
        t1 = record.get("t1", 5)
        
        for player_idx, score in enumerate(score_list):
            if isinstance(score, (int, float)):
                team_tricks = t0 if player_idx in (0, 2) else t1
                scores.append(score)
                tricks.append(team_tricks)
    
    if len(scores) < 10:
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Hand Score Calibration")
        return
    
    scores = np.array(scores)
    tricks = np.array(tricks)
    
    # Create 2D histogram for density
    bins_x = np.linspace(scores.min(), scores.max(), 50)
    bins_y = np.arange(0, 11)
    
    h, xedges, yedges = np.histogram2d(scores, tricks, bins=[bins_x, bins_y])
    
    # Plot heatmap
    im = ax.imshow(h.T, origin='lower', aspect='auto', cmap='YlOrRd',
                   extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]], alpha=0.7)
    
    # Add regression line
    z = np.polyfit(scores, tricks, 1)
    p = np.poly1d(z)
    score_range = np.linspace(scores.min(), scores.max(), 100)
    ax.plot(score_range, p(score_range), "b-", linewidth=2, label=f"y = {z[0]:.4f}x + {z[1]:.2f}")
    
    # Compute correlation
    corr, _ = scipy_stats.pearsonr(scores, tricks)
    
    ax.set_xlabel("Hand Score", fontsize=10)
    ax.set_ylabel("Tricks Won", fontsize=10)
    ax.set_title(f"Hand Score Calibration (r={corr:.3f})", fontsize=11, fontweight="bold", pad=10)
    ax.set_ylim(-0.5, 10.5)
    ax.legend(loc='upper left', fontsize=8)
    ax.axhline(5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Frequency", rotation=270, labelpad=15, fontsize=8)


def plot_feature_interaction_heatmap(ax, hand_records: List[Dict], 
                                     feature_x: str, feature_y: str):
    """2D heatmap showing interaction between two features and tricks won."""
    x_vals = []
    y_vals = []
    trick_vals = []
    
    for record in hand_records:
        features_list = record.get("features", [])
        t0 = record.get("t0", 5)
        t1 = record.get("t1", 5)
        
        for player_idx, player_features in enumerate(features_list):
            if not isinstance(player_features, dict):
                continue
            
            if feature_x in player_features and feature_y in player_features:
                x_val = player_features[feature_x]
                y_val = player_features[feature_y]
                team_tricks = t0 if player_idx in (0, 2) else t1
                
                if isinstance(x_val, (int, float)) and isinstance(y_val, (int, float)):
                    x_vals.append(x_val)
                    y_vals.append(y_val)
                    trick_vals.append(team_tricks)
    
    if len(x_vals) < 100:
        ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"{feature_x} vs {feature_y}")
        return
    
    x_vals = np.array(x_vals)
    y_vals = np.array(y_vals)
    trick_vals = np.array(trick_vals)
    
    # Create bins
    x_bins = np.linspace(x_vals.min(), x_vals.max(), min(15, int(x_vals.max() - x_vals.min()) + 2))
    y_bins = np.linspace(y_vals.min(), y_vals.max(), min(15, int(y_vals.max() - y_vals.min()) + 2))
    
    # Compute mean tricks in each bin
    x_digitized = np.digitize(x_vals, x_bins)
    y_digitized = np.digitize(y_vals, y_bins)
    
    grid = np.full((len(y_bins) - 1, len(x_bins) - 1), np.nan)
    
    for i in range(len(y_bins) - 1):
        for j in range(len(x_bins) - 1):
            mask = (x_digitized == j + 1) & (y_digitized == i + 1)
            if mask.sum() >= 5:
                grid[i, j] = trick_vals[mask].mean()
    
    # Plot heatmap
    im = ax.imshow(grid, origin='lower', aspect='auto', cmap='RdYlGn',
                   extent=[x_bins[0], x_bins[-1], y_bins[0], y_bins[-1]],
                   vmin=3, vmax=7)
    
    ax.set_xlabel(feature_x, fontsize=9)
    ax.set_ylabel(feature_y, fontsize=9)
    ax.set_title(f"{feature_x} × {feature_y}\nInteraction", fontsize=10, fontweight="bold", pad=10)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Avg Tricks", rotation=270, labelpad=15, fontsize=8)


# ============================================================================
# Main Report Generation
# ============================================================================

def generate_hand_eval_dashboard(run_dir: str, output_dir: Optional[str] = None) -> str:
    """
    Generate hand evaluation dashboard.
    
    Writes to standardized archive + latest pattern:
        <run_dir>/reports/bidding_strategy/
        ├── hand_eval_dashboard.png (latest)
        ├── summary.md (latest)
        └── _history/<timestamp>/ (archived version)
    
    Args:
        run_dir: Base run directory
        output_dir: Optional override for output location
    
    Returns:
        Path to latest hand_eval_dashboard.png
    """
    print("=" * 70)
    print("🎯 Generating Hand Evaluation Dashboard")
    print("=" * 70)
    
    # Load hand records
    print("📂 Loading hand records...")
    hand_records = load_hand_records(run_dir)
    print(f"   Loaded {len(hand_records)} hand records")
    
    if len(hand_records) < 100:
        print("   ⚠️  Too few hands for meaningful analysis")
        return ""
    
    # Compute feature correlations
    print("📊 Computing feature correlations...")
    correlations = compute_feature_correlations(hand_records)
    print(f"   Analyzed {len(correlations)} features")
    
    # Determine output paths
    paths = get_report_paths(run_dir)
    
    if output_dir:
        archive_dir = output_dir
        latest_dir = output_dir
    else:
        archive_dir = os.path.join(paths.bidding_strategy_root, "_history", paths.timestamp)
        latest_dir = paths.bidding_strategy_root
    
    ensure_dir(archive_dir)
    ensure_dir(latest_dir)
    
    # Create 2x2 figure
    fig = plt.figure(figsize=(16, 12))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3,
                          left=0.08, right=0.95, top=0.93, bottom=0.07)
    
    print("📊 Generating plots...")
    
    ax1 = fig.add_subplot(gs[0, 0])
    plot_feature_importance(ax1, correlations, top_n=15)
    print("   ✅ Feature importance")
    
    ax2 = fig.add_subplot(gs[0, 1])
    plot_hand_score_calibration(ax2, hand_records)
    print("   ✅ Hand score calibration")
    
    # Find top 2 correlated features for violin plots
    sorted_features = sorted(correlations.items(), key=lambda x: -abs(x[1][0]))
    top_feature = sorted_features[0][0] if sorted_features else "bowers"
    second_feature = sorted_features[1][0] if len(sorted_features) > 1 else "trump_count"
    
    ax3 = fig.add_subplot(gs[1, 0])
    plot_feature_by_contract_violin(ax3, hand_records, top_feature)
    print(f"   ✅ Feature distribution ({top_feature})")
    
    ax4 = fig.add_subplot(gs[1, 1])
    # Plot interaction of top 2 features
    if "trump" in top_feature.lower() and len(sorted_features) > 1:
        plot_feature_interaction_heatmap(ax4, hand_records, top_feature, second_feature)
        print(f"   ✅ Feature interaction ({top_feature} × {second_feature})")
    else:
        plot_feature_by_contract_violin(ax4, hand_records, second_feature)
        print(f"   ✅ Feature distribution ({second_feature})")
    
    # Add overall title
    meta_path = os.path.join(run_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        run_id = meta.get("run_id", "Unknown")
    else:
        run_id = os.path.basename(run_dir)
    
    fig.suptitle(f"Hand Evaluation Dashboard: {run_id}", 
                fontsize=14, fontweight="bold", y=0.98)
    
    # Save to archive
    archive_png = os.path.join(archive_dir, "hand_eval_dashboard.png")
    fig.savefig(archive_png, dpi=150, bbox_inches="tight")
    print(f"   💾 Saved to archive: {archive_png}")
    
    # Copy to latest
    latest_png = os.path.join(latest_dir, "hand_eval_dashboard.png")
    copy_to_latest(archive_png, latest_png)
    print(f"   💾 Saved to latest: {latest_png}")
    
    plt.close(fig)
    
    # Generate summary markdown
    generate_summary_md(run_dir, correlations, latest_dir, archive_dir, paths.timestamp)
    
    # Write latest pointer
    if not output_dir:
        relative_archive = os.path.relpath(archive_dir, latest_dir)
        write_latest_pointer(latest_dir, relative_archive)
    
    print("=" * 70)
    print("✅ Hand evaluation dashboard generated successfully!")
    print(f"📁 Latest: {latest_png}")
    print("=" * 70)
    
    return latest_png


def generate_summary_md(run_dir: str, correlations: Dict[str, Tuple[float, int]],
                       latest_dir: str, archive_dir: str, timestamp: str):
    """Generate summary markdown."""
    lines = []
    lines.append("# Hand Evaluation Dashboard Summary\n\n")
    
    # Load metadata
    meta_path = os.path.join(run_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        
        lines.append("## Run Information\n\n")
        lines.append(f"- **Run ID**: {meta.get('run_id', 'Unknown')}\n")
        lines.append(f"- **Experiment**: {meta.get('experiment_name', 'Unknown')}\n")
        lines.append(f"- **Features Analyzed**: {len(correlations)}\n\n")
    
    # Top features
    if correlations:
        lines.append("## Top Features by Importance\n\n")
        lines.append("| Feature | Correlation (r) | Interpretation |\n")
        lines.append("|---------|-----------------|----------------|\n")
        
        sorted_features = sorted(correlations.items(), key=lambda x: -abs(x[1][0]))[:10]
        
        for feature, (corr, n) in sorted_features:
            if corr > 0.1:
                interp = "✅ Positive (more tricks)"
            elif corr < -0.1:
                interp = "⚠️ Negative (fewer tricks)"
            else:
                interp = "➖ Weak effect"
            
            lines.append(f"| {feature} | {corr:+.3f} | {interp} |\n")
        
        lines.append("\n")
    
    # Feature groups summary
    lines.append("## Feature Groups\n\n")
    
    for group_name, features in FEATURE_GROUPS.items():
        group_corrs = {f: correlations[f][0] for f in features if f in correlations}
        if group_corrs:
            avg_abs_corr = np.mean([abs(c) for c in group_corrs.values()])
            lines.append(f"### {group_name.replace('_', ' ').title()}\n\n")
            lines.append(f"- **Average |correlation|**: {avg_abs_corr:.3f}\n")
            lines.append(f"- **Top feature**: {max(group_corrs.items(), key=lambda x: abs(x[1]))[0]}\n\n")
    
    # Report details
    lines.append("## Report Details\n\n")
    lines.append(f"- **Generated**: {timestamp}\n")
    lines.append(f"- **Archive**: `{os.path.relpath(archive_dir, run_dir)}`\n")
    
    summary_path = os.path.join(latest_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.writelines(lines)
    
    print(f"   📝 Summary saved: {summary_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate hand evaluation dashboard")
    parser.add_argument("--run-dir", type=str, required=True, help="Path to run directory")
    parser.add_argument("--output-dir", type=str, help="Override output directory")
    return parser.parse_args()


def main():
    args = parse_args()
    generate_hand_eval_dashboard(args.run_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
