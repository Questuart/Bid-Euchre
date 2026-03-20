"""Build or update curated memory entries.

Usage:
    uv run python scripts/internal/build_curated_memory.py [--json] list [--category CAT]
    uv run python scripts/internal/build_curated_memory.py [--json] add --category CAT --key KEY --value VALUE --source FILE --by AGENT [--tags TAG1,TAG2]
    uv run python scripts/internal/build_curated_memory.py [--json] remove --id ENTRY_ID
    uv run python scripts/internal/build_curated_memory.py [--json] search --text TEXT
    uv run python scripts/internal/build_curated_memory.py [--json] validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _repo_utils import find_repo_root


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Build or update curated memory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=None,
        help="Override memory directory",
    )

    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # list
    list_parser = subparsers.add_parser("list", help="List memory entries")
    list_parser.add_argument("--category", type=str, default=None)
    list_parser.add_argument("--tag", type=str, default=None)

    # add
    add_parser = subparsers.add_parser("add", help="Add a memory entry")
    add_parser.add_argument("--category", type=str, required=True)
    add_parser.add_argument("--key", type=str, required=True)
    add_parser.add_argument("--value", type=str, required=True)
    add_parser.add_argument("--source", type=str, required=True)
    add_parser.add_argument("--by", type=str, required=True)
    add_parser.add_argument("--tags", type=str, default="")

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove an entry")
    remove_parser.add_argument("--id", type=str, required=True, dest="entry_id")

    # search
    search_parser = subparsers.add_parser("search", help="Search entries")
    search_parser.add_argument("--text", type=str, required=True)

    # validate
    subparsers.add_parser("validate", help="Validate all entries")

    args = parser.parse_args(argv)

    if not args.action:
        parser.print_help()
        return 1

    repo_root = find_repo_root()
    memory_dir = args.memory_dir or (
        repo_root / ".claude" / "runtime" / "curated_memory"
    )

    from bid_euchre.ops.memory import (
        add_entry,
        format_memory_json,
        format_memory_text,
        list_entries,
        load_memory,
        remove_entry,
        search_entries,
        validate_provenance,
    )

    if args.action == "list":
        entries = list_entries(
            memory_dir,
            category=getattr(args, "category", None),
            tag=getattr(args, "tag", None),
        )
        if args.json:
            print(json.dumps(format_memory_json(entries), indent=2))
        else:
            print(format_memory_text(entries))
        return 0

    elif args.action == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        try:
            entry = add_entry(
                memory_dir,
                category=args.category,
                key=args.key,
                value=args.value,
                source_file=args.source,
                added_by=args.by,
                tags=tags,
                check_source_exists=True,
            )
            if args.json:
                print(json.dumps(entry.to_dict(), indent=2))
            else:
                print(f"Added: {entry.key} ({entry.category})")
                print(f"  ID: {entry.entry_id}")
                if entry.supersedes:
                    print(f"  Supersedes: {entry.supersedes}")
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    elif args.action == "remove":
        if remove_entry(memory_dir, args.entry_id):
            if args.json:
                print(json.dumps({"removed": args.entry_id}))
            else:
                print(f"Removed: {args.entry_id}")
            return 0
        else:
            print(f"Entry not found: {args.entry_id}", file=sys.stderr)
            return 1

    elif args.action == "search":
        entries = search_entries(memory_dir, args.text)
        if args.json:
            print(json.dumps(format_memory_json(entries), indent=2))
        else:
            print(format_memory_text(entries))
        return 0

    elif args.action == "validate":
        store = load_memory(memory_dir)
        all_valid = True
        results = []

        for entry in store.entries:
            result = validate_provenance(entry, check_source_exists=True)
            results.append(
                {
                    "entry_id": entry.entry_id,
                    "key": entry.key,
                    **{"valid": result.valid, "errors": result.errors},
                }
            )
            if not result.valid:
                all_valid = False

        if args.json:
            print(json.dumps({"all_valid": all_valid, "results": results}, indent=2))
        else:
            if all_valid:
                print(f"All {len(store.entries)} entries valid.")
            else:
                print("Validation errors found:")
                for r in results:
                    if not r["valid"]:
                        print(f"  {r['entry_id']} ({r['key']}): {r['errors']}")
        return 0 if all_valid else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
