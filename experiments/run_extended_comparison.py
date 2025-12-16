#!/usr/bin/env python3
"""
Run extended strategy comparison including ImprovedGreedyStrategy.

Usage:
    PYTHONPATH=src python experiments/run_extended_comparison.py --n_per 50000 --seed 42
"""

import json
import os
import argparse
from datetime import datetime

from bid_euchre.sim import simulation
from bid_euchre.logging import GameLogger, LogLevel
from bid_euchre.strategy import (
    GreedyStrategy,
    ImprovedGreedyStrategy,
    RandomLegalStrategy,
    AlwaysLowestLegalStrategy,
    AlwaysHighestLegalStrategy,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run extended strategy comparison")
    parser.add_argument("--n_per", "-n", type=int, default=50000)
    parser.add_argument("--seed", "-s", type=int, default=42)
    parser.add_argument("--log-level", choices=["none", "hand", "trick"], default="hand")
    parser.add_argument("--run-dir", type=str, default="data/runs")
    return parser.parse_args()


def scenario_filename(contract_type: str, trump_suit: str | None) -> str:
    if contract_type == "suit":
        return f"suit_{trump_suit}.json"
    return f"{contract_type}.json"


def save_results(results: dict, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    return out_path


def main():
    args = parse_args()

    # Define all strategies including improved_greedy
    strategies = [
        GreedyStrategy(name="greedy"),
        ImprovedGreedyStrategy(name="improved_greedy"),
        RandomLegalStrategy(name="random_legal", seed=args.seed),
        AlwaysLowestLegalStrategy(name="always_lowest"),
        AlwaysHighestLegalStrategy(name="always_highest"),
    ]

    scenarios = [
        ("suit", "C"),
        ("suit", "D"),
        ("suit", "H"),
        ("suit", "S"),
        ("high", None),
        ("low", None),
    ]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"extended_comparison_{args.seed}_{timestamp}"
    run_dir = os.path.join(args.run_dir, run_id)
    results_dir = os.path.join(run_dir, "results")
    logs_dir = os.path.join(run_dir, "logs")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    print("🚀 Extended Strategy Comparison (including ImprovedGreedy)")
    print("=" * 70)
    print(f"Strategies: {', '.join(s.name for s in strategies)}")
    print(f"Hands per scenario: {args.n_per:,}")
    print(f"Random seed: {args.seed}")
    print(f"Total hands: {len(scenarios) * args.n_per * len(strategies):,}")
    print("=" * 70)

    meta = {
        "run_id": run_id,
        "experiment_name": "extended_comparison",
        "seed": args.seed,
        "n_per": args.n_per,
        "log_level": args.log_level,
        "timestamp": timestamp,
        "scenarios": [{"contract_type": c, "trump_suit": t} for (c, t) in scenarios],
        "strategies": [s.name for s in strategies],
        "leader_randomized": True,
        "common_deals": True,
    }
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    for strat in strategies:
        print("\n" + "-" * 70)
        print(f"Strategy: {strat.name}")
        print("-" * 70)

        logger = None
        if args.log_level != "none":
            log_level = LogLevel(args.log_level)
            logger = GameLogger(
                run_id=f"{run_id}_{strat.name}",
                strategy_id=strat.name,
                level=log_level,
                output_dir=logs_dir,
            )
            logger.open()

        try:
            for i, (contract_type, trump_suit) in enumerate(scenarios, 1):
                scenario_seed = args.seed + (i - 1)
                label = f"{contract_type}"
                if trump_suit:
                    label += f" ({trump_suit})"

                print(f"[{i}/{len(scenarios)}] {label} - {args.n_per:,} hands (seed={scenario_seed})")

                results = simulation.simulate_many_hands(
                    n=args.n_per,
                    contract_type=contract_type,
                    trump_suit=trump_suit,
                    seed=None,
                    deal_seed=scenario_seed,
                    strategy=strat,
                    logger=logger,
                )

                out_path = os.path.join(
                    results_dir, strat.name, scenario_filename(contract_type, trump_suit)
                )
                save_results(results, out_path)

                team0_avg = results["avg_team0"]
                team1_avg = results["avg_team1"]
                win_hands = sum(
                    count
                    for tricks, count in results["distribution_team0"].items()
                    if int(tricks) >= 6
                )
                win_rate = win_hands / results["hands"] * 100
                print(f"  Team0: {team0_avg:.1f}  Team1: {team1_avg:.1f}  Win: {win_rate:.1f}%")

        finally:
            if logger:
                logger.close()

    print("\n" + "=" * 70)
    print("✅ Extended comparison completed!")
    print(f"📁 Run: {run_dir}")
    print(f"\n🎯 Generate comparison report:")
    print(f"   PYTHONPATH=src python experiments/generate_strategy_comparison.py --run-dir {run_dir} --seed {args.seed}")


if __name__ == "__main__":
    main()

