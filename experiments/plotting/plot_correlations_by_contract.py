#!/usr/bin/env python3
"""
Plot feature correlations by contract type (suit/high/low).

Usage:
    python experiments/plot_correlations_by_contract.py <train_jsonl_path> <output_dir> <title_prefix>
"""

import json
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict


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
                correlations[fname] = (np.clip(corr, -1, 1), len(fvals))
            else:
                correlations[fname] = (0.0, len(fvals))
        
        results[contract_type] = correlations
    
    return results


def plot_contract_correlations(correlations_by_contract, output_dir, title_prefix=""):
    """Create separate correlation charts for each contract type."""
    
    contract_labels = {
        'suit': 'Suit Contracts (All Suits Combined)',
        'high': 'High Contracts (Ace High)',
        'low': 'Low Contracts (Ten High)'
    }
    
    for contract_type, correlations in correlations_by_contract.items():
        if not correlations:
            print(f"⚠️  No data for {contract_type}, skipping")
            continue
        
        # Sort by correlation value
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
        contract_label = contract_labels[contract_type]
        ax.set_title(f'{title_prefix}{contract_label}\nAll 40 Features vs. Tricks Won (Train Split, n={n_hands:,} hands)', 
                     fontsize=12, fontweight='bold', pad=15)
        
        # Set x limits
        max_abs = max(abs(min(corrs)), abs(max(corrs)))
        limit = max(0.30, max_abs + 0.05)
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
        output_path = os.path.join(output_dir, f'all_features_correlation_{contract_type}.png')
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✅ {contract_type.upper()}: {output_path}")
        
        plt.close()


def print_summary_table(correlations_by_contract):
    """Print summary table comparing top features across contract types."""
    print("\n" + "=" * 100)
    print("TOP 10 FEATURES BY CONTRACT TYPE (TRAIN SPLIT)")
    print("=" * 100)
    
    for contract_type in ['suit', 'high', 'low']:
        correlations = correlations_by_contract.get(contract_type, {})
        if not correlations:
            continue
        
        sorted_corrs = sorted(correlations.items(), key=lambda x: -abs(x[1][0]))[:10]
        
        print(f"\n{contract_type.upper()} CONTRACTS:")
        print("-" * 100)
        print(f"{'Rank':<5} {'Feature':<32} {'Correlation':<15} {'Direction':<20}")
        print("-" * 100)
        
        for rank, (fname, (corr, n)) in enumerate(sorted_corrs, 1):
            if corr > 0.05:
                direction = "✅ Positive"
            elif corr < -0.05:
                direction = "⚠️  Negative"
            else:
                direction = "➖ Weak"
            
            print(f"{rank:<5} {fname:<32} {corr:+.4f}         {direction:<20}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python plot_correlations_by_contract.py <train_jsonl_path> <output_dir> <title_prefix>")
        sys.exit(1)
    
    jsonl_path = sys.argv[1]
    output_dir = sys.argv[2]
    title_prefix = sys.argv[3] + " - " if sys.argv[3] else ""
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading data from: {jsonl_path}")
    correlations_by_contract = compute_correlations_by_contract(jsonl_path)
    
    print("\nGenerating charts by contract type...")
    plot_contract_correlations(correlations_by_contract, output_dir, title_prefix)
    
    print_summary_table(correlations_by_contract)
    
    print("\n" + "=" * 100)
    print("✅ All contract-specific correlation charts generated!")
    print("=" * 100)


if __name__ == "__main__":
    main()
