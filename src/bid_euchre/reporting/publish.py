"""Chart snapshot publishing and versioning.

Manages versioned chart snapshots for report assets. Each snapshot is a
directory of PNGs identified by a snapshot_id (e.g. ``phase0_20260207``).

Do NOT re-export from ``reporting/__init__.py`` (circular import risk).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _next_snapshot_id(
    assets_root: Path,
    prefix: str,
    date_str: str | None = None,
) -> str:
    """Generate the next snapshot ID for *prefix*.

    First snapshot on a date: ``{prefix}_{YYYYMMDD}``
    Same-day reruns: ``{prefix}_{YYYYMMDD}_r2``, ``_r3``, ...
    """
    if date_str is None:
        date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")

    base_id = f"{prefix}_{date_str}"

    if not (assets_root / base_id).exists():
        return base_id

    # Find existing _rN dirs for this date
    pattern = re.compile(rf"^{re.escape(base_id)}_r(\d+)$")
    max_n = 1  # base dir counts as r1
    for d in assets_root.iterdir():
        if d.is_dir():
            m = pattern.match(d.name)
            if m:
                max_n = max(max_n, int(m.group(1)))

    return f"{base_id}_r{max_n + 1}"


def publish_chart_snapshot(
    source_dir: Path,
    assets_root: Path,
    prefix: str,
    snapshot_id: str | None = None,
    update_latest: bool = True,
) -> str:
    """Copy chart PNGs from *source_dir* to a versioned snapshot directory.

    Args:
        source_dir: Directory containing chart PNGs.
        assets_root: Root assets directory (e.g. ``docs/04_reports/assets``).
        prefix: Report prefix (e.g. ``phase0``).
        snapshot_id: Explicit snapshot ID. Auto-generated if *None*.
        update_latest: If *True*, also copy into ``{prefix}_latest/``.

    Returns:
        The snapshot ID that was used.

    Raises:
        FileNotFoundError: If *source_dir* does not exist.
        ValueError: If *source_dir* contains no PNG files.
    """
    source_dir = Path(source_dir)
    assets_root = Path(assets_root)

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    pngs = sorted(source_dir.glob("*.png"))
    if not pngs:
        raise ValueError(f"No PNG files found in {source_dir}")

    if snapshot_id is None:
        snapshot_id = _next_snapshot_id(assets_root, prefix)

    snapshot_dir = assets_root / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for png in pngs:
        shutil.copy2(png, snapshot_dir / png.name)

    if update_latest:
        latest_dir = assets_root / f"{prefix}_latest"
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        shutil.copytree(snapshot_dir, latest_dir)

    return snapshot_id


def update_versions_manifest(
    assets_root: Path,
    prefix: str,
    snapshot_id: str,
    chart_files: list[str],
    source_run_ids: list[str] | None = None,
    notes: str = "",
) -> Path:
    """Append a snapshot entry to ``{prefix}_versions.json``.

    Args:
        assets_root: Root assets directory.
        prefix: Report prefix.
        snapshot_id: The snapshot ID to record.
        chart_files: List of chart filenames in the snapshot.
        source_run_ids: Optional list of source run IDs.
        notes: Optional human-readable notes.

    Returns:
        Path to the versions manifest file.
    """
    assets_root = Path(assets_root)
    manifest_path = assets_root / f"{prefix}_versions.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"snapshots": []}

    entry = {
        "snapshot_id": snapshot_id,
        "created_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "chart_files": sorted(chart_files),
        "source_run_ids": source_run_ids or [],
        "notes": notes,
    }

    manifest["snapshots"].append(entry)
    manifest["latest"] = snapshot_id

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return manifest_path


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Publish chart snapshot")
    parser.add_argument("--source-dir", required=True, help="Dir with chart PNGs")
    parser.add_argument(
        "--assets-root", default="docs/04_reports/assets", help="Assets root"
    )
    parser.add_argument("--prefix", default="phase0", help="Report prefix")
    parser.add_argument("--snapshot-id", default=None, help="Explicit snapshot ID")
    parser.add_argument(
        "--no-update-latest",
        dest="update_latest",
        action="store_false",
        help="Skip updating the latest alias",
    )
    parser.add_argument(
        "--source-run-ids",
        default="",
        help="Comma-separated run IDs for provenance",
    )
    parser.add_argument("--notes", default="", help="Human-readable notes")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    assets_root = Path(args.assets_root)

    sid = publish_chart_snapshot(
        source_dir,
        assets_root,
        args.prefix,
        snapshot_id=args.snapshot_id,
        update_latest=args.update_latest,
    )

    run_ids = [r.strip() for r in args.source_run_ids.split(",") if r.strip()]
    chart_files = [p.name for p in sorted((assets_root / sid).glob("*.png"))]

    manifest_path = update_versions_manifest(
        assets_root,
        args.prefix,
        sid,
        chart_files,
        source_run_ids=run_ids or None,
        notes=args.notes,
    )

    print(f"Published snapshot: {sid}")
    print(f"Snapshot dir: {assets_root / sid}")
    if args.update_latest:
        print(f"Latest alias: {assets_root / f'{args.prefix}_latest'}")
    print(f"Manifest: {manifest_path}")

    sys.exit(0)
