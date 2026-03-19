"""Operator CLI — single entrypoint for steward workspace health.

Usage:
    uv run python scripts/internal/ops.py status [--json]
    uv run python scripts/internal/ops.py worktrees [--json]
    uv run python scripts/internal/ops.py events [--type TYPE] [--lane LANE] [--limit N] [--json]
    uv run python scripts/internal/ops.py events drain [--json]
    uv run python scripts/internal/ops.py tick [--json]
    uv run python scripts/internal/ops.py health [--json]
    uv run python scripts/internal/ops.py watchdogs [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _find_repo_root() -> Path:
    """Find the git repository root."""
    p = Path.cwd().resolve()
    while p != p.parent:
        if (p / ".git").exists() or (p / ".git").is_file():
            return p
        p = p.parent
    return Path.cwd()


def cmd_status(args: argparse.Namespace) -> int:
    """Show status across lanes, sessions, and tasks."""
    from bid_euchre.ops.status import (
        aggregate_status,
        format_status_json,
        format_status_text,
    )

    report = aggregate_status(args.runtime_dir)

    if args.json:
        print(json.dumps(format_status_json(report), indent=2))
    else:
        print(format_status_text(report))

    return 0


def cmd_worktrees(args: argparse.Namespace) -> int:
    """Show worktree registry and reconciliation."""
    from bid_euchre.ops.worktrees import (
        list_worktrees_git,
        list_worktrees_registry,
        reconcile,
    )

    registry_dir = args.runtime_dir / "worktree_registry"
    git_wts = list_worktrees_git()
    registry = list_worktrees_registry(registry_dir)
    report = reconcile(git_wts, registry)

    if args.json:
        data = {
            "matched": [
                {
                    "path": wt.path,
                    "branch": wt.branch,
                    "lane_id": entry.get("lane_id", "?"),
                    "class": entry.get("class", "?"),
                }
                for wt, entry in report.matched
            ],
            "unregistered": [
                {"path": wt.path, "branch": wt.branch} for wt in report.unregistered
            ],
            "missing": [
                {
                    "lane_id": e.get("lane_id", "?"),
                    "worktree_path": e.get("worktree_path", "?"),
                }
                for e in report.missing
            ],
            "warnings": report.warnings,
        }
        print(json.dumps(data, indent=2))
    else:
        print("=== Worktree Registry ===")
        print()
        print(f"Registered & matched: {len(report.matched)}")
        for wt, entry in report.matched:
            print(
                f"  {entry.get('lane_id', '?'):15s} "
                f"[{entry.get('class', '?'):10s}] "
                f"{wt.branch}"
            )

        if report.unregistered:
            print(f"\nUnregistered (no registry entry): {len(report.unregistered)}")
            for wt in report.unregistered:
                print(f"  {wt.path} ({wt.branch})")

        if report.missing:
            print(f"\nMissing (registry but no worktree): {len(report.missing)}")
            for entry in report.missing:
                print(
                    f"  {entry.get('lane_id', '?')} → {entry.get('worktree_path', '?')}"
                )

        if report.warnings:
            print(f"\nWarnings: {len(report.warnings)}")
            for w in report.warnings:
                print(f"  ⚠ {w}")

    return 0


def cmd_events(args: argparse.Namespace) -> int:
    """Show recent events."""
    events_dir = args.runtime_dir / "events"

    from bid_euchre.ops.events import read_events

    events = read_events(
        events_dir,
        event_type=getattr(args, "type", None),
        lane_id=getattr(args, "lane", None),
        limit=getattr(args, "limit", 50),
    )

    if args.json:
        print(json.dumps(events, indent=2))
    else:
        if not events:
            print("No events")
            return 0

        print(f"Events: {len(events)} (most recent first)")
        for event in events:
            ts = event.get("timestamp", "?")
            if len(ts) > 19:
                ts = ts[:19]
            etype = event.get("event_type", "?")
            lane = event.get("lane_id", "?")
            source = event.get("source", "?")
            print(f"  [{ts}] {etype:20s} lane={lane:10s} src={source}")

    return 0


def cmd_events_drain(args: argparse.Namespace) -> int:
    """Drain (archive) all events."""
    events_dir = args.runtime_dir / "events"

    from bid_euchre.ops.events import drain_events

    drained = drain_events(events_dir)
    if args.json:
        print(json.dumps({"drained": drained}))
    else:
        print(f"Drained {drained} event(s)")
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    """Run one scheduler cycle."""
    from bid_euchre.ops.scheduler import format_tick_json, format_tick_text, tick

    result = tick(
        runtime_dir=args.runtime_dir,
        plans_dir=args.plans_dir,
        scheduler_dir=args.runtime_dir / "scheduler",
        events_dir=args.runtime_dir / "events",
    )

    if args.json:
        print(json.dumps(format_tick_json(result), indent=2))
    else:
        print(format_tick_text(result))

    # Non-zero exit if critical findings
    if any(f.severity == "critical" for f in result.findings):
        return 1
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Run aggregated health check (status + watchdogs)."""
    from bid_euchre.ops.status import (
        aggregate_status,
        format_status_json,
        format_status_text,
    )
    from bid_euchre.ops.watchdogs import (
        format_watchdog_json,
        format_watchdog_text,
        run_all_watchdogs,
    )

    status = aggregate_status(args.runtime_dir)
    findings = run_all_watchdogs(args.runtime_dir, args.plans_dir)

    if args.json:
        data = {
            "status": format_status_json(status),
            "watchdogs": format_watchdog_json(findings),
            "healthy": not any(f.severity == "critical" for f in findings),
        }
        print(json.dumps(data, indent=2))
    else:
        print(format_status_text(status))
        print()
        print(format_watchdog_text(findings))

    if any(f.severity == "critical" for f in findings):
        return 1
    return 0


