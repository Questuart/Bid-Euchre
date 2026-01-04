#!/usr/bin/env python3
"""
Plot all feature correlations from a train split.

Usage:
    python experiments/plot_all_feature_correlations.py <train_jsonl_path> <output_path>
"""

import json
import sys
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict


def compute_all_correlations(jsonl_path):
    """Compute correlations for all features from JSONL file."""
    feature_data = defaultdict(lambda: {"feature_vals": [], "trick_vals": []})
    
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            
            if rec.get("event") != "hand_end":
                continue
                
            features_list = rec.get("features", [])
            t0 = rec.get("t0", 5)
            t1 = rec.get("t1", 5)
            
            for player_idx, player_features in enumerate(features_list):
                if not isinstance(player_features, dict):
                    continue
                    
                team_tricks = t0 if player_idx in (0, 2) else t1
                
                for fname, fval in player_features.items():
                    if isinstance(fval, (int, float)):
                        feature_data[fname]["feature_vals"].append(fval)
                        feature_data[fname]["trick_vals"].append(team_tricks)
    
    # Compute correlations
    correlations = {}
    for fname, data in feature_data.items():
        fvals = np.array(data["feature_vals"])
        tvals = np.array(data["trick_vals"])
        
        if len(fvals) > 10 and np.std(fvals) > 0:
            corr = np.corrcoef(fvals, tvals)[0, 1]
            correlations[fname] = (np.clip(corr, -1, 1), len(fvals))
        else:
            correlations[fname] = (0.0, len(fvals))
    
    return correlations


def plot_all_correlations(correlations, output_path, title_prefix=""):
    """Create comprehensive bar chart of all feature correlations."""
    # Sort by correlation value (not absolute)
    sorted_corrs = sorted(correlations.items(), key=lambda x: x[1][0])
    
    features = [f[0] for f in sorted_corrs]
    corrs = [f[1][0] for f in sorted_corrs]
    ns = [f[1][1] for f in sorted_corrs]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 14))
    
    # Color by sign
    colors = ['#e74c3c' if c < 0 else '#2ecc71' for c in corrs]
    
    y_pos = np.arange(len(features))
    ax.barh(y_pos, corrs, color=colors, alpha=0.8, edgecolor='white', linewidth=0.5)
    
    # Add vertical line at 0
    ax.axvline(x=0, color='#2c3e50', linewidth=2, zorder=10)
    
    # Labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features, fontsize=7)
    ax.set_xlabel('Pearson Correlation (r)', fontsize=11, fontweight='bold')
    
    n_hands = ns[0] // 4 if ns else 0  # Divide by 4 players
    ax.set_title(f'{title_prefix}All 40 Features: Correlation with Tricks Won\n(Train Split, n={n_hands:,} hands)', 
                 fontsize=13, fontweight='bold', pad=15)
    
    # Set x limits
    max_abs = max(abs(min(corrs)), abs(max(corrs)))
    limit = max(0.25, max_abs + 0.05)
    ax.set_xlim(-limit, limit)
    
    # Add gridlines
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    # Add correlation values on bars
    for i, (feature, corr) in enumerate(zip(features, corrs)):
        ha = 'left' if corr >= 0 else 'right'
        offset = 0.005 if corr >= 0 else -0.005
        ax.text(corr + offset, i, f'{corr:+.3f}', 
                va='center', ha=ha, fontsize=6, fontweight='bold')
    
    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='Positive (more tricks)'),
        Patch(facecolor='#e74c3c', label='Negative (fewer tricks)')
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9, framealpha=0.9)
    
    # Tight layout
    plt.tight_layout()
    
    # Save
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ Chart saved to: {output_path}")
    
    plt.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: python plot_all_feature_correlations.py <train_jsonl_path> <output_path> [title_prefix]")
        sys.exit(1)
    
    jsonl_path = sys.argv[1]
    output_path = sys.argv[2]
    title_prefix = sys.argv[3] + " - " if len(sys.argv) > 3 else ""
    
    print(f"Loading data from: {jsonl_path}")
    correlations = compute_all_correlations(jsonl_path)
    print(f"Computed correlations for {len(correlations)} features")
    
    plot_all_correlations(correlations, output_path, title_prefix)


if __name__ == "__main__":
    main()
