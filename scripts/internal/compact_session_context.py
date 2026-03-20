"""Compact and archive session context.

Usage:
    uv run python scripts/internal/compact_session_context.py [--json] compact \
        --session-id SESSION_ID --lane LANE --context-file FILE \
        [--summary TEXT] [--outcome TEXT] [--pr PR1,PR2]
    uv run python scripts/internal/compact_session_context.py [--json] list
    uv run python scripts/internal/compact_session_context.py [--json] show --session-id SESSION_ID
    uv run python scripts/internal/compact_session_context.py [--json] artifacts --session-id SESSION_ID
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _repo_utils import find_repo_root


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Compact and archive session context")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=None,
        help="Override archive directory",
    )

    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # compact
    compact_parser = subparsers.add_parser("compact", help="Compact session context")
    compact_parser.add_argument(
        "--session-id", type=str, required=True, help="Session identifier"
    )
    compact_parser.add_argument("--lane", type=str, required=True, help="Lane ID")
    compact_parser.add_argument(
        "--context-file",
        type=Path,
        required=True,
        help="Path to context file to archive",
    )
    compact_parser.add_argument(
        "--artifacts-file",
        type=Path,
        default=None,
        help="JSON file listing touched artifacts",
    )
    compact_parser.add_argument("--summary", type=str, default="")
    compact_parser.add_argument("--task", type=str, default="")
    compact_parser.add_argument("--outcome", type=str, default="")
    compact_parser.add_argument("--pr", type=str, default="")

    # list
    subparsers.add_parser("list", help="List archived sessions")

    # show
    show_parser = subparsers.add_parser(
        "show", help="Show metadata for an archived session"
    )
    show_parser.add_argument("--session-id", type=str, required=True)

    # artifacts
    artifacts_parser = subparsers.add_parser(
        "artifacts", help="Show touched artifacts for an archived session"
    )
    artifacts_parser.add_argument("--session-id", type=str, required=True)

    args = parser.parse_args(argv)

    if not args.action:
        parser.print_help()
        return 1

    repo_root = find_repo_root()
    archive_dir = args.archive_dir or (
        repo_root / ".claude" / "runtime" / "session_archive"
    )

    from bid_euchre.ops.compaction import (
        ArtifactRef,
        compact_session,
        format_archives_text,
        format_compaction_json,
        format_compaction_text,
        get_archive,
        get_archive_artifacts,
        list_archives,
    )

    if args.action == "compact":
        # Read context file
        context_file = args.context_file
        if not context_file.exists():
            print(f"Error: context file not found: {context_file}", file=sys.stderr)
            return 1

        context_text = context_file.read_text()

        # Read artifacts if provided
        artifacts: list[ArtifactRef] = []
        if args.artifacts_file and args.artifacts_file.exists():
            try:
                data = json.loads(args.artifacts_file.read_text())
                artifacts = [ArtifactRef.from_dict(a) for a in data]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: failed to load artifacts: {e}", file=sys.stderr)

        # Parse PR numbers
        pr_numbers: list[int] = []
        if args.pr:
            for p in args.pr.split(","):
                try:
                    pr_numbers.append(int(p.strip()))
                except ValueError:
                    pass

        result = compact_session(
            session_id=args.session_id,
            lane_id=args.lane,
            context_text=context_text,
            artifacts=artifacts,
            summary=args.summary,
            task_description=args.task,
            outcome=args.outcome,
            pr_numbers=pr_numbers,
            archive_dir=archive_dir,
        )

        if args.json:
            print(json.dumps(format_compaction_json(result), indent=2))
        else:
            print(format_compaction_text(result))

        return 0 if result.success else 1

    elif args.action == "list":
        archives = list_archives(archive_dir)
        if args.json:
            from bid_euchre.ops.compaction import format_archives_json

            print(json.dumps(format_archives_json(archives), indent=2))
        else:
            print(format_archives_text(archives))
        return 0

    elif args.action == "show":
        archive = get_archive(args.session_id, archive_dir)
        if archive is None:
            print(f"Archive not found: {args.session_id}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(archive.to_dict(), indent=2))
        else:
            print(f"Session: {archive.session_id}")
            print(f"Lane: {archive.lane_id}")
            print(f"Start: {archive.start_time}")
            print(f"End: {archive.end_time or '?'}")
            print(f"Summary: {archive.summary or '(none)'}")
            print(f"Task: {archive.task_description or '(none)'}")
            print(f"Outcome: {archive.outcome or '(none)'}")
            if archive.pr_numbers:
                print(f"PRs: {archive.pr_numbers}")
            size_kb = archive.context_size_bytes / 1024
            print(f"Context: {size_kb:.1f} KB")
            print(f"Archived: {archive.archived_at}")
        return 0

    elif args.action == "artifacts":
        artifacts_list = get_archive_artifacts(args.session_id, archive_dir)
        if args.json:
            print(json.dumps([a.to_dict() for a in artifacts_list], indent=2))
        else:
            if not artifacts_list:
                print("No artifacts recorded.")
            else:
                print(f"Artifacts ({len(artifacts_list)}):")
                for a in artifacts_list:
                    ts = f" ({a.timestamp})" if a.timestamp else ""
                    print(f"  [{a.action:10s}] {a.path}{ts}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