def cmd_watchdogs(args: argparse.Namespace) -> int:
    """Run watchdog checks."""
    from bid_euchre.ops.watchdogs import (
        format_watchdog_json,
        format_watchdog_text,
        run_all_watchdogs,
    )

    findings = run_all_watchdogs(args.runtime_dir, args.plans_dir)

    if args.json:
        print(json.dumps(format_watchdog_json(findings), indent=2))
    else:
        print(format_watchdog_text(findings))

    if any(f.severity == "critical" for f in findings):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="ops.py",
        description="Operator CLI for steward workspace health and monitoring",
    )

    # Global options
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=None,
        help="Override runtime directory (default: .claude/runtime)",
    )
    parser.add_argument(
        "--plans-dir",
        type=Path,
        default=None,
        help="Override plans directory (default: plans/)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status
    subparsers.add_parser("status", help="Lane/session/task health summary")

    # worktrees
    subparsers.add_parser("worktrees", help="Worktree registry and reconciliation")

    # events
    events_parser = subparsers.add_parser("events", help="Show recent events")
    events_parser.add_argument(
        "--type", type=str, default=None, help="Filter by event type"
    )
    events_parser.add_argument(
        "--lane", type=str, default=None, help="Filter by lane ID"
    )
    events_parser.add_argument(
        "--limit", type=int, default=50, help="Max events to show"
    )

    # events drain (as a separate top-level subcommand for clarity)
    subparsers.add_parser("drain", help="Drain (archive) all events")

    # tick
    subparsers.add_parser("tick", help="Run one scheduler cycle")

    # health
    subparsers.add_parser("health", help="Aggregated health check")

    # watchdogs
    subparsers.add_parser("watchdogs", help="Run watchdog checks")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    # Resolve directories relative to repo root
    repo_root = _find_repo_root()

    if args.runtime_dir is None:
        args.runtime_dir = repo_root / ".claude" / "runtime"

    if args.plans_dir is None:
        args.plans_dir = repo_root / "plans"

    # Dispatch
    commands = {
        "status": cmd_status,
        "worktrees": cmd_worktrees,
        "events": cmd_events,
        "drain": cmd_events_drain,
        "tick": cmd_tick,
        "health": cmd_health,
        "watchdogs": cmd_watchdogs,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
