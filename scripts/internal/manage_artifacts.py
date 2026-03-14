#!/usr/bin/env python
"""CLI for artifact lifecycle management.

Thin wrapper around bid_euchre.arc_d_v2.lifecycle operations.

Usage:
    PYTHONPATH=src uv run python scripts/internal/manage_artifacts.py \\
        status <run_dir>
    PYTHONPATH=src uv run python scripts/internal/manage_artifacts.py \\
        mark-superseded <old_dir> <new_dir>
    PYTHONPATH=src uv run python scripts/internal/manage_artifacts.py \\
        mark-quarantined <run_dir> --reason "description"
    PYTHONPATH=src uv run python scripts/internal/manage_artifacts.py \\
        mark-canonical <run_dir>
    PYTHONPATH=src uv run python scripts/internal/manage_artifacts.py \\
        list <rung_dir>
    PYTHONPATH=src uv run python scripts/internal/manage_artifacts.py \\
        prune <rung_dir> [--execute]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bid_euchre.arc_d_v2.lifecycle import (
    get_status,
    list_runs,
    mark_canonical,
    mark_quarantined,
    mark_superseded,
    prune_superseded,
    supersede_run,
)


def cmd_status(args: argparse.Namespace) -> int:
    """Show status of a run directory."""
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Error: {run_dir} is not a directory", file=sys.stderr)
        return 1
    status = get_status(run_dir)
    if status is None:
        print(f"{run_dir.name}: no status marker (active by default)")
    else:
        print(f"{run_dir.name}: {status.status}")
        if status.superseded_by:
            print(f"  superseded_by: {status.superseded_by}")
        if status.supersedes:
            print(f"  supersedes: {status.supersedes}")
        if status.quarantine_reason:
            print(f"  quarantine_reason: {status.quarantine_reason}")
        if status.notes:
            print(f"  notes: {status.notes}")
        print(f"  timestamp: {status.timestamp}")
    return 0


def cmd_mark_superseded(args: argparse.Namespace) -> int:
    """Mark a run as superseded by another."""
    old_dir = Path(args.old_dir)
    new_dir = Path(args.new_dir)
    if not old_dir.is_dir():
        print(f"Error: {old_dir} is not a directory", file=sys.stderr)
        return 1
    if args.link:
        new_dir.mkdir(parents=True, exist_ok=True)
        manifest = supersede_run(old_dir, new_dir)
        print(f"Superseded {old_dir.name} -> {new_dir.name}")
        print(f"Rerun manifest: {new_dir / 'rerun_manifest.json'}")
        print(f"Rerun ID: {manifest.rerun_id}")
    else:
        mark_superseded(old_dir, new_dir.name)
        print(f"Marked {old_dir.name} as superseded by {new_dir.name}")
    return 0


def cmd_mark_quarantined(args: argparse.Namespace) -> int:
    """Mark a run as quarantined."""
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Error: {run_dir} is not a directory", file=sys.stderr)
        return 1
    mark_quarantined(run_dir, args.reason)
    print(f"Quarantined {run_dir.name}: {args.reason}")
    return 0


def cmd_mark_canonical(args: argparse.Namespace) -> int:
    """Mark a run as canonical."""
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Error: {run_dir} is not a directory", file=sys.stderr)
        return 1
    mark_canonical(run_dir)
    print(f"Marked {run_dir.name} as canonical")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all runs in a rung directory with their statuses."""
    rung_dir = Path(args.rung_dir)
    runs = list_runs(rung_dir)
    if not runs:
        print(f"No run directories found in {rung_dir}")
        return 0
    for run_path, status in runs:
        if status is None:
            label = "active (no marker)"
        else:
            label = status.status
            if status.superseded_by:
                label += f" -> {status.superseded_by}"
            if status.quarantine_reason:
                label += f" ({status.quarantine_reason})"
        print(f"  {run_path.name}: {label}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """List or remove superseded/quarantined run directories."""
    rung_dir = Path(args.rung_dir)
    dry_run = not args.execute
    prunable = prune_superseded(rung_dir, dry_run=dry_run)
    if not prunable:
        print("No superseded/quarantined runs to prune.")
        return 0
    verb = "Removed" if not dry_run else "Would remove"
    for p in prunable:
        print(f"  {verb}: {p.name}")
    if dry_run:
        print(
            f"\n{len(prunable)} directories would be removed. Use --execute to delete."
        )
    else:
        print(f"\n{len(prunable)} directories removed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Artifact lifecycle management for Arc D v2.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = sub.add_parser("status", help="Show run status")
    p_status.add_argument("run_dir", help="Path to run directory")

    # mark-superseded
    p_sup = sub.add_parser("mark-superseded", help="Mark run as superseded")
    p_sup.add_argument("old_dir", help="Path to old run directory")
    p_sup.add_argument("new_dir", help="Path to (or name of) new run directory")
    p_sup.add_argument(
        "--link",
        action="store_true",
        help="Also create rerun manifest in new dir (full supersession)",
    )

    # mark-quarantined
    p_quar = sub.add_parser("mark-quarantined", help="Mark run as quarantined")
    p_quar.add_argument("run_dir", help="Path to run directory")
    p_quar.add_argument("--reason", required=True, help="Quarantine reason")

    # mark-canonical
    p_can = sub.add_parser("mark-canonical", help="Mark run as canonical")
    p_can.add_argument("run_dir", help="Path to run directory")

    # list
    p_list = sub.add_parser("list", help="List runs with statuses")
    p_list.add_argument("rung_dir", help="Path to rung directory")

    # prune
    p_prune = sub.add_parser("prune", help="Remove superseded/quarantined runs")
    p_prune.add_argument("rung_dir", help="Path to rung directory")
    p_prune.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete (default is dry-run)",
    )

    args = parser.parse_args()
    handlers = {
        "status": cmd_status,
        "mark-superseded": cmd_mark_superseded,
        "mark-quarantined": cmd_mark_quarantined,
        "mark-canonical": cmd_mark_canonical,
        "list": cmd_list,
        "prune": cmd_prune,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
