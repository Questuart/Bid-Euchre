#!/usr/bin/env python3
"""
Generate improved visualizations for top 9 features using hexbin/violin plots.

Usage:
    python experiments/plot_top_features_improved.py <train_jsonl_path> <output_dir> <title_prefix>
"""

import json
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats
import matplotlib.gridspec as gridspec


def compute_correlations_by_contract(jsonl_path):
    """Compute correlations for all features grouped by contract type."""
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
    
    # Compute correlations
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


def plot_hexbin_with_trend(ax, x, y, feature_name, corr_value):
    """Plot hexbin density + binned mean trend line."""
    # Add small jitter to y to show density better
    y_jitter = y + np.random.normal(0, 0.1, size=len(y))
    
    # Hexbin plot for density
    hexbin = ax.hexbin(x, y_jitter, gridsize=25, cmap='Blues', mincnt=1, alpha=0.8, edgecolors='none')
    
    # Compute binned means for trend line
    if np.std(x) > 0:
        # Create bins based on feature value quantiles
        n_bins = 15
        bins = np.percentile(x, np.linspace(0, 100, n_bins + 1))
        bins = np.unique(bins)  # Remove duplicates
        
        if len(bins) > 2:
            bin_indices = np.digitize(x, bins[1:-1])
            
            bin_centers = []
            bin_means = []
            bin_stds = []
            
            for i in range(len(bins) - 1):
                mask = (bin_indices == i)
                if np.sum(mask) > 5:
                    bin_centers.append(np.mean(x[mask]))
                    bin_means.append(np.mean(y[mask]))
                    bin_stds.append(np.std(y[mask]) / np.sqrt(np.sum(mask)))  # SEM
            
            if len(bin_centers) > 1:
                bin_centers = np.array(bin_centers)
                bin_means = np.array(bin_means)
                bin_stds = np.array(bin_stds)
                
                # Plot trend line with confidence band
                ax.plot(bin_centers, bin_means, color='#e74c3c', linewidth=3, 
                       label=f'Binned mean', zorder=10)
                ax.fill_between(bin_centers, 
                               bin_means - 1.96 * bin_stds,
                               bin_means + 1.96 * bin_stds,
                               color='#e74c3c', alpha=0.3, zorder=9)
    
    # Also plot overall linear regression for comparison
    if len(x) > 1 and np.std(x) > 0:
        slope, intercept, _, _, _ = stats.linregress(x, y)
        x_line = np.array([x.min(), x.max()])
        y_line = slope * x_line + intercept
        ax.plot(x_line, y_line, color='orange', linewidth=2, linestyle='--',
               label=f'Linear: y={slope:.3f}x+{intercept:.2f}', zorder=11, alpha=0.9)
    
    # Formatting
    ax.set_title(f'{feature_name}\nr = {corr_value:+.3f}', 
                 fontsize=9, fontweight='bold', pad=8)
    ax.set_xlabel(feature_name, fontsize=7)
    ax.set_ylabel('Team Tricks Won', fontsize=7)
    ax.set_ylim(-0.5, 10.5)
    ax.grid(alpha=0.2, linestyle='--', linewidth=0.5)
    ax.legend(loc='best', fontsize=5, framealpha=0.9)
    ax.tick_params(axis='both', labelsize=6)
    
    # Add colorbar
    return hexbin


