#!/usr/bin/env python3
"""
Generate 3x3 scatterplot dashboards for top 9 features by contract type.

Usage:
    python experiments/plot_top_features_scatter.py <train_jsonl_path> <output_dir> <title_prefix>
"""

import json
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats


def compute_correlations_by_contract(jsonl_path):
    """Compute correlations for all features grouped by contract type."""
    # Separate feature data by contract type
    contract_data = {
        'suit': defaultdict(lambda: {"feature_vals": [], "trick_vals": []}),
        'high': defaultdict(lambda: {"feature_vals": [], "trick_vals": []}),
        'low': defaultdict(lambda: {"feature_vals": [], "trick_vals": []})
    }
    
    with open(jsonl_path) as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            
            if rec.get("event") != "hand_end":
                continue
            
            contract_type = rec.get("contract")
            if contract_type not in ['suit', 'high', 'low']:
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
                        contract_data[contract_type][fname]["feature_vals"].append(fval)
                        contract_data[contract_type][fname]["trick_vals"].append(team_tricks)
    
    # Compute correlations for each contract type
    results = {}
    for contract_type, feature_data in contract_data.items():
        correlations = {}
        for fname, data in feature_data.items():
            fvals = np.array(data["feature_vals"])
            tvals = np.array(data["trick_vals"])
            
            if len(fvals) > 10 and np.std(fvals) > 0:
                corr = np.corrcoef(fvals, tvals)[0, 1]
                correlations[fname] = {
                    'corr': np.clip(corr, -1, 1),
                    'feature_vals': fvals,
                    'trick_vals': tvals,
                    'n': len(fvals)
                }
            else:
                correlations[fname] = {
                    'corr': 0.0,
                    'feature_vals': fvals,
                    'trick_vals': tvals,
                    'n': len(fvals)
                }
        
        results[contract_type] = correlations
    
    return results


def plot_scatter_with_regression(ax, x, y, feature_name, corr_value, n_points):
    """Plot scatter with linear regression line."""
    # Sample data if too many points (for performance)
    if len(x) > 5000:
        indices = np.random.choice(len(x), 5000, replace=False)
        x_plot = x[indices]
        y_plot = y[indices]
    else:
        x_plot = x
        y_plot = y
    
    # Scatter plot with alpha for overlapping points
    ax.scatter(x_plot, y_plot, alpha=0.3, s=10, color='#3498db', edgecolors='none')
    
    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    
    # Plot regression line
    x_line = np.array([x.min(), x.max()])
    y_line = slope * x_line + intercept
    ax.plot(x_line, y_line, color='#e74c3c', linewidth=2.5, label=f'y = {slope:.3f}x + {intercept:.2f}')
    
    # Title with correlation
    ax.set_title(f'{feature_name}\nr = {corr_value:+.3f}, n = {n_points:,}', 
                 fontsize=9, fontweight='bold', pad=8)
    
    # Labels
    ax.set_xlabel(feature_name, fontsize=7)
    ax.set_ylabel('Team Tricks Won', fontsize=7)
    
    # Grid
    ax.grid(alpha=0.3, linestyle='--', linewidth=0.5)
    
    # Legend
    ax.legend(loc='best', fontsize=6, framealpha=0.9)
    
    # Tick label size
    ax.tick_params(axis='both', labelsize=6)


def plot_top9_dashboard(correlations_by_contract, contract_type, output_dir, title_prefix=""):
    """Create 3x3 dashboard for top 9 features."""
    
    contract_labels = {
        'suit': 'Suit Contracts (All Suits Combined)',
        'high': 'High Contracts (Ace High)',
        'low': 'Low Contracts (Ten High)'
    }
    
    correlations = correlations_by_contract[contract_type]
    
    # Get top 9 by absolute correlation
    sorted_features = sorted(correlations.items(), key=lambda x: -abs(x[1]['corr']))[:9]
    
    if len(sorted_features) < 9:
        print(f"⚠️  Only {len(sorted_features)} features for {contract_type}, skipping")
        return
    
    # Create 3x3 figure
    fig, axes = plt.subplots(3, 3, figsize=(18, 16))
    fig.suptitle(f'{title_prefix}{contract_labels[contract_type]}\nTop 9 Features: Scatterplots with Linear Regression (Train Split)', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    # Plot each feature
    for idx, (fname, data) in enumerate(sorted_features):
        row = idx // 3
        col = idx % 3
        ax = axes[row, col]
        
        plot_scatter_with_regression(
            ax, 
            data['feature_vals'], 
            data['trick_vals'],
            fname,
            data['corr'],
            data['n']
        )
    
    # Tight layout
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    # Save
    output_path = os.path.join(output_dir, f'top9_scatter_{contract_type}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ {contract_type.upper()}: {output_path}")
    
    plt.close()
    
    # Print feature list
    print(f"\n{contract_type.upper()} - Top 9 Features:")
    for rank, (fname, data) in enumerate(sorted_features, 1):
        print(f"  {rank}. {fname:<35} r = {data['corr']:+.4f}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python plot_top_features_scatter.py <train_jsonl_path> <output_dir> <title_prefix>")
        sys.exit(1)
    
    jsonl_path = sys.argv[1]
    output_dir = sys.argv[2]
    title_prefix = sys.argv[3] + " - " if sys.argv[3] else ""
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading data from: {jsonl_path}")
    correlations_by_contract = compute_correlations_by_contract(jsonl_path)
    
    print(f"\nGenerating 3x3 scatterplot dashboards...")
    
    for contract_type in ['suit', 'high', 'low']:
        print(f"\n{'='*80}")
        print(f"Processing {contract_type.upper()} contracts...")
        print('='*80)
        plot_top9_dashboard(correlations_by_contract, contract_type, output_dir, title_prefix)
    
    print("\n" + "=" * 80)
    print("✅ All 3x3 scatterplot dashboards generated!")
    print("=" * 80)
    print(f"\nOutput directory: {output_dir}")
    print("  - top9_scatter_suit.png")
    print("  - top9_scatter_high.png")
    print("  - top9_scatter_low.png")


if __name__ == "__main__":
    main()
