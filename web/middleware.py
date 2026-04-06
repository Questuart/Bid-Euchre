"""Middleware and guards for the Bid Euchre browser game.

Rate-limiting, session-tracking, and request-level guards that protect
the hosted-play application from resource exhaustion during the pilot
phase and support transparent session reconnection.

Includes :class:`RequestLoggingMiddleware` for structured request-level
logging with per-request correlation IDs.
"""

from __future__ import annotations

import contextvars
import logging
import time
import uuid
from typing import Optional

from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from web.db import Match, Player

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-ID context variable — available to all route handlers via
# get_request_id() for log correlation.
# ---------------------------------------------------------------------------

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    """Return the current request's correlation ID (empty outside a request)."""
    return request_id_var.get()


class _RequestIdFilter(logging.Filter):
    """Inject ``request_id`` into every log record for the JSON formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        return True


# Attach the filter to the root logger so all loggers inherit it.
logging.getLogger().addFilter(_RequestIdFilter())

# Paths to exclude from verbose request logging (health probes generate
# high-frequency traffic that would drown out meaningful entries).
_QUIET_PATHS: frozenset[str] = frozenset({"/health", "/ready"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log structured request_start / request_complete events for every HTTP request.

    * Assigns a UUID4 ``request_id`` to each request via :data:`request_id_var`.
    * Logs ``request_start`` on entry with method, path, and client IP.
    * Logs ``request_complete`` on exit with status code and duration in ms.
    * Health and readiness probe paths are logged at DEBUG level to reduce
      noise on free-tier log providers.
    """

    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        token = request_id_var.set(rid)

        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else ""

        # Use DEBUG for noisy health-check paths, INFO for everything else.
        level = logging.DEBUG if path in _QUIET_PATHS else logging.INFO

        logger.log(
            level,
            "request_start method=%s path=%s client_ip=%s request_id=%s",
            method,
            path,
            client_ip,
            rid,
        )

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            logger.log(
                logging.ERROR,
                "request_error method=%s path=%s duration_ms=%.1f request_id=%s",
                method,
                path,
                duration_ms,
                rid,
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.log(
            level,
            "request_complete method=%s path=%s status_code=%d duration_ms=%.1f request_id=%s",
            method,
            path,
            response.status_code,
            duration_ms,
            rid,
        )
        return response


# Cookie name used to remember the player's link_uuid across visits.
PLAYER_COOKIE_NAME = "bid_euchre_player"

# Cookie max-age: 30 days (seconds).
PLAYER_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


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
