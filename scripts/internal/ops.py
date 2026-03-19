"""Operator CLI — single entrypoint for steward workspace health.

Usage:
    uv run python scripts/internal/ops.py status [--json]
    uv run python scripts/internal/ops.py worktrees [--json]
    uv run python scripts/internal/ops.py events [--type TYPE] [--lane LANE] [--limit N] [--json]
    uv run python scripts/internal/ops.py events drain [--json]
    uv run python scripts/internal/ops.py tick [--json]
    uv run python scripts/internal/ops.py health [--json]
    uv run python scripts/internal/ops.py watchdogs [--json]
    uv run python scripts/internal/ops.py reviews [--json]
    uv run python scripts/internal/ops.py ci [--json]
    uv run python scripts/internal/ops.py ci --pr N [--json]
    uv run python scripts/internal/ops.py daemon [--interval N] [--max-ticks N] [--json]
    uv run python scripts/internal/ops.py retry --task TASK_ID [--json]
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
    """Show worktree registry and reconciliation, or dispatch sub-action."""
    # Dispatch to sub-action if present
    wt_action = getattr(args, "worktrees_action", None)
    if wt_action == "prune":
        return cmd_worktrees_prune(args)
    if wt_action == "quarantine":
        return cmd_worktrees_quarantine(args)
    if wt_action == "archive":
        return cmd_worktrees_archive(args)

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


def cmd_worktrees_prune(args: argparse.Namespace) -> int:
    """Prune stale worktrees (dry-run by default)."""
    from bid_euchre.ops.worktrees import prune_worktrees

    execute = getattr(args, "execute", False)
    events_dir = args.runtime_dir / "events"

    results = prune_worktrees(
        args.runtime_dir,
        dry_run=not execute,
        events_dir=events_dir,
    )

    if args.json:
        data = [
            {
                "path": r.path,
                "branch": r.branch,
                "action": r.action,
                "reason": r.reason,
                "dry_run": r.dry_run,
            }
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        mode = "EXECUTE" if execute else "DRY-RUN"
        print(f"=== Worktree Prune ({mode}) ===")
        print()
        if not results:
            print("No cleanup candidates found.")
        else:
            for r in results:
                icon = {"removed": "✗", "quarantined": "⚠", "skipped": "·"}.get(
                    r.action, "?"
                )
                print(f"  {icon} [{r.action:12s}] {r.path}")
                print(f"    {r.reason}")
            print()
            removed = sum(1 for r in results if r.action == "removed")
            quarantined = sum(1 for r in results if r.action == "quarantined")
            skipped = sum(1 for r in results if r.action == "skipped")
            print(
                f"Summary: {removed} removed, {quarantined} quarantined, "
                f"{skipped} skipped"
            )

    return 0


def cmd_worktrees_quarantine(args: argparse.Namespace) -> int:
    """Manually quarantine a worktree."""
    from bid_euchre.ops.worktrees import quarantine_worktree

    wt_path = getattr(args, "path", None)
    if not wt_path:
        print("Error: worktree path required", file=sys.stderr)
        return 1

    reason = getattr(args, "reason", "Manual quarantine")
    events_dir = args.runtime_dir / "events"

    try:
        diff_path = quarantine_worktree(
            wt_path,
            reason,
            args.runtime_dir,
            events_dir=events_dir,
        )
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"path": wt_path, "diff_file": str(diff_path)}))
    else:
        print(f"Quarantined: {wt_path}")
        print(f"Diff saved: {diff_path}")

    return 0


def cmd_worktrees_archive(args: argparse.Namespace) -> int:
    """Archive (remove) a worktree."""
    from bid_euchre.ops.worktrees import archive_worktree

    wt_path = getattr(args, "path", None)
    if not wt_path:
        print("Error: worktree path required", file=sys.stderr)
        return 1

    force = getattr(args, "force", False)
    events_dir = args.runtime_dir / "events"

    try:
        archive_worktree(
            wt_path,
            args.runtime_dir,
            events_dir=events_dir,
            force=force,
        )
    except (OSError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"archived": wt_path}))
    else:
        print(f"Archived: {wt_path}")

    return 0


def cmd_events(args: argparse.Namespace) -> int:
    """Show recent events, or drain if subcommand given."""
    # Dispatch to drain if nested subcommand
    if getattr(args, "events_action", None) == "drain":
        return cmd_events_drain(args)

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


def cmd_recover(args: argparse.Namespace) -> int:
    """Show recovery guidance for active failures."""
    from bid_euchre.ops.recovery import (
        format_recovery_json,
        format_recovery_text,
        get_active_failures,
    )

    events_dir = args.runtime_dir / "events"
    failures = get_active_failures(events_dir)

    if args.json:
        print(json.dumps(format_recovery_json(failures), indent=2))
    else:
        print(format_recovery_text(failures))

    return 0


def cmd_reviews(args: argparse.Namespace) -> int:
    """Show PR review/check outcomes from GitHub."""
    from bid_euchre.ops.reviews import (
        format_reviews_json,
        format_reviews_text,
        get_open_pr_reviews,
        get_pr_review_detail,
    )

    pr_number = getattr(args, "pr", None)

    if pr_number is not None:
        try:
            outcome = get_pr_review_detail(pr_number)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(outcome.to_dict(), indent=2))
        else:
            print(format_reviews_text([outcome]))
        return 0

    outcomes = get_open_pr_reviews()

    if args.json:
        print(json.dumps(format_reviews_json(outcomes), indent=2))
    else:
        print(format_reviews_text(outcomes))

    return 0


def cmd_ci(args: argparse.Namespace) -> int:
    """Show CI status, optionally classify failures for a specific PR."""
    pr_number = getattr(args, "pr", None)

    if pr_number is None:
        print("Error: --pr <number> is required for ci command", file=sys.stderr)
        return 1

    from bid_euchre.ops.ci import format_ci_json, format_ci_text, poll_ci_status

    report = poll_ci_status(pr_number)

    if args.json:
        print(json.dumps(format_ci_json(report), indent=2))
    else:
        print(format_ci_text(report))

    return 1 if report.overall == "failure" else 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Run bounded daemon loop (repeating tick)."""
    from bid_euchre.ops.scheduler import (
        daemon,
        format_daemon_json,
        format_daemon_text,
    )

    interval = getattr(args, "interval", 300)
    max_ticks = getattr(args, "max_ticks", 100)

    result = daemon(
        runtime_dir=args.runtime_dir,
        plans_dir=args.plans_dir,
        scheduler_dir=args.runtime_dir / "scheduler",
        events_dir=args.runtime_dir / "events",
        interval_seconds=interval,
        max_iterations=max_ticks,
    )

    if args.json:
        print(json.dumps(format_daemon_json(result), indent=2))
    else:
        print(format_daemon_text(result))

    if result.critical_findings > 0:
        return 1
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    """Evaluate retry/reroute policy for a task."""
    from bid_euchre.ops.events import read_events
    from bid_euchre.ops.recovery import (
        evaluate_retry_policy,
        format_retry_policy_json,
        format_retry_policy_text,
    )

    task_id = getattr(args, "task", None)
    if not task_id:
        print("Error: --task <task_id> is required", file=sys.stderr)
        return 1

    max_retries = getattr(args, "max_retries", 3)
    lane = getattr(args, "lane", None)

    events_dir = args.runtime_dir / "events"
    events = read_events(events_dir, limit=200)

    policy = evaluate_retry_policy(
        task_id, events, max_retries=max_retries, current_lane=lane
    )

    if args.json:
        print(json.dumps(format_retry_policy_json(policy), indent=2))
    else:
        print(format_retry_policy_text(policy))

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

    # worktrees (with nested prune/quarantine/archive subcommands)
    wt_parser = subparsers.add_parser(
        "worktrees", help="Worktree registry and reconciliation"
    )
    wt_sub = wt_parser.add_subparsers(dest="worktrees_action")

    prune_parser = wt_sub.add_parser(
        "prune", help="Prune stale worktrees (dry-run default)"
    )
    prune_parser.add_argument(
        "--execute", action="store_true", help="Actually remove (default: dry-run)"
    )

    quarantine_parser = wt_sub.add_parser(
        "quarantine", help="Quarantine a dirty worktree"
    )
    quarantine_parser.add_argument("path", type=str, help="Worktree path to quarantine")
    quarantine_parser.add_argument(
        "--reason", type=str, default="Manual quarantine", help="Reason for quarantine"
    )

    archive_parser = wt_sub.add_parser("archive", help="Archive (remove) a worktree")
    archive_parser.add_argument("path", type=str, help="Worktree path to archive")
    archive_parser.add_argument(
        "--force", action="store_true", help="Force removal even if dirty"
    )

    # events (with nested "drain" subcommand)
    events_parser = subparsers.add_parser("events", help="Event log")
    events_parser.add_argument(
        "--type", type=str, default=None, help="Filter by event type"
    )
    events_parser.add_argument(
        "--lane", type=str, default=None, help="Filter by lane ID"
    )
    events_parser.add_argument(
        "--limit", type=int, default=50, help="Max events to show"
    )
    events_sub = events_parser.add_subparsers(dest="events_action")
    events_sub.add_parser("drain", help="Drain (archive) all events")

    # tick
    subparsers.add_parser("tick", help="Run one scheduler cycle")

    # health
    subparsers.add_parser("health", help="Aggregated health check")

    # watchdogs
    subparsers.add_parser("watchdogs", help="Run watchdog checks")

    # recover
    subparsers.add_parser("recover", help="Show recovery guidance for active failures")

    # reviews
    reviews_parser = subparsers.add_parser(
        "reviews", help="PR review/check outcomes from GitHub"
    )
    reviews_parser.add_argument(
        "--pr", type=int, default=None, help="Show detail for a specific PR number"
    )

    # ci
    ci_parser = subparsers.add_parser("ci", help="CI status and failure classification")
    ci_parser.add_argument(
        "--pr", type=int, default=None, help="PR number to check (required)"
    )

    # daemon
    daemon_parser = subparsers.add_parser(
        "daemon", help="Run bounded repeating tick loop"
    )
    daemon_parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconds between ticks (default: 300)",
    )
    daemon_parser.add_argument(
        "--max-ticks",
        type=int,
        default=100,
        help="Maximum number of ticks (default: 100, hard cap: 1000)",
    )

    # retry
    retry_parser = subparsers.add_parser(
        "retry", help="Evaluate retry/reroute policy for a task"
    )
    retry_parser.add_argument(
        "--task", type=str, required=True, help="Task ID to evaluate"
    )
    retry_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries before reroute (default: 3)",
    )
    retry_parser.add_argument(
        "--lane", type=str, default=None, help="Current lane (for reroute target)"
    )

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
        "tick": cmd_tick,
        "health": cmd_health,
        "watchdogs": cmd_watchdogs,
        "recover": cmd_recover,
        "reviews": cmd_reviews,
        "ci": cmd_ci,
        "daemon": cmd_daemon,
        "retry": cmd_retry,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
