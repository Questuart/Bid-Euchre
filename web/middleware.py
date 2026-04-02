"""Middleware and guards for the Bid Euchre browser game.

Rate-limiting, session-tracking, and request-level guards that protect
the hosted-play application from resource exhaustion during the pilot
phase and support transparent session reconnection.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.responses import Response

from web.db import Match, Player

# Maximum number of active matches a single player may have concurrently.
MAX_ACTIVE_MATCHES_PER_PLAYER = 5

# Cookie name used to remember the player's link_uuid across visits.
PLAYER_COOKIE_NAME = "bid_euchre_player"

# Cookie max-age: 30 days (seconds).
PLAYER_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


def check_match_limit(session, player_id: int) -> bool:
    """Return True if the player is within the active match limit.

    Counts matches with ``status='active'`` for the given *player_id*.
    Returns ``False`` (limit exceeded) when the count reaches or exceeds
    :data:`MAX_ACTIVE_MATCHES_PER_PLAYER`.
    """
    active_count = (
        session.query(Match).filter_by(player_id=player_id, status="active").count()
    )
    return active_count < MAX_ACTIVE_MATCHES_PER_PLAYER


def get_player_link_from_cookie(request: Request) -> Optional[str]:
    """Extract the player ``link_uuid`` from the session cookie.

    Returns ``None`` when no cookie is set or the value is empty.
    """
    value = request.cookies.get(PLAYER_COOKIE_NAME, "").strip()
    return value if value else None


def set_player_cookie(response: Response, link_uuid: str) -> None:
    """Attach the player session cookie to *response*.

    The cookie is ``HttpOnly``, ``SameSite=Lax``, and valid for
    :data:`PLAYER_COOKIE_MAX_AGE` seconds.  ``secure`` is omitted so the
    cookie works over plain HTTP during local development.
    """
    response.set_cookie(
        key=PLAYER_COOKIE_NAME,
        value=link_uuid,
        max_age=PLAYER_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def lookup_active_match(session, link_uuid: str) -> Optional[dict]:
    """Look up a player by *link_uuid* and return active-match info.

    Returns a dict with keys ``link_uuid``, ``nickname``, and
    ``match_uuid`` when a valid player with an active match is found.
    Returns ``None`` otherwise (player not found, no nickname set, or no
    active match).
    """
    player = session.query(Player).filter_by(link_uuid=link_uuid).first()
    if player is None or not player.nickname:
        return None

    match_row = (
        session.query(Match)
        .filter_by(player_id=player.id, status="active")
        .order_by(Match.created_at.desc())
        .first()
    )
    if match_row is None:
        return None

    return {
        "link_uuid": link_uuid,
        "nickname": player.nickname,
        "match_uuid": match_row.match_uuid,
    }
