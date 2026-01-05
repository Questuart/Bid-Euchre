#!/usr/bin/env python3
"""
"Three-Horse Race": Bidding Comparison Experiment.

Pits three bidding personalities against each other:
1. FiveHeadFred: Always bids 5 on its best contract.
2. OLSa SR: Bids rounded OLS prediction based on Hand Value (1 feature).
3. OLSa: Bids rounded OLS prediction based on Baseline OLS (4 features).

Usage:
    PYTHONPATH=src python experiments/run_bidding_comparison.py
"""


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

def run_comparison(n_hands: int = 10000, seed: int = 42):
    print(f"Starting Three-Horse Race ({n_hands:,} hands, seed={seed})")
    print("-" * 60)

    # 1. Define Personalities
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

    matchups = [
        ("OLSa vs FiveHeadFred", [olsa, fred, olsa, fred]),
        ("OLSa vs OLSa_SR", [olsa, olsa_sr, olsa, olsa_sr]),
        ("OLSa_SR vs FiveHeadFred", [olsa_sr, fred, olsa_sr, fred]),
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
            t0, t1, _, _, leader, _, bid, _, _, _, _, _, _ = play_single_hand(
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
        print(f"  Team 0 Win Rate: {win_rate0:.1%}")
        print(f"  Team 1 Win Rate: {win_rate1:.1%}")
        print(f"  Team 0 Bid Make Rate: {make_rate0:.1%}")
        print(f"  Team 1 Bid Make Rate: {make_rate1:.1%}")
        print(f"  Team 0 Avg Bid: {avg_bid0:.2f}")
        print(f"  Team 1 Avg Bid: {avg_bid1:.2f}")

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
    print("FINAL SUMMARY - THREE-HORSE RACE")
    print("=" * 80)
    print(f"{'Matchup':<30} | {'Team 0 Win':<12} | {'Team 1 Win':<12} | {'Misdeals':<10}")
    print("-" * 80)
    for res in overall_results:
        print(f"{res['matchup']:<30} | {res['team0_win_rate']:>11.1%} | {res['team1_win_rate']:>11.1%} | {res['misdeals']:<10}")
    print("=" * 80)

if __name__ == "__main__":
    run_comparison(n_hands=10000)
