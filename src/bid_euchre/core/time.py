"""Time utilities for the Bid Euchre framework."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """UTC time in ISO8601 with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
