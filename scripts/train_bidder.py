#!/usr/bin/env python3
"""
Train a deterministic bidding model to imitate a teacher bidding policy.

This script trains simple deterministic models that replicate teacher bidding behavior
and emit JSON artifacts conforming to the bidding model schema.

Supported teachers:
- strict_raiser: StrictRaiserBidder (simple raising strategy)
- heuristics: HeuristicsBidder (v1 baseline heuristic bidder)
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bid_euchre.models.train_bidder import train_and_save_model


def main():
    parser = argparse.ArgumentParser(
        description="Train deterministic bidding model via imitation learning"
    )
    parser.add_argument(
        "--teacher",
        type=str,
        default="strict_raiser",
        choices=["strict_raiser", "heuristics"],
        help="Teacher bidding policy to imitate (default: strict_raiser)"
    )
    parser.add_argument(
        "--contract",
        type=str,
        default="S",
        choices=["C", "D", "H", "S", "HIGH", "LOW"],
        help="Contract to train model for (default: S)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for JSON artifact"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )

    args = parser.parse_args()

    try:
        # Train and save model
        artifact = train_and_save_model(
            contract=args.contract,
            output_path=args.output,
            seed=args.seed,
            teacher=args.teacher
        )

        print(f"✅ Successfully trained and saved model to {args.output}")
        print(f"   Teacher: {args.teacher}")
        print(f"   Model type: {artifact['model_type']}")
        print(f"   Contract: {artifact['contract']}")
        print(f"   Schema version: {artifact['schema_version']}")

    except Exception as e:
        print(f"❌ Training failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
