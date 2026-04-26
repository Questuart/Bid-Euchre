"""Operator-facing timestamp normalization to Pacific Time.

Issue #2807 / governing prompt-policy clause "Operator-facing timestamps in
Pacific Time": every operator-visible surface (CLI dashboards, task/inbox
lists, review-driver narration, orchestrator chat, Telegram alerts,
session-end MEMORY.md) renders timestamps in America/Los_Angeles. Machine-
facing artifacts (event logs, message bus payloads, audit trails, git/GitHub
metadata) stay UTC.

Naive datetimes are treated as UTC (the convention used by every emitter in
this codebase). The format string uses a literal ``PT`` suffix rather than
``%Z`` so output is stable across DST (golden tests would otherwise see
PST/PDT drift).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    PT_TZ = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError as exc:
    raise RuntimeError(
        "America/Los_Angeles tzdata not available. Install the 'tzdata' "
        "package (Windows) or the system tzdata package (Linux/macOS)."
    ) from exc


def to_operator_tz(dt: datetime) -> datetime:
    """Convert a datetime to Pacific Time.

    Naive inputs are treated as UTC. Aware inputs are converted via
    ``astimezone``. The returned datetime is timezone-aware in
    America/Los_Angeles.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PT_TZ)


def fmt_operator(dt: datetime) -> str:
    """Format a datetime for operator display: ``YYYY-MM-DD HH:MM PT``.

    The ``PT`` suffix is a literal — using ``%Z`` would emit ``PST`` or
    ``PDT`` depending on the season and break operator-output stability
    across DST transitions.
    """
    return to_operator_tz(dt).strftime("%Y-%m-%d %H:%M PT")


def fmt_operator_iso(value: str | None) -> str:
    """Format an ISO-8601 timestamp string for operator display.

    Convenience wrapper for the many CLI / dashboard sites that hold
    timestamps as strings (e.g. ``"2026-04-26T20:25:00Z"`` from JSON
    payloads). Returns the original string unchanged if it cannot be
    parsed, and ``""`` for ``None``/empty input — call sites format
    operator-readable text and would lose context if a parse failure
    raised.
    """
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return value
    return fmt_operator(dt)
