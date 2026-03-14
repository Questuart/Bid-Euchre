#!/usr/bin/env python
"""CLI wrapper for markdown rung report generation.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.report``.

Usage:
    uv run python scripts/internal/generate_rung_report.py \\
        --report-dir /tmp/rung_report
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from bid_euchre.arc_d_v2.report import generate_report

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate markdown rung report from CSV tables and chart PNGs."
    )
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="Directory containing tables/*.csv and charts/*.png",
    )
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Output file path (default: report-dir/01_results.md)",
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

    report_content = generate_report(args.report_dir)

    output_path = args.output or (args.report_dir / "01_results.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content)
    logger.info("Wrote report: %s", output_path)


if __name__ == "__main__":
    main()
