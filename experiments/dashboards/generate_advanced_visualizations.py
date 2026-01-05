#!/usr/bin/env python3
"""
Generate advanced visualizations for hand evaluation analysis.

1. Feature correlation heatmaps (feature↔feature) per contract type
2. 2D interaction heatmaps (mean tricks) for key feature pairs
3. Tricks-won distribution by contract type
4. Partial dependence plots (if GBM/RF available)
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
import os

# Paths
GREEDY_TRAIN = "data/runs/hand_eval_test_greedy_42_20251217_200200/splits/hand_eval_test_42_20251217_200200_improved_greedy.train.jsonl"
OUTPUT_DIR = "data/runs/hand_eval_test_greedy_42_20251217_200200/reports/train_only/advanced_viz"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Key features to analyze
FEATURES_BY_CONTRACT = {
    'suit': [
        'bowers', 'trump_count', 'offsuit_aces', 'trump_power_sum',
        'trump_count_x_offsuit_ace', 'trump_count_x_void_count', 'void_count',
        'top_trump_count', 'trump_rb_count', 'trump_lb_count',
        'highest_trump_rank', 'second_highest_trump_rank', 'third_highest_trump_rank'
    ],
    'high': [
        'offsuit_aces', 'offsuit_suits_with_ace', 'rank_sum', 'high_card_count',
        'offsuit_suits_with_double_ace', 'offsuit_king_count_total',
        'offsuit_suits_with_ace_and_king', 'high_offsuit', 'offsuit_secondbest_rank_sum'
    ],
    'low': [
        'offsuit_tens_count', 'rank_sum', 'low_card_count',
        'offsuit_secondbest_rank_sum', 'double_ten_jack_count',
        'high_card_count', 'offsuit_aces', 'high_offsuit', 'offsuit_best_rank_sum'
    ]
}

# Key interaction pairs
INTERACTION_PAIRS = {
    'suit': [
        ('trump_count', 'void_count'),
        ('trump_power_sum', 'bowers'),
        ('top_trump_count', 'offsuit_aces'),
        ('trump_count', 'offsuit_aces'),
        ('bowers', 'void_count'),
        # Additional high-signal interactions
        ('trump_power_sum', 'void_count'),
        ('trump_rb_count', 'trump_lb_count'),
        ('trump_power_sum', 'offsuit_aces'),
        ('top_trump_count', 'void_count'),
    ],
    'high': [
        ('offsuit_aces', 'high_card_count'),
        ('offsuit_suits_with_ace', 'offsuit_aces'),
        ('rank_sum', 'offsuit_aces'),
        # Additional high-signal interactions
        ('offsuit_aces', 'offsuit_suits_with_double_ace'),
        ('offsuit_aces', 'offsuit_suits_with_ace_and_king'),
    ],
    'low': [
        ('offsuit_tens_count', 'low_card_count'),
        ('offsuit_tens_count', 'rank_sum'),
        ('low_card_count', 'high_card_count'),
        # Additional high-signal interactions
        ('offsuit_tens_count', 'double_ten_jack_count'),
        ('offsuit_tens_count', 'high_card_count'),
    ]
}

def load_data_by_contract():
    """Load all data organized by contract type."""
    data = defaultdict(lambda: defaultdict(list))
    
    with open(GREEDY_TRAIN) as f:
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
                
                # Store all features
                for fname, fval in player_features.items():
                    if isinstance(fval, (int, float)):
                        data[contract_type][fname].append(fval)
                
                # Also store tricks
                data[contract_type]['_tricks'].append(team_tricks)
    
    # Convert to numpy arrays
    for contract_type in data:
        for fname in data[contract_type]:
            data[contract_type][fname] = np.array(data[contract_type][fname])
    
    return data

def plot_feature_correlation_heatmap(data, contract_type, feature_names):
    """Plot feature-to-feature correlation heatmap."""
    print(f"  Generating correlation heatmap for {contract_type}...")
    
    # Build feature matrix
    n_samples = len(data[contract_type]['_tricks'])
    X = np.zeros((n_samples, len(feature_names)))
    
    for i, fname in enumerate(feature_names):
        if fname in data[contract_type]:
            X[:, i] = data[contract_type][fname]
    
    # Compute correlation matrix
    corr_matrix = np.corrcoef(X.T)
    
    # Plot
    fig, ax = plt.subplots(figsize=(12, 10))
    
    im = ax.imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Correlation', fontsize=12, fontweight='bold')
    
    # Ticks and labels
    ax.set_xticks(np.arange(len(feature_names)))
    ax.set_yticks(np.arange(len(feature_names)))
    ax.set_xticklabels(feature_names, rotation=45, ha='right', fontsize=8)
    ax.set_yticklabels(feature_names, fontsize=8)
    
    # Add correlation values
    for i in range(len(feature_names)):
        for j in range(len(feature_names)):
            if abs(corr_matrix[i, j]) > 0.3:  # Only show significant correlations
                text = ax.text(j, i, f'{corr_matrix[i, j]:.2f}',
                             ha="center", va="center", color="black" if abs(corr_matrix[i, j]) < 0.7 else "white",
                             fontsize=6)
    
    ax.set_title(f'{contract_type.upper()} Contracts: Feature Correlation Matrix\n'
                 f'(Shows redundancy - high values indicate features can be combined)',
                 fontsize=13, fontweight='bold', pad=15)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, f'correlation_heatmap_{contract_type}.png'), dpi=150, bbox_inches='tight')
    plt.close()
    
    # Return highly correlated pairs
    high_corr_pairs = []
    for i in range(len(feature_names)):
        for j in range(i+1, len(feature_names)):
            if abs(corr_matrix[i, j]) > 0.7:
                high_corr_pairs.append((feature_names[i], feature_names[j], corr_matrix[i, j]))
    
    return high_corr_pairs

def plot_2d_interaction_heatmap(data, contract_type, feat1, feat2):
    """Plot 2D heatmap showing mean tricks for feature pair."""
    print(f"  Generating 2D interaction: {feat1} × {feat2}...")
    
    if feat1 not in data[contract_type] or feat2 not in data[contract_type]:
        print("    Skipping (features not found)")
        return
    
    X1 = data[contract_type][feat1]
    X2 = data[contract_type][feat2]
    Y = data[contract_type]['_tricks']
    
    # Create bins
    x1_bins = np.arange(int(X1.min()), int(X1.max()) + 2)
    x2_bins = np.arange(int(X2.min()), int(X2.max()) + 2)
    
    # Compute mean tricks for each bin
    mean_tricks = np.zeros((len(x2_bins)-1, len(x1_bins)-1))
    counts = np.zeros((len(x2_bins)-1, len(x1_bins)-1))
    
    for i in range(len(X1)):
        x1_idx = np.searchsorted(x1_bins, X1[i]) - 1
        x2_idx = np.searchsorted(x2_bins, X2[i]) - 1
        
        if 0 <= x1_idx < len(x1_bins)-1 and 0 <= x2_idx < len(x2_bins)-1:
            mean_tricks[x2_idx, x1_idx] += Y[i]
            counts[x2_idx, x1_idx] += 1
    
    # Avoid division by zero
    mean_tricks = np.divide(mean_tricks, counts, where=counts>0, out=np.full_like(mean_tricks, np.nan))
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 8))
    
    im = ax.imshow(mean_tricks, cmap='RdYlGn', aspect='auto', origin='lower',
                   vmin=2, vmax=8, extent=[x1_bins[0], x1_bins[-1], x2_bins[0], x2_bins[-1]])
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Mean Team Tricks Won', fontsize=11, fontweight='bold')
    
    # Add text annotations for mean values
    for i in range(len(x2_bins)-1):
        for j in range(len(x1_bins)-1):
            if counts[i, j] > 10 and not np.isnan(mean_tricks[i, j]):
                text_color = 'white' if mean_tricks[i, j] < 4 or mean_tricks[i, j] > 6 else 'black'
                ax.text(x1_bins[j] + 0.5, x2_bins[i] + 0.5, f'{mean_tricks[i, j]:.1f}',
                       ha="center", va="center", color=text_color, fontsize=8, fontweight='bold')
    
    ax.set_xlabel(feat1, fontsize=12, fontweight='bold')
    ax.set_ylabel(feat2, fontsize=12, fontweight='bold')
    ax.set_title(f'{contract_type.upper()}: Interaction Surface\n{feat1} × {feat2}',
                 fontsize=13, fontweight='bold', pad=15)
    
    plt.tight_layout()
    safe_name = f"{feat1}_x_{feat2}".replace('_', '')
    plt.savefig(os.path.join(OUTPUT_DIR, f'interaction_2d_{contract_type}_{safe_name}.png'), dpi=150, bbox_inches='tight')
    plt.close()

def plot_tricks_distribution(data):
    """Plot tricks-won distribution by contract type."""
    print("  Generating tricks distribution...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    contract_types = ['all', 'suit', 'high', 'low']
    
    for idx, contract_type in enumerate(contract_types):
        ax = axes[idx // 2, idx % 2]
        
        if contract_type == 'all':
            # Combine all contracts
            tricks = np.concatenate([data['suit']['_tricks'], data['high']['_tricks'], data['low']['_tricks']])
        else:
            tricks = data[contract_type]['_tricks']
        
        # Histogram
        counts, bins, patches = ax.hist(tricks, bins=np.arange(-0.5, 11.5, 1), 
                                       alpha=0.7, edgecolor='black', color='#3498db')
        
        # Statistics
        mean_tricks = np.mean(tricks)
        std_tricks = np.std(tricks)
        median_tricks = np.median(tricks)
        
        # Add vertical lines
        ax.axvline(mean_tricks, color='red', linestyle='--', linewidth=2, label=f'Mean = {mean_tricks:.2f}')
        ax.axvline(median_tricks, color='orange', linestyle='--', linewidth=2, label=f'Median = {median_tricks:.1f}')
        
        # Formatting
        ax.set_xlabel('Team Tricks Won', fontsize=11, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax.set_title(f'{contract_type.upper()} Contracts\nμ={mean_tricks:.2f}, σ={std_tricks:.2f}, n={len(tricks):,}',
                     fontsize=12, fontweight='bold')
        ax.set_xticks(np.arange(0, 11))
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        
        # Add text annotations
        max_count = np.max(counts)
        for i, (count, bin_edge) in enumerate(zip(counts, bins[:-1])):
            if count > max_count * 0.05:  # Only show significant bars
                ax.text(bin_edge + 0.5, count + max_count * 0.02, f'{int(count):,}',
                       ha='center', va='bottom', fontsize=8)
    
    fig.suptitle('Tricks Won Distribution by Contract Type\n(Greedy Self-Play, Train Split)',
                 fontsize=15, fontweight='bold', y=0.995)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'tricks_distribution_by_contract.png'), dpi=150, bbox_inches='tight')
    plt.close()

def generate_summary_report(high_corr_pairs_by_contract):
    """Generate text summary of findings."""
    summary_path = os.path.join(OUTPUT_DIR, 'ANALYSIS_SUMMARY.md')
    
    with open(summary_path, 'w') as f:
        f.write("# Advanced Visualization Analysis Summary\n\n")
        f.write("## Highly Correlated Feature Pairs (|r| > 0.7)\n\n")
        f.write("These features are redundant - consider dropping one from each pair:\n\n")
        
        for contract_type, pairs in high_corr_pairs_by_contract.items():
            f.write(f"### {contract_type.upper()} Contracts\n\n")
            if pairs:
                for feat1, feat2, corr in sorted(pairs, key=lambda x: -abs(x[2])):
                    f.write(f"- **{feat1}** ↔ **{feat2}**: r = {corr:+.3f}\n")
            else:
                f.write("- No highly correlated pairs found\n")
            f.write("\n")
        
        f.write("## Interpretation Guide\n\n")
        f.write("### Correlation Heatmaps\n")
        f.write("- **Red (r ≈ -1)**: Strong negative correlation\n")
        f.write("- **White (r ≈ 0)**: No correlation (independent)\n")
        f.write("- **Blue (r ≈ +1)**: Strong positive correlation\n")
        f.write("- **High |r| > 0.7**: Features are redundant\n\n")
        
        f.write("### 2D Interaction Heatmaps\n")
        f.write("- **Green**: High mean tricks (good combinations)\n")
        f.write("- **Yellow**: Average tricks\n")
        f.write("- **Red**: Low mean tricks (bad combinations)\n")
        f.write("- Look for **non-linear patterns** (not just diagonal gradients)\n\n")
        
        f.write("### Tricks Distribution\n")
        f.write("- **Mean ≈ 5.0**: Game is symmetric (as expected)\n")
        f.write("- **Std Dev ≈ 2.0**: High variance (card play matters!)\n")
        f.write("- **Distribution shape**: Helps contextualize feature effects\n\n")
        
        f.write("## Key Insights\n\n")
        f.write("1. **Feature Redundancy**: High correlations indicate which features can be dropped\n")
        f.write("2. **Interaction Effects**: 2D heatmaps show synergies (e.g., trump + voids)\n")
        f.write("3. **Variance Context**: σ ≈ 2.0 means even +0.3 correlation is meaningful\n")
        f.write("4. **Non-linearity**: If 2D heatmaps show curved patterns → need non-linear models\n\n")
    
    print(f"✅ Summary report saved: {summary_path}")

def main():
    print("=" * 100)
    print("ADVANCED VISUALIZATION GENERATION")
    print("=" * 100)
    print()
    print("Generating:")
    print("  1. Feature correlation heatmaps (per contract)")
    print("  2. 2D interaction surfaces (mean tricks)")
    print("  3. Tricks-won distributions")
    print()
    
    # Load data
    print("Loading data...")
    data = load_data_by_contract()
    print(f"  Loaded {len(data['suit']['_tricks']):,} SUIT hands")
    print(f"  Loaded {len(data['high']['_tricks']):,} HIGH hands")
    print(f"  Loaded {len(data['low']['_tricks']):,} LOW hands")
    print()
    
    # 1. Feature correlation heatmaps
    print("Generating correlation heatmaps...")
    high_corr_pairs = {}
    for contract_type, features in FEATURES_BY_CONTRACT.items():
        pairs = plot_feature_correlation_heatmap(data, contract_type, features)
        high_corr_pairs[contract_type] = pairs
        print(f"    Found {len(pairs)} highly correlated pairs in {contract_type}")
    print()
    
    # 2. 2D interaction heatmaps
    print("Generating 2D interaction heatmaps...")
    for contract_type, pairs in INTERACTION_PAIRS.items():
        for feat1, feat2 in pairs:
            plot_2d_interaction_heatmap(data, contract_type, feat1, feat2)
    print()
    
    # 3. Tricks distribution
    print("Generating tricks distribution...")
    plot_tricks_distribution(data)
    print()
    
    # 4. Summary report
    print("Generating summary report...")
    generate_summary_report(high_corr_pairs)
    print()
    
    print("=" * 100)
    print("✅ ALL VISUALIZATIONS COMPLETE")
    print("=" * 100)
    print(f"\nOutput directory: {OUTPUT_DIR}/")
    print("\nGenerated files:")
    print("  • correlation_heatmap_suit.png")
    print("  • correlation_heatmap_high.png")
    print("  • correlation_heatmap_low.png")
    print("  • interaction_2d_*.png (15 files)")
    print("  • tricks_distribution_by_contract.png")
    print("  • ANALYSIS_SUMMARY.md")
    print()
    print("Next: Review visualizations to:")
    print("  1. Identify redundant features (high correlation)")
    print("  2. Find non-linear patterns (2D interactions)")
    print("  3. Understand variance context (distributions)")
    print()

if __name__ == "__main__":
    main()

