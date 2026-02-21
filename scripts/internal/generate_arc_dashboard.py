#!/usr/bin/env python
"""Generate cross-rung progression dashboard for Arc D.

Reads all completed rung bundles under data/artifacts/arc_d/ and produces
a Markdown dashboard with a progression table.

Usage:
    PYTHONPATH=src python scripts/internal/generate_arc_dashboard.py \
        --artifacts-base data/artifacts/arc_d \
        --output docs/04_reports/model_arc_d_dashboard.md
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_dashboard(
    artifacts_base: str | Path = "data/artifacts/arc_d",
    output_path: str | Path = "docs/04_reports/model_arc_d_dashboard.md",
) -> str:
    """Generate cross-rung progression dashboard from completed rung bundles.

    Scans artifacts_base for rung_bundle_*.json files, extracts key
    metrics, and produces a Markdown table showing progression across rungs.

    Args:
        artifacts_base: Base directory containing per-rung subdirectories.
        output_path: Path to write the dashboard Markdown.

    Returns:
        The dashboard as a Markdown string.
    """
    base = Path(artifacts_base)
    bundles = []

    if base.exists():
        for bundle_file in sorted(base.rglob("rung_bundle_*.json")):
            try:
                with open(bundle_file) as f:
                    bundle = json.load(f)
                bundle["_source_path"] = str(bundle_file)
                bundles.append(bundle)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping %s: %s", bundle_file, e)

    sections = []
    sections.append("# Arc D Progression Dashboard")
    sections.append("")

    if not bundles:
        sections.append("*No completed rung bundles found.*")
        sections.append("")
        sections.append(f"Searched: `{artifacts_base}`")
    else:
        sections.append(
            "| Rung | OLSa net_eppd | Full net_eppd | Gap"
            " | OLSa Features | Full Features | Bundle Path |"
        )
        sections.append(
            "|------|--------------|--------------|-----"
            "|--------------|--------------|-------------|"
        )

        for b in bundles:
            rung = b.get("rung_id", "?")
            olsa = b.get("olsa", {})
            olsa_full = b.get("olsa_full", {})

            olsa_feats = _feature_summary(olsa)
            full_feats = _feature_summary(olsa_full)

            olsa_eppd = olsa.get("net_eppd")
            full_eppd = olsa_full.get("net_eppd")
            gap_str = "\u2014"
            olsa_eppd_str = f"{olsa_eppd:.4f}" if olsa_eppd is not None else "\u2014"
            full_eppd_str = f"{full_eppd:.4f}" if full_eppd is not None else "\u2014"
            if olsa_eppd is not None and full_eppd is not None:
                gap_str = f"{full_eppd - olsa_eppd:+.4f}"
            src = b.get("_source_path", "\u2014")

            sections.append(
                f"| {rung} | {olsa_eppd_str} | {full_eppd_str} | {gap_str}"
                f" | {olsa_feats} | {full_feats} | {src} |"
            )

        sections.append("")
        sections.append(f"*{len(bundles)} rung(s) found.*")

    sections.append("")
    dashboard = "\n".join(sections)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dashboard)
    logger.info("Dashboard written to %s", output)

    return dashboard


def _feature_summary(arm_data: dict) -> str:
    """Summarize feature counts per contract."""
    selected = arm_data.get("selected_features", {})
    if not selected:
        return "\u2014"
    return "/".join(str(len(feats)) for _, feats in sorted(selected.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Arc D dashboard")
    parser.add_argument(
        "--artifacts-base",
        default="data/artifacts/arc_d",
        help="Base directory for rung artifacts",
    )
    parser.add_argument(
        "--output",
        default="docs/04_reports/model_arc_d_dashboard.md",
        help="Output dashboard path",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    generate_dashboard(args.artifacts_base, args.output)


if __name__ == "__main__":
    main()
