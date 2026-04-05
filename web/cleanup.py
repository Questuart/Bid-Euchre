"""Session cleanup utilities for the Bid Euchre browser game.

Expires stale matches that have been active for longer than the configured
timeout.  Designed to be called periodically (e.g. on startup, via a
background task, or an admin endpoint).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .db import Match

logger = logging.getLogger(__name__)

# Default threshold: matches active for more than 24 hours are abandoned.
DEFAULT_MAX_MATCH_AGE = timedelta(hours=24)

# Per-player on-create cleanup: abandon a player's matches idle for >2 hours
# when they create a new one.  Shorter than the startup threshold because
# this runs per-request and should catch recent orphans quickly (#2211).
PLAYER_STALE_MATCH_AGE = timedelta(hours=2)


def expire_stale_matches(
    session: Session,
    *,
    max_age: timedelta = DEFAULT_MAX_MATCH_AGE,
) -> int:
    """Mark active matches older than *max_age* as ``'abandoned'``.

    Parameters
    ----------
    session:
        An open SQLAlchemy session (caller is responsible for commit).
    max_age:
        Maximum age for active matches.  Matches whose ``created_at``
        is older than ``now - max_age`` will be marked abandoned.

    Returns
    -------
    int
        Number of matches expired.
    """
    cutoff = datetime.now(timezone.utc) - max_age
    stale = (
        session.query(Match)
        .filter(Match.status == "active", Match.created_at < cutoff)
        .all()
    )

    now = datetime.now(timezone.utc)
    for match in stale:
        match.status = "abandoned"
        match.completed_at = now

    count = len(stale)
    if count > 0:
        logger.info("Expired %d stale match(es) older than %s", count, max_age)

    return count


def expire_player_stale_matches(
    session: Session,
    player_id: int,
    *,
    max_age: timedelta = PLAYER_STALE_MATCH_AGE,
) -> int:
    """Abandon a specific player's active matches older than *max_age*.

    Called when a player creates a new match to self-heal orphaned matches
    from previous sessions (browser closed, network loss, etc.).  This
    prevents the per-player rate limit from permanently blocking players
    who accumulated abandoned matches (#2211).

    Parameters
    ----------
    session:
        An open SQLAlchemy session (caller is responsible for commit).
    player_id:
        The player whose matches to inspect.
    max_age:
        Maximum age for the player's active matches (default 2 hours).

    Returns
    -------
    int
        Number of matches expired for this player.
    """
    cutoff = datetime.now(timezone.utc) - max_age
    stale = (
        session.query(Match)
        .filter(
            Match.player_id == player_id,
            Match.status == "active",
            Match.created_at < cutoff,
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    for match in stale:
        match.status = "abandoned"
        match.completed_at = now

    count = len(stale)
    if count > 0:
        logger.info(
            "Expired %d stale match(es) for player %d (older than %s)",
            count,
            player_id,
            max_age,
        )

    return count


def abandon_player_active_matches(
    session: Session,
    player_id: int,
) -> int:
    """Abandon **all** active matches for a player.

    Called when a player creates a new match to ensure at most one active
    match exists per player.  Unlike :func:`expire_player_stale_matches`,
    this has no age threshold — every active match is abandoned regardless
    of how recently it was created.

    This prevents stale active matches from shadowing newer completed
    matches on page refresh (#2467).

    Parameters
    ----------
    session:
        An open SQLAlchemy session (caller is responsible for commit).
    player_id:
        The player whose active matches to abandon.

    Returns
    -------
    int
        Number of matches abandoned.
    """
    active = (
        session.query(Match)
        .filter(
            Match.player_id == player_id,
            Match.status == "active",
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    for match in active:
        match.status = "abandoned"
        match.completed_at = now

    count = len(active)
    if count > 0:
        logger.info(
            "Abandoned %d active match(es) for player %d before new match",
            count,
            player_id,
        )

    return count
