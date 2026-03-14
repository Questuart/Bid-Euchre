#!/usr/bin/env python
"""CLI wrapper for evidence manifest generation.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.manifest``.

Usage:
    PYTHONPATH=src uv run python scripts/internal/generate_evidence_manifest.py \\
        --rung-dir data/fixtures/arc_d_v2 \\
        --report-dir /tmp/rung_report \\
        --plan-dir plans/arc_d_v2/r0
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from bid_euchre.arc_d_v2.manifest import (
    generate_evidence_manifest,
    render_manifest_markdown,
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate evidence manifest for an Arc D v2 rung."
    )
    parser.add_argument(
        "--rung-dir",
        required=True,
        type=Path,
        help="Path to rung artifacts directory",
    )
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="Path to generated report directory (tables/, charts/)",
    )
    parser.add_argument(
        "--plan-dir",
        default=None,
        type=Path,
        help="Path to rung plan directory (optional)",
    )
    parser.add_argument(
        "--rung-id",
        default="r0",
        help="Rung identifier (default: r0)",
    )
    parser.add_argument(
        "--lineage-id",
        default="arc_d_v2",
        help="Lineage identifier (default: arc_d_v2)",
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

    manifest = generate_evidence_manifest(
        rung_dir=args.rung_dir,
        report_dir=args.report_dir,
        plan_dir=args.plan_dir,
        rung_id=args.rung_id,
        lineage_id=args.lineage_id,
    )

    # Write JSON manifest
    output_json = args.report_dir / "evidence_manifest.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("Wrote: %s", output_json)

    # Write markdown manifest
    output_md = args.report_dir / "00_manifest.md"
    md_content = render_manifest_markdown(manifest)
    output_md.write_text(md_content)
    logger.info("Wrote: %s", output_md)


if __name__ == "__main__":
    main()
