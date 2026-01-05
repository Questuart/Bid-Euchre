#!/usr/bin/env python3
"""
Full Head-to-Head Bidding Analysis

Runs all possible matchups including mirror matches and creates a heatmap
showing make-bid rates for each strategy vs each opponent.

Usage:
    PYTHONPATH=src python experiments/run_full_head_to_head.py
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

def run_full_head_to_head(n_hands: int = 10000, seed: int = 42):
    """Run all possible head-to-head matchups."""
    print(f"Starting Full Head-to-Head Analysis ({n_hands:,} hands per matchup)")
    print("-" * 80)

    # Define strategies
    strategies_dict = {
        "OLSa": RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa", policy="round"),
        "OLSa_SR": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="OLSa_SR", policy="round"),
        "FiveHeadFred": RegressionBidder(model_paths=HAND_VALUE_MODELS, name="FiveHeadFred", fixed_bid=5)
    }

    strategy_names = list(strategies_dict.keys())

    # Storage for results
    # results[strategy_a][strategy_b] = {wins, bids_attempted, bids_made, avg_bid, ...}
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
                'team0_bid_total': 0,
                'team1_bid_total': 0,
                'misdeals': 0,
                'valid_hands': 0
            }

    # Run all matchups
    import random

    for strat_a_name in strategy_names:
        for strat_b_name in strategy_names:
            print(f"\nMatchup: {strat_a_name} vs {strat_b_name}")

            # Create fresh strategy instances for this matchup
            strat_a = strategies_dict[strat_a_name]
            strat_b = strategies_dict[strat_b_name]

            # Team 0 = seats 0&2 (strat_a)
            # Team 1 = seats 1&3 (strat_b)
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
                    results[strat_a_name][strat_b_name]['misdeals'] += 1
                    continue

                results[strat_a_name][strat_b_name]['valid_hands'] += 1

                # Track bidding
                winning_team = 0 if leader in (0, 2) else 1
                tricks_won = t0 if winning_team == 0 else t1
                made_bid = tricks_won >= bid

                # Track wins and points based on making the bid
                if made_bid:
                    # Bidding team wins and scores +bid points
                    if winning_team == 0:
                        results[strat_a_name][strat_b_name]['team0_wins'] += 1
                        results[strat_a_name][strat_b_name]['team0_points'] += bid
                    else:
                        results[strat_a_name][strat_b_name]['team1_wins'] += 1
                        results[strat_a_name][strat_b_name]['team1_points'] += bid
                else:
                    # Defending team wins, bidding team loses -bid points
                    if winning_team == 0:
                        results[strat_a_name][strat_b_name]['team1_wins'] += 1
                        results[strat_a_name][strat_b_name]['team0_points'] -= bid
                    else:
                        results[strat_a_name][strat_b_name]['team0_wins'] += 1
                        results[strat_a_name][strat_b_name]['team1_points'] -= bid

                # Track bid attempts
                if winning_team == 0:
                    results[strat_a_name][strat_b_name]['team0_bid_attempts'] += 1
                    results[strat_a_name][strat_b_name]['team0_bid_total'] += bid
                    if made_bid:
                        results[strat_a_name][strat_b_name]['team0_bid_successes'] += 1
                else:
                    results[strat_a_name][strat_b_name]['team1_bid_attempts'] += 1
                    results[strat_a_name][strat_b_name]['team1_bid_total'] += bid
                    if made_bid:
                        results[strat_a_name][strat_b_name]['team1_bid_successes'] += 1

            # Print summary
            r = results[strat_a_name][strat_b_name]
            valid = r['valid_hands']
            print(f"  Valid hands: {valid:,}")
            win_rate_0 = r['team0_wins'] / valid * 100
            win_rate_1 = r['team1_wins'] / valid * 100
            ev_0 = r['team0_points'] / max(1, r['team0_bid_attempts'])
            ev_1 = r['team1_points'] / max(1, r['team1_bid_attempts'])
            print(f"  {strat_a_name} (Team 0): {win_rate_0:.1f}% win rate, "
                  f"{r['team0_bid_successes']/max(1,r['team0_bid_attempts'])*100:.1f}% make rate, "
                  f"EV={ev_0:+.2f}")
            print(f"  {strat_b_name} (Team 1): {win_rate_1:.1f}% win rate, "
                  f"{r['team1_bid_successes']/max(1,r['team1_bid_attempts'])*100:.1f}% make rate, "
                  f"EV={ev_1:+.2f}")

    return results, strategy_names

def create_heatmaps(results: Dict, strategy_names: List[str], output_dir: str):
    """Create heatmaps showing various metrics."""
    print("\n" + "="*80)
    print("GENERATING HEATMAPS")
    print("="*80)

    os.makedirs(output_dir, exist_ok=True)

    # 1. Make-bid rate heatmap
    make_rate_matrix = np.zeros((len(strategy_names), len(strategy_names)))

    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            # Team 0 is strat_a, so we want their make rate
            attempts = r['team0_bid_attempts']
            successes = r['team0_bid_successes']
            make_rate_matrix[i, j] = (successes / attempts * 100) if attempts > 0 else 0

    # 2. Win rate heatmap (based on making bids)
    win_rate_matrix = np.zeros((len(strategy_names), len(strategy_names)))

    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            valid = r['valid_hands']
            win_rate_matrix[i, j] = (r['team0_wins'] / valid * 100) if valid > 0 else 0

    # 3. Expected Value when bidding heatmap
    ev_matrix = np.zeros((len(strategy_names), len(strategy_names)))

    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            attempts = r['team0_bid_attempts']
            points = r['team0_points']
            ev_matrix[i, j] = (points / attempts) if attempts > 0 else 0

    # 4. Average bid heatmap
    avg_bid_matrix = np.zeros((len(strategy_names), len(strategy_names)))

    for i, strat_a in enumerate(strategy_names):
        for j, strat_b in enumerate(strategy_names):
            r = results[strat_a][strat_b]
            attempts = r['team0_bid_attempts']
            total = r['team0_bid_total']
            avg_bid_matrix[i, j] = (total / attempts) if attempts > 0 else 0

    # Create combined figure
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle("Head-to-Head Performance Matrix (Points-Based Scoring)", fontsize=16, fontweight='bold')
    axes = axes.flatten()

    # Helper function to create heatmap
    def create_heatmap(ax, data, title, cmap, vmin, vmax, cbar_label):
        im = ax.imshow(data, cmap=cmap, aspect='auto', vmin=vmin, vmax=vmax)

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(cbar_label, fontsize=10)

        # Set ticks
        ax.set_xticks(np.arange(len(strategy_names)))
        ax.set_yticks(np.arange(len(strategy_names)))
        ax.set_xticklabels(strategy_names, fontsize=10)
        ax.set_yticklabels(strategy_names, fontsize=10)

        # Rotate x labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

        # Add text annotations
        for i in range(len(strategy_names)):
            for j in range(len(strategy_names)):
                text = ax.text(j, i, f'{data[i, j]:.1f}',
                             ha="center", va="center", color="black", fontsize=10, fontweight='bold')

        ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel("Opponent Strategy", fontsize=11)
        ax.set_ylabel("Strategy", fontsize=11)

    # Make-bid rate heatmap
    create_heatmap(axes[0], make_rate_matrix,
                   "Bid Make Rate (%)\n(Row strategy vs Column opponent)",
                   'RdYlGn', 0, 100, 'Make Rate (%)')

    # Win rate heatmap
    create_heatmap(axes[1], win_rate_matrix,
                   "Win Rate (%)\n(Row strategy vs Column opponent)",
                   'Blues', 0, 100, 'Win Rate (%)')

    # Expected Value heatmap
    create_heatmap(axes[2], ev_matrix,
                   "Expected Value When Bidding\n(Row strategy vs Column opponent)",
                   'RdYlGn', -2, 2, 'EV')

    # Average bid heatmap
    create_heatmap(axes[3], avg_bid_matrix,
                   "Average Bid Amount\n(Row strategy vs Column opponent)",
                   'Purples', 5, 8, 'Avg Bid')

    plt.tight_layout()

    output_path = os.path.join(output_dir, "head_to_head_heatmaps.png")
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved heatmaps to: {output_path}")

    # Print detailed make-rate matrix
    print("\n" + "="*80)
    print("MAKE-BID RATE MATRIX (%)")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>12}" for s in strategy_names]))
    print("-" * 80)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{make_rate_matrix[i,j]:>11.1f}%" for j in range(len(strategy_names))])
        print(row_str)
    print("="*80)

    # Print win rate matrix
    print("\n" + "="*80)
    print("WIN RATE MATRIX (%)")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>12}" for s in strategy_names]))
    print("-" * 80)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{win_rate_matrix[i,j]:>11.1f}%" for j in range(len(strategy_names))])
        print(row_str)
    print("="*80)

    # Print EV matrix
    print("\n" + "="*80)
    print("EXPECTED VALUE (EV) WHEN BIDDING MATRIX")
    print("="*80)
    print(f"{'Strategy':<15} | " + " | ".join([f"{s:>12}" for s in strategy_names]))
    print("-" * 80)
    for i, strat_a in enumerate(strategy_names):
        row_str = f"{strat_a:<15} | "
        row_str += " | ".join([f"{ev_matrix[i,j]:>12.2f}" for j in range(len(strategy_names))])
        print(row_str)
    print("="*80)

if __name__ == "__main__":
    results, strategy_names = run_full_head_to_head(n_hands=10000, seed=42)
    create_heatmaps(results, strategy_names, output_dir="data/reports")
    print("\n✅ Full head-to-head analysis complete!")
