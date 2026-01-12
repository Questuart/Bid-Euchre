#!/usr/bin/env python3
"""
Train a deterministic bidding model to imitate StrictRaiserBidder.

This script trains a simple deterministic model that replicates StrictRaiserBidder
behavior and emits a JSON artifact conforming to the bidding model schema.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bid_euchre.models.train_bidder import train_and_save_model


def main():
    parser = argparse.ArgumentParser(
        description="Train deterministic bidding model for StrictRaiserBidder imitation"
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
            seed=args.seed
        )

        print(f"✅ Successfully trained and saved model to {args.output}")
        print(f"   Model type: {artifact['model_type']}")
        print(f"   Contract: {artifact['contract']}")
        print(f"   Schema version: {artifact['schema_version']}")

    except Exception as e:
        print(f"❌ Training failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
