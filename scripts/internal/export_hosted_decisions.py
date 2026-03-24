#!/usr/bin/env python
"""CLI wrapper for exporting hosted-play decisions to JSONL.

Reads decisions from the hosted-play SQLite database and writes them
as JSONL records matching the SP-4-01 schema (schema_version 1).

Usage
-----
Export all decisions::

    uv run python scripts/internal/export_hosted_decisions.py \
        --db data/hosted/bideuchre.db \
        --output data/hosted/export/decisions.jsonl

Export decisions for a specific match::

    uv run python scripts/internal/export_hosted_decisions.py \
        --db data/hosted/bideuchre.db \
        --match-uuid a1b2c3d4-... \
        --output data/hosted/export/match_a1b2c3d4.jsonl

Export only human decisions::

    uv run python scripts/internal/export_hosted_decisions.py \
        --db data/hosted/bideuchre.db \
        --human-only \
        --output data/hosted/export/human_decisions.jsonl
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from web.db import init_engine, make_session_factory
    from web.export import export_decisions
except ImportError:
    print(
        "Error: web package not found. Install the hosted extras:\n"
        "  uv sync --extra hosted",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export hosted-play decisions to JSONL (SP-4-01 schema).",
    )
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSONL file path.",
    )
    parser.add_argument(
        "--match-uuid",
        default=None,
        help="Filter to a specific match UUID.",
    )
    parser.add_argument(
        "--human-only",
        action="store_true",
        default=False,
        help="Export only human decisions (actor_type='human').",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the export CLI."""
    args = _parse_args(argv)

    db_path: Path = args.db
    if not db_path.exists():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        return 1

    output_path: Path = args.output
    if output_path.exists() and os.path.samefile(db_path, output_path):
        print(
            "Error: --output resolves to the same file as --db. "
            "This would overwrite the database.",
            file=sys.stderr,
        )
        return 1

    database_url = f"sqlite:///{db_path.resolve()}"
    engine = init_engine(database_url)
    factory = make_session_factory(engine)
    session = factory()

    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        count = export_decisions(
            session,
            args.output,
            match_uuid=args.match_uuid,
            human_only=args.human_only,
        )
    finally:
        session.close()

    print(f"{count} records exported to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
