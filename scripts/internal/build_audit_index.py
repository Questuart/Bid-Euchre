"""Build or rebuild the local audit index.

Usage:
    uv run python scripts/internal/build_audit_index.py [--rebuild] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _repo_utils import find_repo_root


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Build or rebuild the local audit index"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Full rebuild (drop and recreate)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=None,
        help="Override runtime directory",
    )
    parser.add_argument(
        "--plans-dir",
        type=Path,
        default=None,
        help="Override plans directory",
    )

    args = parser.parse_args(argv)

    repo_root = find_repo_root()
    runtime_dir = args.runtime_dir or (repo_root / ".claude" / "runtime")
    plans_dir = args.plans_dir or (repo_root / "plans")
    index_dir = runtime_dir / "audit_index"

    from bid_euchre.ops.index import build_index, format_stats_json, get_stats

    result = build_index(
        index_dir,
        runtime_dir=runtime_dir,
        plans_dir=plans_dir,
        full_rebuild=args.rebuild,
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
        mode = "REBUILD" if args.rebuild else "BUILD"
        print(f"=== Audit Index {mode} ===")
        print()
        print(f"Sources indexed: {result.sources_indexed}")
        print(f"Entries indexed: {result.entries_indexed}")
        print(f"Duration: {result.duration_seconds:.3f}s")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for err in result.errors:
                print(f"  - {err}")

        print(f"\nDatabase: {stats.db_path}")
        print(f"Total entries: {stats.total_entries}")

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
