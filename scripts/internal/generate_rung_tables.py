#!/usr/bin/env python
"""CLI wrapper for canonical CSV table generation.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.tables``.

Usage:
    PYTHONPATH=src uv run python scripts/internal/generate_rung_tables.py \\
        --rung-dir data/fixtures/arc_d_v2 \\
        --output-dir /tmp/rung_tables
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from bid_euchre.arc_d_v2.tables import (
    generate_all_tables,
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate canonical CSV tables for an Arc D v2 rung report."
    )
    parser.add_argument(
        "--rung-dir",
        required=True,
        type=Path,
        help="Path to directory containing rung artifacts",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Path to write CSV tables",
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "quick", "full"],
        default=None,
        help="Execution mode for deterministic artifact selection",
    )
    parser.add_argument(
        "--seed",
        default=None,
        help="RNG seed(s) for deterministic artifact selection. "
        "Comma-separated for multi-seed FULL (e.g., '42,123,456')",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        action="append",
        default=None,
        help="Path to dataset directory containing action_value.parquet. "
        "Can be specified multiple times for multi-shard datasets. "
        "When provided, parquet discovery uses these instead of rung-dir.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Parse seed(s) — supports single int or comma-separated list
    seeds = None
    if args.seed:
        seeds = [int(s.strip()) for s in args.seed.split(",")]

    generated = generate_all_tables(
        args.rung_dir,
        args.output_dir,
        mode=args.mode,
        seeds=seeds,
        dataset_dirs=args.dataset_dir,
    )
    logger.info("Generated %d tables: %s", len(generated), ", ".join(generated))


if __name__ == "__main__":
    main()
