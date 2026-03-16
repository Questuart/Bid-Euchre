"""Evidence manifest assembly and markdown rendering for Arc D v2.

Produces evidence_manifest.json and 00_manifest.md that record the
full provenance chain for a rung: lineage ID, roster, seeds, run IDs,
artifact inventory, table inventory, and chart inventory.

Extracted from ``scripts/internal/generate_evidence_manifest.py``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from bid_euchre.arc_d_v2.lifecycle import list_runs

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


def _get_lifecycle_status(rung_dir: Path) -> list[dict]:
    """Collect lifecycle status for all run subdirectories in a rung dir."""
    entries: list[dict] = []
    for run_path, art_status in list_runs(rung_dir):
        entry: dict = {"run_id": run_path.name}
        if art_status is None:
            entry["status"] = "active"
        else:
            entry["status"] = art_status.status
            if art_status.superseded_by:
                entry["superseded_by"] = art_status.superseded_by
            if art_status.supersedes:
                entry["supersedes"] = art_status.supersedes
            if art_status.quarantine_reason:
                entry["quarantine_reason"] = art_status.quarantine_reason
        entries.append(entry)
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

    # Lifecycle status for the rung directory
    lifecycle_status = _get_lifecycle_status(rung_dir)

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
        "lifecycle": lifecycle_status,
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

    # Lifecycle status
    lifecycle = manifest.get("lifecycle", [])
    if lifecycle:
        lines.extend(
            [
                "## Lifecycle Status",
                "",
                "| Run | Status | Superseded By |",
                "|-----|--------|---------------|",
            ]
        )
        for entry in lifecycle:
            sup_by = entry.get("superseded_by", "")
            lines.append(
                f"| `{entry.get('run_id', '')}` "
                f"| {entry.get('status', '')} "
                f"| {sup_by or '-'} |"
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

    # Chart Data
    chart_data = manifest.get("chart_data", [])
    if chart_data:
        lines.extend(
            [
                "## Chart Data",
                "",
                "| Name | Size |",
                "|------|------|",
            ]
        )
        for cd in chart_data:
            size = cd.get("size_bytes", 0)
            lines.append(f"| `{cd.get('name', '')}` | {size:,} bytes |")
        lines.append("")

    return "\n".join(lines) + "\n"
