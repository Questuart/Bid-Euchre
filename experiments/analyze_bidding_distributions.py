#!/usr/bin/env python3
"""
Analyze bidding distributions from the Three-Horse Race experiment.

Generates plots showing the distribution of bid amounts by strategy.

Usage:
    PYTHONPATH=src python experiments/analyze_bidding_distributions.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import List, Dict, Any

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.regression import RegressionBidder

# Model Paths
BASELINE_MODELS = {
    'suit': 'data/models/baseline_regression/baseline_regression_suit.pkl',
    'high': 'data/models/baseline_regression/baseline_regression_high.pkl',
    'low': 'data/models/baseline_regression/baseline_regression_low.pkl'
}

HAND_VALUE_MODELS = {
    'suit': 'data/models/hand_value_ols/hand_value_ols_suit.pkl',
    'high': 'data/models/hand_value_ols/hand_value_ols_high.pkl',
    'low': 'data/models/hand_value_ols/hand_value_ols_low.pkl'
}

def collect_bidding_data(n_hands: int = 10000, seed: int = 42):
    """Run simulations and collect bidding data for each strategy."""
    print(f"Collecting bidding data ({n_hands:,} hands per strategy)...")
    
    # Define strategies
    fred = RegressionBidder(
        model_paths=HAND_VALUE_MODELS, 
        name="FiveHeadFred", 
        fixed_bid=5
    )
    olsa_sr = RegressionBidder(
        model_paths=HAND_VALUE_MODELS, 
        name="OLSa_SR", 
        policy="round"
    )
    olsa = RegressionBidder(
        model_paths=BASELINE_MODELS, 
        name="OLSa", 
        policy="round"
    )
    
    # Storage for bid data
    bid_data = {
        "FiveHeadFred": [],
        "OLSa_SR": [],
        "OLSa": []
    }
    
    # For reproducibility
    import random
    
    # Run each strategy pairing to collect bids
    strategies_list = [
        ("OLSa vs FiveHeadFred", [olsa, fred, olsa, fred]),
        ("OLSa vs OLSa_SR", [olsa, olsa_sr, olsa, olsa_sr]),
        ("OLSa_SR vs FiveHeadFred", [olsa_sr, fred, olsa_sr, fred]),
    ]
    
    for label, strategies in strategies_list:
        print(f"  Running {label}...")
        rng = random.Random(seed)
        
        for i in range(n_hands):
            t0, t1, _, _, leader, _, bid, _, _, _, _, _, _ = play_single_hand(
                contract_type=None,
                strategies=strategies,
                rng=rng,
                deal_id=i
            )
            
            # Skip misdeals
            if leader == -1 or bid == 0:
                continue
            
            # Record bid for the winning bidder's strategy
            bidder_strategy = strategies[leader].name
            bid_data[bidder_strategy].append(bid)
    
    return bid_data

def plot_bid_distributions(bid_data: Dict[str, List[int]], output_path: str):
    """Create visualization of bid distributions."""
    print("\nGenerating plots...")
    
    # Create figure with multiple subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Three-Horse Race: Bidding Behavior Analysis", fontsize=16, fontweight='bold')
    
    strategies = ["FiveHeadFred", "OLSa_SR", "OLSa"]
    colors = ["#e74c3c", "#3498db", "#2ecc71"]
    
    # 1. Histogram comparison
    ax1 = axes[0, 0]
    bins = np.arange(0, 13, 1)
    for strategy, color in zip(strategies, colors):
        if bid_data[strategy]:
            ax1.hist(bid_data[strategy], bins=bins, alpha=0.6, label=strategy, color=color, edgecolor='black')
    ax1.set_xlabel("Bid Amount", fontsize=12)
    ax1.set_ylabel("Frequency", fontsize=12)
    ax1.set_title("Bid Distribution (Overlaid Histograms)", fontsize=13, fontweight='bold')
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # 2. Side-by-side box plots
    ax2 = axes[0, 1]
    box_data = [bid_data[s] for s in strategies]
    bp = ax2.boxplot(box_data, labels=strategies, patch_artist=True, 
                      showmeans=True, meanline=True,
                      boxprops=dict(alpha=0.7),
                      medianprops=dict(color='red', linewidth=2),
                      meanprops=dict(color='blue', linewidth=2, linestyle='--'))
    
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    ax2.set_ylabel("Bid Amount", fontsize=12)
    ax2.set_title("Bid Distribution (Box Plots)", fontsize=13, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    ax2.set_ylim(0, 12)
    
    # 3. Violin plots
    ax3 = axes[1, 0]
    parts = ax3.violinplot(box_data, positions=range(1, len(strategies)+1), 
                            showmeans=True, showmedians=True)
    
    for i, (pc, color) in enumerate(zip(parts['bodies'], colors)):
        pc.set_facecolor(color)
        pc.set_alpha(0.7)
    
    ax3.set_xticks(range(1, len(strategies)+1))
    ax3.set_xticklabels(strategies)
    ax3.set_ylabel("Bid Amount", fontsize=12)
    ax3.set_title("Bid Distribution (Violin Plots)", fontsize=13, fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    ax3.set_ylim(0, 12)
    
    # 4. Statistics table
    ax4 = axes[1, 1]
    ax4.axis('off')
    
    # Calculate statistics
    stats_data = []
    for strategy in strategies:
        bids = bid_data[strategy]
        if bids:
            stats_data.append([
                strategy,
                f"{np.mean(bids):.2f}",
                f"{np.median(bids):.1f}",
                f"{np.std(bids):.2f}",
                f"{min(bids)}",
                f"{max(bids)}",
                f"{len(bids):,}"
            ])
    
    table = ax4.table(
        cellText=stats_data,
        colLabels=["Strategy", "Mean", "Median", "Std Dev", "Min", "Max", "N Bids"],
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header
    for i in range(7):
        table[(0, i)].set_facecolor('#34495e')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Color rows
    for i, color in enumerate(colors, start=1):
        for j in range(7):
            table[(i, j)].set_facecolor(color)
            table[(i, j)].set_alpha(0.3)
    
    ax4.set_title("Bidding Statistics Summary", fontsize=13, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved plot to: {output_path}")
    
    # Also print detailed statistics
    print("\n" + "="*80)
    print("DETAILED BIDDING STATISTICS")
    print("="*80)
    for strategy in strategies:
        bids = bid_data[strategy]
        if bids:
            print(f"\n{strategy}:")
            print(f"  Total Bids: {len(bids):,}")
            print(f"  Mean: {np.mean(bids):.3f}")
            print(f"  Median: {np.median(bids):.1f}")
            print(f"  Std Dev: {np.std(bids):.3f}")
            print(f"  Min: {min(bids)}")
            print(f"  Max: {max(bids)}")
            print(f"  25th percentile: {np.percentile(bids, 25):.1f}")
            print(f"  75th percentile: {np.percentile(bids, 75):.1f}")
            
            # Bid frequency
            unique, counts = np.unique(bids, return_counts=True)
            print(f"  Bid frequency:")
            for bid_val, count in zip(unique, counts):
                pct = 100 * count / len(bids)
                print(f"    {bid_val}: {count:>6,} ({pct:>5.1f}%)")
    print("="*80)

if __name__ == "__main__":
    # Collect data
    bid_data = collect_bidding_data(n_hands=10000, seed=42)
    
    # Generate plots
    output_path = "data/reports/bidding_distributions.png"
    plot_bid_distributions(bid_data, output_path)
    
    print("\n✅ Analysis complete!")
