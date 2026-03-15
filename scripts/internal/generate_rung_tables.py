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
        type=int,
        default=None,
        help="RNG seed for deterministic artifact selection",
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

    generated = generate_all_tables(
        args.rung_dir, args.output_dir, mode=args.mode, seed=args.seed
    )
    logger.info("Generated %d tables: %s", len(generated), ", ".join(generated))


if __name__ == "__main__":
    main()
