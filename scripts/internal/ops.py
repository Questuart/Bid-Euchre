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
    if result.stopped_reason == "error" or result.errors:
        return 1
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    """Evaluate retry/reroute policy for a task and optionally emit events."""
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

    # No subcommand — show help
    print("Usage: ops.py scope {show|set|touch} --task TASK_ID ...", file=sys.stderr)
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
    retry_parser.add_argument(
        "--emit",
        action="store_true",
        help="Emit durable event for the policy decision (default: off)",
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

    if args.runtime_dir is None:
        args.runtime_dir = repo_root / ".claude" / "runtime"

    if args.plans_dir is None:
        args.plans_dir = repo_root / "plans"

    args.repo_root = repo_root

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
        "index": cmd_index,
        "query": cmd_query,
        "memory": cmd_memory,
        "compact": cmd_compact,
        "scope": cmd_scope,
        "snapshot": cmd_snapshot,
    }

    handler = commands.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
