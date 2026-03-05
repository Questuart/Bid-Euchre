#!/usr/bin/env python
"""
CLI wrapper for the hybrid OLSa training pipeline.

Usage:
    PYTHONPATH=src python scripts/train_hybrid_olsa.py \
        --run-dir data/runs/<run_id> \
        --seed 42 \
        --output /tmp/hybrid_artifacts/

    # Constrained arm only (locked 3/1/1 features):
    PYTHONPATH=src python scripts/train_hybrid_olsa.py \
        --run-dir data/runs/<run_id> \
        --seed 42 \
        --output /tmp/hybrid_artifacts/ \
        --arm-mode constrained

    # Custom feature budget for full arm:
    PYTHONPATH=src python scripts/train_hybrid_olsa.py \
        --run-dir data/runs/<run_id> \
        --seed 42 \
        --output /tmp/hybrid_artifacts/ \
        --feature-budget "suit:10,high:5,low:5"
"""

import argparse
import logging

from bid_euchre.models.train_hybrid_olsa import train_hybrid_olsa


def _parse_feature_budget(raw: str) -> dict[str, int]:
    """Parse 'suit:10,high:5,low:5' into {'suit': 10, 'high': 5, 'low': 5}."""
    budget = {}
    for entry in raw.split(","):
        key, val = entry.strip().split(":")
        budget[key.strip()] = int(val.strip())
    return budget


def main() -> None:
    parser = argparse.ArgumentParser(description="Train hybrid OLSa models")
    parser.add_argument(
        "--run-dir", required=True, help="Canonical bidless run directory"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--output", required=True, help="Output directory for artifacts"
    )
    parser.add_argument(
        "--split-type",
        default="three_way",
        choices=["two_way", "three_way"],
        help="Split type (default: three_way)",
    )
    parser.add_argument(
        "--arm-mode",
        default="both",
        choices=["both", "constrained", "full"],
        help="Which arms to train (default: both)",
    )
    parser.add_argument(
        "--feature-budget",
        default=None,
        help="Per-contract max features, e.g. 'suit:10,high:5,low:5'",
    )
    parser.add_argument(
        "--no-freeze", action="store_true", help="Skip freezing artifacts"
    )
    parser.add_argument("--rung-id", default="r0", help="Rung identifier (default: r0)")
    parser.add_argument(
        "--risk-lambda",
        type=float,
        default=0.0,
        help="Risk penalty coefficient (default: 0.0)",
    )
    parser.add_argument(
        "--offensive-defensive",
        action="store_true",
        help="Train separate offensive/defensive sub-models per contract",
    )
    parser.add_argument(
        "--context-candidates",
        default=None,
        help="Comma-separated context feature names for constrained arm additive "
        "forward selection, e.g. 'partner_bid_level,partner_passed,"
        "partner_suit_match'",
    )
    parser.add_argument(
        "--training-mode",
        choices=["joint", "ridge", "two_stage"],
        default="joint",
        help="Weight fitting strategy: 'joint' (OLS), 'ridge' (L2), 'two_stage' (fit base then partner on residuals)",
    )
    parser.add_argument(
        "--ridge-alpha",
        type=float,
        default=1.0,
        help="L2 penalty strength for 'ridge' mode (default: 1.0)",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    feature_budget = None
    if args.feature_budget:
        feature_budget = _parse_feature_budget(args.feature_budget)

    context_candidates = None
    if args.context_candidates:
        context_candidates = [c.strip() for c in args.context_candidates.split(",")]

    result = train_hybrid_olsa(
        run_dir=args.run_dir,
        seed=args.seed,
        output_dir=args.output,
        split_type=args.split_type,
        arm_mode=args.arm_mode,
        feature_budget=feature_budget,
        freeze=not args.no_freeze,
        rung_id=args.rung_id,
        risk_lambda=args.risk_lambda,
        offensive_defensive=args.offensive_defensive,
        context_candidates=context_candidates,
        training_mode=args.training_mode,
        ridge_alpha=args.ridge_alpha,
    )

    print(f"\nTraining complete for rung {result['rung_id']}")
    for arm, path in result.get("artifacts", {}).items():
        print(f"  {arm}: {path}")
    if "training_report" in result:
        print(f"  report: {result['training_report']}")
    if "rung_bundle" in result:
        print(f"  bundle: {result['rung_bundle']}")


if __name__ == "__main__":
    main()
