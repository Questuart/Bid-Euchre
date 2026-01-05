#!/usr/bin/env python3
"""
Generate Training Data for Bidder-Aware Models.

This script generates hand-level data with full bidding to train models
that understand the bidder/defender dynamic. It follows the existing
experiment infrastructure pattern but focuses on bidding simulations.

Key features:
- Runs hands with bidding enabled (contract_type=None)
- Logs all player hands with positional data (schema v5)
- Compatible with existing split_train_val_test.py workflow
- Generates data suitable for training bidder/defender models

Usage:
    PYTHONPATH=src python experiments/generate_bidder_training_data.py \\
        --hands 30000 --seed 42

Output:
    data/runs/bidder_training_data_<seed>_<timestamp>/
    ├── meta.json
    ├── logs/
    │   └── bidder_training_data_<seed>_<timestamp>_olsa_sr_floor.jsonl
    └── (run split_train_val_test.py next to create train/val/test splits)
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.sim import simulation
from bid_euchre.strategy.regression import RegressionBidder
from bid_euchre.logging import GameLogger, LogLevel


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate training data for bidder-aware models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--hands", "-n",
        type=int,
        default=30000,
        help="Number of hands to simulate (default: 30000)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducible results (default: 42)"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default="data/runs",
        help="Base directory for run outputs (default: data/runs)"
    )
    return parser.parse_args()


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def main():
    args = parse_args()
    
    # Configuration
    experiment_name = "bidder_training_data"
    n_hands = args.hands
    seed = args.seed
    strategy_name = "olsa_sr_floor"
    
    # Print experiment summary
    print("\n" + "=" * 80)
    print("🚀 Generating Bidder Training Data")
    print("=" * 80)
    print(f"Strategy: {strategy_name} (Hand Value OLS, floor policy)")
    print("Mode: Self-play with full bidding")
    print(f"Hands: {n_hands:,}")
    print(f"Random seed: {seed}")
    print("Log level: hand (schema v5 with position data)")
    print("=" * 80)
    
    # Create run directory structure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{experiment_name}_{seed}_{timestamp}"
    run_dir = os.path.join(args.run_dir, run_id)
    logs_dir = os.path.join(run_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    print(f"\n📁 Run directory: {run_dir}\n")
    
    # Load strategy (Hand Value OLS with floor policy)
    print("Loading Hand Value OLS models...")
    hand_value_models = {
        'suit': 'data/models/hand_value_ols/hand_value_ols_suit.pkl',
        'high': 'data/models/hand_value_ols/hand_value_ols_high.pkl',
        'low': 'data/models/hand_value_ols/hand_value_ols_low.pkl'
    }
    
    strategy = RegressionBidder(
        model_paths=hand_value_models,
        name="OLSa_SR_Floor",
        policy="floor"
    )
    
    # All 4 players use same strategy (self-play)
    strategies = [strategy, strategy, strategy, strategy]
    
    # Setup logger
    logger = GameLogger(
        run_id=f"{run_id}_{strategy_name}",
        strategy_id=strategy_name,
        level=LogLevel.HAND,
        output_dir=logs_dir,
    )
    
    print(f"📝 Logging to: {logs_dir}/{logger.run_id}.jsonl")
    print(f"\n🎲 Running {n_hands:,} hands with full bidding...")
    print("-" * 80)
    
    # Run simulation with bidding
    start_time = time.time()
    
    logger.open()
    try:
        results = simulation.simulate_many_hands(
            n=n_hands,
            contract_type=None,  # Enable bidding phase
            trump_suit=None,
            seed=None,  # Use deal_seed instead
            deal_seed=seed,
            strategy=None,
            strategies=strategies,
            logger=logger,
        )
    finally:
        logger.close()
    
    duration = time.time() - start_time
    hands_per_sec = n_hands / duration if duration > 0 else 0
    
    # Print results summary
    print("-" * 80)
    print("\n✅ Simulation complete!")
    print(f"   Duration: {format_duration(duration)}")
    print(f"   Throughput: {hands_per_sec:.0f} hands/sec")
    print(f"   Total hands: {results['hands']:,}")
    
    # Write metadata
    meta = {
        "run_id": run_id,
        "experiment_name": experiment_name,
        "timestamp": timestamp,
        "seed": seed,
        "n_hands": n_hands,
        "strategy": strategy_name,
        "mode": "self_play",
        "log_level": "hand",
        "schema_version": 5,
        "purpose": "Training data generation for bidder-aware models",
        "total_hands": results["hands"],
        "duration_sec": round(duration, 2),
        "hands_per_sec": round(hands_per_sec, 1),
    }
    
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    
    print(f"\n📄 Metadata saved to: {run_dir}/meta.json")
    
    # Print next steps
    print("\n" + "=" * 80)
    print("🎯 Next Steps:")
    print("=" * 80)
    print("\n1. Split data into train/val/test:")
    print(f"   python experiments/split_train_val_test.py {run_dir}")
    print("\n2. Convert splits to CSV:")
    print(f"   PYTHONPATH=src python experiments/convert_splits_to_csv.py {run_dir}")
    print("\n3. Train bidder-aware models:")
    print("   PYTHONPATH=src python experiments/train_bidder_models.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
