"""Middleware and guards for the Bid Euchre browser game.

Rate-limiting and request-level guards that protect the hosted-play
application from resource exhaustion during the pilot phase.
"""

from __future__ import annotations

from web.db import Match

# Maximum number of active matches a single player may have concurrently.
MAX_ACTIVE_MATCHES_PER_PLAYER = 5


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
