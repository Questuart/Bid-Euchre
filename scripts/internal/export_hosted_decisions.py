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
import json
import sys
from pathlib import Path

try:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from web.db import Decision, Hand, Match, init_engine, make_session_factory
    from web.export import decision_to_jsonl
except ImportError as exc:
    print(
        "Error: missing dependencies for export CLI.\n"
        "Install the web extras:  uv sync --extra web\n"
        f"  ({exc})",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def _build_query(
    *,
    match_uuid: str | None = None,
    human_only: bool = False,
):
    """Build a SQLAlchemy select for decisions with match and hand context.

    Returns a select() that yields (Decision, Match, Hand) tuples,
    ordered by match_id, hand turn_number for deterministic output.
    """
    stmt = (
        select(Decision, Match, Hand)
        .join(Match, Decision.match_id == Match.id)
        .join(Hand, Decision.hand_id == Hand.id)
        .order_by(Decision.match_id, Hand.hand_number, Decision.turn_number)
    )

    if match_uuid is not None:
        stmt = stmt.where(Match.match_uuid == match_uuid)

    if human_only:
        stmt = stmt.where(Decision.actor_type == "human")

    return stmt


def export_decisions(
    session: Session,
    output_path: Path,
    *,
    match_uuid: str | None = None,
    human_only: bool = False,
) -> int:
    """Query decisions and write JSONL to *output_path*.

    Parameters
    ----------
    session:
        Active SQLAlchemy session.
    output_path:
        Destination file path. Parent directories are created if needed.
    match_uuid:
        If provided, restrict export to this match UUID.
    human_only:
        If True, restrict export to human decisions only.

    Returns
    -------
    int
        Number of records written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stmt = _build_query(match_uuid=match_uuid, human_only=human_only)
    result = session.execute(stmt).yield_per(500)

    count = 0
    with open(output_path, "w") as fh:
        for decision_row, match_row, hand_row in result:
            record = decision_to_jsonl(decision_row, match_row, hand_row)
            fh.write(json.dumps(record) + "\n")
            count += 1

    return count


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
    output_path: Path = args.output

    if not db_path.exists():
        print(f"Error: database not found: {db_path}", file=sys.stderr)
        return 1

    if db_path.resolve() == output_path.resolve():
        print(
            "Error: --output resolves to the same path as --db; "
            "refusing to overwrite the source database.",
            file=sys.stderr,
        )
        return 1

    database_url = f"sqlite:///{db_path.resolve()}"
    engine = init_engine(database_url)
    factory = make_session_factory(engine)
    session = factory()

    try:
        count = export_decisions(
            session,
            output_path,
            match_uuid=args.match_uuid,
            human_only=args.human_only,
        )
    finally:
        session.close()

    print(f"{count} records exported to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
