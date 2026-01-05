#!/usr/bin/env python3
"""
Quick experiment runner to test positional tracking.

Usage:
    PYTHONPATH=src python experiments/run_position_test.py
"""

import os
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.regression import RegressionBidder
from bid_euchre.logging import GameLogger, LogLevel

def main():
    print("="*80)
    print("POSITION TRACKING TEST EXPERIMENT")
    print("="*80)

    # Configuration
    run_id = "position_test"
    n_hands = 5000
    seed = 42

    print("\nConfiguration:")
    print(f"  Hands: {n_hands:,}")
    print(f"  Seed: {seed}")
    print("  Strategy: OLSa vs OLSa (self-play)")
    print("  Logging: Schema v5 (with position data)")

    # Load models
    baseline_models = {
        'suit': 'data/models/baseline_regression/baseline_regression_suit.pkl',
        'high': 'data/models/baseline_regression/baseline_regression_high.pkl',
        'low': 'data/models/baseline_regression/baseline_regression_low.pkl'
    }

    # Create strategy (all 4 players use OLSa)
    olsa = RegressionBidder(model_paths=baseline_models, name="OLSa", policy="round")
    strategies = [olsa, olsa, olsa, olsa]

    # Setup logger
    os.makedirs("data/hand_logs", exist_ok=True)
    logger = GameLogger(
        run_id=run_id,
        strategy_id="olsa_self_play",
        level=LogLevel.HAND,
        output_dir="data/hand_logs"
    )

    print(f"\n📝 Logging to: data/hand_logs/{run_id}.jsonl")
    print("\nRunning simulation...")

    # Open logger (important!)
    logger.open()

    try:
        # Run simulation with bidding (contract_type=None)
        results = simulate_many_hands(
            n=n_hands,
            contract_type=None,  # Enable bidding
            trump_suit=None,
            seed=seed,
            strategies=strategies,
            logger=logger,
        )
    finally:
        # Close logger
        logger.close()

    print("\n✅ Simulation complete!")
    print(f"   Total hands: {results['hands']:,}")
    if 'team0_wins' in results:
        print(f"   Team 0 wins: {results['team0_wins']:,} ({results['team0_wins']/results['hands']*100:.1f}%)")
        print(f"   Team 1 wins: {results['team1_wins']:,} ({results['team1_wins']/results['hands']*100:.1f}%)")
    else:
        print("   (Team stats not tracked in bidding mode)")

    print("\n📊 Next step: Run analysis")
    print("   PYTHONPATH=src python experiments/analyze_position_impact.py")

    print("="*80)

if __name__ == "__main__":
    main()
