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
from typing import Any, Dict

import yaml

# TODO: Import bidless dataset collector from PR 140 when it lands
# from bid_euchre.datasets.bidless import BidlessDatasetCollector


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
    return parser.parse_args()


def load_suite_config(suite_path: str) -> Dict[str, Any]:
    """Load suite configuration from YAML."""
    with open(suite_path, 'r') as f:
        return yaml.safe_load(f)


def collect_dataset(suite_config: Dict[str, Any], seed: int, output_path: str) -> None:
    """
    Collect bidless dataset from suite configuration.
    
    This is a placeholder implementation that will be updated when PR 140 lands
    with the actual bidless dataset collector.
    """
    # For now, create a minimal deterministic output
    # This will be replaced with actual simulation + collection logic
    
    # Use seed for deterministic output
    import random
    random.seed(seed)
    
    # Placeholder: generate some sample hand data
    # In real implementation, this would run simulations and collect from BidlessDatasetCollector
    n_per = suite_config['parameters'].get('n_per', 10)
    
    sample_hands = [
        {
            "hand_id": f"hand_{i:04d}",
            "cards": sorted(["AH", "KH", "QH", "JH", "TH"]),  # Sample hand (sorted for determinism)
            "features": {"trump_strength": 0.8, "offsuit_control": 0.6},
            "run_id": f"run_{seed}",
            "seed": seed
        }
        for i in range(n_per)
    ]
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Write JSONL output
    with open(output_path, 'w') as f:
        for hand_data in sample_hands:
            json.dump(hand_data, f, sort_keys=True)
            f.write('\n')
    
    print(f"Collected {len(sample_hands)} hands to {output_path}")


def main() -> None:
    """Main entry point."""
    args = parse_args()
    
    # Load suite configuration
    suite_config = load_suite_config(args.suite)
    
    # Use provided seed or suite default
    seed = args.seed if args.seed is not None else suite_config['parameters']['seed']
    
    # Collect dataset
    collect_dataset(suite_config, seed, args.out)
    
    print(f"Dataset collection complete. Output: {args.out}")


if __name__ == "__main__":
    main()
