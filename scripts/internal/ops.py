"""Operator CLI — single entrypoint for steward workspace health.

Usage:
    uv run python scripts/internal/ops.py dashboard [--watch] [--interval N] [--no-probe] [--json]
    uv run python scripts/internal/ops.py status [--json]
    uv run python scripts/internal/ops.py worktrees [--json]
    uv run python scripts/internal/ops.py events [--type TYPE] [--lane LANE] [--limit N] [--json]
    uv run python scripts/internal/ops.py events drain [--json]
    uv run python scripts/internal/ops.py tick [--json]
    uv run python scripts/internal/ops.py health [--json]
    uv run python scripts/internal/ops.py watchdogs [--json]
    uv run python scripts/internal/ops.py reviews [--json]
    uv run python scripts/internal/ops.py [--json] queue [--pr N]
    uv run python scripts/internal/ops.py comments --pr N [--ingest] [--json]
    uv run python scripts/internal/ops.py ci [--json]
    uv run python scripts/internal/ops.py ci --pr N [--json]
    uv run python scripts/internal/ops.py daemon [--interval N] [--max-ticks N] [--json]
    uv run python scripts/internal/ops.py retry --task TASK_ID [--json]
    uv run python scripts/internal/ops.py index [--rebuild] [--json]
    uv run python scripts/internal/ops.py query --text TEXT [--type TYPE] [--limit N] [--json]
    uv run python scripts/internal/ops.py memory [--category CAT] [--json]
    uv run python scripts/internal/ops.py compact [--json]
    uv run python scripts/internal/ops.py scope show --task TASK_ID [--json]
    uv run python scripts/internal/ops.py scope set --task TASK_ID --declared PATTERN [PATTERN ...]
    uv run python scripts/internal/ops.py scope touch --task TASK_ID --file PATH [PATH ...]
    uv run python scripts/internal/ops.py snapshot create --worktree PATH --reason TEXT [--lane LANE] [--task TASK] [--json]
    uv run python scripts/internal/ops.py snapshot list [--worktree PATH] [--limit N] [--json]
    uv run python scripts/internal/ops.py snapshot rollback SNAPSHOT_ID [--json]
    uv run python scripts/internal/ops.py snapshot prune [--max-per-worktree N] [--max-age-hours H] [--json]
    uv run python scripts/internal/ops.py skills [--status STATUS] [--json]
    uv run python scripts/internal/ops.py skills propose --name NAME --description DESC --content-file PATH --source-workflow TEXT --proposed-by LANE [--json]
    uv run python scripts/internal/ops.py skills review CANDIDATE_ID --approve|--reject --reviewed-by LANE [--notes TEXT] [--json]
    uv run python scripts/internal/ops.py skills promote CANDIDATE_ID [--json]
    uv run python scripts/internal/ops.py skills disable NAME [--reason TEXT] [--disabled-by LANE] [--json]
    uv run python scripts/internal/ops.py repairs [--json]
    uv run python scripts/internal/ops.py task list [--status STATUS] [--owner LANE] [--domain DOMAIN] [--json]
    uv run python scripts/internal/ops.py task show PACKET_ID [--json]
    uv run python scripts/internal/ops.py task approve PACKET_ID [--json]
    uv run python scripts/internal/ops.py task dispatch PACKET_ID LANE_ID [--approve] [--json]
    uv run python scripts/internal/ops.py task accept PACKET_ID --lane LANE [--json]
    uv run python scripts/internal/ops.py inbox [--lane LANE] [--status STATUS] [--type TYPE] [--thread THREAD] [--prioritized] [--json]
    uv run python scripts/internal/ops.py inbox stats [--json]
    uv run python scripts/internal/ops.py inbox ack MSG_ID --lane LANE [--json]
    uv run python scripts/internal/ops.py message show MSG_ID [--json]
    uv run python scripts/internal/ops.py message send --from LANE --to LANE --type TYPE --summary TEXT [--task-id ID] [--thread ID] [--json]
    uv run python scripts/internal/ops.py supervisor [--json] [--save] [--diff SNAPSHOT_PATH]
    uv run python scripts/internal/ops.py monitor [--skip-pr-check] [--no-notify] [--json]
    uv run python scripts/internal/ops.py review-check [--limit N] [--no-notify] [--json]
    uv run python scripts/internal/ops.py workers [--json]
    uv run python scripts/internal/ops.py workers wake LANE_ID [--json]
    uv run python scripts/internal/ops.py workers park LANE_ID [--json]
    uv run python scripts/internal/ops.py workers retire LANE_ID [--json]
    uv run python scripts/internal/ops.py workers dispatch PACKET_ID LANE_ID [--json]
    uv run python scripts/internal/ops.py workers maintain [--dry-run] [--json]
    uv run python scripts/internal/ops.py usage import [--usage-dir DIR] [--output-dir DIR] [--json]
    uv run python scripts/internal/ops.py usage attribute [--output-dir DIR] [--json]
    uv run python scripts/internal/ops.py usage summary [--output-dir DIR] [--json]
    uv run python scripts/internal/ops.py usage lanes [--output-dir DIR] [--json]
    uv run python scripts/internal/ops.py usage throughput [--output-dir DIR] [--json]
    uv run python scripts/internal/ops.py usage anti-patterns [--output-dir DIR] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from _repo_utils import find_repo_root

if TYPE_CHECKING:
    from bid_euchre.ops.recovery import RetryPolicy


# ---------------------------------------------------------------------------
# Filesystem boundary enforcement
# ---------------------------------------------------------------------------


def _check_boundary(
    path: str | Path,
    args: argparse.Namespace,
    *,
    label: str = "path",
) -> int | None:
    """Validate that *path* is within the repo boundary.

    Returns ``None`` if the path is allowed, or ``1`` (error exit code) if it
    is outside the boundary. Emits an audit event on violation.

    This is a thin CLI adapter around
    :func:`bid_euchre.ops.fs_boundary.require_in_boundary`.
    """
    from bid_euchre.ops.fs_boundary import (
        BoundaryViolationError,
        get_repo_boundaries,
        require_in_boundary,
    )

    boundaries = get_repo_boundaries(repo_root=args.repo_root)
    events_dir = args.runtime_dir / "events"

    try:
        require_in_boundary(
            path,
            repo_root=boundaries["repo_root"],
            worktree_paths=boundaries["worktree_paths"],
            runtime_dirs=boundaries["runtime_dirs"],
            events_dir=events_dir,
            source="ops.cli",
        )
    except BoundaryViolationError:
        print(
            f"Error: {label} is outside the repo boundary: {path}",
            file=sys.stderr,
        )
        return 1

    return None


def cmd_status(args: argparse.Namespace) -> int:
    """Show status across lanes, sessions, and tasks."""
    from bid_euchre.ops.status import (
        aggregate_status,
        format_status_json,
        format_status_text,
    )

    check_worktree = not getattr(args, "no_probe", False)
    report = aggregate_status(args.runtime_dir, check_worktree=check_worktree)

    if args.json:
        print(json.dumps(format_status_json(report), indent=2))
    else:
        print(format_status_text(report))

    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Dashboard-first steward supervision surface."""
    import time

    dashboard_action = getattr(args, "dashboard_action", None)

    if dashboard_action == "set-visibility":
        from bid_euchre.ops.dashboard import set_lane_visibility

        lane_id = args.lane
        visibility = args.visibility
        ok = set_lane_visibility(lane_id, visibility, args.runtime_dir)
        if ok:
            print(f"Set {lane_id} visibility to {visibility}")
            return 0
        else:
            print(f"Lane {lane_id!r} not found in registry", file=sys.stderr)
            return 1

    from bid_euchre.ops.dashboard import (
        build_dashboard_view,
        format_dashboard_json,
        format_dashboard_text,
    )

    watch = getattr(args, "watch", False)
    interval = getattr(args, "interval", 30)

    try:
        while True:
            view = build_dashboard_view(
                args.runtime_dir,
                check_worktree=not getattr(args, "no_probe", False),
            )

            if args.json:
                # In watch mode, emit compact NDJSON (one JSON object per line)
                # so the output stream stays machine-parseable.
                # In single-shot mode, emit indented JSON for readability.
                if watch:
                    print(json.dumps(format_dashboard_json(view)))
                else:
                    print(json.dumps(format_dashboard_json(view), indent=2))
            else:
                if watch:
                    # Clear screen for clean refresh (text mode only —
                    # ANSI escapes would corrupt JSON output)
                    print("\033[2J\033[H", end="", flush=True)
                print(format_dashboard_text(view))

            if not watch:
                break

            if not args.json:
                print(f"\n--- Refreshing every {interval}s (Ctrl+C to stop) ---")
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        if watch:
            print("\nWatch stopped.", file=sys.stderr)
        return 0

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
    if wt_action == "register-all":
        return cmd_worktrees_register_all(args)

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
                    "visibility": entry.get("visibility"),
                    "session_handle": entry.get("session_handle"),
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
        _VIS_BADGES = {"foreground": "fg", "background": "bg"}

        print("=== Worktree Registry ===")
        print()
        print(f"Registered & matched: {len(report.matched)}")
        for wt, entry in report.matched:
            vis = entry.get("visibility")
            vis_badge = _VIS_BADGES.get(vis, "\u2014") if vis else "\u2014"
            print(
                f"  {entry.get('lane_id', '?'):15s} "
                f"[{entry.get('class', '?'):10s}] "
                f"[{vis_badge:3s}] "
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


def cmd_worktrees_register_all(args: argparse.Namespace) -> int:
    """Scan git worktrees and create/update registry entries for steward lanes."""
    from bid_euchre.ops.worktrees import register_all_worktrees

    registry_dir = args.runtime_dir / "worktree_registry"
    results = register_all_worktrees(registry_dir)

    if args.json:
        data = [
            {
                "lane_id": r.lane_id,
                "worktree_path": r.worktree_path,
                "action": r.action,
                "reason": r.reason,
            }
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        created = [r for r in results if r.action == "created"]
        updated = [r for r in results if r.action == "updated"]
        skipped = [r for r in results if r.action == "skipped"]

        print(
            f"Registered {len(created)} new, updated {len(updated)}, skipped {len(skipped)}"
        )
        print()

        if created:
            print("Created:")
            for r in created:
                print(f"  {r.lane_id:20s} {r.worktree_path}")

        if updated:
            print("Updated:")
            for r in updated:
                print(f"  {r.lane_id:20s} {r.reason}")

        if skipped:
            print(f"\nSkipped ({len(skipped)}):")
            for r in skipped:
                print(f"  {r.lane_id:20s} {r.reason}")

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

    # Boundary check: reject external paths
    boundary_rc = _check_boundary(wt_path, args, label="worktree path")
    if boundary_rc is not None:
        return boundary_rc

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

    # Boundary check: reject external paths
    boundary_rc = _check_boundary(wt_path, args, label="worktree path")
    if boundary_rc is not None:
        return boundary_rc

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

    check_worktree = not getattr(args, "no_probe", False)
    status = aggregate_status(args.runtime_dir, check_worktree=check_worktree)
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


def cmd_comments(args: argparse.Namespace) -> int:
    """Show or ingest PR comment overlays."""
    from bid_euchre.ops.reviews import (
        format_comment_overlays_json,
        format_comment_overlays_text,
        get_pr_comment_overlay,
    )

    pr_number = getattr(args, "pr", None)
    if pr_number is None:
        print("Error: --pr <number> is required for comments command", file=sys.stderr)
        return 1

    ingest = getattr(args, "ingest", False)

    overlay = get_pr_comment_overlay(pr_number)

    if ingest and overlay.total_comments > 0:
        # Write comment sidecar JSONL for index ingestion
        pr_comments_dir = args.runtime_dir / "pr_comments"
        pr_comments_dir.mkdir(parents=True, exist_ok=True)
        sidecar_file = pr_comments_dir / f"pr_{pr_number}.jsonl"
        with open(sidecar_file, "w") as f:
            for c in overlay.comments:
                record = {**c, "pr_number": pr_number}
                f.write(json.dumps(record, sort_keys=True) + "\n")

        # Emit event
        from bid_euchre.ops.events import append_event

        append_event(
            event_type="pr_comment_ingested",
            source="ops.comments",
            lane_id="operator",
            payload={
                "pr_number": pr_number,
                "total_comments": overlay.total_comments,
                "trusted_bot_comments": overlay.trusted_bot_comments,
                "sidecar_file": str(sidecar_file),
            },
            events_dir=args.runtime_dir / "events",
        )

    if args.json:
        print(json.dumps(format_comment_overlays_json([overlay]), indent=2))
    else:
        print(format_comment_overlays_text([overlay]))

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
    if result.stopped_reason == "error" or result.errors:
        return 1
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    """Evaluate retry/reroute policy for a task and optionally emit events."""
    # Dispatch to summary subcommand if requested
    retry_action = getattr(args, "retry_action", None)
    if retry_action == "summary":
        return cmd_retry_summary(args)

    from bid_euchre.ops.events import read_events
    from bid_euchre.ops.recovery import (
        evaluate_retry_policy,
        format_retry_policy_json,
        format_retry_policy_text,
    )

    task_id = getattr(args, "task", None)
    if not task_id:
        print(
            "Error: --task <task_id> is required (or use `retry summary`)",
            file=sys.stderr,
        )
        return 1

    max_retries = getattr(args, "max_retries", 3)
    lane = getattr(args, "lane", None)
    emit = getattr(args, "emit", False)

    events_dir = args.runtime_dir / "events"
    events = read_events(events_dir, limit=200)

    policy = evaluate_retry_policy(
        task_id, events, max_retries=max_retries, current_lane=lane
    )

    # Emit durable event for the policy decision
    if emit:
        _emit_retry_event(policy, lane or "unknown", events_dir)

    if args.json:
        print(json.dumps(format_retry_policy_json(policy), indent=2))
    else:
        print(format_retry_policy_text(policy))

    return 0


def _emit_retry_event(
    policy: RetryPolicy,
    lane_id: str,
    events_dir: Path,
) -> None:
    """Emit a durable event based on the retry policy decision.

    Delegates to ``recovery.emit_retry_event()`` which is the canonical
    producer for ``retry_attempted`` and ``task_rerouted`` events (#930).
    This wrapper adds error handling for CLI context.
    """
    from bid_euchre.ops.recovery import emit_retry_event

    try:
        emit_retry_event(policy, lane_id, events_dir)
    except Exception as e:
        print(f"Warning: failed to emit retry event: {e}", file=sys.stderr)


def cmd_index(args: argparse.Namespace) -> int:
    """Build or show audit index."""
    from bid_euchre.ops.index import (
        build_index,
        format_stats_json,
        format_stats_text,
        get_stats,
    )

    index_dir = args.runtime_dir / "audit_index"
    rebuild = getattr(args, "rebuild", False)

    result = build_index(
        index_dir,
        runtime_dir=args.runtime_dir,
        plans_dir=args.plans_dir,
        repo_root=getattr(args, "repo_root", None),
        full_rebuild=rebuild,
    )

    stats = get_stats(index_dir)

    if args.json:
        data = {
            "build": {
                "sources_indexed": result.sources_indexed,
                "entries_indexed": result.entries_indexed,
                "errors": result.errors,
                "duration_seconds": round(result.duration_seconds, 3),
            },
            "stats": format_stats_json(stats),
        }
        print(json.dumps(data, indent=2))
    else:
        print(format_stats_text(stats))
        print()
        mode = "Rebuilt" if rebuild else "Updated"
        print(
            f"{mode}: {result.sources_indexed} sources, "
            f"{result.entries_indexed} entries "
            f"({result.duration_seconds:.3f}s)"
        )
        if result.errors:
            print(f"\nErrors: {len(result.errors)}")
            for err in result.errors:
                print(f"  - {err}")

    return 1 if result.errors else 0


def cmd_query(args: argparse.Namespace) -> int:
    """Query the audit index."""
    search_text = getattr(args, "text", None)
    entry_type = getattr(args, "type", None)
    limit = getattr(args, "limit", 20)
    recent = getattr(args, "recent", False)

    index_dir = args.runtime_dir / "audit_index"

    if recent or not search_text:
        from bid_euchre.ops.index import (
            format_query_json,
            format_query_text,
            query_recent,
        )

        response = query_recent(index_dir, entry_type=entry_type, limit=limit)
    else:
        from bid_euchre.ops.index import (
            format_query_json,
            format_query_text,
            query,
        )

        response = query(index_dir, search_text, entry_type=entry_type, limit=limit)

    if args.json:
        print(json.dumps(format_query_json(response), indent=2))
    else:
        print(format_query_text(response))

    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    """Show or manage curated memory."""
    from bid_euchre.ops.memory import (
        format_memory_json,
        format_memory_text,
        list_entries,
    )

    memory_dir = args.runtime_dir / "curated_memory"
    category = getattr(args, "category", None)
    tag = getattr(args, "tag", None)

    entries = list_entries(memory_dir, category=category, tag=tag)

    if args.json:
        print(json.dumps(format_memory_json(entries), indent=2))
    else:
        print(format_memory_text(entries))

    return 0


def cmd_compact(args: argparse.Namespace) -> int:
    """List archived sessions or show compact info."""
    from bid_euchre.ops.compaction import (
        format_archives_json,
        format_archives_text,
        list_archives,
    )

    archive_dir = args.runtime_dir / "session_archive"
    archives = list_archives(archive_dir)

    if args.json:
        print(json.dumps(format_archives_json(archives), indent=2))
    else:
        print(format_archives_text(archives))

    return 0


def cmd_scope(args: argparse.Namespace) -> int:
    """Manage task scope fields (declared_files, touched_files)."""
    scope_action = getattr(args, "scope_action", None)

    if scope_action == "set":
        return cmd_scope_set(args)
    if scope_action == "touch":
        return cmd_scope_touch(args)
    if scope_action == "show":
        return cmd_scope_show(args)
    if scope_action == "check":
        return cmd_scope_check(args)

    # No subcommand — show help
    print(
        "Usage: ops.py scope {show|set|touch|check} --task TASK_ID ...",
        file=sys.stderr,
    )
    return 1


def cmd_scope_set(args: argparse.Namespace) -> int:
    """Set declared_files for a task's scope."""
    from bid_euchre.ops.status import update_task_scope

    task_id = getattr(args, "task", None)
    declared = getattr(args, "declared", None)

    if not task_id:
        print("Error: --task required", file=sys.stderr)
        return 1
    if not declared:
        print("Error: --declared required", file=sys.stderr)
        return 1

    try:
        data = update_task_scope(
            task_id, declared_files=declared, runtime_dir=args.runtime_dir
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    scope = data.get("scope", {})
    if args.json:
        print(json.dumps(scope, indent=2))
    else:
        print(f"Scope updated for task {task_id}")
        print(f"  declared_files: {scope.get('declared_files', [])}")

    return 0


def cmd_scope_touch(args: argparse.Namespace) -> int:
    """Record touched files for a task's scope."""
    from bid_euchre.ops.status import update_task_scope

    task_id = getattr(args, "task", None)
    files = getattr(args, "file", None)

    if not task_id:
        print("Error: --task required", file=sys.stderr)
        return 1
    if not files:
        print("Error: --file required", file=sys.stderr)
        return 1

    try:
        data = update_task_scope(
            task_id,
            touched_files=files,
            append_touched=True,
            runtime_dir=args.runtime_dir,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    scope = data.get("scope", {})
    if args.json:
        print(json.dumps(scope, indent=2))
    else:
        touched = scope.get("touched_files", [])
        print(f"Recorded {len(files)} file(s) for task {task_id}")
        print(f"  touched_files ({len(touched)} total): {touched}")

    return 0


def cmd_scope_show(args: argparse.Namespace) -> int:
    """Show current scope for a task."""
    from bid_euchre.ops.status import get_task_scope

    task_id = getattr(args, "task", None)
    if not task_id:
        print("Error: --task required", file=sys.stderr)
        return 1

    try:
        scope = get_task_scope(task_id, runtime_dir=args.runtime_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(scope, indent=2))
    else:
        declared = scope.get("declared_files", [])
        touched = scope.get("touched_files", [])
        print(f"Scope for task {task_id}:")
        print(f"  declared_files ({len(declared)}):")
        for p in declared:
            print(f"    - {p}")
        print(f"  touched_files ({len(touched)}):")
        for p in touched:
            print(f"    - {p}")

    return 0


def cmd_scope_check(args: argparse.Namespace) -> int:
    """Check scope drift for a task (declared vs touched files)."""
    from bid_euchre.ops.scope import (
        check_scope_drift,
        emit_scope_drift_event,
        format_scope_drift_json,
        format_scope_drift_text,
    )

    task_id = getattr(args, "task", None)
    if not task_id:
        print("Error: --task required", file=sys.stderr)
        return 1

    emit = getattr(args, "emit", False)

    try:
        report = check_scope_drift(task_id, runtime_dir=args.runtime_dir)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if emit and report.has_drift:
        lane = getattr(args, "lane", None) or "unknown"
        events_dir = args.runtime_dir / "events"
        try:
            emit_scope_drift_event(report, lane, events_dir)
        except Exception as e:
            print(f"Warning: failed to emit scope event: {e}", file=sys.stderr)

    if args.json:
        print(json.dumps(format_scope_drift_json(report), indent=2))
    else:
        print(format_scope_drift_text(report))

    return 1 if report.has_drift else 0


def cmd_retry_summary(args: argparse.Namespace) -> int:
    """Show retry follow-through summary across all tasks."""
    from bid_euchre.ops.events import read_events
    from bid_euchre.ops.retries import (
        format_retry_summary_json,
        format_retry_summary_text,
        get_retry_summary,
    )

    events_dir = args.runtime_dir / "events"
    events = read_events(events_dir, limit=500)
    summary = get_retry_summary(events)

    if args.json:
        print(json.dumps(format_retry_summary_json(summary), indent=2))
    else:
        print(format_retry_summary_text(summary))

    return 1 if summary.dropped_count > 0 else 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Dispatch snapshot subcommands."""
    snap_action = getattr(args, "snapshot_action", None)
    if snap_action == "create":
        return cmd_snapshot_create(args)
    if snap_action == "list":
        return cmd_snapshot_list(args)
    if snap_action == "rollback":
        return cmd_snapshot_rollback(args)
    if snap_action == "prune":
        return cmd_snapshot_prune(args)

    print(
        "Usage: ops.py snapshot {create|list|rollback|prune} ...",
        file=sys.stderr,
    )
    return 1


def cmd_snapshot_create(args: argparse.Namespace) -> int:
    """Create a shadow snapshot."""
    from bid_euchre.ops.snapshots import (
        create_snapshot,
        format_snapshots_json,
        format_snapshots_text,
    )

    worktree = getattr(args, "worktree", None)
    reason = getattr(args, "reason", "Manual snapshot")
    lane = getattr(args, "lane", None)
    task = getattr(args, "task", None)
    snapshots_dir = args.runtime_dir / "snapshots"
    events_dir = args.runtime_dir / "events"

    if not worktree:
        print("Error: --worktree required", file=sys.stderr)
        return 1

    # Boundary check: reject external paths
    boundary_rc = _check_boundary(worktree, args, label="--worktree")
    if boundary_rc is not None:
        return boundary_rc

    try:
        record = create_snapshot(
            worktree,
            reason,
            snapshots_dir,
            lane_id=lane,
            task_id=task,
            events_dir=events_dir,
        )
    except (FileNotFoundError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(format_snapshots_json([record])[0], indent=2))
    else:
        print(format_snapshots_text([record]))

    return 0


def cmd_snapshot_list(args: argparse.Namespace) -> int:
    """List shadow snapshots."""
    from bid_euchre.ops.snapshots import (
        format_snapshots_json,
        format_snapshots_text,
        list_snapshots,
    )

    snapshots_dir = args.runtime_dir / "snapshots"
    worktree = getattr(args, "worktree", None)
    limit = getattr(args, "limit", 20)

    records = list_snapshots(snapshots_dir, worktree_path=worktree, limit=limit)

    if args.json:
        print(json.dumps(format_snapshots_json(records), indent=2))
    else:
        print(format_snapshots_text(records))

    return 0


def cmd_snapshot_rollback(args: argparse.Namespace) -> int:
    """Roll back to a shadow snapshot."""
    from bid_euchre.ops.snapshots import (
        format_rollback_json,
        format_rollback_text,
        rollback_snapshot,
    )

    snapshot_id = getattr(args, "snapshot_id", None)
    if not snapshot_id:
        print("Error: snapshot ID required", file=sys.stderr)
        return 1

    snapshots_dir = args.runtime_dir / "snapshots"
    events_dir = args.runtime_dir / "events"

    try:
        result = rollback_snapshot(
            snapshot_id,
            snapshots_dir,
            events_dir=events_dir,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(format_rollback_json(result), indent=2))
    else:
        print(format_rollback_text(result))

    return 0 if result.success else 1


def cmd_snapshot_prune(args: argparse.Namespace) -> int:
    """Prune old shadow snapshots."""
    from bid_euchre.ops.snapshots import (
        format_prune_json,
        format_prune_text,
        prune_snapshots,
    )

    snapshots_dir = args.runtime_dir / "snapshots"
    max_per_worktree = getattr(args, "max_per_worktree", 20)
    max_age_hours = getattr(args, "max_age_hours", 168.0)

    pruned = prune_snapshots(
        snapshots_dir,
        max_per_worktree=max_per_worktree,
        max_age_hours=max_age_hours,
    )

    if args.json:
        print(json.dumps(format_prune_json(pruned), indent=2))
    else:
        print(format_prune_text(pruned))

    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    """Dispatch skill promotion subcommands."""
    action = getattr(args, "skills_action", None)
    if action == "propose":
        return cmd_skills_propose(args)
    if action == "review":
        return cmd_skills_review(args)
    if action == "promote":
        return cmd_skills_promote(args)
    if action == "disable":
        return cmd_skills_disable(args)
    # Default: list candidates
    return cmd_skills_list(args)


def cmd_skills_list(args: argparse.Namespace) -> int:
    """List skill candidates."""
    from bid_euchre.ops.skill_promotion import (
        format_candidates_json,
        format_candidates_text,
        list_candidates,
    )

    candidates_dir = args.runtime_dir / "skill_candidates"
    status_filter = getattr(args, "status", None)
    candidates = list_candidates(
        status_filter=status_filter, candidates_dir=candidates_dir
    )

    if args.json:
        print(json.dumps(format_candidates_json(candidates), indent=2))
    else:
        print(format_candidates_text(candidates))

    return 0


def cmd_skills_propose(args: argparse.Namespace) -> int:
    """Propose a new skill candidate."""
    from bid_euchre.ops.skill_promotion import propose_skill

    content_file = Path(args.content_file)

    # Boundary check: reject external content files
    boundary_rc = _check_boundary(content_file, args, label="--content-file")
    if boundary_rc is not None:
        return boundary_rc

    if not content_file.exists():
        print(f"Error: content file not found: {content_file}", file=sys.stderr)
        return 1

    content = content_file.read_text(encoding="utf-8")
    candidates_dir = args.runtime_dir / "skill_candidates"

    try:
        candidate = propose_skill(
            name=args.name,
            description=args.description,
            content=content,
            source_workflow=args.source_workflow,
            proposed_by=args.proposed_by,
            candidates_dir=candidates_dir,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(candidate.to_dict(), indent=2))
    else:
        safety_note = ""
        if candidate.safety_scan_outcome == "reject":
            safety_note = " ⚠ SAFETY REJECTED — fix content before promotion"
        elif candidate.safety_scan_outcome == "warn":
            safety_note = " ⚠ safety warnings present"
        print(
            f"Proposed skill '{candidate.name}' "
            f"(id={candidate.candidate_id}){safety_note}"
        )

    return 0


def cmd_skills_review(args: argparse.Namespace) -> int:
    """Review (approve/reject) a skill candidate."""
    from bid_euchre.ops.skill_promotion import review_skill

    candidates_dir = args.runtime_dir / "skill_candidates"
    approve = args.approve  # True if --approve, False if --reject

    try:
        candidate = review_skill(
            args.candidate_id,
            approve=approve,
            reviewed_by=args.reviewed_by,
            review_notes=getattr(args, "notes", "") or "",
            candidates_dir=candidates_dir,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(candidate.to_dict(), indent=2))
    else:
        print(f"Skill '{candidate.name}' → {candidate.status}")

    return 0


def cmd_skills_promote(args: argparse.Namespace) -> int:
    """Promote an approved skill candidate."""
    from bid_euchre.ops.skill_promotion import promote_skill

    candidates_dir = args.runtime_dir / "skill_candidates"
    skills_dir = args.repo_root / ".claude" / "skills"
    events_dir = args.runtime_dir / "events"

    try:
        candidate, skill_path = promote_skill(
            args.candidate_id,
            candidates_dir=candidates_dir,
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {"candidate": candidate.to_dict(), "skill_path": str(skill_path)},
                indent=2,
            )
        )
    else:
        print(f"Promoted skill '{candidate.name}' → {skill_path}")

    return 0


def cmd_skills_disable(args: argparse.Namespace) -> int:
    """Disable a promoted skill."""
    from bid_euchre.ops.skill_promotion import disable_skill

    skills_dir = args.repo_root / ".claude" / "skills"
    events_dir = args.runtime_dir / "events"

    try:
        disabled_path = disable_skill(
            args.name,
            reason=getattr(args, "reason", "") or "",
            disabled_by=getattr(args, "disabled_by", "operator") or "operator",
            skills_dir=skills_dir,
            events_dir=events_dir,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"disabled_path": str(disabled_path)}, indent=2))
    else:
        print(f"Disabled skill → {disabled_path}")

    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    """Show shared review queue state (request + verdict packets).

    Uses the canonical shared queue root (derived from git common dir)
    so that all worktrees see the same queue.  When ``--runtime-dir`` is
    explicitly provided and contains a ``review_queue/`` subdirectory,
    that override takes precedence (useful for debug/sandbox workflows).
    """
    from bid_euchre.ops.review_queue import shared_queue_root
    from bid_euchre.ops.reviews import (
        format_queue_json,
        format_queue_text,
        get_queue_entries,
        get_queue_entry,
    )

    # Respect explicit --runtime-dir override for debug/sandbox (#1196).
    local_queue = args.runtime_dir / "review_queue"
    if getattr(args, "_runtime_dir_explicit", False) and local_queue.is_dir():
        queue_dir = local_queue
    else:
        queue_dir = shared_queue_root()
    pr_number = getattr(args, "pr", None)

    if pr_number is not None:
        entry = get_queue_entry(pr_number, queue_dir)
        if args.json:
            print(json.dumps(entry.to_dict(), indent=2))
        else:
            print(format_queue_text([entry]))
        return 0

    entries = get_queue_entries(queue_dir)

    if args.json:
        print(json.dumps(format_queue_json(entries), indent=2))
    else:
        print(format_queue_text(entries))

    return 0


def cmd_repairs(args: argparse.Namespace) -> int:
    """Show the post-merge repair queue (eligible issues for autonomous fix)."""
    from bid_euchre.ops.repairs import build_repair_queue

    try:
        queue = build_repair_queue()
    except RuntimeError as exc:
        print(f"Error querying repair queue: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(queue.to_dict(), indent=2))
    else:
        print(queue.format_text())

    return 0


def cmd_task(args: argparse.Namespace) -> int:
    """Orchestrator task queue inspection (Platform-2)."""
    from bid_euchre.ops.task_queue import (
        complete_packet,
        create_packet,
        create_result,
        list_packets,
        load_ack,
        load_packet,
        load_result,
        save_packet,
        transition_status,
    )

    task_queue_root = args.runtime_dir / "task_queue"

    action = getattr(args, "task_action", None)

    if action == "list":
        packets = list_packets(
            task_queue_root,
            status_filter=args.status,
            owner_filter=args.owner,
            domain_filter=getattr(args, "domain", None),
        )
        if args.json:
            from dataclasses import asdict

            print(json.dumps([asdict(p) for p in packets], indent=2, default=str))
        else:
            if not packets:
                print("No active task packets.")
            else:
                print(f"Task Queue: {len(packets)} packet(s)")
                print()
                for pkt in packets:
                    owner_str = pkt.owner or "(unassigned)"
                    print(
                        f"  {pkt.packet_id}  [{pkt.status:11s}]  "
                        f"{pkt.priority:6s}  {owner_str:15s}  {pkt.title}"
                    )
        return 0

    elif action == "show":
        pkt = load_packet(args.packet_id, task_queue_root)
        if pkt is None:
            print(f"Packet {args.packet_id!r} not found.", file=sys.stderr)
            return 1

        ack = load_ack(args.packet_id, task_queue_root)
        result = load_result(args.packet_id, task_queue_root)

        if args.json:
            from dataclasses import asdict

            data: dict = {"packet": asdict(pkt)}
            if ack:
                data["ack"] = asdict(ack)
            if result:
                data["result"] = asdict(result)
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"Packet: {pkt.packet_id}")
            print(f"  Title:       {pkt.title}")
            print(f"  Status:      {pkt.status}")
            print(f"  Owner:       {pkt.owner or '(unassigned)'}")
            print(f"  Priority:    {pkt.priority}")
            if pkt.domain:
                print(f"  Domain:      {pkt.domain}")
            print(f"  Created by:  {pkt.created_by}")
            print(f"  Created at:  {pkt.created_at}")
            print(f"  Description: {pkt.description}")
            if pkt.scope_declared:
                print(f"  Scope:       {', '.join(pkt.scope_declared)}")
            if pkt.validation:
                print(f"  Validation:  {', '.join(pkt.validation)}")
            if pkt.metadata:
                print(f"  Metadata:    {pkt.metadata}")
            if ack:
                print()
                print(f"  Ack: {ack.action} by {ack.acked_by} at {ack.acked_at}")
                if ack.edited_fields:
                    print(f"    Edits: {ack.edited_fields}")
                if ack.redirect_to:
                    print(f"    Redirect to: {ack.redirect_to}")
            if result:
                print()
                print(
                    f"  Result: {result.status} by {result.completed_by} "
                    f"at {result.completed_at}"
                )
                print(f"    Summary: {result.summary}")
                if result.pr_number:
                    print(f"    PR: #{result.pr_number}")
        return 0

    elif action == "create":
        pkt = create_packet(
            title=args.title,
            description=args.description or "",
            owner=args.owner,
            priority=args.priority,
            domain=getattr(args, "domain", None),
            scope_declared=args.scope_declared,
            validation=args.validation,
        )
        save_packet(pkt, task_queue_root)
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(pkt), indent=2, default=str))
        else:
            print(f"Created task packet: {pkt.packet_id}")
            print(f"  Title:    {pkt.title}")
            print(f"  Owner:    {pkt.owner or '(unassigned)'}")
            print(f"  Priority: {pkt.priority}")
            if pkt.domain:
                print(f"  Domain:   {pkt.domain}")
            if pkt.scope_declared:
                print(f"  Scope:    {', '.join(pkt.scope_declared)}")
            if pkt.validation:
                print(f"  Validation: {', '.join(pkt.validation)}")
        return 0

    elif action == "approve":
        updated = transition_status(args.packet_id, "approved", task_queue_root)
        if updated is None:
            print(f"Packet {args.packet_id!r} not found.", file=sys.stderr)
            return 1
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(updated), indent=2, default=str))
        else:
            print(f"Approved: {updated.packet_id}")
            print(f"  Status: {updated.status}")
        return 0

    elif action == "dispatch":
        from bid_euchre.ops.worker_pool import (
            dispatch_to_worker,
            format_action_text,
        )

        packet_id = args.packet_id
        lane_id = args.lane_id

        # Optional --approve: transition to approved first if needed
        if getattr(args, "auto_approve", False):
            pkt = load_packet(packet_id, task_queue_root)
            if pkt is None:
                print(f"Packet {packet_id!r} not found.", file=sys.stderr)
                return 1
            if pkt.status in ("pending", "previewing"):
                approved = transition_status(packet_id, "approved", task_queue_root)
                if approved is None:
                    print(
                        f"Failed to approve packet {packet_id!r}.",
                        file=sys.stderr,
                    )
                    return 1

        do_reset = getattr(args, "reset", False)
        no_auto_refresh = getattr(args, "no_auto_refresh", False)
        result = dispatch_to_worker(
            packet_id,
            lane_id,
            runtime_dir=args.runtime_dir,
            reset=do_reset,
            no_auto_refresh=no_auto_refresh,
        )
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2))
        else:
            print(format_action_text(result))
            if result.executed:
                if do_reset:
                    print(f"\nDispatched {packet_id} -> {lane_id} (with reset)")
                else:
                    print(f"\nDispatched {packet_id} -> {lane_id}")
                print(f"  The lane should receive /start-task {packet_id}")
        return 0 if result.executed else 1

    elif action == "accept":
        return _cmd_task_accept(args, task_queue_root)

    elif action == "complete":
        packet_id = args.packet_id
        summary = getattr(args, "summary", "") or ""
        pr_number = getattr(args, "pr_number", None)
        completed_by = getattr(args, "completed_by", "") or ""
        no_archive = getattr(args, "no_archive", False)

        # Verify the packet exists before creating the result
        pkt = load_packet(packet_id, task_queue_root)
        if pkt is None:
            print(f"Packet {packet_id!r} not found.", file=sys.stderr)
            return 1

        # Auto-transition approved → dispatched so the completion
        # follows the state machine (approved → dispatched → completed).
        if pkt.status == "approved":
            transition_status(packet_id, "dispatched", task_queue_root)
        elif pkt.status != "dispatched":
            print(
                f"Cannot complete packet in {pkt.status!r} state "
                f"(expected 'dispatched' or 'approved').",
                file=sys.stderr,
            )
            return 1

        result = create_result(
            packet_id=packet_id,
            status="completed",
            summary=summary,
            pr_number=pr_number,
            completed_by=completed_by,
        )

        updated = complete_packet(result, task_queue_root, archive=not no_archive)
        if updated is None:
            print(f"Failed to complete packet {packet_id!r}.", file=sys.stderr)
            return 1

        # Emit task_completed event (append-only, best-effort)
        try:
            from bid_euchre.ops.events import append_event

            append_event(
                event_type="task_completed",
                source="ops.task_complete",
                lane_id=completed_by or (pkt.owner or "unknown"),
                payload={
                    "packet_id": packet_id,
                    "title": pkt.title,
                    "summary": summary,
                    "pr_number": pr_number,
                    "completed_by": completed_by or (pkt.owner or "unknown"),
                },
                events_dir=args.runtime_dir / "events",
            )
        except Exception:
            pass  # best-effort — don't fail completion on event emission

        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(updated), indent=2, default=str))
        else:
            print(f"Completed: {updated.packet_id}")
            print(f"  Status:  {updated.status}")
            print(f"  Summary: {summary}")
            if pr_number:
                print(f"  PR:      #{pr_number}")
            if not no_archive:
                print("  (archived)")
        return 0

    else:
        print(
            "Usage: ops.py task {list|show|create|approve|dispatch|accept|complete}",
            file=sys.stderr,
        )
        return 1


def _cmd_task_accept(args: argparse.Namespace, task_queue_root: Path) -> int:
    """Accept a dispatched task: ack inbox, send ack to orchestrator, emit event.

    Idempotent — safe to call multiple times for the same packet.
    """
    from bid_euchre.ops.events import append_event
    from bid_euchre.ops.message_bus import (
        ack_message,
        create_message,
        read_inbox,
        send_message,
        shared_bus_root,
    )
    from bid_euchre.ops.task_queue import load_packet

    packet_id = args.packet_id
    lane_id = args.lane_id
    bus_root = shared_bus_root()
    events_dir = args.runtime_dir / "events"

    # 1. Verify packet exists
    pkt = load_packet(packet_id, task_queue_root)
    if pkt is None:
        print(f"Packet {packet_id!r} not found.", file=sys.stderr)
        return 1

    steps_done: list[str] = []

    # 2. Ack inbox messages for this task (idempotent — skip already acked)
    inbox_msgs = read_inbox(
        lane_id, bus_root, message_type="assignment", auto_expire=True
    )
    acked_count = 0
    for msg in inbox_msgs:
        if msg.get("task_id") == packet_id and msg.get("status") in (
            "pending",
            "delivered",
        ):
            try:
                ack_message(msg["message_id"], lane_id, bus_root)
                acked_count += 1
            except (ValueError, KeyError):
                pass  # already acked or invalid transition
    if acked_count > 0:
        steps_done.append(f"acked {acked_count} inbox message(s)")
    else:
        steps_done.append("inbox already acked (or no assignment message)")

    # 3. Send ack message to orchestrator (safe to re-run — duplicate acks are harmless)
    try:
        ack_msg = create_message(
            from_lane=lane_id,
            to_lane="orchestrator",
            message_type="ack",
            summary=f"Task accepted: {pkt.title}",
            task_id=packet_id,
        )
        send_message(ack_msg, bus_root=bus_root)
        steps_done.append("sent ack to orchestrator")
    except ValueError:
        # Duplicate message_id — already sent
        steps_done.append("ack already sent to orchestrator")

    # 4. Emit task_started event (always — events are append-only)
    try:
        append_event(
            event_type="task_started",
            source="ops.task_accept",
            lane_id=lane_id,
            payload={
                "packet_id": packet_id,
                "title": pkt.title,
                "owner": lane_id,
            },
            events_dir=events_dir,
        )
        steps_done.append("emitted task_started event")
    except Exception as exc:
        steps_done.append(f"event emission failed: {exc}")

    if args.json:
        print(
            json.dumps(
                {
                    "packet_id": packet_id,
                    "lane": lane_id,
                    "title": pkt.title,
                    "steps": steps_done,
                },
                indent=2,
            )
        )
    else:
        print(f"Accepted: {packet_id}")
        print(f"  Lane:  {lane_id}")
        print(f"  Title: {pkt.title}")
        for step in steps_done:
            print(f"  ✓ {step}")

    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    """Communication bus inbox inspection and acknowledgment (Platform-3)."""
    from bid_euchre.ops.message_bus import (
        ack_message,
        bulk_ack_messages,
        compact_all_inboxes,
        compact_inbox,
        import_native_inbox,
        inbox_stats,
        read_inbox,
        read_inbox_prioritized,
        shared_bus_root,
    )

    bus_root = shared_bus_root()

    # If --include-native is set, import native inbox first
    include_native = getattr(args, "include_native", False)
    native_lane = getattr(args, "lane", None)
    if include_native and native_lane:
        imported = import_native_inbox(native_lane, bus_root=bus_root)
        if imported and not getattr(args, "json", False):
            print(f"Imported {len(imported)} native message(s) for {native_lane}")
            print()

    action = getattr(args, "inbox_action", None)

    if action == "ack":
        msg_id = getattr(args, "message_id", None)
        lane = getattr(args, "lane", None)
        if not msg_id or not lane:
            print(
                "Usage: ops.py inbox ack MSG_ID --lane LANE",
                file=sys.stderr,
            )
            return 1
        result = ack_message(msg_id, lane, bus_root)
        if result is None:
            print(
                f"Message {msg_id!r} not found in {lane!r} inbox.",
                file=sys.stderr,
            )
            return 1
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Acknowledged: {msg_id} in {lane} inbox")
            print(f"  Status: {result.get('status', '?')}")
        return 0

    elif action in ("ack-all", "bulk-ack"):
        import re
        from datetime import datetime, timezone

        lane = getattr(args, "lane", None)
        if not lane:
            print(
                "Usage: ops.py inbox ack-all --lane LANE"
                " [--filter-summary PATTERN] [--max-age HOURS]",
                file=sys.stderr,
            )
            return 1

        # Build composable filter predicates
        predicates: list = []

        summary_pattern = getattr(args, "filter_summary", None)
        if summary_pattern:
            pat = re.compile(summary_pattern, re.IGNORECASE)
            predicates.append(lambda msg: bool(pat.search(msg.get("summary", ""))))

        max_age_hours = getattr(args, "max_age", None)
        if max_age_hours is not None:
            cutoff = datetime.now(timezone.utc).timestamp() - max_age_hours * 3600

            def _older_than_cutoff(msg: dict) -> bool:
                created = msg.get("created_at", "")
                if not created:
                    return False
                try:
                    ts = datetime.fromisoformat(
                        created.replace("Z", "+00:00")
                    ).timestamp()
                except (ValueError, TypeError):
                    return False
                return ts < cutoff

            predicates.append(_older_than_cutoff)

        if predicates:

            def filter_fn(msg: dict) -> bool:
                return all(p(msg) for p in predicates)
        else:

            def filter_fn(msg: dict) -> bool:
                return True

        acked = bulk_ack_messages(lane, filter_fn, bus_root)
        if args.json:
            print(json.dumps(acked, indent=2, default=str))
        else:
            if not acked:
                print(f"No ack-able messages in {lane} inbox.")
            else:
                print(f"Bulk-acked {len(acked)} message(s) in {lane} inbox:")
                for msg in acked:
                    print(
                        f"  {msg.get('message_id', '?'):16s}  "
                        f"{msg.get('summary', '')[:60]}"
                    )
        return 0

    elif action == "stats":
        stats = inbox_stats(bus_root)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            lanes = stats.get("lanes", [])
            if not lanes:
                print("No inbox data.")
            else:
                print(f"Inbox Stats: {len(lanes)} lane(s)")
                print()
                for lane in lanes:
                    print(f"  {lane['lane_id']:20s}  total={lane['total']}")
                    for status, count in sorted(lane.get("by_status", {}).items()):
                        print(f"    {status:16s}: {count}")
        return 0

    elif action == "purge":
        max_age = getattr(args, "max_age", 24.0)
        lane = getattr(args, "lane", None)

        if lane:
            results = [compact_inbox(lane, bus_root, max_age_hours=max_age)]
        else:
            results = compact_all_inboxes(bus_root, max_age_hours=max_age)

        if args.json:
            print(json.dumps(results, indent=2))
        else:
            total_removed = sum(r["removed"] for r in results)
            total_before = sum(r["before"] for r in results)
            total_after = sum(r["after"] for r in results)
            if not results:
                print("No inbox files found.")
            else:
                print(
                    f"Purged {total_removed} terminal message(s) "
                    f"older than {max_age}h across {len(results)} inbox(es)"
                )
                print(f"  Raw records before: {total_before}")
                print(f"  Deduplicated after: {total_after}")
                print()
                for r in results:
                    if r["removed"] > 0 or r["before"] != r["after"]:
                        print(
                            f"  {r['lane_id']:20s}  "
                            f"{r['before']} -> {r['after']}  "
                            f"(-{r['removed']} purged)"
                        )
        return 0

    # Default: list messages
    lane = getattr(args, "lane", None)
    status_filter = getattr(args, "status", None)
    raw_type = getattr(args, "type", None)
    thread_filter = getattr(args, "thread", None)

    # Support comma-separated type filters (e.g. --type completion,escalation)
    type_filter: str | list[str] | None = None
    if raw_type is not None:
        parts = [t.strip() for t in raw_type.split(",") if t.strip()]
        type_filter = parts[0] if len(parts) == 1 else parts

    if lane is None:
        # Show aggregate stats across all lanes
        stats = inbox_stats(bus_root)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            lanes = stats.get("lanes", [])
            if not lanes:
                print("No inbox data. Use --lane LANE to inspect a specific lane.")
            else:
                print(f"Inbox Overview: {len(lanes)} lane(s)")
                print("  Use --lane LANE to see messages for a specific lane.")
                print()
                for ln in lanes:
                    total = ln["total"]
                    by_s = ln.get("by_status", {})
                    pending = by_s.get("pending", 0) + by_s.get("delivered", 0)
                    print(f"  {ln['lane_id']:20s}  {total} msg  ({pending} unresolved)")
        return 0

    # --prioritized: group messages by P0/P1/P2 tiers
    use_prioritized = getattr(args, "prioritized", False)
    if use_prioritized:
        p0, p1, p2 = read_inbox_prioritized(
            lane,
            bus_root,
            status=status_filter,
        )

        # Forward --type and --thread filters (read_inbox_prioritized does
        # not accept these natively, so post-filter each tier).
        if type_filter is not None or thread_filter is not None:
            allowed_types = (
                ({type_filter} if isinstance(type_filter, str) else set(type_filter))
                if type_filter is not None
                else None
            )

            def _match(msg: dict) -> bool:
                if allowed_types and msg.get("message_type") not in allowed_types:
                    return False
                if thread_filter and msg.get("thread_id") != thread_filter:
                    return False
                return True

            p0 = [m for m in p0 if _match(m)]
            p1 = [m for m in p1 if _match(m)]
            p2 = [m for m in p2 if _match(m)]
        if args.json:
            print(
                json.dumps(
                    {"p0": p0, "p1": p1, "p2": p2},
                    indent=2,
                    default=str,
                )
            )
        else:
            total = len(p0) + len(p1) + len(p2)
            if total == 0:
                print(f"No messages in {lane} inbox.")
            else:
                print(f"Inbox for {lane}: {total} message(s) (prioritized)")
                for label, tier in [
                    ("P0 (urgent)", p0),
                    ("P1 (high)", p1),
                    ("P2 (normal/low)", p2),
                ]:
                    print()
                    print(f"  {label}: {len(tier)} message(s)")
                    for msg in tier:
                        print(
                            f"    {msg.get('message_id', '?'):16s}  "
                            f"[{msg.get('status', '?'):14s}]  "
                            f"{msg.get('message_type', '?'):18s}  "
                            f"from={msg.get('from_lane', '?'):12s}  "
                            f"{msg.get('summary', '')[:50]}"
                        )
        return 0

    messages = read_inbox(
        lane,
        bus_root,
        status=status_filter,
        thread_id=thread_filter,
        message_type=type_filter,
    )

    if args.json:
        print(json.dumps(messages, indent=2, default=str))
    else:
        if not messages:
            print(f"No messages in {lane} inbox.")
        else:
            print(f"Inbox for {lane}: {len(messages)} message(s)")
            print()
            for msg in messages:
                priority = msg.get("priority", "normal")
                prio_flag = " !" if priority in ("high", "urgent") else ""
                print(
                    f"  {msg.get('message_id', '?'):16s}  "
                    f"[{msg.get('status', '?'):14s}]  "
                    f"{msg.get('message_type', '?'):18s}  "
                    f"from={msg.get('from_lane', '?'):12s}  "
                    f"{msg.get('summary', '')[:50]}{prio_flag}"
                )
    return 0


def cmd_message(args: argparse.Namespace) -> int:
    """Show or send messages via the audit trail (Platform-3)."""
    from bid_euchre.ops.message_bus import read_messages, shared_bus_root

    bus_root = shared_bus_root()

    action = getattr(args, "message_action", None)

    if action == "send":
        from bid_euchre.ops.message_bus import create_message, send_message

        msg = create_message(
            from_lane=args.from_lane,
            to_lane=args.to_lane,
            message_type=args.msg_type,
            summary=args.summary,
            task_id=getattr(args, "task_id", None),
            thread_id=getattr(args, "thread_id", None),
            priority=getattr(args, "priority", "normal"),
        )
        try:
            msg_id = send_message(msg, bus_root)
        except ValueError as exc:
            print(f"Send failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(msg), indent=2, default=str))
        else:
            print(f"Sent message: {msg_id}")
            print(f"  From:    {args.from_lane}")
            print(f"  To:      {args.to_lane}")
            print(f"  Type:    {args.msg_type}")
            print(f"  Summary: {args.summary}")
        return 0

    if action != "show":
        print(
            "Usage: ops.py message {show|send} ...",
            file=sys.stderr,
        )
        return 1

    msg_id = args.message_id

    # Search audit trail for the message
    # Read all (large limit) and find by ID
    all_msgs = read_messages(bus_root, limit=10000)
    found = None
    for msg in all_msgs:
        if msg.get("message_id") == msg_id:
            found = msg
            break

    if found is None:
        print(f"Message {msg_id!r} not found in audit trail.", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(found, indent=2, default=str))
    else:
        print(f"Message: {found.get('message_id', '?')}")
        print(f"  Type:        {found.get('message_type', '?')}")
        print(f"  Status:      {found.get('status', '?')}")
        print(f"  From:        {found.get('from_lane', '?')}")
        print(f"  To:          {found.get('to_lane', '?')}")
        print(f"  Priority:    {found.get('priority', '?')}")
        print(f"  Created at:  {found.get('created_at', '?')}")
        print(f"  Summary:     {found.get('summary', '?')}")
        thread = found.get("thread_id")
        if thread:
            print(f"  Thread:      {thread}")
        task = found.get("task_id")
        if task:
            print(f"  Task:        {task}")
        parent = found.get("parent_message_id")
        if parent:
            print(f"  Parent:      {parent}")
        if found.get("requires_human"):
            print("  Requires human attention: YES")
        acked = found.get("acked_at")
        if acked:
            print(f"  Acked at:    {acked}")
        resolved = found.get("resolved_at")
        if resolved:
            print(f"  Resolved at: {resolved}")
        payload = found.get("payload", {})
        if payload:
            # Show payload without delivery policy internals
            display = {
                k: v
                for k, v in payload.items()
                if k not in ("max_retries", "retry_count", "ttl_seconds")
            }
            if display:
                print(f"  Payload:     {display}")
    return 0


def cmd_supervisor(args: argparse.Namespace) -> int:
    """Run a supervisor cycle: snapshot, delta, recommend (Platform-6)."""
    from bid_euchre.ops.supervisor import (
        SupervisorSnapshot,
        format_supervisor_json,
        format_supervisor_text,
        load_latest_snapshot,
        run_supervisor_cycle,
    )

    save = getattr(args, "save", False)

    # Load an explicit previous snapshot for diffing, if specified
    prev_snapshot: SupervisorSnapshot | None = None
    diff_path = getattr(args, "diff", None)
    if diff_path:
        from bid_euchre.ops.supervisor import load_snapshot_from_file

        try:
            prev_snapshot = load_snapshot_from_file(diff_path)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(f"Error loading snapshot: {exc}", file=sys.stderr)
            return 1
    elif save:
        # If saving, try to load previous for delta
        prev_snapshot = load_latest_snapshot(args.runtime_dir)

    result = run_supervisor_cycle(
        runtime_dir=args.runtime_dir,
        plans_dir=args.plans_dir,
        prev_snapshot=prev_snapshot,
        save=save,
    )

    if args.json:
        print(json.dumps(format_supervisor_json(result), indent=2))
    else:
        print(format_supervisor_text(result))

    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    """Run a single ops monitoring cycle (SP-3-08).

    After collecting findings, the controller projection is updated via
    ``reconcile()`` so that ``fleet_status.json`` stays current.  Pass
    ``--no-reconcile`` to skip the projection update (useful in tests or
    when only findings output is needed).
    """
    from dataclasses import asdict as _asdict

    from bid_euchre.ops.control_plane import reconcile as _reconcile
    from bid_euchre.ops.monitor import (
        format_findings_json,
        format_findings_text,
        run_monitoring_cycle,
    )
    from bid_euchre.ops.task_queue import list_packets

    skip_pr = getattr(args, "skip_pr_check", False)
    no_notify = getattr(args, "no_notify", False)
    no_recovery = getattr(args, "no_recovery", False)
    no_auto_dispatch = getattr(args, "no_auto_dispatch", False)
    no_reconcile = getattr(args, "no_reconcile", False)

    findings = run_monitoring_cycle(
        runtime_dir=args.runtime_dir,
        notify_orchestrator=not no_notify,
        skip_pr_check=skip_pr,
        no_recovery=no_recovery,
        no_auto_dispatch=no_auto_dispatch,
    )

    if args.json:
        print(json.dumps(format_findings_json(findings), indent=2))
    else:
        print(format_findings_text(findings))

    # Update the controller projection so fleet_status.json reflects the
    # latest monitor findings, task queue, inbox, and audit state.
    if not no_reconcile:
        try:
            task_dicts = [
                _asdict(p) for p in list_packets(root=args.runtime_dir / "task_queue")
            ]
        except Exception:
            task_dicts = None

        # Load unacked inbox messages for the orchestrator lane so the
        # controller can surface stale urgent items in fleet_status.json.
        try:
            from bid_euchre.ops.message_bus import read_inbox

            inbox_msgs = read_inbox("orchestrator", status="pending")
            inbox_msgs += read_inbox("orchestrator", status="delivered")
        except Exception:
            inbox_msgs = None

        # Load recent audit trail records so unanswered inbound remote
        # exchanges are surfaced in the fleet projection.
        try:
            from bid_euchre.ops.audit_trail import read_records

            audit_dir = args.runtime_dir / "audit_trail" if args.runtime_dir else None
            raw_records = read_records(audit_dir=audit_dir)
            audit_dicts = [r.to_dict() for r in raw_records]
        except Exception:
            audit_dicts = None

        _reconcile(
            runtime_dir=args.runtime_dir,
            monitor_finding_objects=findings,
            task_packets=task_dicts,
            unacked_messages=inbox_msgs,
            audit_records=audit_dicts,
        )

    # Exit 1 if any high-severity findings
    has_high = any(f.severity == "high" for f in findings)
    return 1 if has_high else 0


def cmd_fleet(args: argparse.Namespace) -> int:
    """Fleet status — read-only view of the controller projection (SP-4-07)."""
    from bid_euchre.ops.control_plane import (
        ack_item,
        clear_item,
        format_status_json,
        format_status_text,
        load_fleet_status,
        save_fleet_status,
        suppress_item,
    )

    status = load_fleet_status(args.runtime_dir)
    if status is None:
        if args.json:
            print(json.dumps({"items": [], "summary": {"total": 0, "open": 0}}))
        else:
            print("No fleet status file found. Run a reconcile cycle first.")
        return 0

    # Handle ack/clear/suppress mutations.
    mutated = False
    for action_name, action_fn, arg_name in [
        ("ack", ack_item, "ack"),
        ("clear", clear_item, "clear"),
        ("suppress", suppress_item, "suppress"),
    ]:
        item_prefix = getattr(args, arg_name, None)
        if item_prefix:
            # Prefix match on item_id.
            matches = [i for i in status.items if i.item_id.startswith(item_prefix)]
            if not matches:
                print(f"No item matching prefix {item_prefix!r}")
                return 1
            if len(matches) > 1:
                print(
                    f"Ambiguous prefix {item_prefix!r} — matches {len(matches)} items:"
                )
                for m in matches:
                    print(f"  {m.item_id}  {m.summary}")
                return 1
            ok = action_fn(status, matches[0].item_id)
            if ok:
                print(f"{action_name.title()}ed item {matches[0].item_id[:8]}")
                mutated = True
            else:
                print(
                    f"Cannot {action_name} item {matches[0].item_id[:8]} (state: {matches[0].state})"
                )
                return 1

    if mutated:
        save_fleet_status(status, args.runtime_dir)

    if args.json:
        print(format_status_json(status))
    else:
        print(format_status_text(status))

    return 0


def cmd_review_check(args: argparse.Namespace) -> int:
    """Check recently merged PRs for diff stats and contract issues.

    Queries ``gh pr list --state merged`` for the N most recent merges, runs
    basic diff-stat and contract checks (large file count, data/ artifacts,
    contract-doc changes without test changes), and writes findings to the
    orchestrator inbox via the message bus.

    Designed to run on a ``/loop 20m`` cadence from the review lane.
    """
    import subprocess as sp

    from bid_euchre.ops.message_bus import (
        create_message,
        send_message,
        shared_bus_root,
    )

    limit = getattr(args, "limit", 5)
    no_notify = getattr(args, "no_notify", False)
    bus_root = shared_bus_root()

    # Fetch recently merged PRs via gh CLI
    try:
        result = sp.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "merged",
                "--limit",
                str(limit),
                "--json",
                "number,title,mergedAt,changedFiles,additions,deletions",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"gh pr list failed: {result.stderr.strip()}", file=sys.stderr)
            return 1
        prs = json.loads(result.stdout)
    except (sp.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Error fetching merged PRs: {exc}", file=sys.stderr)
        return 1

    if not prs:
        if args.json:
            print(json.dumps({"findings": [], "prs_checked": 0}))
        else:
            print("No recently merged PRs found.")
        return 0

    # Run basic checks on each PR
    findings: list[dict[str, str]] = []
    for pr in prs:
        pr_num = pr["number"]
        title = pr.get("title", "")
        changed = pr.get("changedFiles", 0)
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)

        # Check 1: Large diff (>500 changed files or >5000 lines)
        total_lines = additions + deletions
        if changed > 500 or total_lines > 5000:
            findings.append(
                {
                    "pr": pr_num,
                    "check": "large_diff",
                    "severity": "warn",
                    "detail": (
                        f"PR #{pr_num} ({title}): {changed} files, "
                        f"+{additions}/-{deletions} lines"
                    ),
                }
            )

        # Check 2: Fetch diff stat for data/ artifact detection
        try:
            diff_result = sp.run(
                [
                    "gh",
                    "pr",
                    "diff",
                    str(pr_num),
                    "--name-only",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if diff_result.returncode == 0:
                changed_files = diff_result.stdout.strip().splitlines()

                # Check for committed data artifacts
                data_files = [
                    f
                    for f in changed_files
                    if f.startswith(("data/runs/", "data/reports/", "data/models/"))
                ]
                if data_files:
                    findings.append(
                        {
                            "pr": pr_num,
                            "check": "data_artifact",
                            "severity": "block",
                            "detail": (
                                f"PR #{pr_num} ({title}): committed data artifacts: "
                                f"{', '.join(data_files[:5])}"
                            ),
                        }
                    )

                # Check for contract doc changes without test changes
                contract_docs = [
                    f
                    for f in changed_files
                    if f.startswith("docs/01_core/")
                    and f.endswith(("RULES.md", "DATA_CONTRACT.md", "METRICS.md"))
                ]
                test_files = [f for f in changed_files if f.startswith("tests/")]
                if contract_docs and not test_files:
                    findings.append(
                        {
                            "pr": pr_num,
                            "check": "contract_no_tests",
                            "severity": "warn",
                            "detail": (
                                f"PR #{pr_num} ({title}): contract docs changed "
                                f"({', '.join(contract_docs)}) without test updates"
                            ),
                        }
                    )
        except (sp.TimeoutExpired, FileNotFoundError, OSError):
            pass  # Best-effort — skip diff check if gh fails

    # Output
    if args.json:
        print(
            json.dumps(
                {"findings": findings, "prs_checked": len(prs)},
                indent=2,
            )
        )
    else:
        print(f"Checked {len(prs)} recently merged PR(s).")
        if findings:
            for f in findings:
                severity = f["severity"].upper()
                print(f"  [{severity}] {f['detail']}")
        else:
            print("  No issues found.")

    # Notify orchestrator if there are findings
    if findings and not no_notify:
        summary_parts = []
        blocks = sum(1 for f in findings if f["severity"] == "block")
        warns = sum(1 for f in findings if f["severity"] == "warn")
        if blocks:
            summary_parts.append(f"{blocks} blocker(s)")
        if warns:
            summary_parts.append(f"{warns} warning(s)")
        summary = (
            f"review-check: {', '.join(summary_parts)} across {len(prs)} merged PRs"
        )

        try:
            msg = create_message(
                from_lane="review",
                to_lane="orchestrator",
                message_type="supervisor_alert",
                summary=summary,
                payload={"findings": findings, "prs_checked": len(prs)},
            )
            send_message(msg, bus_root)
        except Exception as exc:
            print(
                f"Warning: could not send findings to orchestrator: {exc}",
                file=sys.stderr,
            )

    has_blockers = any(f["severity"] == "block" for f in findings)
    return 1 if has_blockers else 0


def cmd_lane(args: argparse.Namespace) -> int:
    """Lane lifecycle management (refresh, etc.)."""
    action = getattr(args, "lane_action", None)

    if action == "refresh":
        all_idle = getattr(args, "all_idle", False)
        force = getattr(args, "force", False)

        if all_idle:
            from bid_euchre.ops.worker_pool import (
                format_action_text,
                format_actions_json,
                refresh_all_idle,
            )

            actions = refresh_all_idle(force=force, runtime_dir=args.runtime_dir)
            if args.json:
                print(json.dumps(format_actions_json(actions), indent=2))
            else:
                if actions:
                    for a in actions:
                        print(format_action_text(a))
                else:
                    print("No idle lanes to refresh.")
            # Return 0 if at least one action executed, 1 if all failed
            return 0 if any(a.executed for a in actions) or not actions else 1

        # Single lane refresh
        lane_id = getattr(args, "lane_id", None)
        if not lane_id:
            print("Error: either lane_id or --all-idle is required", file=sys.stderr)
            return 1

        from bid_euchre.ops.worker_pool import format_action_text, refresh_worker

        result = refresh_worker(lane_id, force=force, runtime_dir=args.runtime_dir)
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2))
        else:
            print(format_action_text(result))
        return 0 if result.executed else 1

    elif action == "check-approvals":
        from bid_euchre.ops.monitor import (
            check_approval_stalls,
            format_findings_json,
            format_findings_text,
        )

        findings = check_approval_stalls(runtime_dir=args.runtime_dir)
        if args.json:
            print(json.dumps(format_findings_json(findings), indent=2))
        else:
            if findings:
                print(format_findings_text(findings))
            else:
                print("No lanes stuck on approval prompts.")
        return 1 if findings else 0

    elif action == "peek":
        import subprocess

        lane_id = args.lane_id
        lines = args.lines
        tmux_session = "steward"

        from bid_euchre.ops.worker_pool import _resolve_tmux_target

        target = _resolve_tmux_target(
            lane_id, tmux_session, runtime_dir=args.runtime_dir
        )
        try:
            result = subprocess.run(
                [
                    "tmux",
                    "capture-pane",
                    "-t",
                    target,
                    "-p",
                    "-S",
                    str(-lines),
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                err = result.stderr.strip()
                print(f"Error: tmux capture-pane failed: {err}", file=sys.stderr)
                return 1
            content = result.stdout
            if args.json:
                print(
                    json.dumps(
                        {"lane": lane_id, "content": content},
                        indent=2,
                    )
                )
            else:
                print(content, end="")
            return 0
        except FileNotFoundError:
            print("Error: tmux is not installed or not on PATH", file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired:
            print("Error: tmux capture-pane timed out", file=sys.stderr)
            return 1

    else:
        print(
            "Usage: ops.py lane refresh <lane-id> | --all-idle\n"
            "       ops.py lane check-approvals\n"
            "       ops.py lane peek <lane-id> [--lines N]"
        )
        return 1


def cmd_workers(args: argparse.Namespace) -> int:
    """Worker pool lifecycle management (Platform-7)."""
    from bid_euchre.ops.worker_pool import (
        dispatch_to_worker,
        format_action_text,
        format_actions_json,
        format_pool_json,
        format_pool_text,
        park_worker,
        retire_worker,
        run_pool_maintenance,
        take_pool_snapshot,
        wake_worker,
    )

    action = getattr(args, "workers_action", None)

    if action == "wake":
        lane_id = args.lane_id
        result = wake_worker(lane_id, runtime_dir=args.runtime_dir)
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2))
        else:
            print(format_action_text(result))
        return 0 if result.executed else 1

    elif action == "park":
        lane_id = args.lane_id
        result = park_worker(lane_id, runtime_dir=args.runtime_dir)
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2))
        else:
            print(format_action_text(result))
        return 0 if result.executed else 1

    elif action == "retire":
        lane_id = args.lane_id
        result = retire_worker(lane_id, runtime_dir=args.runtime_dir)
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2))
        else:
            print(format_action_text(result))
        return 0 if result.executed else 1

    elif action == "dispatch":
        packet_id = args.packet_id
        lane_id = args.lane_id
        do_reset = getattr(args, "reset", False)
        no_auto_refresh = getattr(args, "no_auto_refresh", False)
        result = dispatch_to_worker(
            packet_id,
            lane_id,
            runtime_dir=args.runtime_dir,
            reset=do_reset,
            no_auto_refresh=no_auto_refresh,
        )
        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2))
        else:
            print(format_action_text(result))
        return 0 if result.executed else 1

    elif action == "maintain":
        dry_run = getattr(args, "dry_run", False)
        actions = run_pool_maintenance(runtime_dir=args.runtime_dir, dry_run=dry_run)
        if args.json:
            print(json.dumps(format_actions_json(actions), indent=2))
        else:
            if actions:
                for a in actions:
                    print(format_action_text(a))
            else:
                print("No maintenance actions needed.")
        return 0

    else:
        # Default: show pool snapshot
        pool = take_pool_snapshot(args.runtime_dir)
        if args.json:
            print(json.dumps(format_pool_json(pool), indent=2))
        else:
            print(format_pool_text(pool))
        return 0


def cmd_usage(args: argparse.Namespace) -> int:
    """Token economy: import and query usage data."""
    action = getattr(args, "usage_action", None)

    if action == "import":
        from bid_euchre.ops.token_economy import import_usage_data

        result = import_usage_data(
            usage_dir=getattr(args, "usage_dir", None),
            output_dir=getattr(args, "output_dir", None),
        )

        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print("Import complete:")
            print(f"  Sessions imported: {result.sessions_imported}")
            print(f"  Sessions skipped:  {result.sessions_skipped}")
            print(f"  Sessions failed:   {result.sessions_failed}")
            print(f"  Total sessions:    {result.total_sessions}")
            print(f"  Output dir:        {result.output_dir}")
        return 0

    elif action == "attribute":
        from bid_euchre.ops.token_economy import attribute_sessions

        result = attribute_sessions(
            output_dir=getattr(args, "output_dir", None),
        )

        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print("Attribution complete:")
            print(f"  Total sessions:          {result.total_sessions}")
            print(f"  Attributed:              {result.attributed}")
            print(f"  Partially attributed:    {result.partially_attributed}")
            print(f"  Unattributed:            {result.unattributed}")
            if result.lanes_found:
                print(f"  Lanes found:             {', '.join(result.lanes_found)}")
            print(f"  Output dir:              {result.output_dir}")
        return 0

    elif action == "summary":
        from bid_euchre.ops.token_economy import usage_summary

        result = usage_summary(
            output_dir=getattr(args, "output_dir", None),
        )

        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print("Token Economy Summary")
            print("=" * 50)
            print(f"  Sessions:            {result.session_count}")
            print(f"  Time range:          {result.time_range_start or 'N/A'}")
            print(f"                    to {result.time_range_end or 'N/A'}")
            print(f"  Total duration:      {result.total_duration_minutes} min")
            print()
            print("  Tokens:")
            print(f"    Input:             {result.total_input_tokens:,}")
            print(f"    Output:            {result.total_output_tokens:,}")
            print(f"    Total:             {result.total_tokens:,}")
            print(f"    Output/Input:      {result.output_input_ratio:.1f}x")
            print(f"    Tokens/hour:       {result.tokens_per_hour:,.0f}")
            print()
            print("  Throughput:")
            print(f"    Lines added:       {result.total_lines_added:,}")
            print(f"    Lines removed:     {result.total_lines_removed:,}")
            print(f"    Net lines:         {result.net_lines:,}")
            print(f"    Git commits:       {result.total_git_commits}")
            print(f"    Git pushes:        {result.total_git_pushes}")
            print(f"    Files modified:    {result.total_files_modified}")
            print()
            print("  Interaction:")
            print(f"    User messages:     {result.total_user_messages}")
            print(f"    Assistant msgs:    {result.total_assistant_messages}")
            print(f"    Assist/User:       {result.assistant_user_ratio:.1f}x")
            print(f"    Tool errors:       {result.total_tool_errors}")
        return 0

    elif action == "lanes":
        from bid_euchre.ops.token_economy import lane_summary

        lanes = lane_summary(
            output_dir=getattr(args, "output_dir", None),
        )

        if args.json:
            from dataclasses import asdict

            print(json.dumps([asdict(ls) for ls in lanes], indent=2, default=str))
        else:
            if not lanes:
                print("No attribution data. Run: ops.py usage attribute")
            else:
                print("Per-Lane Token Usage")
                print("=" * 90)
                print(
                    f"  {'Lane':<20s} {'Pool':<12s} {'Sessions':>8s} "
                    f"{'Tokens':>12s} {'Commits':>8s} {'Net Δ':>8s} "
                    f"{'Tok/Commit':>11s}"
                )
                print("-" * 90)
                for ls in lanes:
                    pool = ls.pool or "—"
                    tpc = (
                        f"{ls.tokens_per_commit:,.0f}" if ls.tokens_per_commit else "—"
                    )
                    print(
                        f"  {ls.lane_id:<20s} {pool:<12s} {ls.session_count:>8d} "
                        f"{ls.total_tokens:>12,d} {ls.git_commits:>8d} "
                        f"{ls.net_lines:>+8d} {tpc:>11s}"
                    )
        return 0

    elif action == "throughput":
        from bid_euchre.ops.token_economy import throughput_summary

        result = throughput_summary(
            output_dir=getattr(args, "output_dir", None),
        )

        if args.json:
            from dataclasses import asdict

            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print("Throughput Metrics")
            print("=" * 50)
            print(f"  Sessions:                {result.total_sessions}")
            print(f"  Total tokens:            {result.total_tokens:,}")
            print()
            print(f"  Tokens/commit:           {result.tokens_per_commit:,.0f}")
            print(f"  Tokens/net line:         {result.tokens_per_net_line:,.0f}")
            print(f"  Tokens/hour:             {result.tokens_per_hour:,.0f}")
            print(f"  Output/Input ratio:      {result.output_input_ratio:.1f}x")
            print(
                f"  Assist/User msgs:        {result.assistant_per_user_message:.1f}x"
            )
            print(f"  Tool errors/1K tokens:   {result.tool_errors_per_1k_tokens:.2f}")
        return 0

    elif action == "anti-patterns":
        from bid_euchre.ops.token_economy import detect_anti_patterns

        findings = detect_anti_patterns(
            output_dir=getattr(args, "output_dir", None),
        )

        if args.json:
            from dataclasses import asdict

            print(json.dumps([asdict(f) for f in findings], indent=2, default=str))
        else:
            if not findings:
                print("No anti-patterns detected. ✓")
            else:
                print(f"Anti-Patterns Detected: {len(findings)}")
                print("=" * 70)
                for f in findings:
                    sev_icon = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(
                        f.severity, "⚪"
                    )
                    print(f"\n  {sev_icon} [{f.severity.upper()}] {f.name}")
                    print(f"    {f.description}")
        return 0

    else:
        print(
            "Usage: ops.py usage {import|attribute|summary|lanes|throughput|anti-patterns}",
            file=sys.stderr,
        )
        return 1


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
        help=(
            "Override runtime directory (default: .claude/runtime). "
            "For queue, only used when the override contains a review_queue/ subdir; "
            "otherwise the shared queue root is used (see BID_EUCHRE_REVIEW_QUEUE_DIR)."
        ),
    )
    parser.add_argument(
        "--plans-dir",
        type=Path,
        default=None,
        help="Override plans directory (default: plans/)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status
    status_parser = subparsers.add_parser(
        "status", help="Lane/session/task health summary"
    )
    status_parser.add_argument(
        "--no-probe",
        action="store_true",
        default=False,
        help="Skip dirty-worktree subprocess probes (faster with many idle lanes)",
    )

    # dashboard (Platform-4: dashboard-first supervision surface)
    dash_parser = subparsers.add_parser(
        "dashboard", help="Dashboard-first steward supervision"
    )
    dash_parser.add_argument(
        "--no-probe",
        action="store_true",
        default=False,
        help="Skip dirty-worktree subprocess probes (faster)",
    )
    dash_parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        default=False,
        help="Auto-refresh dashboard in a loop (Ctrl+C to stop)",
    )
    dash_parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Refresh interval in seconds when --watch is active (default: 30)",
    )
    dash_sub = dash_parser.add_subparsers(dest="dashboard_action")
    set_vis = dash_sub.add_parser(
        "set-visibility", help="Set lane visibility (foreground/background/hidden)"
    )
    set_vis.add_argument("lane", help="Lane ID to update")
    set_vis.add_argument(
        "visibility",
        choices=["foreground", "background", "hidden"],
        help="Visibility level",
    )

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

    wt_sub.add_parser(
        "register-all",
        help="Scan git worktrees and register all steward lanes",
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
    health_parser = subparsers.add_parser("health", help="Aggregated health check")
    health_parser.add_argument(
        "--no-probe",
        action="store_true",
        default=False,
        help="Skip dirty-worktree subprocess probes (faster with many idle lanes)",
    )

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

    # comments
    comments_parser = subparsers.add_parser(
        "comments", help="PR comment overlays (Codex Cloud, bots, humans)"
    )
    comments_parser.add_argument(
        "--pr", type=int, default=None, help="PR number (required)"
    )
    comments_parser.add_argument(
        "--ingest",
        action="store_true",
        help="Write comment sidecar for index and emit event",
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

    # retry (with nested "summary" subcommand)
    retry_parser = subparsers.add_parser(
        "retry", help="Evaluate retry/reroute policy for a task"
    )
    retry_parser.add_argument(
        "--task", type=str, default=None, help="Task ID to evaluate"
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
    retry_parser.add_argument(
        "--emit",
        action="store_true",
        help="Emit durable event for the policy decision (default: off)",
    )
    retry_sub = retry_parser.add_subparsers(dest="retry_action")
    retry_sub.add_parser(
        "summary", help="Show retry follow-through summary across all tasks"
    )

    # index
    index_parser = subparsers.add_parser("index", help="Build or show audit index")
    index_parser.add_argument(
        "--rebuild", action="store_true", help="Full rebuild (drop and recreate)"
    )

    # query
    query_parser = subparsers.add_parser("query", help="Query the audit index")
    query_parser.add_argument(
        "--text", type=str, default=None, help="Search text (FTS5 query)"
    )
    query_parser.add_argument(
        "--type", type=str, default=None, help="Filter by entry type"
    )
    query_parser.add_argument(
        "--limit", type=int, default=20, help="Max results (default: 20)"
    )
    query_parser.add_argument(
        "--recent", action="store_true", help="Show recent entries instead of searching"
    )

    # memory
    memory_parser = subparsers.add_parser("memory", help="Show curated memory entries")
    memory_parser.add_argument(
        "--category", type=str, default=None, help="Filter by category"
    )
    memory_parser.add_argument("--tag", type=str, default=None, help="Filter by tag")

    # compact
    subparsers.add_parser("compact", help="List archived sessions")

    # snapshot (with nested create/list/rollback/prune subcommands)
    snap_parser = subparsers.add_parser(
        "snapshot", help="Shadow snapshots for auditable rollback"
    )
    snap_sub = snap_parser.add_subparsers(dest="snapshot_action")

    snap_create_parser = snap_sub.add_parser("create", help="Create a shadow snapshot")
    snap_create_parser.add_argument(
        "--worktree", type=str, required=True, help="Worktree path to snapshot"
    )
    snap_create_parser.add_argument(
        "--reason", type=str, default="Manual snapshot", help="Reason for snapshot"
    )
    snap_create_parser.add_argument(
        "--lane", type=str, default=None, help="Lane ID for attribution"
    )
    snap_create_parser.add_argument(
        "--task", type=str, default=None, help="Task ID for attribution"
    )

    snap_list_parser = snap_sub.add_parser("list", help="List shadow snapshots")
    snap_list_parser.add_argument(
        "--worktree", type=str, default=None, help="Filter by worktree path"
    )
    snap_list_parser.add_argument(
        "--limit", type=int, default=20, help="Max results (default: 20)"
    )

    snap_rollback_parser = snap_sub.add_parser(
        "rollback", help="Roll back to a snapshot"
    )
    snap_rollback_parser.add_argument(
        "snapshot_id", type=str, help="Snapshot ID to roll back to"
    )

    snap_prune_parser = snap_sub.add_parser("prune", help="Prune old snapshots")
    snap_prune_parser.add_argument(
        "--max-per-worktree",
        type=int,
        default=20,
        help="Max snapshots per worktree (default: 20)",
    )
    snap_prune_parser.add_argument(
        "--max-age-hours",
        type=float,
        default=168.0,
        help="Max age in hours (default: 168 = 7 days)",
    )

    # scope (with nested set/touch/show subcommands)
    scope_parser = subparsers.add_parser(
        "scope", help="Manage task scope fields (declared/touched files)"
    )
    scope_sub = scope_parser.add_subparsers(dest="scope_action")

    scope_show_parser = scope_sub.add_parser("show", help="Show scope for a task")
    scope_show_parser.add_argument(
        "--task", type=str, required=True, help="Task ID to inspect"
    )

    scope_set_parser = scope_sub.add_parser(
        "set", help="Set declared_files for a task scope"
    )
    scope_set_parser.add_argument("--task", type=str, required=True, help="Task ID")
    scope_set_parser.add_argument(
        "--declared",
        type=str,
        nargs="+",
        required=True,
        help="Glob patterns for declared file scope",
    )

    scope_touch_parser = scope_sub.add_parser(
        "touch", help="Record touched files for a task scope"
    )
    scope_touch_parser.add_argument("--task", type=str, required=True, help="Task ID")
    scope_touch_parser.add_argument(
        "--file",
        type=str,
        nargs="+",
        required=True,
        help="File paths to record as touched",
    )

    scope_check_parser = scope_sub.add_parser(
        "check", help="Check scope drift (declared vs touched)"
    )
    scope_check_parser.add_argument(
        "--task", type=str, required=True, help="Task ID to check"
    )
    scope_check_parser.add_argument(
        "--emit",
        action="store_true",
        help="Emit watchdog_finding event on drift (default: off)",
    )
    scope_check_parser.add_argument(
        "--lane", type=str, default=None, help="Lane ID for event attribution"
    )

    # skills (with nested propose/review/promote/disable subcommands)
    skills_parser = subparsers.add_parser("skills", help="Skill-promotion workflow")
    skills_parser.add_argument(
        "--status",
        type=str,
        choices=["pending", "approved", "rejected", "promoted"],
        help="Filter by candidate status",
    )
    skills_sub = skills_parser.add_subparsers(dest="skills_action")

    skills_propose = skills_sub.add_parser("propose", help="Propose a new skill")
    skills_propose.add_argument(
        "--name", type=str, required=True, help="Skill name (kebab-case)"
    )
    skills_propose.add_argument(
        "--description", type=str, required=True, help="One-line description"
    )
    skills_propose.add_argument(
        "--content-file", type=str, required=True, help="Path to SKILL.md content"
    )
    skills_propose.add_argument(
        "--source-workflow", type=str, required=True, help="Source workflow description"
    )
    skills_propose.add_argument(
        "--proposed-by", type=str, required=True, help="Proposer lane ID"
    )

    skills_review = skills_sub.add_parser("review", help="Review a skill candidate")
    skills_review.add_argument("candidate_id", type=str, help="Candidate ID to review")
    review_group = skills_review.add_mutually_exclusive_group(required=True)
    review_group.add_argument(
        "--approve", action="store_true", help="Approve the candidate"
    )
    review_group.add_argument(
        "--reject", action="store_false", dest="approve", help="Reject the candidate"
    )
    skills_review.add_argument(
        "--reviewed-by", type=str, required=True, help="Reviewer lane ID"
    )
    skills_review.add_argument("--notes", type=str, help="Review notes")

    skills_promote = skills_sub.add_parser("promote", help="Promote an approved skill")
    skills_promote.add_argument(
        "candidate_id", type=str, help="Candidate ID to promote"
    )

    skills_disable = skills_sub.add_parser("disable", help="Disable a promoted skill")
    skills_disable.add_argument("name", type=str, help="Skill name to disable")
    skills_disable.add_argument("--reason", type=str, help="Reason for disabling")
    skills_disable.add_argument(
        "--disabled-by", type=str, default="operator", help="Who is disabling"
    )

    # queue (review queue visibility)
    queue_parser = subparsers.add_parser(
        "queue", help="Local review queue state (request + verdict packets)"
    )
    queue_parser.add_argument(
        "--pr", type=int, default=None, help="Show queue entry for a specific PR number"
    )

    # repairs
    subparsers.add_parser(
        "repairs", help="Post-merge repair queue — eligible issues for autonomous fix"
    )

    # task (Platform-2 task queue)
    task_parser = subparsers.add_parser(
        "task", help="Orchestrator task queue (Platform-2)"
    )
    task_sub = task_parser.add_subparsers(dest="task_action")

    task_list_parser = task_sub.add_parser("list", help="List active task packets")
    task_list_parser.add_argument(
        "--status", default=None, help="Filter by packet status"
    )
    task_list_parser.add_argument("--owner", default=None, help="Filter by owner lane")
    task_list_parser.add_argument(
        "--domain", default=None, help="Filter by execution domain"
    )

    task_show_parser = task_sub.add_parser("show", help="Show a task packet by ID")
    task_show_parser.add_argument("packet_id", help="The packet ID to show")

    task_create_parser = task_sub.add_parser("create", help="Create a new task packet")
    task_create_parser.add_argument(
        "--title", required=True, help="Short imperative task title"
    )
    task_create_parser.add_argument(
        "--owner", default=None, help="Target author lane (e.g. author-a)"
    )
    task_create_parser.add_argument(
        "--priority",
        default="normal",
        choices=["low", "normal", "high"],
        help="Priority: low / normal / high (default: normal)",
    )
    task_create_parser.add_argument(
        "--description", default="", help="Full task description"
    )
    task_create_parser.add_argument(
        "--domain",
        default=None,
        choices=["platform", "browser-game"],
        help="Execution domain for routing (platform / browser-game)",
    )
    task_create_parser.add_argument(
        "--scope",
        action="append",
        default=None,
        dest="scope_declared",
        help="Declared scope file pattern (repeatable)",
    )
    task_create_parser.add_argument(
        "--validation",
        action="append",
        default=None,
        help="Validation command (repeatable)",
    )

    task_approve_parser = task_sub.add_parser(
        "approve", help="Transition a task packet to 'approved' status"
    )
    task_approve_parser.add_argument("packet_id", help="The packet ID to approve")

    task_dispatch_parser = task_sub.add_parser(
        "dispatch",
        help="Approve (optionally) and dispatch a task packet to an author lane",
    )
    task_dispatch_parser.add_argument("packet_id", help="The packet ID to dispatch")
    task_dispatch_parser.add_argument(
        "lane_id", help="Target author lane (e.g. author-a)"
    )
    task_dispatch_parser.add_argument(
        "--approve",
        action="store_true",
        dest="auto_approve",
        help="Auto-approve the packet before dispatching (for pending/previewing packets)",
    )
    task_dispatch_parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Reset worktree to origin/main and clear Claude session before dispatching",
    )
    task_dispatch_parser.add_argument(
        "--no-refresh",
        action="store_true",
        dest="no_auto_refresh",
        default=False,
        help="Skip automatic staleness check and refresh of the target worktree",
    )

    task_accept_parser = task_sub.add_parser(
        "accept",
        help="Accept a dispatched task: ack inbox, notify orchestrator, emit event",
    )
    task_accept_parser.add_argument("packet_id", help="The packet ID to accept")
    task_accept_parser.add_argument(
        "--lane", required=True, dest="lane_id", help="Lane accepting the task"
    )

    task_complete_parser = task_sub.add_parser(
        "complete",
        help="Complete a dispatched task: record result and archive",
    )
    task_complete_parser.add_argument("packet_id", help="The packet ID to complete")
    task_complete_parser.add_argument(
        "--summary", default="", help="Completion summary (one-line description)"
    )
    task_complete_parser.add_argument(
        "--pr", type=int, default=None, dest="pr_number", help="Associated PR number"
    )
    task_complete_parser.add_argument(
        "--by",
        default="",
        dest="completed_by",
        help="Lane or actor completing the task",
    )
    task_complete_parser.add_argument(
        "--no-archive",
        action="store_true",
        dest="no_archive",
        help="Keep the packet in active queue (do not archive)",
    )

    # inbox (Platform-3 message bus)
    inbox_parser = subparsers.add_parser(
        "inbox", help="Communication bus inbox (Platform-3)"
    )
    inbox_sub = inbox_parser.add_subparsers(dest="inbox_action")

    inbox_sub.add_parser("stats", help="Per-lane inbox statistics")

    inbox_ack_parser = inbox_sub.add_parser("ack", help="Acknowledge an inbox message")
    inbox_ack_parser.add_argument("message_id", help="The message ID to acknowledge")
    inbox_ack_parser.add_argument(
        "--lane", required=True, help="Lane whose inbox contains the message"
    )

    inbox_ack_all_parser = inbox_sub.add_parser(
        "ack-all",
        aliases=["bulk-ack"],
        help="Bulk-acknowledge inbox messages",
    )
    inbox_ack_all_parser.add_argument(
        "--lane", required=True, help="Lane whose inbox to bulk-ack"
    )
    inbox_ack_all_parser.add_argument(
        "--filter-summary",
        default=None,
        help="Regex pattern to match against message summary (case-insensitive)",
    )
    inbox_ack_all_parser.add_argument(
        "--max-age",
        type=float,
        default=None,
        help="Only ack messages older than N hours (based on created_at)",
    )

    inbox_purge_parser = inbox_sub.add_parser(
        "purge",
        help="Remove old terminal messages from per-lane inbox files",
    )
    inbox_purge_parser.add_argument(
        "--lane",
        default=None,
        help="Lane to compact (default: all lanes)",
    )
    inbox_purge_parser.add_argument(
        "--max-age",
        type=float,
        default=24.0,
        help="Remove terminal messages older than N hours (default: 24)",
    )

    inbox_parser.add_argument(
        "--lane", default=None, help="Show inbox for a specific lane"
    )
    inbox_parser.add_argument("--status", default=None, help="Filter by message status")
    inbox_parser.add_argument(
        "--type",
        default=None,
        help="Filter by message type (comma-separated for multiple, e.g. completion,escalation)",
    )
    inbox_parser.add_argument("--thread", default=None, help="Filter by thread ID")
    inbox_parser.add_argument(
        "--include-native",
        action="store_true",
        default=False,
        help="Import Claude native inbox messages before listing (requires --lane)",
    )
    inbox_parser.add_argument(
        "--prioritized",
        action="store_true",
        default=False,
        help="Group messages by priority tier (P0/P1/P2). Requires --lane.",
    )

    # message (Platform-3 audit trail)
    message_parser = subparsers.add_parser(
        "message", help="Communication bus message detail (Platform-3)"
    )
    message_sub = message_parser.add_subparsers(dest="message_action")

    message_show_parser = message_sub.add_parser("show", help="Show a message by ID")
    message_show_parser.add_argument("message_id", help="The message ID to show")

    message_send_parser = message_sub.add_parser(
        "send", help="Send a message to another lane's inbox"
    )
    message_send_parser.add_argument(
        "--from", required=True, dest="from_lane", help="Sender lane ID"
    )
    message_send_parser.add_argument(
        "--to", required=True, dest="to_lane", help="Recipient lane ID"
    )
    message_send_parser.add_argument(
        "--type",
        required=True,
        dest="msg_type",
        choices=[
            "ack",
            "progress",
            "blocker",
            "completion",
            "escalation",
            "recovery",
        ],
        help="Message type",
    )
    message_send_parser.add_argument(
        "--summary", required=True, help="One-line message summary"
    )
    message_send_parser.add_argument(
        "--task-id", default=None, dest="task_id", help="Associated task packet ID"
    )
    message_send_parser.add_argument(
        "--thread", default=None, dest="thread_id", help="Thread ID for conversation"
    )
    message_send_parser.add_argument(
        "--priority",
        default="normal",
        choices=["low", "normal", "high", "urgent"],
        help="Message priority (default: normal)",
    )

    # supervisor (Platform-6: supervisor routines and delta summaries)
    supervisor_parser = subparsers.add_parser(
        "supervisor", help="Supervisor cycle: snapshot, delta, recommend (Platform-6)"
    )
    supervisor_parser.add_argument(
        "--save",
        action="store_true",
        default=False,
        help="Persist snapshot for future delta computation",
    )
    supervisor_parser.add_argument(
        "--diff",
        type=str,
        default=None,
        metavar="SNAPSHOT_PATH",
        help="Path to a previous snapshot JSON file to diff against",
    )

    # monitor (SP-3-08: ops monitoring cycle)
    monitor_parser = subparsers.add_parser(
        "monitor", help="Run a single ops monitoring cycle (SP-3-08)"
    )
    monitor_parser.add_argument(
        "--skip-pr-check",
        action="store_true",
        help="Skip the gh pr list check (for testing or offline use)",
    )
    monitor_parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Do not send findings to the orchestrator inbox",
    )
    monitor_parser.add_argument(
        "--no-recovery",
        action="store_true",
        help="Disable stall recovery actions (report only, no re-nudge/escalate)",
    )
    monitor_parser.add_argument(
        "--no-auto-dispatch",
        action="store_true",
        help="Disable auto-dispatch of approved packets to idle lanes",
    )
    monitor_parser.add_argument(
        "--no-reconcile",
        action="store_true",
        help="Skip controller projection update (fleet_status.json) after monitor sweep",
    )

    # fleet (SP-4-07: controller projection read-only view)
    fleet_parser = subparsers.add_parser(
        "fleet", help="Fleet status — controller projection (read-only view)"
    )
    fleet_parser.add_argument(
        "--ack",
        metavar="ITEM_ID",
        help="Acknowledge an item by ID (prefix match)",
    )
    fleet_parser.add_argument(
        "--clear",
        metavar="ITEM_ID",
        help="Clear an item by ID (prefix match)",
    )
    fleet_parser.add_argument(
        "--suppress",
        metavar="ITEM_ID",
        help="Suppress an item by ID (prefix match)",
    )

    # review-check (merged PR review scanning)
    rc_parser = subparsers.add_parser(
        "review-check",
        help="Check recently merged PRs for diff stats and contract issues",
    )
    rc_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of recently merged PRs to check (default: 5)",
    )
    rc_parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Do not send findings to the orchestrator inbox",
    )

    # lane (lane lifecycle management)
    lane_parser = subparsers.add_parser(
        "lane", help="Lane lifecycle management (refresh, etc.)"
    )
    lane_sub = lane_parser.add_subparsers(dest="lane_action")

    lane_refresh_parser = lane_sub.add_parser(
        "refresh",
        help="Reset worktree to origin/main and clear Claude session",
    )
    lane_refresh_parser.add_argument(
        "lane_id",
        nargs="?",
        default=None,
        help="Lane ID to refresh (e.g. author-a)",
    )
    lane_refresh_parser.add_argument(
        "--all-idle",
        action="store_true",
        default=False,
        help="Refresh all lanes without active dispatched packets",
    )
    lane_refresh_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Save dirty worktree diff to /tmp and proceed with reset",
    )

    lane_sub.add_parser(
        "check-approvals",
        help="Check for lanes stuck on tool-approval prompts",
    )

    lane_peek_parser = lane_sub.add_parser(
        "peek",
        help="Capture tmux pane content for a lane (large scrollback buffer)",
    )
    lane_peek_parser.add_argument(
        "lane_id",
        help="Lane ID to peek (e.g. author-a)",
    )
    lane_peek_parser.add_argument(
        "--lines",
        type=int,
        default=80,
        help="Number of scrollback lines to capture (default: 80)",
    )

    # workers (Platform-7: worker pool lifecycle management)
    workers_parser = subparsers.add_parser(
        "workers", help="Worker pool lifecycle management (Platform-7)"
    )
    workers_sub = workers_parser.add_subparsers(dest="workers_action")

    workers_wake = workers_sub.add_parser(
        "wake", help="Wake (open/resume) an author pane"
    )
    workers_wake.add_argument("lane_id", help="Lane ID to wake")

    workers_park = workers_sub.add_parser("park", help="Park an idle author lane")
    workers_park.add_argument("lane_id", help="Lane ID to park")

    workers_retire = workers_sub.add_parser(
        "retire", help="Retire a parked author lane"
    )
    workers_retire.add_argument("lane_id", help="Lane ID to retire")

    workers_dispatch = workers_sub.add_parser(
        "dispatch", help="Dispatch a task packet to an author lane"
    )
    workers_dispatch.add_argument("packet_id", help="Task packet ID to dispatch")
    workers_dispatch.add_argument("lane_id", help="Target lane ID")
    workers_dispatch.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Reset worktree to origin/main and clear Claude session before dispatching",
    )
    workers_dispatch.add_argument(
        "--no-refresh",
        action="store_true",
        dest="no_auto_refresh",
        default=False,
        help="Skip automatic staleness check and refresh of the target worktree",
    )

    workers_maintain = workers_sub.add_parser(
        "maintain", help="Run periodic maintenance (park idle, retire parked)"
    )
    workers_maintain.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Only propose actions without executing them",
    )

    # usage (Token economy: import and query usage data)
    usage_parser = subparsers.add_parser(
        "usage", help="Token economy: import and query usage data"
    )
    usage_sub = usage_parser.add_subparsers(dest="usage_action")

    usage_import_parser = usage_sub.add_parser(
        "import", help="Import native Claude usage data into repo runtime"
    )
    usage_import_parser.add_argument(
        "--usage-dir",
        type=Path,
        default=None,
        help="Path to ~/.claude/usage-data/ (default: auto-detect)",
    )
    usage_import_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: .claude/runtime/token_economy/)",
    )

    usage_attr_parser = usage_sub.add_parser(
        "attribute", help="Attribute sessions to lanes and work outcomes"
    )
    usage_attr_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Token economy store directory (default: .claude/runtime/token_economy/)",
    )

    usage_summary_parser = usage_sub.add_parser(
        "summary", help="Overview of total tokens, sessions, time range"
    )
    usage_summary_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Token economy store directory (default: .claude/runtime/token_economy/)",
    )

    usage_lanes_parser = usage_sub.add_parser(
        "lanes", help="Per-lane breakdown of token usage"
    )
    usage_lanes_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Token economy store directory (default: .claude/runtime/token_economy/)",
    )

    usage_throughput_parser = usage_sub.add_parser(
        "throughput", help="Throughput-normalized token metrics"
    )
    usage_throughput_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Token economy store directory (default: .claude/runtime/token_economy/)",
    )

    usage_ap_parser = usage_sub.add_parser(
        "anti-patterns", help="Detect high-waste usage patterns"
    )
    usage_ap_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Token economy store directory (default: .claude/runtime/token_economy/)",
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
    repo_root = find_repo_root()

    # Stash whether the user explicitly passed --runtime-dir before we apply
    # the default.  cmd_queue() uses this to respect explicit overrides (#1196).
    args._runtime_dir_explicit = args.runtime_dir is not None

    if args.runtime_dir is None:
        args.runtime_dir = repo_root / ".claude" / "runtime"

    if args.plans_dir is None:
        args.plans_dir = repo_root / "plans"

    args.repo_root = repo_root

    # Dispatch
    commands = {
        "status": cmd_status,
        "dashboard": cmd_dashboard,
        "worktrees": cmd_worktrees,
        "events": cmd_events,
        "tick": cmd_tick,
        "health": cmd_health,
        "watchdogs": cmd_watchdogs,
        "recover": cmd_recover,
        "reviews": cmd_reviews,
        "comments": cmd_comments,
        "ci": cmd_ci,
        "daemon": cmd_daemon,
        "retry": cmd_retry,
        "index": cmd_index,
        "query": cmd_query,
        "memory": cmd_memory,
        "compact": cmd_compact,
        "scope": cmd_scope,
        "snapshot": cmd_snapshot,
        "skills": cmd_skills,
        "queue": cmd_queue,
        "repairs": cmd_repairs,
        "task": cmd_task,
        "inbox": cmd_inbox,
        "message": cmd_message,
        "supervisor": cmd_supervisor,
        "monitor": cmd_monitor,
        "fleet": cmd_fleet,
        "review-check": cmd_review_check,
        "lane": cmd_lane,
        "workers": cmd_workers,
        "usage": cmd_usage,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
