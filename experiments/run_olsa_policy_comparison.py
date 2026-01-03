#!/usr/bin/env python3
"""
OLSa Policy Comparison: Ceil vs Floor vs Round

Tests the impact of bidding aggressiveness on win rates and make rates.

Usage:
    PYTHONPATH=src python experiments/run_olsa_policy_comparison.py
"""

import os
import json
import numpy as np
from typing import List, Dict, Any

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.regression import RegressionBidder
from bid_euchre.logging.game_logger import GameLogger, LogLevel

# Model Paths
BASELINE_MODELS = {
    'suit': 'data/models/baseline_regression/baseline_regression_suit.pkl',
    'high': 'data/models/baseline_regression/baseline_regression_high.pkl',
    'low': 'data/models/baseline_regression/baseline_regression_low.pkl'
}

def run_comparison(n_hands: int = 10000, seed: int = 42):
    print(f"Starting OLSa Policy Comparison ({n_hands:,} hands, seed={seed})")
    print("Testing: Ceil (Aggressive) vs Floor (Conservative) vs Round (Baseline)")
    print("-" * 80)

    # 1. Define Personalities with different policies
    olsa_floor = RegressionBidder(
        model_paths=BASELINE_MODELS, 
        name="OLSa_Floor", 
        policy="floor"
    )
    olsa_ceil = RegressionBidder(
        model_paths=BASELINE_MODELS, 
        name="OLSa_Ceil", 
        policy="ceil"
    )
    olsa_round = RegressionBidder(
        model_paths=BASELINE_MODELS, 
        name="OLSa_Round", 
        policy="round"
    )

    matchups = [
        ("OLSa_Ceil vs OLSa_Floor", [olsa_ceil, olsa_floor, olsa_ceil, olsa_floor]),
        ("OLSa_Round vs OLSa_Floor", [olsa_round, olsa_floor, olsa_round, olsa_floor]),
        ("OLSa_Ceil vs OLSa_Round", [olsa_ceil, olsa_round, olsa_ceil, olsa_round]),
    ]

    overall_results = []

    for label, strategies in matchups:
        print(f"\nMatchup: {label}")
        print("Team 0 (Seats 0, 2):", strategies[0].name)
        print("Team 1 (Seats 1, 3):", strategies[1].name)
        
        team0_wins = 0
        team1_wins = 0
        misdeals = 0
        
        team0_tricks_total = 0
        team1_tricks_total = 0
        
        # Track bid success
        bid_attempts = {0: 0, 1: 0}
        bid_successes = {0: 0, 1: 0}
        bid_totals = {0: 0, 1: 0}
        
        # For reproducibility
        import random
        rng = random.Random(seed)

        for i in range(n_hands):
            t0, t1, _, _, leader, _, bid = play_single_hand(
                contract_type=None, # Trigger bidding phase
                strategies=strategies,
                rng=rng,
                deal_id=i
            )
            
            if leader == -1:
                misdeals += 1
                continue
                
            team0_tricks_total += t0
            team1_tricks_total += t1
            
            # Winning bidder's team
            winning_team = 0 if leader in (0, 2) else 1
            bid_attempts[winning_team] += 1
            bid_totals[winning_team] += bid
            
            # Did they make the bid?
            tricks_won = t0 if winning_team == 0 else t1
            if tricks_won >= bid:
                bid_successes[winning_team] += 1
            
            # Who won the hand?
            if t0 > t1:
                team0_wins += 1
            elif t1 > t0:
                team1_wins += 1
            else:
                # Tie
                pass

        valid_hands = n_hands - misdeals
        win_rate0 = team0_wins / valid_hands if valid_hands > 0 else 0
        win_rate1 = team1_wins / valid_hands if valid_hands > 0 else 0
        
        make_rate0 = bid_successes[0] / bid_attempts[0] if bid_attempts[0] > 0 else 0
        make_rate1 = bid_successes[1] / bid_attempts[1] if bid_attempts[1] > 0 else 0
        
        avg_bid0 = bid_totals[0] / bid_attempts[0] if bid_attempts[0] > 0 else 0
        avg_bid1 = bid_totals[1] / bid_attempts[1] if bid_attempts[1] > 0 else 0

        print(f"  Valid Hands: {valid_hands:,} (Misdeals: {misdeals})")
        print(f"  Team 0 ({strategies[0].name}):")
        print(f"    Win Rate:      {win_rate0:.1%}")
        print(f"    Make Rate:     {make_rate0:.1%}")
        print(f"    Avg Bid:       {avg_bid0:.2f}")
        print(f"  Team 1 ({strategies[1].name}):")
        print(f"    Win Rate:      {win_rate1:.1%}")
        print(f"    Make Rate:     {make_rate1:.1%}")
        print(f"    Avg Bid:       {avg_bid1:.2f}")
        
        overall_results.append({
            "matchup": label,
            "team0_name": strategies[0].name,
            "team1_name": strategies[1].name,
            "team0_win_rate": win_rate0,
            "team1_win_rate": win_rate1,
            "team0_make_rate": make_rate0,
            "team1_make_rate": make_rate1,
            "team0_avg_bid": avg_bid0,
            "team1_avg_bid": avg_bid1,
            "misdeals": misdeals
        })

    # Final Summary Table
    print("\n" + "=" * 80)
    print("FINAL SUMMARY - OLSA POLICY COMPARISON")
    print("=" * 80)
    print(f"{'Matchup':<35} | {'Win Rate':<12} | {'Make Rate':<12} | {'Avg Bid':<8}")
    print("-" * 80)
    for res in overall_results:
        print(f"{res['team0_name']:<35} | {res['team0_win_rate']:>11.1%} | {res['team0_make_rate']:>11.1%} | {res['team0_avg_bid']:>7.2f}")
        print(f"{res['team1_name']:<35} | {res['team1_win_rate']:>11.1%} | {res['team1_make_rate']:>11.1%} | {res['team1_avg_bid']:>7.2f}")
        print("-" * 80)
    print("=" * 80)

if __name__ == "__main__":
    run_comparison(n_hands=10000)
