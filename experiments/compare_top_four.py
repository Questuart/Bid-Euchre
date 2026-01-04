#!/usr/bin/env python3
"""
Top 4 Strategy Comparison Dashboard

Comparison of OLSa, OLSa_Floor, OLSa_SR, and OLSa_SR_Floor.

OLSa_SR_Floor = Hand Value model (SR) + Floor rounding policy

Usage:
    PYTHONPATH=src python experiments/compare_top_four.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
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

def run_top_four_analysis(n_hands: int = 20000, seed: int = 42):
    """Run comprehensive analysis of top 4 strategies."""
    print(f"Analyzing Top 4 Strategies ({n_hands:,} hands per matchup)")
    print("-" * 80)
    
    # Define top 4 strategies
    strategies_dict = {
        "OLSa": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa", policy="round"),
        "OLSa_Floor": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_Floor", policy="floor"),
        "OLSa_SR": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="OLSa_SR", policy="round"),
        "OLSa_SR_Floor": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="OLSa_SR_Floor", policy="floor"),
    }
    
    strategy_names = list(strategies_dict.keys())
    
    # Storage for results
    results = {}
    for s1 in strategy_names:
        results[s1] = {}
        for s2 in strategy_names:
            results[s1][s2] = {
                'team0_wins': 0,
                'team1_wins': 0,
                'team0_points': 0,
                'team1_points': 0,
                'team0_bid_attempts': 0,
                'team1_bid_attempts': 0,
                'team0_bid_successes': 0,
                'team1_bid_successes': 0,
                'team0_auction_wins': 0,
                'team1_auction_wins': 0,
                'team0_points_per_hand': [],
                'valid_hands': 0
            }
    
    # Run all matchups
    import random
    
    for strat_a_name in strategy_names:
        for strat_b_name in strategy_names:
            print(f"\nAnalyzing: {strat_a_name} vs {strat_b_name}")
            
            strat_a = strategies_dict[strat_a_name]
            strat_b = strategies_dict[strat_b_name]
            
            strategies = [strat_a, strat_b, strat_a, strat_b]
            rng = random.Random(seed)
            
            for i in range(n_hands):
                if i % 5000 == 0 and i > 0:
                    print(f"  Progress: {i:,}/{n_hands:,}")
                
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
                
                # Track points
                tricks_won = t0 if winning_team == 0 else t1
                made_bid = tricks_won >= bid
                
                team0_hand_points = 0
                
                if made_bid:
                    if winning_team == 0:
                        r['team0_wins'] += 1
                        r['team0_points'] += bid
                        team0_hand_points = bid
                    else:
                        r['team1_wins'] += 1
                        r['team1_points'] += bid
                else:
                    if winning_team == 0:
                        r['team1_wins'] += 1
                        r['team0_points'] -= bid
                        team0_hand_points = -bid
                    else:
                        r['team0_wins'] += 1
                        r['team1_points'] -= bid
                
                r['team0_points_per_hand'].append(team0_hand_points)
                
                # Track bid attempts
                if winning_team == 0:
                    r['team0_bid_attempts'] += 1
                    if made_bid:
                        r['team0_bid_successes'] += 1
                else:
                    r['team1_bid_attempts'] += 1
                    if made_bid:
                        r['team1_bid_successes'] += 1
    
    return results, strategy_names

def create_top_four_dashboard(results: Dict, strategy_names: List[str], output_dir: str):
    """Create comprehensive dashboard comparing top 4 strategies."""
    print("\n" + "="*80)
    print("GENERATING TOP 4 COMPARISON DASHBOARD")
    print("="*80)
    
    os.makedirs(output_dir, exist_ok=True)
    
    n = len(strategy_names)
    
    # Calculate metrics
    metrics = {}
    for strat in strategy_names:
        metrics[strat] = {
            'avg_win_rate': [],
            'avg_make_rate': [],
            'avg_points_per_hand': [],
            'avg_auction_win': [],
            'avg_ev': [],
            'avg_volatility': []
        }
        
        for opponent in strategy_names:
            r = results[strat][opponent]
            valid = r['valid_hands']
            
            # Win rate
            win_rate = (r['team0_wins'] / valid * 100) if valid > 0 else 0
            metrics[strat]['avg_win_rate'].append(win_rate)
            
            # Make rate
            make_rate = (r['team0_bid_successes'] / r['team0_bid_attempts'] * 100) if r['team0_bid_attempts'] > 0 else 0
            metrics[strat]['avg_make_rate'].append(make_rate)
            
            # Points per hand
            pts_per_hand = r['team0_points'] / valid if valid > 0 else 0
            metrics[strat]['avg_points_per_hand'].append(pts_per_hand)
            
            # Auction win %
            total_auctions = r['team0_auction_wins'] + r['team1_auction_wins']
            auction_win = (r['team0_auction_wins'] / total_auctions * 100) if total_auctions > 0 else 0
            metrics[strat]['avg_auction_win'].append(auction_win)
            
            # EV when bidding
            ev = r['team0_points'] / r['team0_bid_attempts'] if r['team0_bid_attempts'] > 0 else 0
            metrics[strat]['avg_ev'].append(ev)
            
            # Volatility
            volatility = np.std(r['team0_points_per_hand']) if len(r['team0_points_per_hand']) > 0 else 0
            metrics[strat]['avg_volatility'].append(volatility)
    
    # Create figure
    fig = plt.figure(figsize=(20, 12))
    
    # Title
    fig.suptitle("Top 4 Strategy Comparison Dashboard\nFour-Way Horse Race", 
                 fontsize=18, fontweight='bold', y=0.98)
    
    # Colors for each strategy
    colors = {
        'OLSa': '#4C9BD3', 
        'OLSa_Floor': '#7ED957', 
        'OLSa_SR': '#FFA500',
        'OLSa_SR_Floor': '#FF1493'  # Hot pink for the new contender
    }
    
    # 1. Win Rate Comparison (Top Left)
    ax1 = plt.subplot(2, 3, 1)
    x_pos = np.arange(n)
    win_rates = [np.mean(metrics[s]['avg_win_rate']) for s in strategy_names]
    bars1 = ax1.bar(x_pos, win_rates, color=[colors[s] for s in strategy_names], 
                    edgecolor='black', linewidth=2, alpha=0.8)
    ax1.set_ylabel('Win Rate (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Average Win Rate\n(Across all matchups)', fontsize=13, fontweight='bold', pad=10)
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(strategy_names, rotation=30, ha='right', fontsize=10, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim(45, 55)
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars1, win_rates)):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    # Add winner marker
    winner_idx = np.argmax(win_rates)
    ax1.text(winner_idx, win_rates[winner_idx] + 1.2, '★', ha='center', fontsize=18, color='gold')
    
    # 2. Make Rate Comparison (Top Middle)
    ax2 = plt.subplot(2, 3, 2)
    make_rates = [np.mean(metrics[s]['avg_make_rate']) for s in strategy_names]
    bars2 = ax2.bar(x_pos, make_rates, color=[colors[s] for s in strategy_names], 
                    edgecolor='black', linewidth=2, alpha=0.8)
    ax2.set_ylabel('Make Rate (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Average Make Rate\n(% of bids successfully made)', fontsize=13, fontweight='bold', pad=10)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(strategy_names, rotation=30, ha='right', fontsize=10, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim(50, 80)
    
    for i, (bar, val) in enumerate(zip(bars2, make_rates)):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    winner_idx = np.argmax(make_rates)
    ax2.text(winner_idx, make_rates[winner_idx] + 1.8, '★', ha='center', fontsize=18, color='gold')
    
    # 3. Points Per Hand (Top Right) - MOST IMPORTANT
    ax3 = plt.subplot(2, 3, 3)
    pts_per_hand = [np.mean(metrics[s]['avg_points_per_hand']) for s in strategy_names]
    bars3 = ax3.bar(x_pos, pts_per_hand, color=[colors[s] for s in strategy_names], 
                    edgecolor='black', linewidth=3, alpha=0.9)
    ax3.set_ylabel('Avg Points Per Hand', fontsize=12, fontweight='bold')
    ax3.set_title('★ AVERAGE POINTS PER HAND ★\n(PRIMARY METRIC)', 
                  fontsize=13, fontweight='bold', pad=10, color='darkred')
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(strategy_names, rotation=30, ha='right', fontsize=10, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax3.set_ylim(0, 1.3)
    
    for i, (bar, val) in enumerate(zip(bars3, pts_per_hand)):
        color = 'darkgreen' if val == max(pts_per_hand) else 'black'
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{val:+.3f}', ha='center', va='bottom', fontweight='bold', 
                fontsize=11, color=color)
    
    winner_idx = np.argmax(pts_per_hand)
    ax3.text(winner_idx, pts_per_hand[winner_idx] + 0.08, '★ WINNER', 
             ha='center', fontsize=13, color='gold', fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.3', facecolor='darkgreen', alpha=0.8, edgecolor='gold', linewidth=2))
    
    # 4. Auction Win % (Bottom Left)
    ax4 = plt.subplot(2, 3, 4)
    auction_wins = [np.mean(metrics[s]['avg_auction_win']) for s in strategy_names]
    bars4 = ax4.bar(x_pos, auction_wins, color=[colors[s] for s in strategy_names], 
                    edgecolor='black', linewidth=2, alpha=0.8)
    ax4.set_ylabel('Auction Win %', fontsize=12, fontweight='bold')
    ax4.set_title('Average Auction Win Rate\n(% of times wins the bid)', fontsize=13, fontweight='bold', pad=10)
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(strategy_names, rotation=30, ha='right', fontsize=10, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')
    
    for i, (bar, val) in enumerate(zip(bars4, auction_wins)):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    # 5. Expected Value When Bidding (Bottom Middle)
    ax5 = plt.subplot(2, 3, 5)
    evs = [np.mean(metrics[s]['avg_ev']) for s in strategy_names]
    bars5 = ax5.bar(x_pos, evs, color=[colors[s] for s in strategy_names], 
                    edgecolor='black', linewidth=2, alpha=0.8)
    ax5.set_ylabel('Expected Value', fontsize=12, fontweight='bold')
    ax5.set_title('Expected Value When Bidding\n(Avg points per bid attempt)', fontsize=13, fontweight='bold', pad=10)
    ax5.set_xticks(x_pos)
    ax5.set_xticklabels(strategy_names, rotation=30, ha='right', fontsize=10, fontweight='bold')
    ax5.grid(True, alpha=0.3, axis='y')
    ax5.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    
    for i, (bar, val) in enumerate(zip(bars5, evs)):
        ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.08,
                f'{val:+.2f}', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    winner_idx = np.argmax(evs)
    ax5.text(winner_idx, evs[winner_idx] + 0.2, '★', ha='center', fontsize=18, color='gold')
    
    # 6. Risk-Reward Profile (Bottom Right)
    ax6 = plt.subplot(2, 3, 6)
    volatilities = [np.mean(metrics[s]['avg_volatility']) for s in strategy_names]
    
    # Create scatter plot
    for i, strat in enumerate(strategy_names):
        ax6.scatter(volatilities[i], pts_per_hand[i], s=800, 
                   color=colors[strat], edgecolor='black', linewidth=2.5,
                   alpha=0.7, zorder=5)
        ax6.annotate(strat, (volatilities[i], pts_per_hand[i]),
                    xytext=(0, -20), textcoords='offset points',
                    ha='center', fontsize=9, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                             alpha=0.9, edgecolor='black', linewidth=1.5))
    
    ax6.set_xlabel('Volatility (Std Dev)', fontsize=12, fontweight='bold')
    ax6.set_ylabel('Avg Points Per Hand', fontsize=12, fontweight='bold')
    ax6.set_title('Risk-Reward Profile\n(Lower left = Best)', fontsize=13, fontweight='bold', pad=10)
    ax6.grid(True, alpha=0.3)
    ax6.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    
    # Add target zone
    rect = Rectangle((3, 0.8), 1, 0.4, linewidth=2, edgecolor='green', 
                     facecolor='green', alpha=0.1, linestyle='--')
    ax6.add_patch(rect)
    ax6.text(3.5, 1.0, 'IDEAL\nZONE', ha='center', va='center', 
            fontsize=8, fontweight='bold', color='darkgreen')
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    output_path = os.path.join(output_dir, "top_four_comparison.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved dashboard to: {output_path}")
    
    # Print detailed summary
    print("\n" + "="*80)
    print("COMPREHENSIVE COMPARISON SUMMARY")
    print("="*80)
    
    for strat in strategy_names:
        print(f"\n{strat}:")
        print(f"  Avg Win Rate:        {np.mean(metrics[strat]['avg_win_rate']):.2f}%")
        print(f"  Avg Make Rate:       {np.mean(metrics[strat]['avg_make_rate']):.2f}%")
        print(f"  Avg Pts/Hand:        {np.mean(metrics[strat]['avg_points_per_hand']):+.3f}")
        print(f"  Avg Auction Win:     {np.mean(metrics[strat]['avg_auction_win']):.2f}%")
        print(f"  Avg EV When Bidding: {np.mean(metrics[strat]['avg_ev']):+.2f}")
        print(f"  Avg Volatility:      {np.mean(metrics[strat]['avg_volatility']):.2f}")
    
    # Determine winner
    print("\n" + "="*80)
    print("🏆 FINAL VERDICT")
    print("="*80)
    
    best_idx = np.argmax(pts_per_hand)
    winner = strategy_names[best_idx]
    
    print(f"\n★★★ BEST STRATEGY: {winner} ★★★")
    print(f"\nPoints Per Hand: {pts_per_hand[best_idx]:+.3f}")
    print(f"\nPerformance vs Others:")
    for i, strat in enumerate(strategy_names):
        if i != best_idx:
            diff = pts_per_hand[best_idx] - pts_per_hand[i]
            pct_better = (diff / pts_per_hand[i]) * 100
            print(f"  • {pct_better:+.1f}% better than {strat}")
    
    print(f"\nKey Strengths:")
    print(f"  • Make Rate: {make_rates[best_idx]:.1f}%")
    print(f"  • EV: {evs[best_idx]:+.2f}")
    print(f"  • Volatility: {volatilities[best_idx]:.2f}")
    
    print("="*80)

if __name__ == "__main__":
    results, strategy_names = run_top_four_analysis(n_hands=20000, seed=42)
    create_top_four_dashboard(results, strategy_names, output_dir="data/reports")
    print("\n✅ Top 4 comparison complete!")
