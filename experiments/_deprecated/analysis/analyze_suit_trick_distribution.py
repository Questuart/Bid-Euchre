#!/usr/bin/env python3
"""
Analyze the distribution of tricks won on SUIT contracts for OLSa vs CCrider.

Usage:
    PYTHONPATH=src python experiments/analyze_suit_trick_distribution.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.regression import RegressionBidder

# Model Paths
BASELINE_MODELS = {
    'suit': 'data/models/baseline_regression/baseline_regression_suit.pkl',
    'high': 'data/models/baseline_regression/baseline_regression_high.pkl',
    'low': 'data/models/baseline_regression/baseline_regression_low.pkl'
}

def run_analysis(n_hands: int = 20000, seed: int = 42):
    """Collect suit contract trick distributions."""
    print(f"Analyzing Suit Contract Trick Distributions ({n_hands:,} hands, seed={seed})")
    print("-" * 80)
    
    # Define strategies
    olsa = RegressionBidder(
        model_paths=BASELINE_MODELS, 
        name="OLSa", 
        policy="round"
    )
    
    olsa_ccrider = RegressionBidder(
        model_paths=BASELINE_MODELS, 
        name="OLSa_CCrider", 
        policy="ccrider"
    )
    
    # Team 0 = OLSa (seats 0, 2)
    # Team 1 = OLSa_CCrider (seats 1, 3)
    strategies = [olsa, olsa_ccrider, olsa, olsa_ccrider]
    
    # Storage for suit contracts only
    olsa_tricks = []
    ccrider_tricks = []
    olsa_bids = []
    ccrider_bids = []
    
    # For reproducibility
    import random
    rng = random.Random(seed)
    
    for i in range(n_hands):
        if i % 5000 == 0 and i > 0:
            print(f"  Progress: {i:,}/{n_hands:,} hands")
        
        t0, t1, _, _, leader, starting_hands, bid, _, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            rng=rng,
            deal_id=i
        )
        
        if leader == -1:
            continue
        
        # Get contract type
        bid_amount, contract_type, trump_suit = strategies[leader].decide_bid(
            hand=starting_hands[leader],
            current_high_bid=0,
            current_winner_index=None,
            partner_index=(leader + 2) % 4,
            player_index=leader
        )
        
        # Only track suit contracts
        if contract_type != "suit":
            continue
        
        # Track by which team won the bid
        winning_team = 0 if leader in (0, 2) else 1
        tricks_won = t0 if winning_team == 0 else t1
        
        if winning_team == 0:
            olsa_tricks.append(tricks_won)
            olsa_bids.append(bid)
        else:
            ccrider_tricks.append(tricks_won)
            ccrider_bids.append(bid)
    
    # Convert to numpy arrays
    olsa_tricks = np.array(olsa_tricks)
    ccrider_tricks = np.array(ccrider_tricks)
    olsa_bids = np.array(olsa_bids)
    ccrider_bids = np.array(ccrider_bids)
    
    # Print statistics
    print("\n" + "="*80)
    print("SUIT CONTRACT STATISTICS")
    print("="*80)
    print(f"\nOLSa (n={len(olsa_tricks):,} suit contracts won):")
    print(f"  Tricks Won:  Mean={olsa_tricks.mean():.2f}, Median={np.median(olsa_tricks):.1f}, Std={olsa_tricks.std():.2f}")
    print(f"  Bid Amount:  Mean={olsa_bids.mean():.2f}, Median={np.median(olsa_bids):.1f}, Std={olsa_bids.std():.2f}")
    print(f"  Made Bid:    {(olsa_tricks >= olsa_bids).sum():,} / {len(olsa_tricks):,} ({(olsa_tricks >= olsa_bids).mean()*100:.1f}%)")
    
    print(f"\nOLSa_CCrider (n={len(ccrider_tricks):,} suit contracts won):")
    print(f"  Tricks Won:  Mean={ccrider_tricks.mean():.2f}, Median={np.median(ccrider_tricks):.1f}, Std={ccrider_tricks.std():.2f}")
    print(f"  Bid Amount:  Mean={ccrider_bids.mean():.2f}, Median={np.median(ccrider_bids):.1f}, Std={ccrider_bids.std():.2f}")
    print(f"  Made Bid:    {(ccrider_tricks >= ccrider_bids).sum():,} / {len(ccrider_tricks):,} ({(ccrider_tricks >= ccrider_bids).mean()*100:.1f}%)")
    
    # Distribution breakdown
    print("\n" + "="*80)
    print("TRICK COUNT DISTRIBUTION")
    print("="*80)
    print(f"\n{'Tricks':<10} {'OLSa':<20} {'CCrider':<20}")
    print("-" * 50)
    for trick_count in range(11):
        olsa_count = (olsa_tricks == trick_count).sum()
        ccrider_count = (ccrider_tricks == trick_count).sum()
        olsa_pct = olsa_count / len(olsa_tricks) * 100 if len(olsa_tricks) > 0 else 0
        ccrider_pct = ccrider_count / len(ccrider_tricks) * 100 if len(ccrider_tricks) > 0 else 0
        print(f"{trick_count:<10} {olsa_count:>6} ({olsa_pct:>5.1f}%)    {ccrider_count:>6} ({ccrider_pct:>5.1f}%)")
    
    # Create visualizations
    create_plots(olsa_tricks, ccrider_tricks, olsa_bids, ccrider_bids)
    
    print("\n✅ Analysis complete! Plots saved to data/reports/")

def create_plots(olsa_tricks, ccrider_tricks, olsa_bids, ccrider_bids):
    """Create visualization plots."""
    
    fig = plt.figure(figsize=(16, 10))
    
    # 1. Histogram of Tricks Won
    ax1 = plt.subplot(2, 3, 1)
    bins = np.arange(-0.5, 11.5, 1)
    ax1.hist(olsa_tricks, bins=bins, alpha=0.6, label='OLSa', color='steelblue', edgecolor='black')
    ax1.hist(ccrider_tricks, bins=bins, alpha=0.6, label='CCrider', color='coral', edgecolor='black')
    ax1.set_xlabel('Tricks Won', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax1.set_title('Distribution of Tricks Won\n(Suit Contracts)', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(range(11))
    
    # 2. Histogram of Bid Amounts
    ax2 = plt.subplot(2, 3, 2)
    bins = np.arange(4.5, 11.5, 1)
    ax2.hist(olsa_bids, bins=bins, alpha=0.6, label='OLSa', color='steelblue', edgecolor='black')
    ax2.hist(ccrider_bids, bins=bins, alpha=0.6, label='CCrider', color='coral', edgecolor='black')
    ax2.set_xlabel('Bid Amount', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax2.set_title('Distribution of Bid Amounts\n(Suit Contracts)', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(range(5, 11))
    
    # 3. Box Plot of Tricks Won
    ax3 = plt.subplot(2, 3, 3)
    bp = ax3.boxplot([olsa_tricks, ccrider_tricks], 
                      labels=['OLSa', 'CCrider'],
                      patch_artist=True,
                      widths=0.5)
    bp['boxes'][0].set_facecolor('steelblue')
    bp['boxes'][1].set_facecolor('coral')
    ax3.set_ylabel('Tricks Won', fontsize=11, fontweight='bold')
    ax3.set_title('Box Plot: Tricks Won\n(Suit Contracts)', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.set_yticks(range(11))
    
    # 4. Scatter: Bid vs Tricks Won (with binned means)
    ax4 = plt.subplot(2, 3, 4)
    ax4.scatter(olsa_bids, olsa_tricks, alpha=0.3, s=20, label='OLSa (raw)', color='steelblue')
    ax4.scatter(ccrider_bids, ccrider_tricks, alpha=0.3, s=20, label='CCrider (raw)', color='coral')
    
    # Calculate binned means for each bid amount
    for bid_val in range(5, 11):
        olsa_mask = olsa_bids == bid_val
        ccrider_mask = ccrider_bids == bid_val
        
        if olsa_mask.sum() > 0:
            olsa_mean = olsa_tricks[olsa_mask].mean()
            ax4.plot(bid_val, olsa_mean, 'D', markersize=10, color='darkblue', 
                    markeredgecolor='white', markeredgewidth=1.5, zorder=5)
        
        if ccrider_mask.sum() > 0:
            ccrider_mean = ccrider_tricks[ccrider_mask].mean()
            ax4.plot(bid_val, ccrider_mean, 'D', markersize=10, color='darkred', 
                    markeredgecolor='white', markeredgewidth=1.5, zorder=5)
    
    # Connect binned means with lines
    olsa_binned_means = []
    ccrider_binned_means = []
    bid_values = []
    
    for bid_val in range(5, 11):
        olsa_mask = olsa_bids == bid_val
        ccrider_mask = ccrider_bids == bid_val
        
        if olsa_mask.sum() > 0 or ccrider_mask.sum() > 0:
            bid_values.append(bid_val)
            olsa_binned_means.append(olsa_tricks[olsa_mask].mean() if olsa_mask.sum() > 0 else np.nan)
            ccrider_binned_means.append(ccrider_tricks[ccrider_mask].mean() if ccrider_mask.sum() > 0 else np.nan)
    
    ax4.plot(bid_values, olsa_binned_means, 'D-', color='darkblue', linewidth=2.5, 
            markersize=10, markeredgecolor='white', markeredgewidth=1.5, 
            label='OLSa (binned mean)', zorder=5)
    ax4.plot(bid_values, ccrider_binned_means, 'D-', color='darkred', linewidth=2.5, 
            markersize=10, markeredgecolor='white', markeredgewidth=1.5, 
            label='CCrider (binned mean)', zorder=5)
    
    ax4.plot([5, 10], [5, 10], 'k--', linewidth=1, alpha=0.5, label='Perfect (Bid=Tricks)')
    ax4.set_xlabel('Bid Amount', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Tricks Won', fontsize=11, fontweight='bold')
    ax4.set_title('Bid Amount vs Tricks Won\n(Suit Contracts)', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=8, loc='upper left')
    ax4.grid(True, alpha=0.3)
    ax4.set_xticks(range(5, 11))
    ax4.set_yticks(range(11))
    
    # 5. Percentage Distribution (Normalized Histogram)
    ax5 = plt.subplot(2, 3, 5)
    trick_bins = np.arange(11)
    olsa_dist = np.array([(olsa_tricks == t).sum() / len(olsa_tricks) * 100 for t in trick_bins])
    ccrider_dist = np.array([(ccrider_tricks == t).sum() / len(ccrider_tricks) * 100 for t in trick_bins])
    
    x = np.arange(11)
    width = 0.35
    ax5.bar(x - width/2, olsa_dist, width, label='OLSa', color='steelblue', edgecolor='black')
    ax5.bar(x + width/2, ccrider_dist, width, label='CCrider', color='coral', edgecolor='black')
    ax5.set_xlabel('Tricks Won', fontsize=11, fontweight='bold')
    ax5.set_ylabel('Percentage (%)', fontsize=11, fontweight='bold')
    ax5.set_title('Normalized Distribution\n(Suit Contracts)', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=10)
    ax5.grid(True, alpha=0.3, axis='y')
    ax5.set_xticks(range(11))
    
    # 6. Cumulative Distribution
    ax6 = plt.subplot(2, 3, 6)
    olsa_sorted = np.sort(olsa_tricks)
    ccrider_sorted = np.sort(ccrider_tricks)
    olsa_cdf = np.arange(1, len(olsa_sorted) + 1) / len(olsa_sorted) * 100
    ccrider_cdf = np.arange(1, len(ccrider_sorted) + 1) / len(ccrider_sorted) * 100
    
    ax6.plot(olsa_sorted, olsa_cdf, label='OLSa', color='steelblue', linewidth=2)
    ax6.plot(ccrider_sorted, ccrider_cdf, label='CCrider', color='coral', linewidth=2)
    ax6.set_xlabel('Tricks Won', fontsize=11, fontweight='bold')
    ax6.set_ylabel('Cumulative Percentage (%)', fontsize=11, fontweight='bold')
    ax6.set_title('Cumulative Distribution\n(Suit Contracts)', fontsize=12, fontweight='bold')
    ax6.legend(fontsize=10)
    ax6.grid(True, alpha=0.3)
    ax6.set_xticks(range(11))
    
    plt.tight_layout()
    
    # Save
    output_path = 'data/reports/suit_trick_distributions.png'
    os.makedirs('data/reports', exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 Saved plot: {output_path}")
    plt.close()

if __name__ == "__main__":
    run_analysis(n_hands=20000, seed=42)
