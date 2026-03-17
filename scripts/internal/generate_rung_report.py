#!/usr/bin/env python
"""CLI wrapper for markdown rung report generation.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.report``.

Generates both:
- ``01_results.md`` — full results report
- ``02_decision.md`` — concise decision report

Usage:
    uv run python scripts/internal/generate_rung_report.py \\
        --report-dir /tmp/rung_report

    uv run python scripts/internal/generate_rung_report.py \\
        --report-dir /tmp/rung_report --rung R3 --mode QUICK
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from bid_euchre.arc_d_v2.report import generate_decision_report, generate_report

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
        "--rung",
        default="?",
        help="Rung identifier (e.g., R0, R3) for decision report",
    )
    parser.add_argument(
        "--mode",
        default="QUICK",
        help="Compute mode (e.g., QUICK, FULL) for decision report",
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

    # 01_results.md
    report_content = generate_report(args.report_dir)
    output_path = args.output or (args.report_dir / "01_results.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content)
    logger.info("Wrote report: %s", output_path)

    # 02_decision.md
    tables_dir = args.report_dir / "tables"
    charts_dir = args.report_dir / "charts"
    chart_data_dir = args.report_dir / "chart_data"
    decision_path = output_path.parent / "02_decision.md"
    generate_decision_report(
        tables_dir=tables_dir,
        charts_dir=charts_dir,
        chart_data_dir=chart_data_dir if chart_data_dir.exists() else None,
        output_path=decision_path,
        rung=args.rung,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