def plot_top9_hexbin_dashboard(correlations_by_contract, contract_type, output_dir, title_prefix=""):
    """Create 3x3 hexbin dashboard for top 9 features."""
    
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
    fig = plt.figure(figsize=(20, 16))
    gs = gridspec.GridSpec(3, 4, figure=fig, width_ratios=[1, 1, 1, 0.05],
                          hspace=0.35, wspace=0.25, left=0.05, right=0.96, top=0.94, bottom=0.05)
    
    fig.suptitle(f'{title_prefix}{contract_labels[contract_type]}\n'
                 f'Top 9 Features: Hexbin Density + Binned Means (Train Split)', 
                 fontsize=16, fontweight='bold', y=0.97)
    
    # Plot each feature
    hexbins = []
    for idx, (fname, data) in enumerate(sorted_features):
        row = idx // 3
        col = idx % 3
        ax = fig.add_subplot(gs[row, col])
        
        hexbin = plot_hexbin_with_trend(
            ax, 
            data['feature_vals'], 
            data['trick_vals'],
            fname,
            data['corr']
        )
        hexbins.append(hexbin)
    
    # Add shared colorbar
    cbar_ax = fig.add_subplot(gs[:, 3])
    cbar = fig.colorbar(hexbins[0], cax=cbar_ax, label='Point Density')
    cbar.ax.tick_params(labelsize=8)
    
    # Save
    output_path = os.path.join(output_dir, f'top9_hexbin_{contract_type}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ {contract_type.upper()}: {output_path}")
    
    plt.close()


def plot_top9_violin_dashboard(correlations_by_contract, contract_type, output_dir, title_prefix=""):
    """Create 3x3 violin plot dashboard showing feature distribution by trick count."""
    
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
    fig, axes = plt.subplots(3, 3, figsize=(20, 16))
    fig.suptitle(f'{title_prefix}{contract_labels[contract_type]}\n'
                 f'Top 9 Features: Distribution by Tricks Won (Train Split)', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    # Plot each feature
    for idx, (fname, data) in enumerate(sorted_features):
        row = idx // 3
        col = idx % 3
        ax = axes[row, col]
        
        x = data['feature_vals']
        y = data['trick_vals']
        
        # Group by trick count
        trick_counts = np.arange(0, 11)
        data_by_trick = [x[y == t] for t in trick_counts]
        
        # Filter out empty groups
        valid_tricks = [t for t, d in zip(trick_counts, data_by_trick) if len(d) > 0]
        valid_data = [d for d in data_by_trick if len(d) > 0]
        
        if len(valid_data) > 0:
            # Violin plot
            parts = ax.violinplot(valid_data, positions=valid_tricks, widths=0.7,
                                 showmeans=True, showmedians=False)
            
            # Color by correlation sign
            color = '#2ecc71' if data['corr'] > 0 else '#e74c3c'
            for pc in parts['bodies']:
                pc.set_facecolor(color)
                pc.set_alpha(0.7)
                pc.set_edgecolor('black')
                pc.set_linewidth(0.5)
            
            # Style means and extrema
            for partname in ('cbars', 'cmins', 'cmaxes', 'cmeans'):
                if partname in parts:
                    parts[partname].set_edgecolor('black')
                    parts[partname].set_linewidth(1.5)
        
        # Formatting
        ax.set_title(f'{fname}\nr = {data["corr"]:+.3f}', 
                     fontsize=9, fontweight='bold', pad=8)
        ax.set_xlabel('Team Tricks Won', fontsize=8)
        ax.set_ylabel(f'{fname} Value', fontsize=7)
        ax.set_xticks(np.arange(0, 11))
        ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.5)
        ax.tick_params(axis='both', labelsize=7)
    
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    # Save
    output_path = os.path.join(output_dir, f'top9_violin_{contract_type}.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ {contract_type.upper()} VIOLIN: {output_path}")
    
    plt.close()


def main():
    if len(sys.argv) < 4:
        print("Usage: python plot_top_features_improved.py <train_jsonl_path> <output_dir> <title_prefix>")
        sys.exit(1)
    
    jsonl_path = sys.argv[1]
    output_dir = sys.argv[2]
    title_prefix = sys.argv[3] + " - " if sys.argv[3] else ""
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading data from: {jsonl_path}")
    correlations_by_contract = compute_correlations_by_contract(jsonl_path)
    
    print(f"\n{'='*80}")
    print("GENERATING IMPROVED VISUALIZATIONS")
    print('='*80)
    
    for contract_type in ['suit', 'high', 'low']:
        print(f"\n{contract_type.upper()} contracts:")
        print("-" * 80)
        
        # Hexbin plots
        plot_top9_hexbin_dashboard(correlations_by_contract, contract_type, output_dir, title_prefix)
        
        # Violin plots
        plot_top9_violin_dashboard(correlations_by_contract, contract_type, output_dir, title_prefix)
    
    print("\n" + "=" * 80)
    print("✅ All improved visualizations generated!")
    print("=" * 80)
    print(f"\nOutput directory: {output_dir}")
    print("\nHEXBIN PLOTS (density + trend):")
    print("  - top9_hexbin_suit.png")
    print("  - top9_hexbin_high.png")
    print("  - top9_hexbin_low.png")
    print("\nVIOLIN PLOTS (distribution by trick count):")
    print("  - top9_violin_suit.png")
    print("  - top9_violin_high.png")
    print("  - top9_violin_low.png")


if __name__ == "__main__":
    main()
