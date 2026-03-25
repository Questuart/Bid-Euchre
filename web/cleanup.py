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
