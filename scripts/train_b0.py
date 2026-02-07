#!/usr/bin/env python3
"""Train B0 hand value regression model from bidless dataset.

Thin CLI wrapper around bid_euchre.models.train_b0.

Usage:
    PYTHONPATH=src python scripts/train_b0.py \
        --dataset data/bidless_dataset.jsonl \
        --output data/models/b0_v1.json \
        --seed 42
"""

from __future__ import annotations

import argparse

from bid_euchre.models.train_b0 import B0TrainingConfig, save_b0_model, train_b0_model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train B0 hand value regression model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to bidless dataset JSONL file",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for trained model JSON",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--model-type",
        choices=["ols", "ridge"],
        default="ridge",
        help="Model type (default: ridge)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Ridge regularization parameter (default: 1.0)",
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.2,
        help="Test set fraction (default: 0.2)",
    )

    args = parser.parse_args()

    config = B0TrainingConfig(
        dataset_path=args.dataset,
        output_path=args.output,
        seed=args.seed,
        model_type=args.model_type,
        alpha=args.alpha,
        test_split=args.test_split,
    )

    print(f"Training B0 model from {config.dataset_path}...")
    model, metrics = train_b0_model(config)

    print(f"Train metrics: MSE={metrics['train']['mse']:.4f}, R²={metrics['train']['r2']:.4f}")
    print(f"Test metrics:  MSE={metrics['test']['mse']:.4f}, R²={metrics['test']['r2']:.4f}")

    save_b0_model(model, config.output_path, config.seed)
    print(f"Model saved to {config.output_path}")


if __name__ == "__main__":
    main()
