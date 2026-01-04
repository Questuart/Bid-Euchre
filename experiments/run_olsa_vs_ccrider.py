#!/usr/bin/env python3
"""
OLSa vs OLSa_CCrider Head-to-Head Comparison

Tests the CCrider policy:
- Ceiling for suit contracts when prediction > 7
- Round for all other contracts (high/low and suit <= 7)

Usage:
    PYTHONPATH=src python experiments/run_olsa_vs_ccrider.py
"""

import os
import numpy as np
from typing import Dict

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.regression import RegressionBidder

# Model Paths
BASELINE_MODELS = {
    'suit': 'data/models/baseline_regression/baseline_regression_suit.pkl',
    'high': 'data/models/baseline_regression/baseline_regression_high.pkl',
    'low': 'data/models/baseline_regression/baseline_regression_low.pkl'
}

def run_comparison(n_hands: int = 10000, seed: int = 42):
    """Run OLSa vs OLSa_CCrider comparison."""
    print(f"Starting OLSa vs OLSa_CCrider Comparison ({n_hands:,} hands, seed={seed})")
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
    
    # Storage
    results = {
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
    
    # Track by contract type
    contract_stats = {
        'suit': {'team0_wins': 0, 'team1_wins': 0, 'team0_bids': 0, 'team1_bids': 0},
        'high': {'team0_wins': 0, 'team1_wins': 0, 'team0_bids': 0, 'team1_bids': 0},
        'low': {'team0_wins': 0, 'team1_wins': 0, 'team0_bids': 0, 'team1_bids': 0}
    }
    
    # For reproducibility
    import random
    rng = random.Random(seed)
    
    for i in range(n_hands):
        if i % 5000 == 0 and i > 0:
            print(f"  Progress: {i:,}/{n_hands:,} hands")
        
        t0, t1, _, _, leader, starting_hands, bid, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            rng=rng,
            deal_id=i
        )
        
        if leader == -1:
            results['misdeals'] += 1
            continue
        
        results['valid_hands'] += 1
        
        # Track bidding
        winning_team = 0 if leader in (0, 2) else 1
        tricks_won = t0 if winning_team == 0 else t1
        
        # Track who won the HAND (based on making the bid)
        made_bid = tricks_won >= bid
        if made_bid:
            # Bidding team wins and scores +bid points
            if winning_team == 0:
                results['team0_wins'] += 1
                results['team0_points'] += bid
            else:
                results['team1_wins'] += 1
                results['team1_points'] += bid
        else:
            # Defending team wins, bidding team loses -bid points
            if winning_team == 0:
                results['team1_wins'] += 1
                results['team0_points'] -= bid
            else:
                results['team0_wins'] += 1
                results['team1_points'] -= bid
        
        # Get contract type
        bid_amount, contract_type, trump_suit = strategies[leader].decide_bid(
            hand=starting_hands[leader],
            current_high_bid=0,
            current_winner_index=None,
            partner_index=(leader + 2) % 4,
            player_index=leader
        )
        
        # Track by contract
        if winning_team == 0:
            contract_stats[contract_type]['team0_bids'] += 1
            if t0 > t1:
                contract_stats[contract_type]['team0_wins'] += 1
        else:
            contract_stats[contract_type]['team1_bids'] += 1
            if t1 > t0:
                contract_stats[contract_type]['team1_wins'] += 1
        
        if winning_team == 0:
            results['team0_bid_attempts'] += 1
            results['team0_bid_total'] += bid
            if tricks_won >= bid:
                results['team0_bid_successes'] += 1
        else:
            results['team1_bid_attempts'] += 1
            results['team1_bid_total'] += bid
            if tricks_won >= bid:
                results['team1_bid_successes'] += 1
    
    # Calculate statistics
    valid = results['valid_hands']
    
    win_rate_0 = results['team0_wins'] / valid * 100
    win_rate_1 = results['team1_wins'] / valid * 100
    
    make_rate_0 = results['team0_bid_successes'] / max(1, results['team0_bid_attempts']) * 100
    make_rate_1 = results['team1_bid_successes'] / max(1, results['team1_bid_attempts']) * 100
    
    avg_bid_0 = results['team0_bid_total'] / max(1, results['team0_bid_attempts'])
    avg_bid_1 = results['team1_bid_total'] / max(1, results['team1_bid_attempts'])
    
    avg_points_per_hand_0 = results['team0_points'] / valid
    avg_points_per_hand_1 = results['team1_points'] / valid
    
    ev_when_bidding_0 = results['team0_points'] / max(1, results['team0_bid_attempts'])
    ev_when_bidding_1 = results['team1_points'] / max(1, results['team1_bid_attempts'])
    
    point_diff = results['team0_points'] - results['team1_points']
    
    # Print results
    print("\n" + "="*80)
    print("OVERALL RESULTS (Points-Based Scoring)")
    print("="*80)
    print(f"Valid hands: {valid:,} (Misdeals: {results['misdeals']})")
    print()
    print(f"OLSa (Team 0):")
    print(f"  Win Rate:           {win_rate_0:.2f}%")
    print(f"  Total Points:       {results['team0_points']:+,}")
    print(f"  Avg Points/Hand:    {avg_points_per_hand_0:+.3f}")
    print(f"  EV When Bidding:    {ev_when_bidding_0:+.3f}")
    print(f"  Make Rate:          {make_rate_0:.2f}%")
    print(f"  Avg Bid:            {avg_bid_0:.2f}")
    print(f"  Bids Won:           {results['team0_bid_attempts']:,}")
    print()
    print(f"OLSa_CCrider (Team 1):")
    print(f"  Win Rate:           {win_rate_1:.2f}%")
    print(f"  Total Points:       {results['team1_points']:+,}")
    print(f"  Avg Points/Hand:    {avg_points_per_hand_1:+.3f}")
    print(f"  EV When Bidding:    {ev_when_bidding_1:+.3f}")
    print(f"  Make Rate:          {make_rate_1:.2f}%")
    print(f"  Avg Bid:            {avg_bid_1:.2f}")
    print(f"  Bids Won:           {results['team1_bid_attempts']:,}")
    print()
    print(f"Point Differential: {point_diff:+,} ({'OLSa' if point_diff > 0 else 'CCrider'} ahead)")
    
    # Print by contract type
    print("\n" + "="*80)
    print("RESULTS BY CONTRACT TYPE")
    print("="*80)
    
    for ctype in ['suit', 'high', 'low']:
        cs = contract_stats[ctype]
        total_bids = cs['team0_bids'] + cs['team1_bids']
        if total_bids == 0:
            continue
        
        team0_pct = cs['team0_bids'] / total_bids * 100 if total_bids > 0 else 0
        team1_pct = cs['team1_bids'] / total_bids * 100 if total_bids > 0 else 0
        
        team0_win_rate = cs['team0_wins'] / cs['team0_bids'] * 100 if cs['team0_bids'] > 0 else 0
        team1_win_rate = cs['team1_wins'] / cs['team1_bids'] * 100 if cs['team1_bids'] > 0 else 0
        
        print(f"\n{ctype.upper()}:")
        print(f"  Total hands: {total_bids:,}")
        print(f"  OLSa won bid: {cs['team0_bids']:,} ({team0_pct:.1f}%) | Win rate: {team0_win_rate:.1f}%")
        print(f"  CCrider won bid: {cs['team1_bids']:,} ({team1_pct:.1f}%) | Win rate: {team1_win_rate:.1f}%")
    
    print("="*80)

if __name__ == "__main__":
    run_comparison(n_hands=20000, seed=42)
    print("\n✅ Comparison complete!")
