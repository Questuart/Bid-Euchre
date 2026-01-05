#!/usr/bin/env python3
"""
Analyze predicted tricks vs actual tricks for OLSa vs OLSa matchups.

Shows calibration of the regression model by contract type.

Usage:
    PYTHONPATH=src python experiments/analyze_predicted_vs_actual.py
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.regression import RegressionBidder
from bid_euchre.features.hand_eval import get_hand_features

# Model Paths
BASELINE_MODELS = {
    'suit': 'data/models/baseline_regression/baseline_regression_suit.pkl',
    'high': 'data/models/baseline_regression/baseline_regression_high.pkl',
    'low': 'data/models/baseline_regression/baseline_regression_low.pkl'
}

def collect_prediction_data(n_hands: int = 50000, seed: int = 42):
    """Run OLSa vs OLSa and collect predictions vs actual tricks."""
    print(f"Collecting prediction data (OLSa vs OLSa, {n_hands:,} hands)...")
    
    # Create OLSa strategies
    olsa = RegressionBidder(model_paths=BASELINE_MODELS, name="OLSa", policy="round")
    strategies = [olsa, olsa, olsa, olsa]
    
    # Storage by contract type
    data = {
        'suit_H': {'predicted': [], 'actual': []},
        'suit_S': {'predicted': [], 'actual': []},
        'suit_D': {'predicted': [], 'actual': []},
        'suit_C': {'predicted': [], 'actual': []},
        'high': {'predicted': [], 'actual': []},
        'low': {'predicted': [], 'actual': []}
    }
    
    import random
    rng = random.Random(seed)
    
    for i in range(n_hands):
        if i % 10000 == 0:
            print(f"  Progress: {i:,}/{n_hands:,} hands")
        
        t0, t1, _, _, leader, starting_hands, bid, _, _, _, _, _, _ = play_single_hand(
            contract_type=None,  # Trigger bidding
            strategies=strategies,
            rng=rng,
            deal_id=i
        )
        
        # Skip misdeals
        if leader == -1:
            continue
        
        # Get the winning bidder's hand and contract
        bidder_hand = starting_hands[leader]
        
        # We need to figure out what contract was chosen
        # Let's run decide_bid to get the contract info
        bid_amount, contract_type, trump_suit = strategies[leader].decide_bid(
            hand=bidder_hand,
            current_high_bid=0,
            current_winner_index=None,
            partner_index=(leader + 2) % 4,
            player_index=leader
        )
        
        # Get features and predict
        features = get_hand_features(bidder_hand, contract_type, trump_suit)
        model_data = olsa.models[contract_type]
        model = model_data['model']
        feature_names = model_data['features']
        
        X = np.array([features[fname] for fname in feature_names]).reshape(1, -1)
        predicted_tricks = model.predict(X)[0]
        
        # Actual tricks for the winning bidder's team
        actual_tricks = t0 if leader in (0, 2) else t1
        
        # Store data
        if contract_type == 'suit':
            key = f'suit_{trump_suit}'
        else:
            key = contract_type
        
        data[key]['predicted'].append(predicted_tricks)
        data[key]['actual'].append(actual_tricks)
    
    print("✅ Data collection complete!")
    return data

def create_predicted_vs_actual_plot(data: Dict, output_path: str):
    """Create scatter plot with binned means like the reference image."""
    print("\nGenerating predicted vs actual plot...")
    
    # Aggregate suit contracts
    suit_data = {
        'predicted': [],
        'actual': []
    }
    for key in ['suit_H', 'suit_S', 'suit_D', 'suit_C']:
        suit_data['predicted'].extend(data[key]['predicted'])
        suit_data['actual'].extend(data[key]['actual'])
    
    # Create figure with 3 subplots (suit, high, low)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("OLSa: Predicted vs Actual Tricks (OLSa vs OLSa matchup)", 
                 fontsize=16, fontweight='bold')
    
    plot_configs = [
        (suit_data, "SUIT contracts", axes[0]),
        (data['high'], "HIGH contracts", axes[1]),
        (data['low'], "LOW contracts", axes[2])
    ]
    
    for plot_data, title, ax in plot_configs:
        predicted = np.array(plot_data['predicted'])
        actual = np.array(plot_data['actual'])
        
        if len(predicted) == 0:
            continue
        
        # Scatter plot with alpha
        ax.scatter(predicted, actual, alpha=0.3, s=10, color='steelblue', edgecolors='none')
        
        # Calculate binned means
        bins = np.arange(0, 11, 0.5)  # Bins every 0.5 tricks
        bin_means_x = []
        bin_means_y = []
        
        for i in range(len(bins) - 1):
            mask = (predicted >= bins[i]) & (predicted < bins[i+1])
            if mask.sum() > 10:  # Need at least 10 points
                bin_means_x.append((bins[i] + bins[i+1]) / 2)
                bin_means_y.append(actual[mask].mean())
        
        # Plot binned means
        if len(bin_means_x) > 0:
            ax.plot(bin_means_x, bin_means_y, color='orange', linewidth=3, 
                   label='binned mean', zorder=10)
        
        # Perfect prediction line
        ax.plot([0, 10], [0, 10], 'k--', alpha=0.5, linewidth=1.5, zorder=5)
        
        # Formatting
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.set_xlabel("Predicted tricks", fontsize=12)
        ax.set_ylabel("Actual team tricks", fontsize=12)
        ax.set_title(f"{title} (n={len(predicted):,})", fontsize=13, fontweight='bold')
        ax.legend(loc='lower right', fontsize=10)
        
        # Add gridlines for all integer values
        ax.set_xticks(range(0, 11))
        ax.set_yticks(range(0, 11))
        ax.grid(True, alpha=0.3, linewidth=0.5)
        
        ax.set_aspect('equal')
    
    plt.tight_layout()
    
    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Saved plot to: {output_path}")
    
    # Print statistics
    print("\n" + "="*80)
    print("CALIBRATION STATISTICS")
    print("="*80)
    
    for plot_data, title, _ in plot_configs:
        predicted = np.array(plot_data['predicted'])
        actual = np.array(plot_data['actual'])
        
        if len(predicted) == 0:
            continue
        
        mae = np.mean(np.abs(predicted - actual))
        rmse = np.sqrt(np.mean((predicted - actual)**2))
        bias = np.mean(predicted - actual)
        
        print(f"\n{title}:")
        print(f"  N: {len(predicted):,}")
        print(f"  Mean predicted: {predicted.mean():.3f}")
        print(f"  Mean actual: {actual.mean():.3f}")
        print(f"  MAE: {mae:.3f}")
        print(f"  RMSE: {rmse:.3f}")
        print(f"  Bias: {bias:.3f} (positive = overprediction)")
    
    print("="*80)

if __name__ == "__main__":
    data = collect_prediction_data(n_hands=50000, seed=42)
    create_predicted_vs_actual_plot(data, output_path="data/reports/olsa_predicted_vs_actual.png")
    print("\n✅ Analysis complete!")
