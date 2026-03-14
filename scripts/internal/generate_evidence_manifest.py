#!/usr/bin/env python
"""Generate evidence manifest for an Arc D v2 rung report.

Produces evidence_manifest.json and 00_manifest.md that record the
full provenance chain for the rung: lineage ID, roster, seeds, run IDs,
artifact inventory, table inventory, and chart inventory.

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
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_git_sha() -> str:
    """Get current git HEAD SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def _load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if not found."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _inventory_dir(directory: Path, suffix: str) -> list[dict]:
    """Inventory files in a directory with a given suffix."""
    if not directory.exists():
        return []
    entries = []
    for p in sorted(directory.glob(f"*{suffix}")):
        entries.append(
            {
                "name": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
            }
        )
    return entries


def generate_evidence_manifest(
    rung_dir: Path,
    report_dir: Path,
    plan_dir: Path | None = None,
    rung_id: str = "r0",
    lineage_id: str = "arc_d_v2",
) -> dict:
    """Generate the evidence manifest dict.

    Args:
        rung_dir: Path to rung artifacts (H2H, comparator, training).
        report_dir: Path to generated report (tables/, charts/).
        plan_dir: Path to rung plan directory.
        rung_id: Rung identifier (e.g., "r0").
        lineage_id: Lineage identifier (e.g., "arc_d_v2").

    Returns:
        Evidence manifest dict matching arc_d_evidence_manifest_v1 schema.
    """
    provenance_sha = _get_git_sha()

    # Load roster for anchor and models
    roster = _load_json(rung_dir / "roster.json")
    anchor_name = ""
    roster_entries = []
    if roster:
        anchor = roster.get("anchor", {})
        anchor_name = anchor.get("name", "")
        for m in roster.get("models", []):
            roster_entries.append(
                {
                    "name": m.get("name"),
                    "class_name": m.get("class_name"),
                    "trainable": m.get("trainable", False),
                    "status": "evaluated",
                }
            )

    # Load H2H for run_ids and seeds
    h2h = _load_json(rung_dir / "h2h_battery.json")
    seeds = []
    run_ids = []
    mode = "QUICK"
    if h2h:
        seeds.append(h2h.get("seed", 42))
        mode = h2h.get("mode", "QUICK")
        for cell in h2h.get("cells", {}).values():
            rid = cell.get("run_id")
            if rid and rid not in run_ids:
                run_ids.append(rid)

    # Load comparator for additional run info
    comparator = _load_json(rung_dir / "comparator_cis.json")
    if comparator:
        comp_seed = comparator.get("seed")
        if comp_seed and comp_seed not in seeds:
            seeds.append(comp_seed)

    # Inventory tables
    tables_dir = report_dir / "tables"
    table_inventory = _inventory_dir(tables_dir, ".csv")

    # Inventory charts
    charts_dir = report_dir / "charts"
    chart_inventory = _inventory_dir(charts_dir, ".png")

    # Inventory chart data
    chart_data_dir = report_dir / "chart_data"
    chart_data_inventory = _inventory_dir(chart_data_dir, ".csv")

    # Artifact inventory from rung_dir
    artifact_inventory = []
    for art_path in sorted(rung_dir.glob("*.json")):
        artifact_inventory.append(
            {
                "name": art_path.stem,
                "path": str(art_path),
                "schema_version": "",
            }
        )
        # Try to extract schema version
        art_data = _load_json(art_path)
        if art_data:
            sv = art_data.get("schema_version") or art_data.get("schema", "")
            artifact_inventory[-1]["schema_version"] = sv

    # Plan references
    governing_plan = ""
    plan_shas: list[str] = []
    if plan_dir and plan_dir.exists():
        plan_file = plan_dir / "plan.md"
        if plan_file.exists():
            governing_plan = str(plan_file)

    manifest = {
        "schema_version": "arc_d_evidence_manifest_v1",
        "lineage_id": lineage_id,
        "rung_id": rung_id,
        "provenance_sha": provenance_sha,
        "governing_plan": governing_plan,
        "plan_shas": plan_shas,
        "anchor": anchor_name,
        "roster": roster_entries,
        "seeds": seeds,
        "mode": mode,
        "run_ids": run_ids,
        "artifacts": artifact_inventory,
        "tables": table_inventory,
        "charts": chart_inventory,
        "chart_data": chart_data_inventory,
    }

    return manifest


def render_manifest_markdown(manifest: dict) -> str:
    """Render evidence manifest as markdown for 00_manifest.md."""
    lines = [
        "# Rung Manifest",
        "",
        f"**Lineage:** {manifest.get('lineage_id', 'unknown')}",
        f"**Rung:** {manifest.get('rung_id', 'unknown')}",
        f"**Provenance SHA:** `{manifest.get('provenance_sha', 'unknown')}`",
        f"**Mode:** {manifest.get('mode', 'unknown')}",
        f"**Seeds:** {manifest.get('seeds', [])}",
        f"**Anchor:** {manifest.get('anchor', 'none')}",
        "",
    ]

    # Governing plan
    plan = manifest.get("governing_plan", "")
    if plan:
        lines.extend(
            [
                f"**Governing Plan:** `{plan}`",
                "",
            ]
        )

    # Roster
    roster = manifest.get("roster", [])
    if roster:
        lines.extend(
            [
                "## Model Roster",
                "",
                "| Model | Class | Trainable | Status |",
                "|-------|-------|-----------|--------|",
            ]
        )
        for entry in roster:
            lines.append(
                f"| {entry.get('name', '')} "
                f"| {entry.get('class_name', '')} "
                f"| {entry.get('trainable', False)} "
                f"| {entry.get('status', '')} |"
            )
        lines.append("")

    # Run IDs
    run_ids = manifest.get("run_ids", [])
    if run_ids:
        lines.extend(
            [
                "## Run IDs",
                "",
            ]
        )
        for rid in run_ids:
            lines.append(f"- `{rid}`")
        lines.append("")

    # Artifacts
    artifacts = manifest.get("artifacts", [])
    if artifacts:
        lines.extend(
            [
                "## Artifacts",
                "",
                "| Name | Schema | Path |",
                "|------|--------|------|",
            ]
        )
        for a in artifacts:
            lines.append(
                f"| {a.get('name', '')} "
                f"| {a.get('schema_version', '')} "
                f"| `{a.get('path', '')}` |"
            )
        lines.append("")

    # Tables
    tables = manifest.get("tables", [])
    if tables:
        lines.extend(
            [
                "## Tables",
                "",
                "| Name | Size |",
                "|------|------|",
            ]
        )
        for t in tables:
            size = t.get("size_bytes", 0)
            lines.append(f"| `{t.get('name', '')}` | {size:,} bytes |")
        lines.append("")

    # Charts
    charts = manifest.get("charts", [])
    if charts:
        lines.extend(
            [
                "## Charts",
                "",
                "| Name | Size |",
                "|------|------|",
            ]
        )
        for c in charts:
            size = c.get("size_bytes", 0)
            lines.append(f"| `{c.get('name', '')}` | {size:,} bytes |")
        lines.append("")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


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
