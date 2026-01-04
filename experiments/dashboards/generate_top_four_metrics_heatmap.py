#!/usr/bin/env python3
"""
Top 4 Strategy Metrics Heatmap

Creates a 4-panel heatmap showing:
1. Points per hand (by matchup)
2. Expected value when bidding
3. Standard deviation (volatility)
4. Risk-adjusted return (4 * pts/hand / std)

Usage:
    PYTHONPATH=src python experiments/generate_top_four_metrics_heatmap.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List

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

def run_metrics_analysis(n_hands: int = 10000, seed: int = 42):
    """Run analysis to collect all metrics."""
    print(f"Collecting metrics for Top 4 strategies ({n_hands:,} hands per matchup)")
    print("-" * 80)
    
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
                'team0_points': 0,
                'team0_bid_attempts': 0,
                'team0_points_per_hand': [],
                'valid_hands': 0
            }
    
    # Run all matchups
    import random
    
    for strat_a_name in strategy_names:
        for strat_b_name in strategy_names:
            print(f"  {strat_a_name} vs {strat_b_name}")
            
            strat_a = strategies_dict[strat_a_name]
            strat_b = strategies_dict[strat_b_name]
            
            strategies = [strat_a, strat_b, strat_a, strat_b]
            rng = random.Random(seed)
            
            for i in range(n_hands):
                t0, t1, _, _, leader, _, bid, _, _, _, _, _, _ = play_single_hand(
                    contract_type=None,
                    strategies=strategies,
                    rng=rng,
                    deal_id=i
                )
                
                if leader == -1:
                    continue
                
                r = results[strat_a_name][strat_b_name]
                r['valid_hands'] += 1
                
                winning_team = 0 if leader in (0, 2) else 1
                tricks_won = t0 if winning_team == 0 else t1
                made_bid = tricks_won >= bid
                
                team0_hand_points = 0
                
                if made_bid:
                    if winning_team == 0:
                        r['team0_points'] += bid
                        team0_hand_points = bid
                    else:
                        pass  # Opponent scored
                else:
                    if winning_team == 0:
                        r['team0_points'] -= bid
                        team0_hand_points = -bid
                    else:
                        pass  # Opponent failed
                
                r['team0_points_per_hand'].append(team0_hand_points)
                
                if winning_team == 0:
                    r['team0_bid_attempts'] += 1
    
    return results, strategy_names

def create_metrics_heatmap(results: Dict, strategy_names: List[str], output_dir: str):
    """Create 4-panel heatmap of key metrics."""
    print("\n" + "="*80)
    print("GENERATING METRICS HEATMAP")
    print("="*80)
    
    os.makedirs(output_dir, exist_ok=True)
    
    n = len(strategy_names)
    
    # Calculate matrices
    # 1. Points per hand matrix
    pts_per_hand_matrix = np.zeros((n, n))
    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            valid = r['valid_hands']
            pts_per_hand_matrix[i, j] = (r['team0_points'] / valid) if valid > 0 else 0
    
    # 2. Expected Value matrix (average across all matchups)
    ev_matrix = np.zeros((n, n))
    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            attempts = r['team0_bid_attempts']
            points = r['team0_points']
            ev_matrix[i, j] = (points / attempts) if attempts > 0 else 0
    
    # 3. Volatility matrix (std dev of points per hand)
    volatility_matrix = np.zeros((n, n))
    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            if len(r['team0_points_per_hand']) > 0:
                volatility_matrix[i, j] = np.std(r['team0_points_per_hand'])
            else:
                volatility_matrix[i, j] = 0
    
    # 4. Risk-adjusted return matrix (4 * pts_per_hand / volatility)
    risk_adj_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if volatility_matrix[i, j] > 0:
                risk_adj_matrix[i, j] = (4 * pts_per_hand_matrix[i, j]) / volatility_matrix[i, j]
            else:
                risk_adj_matrix[i, j] = 0
    
    # Create figure
    fig, axes = plt.subplots(2, 2, figsize=(18, 16))
    fig.suptitle("Top 4 Strategy Metrics Heatmaps\nHead-to-Head Performance", 
                 fontsize=18, fontweight='bold', y=0.995)
    axes = axes.flatten()
    
    # Helper function
    def create_heatmap(ax, data, title, cmap, vmin, vmax, cbar_label, fmt='.3f'):
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)
        
        cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(cbar_label, fontsize=11, fontweight='bold')
        
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(strategy_names, rotation=45, ha='right', fontsize=11)
        ax.set_yticklabels(strategy_names, fontsize=11)
        
        # Add text annotations
        for i in range(n):
            for j in range(n):
                text_color = 'white' if (data[i, j] < (vmin + (vmax - vmin) * 0.5)) else 'black'
                
                if fmt == '.3f':
                    text_val = f'{data[i, j]:.3f}'
                elif fmt == '.2f':
                    text_val = f'{data[i, j]:.2f}'
                elif fmt == '.1f':
                    text_val = f'{data[i, j]:.1f}'
                else:
                    text_val = f'{data[i, j]:{fmt}}'
                
                ax.text(j, i, text_val, ha="center", va="center", 
                       color=text_color, fontsize=10, fontweight='bold')
        
        ax.set_title(title, fontsize=13, fontweight='bold', pad=15)
        ax.set_xlabel("Opponent Strategy", fontsize=12, fontweight='bold')
        ax.set_ylabel("Strategy", fontsize=12, fontweight='bold')
    
    # 1. Points Per Hand
    create_heatmap(axes[0], pts_per_hand_matrix, 
                   "Points Per Hand\n(Row strategy vs Column opponent)",
                   'RdYlGn', -0.5, 1.5, 'Pts/Hand', fmt='.3f')
    
    # 2. Expected Value When Bidding
    create_heatmap(axes[1], ev_matrix,
                   "Expected Value When Bidding\n(Avg points per bid attempt)",
                   'RdYlGn', 0, 4, 'EV', fmt='.2f')
    
    # 3. Volatility (Std Dev)
    create_heatmap(axes[2], volatility_matrix,
                   "Volatility (Std Dev)\n(Points per hand variability)",
                   'YlOrRd', 2, 7, 'Std Dev', fmt='.2f')
    
    # 4. Risk-Adjusted Return
    create_heatmap(axes[3], risk_adj_matrix,
                   "Risk-Adjusted Return\n(4 × Pts/Hand ÷ Std Dev) - HIGHER IS BETTER",
                   'RdYlGn', 0, 2, 'Risk-Adj Return', fmt='.3f')
    
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    output_path = os.path.join(output_dir, "top_four_metrics_heatmap.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved heatmap to: {output_path}")
    
    # Print summary tables
    print("\n" + "="*80)
    print("1. POINTS PER HAND MATRIX")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>14}" for s in strategy_names]))
    print("-" * 90)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{pts_per_hand_matrix[i,j]:>14.3f}" for j in range(n)])
        print(row_str)
    
    print("\n" + "="*80)
    print("2. EXPECTED VALUE WHEN BIDDING MATRIX")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>14}" for s in strategy_names]))
    print("-" * 90)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{ev_matrix[i,j]:>14.2f}" for j in range(n)])
        print(row_str)
    
    print("\n" + "="*80)
    print("3. VOLATILITY (STD DEV) MATRIX")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>14}" for s in strategy_names]))
    print("-" * 90)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{volatility_matrix[i,j]:>14.2f}" for j in range(n)])
        print(row_str)
    
    print("\n" + "="*80)
    print("4. RISK-ADJUSTED RETURN MATRIX (4 × Pts/Hand ÷ Std Dev)")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>14}" for s in strategy_names]))
    print("-" * 90)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{risk_adj_matrix[i,j]:>14.3f}" for j in range(n)])
        print(row_str)
    
    # Find best strategy by risk-adjusted return
    print("\n" + "="*80)
    print("🏆 BEST BY RISK-ADJUSTED RETURN")
    print("="*80)
    
    avg_risk_adj = [np.mean(risk_adj_matrix[i, :]) for i in range(n)]
    best_idx = np.argmax(avg_risk_adj)
    
    print(f"\n★★★ WINNER: {strategy_names[best_idx]} ★★★")
    print(f"Average Risk-Adjusted Return: {avg_risk_adj[best_idx]:.3f}")
    print("\nFull Rankings:")
    for idx in np.argsort(avg_risk_adj)[::-1]:
        print(f"  {strategy_names[idx]:<15}: {avg_risk_adj[idx]:.3f}")
    
    print("="*80)

if __name__ == "__main__":
    results, strategy_names = run_metrics_analysis(n_hands=10000, seed=42)
    create_metrics_heatmap(results, strategy_names, output_dir="data/reports")
    print("\n✅ Metrics heatmap analysis complete!")
