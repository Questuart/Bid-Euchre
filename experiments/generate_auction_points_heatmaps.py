#!/usr/bin/env python3
"""
Auction and Points Analysis Heatmaps

Creates heatmaps showing:
1. Win Auction % - How often each strategy wins the bidding auction
2. Total Points Won - Overall points accumulated in the matchup
3. Std Dev of Points/Hand - Volatility of points per hand

Usage:
    PYTHONPATH=src python experiments/generate_auction_points_heatmaps.py
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

def run_auction_analysis(n_hands: int = 10000, seed: int = 42):
    """Run analysis focusing on auction wins and points distribution."""
    print(f"Analyzing Auction and Points Metrics ({n_hands:,} hands per matchup)")
    print("-" * 80)
    
    # Define all 6 strategies
    strategies_dict = {
        "OLSa": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa", policy="round"),
        "OLSa_Floor": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_Floor", policy="floor"),
        "OLSa_Ceil": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_Ceil", policy="ceil"),
        "OLSa_CCrider": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_CCrider", policy="ccrider"),
        "OLSa_SR": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="OLSa_SR", policy="round"),
        "FiveHeadFred": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="FiveHeadFred", fixed_bid=5)
    }
    
    strategy_names = list(strategies_dict.keys())
    
    # Storage for results
    results = {}
    for s1 in strategy_names:
        results[s1] = {}
        for s2 in strategy_names:
            results[s1][s2] = {
                'team0_auction_wins': 0,
                'team1_auction_wins': 0,
                'team0_points': 0,
                'team1_points': 0,
                'team0_points_per_hand': [],  # Track for std dev
                'team1_points_per_hand': [],
                'valid_hands': 0
            }
    
    # Run all matchups
    import random
    
    for strat_a_name in strategy_names:
        for strat_b_name in strategy_names:
            print(f"\nAnalyzing: {strat_a_name} vs {strat_b_name}")
            
            strat_a = strategies_dict[strat_a_name]
            strat_b = strategies_dict[strat_b_name]
            
            # Team 0 = seats 0&2 (strat_a)
            # Team 1 = seats 1&3 (strat_b)
            strategies = [strat_a, strat_b, strat_a, strat_b]
            
            rng = random.Random(seed)
            
            for i in range(n_hands):
                t0, t1, _, _, leader, _, bid, _, _ = play_single_hand(
                    contract_type=None,
                    strategies=strategies,
                    rng=rng,
                    deal_id=i
                )
                
                if leader == -1:
                    continue
                
                r = results[strat_a_name][strat_b_name]
                r['valid_hands'] += 1
                
                # Track auction wins
                winning_team = 0 if leader in (0, 2) else 1
                if winning_team == 0:
                    r['team0_auction_wins'] += 1
                else:
                    r['team1_auction_wins'] += 1
                
                # Track points for this hand
                tricks_won = t0 if winning_team == 0 else t1
                made_bid = tricks_won >= bid
                
                team0_hand_points = 0
                team1_hand_points = 0
                
                if made_bid:
                    if winning_team == 0:
                        team0_hand_points = bid
                        r['team0_points'] += bid
                    else:
                        team1_hand_points = bid
                        r['team1_points'] += bid
                else:
                    if winning_team == 0:
                        team0_hand_points = -bid
                        r['team0_points'] -= bid
                    else:
                        team1_hand_points = -bid
                        r['team1_points'] -= bid
                
                # Store points per hand for std dev calculation
                r['team0_points_per_hand'].append(team0_hand_points)
                r['team1_points_per_hand'].append(team1_hand_points)
    
    return results, strategy_names

def create_auction_points_heatmaps(results: Dict, strategy_names: List[str], output_dir: str):
    """Create heatmaps for auction wins, total points, and points std dev."""
    print("\n" + "="*80)
    print("GENERATING AUCTION & POINTS HEATMAPS")
    print("="*80)
    
    os.makedirs(output_dir, exist_ok=True)
    
    n = len(strategy_names)
    
    # 1. Win Auction % matrix
    win_auction_matrix = np.zeros((n, n))
    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            total_auctions = r['team0_auction_wins'] + r['team1_auction_wins']
            win_auction_matrix[i, j] = (r['team0_auction_wins'] / total_auctions * 100) if total_auctions > 0 else 0
    
    # 2. Total Points Won matrix
    total_points_matrix = np.zeros((n, n))
    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            total_points_matrix[i, j] = r['team0_points']
    
    # 3. Std Dev of Points Per Hand matrix
    std_points_matrix = np.zeros((n, n))
    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            if len(r['team0_points_per_hand']) > 0:
                std_points_matrix[i, j] = np.std(r['team0_points_per_hand'])
            else:
                std_points_matrix[i, j] = 0
    
    # Create combined figure
    fig, axes = plt.subplots(1, 3, figsize=(22, 7))
    fig.suptitle("Auction and Points Analysis Heatmaps\nPoints-Based Scoring", 
                 fontsize=18, fontweight='bold', y=0.98)
    
    # Helper function to create heatmap
    def create_heatmap(ax, data, title, cmap, vmin, vmax, cbar_label, fmt='.1f'):
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(cbar_label, fontsize=11, fontweight='bold')
        
        # Ticks and labels
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(strategy_names, rotation=45, ha='right', fontsize=11)
        ax.set_yticklabels(strategy_names, fontsize=11)
        
        # Add text annotations
        for i in range(n):
            for j in range(n):
                # Choose text color based on background
                text_color = 'white' if (data[i, j] < (vmin + (vmax - vmin) * 0.5)) else 'black'
                
                # Format number based on type
                if fmt == '.0f':
                    text_val = f'{data[i, j]:.0f}'
                elif fmt == '.1f':
                    text_val = f'{data[i, j]:.1f}'
                elif fmt == '.2f':
                    text_val = f'{data[i, j]:.2f}'
                else:
                    text_val = f'{data[i, j]:{fmt}}'
                
                text = ax.text(j, i, text_val,
                             ha="center", va="center", color=text_color, 
                             fontsize=10, fontweight='bold')
        
        ax.set_title(title, fontsize=13, fontweight='bold', pad=15)
        ax.set_xlabel("Opponent Strategy", fontsize=12, fontweight='bold')
        ax.set_ylabel("Strategy", fontsize=12, fontweight='bold')
    
    # 1. Win Auction %
    create_heatmap(axes[0], win_auction_matrix, 
                   "Win Auction Rate (%)\n(% of times strategy wins the bid)",
                   'RdYlGn', 0, 100, 'Auction Win %', fmt='.1f')
    
    # 2. Total Points Won
    create_heatmap(axes[1], total_points_matrix,
                   "Total Points Accumulated\n(Over 10,000 hands)",
                   'RdYlGn', -5000, 15000, 'Total Points', fmt='.0f')
    
    # 3. Std Dev of Points Per Hand
    create_heatmap(axes[2], std_points_matrix,
                   "Volatility (Std Dev)\n(Points per hand variability)",
                   'YlOrRd', 0, 8, 'Std Dev', fmt='.2f')
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    output_path = os.path.join(output_dir, "auction_points_heatmaps.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved heatmaps to: {output_path}")
    
    # Print summary tables
    print("\n" + "="*80)
    print("WIN AUCTION RATE MATRIX (%)")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>12}" for s in strategy_names]))
    print("-" * 120)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{win_auction_matrix[i,j]:>11.1f}%" for j in range(n)])
        print(row_str)
    print("="*120)
    
    print("\n" + "="*80)
    print("TOTAL POINTS ACCUMULATED MATRIX")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>12}" for s in strategy_names]))
    print("-" * 120)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{total_points_matrix[i,j]:>12,.0f}" for j in range(n)])
        print(row_str)
    print("="*120)
    
    print("\n" + "="*80)
    print("VOLATILITY (STD DEV OF POINTS/HAND) MATRIX")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>12}" for s in strategy_names]))
    print("-" * 120)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{std_points_matrix[i,j]:>12.2f}" for j in range(n)])
        print(row_str)
    print("="*120)

if __name__ == "__main__":
    results, strategy_names = run_auction_analysis(n_hands=10000, seed=42)
    create_auction_points_heatmaps(results, strategy_names, output_dir="data/reports")
    print("\n✅ Auction and points analysis complete!")
