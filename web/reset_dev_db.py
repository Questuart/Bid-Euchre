"""Dev database reset utility for the Bid Euchre browser game.

Clears game data (matches, hands, decisions, comments) while preserving
player accounts and invite codes.  Intended for pre-launch cleanup of
test/bot data accumulated during development.

Usage::

    # Preview what would be deleted (dry run)
    uv run python -m web.reset_dev_db --dry-run

    # Reset game data, keep players and invite codes
    uv run python -m web.reset_dev_db --yes

    # Full nuke — clear everything including players and invite codes
    uv run python -m web.reset_dev_db --full --yes

    # Custom DATABASE_URL
    DATABASE_URL=sqlite:///mydev.db uv run python -m web.reset_dev_db --yes

Environment variables
---------------------
Uses the same ``DATABASE_URL`` as the web application (see ``web.config``).
Defaults to ``sqlite:///hosted_play.db`` when unset.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_config
from .db import (
    Comment,
    Decision,
    Hand,
    InviteCode,
    Match,
    Player,
    init_engine,
    make_session_factory,
)


@dataclass
class ResetResult:
    """Counts of rows deleted per table."""

    decisions: int = 0
    hands: int = 0
    comments: int = 0
    matches: int = 0
    invite_codes: int = 0
    players: int = 0


def get_counts(session: Session) -> dict[str, int]:
    """Return row counts for all game-related tables."""
    return {
        "players": session.query(Player).count(),
        "invite_codes": session.query(InviteCode).count(),
        "matches": session.query(Match).count(),
        "hands": session.query(Hand).count(),
        "decisions": session.query(Decision).count(),
        "comments": session.query(Comment).count(),
    }


def reset_game_data(session: Session, *, full: bool = False) -> ResetResult:
    """Delete game data from the database.

    Parameters
    ----------
    session:
        An open SQLAlchemy session.  Caller is responsible for commit/rollback.
    full:
        If True, also delete players and invite codes (complete reset).
        If False (default), only delete matches, hands, decisions, and
        comments — preserving player accounts and invite codes.

    Returns
    -------
    ResetResult
        Counts of rows deleted from each table.
    """
    result = ResetResult()

    # Delete in FK-safe order: children before parents
    result.decisions = session.query(Decision).delete()
    result.hands = session.query(Hand).delete()
    result.comments = session.query(Comment).delete()
    result.matches = session.query(Match).delete()

    if full:
        result.invite_codes = session.query(InviteCode).delete()
        result.players = session.query(Player).delete()

    return result


def _reset_sqlite_sequences(session: Session, *, full: bool = False) -> None:
    """Reset SQLite autoincrement counters for cleared tables.

    SQLite tracks autoincrement via the ``sqlite_sequence`` table.  After
    deleting all rows, resetting the sequence ensures new rows start from
    ID 1 for a clean-slate feel.

    No-op if ``sqlite_sequence`` does not exist (e.g. Postgres, or tables
    that have never had an insert with AUTOINCREMENT).
    """
    game_tables = ["decisions", "hands", "comments", "matches"]
    account_tables = ["invite_codes", "players"]
    tables = game_tables + (account_tables if full else [])

    try:
        for table in tables:
            session.execute(
                text("DELETE FROM sqlite_sequence WHERE name = :name"),
                {"name": table},
            )
    except Exception:
        # sqlite_sequence may not exist — safe to ignore
        pass


def _format_result(result: ResetResult, *, full: bool) -> str:
    """Format the reset result as a human-readable summary."""
    lines = [
        f"  decisions:    {result.decisions}",
        f"  hands:        {result.hands}",
        f"  comments:     {result.comments}",
        f"  matches:      {result.matches}",
    ]
    if full:
        lines.extend(
            [
                f"  invite_codes: {result.invite_codes}",
                f"  players:      {result.players}",
            ]
        )
    return "\n".join(lines)


def _format_counts(counts: dict[str, int]) -> str:
    """Format table counts as a human-readable summary."""
    return "\n".join(f"  {table}: {count}" for table, count in counts.items())


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for dev database reset."""
    parser = argparse.ArgumentParser(
        description="Reset the dev database — clear game data before go-live.",
        epilog=(
            "Default mode preserves player accounts and invite codes.\n"
            "Use --full to clear everything."
        ),
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also delete players and invite codes (complete reset)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without making changes",
    )
    args = parser.parse_args(argv)

    # Use same config resolution as the web app
    config = get_config()
    db_url = config.database_url

    print(f"Database: {db_url}")

    engine = init_engine(db_url)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        counts = get_counts(session)
        print(f"\nCurrent row counts:\n{_format_counts(counts)}")

        game_total = (
            counts["matches"]
            + counts["hands"]
            + counts["decisions"]
            + counts["comments"]
        )
        if args.full:
            game_total += counts["players"] + counts["invite_codes"]

        if game_total == 0:
            print("\nDatabase is already empty — nothing to reset.")
            return 0

        if args.dry_run:
            mode = (
                "FULL (including players and invite codes)"
                if args.full
                else "game data only"
            )
            print(f"\nDry run — would delete {game_total} rows ({mode}).")
            return 0

        # Confirmation gate
        if not args.yes:
            mode = (
                "ALL data (including players and invite codes)"
                if args.full
                else "game data (preserving players and invite codes)"
            )
            prompt = f"\nThis will delete {mode}. Continue? [y/N] "
            answer = input(prompt).strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted.")
                return 1

        result = reset_game_data(session, full=args.full)

        # Reset autoincrement counters for SQLite
        if db_url.startswith("sqlite"):
            _reset_sqlite_sequences(session, full=args.full)

        session.commit()

        mode = "Full reset" if args.full else "Game data reset"
        print(f"\n{mode} complete. Rows deleted:")
        print(_format_result(result, full=args.full))

        # Show remaining data
        remaining = get_counts(session)
        if remaining["players"] > 0 or remaining["invite_codes"] > 0:
            print(
                f"\nPreserved:\n  players:      {remaining['players']}\n  invite_codes: {remaining['invite_codes']}"
            )

        return 0

    except Exception as exc:
        session.rollback()
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
