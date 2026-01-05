#!/usr/bin/env python3
"""
Analyze which player (seat) wins the bid by strategy.

Shows positional bias in bidding and which strategies win from which seats.

Usage:
    PYTHONPATH=src python experiments/analyze_bid_winners.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict

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

def collect_bid_winner_data(n_hands: int = 10000, seed: int = 42):
    """Run simulations and collect which seat wins the bid for each strategy."""
    print(f"Collecting bid winner data ({n_hands:,} hands per matchup)...")
    
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
    
    # Storage for seat data by strategy
    # seat_data[strategy_name] = [seat0_count, seat1_count, seat2_count, seat3_count]
    seat_data = {
        "FiveHeadFred": [0, 0, 0, 0],
        "OLSa_SR": [0, 0, 0, 0],
        "OLSa": [0, 0, 0, 0]
    }
    
    # Also track which matchup for context
    matchup_data = {
        "FiveHeadFred": {"vs_OLSa": [0,0,0,0], "vs_OLSa_SR": [0,0,0,0]},
        "OLSa_SR": {"vs_OLSa": [0,0,0,0], "vs_FiveHeadFred": [0,0,0,0]},
        "OLSa": {"vs_FiveHeadFred": [0,0,0,0], "vs_OLSa_SR": [0,0,0,0]}
    }
    
    # For reproducibility
    import random
    
    # Run each strategy pairing
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
            
            # Record seat for the winning bidder's strategy
            bidder_strategy = strategies[leader].name
            seat_data[bidder_strategy][leader] += 1
            
            # Track by matchup too
            if "FiveHeadFred" in label and "OLSa_SR" in label:
                if bidder_strategy == "FiveHeadFred":
                    matchup_data["FiveHeadFred"]["vs_OLSa_SR"][leader] += 1
                elif bidder_strategy == "OLSa_SR":
                    matchup_data["OLSa_SR"]["vs_FiveHeadFred"][leader] += 1
            elif "OLSa" in label and "FiveHeadFred" in label and "OLSa_SR" not in label:
                if bidder_strategy == "FiveHeadFred":
                    matchup_data["FiveHeadFred"]["vs_OLSa"][leader] += 1
                elif bidder_strategy == "OLSa":
                    matchup_data["OLSa"]["vs_FiveHeadFred"][leader] += 1
            elif "OLSa" in label and "OLSa_SR" in label:
                if bidder_strategy == "OLSa":
                    matchup_data["OLSa"]["vs_OLSa_SR"][leader] += 1
                elif bidder_strategy == "OLSa_SR":
                    matchup_data["OLSa_SR"]["vs_OLSa"][leader] += 1
    
    return seat_data, matchup_data

def plot_bid_winners(seat_data: Dict[str, List[int]], output_path: str):
    """Create visualization of bid winners by seat."""
    print("\nGenerating plots...")
    
    strategies = ["FiveHeadFred", "OLSa_SR", "OLSa"]
    colors = ["#e74c3c", "#3498db", "#2ecc71"]
    
    fig = plt.figure(figsize=(16, 10))
    
    # Overall title
    fig.suptitle("Three-Horse Race: Bid Winners by Seat Position", fontsize=16, fontweight='bold', y=0.98)
    
    # 1. Grouped bar chart - top left
    ax1 = plt.subplot(2, 3, 1)
    x = np.arange(4)  # 4 seats
    width = 0.25
    
    for i, (strategy, color) in enumerate(zip(strategies, colors)):
        counts = seat_data[strategy]
        offset = (i - 1) * width
        ax1.bar(x + offset, counts, width, label=strategy, color=color, alpha=0.8, edgecolor='black')
    
    ax1.set_xlabel("Seat Position", fontsize=11)
    ax1.set_ylabel("Number of Bids Won", fontsize=11)
    ax1.set_title("Bid Winners by Seat (Absolute)", fontsize=12, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['Seat 0\n(LOD)', 'Seat 1', 'Seat 2', 'Seat 3\n(Dealer)'], fontsize=9)
    ax1.legend(fontsize=9)
    ax1.grid(axis='y', alpha=0.3)
    
    # 2. Percentage bar chart - top middle
    ax2 = plt.subplot(2, 3, 2)
    
    for i, (strategy, color) in enumerate(zip(strategies, colors)):
        counts = seat_data[strategy]
        total = sum(counts)
        percentages = [100 * c / total if total > 0 else 0 for c in counts]
        offset = (i - 1) * width
        ax2.bar(x + offset, percentages, width, label=strategy, color=color, alpha=0.8, edgecolor='black')
    
    ax2.set_xlabel("Seat Position", fontsize=11)
    ax2.set_ylabel("Percentage of Bids Won (%)", fontsize=11)
    ax2.set_title("Bid Winners by Seat (Percentage)", fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], fontsize=9)
    ax2.legend(fontsize=9)
    ax2.grid(axis='y', alpha=0.3)
    ax2.axhline(y=25, color='red', linestyle='--', alpha=0.5, linewidth=1)
    
    # 3. Statistics table - top right
    ax3 = plt.subplot(2, 3, 3)
    ax3.axis('off')
    
    stats_data = []
    for strategy in strategies:
        counts = seat_data[strategy]
        total = sum(counts)
        if total > 0:
            percentages = [100 * c / total for c in counts]
            stats_data.append([
                strategy,
                f"{total:,}",
                f"{percentages[0]:.1f}%",
                f"{percentages[1]:.1f}%",
                f"{percentages[2]:.1f}%",
                f"{percentages[3]:.1f}%"
            ])
    
    table = ax3.table(
        cellText=stats_data,
        colLabels=["Strategy", "Total", "S0", "S1", "S2", "S3"],
        loc='center',
        cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.2)
    
    # Style header
    for i in range(6):
        table[(0, i)].set_facecolor('#34495e')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Color rows
    for i, color in enumerate(colors, start=1):
        for j in range(6):
            table[(i, j)].set_facecolor(color)
            table[(i, j)].set_alpha(0.3)
    
    ax3.set_title("Summary Statistics", fontsize=12, fontweight='bold', pad=15)
    
    # 4-6. Individual pie charts for each strategy - bottom row
    seat_labels = ['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3']
    pie_colors = ['#ffcccc', '#ccddff', '#ccffcc', '#ffffcc']
    
    for i, (strategy, color) in enumerate(zip(strategies, colors)):
        ax = plt.subplot(2, 3, 4 + i)
        counts = seat_data[strategy]
        total = sum(counts)
        
        if total > 0:
            wedges, texts, autotexts = ax.pie(
                counts, 
                labels=seat_labels,
                autopct=lambda pct: f'{pct:.1f}%' if pct > 2 else '',
                colors=pie_colors,
                startangle=90,
                textprops={'fontsize': 9}
            )
            
            for autotext in autotexts:
                autotext.set_color('black')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(9)
            
            ax.set_title(f"{strategy}\n(Total Bids: {total:,})", 
                        fontsize=11, fontweight='bold', pad=10)
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved plot to: {output_path}")
    
    # Print detailed statistics
    print("\n" + "="*80)
    print("DETAILED SEAT POSITION STATISTICS")
    print("="*80)
    for strategy in strategies:
        counts = seat_data[strategy]
        total = sum(counts)
        print(f"\n{strategy} (Total: {total:,} bids won):")
        for seat, count in enumerate(counts):
            pct = 100 * count / total if total > 0 else 0
            print(f"  Seat {seat}: {count:>6,} ({pct:>5.1f}%)")
    print("="*80)

if __name__ == "__main__":
    # Collect data
    seat_data, matchup_data = collect_bid_winner_data(n_hands=10000, seed=42)
    
    # Generate plots
    output_path = "data/reports/bid_winners_by_seat.png"
    plot_bid_winners(seat_data, output_path)
    
    print("\n✅ Analysis complete!")
