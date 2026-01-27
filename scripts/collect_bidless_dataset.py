#!/usr/bin/env python
"""
Collect a bidless dataset (JSONL) for training.

Runs simulations from a suite YAML and collects hand-level data without bidding
decisions into a deterministic JSONL output file.

Usage:
    PYTHONPATH=src python scripts/collect_bidless_dataset.py \\
        --suite experiments/suites/bidless_dataset_tiny.yaml \\
        --seed 42 \\
        --out /tmp/bidless_dataset.jsonl
"""

import argparse
import json
import os
import random
from typing import Any, Dict, List

import yaml

from bid_euchre.datasets.bidless import BidlessDatasetCollector
from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.baselines import RandomLegalStrategy


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Collect bidless dataset (JSONL) for training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--suite",
        required=True,
        help="Path to suite YAML file (e.g., experiments/suites/bidless_dataset_tiny.yaml)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Override suite seed (default: use suite.parameters.seed)"
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for JSONL dataset file"
    )
    parser.add_argument(
        "--n-per",
        type=int,
        help="Override n_per from suite (hands per scenario)"
    )
    return parser.parse_args()


def load_suite_config(suite_path: str) -> Dict[str, Any]:
    """Load suite configuration from YAML."""
    with open(suite_path, 'r') as f:
        return yaml.safe_load(f)


def load_experiment_config(config_path: str) -> Dict[str, Any]:
    """Load experiment configuration from YAML."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def normalize_contract_type(contract_type: str) -> str:
    """Normalize contract type to lowercase (expected by simulation and hand_eval)."""
    ct_lower = contract_type.lower()
    if ct_lower in ("high", "low", "suit"):
        return ct_lower
    return contract_type


def collect_dataset(
    suite_config: Dict[str, Any],
    seed: int,
    n_per: int,
    output_path: str
) -> None:
    """
    Collect bidless dataset from suite configuration.

    Runs simulations for each scenario and collects hand-level data.
    """
    # Use deterministic run_id based on seed for reproducibility
    run_id = f"bidless_seed{seed}"

    # Load experiment config from suite
    config_paths = suite_config.get('configs', [])
    if not config_paths:
        raise ValueError("Suite must specify at least one config in 'configs'")

    all_collectors: List[BidlessDatasetCollector] = []
    hand_counter = 0

    for config_path in config_paths:
        config = load_experiment_config(config_path)
        scenarios = config.get('scenarios', [])

        if not scenarios:
            print(f"Warning: No scenarios in {config_path}, skipping")
            continue

        for scenario_idx, scenario in enumerate(scenarios):
            contract_type = normalize_contract_type(scenario.get('contract_type', 'suit'))
            trump_suit = scenario.get('trump_suit')

            # Validate contract/trump combination
            if contract_type == "suit" and trump_suit is None:
                print(f"Warning: Suit contract without trump_suit in scenario {scenario_idx}, skipping")
                continue
            if contract_type in ("high", "low"):
                trump_suit = None  # Ensure no trump for HIGH/LOW

            # Create deterministic RNG for this scenario
            scenario_seed = seed + scenario_idx
            rng = random.Random(scenario_seed)

            # Create strategies for all 4 seats (deterministic)
            strategies = [
                RandomLegalStrategy(seed=scenario_seed + seat)
                for seat in range(4)
            ]

            print(f"Collecting {n_per} hands for {contract_type}"
                  f"{f' ({trump_suit})' if trump_suit else ''}...")

            for deal_id in range(n_per):
                # Generate deterministic deal
                hands = generate_deal(scenario_seed, deal_id)

                # Determine dealer (deterministic based on seed)
                dealer_seat = rng.randint(0, 3)

                # Run simulation to validate the scenario works
                try:
                    result = play_single_hand(
                        contract_type=contract_type,
                        trump_suit=trump_suit,
                        strategies=strategies,
                        deal_id=deal_id,
                        hands=hands,
                        deal_seed=scenario_seed,
                        initial_leader=dealer_seat,
                        rng=random.Random(scenario_seed + deal_id),
                    )
                    # Simulation succeeded - we just need to verify it runs
                    _ = result[0], result[1]  # t0, t1 trick counts (unused)
                except Exception as e:
                    print(f"Warning: Failed to simulate hand {deal_id}: {e}")
                    continue

                # Create collector for this hand
                collector = BidlessDatasetCollector(run_id, hand_counter)

                # Record each player's hand
                # Note: BidlessDatasetCollector expects "suit", "high", "low" (lowercase)
                # but its validation checks for "HIGH"/"LOW". We pass lowercase since
                # that's what get_hand_features() expects internally.
                for seat in range(4):
                    collector.record_hand_value(
                        hand=hands[seat],
                        seat=seat,
                        dealer_seat=dealer_seat,
                        contract_type=contract_type,
                        trump_suit=trump_suit,
                        deal_id=deal_id,
                    )

                # Set contract context for feature computation
                collector.set_contract_context(contract_type, trump_suit)

                all_collectors.append(collector)
                hand_counter += 1

    if not all_collectors:
        print("Warning: No hands collected")
        return

    # Combine all rows and write to JSONL
    all_rows = []
    for collector in all_collectors:
        all_rows.extend(collector.get_rows_sorted())

    # Sort all rows deterministically
    all_rows_sorted = sorted(
        all_rows,
        key=lambda r: (r["hand_id"], r["seat"])
    )

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Write JSONL output
    with open(output_path, 'w') as f:
        for row in all_rows_sorted:
            # Add run_id to each row for traceability
            row_with_meta = {"run_id": run_id, **row}
            json.dump(row_with_meta, f, sort_keys=True)
            f.write('\n')

    print(f"Collected {len(all_collectors)} hands ({len(all_rows_sorted)} rows) to {output_path}")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load suite configuration
    suite_config = load_suite_config(args.suite)

    # Get parameters (CLI overrides suite)
    suite_params = suite_config.get('parameters', {})
    seed = args.seed if args.seed is not None else suite_params.get('seed', 42)
    n_per = args.n_per if args.n_per is not None else suite_params.get('n_per', 10)

    # Collect dataset
    collect_dataset(suite_config, seed, n_per, args.out)

    print(f"Dataset collection complete. Output: {args.out}")


if __name__ == "__main__":
    main()
