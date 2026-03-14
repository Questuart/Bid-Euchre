"""Heartbeat mechanism for orchestrator stall detection.

The orchestrator writes a heartbeat file periodically during execution.
External watchdogs (scripts, hooks, humans) can check the heartbeat to
detect when an orchestrator agent has silently died.

The heartbeat file lives at ``plans/arc_d_v2/<rung>/heartbeat`` and contains
a single line with a Unix timestamp (``time.time()``).
"""

from __future__ import annotations

import time

from bid_euchre.arc_d_v2 import paths


def write_heartbeat(rung: str) -> None:
    """Write current timestamp to heartbeat file for stall detection."""
    heartbeat_path = paths.rung_heartbeat(rung)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_path.write_text(f"{time.time()}\n")


def check_heartbeat(rung: str, max_stale_seconds: int = 300) -> bool:
    """Check if heartbeat is fresh.

    Returns True if alive (heartbeat exists and is recent),
    False if stale or missing.
    """
    heartbeat_path = paths.rung_heartbeat(rung)
    if not heartbeat_path.exists():
        return False  # No heartbeat = not running
    try:
        ts = float(heartbeat_path.read_text().strip())
        age = time.time() - ts
        return age < max_stale_seconds
    except (ValueError, OSError):
        return False


def clear_heartbeat(rung: str) -> None:
    """Remove heartbeat file when orchestrator completes normally."""
    heartbeat_path = paths.rung_heartbeat(rung)
    if heartbeat_path.exists():
        heartbeat_path.unlink()
