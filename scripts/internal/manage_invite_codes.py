#!/usr/bin/env python
"""Admin CLI for managing invite codes.

Usage::

    # Generate 5 new codes
    uv run python scripts/internal/manage_invite_codes.py generate --count 5

    # Generate codes with labels
    uv run python scripts/internal/manage_invite_codes.py generate --count 3 --label "Beta testers"

    # List all codes
    uv run python scripts/internal/manage_invite_codes.py list

    # List only active codes
    uv run python scripts/internal/manage_invite_codes.py list --status active

    # Revoke a code
    uv run python scripts/internal/manage_invite_codes.py revoke ABC12345

Requires ``DATABASE_URL`` env var (or defaults to ``sqlite:///hosted_play.db``).
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure the repo root is importable so ``web.*`` resolves.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from web.db import (  # noqa: E402
    InviteCode,
    create_tables,
    generate_invite_code,
    init_engine,
    make_session_factory,
)


def _get_session():
    """Create a DB session from env-derived config."""
    database_url = os.environ.get("DATABASE_URL", "sqlite:///hosted_play.db")
    engine = init_engine(database_url)
    create_tables(engine)
    factory = make_session_factory(engine)
    return factory()


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate new invite codes."""
    session = _get_session()
    try:
        codes = []
        for _ in range(args.count):
            # Retry on collision (astronomically unlikely but safe)
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

        print(f"Generated {len(codes)} invite code(s):")
        print()
        for c in codes:
            label_suffix = f"  ({args.label})" if args.label else ""
            print(f"  {c}{label_suffix}")
        print()
    finally:
        session.close()


def cmd_list(args: argparse.Namespace) -> None:
    """List invite codes."""
    session = _get_session()
    try:
        query = session.query(InviteCode)
        if args.status:
            query = query.filter_by(status=args.status)
        query = query.order_by(InviteCode.created_at.desc())

        codes = query.all()
        if not codes:
            print("No invite codes found.")
            return

        # Header
        print(
            f"{'Code':<12} {'Status':<10} {'Label':<20} {'Player ID':<12} {'Created':<20} {'Redeemed':<20}"
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
                f"{ic.code:<12} {ic.status:<10} {label:<20} {player_id:<12} {created:<20} {redeemed:<20}"
            )
    finally:
        session.close()


def cmd_revoke(args: argparse.Namespace) -> None:
    """Revoke an invite code."""
    session = _get_session()
    try:
        normalized = args.code.strip().upper()
        invite = session.query(InviteCode).filter_by(code=normalized).first()

        if invite is None:
            print(f"ERROR: Code '{normalized}' not found.", file=sys.stderr)
            sys.exit(1)

        if invite.status == "revoked":
            print(f"Code '{normalized}' is already revoked.")
            return

        old_status = invite.status
        invite.status = "revoked"
        session.commit()

        print(f"Revoked code '{normalized}' (was: {old_status})")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage invite codes for the Bid Euchre browser game"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = subparsers.add_parser("generate", help="Generate new invite codes")
    gen.add_argument(
        "--count", "-n", type=int, default=1, help="Number of codes to generate"
    )
    gen.add_argument(
        "--label", "-l", type=str, default=None, help="Label/note for the codes"
    )

    # list
    lst = subparsers.add_parser("list", help="List invite codes")
    lst.add_argument(
        "--status",
        "-s",
        choices=["active", "redeemed", "revoked"],
        default=None,
        help="Filter by status",
    )

    # revoke
    rev = subparsers.add_parser("revoke", help="Revoke an invite code")
    rev.add_argument("code", type=str, help="The invite code to revoke")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "revoke":
        cmd_revoke(args)


if __name__ == "__main__":
    main()
