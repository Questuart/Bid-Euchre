#!/usr/bin/env python
"""Admin CLI for production database management via Render.

Connects to the production Postgres database using ``RENDER_DATABASE_URL``
(or ``DATABASE_URL``) and provides read/write subcommands for common
operator tasks: player lookups, match summaries, invite code management,
and raw SQL access.

Setup::

    # 1. Get the external connection string from the Render dashboard:
    #    Dashboard → bideuchre-db → Info → External Database URL
    # 2. Export it:
    export RENDER_DATABASE_URL="postgresql://user:pass@host:port/db"

Usage::

    # List all players
    uv run python scripts/internal/render_admin.py players list

    # Find a player by nickname (case-insensitive substring)
    uv run python scripts/internal/render_admin.py players find olivejuice

    # Show match statistics
    uv run python scripts/internal/render_admin.py matches stats

    # List matches for a player
    uv run python scripts/internal/render_admin.py matches list --player-id 1

    # List invite codes
    uv run python scripts/internal/render_admin.py codes list

    # Create an invite code
    uv run python scripts/internal/render_admin.py codes create --label "Beta tester"

    # Run raw SQL (read-only)
    uv run python scripts/internal/render_admin.py db query "SELECT count(*) FROM players"

    # Open interactive psql shell (requires psql installed)
    uv run python scripts/internal/render_admin.py db shell

Requires ``RENDER_DATABASE_URL`` or ``DATABASE_URL`` env var pointing to
a Postgres instance. See docs/01_core/DEPLOYMENT.md § Production DB Access.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print(
        "Error: sqlalchemy not found. Run from repo root with:\n"
        "  uv run python scripts/internal/render_admin.py ...",
        file=sys.stderr,
    )
    raise SystemExit(1)

try:
    from web.db import (
        InviteCode,
        Match,
        Player,
        create_tables,
        generate_invite_code,
        init_engine,
        make_session_factory,
    )
except ModuleNotFoundError:
    print(
        "Error: web package not found. Run from repo root with:\n"
        "  uv run python scripts/internal/render_admin.py ...",
        file=sys.stderr,
    )
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_database_url() -> str:
    """Resolve the production database URL from environment.

    Checks ``RENDER_DATABASE_URL`` first (explicit production), then falls
    back to ``DATABASE_URL``.  Aborts with a clear error if neither is set.
    """
    url = os.environ.get("RENDER_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print(
            "ERROR: No database URL found.\n"
            "Set RENDER_DATABASE_URL (recommended) or DATABASE_URL.\n\n"
            "Get the external URL from the Render dashboard:\n"
            "  Dashboard → bideuchre-db → Info → External Database URL\n\n"
            "Then export it:\n"
            "  export RENDER_DATABASE_URL='postgresql://...'",
            file=sys.stderr,
        )
        sys.exit(1)
    return url


def _mask_url(url: str) -> str:
    """Mask the password in a database URL for safe display."""
    parsed = urlparse(url)
    if parsed.password:
        masked = url.replace(f":{parsed.password}@", ":****@")
        return masked
    return url


def _get_session():
    """Create a DB session from the production URL."""
    database_url = _get_database_url()
    engine = init_engine(database_url)
    create_tables(engine)
    factory = make_session_factory(engine)
    return factory(), database_url


# ---------------------------------------------------------------------------
# Players subcommands
# ---------------------------------------------------------------------------


def cmd_players_list(args: argparse.Namespace) -> None:
    """List all players with nicknames."""
    session, url = _get_session()
    print(f"Connected: {_mask_url(url)}\n")
    try:
        query = session.query(Player).order_by(Player.created_at.desc())
        if args.limit:
            query = query.limit(args.limit)

        players = query.all()
        if not players:
            print("No players found.")
            return

        print(f"{'ID':<6} {'Nickname':<20} {'Link UUID':<40} {'Created':<20}")
        print("-" * 86)
        for p in players:
            created = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "--"
            nickname = (p.nickname or "(none)")[:20]
            uuid_short = (p.link_uuid or "--")[:38]
            print(f"{p.id:<6} {nickname:<20} {uuid_short:<40} {created:<20}")

        print(f"\nTotal: {len(players)} player(s)")
    finally:
        session.close()


def cmd_players_find(args: argparse.Namespace) -> None:
    """Find players by nickname (case-insensitive substring match)."""
    session, url = _get_session()
    print(f"Connected: {_mask_url(url)}\n")
    try:
        search = f"%{args.nickname}%"
        players = (
            session.query(Player)
            .filter(Player.nickname.ilike(search))
            .order_by(Player.created_at.desc())
            .all()
        )

        if not players:
            print(f"No players matching '{args.nickname}' found.")
            return

        print(f"{'ID':<6} {'Nickname':<20} {'Link UUID':<40} {'Created':<20}")
        print("-" * 86)
        for p in players:
            created = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "--"
            nickname = (p.nickname or "(none)")[:20]
            uuid_short = (p.link_uuid or "--")[:38]
            print(f"{p.id:<6} {nickname:<20} {uuid_short:<40} {created:<20}")

        print(f"\nFound: {len(players)} player(s) matching '{args.nickname}'")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Matches subcommands
# ---------------------------------------------------------------------------


def cmd_matches_list(args: argparse.Namespace) -> None:
    """List matches, optionally filtered by player or status."""
    session, url = _get_session()
    print(f"Connected: {_mask_url(url)}\n")
    try:
        query = session.query(Match).order_by(Match.created_at.desc())
        if args.player_id:
            query = query.filter(Match.player_id == args.player_id)
        if args.status:
            query = query.filter(Match.status == args.status)
        if args.limit:
            query = query.limit(args.limit)

        matches = query.all()
        if not matches:
            print("No matches found.")
            return

        print(
            f"{'ID':<6} {'Status':<10} {'Player':<8} {'Model':<12} "
            f"{'Score':<12} {'Hands':<7} {'Created':<20}"
        )
        print("-" * 75)
        for m in matches:
            created = m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else "--"
            score = f"{m.score_human}-{m.score_ai}"
            print(
                f"{m.id:<6} {m.status:<10} {m.player_id:<8} {m.ai_model:<12} "
                f"{score:<12} {m.hands_played:<7} {created:<20}"
            )

        print(f"\nTotal: {len(matches)} match(es)")
    finally:
        session.close()


def cmd_matches_stats(args: argparse.Namespace) -> None:  # noqa: ARG001
    """Show high-level match statistics."""
    session, url = _get_session()
    print(f"Connected: {_mask_url(url)}\n")
    try:
        total = session.query(Match).count()
        active = session.query(Match).filter(Match.status == "active").count()
        complete = session.query(Match).filter(Match.status == "complete").count()
        abandoned = session.query(Match).filter(Match.status == "abandoned").count()
        total_players = session.query(Player).count()
        total_codes = session.query(InviteCode).count()
        active_codes = (
            session.query(InviteCode).filter(InviteCode.status == "active").count()
        )
        redeemed_codes = (
            session.query(InviteCode).filter(InviteCode.status == "redeemed").count()
        )

        print("=== Production Database Stats ===\n")
        print(f"Players:          {total_players}")
        print(
            f"Matches:          {total} (active: {active}, complete: {complete}, "
            f"abandoned: {abandoned})"
        )
        print(
            f"Invite codes:     {total_codes} (active: {active_codes}, "
            f"redeemed: {redeemed_codes})"
        )

        # Per-model breakdown
        if total > 0:
            print("\n--- Matches by AI model ---")
            results = session.execute(
                text(
                    "SELECT ai_model, count(*) as cnt, "
                    "avg(hands_played) as avg_hands "
                    "FROM matches GROUP BY ai_model ORDER BY cnt DESC"
                )
            ).fetchall()
            for row in results:
                print(
                    f"  {row[0]:<15} {row[1]:>5} matches, avg {row[2]:.1f} hands/match"
                )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Codes subcommands (mirrors manage_invite_codes.py for convenience)
# ---------------------------------------------------------------------------


def cmd_codes_list(args: argparse.Namespace) -> None:
    """List invite codes."""
    session, url = _get_session()
    print(f"Connected: {_mask_url(url)}\n")
    try:
        query = session.query(InviteCode)
        if args.status:
            query = query.filter_by(status=args.status)
        query = query.order_by(InviteCode.created_at.desc())

        codes = query.all()
        if not codes:
            print("No invite codes found.")
            return

        print(
            f"{'Code':<12} {'Status':<10} {'Label':<20} "
            f"{'Player ID':<12} {'Created':<20} {'Redeemed':<20}"
        )
        print("-" * 94)
        for ic in codes:
            created = (
                ic.created_at.strftime("%Y-%m-%d %H:%M") if ic.created_at else "--"
            )
            redeemed = (
                ic.redeemed_at.strftime("%Y-%m-%d %H:%M") if ic.redeemed_at else "--"
            )
            label = (ic.label or "--")[:20]
            player_id = str(ic.player_id) if ic.player_id else "--"
            print(
                f"{ic.code:<12} {ic.status:<10} {label:<20} "
                f"{player_id:<12} {created:<20} {redeemed:<20}"
            )

        print(f"\nTotal: {len(codes)} code(s)")
    finally:
        session.close()


def cmd_codes_create(args: argparse.Namespace) -> None:
    """Create new invite codes on production."""
    session, url = _get_session()
    print(f"Connected: {_mask_url(url)}\n")
    try:
        codes = []
        for _ in range(args.count):
            for _attempt in range(10):
                code = generate_invite_code()
                exists = session.query(InviteCode).filter_by(code=code).first()
                if exists is None:
                    break
            else:
                print(
                    "ERROR: Failed to generate unique code after 10 attempts",
                    file=sys.stderr,
                )
                sys.exit(1)

            invite = InviteCode(
                code=code,
                status="active",
                label=args.label,
            )
            session.add(invite)
            codes.append(code)

        session.commit()

        print(f"Created {len(codes)} invite code(s):\n")
        for c in codes:
            label_suffix = f"  ({args.label})" if args.label else ""
            print(f"  {c}{label_suffix}")
        print()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# DB subcommands (raw access)
# ---------------------------------------------------------------------------


def cmd_db_query(args: argparse.Namespace) -> None:
    """Run a read-only SQL query against production."""
    database_url = _get_database_url()
    print(f"Connected: {_mask_url(database_url)}\n")

    engine = create_engine(database_url, echo=False)
    with engine.connect() as conn:
        result = conn.execute(text(args.sql))
        rows = result.fetchall()
        columns = result.keys()

        if not rows:
            print("(no rows)")
            return

        # Print header
        header = "  ".join(f"{c:<20}" for c in columns)
        print(header)
        print("-" * len(header))
        for row in rows:
            print("  ".join(f"{str(v):<20}" for v in row))

        print(f"\n({len(rows)} row(s))")


def cmd_db_shell(args: argparse.Namespace) -> None:  # noqa: ARG001
    """Open an interactive psql shell to the production database.

    Requires ``psql`` to be installed locally.
    """
    database_url = _get_database_url()
    print(f"Connecting: {_mask_url(database_url)}\n")

    # Check psql is available
    try:
        subprocess.run(["psql", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print(
            "ERROR: psql not found. Install it with:\n"
            "  brew install postgresql@16   # macOS\n"
            "  apt install postgresql-client  # Debian/Ubuntu",
            file=sys.stderr,
        )
        sys.exit(1)

    # Launch psql with the connection URL
    try:
        subprocess.run(["psql", database_url], check=False)
    except KeyboardInterrupt:
        print("\nDisconnected.")


def cmd_db_url(args: argparse.Namespace) -> None:  # noqa: ARG001
    """Display the production database URL (masked)."""
    database_url = _get_database_url()
    print(f"Database URL (masked): {_mask_url(database_url)}")

    parsed = urlparse(database_url)
    print(f"\n  Host:     {parsed.hostname}")
    print(f"  Port:     {parsed.port or 5432}")
    print(f"  Database: {parsed.path.lstrip('/')}")
    print(f"  User:     {parsed.username}")
    print(f"  SSL:      {'sslmode' in (parsed.query or '')}")


# ---------------------------------------------------------------------------
# CLI structure
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Production database admin CLI for the Bid Euchre browser game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment:\n"
            "  RENDER_DATABASE_URL  External Postgres URL from Render dashboard\n"
            "  DATABASE_URL         Fallback if RENDER_DATABASE_URL is not set\n"
            "\n"
            "Get the URL from: Render Dashboard → bideuchre-db → Info → "
            "External Database URL"
        ),
    )
    subparsers = parser.add_subparsers(dest="group", required=True)

    # --- players ---
    players = subparsers.add_parser("players", help="Player management")
    players_sub = players.add_subparsers(dest="command", required=True)

    pl = players_sub.add_parser("list", help="List all players")
    pl.add_argument("--limit", "-n", type=int, default=None, help="Limit results")

    pf = players_sub.add_parser("find", help="Find player by nickname")
    pf.add_argument("nickname", help="Nickname substring to search (case-insensitive)")

    # --- matches ---
    matches = subparsers.add_parser("matches", help="Match management")
    matches_sub = matches.add_subparsers(dest="command", required=True)

    ml = matches_sub.add_parser("list", help="List matches")
    ml.add_argument(
        "--player-id", "-p", type=int, default=None, help="Filter by player ID"
    )
    ml.add_argument(
        "--status",
        "-s",
        choices=["active", "complete", "abandoned"],
        default=None,
        help="Filter by status",
    )
    ml.add_argument(
        "--limit", "-n", type=int, default=50, help="Limit results (default: 50)"
    )

    matches_sub.add_parser("stats", help="Show match statistics")

    # --- codes ---
    codes = subparsers.add_parser("codes", help="Invite code management")
    codes_sub = codes.add_subparsers(dest="command", required=True)

    cl = codes_sub.add_parser("list", help="List invite codes")
    cl.add_argument(
        "--status",
        "-s",
        choices=["active", "redeemed", "revoked"],
        default=None,
        help="Filter by status",
    )

    cc = codes_sub.add_parser("create", help="Create invite codes")
    cc.add_argument(
        "--count", "-n", type=int, default=1, help="Number of codes (default: 1)"
    )
    cc.add_argument(
        "--label", "-l", type=str, default=None, help="Label/note for the codes"
    )

    # --- db ---
    db = subparsers.add_parser("db", help="Raw database access")
    db_sub = db.add_subparsers(dest="command", required=True)

    dq = db_sub.add_parser("query", help="Run a SQL query")
    dq.add_argument("sql", help="SQL query to execute")

    db_sub.add_parser("shell", help="Open interactive psql shell")
    db_sub.add_parser("url", help="Display connection URL (masked)")

    args = parser.parse_args()

    dispatch = {
        ("players", "list"): cmd_players_list,
        ("players", "find"): cmd_players_find,
        ("matches", "list"): cmd_matches_list,
        ("matches", "stats"): cmd_matches_stats,
        ("codes", "list"): cmd_codes_list,
        ("codes", "create"): cmd_codes_create,
        ("db", "query"): cmd_db_query,
        ("db", "shell"): cmd_db_shell,
        ("db", "url"): cmd_db_url,
    }

    handler = dispatch.get((args.group, args.command))
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
