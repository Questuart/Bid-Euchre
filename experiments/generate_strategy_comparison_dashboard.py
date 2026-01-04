#!/usr/bin/env python3
"""
Strategy Comparison Dashboard

Compares all bidding strategies on:
1. Make rate (% of bids successfully made)
2. Average points when making the bid
3. Average points per hand

Usage:
    PYTHONPATH=src python experiments/generate_strategy_comparison_dashboard.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List
from collections import defaultdict

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

def run_comprehensive_analysis(n_hands_per_matchup: int = 20000, seed: int = 42):
    """Run all strategies and collect comprehensive statistics."""
    print(f"Collecting comprehensive strategy statistics...")
    print(f"Running {n_hands_per_matchup:,} hands per matchup")
    print("-" * 80)
    
    # Define all strategies
    strategies_dict = {
        "OLSa": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa", policy="round"),
        "OLSa_Floor": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_Floor", policy="floor"),
        "OLSa_Ceil": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_Ceil", policy="ceil"),
        "OLSa_CCrider": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa_CCrider", policy="ccrider"),
        "OLSa_SR": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="OLSa_SR", policy="round"),
        "FiveHeadFred": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="FiveHeadFred", fixed_bid=5)
    }
    
    strategy_names = list(strategies_dict.keys())
    
    # Storage for each strategy's statistics
    stats = {}
    for name in strategy_names:
        stats[name] = {
            'total_hands': 0,
            'bid_attempts': 0,
            'bid_successes': 0,
            'points_when_success': [],  # List of points earned when making bid
            'points_when_failure': [],  # List of points lost when failing bid
            'total_points': 0,
            'bid_amounts': []
        }
    
    import random
    
    # Run each strategy against a neutral opponent (OLSa)
    neutral_opponent = "OLSa"
    
    for strat_name in strategy_names:
        print(f"\nAnalyzing {strat_name}...")
        
        strat = strategies_dict[strat_name]
        opponent = strategies_dict[neutral_opponent]
        
        # Team 0 = strategy being analyzed (seats 0, 2)
        # Team 1 = neutral opponent (seats 1, 3)
        strategies = [strat, opponent, strat, opponent]
        
        rng = random.Random(seed + hash(strat_name) % 10000)
        
        for i in range(n_hands_per_matchup):
            if i % 5000 == 0 and i > 0:
                print(f"  Progress: {i:,}/{n_hands_per_matchup:,} hands")
            
            t0, t1, _, _, leader, _, bid, _, _ = play_single_hand(
                contract_type=None,
                strategies=strategies,
                rng=rng,
                deal_id=i
            )
            
            if leader == -1:
                continue
            
            winning_team = 0 if leader in (0, 2) else 1
            tricks_won = t0 if winning_team == 0 else t1
            made_bid = tricks_won >= bid
            
            # Only track when our strategy wins the bid (Team 0)
            if winning_team == 0:
                stats[strat_name]['total_hands'] += 1
                stats[strat_name]['bid_attempts'] += 1
                stats[strat_name]['bid_amounts'].append(bid)
                
                if made_bid:
                    stats[strat_name]['bid_successes'] += 1
                    stats[strat_name]['points_when_success'].append(bid)
                    stats[strat_name]['total_points'] += bid
                else:
                    stats[strat_name]['points_when_failure'].append(-bid)
                    stats[strat_name]['total_points'] -= bid
            else:
                # Opponent won the bid
                stats[strat_name]['total_hands'] += 1
                # If opponent makes bid, we don't score
                # If opponent fails, we don't score either (they lose points)
    
    return stats, strategy_names

def create_dashboard(stats: Dict, strategy_names: List[str], output_dir: str):
    """Create comprehensive comparison dashboard."""
    print("\n" + "="*80)
    print("GENERATING STRATEGY COMPARISON DASHBOARD")
    print("="*80)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Calculate metrics
    make_rates = []
    avg_points_when_success = []
    avg_points_per_hand = []
    avg_bid_amounts = []
    total_bids = []
    
    for name in strategy_names:
        s = stats[name]
        
        # Make rate
        make_rate = (s['bid_successes'] / s['bid_attempts'] * 100) if s['bid_attempts'] > 0 else 0
        make_rates.append(make_rate)
        
        # Avg points when successful
        avg_success = np.mean(s['points_when_success']) if len(s['points_when_success']) > 0 else 0
        avg_points_when_success.append(avg_success)
        
        # Avg points per hand
        avg_per_hand = s['total_points'] / s['total_hands'] if s['total_hands'] > 0 else 0
        avg_points_per_hand.append(avg_per_hand)
        
        # Avg bid amount
        avg_bid = np.mean(s['bid_amounts']) if len(s['bid_amounts']) > 0 else 0
        avg_bid_amounts.append(avg_bid)
        
        # Total bids
        total_bids.append(s['bid_attempts'])
    
    # Create figure with 2x3 layout
    fig = plt.figure(figsize=(18, 12))
    
    # Color scheme
    colors = plt.cm.Set3(np.linspace(0, 1, len(strategy_names)))
    
    # 1. Make Rate
    ax1 = plt.subplot(2, 3, 1)
    bars1 = ax1.bar(range(len(strategy_names)), make_rates, color=colors, edgecolor='black', linewidth=1.5)
    ax1.set_xticks(range(len(strategy_names)))
    ax1.set_xticklabels(strategy_names, rotation=45, ha='right')
    ax1.set_ylabel('Make Rate (%)', fontsize=12, fontweight='bold')
    ax1.set_title('Bid Make Rate by Strategy', fontsize=13, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim(0, 100)
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars1, make_rates)):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{val:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    # 2. Average Points When Making Bid
    ax2 = plt.subplot(2, 3, 2)
    bars2 = ax2.bar(range(len(strategy_names)), avg_points_when_success, color=colors, edgecolor='black', linewidth=1.5)
    ax2.set_xticks(range(len(strategy_names)))
    ax2.set_xticklabels(strategy_names, rotation=45, ha='right')
    ax2.set_ylabel('Points Earned', fontsize=12, fontweight='bold')
    ax2.set_title('Average Points When Making Bid', fontsize=13, fontweight='bold', pad=10)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars2, avg_points_when_success)):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    # 3. Average Points Per Hand
    ax3 = plt.subplot(2, 3, 3)
    bars3 = ax3.bar(range(len(strategy_names)), avg_points_per_hand, color=colors, edgecolor='black', linewidth=1.5)
    ax3.set_xticks(range(len(strategy_names)))
    ax3.set_xticklabels(strategy_names, rotation=45, ha='right')
    ax3.set_ylabel('Points Per Hand', fontsize=12, fontweight='bold')
    ax3.set_title('Average Points Per Hand\n(Including Hands Not Bidding)', fontsize=13, fontweight='bold', pad=10)
    ax3.grid(True, alpha=0.3, axis='y')
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    
    # Add value labels with color coding
    for i, (bar, val) in enumerate(zip(bars3, avg_points_per_hand)):
        color = 'green' if val > 0 else 'red'
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.02 if val > 0 else -0.05),
                f'{val:+.3f}', ha='center', va='bottom' if val > 0 else 'top', 
                fontweight='bold', fontsize=10, color=color)
    
    # 4. Average Bid Amount
    ax4 = plt.subplot(2, 3, 4)
    bars4 = ax4.bar(range(len(strategy_names)), avg_bid_amounts, color=colors, edgecolor='black', linewidth=1.5)
    ax4.set_xticks(range(len(strategy_names)))
    ax4.set_xticklabels(strategy_names, rotation=45, ha='right')
    ax4.set_ylabel('Average Bid', fontsize=12, fontweight='bold')
    ax4.set_title('Average Bid Amount', fontsize=13, fontweight='bold', pad=10)
    ax4.grid(True, alpha=0.3, axis='y')
    ax4.set_ylim(5, 8)
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars4, avg_bid_amounts)):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'{val:.2f}', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    # 5. Total Bids Won
    ax5 = plt.subplot(2, 3, 5)
    bars5 = ax5.bar(range(len(strategy_names)), total_bids, color=colors, edgecolor='black', linewidth=1.5)
    ax5.set_xticks(range(len(strategy_names)))
    ax5.set_xticklabels(strategy_names, rotation=45, ha='right')
    ax5.set_ylabel('Number of Bids', fontsize=12, fontweight='bold')
    ax5.set_title('Total Bids Won\n(Out of ~20,000 hands)', fontsize=13, fontweight='bold', pad=10)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars5, total_bids)):
        ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
                f'{val:,}', ha='center', va='bottom', fontweight='bold', fontsize=10)
    
    # 6. Risk-Reward Scatter
    ax6 = plt.subplot(2, 3, 6)
    
    # Size by total bids
    sizes = [b/50 for b in total_bids]  # Scale for visibility
    
    scatter = ax6.scatter(make_rates, avg_points_per_hand, s=sizes, c=colors, 
                          edgecolor='black', linewidth=2, alpha=0.7, zorder=3)
    
    # Add labels
    for i, name in enumerate(strategy_names):
        ax6.annotate(name, (make_rates[i], avg_points_per_hand[i]),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=9, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='gray'))
    
    ax6.set_xlabel('Make Rate (%)', fontsize=12, fontweight='bold')
    ax6.set_ylabel('Avg Points Per Hand', fontsize=12, fontweight='bold')
    ax6.set_title('Risk-Reward Trade-off\n(Size = Total Bids)', fontsize=13, fontweight='bold', pad=10)
    ax6.grid(True, alpha=0.3)
    ax6.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.7, label='Break-even')
    ax6.legend(fontsize=10)
    
    plt.suptitle('Strategy Comparison Dashboard\nPoints-Based Scoring Analysis', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    output_path = os.path.join(output_dir, "strategy_comparison_dashboard.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✅ Saved dashboard to: {output_path}")
    plt.close()
    
    # Print detailed table
    print("\n" + "="*80)
    print("DETAILED STRATEGY COMPARISON TABLE")
    print("="*80)
    print(f"{'Strategy':<15} | {'Make Rate':<10} | {'Pts/Success':<12} | {'Pts/Hand':<10} | {'Avg Bid':<8} | {'Total Bids':<10}")
    print("-" * 95)
    
    for i, name in enumerate(strategy_names):
        print(f"{name:<15} | {make_rates[i]:>9.2f}% | {avg_points_when_success[i]:>11.3f} | "
              f"{avg_points_per_hand[i]:>+9.3f} | {avg_bid_amounts[i]:>7.2f} | {total_bids[i]:>10,}")
    
    print("="*80)

if __name__ == "__main__":
    stats, strategy_names = run_comprehensive_analysis(n_hands_per_matchup=20000, seed=42)
    create_dashboard(stats, strategy_names, output_dir="data/reports")
    print("\n✅ Strategy comparison dashboard complete!")
