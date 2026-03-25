"""Alert push evaluator and push state tracking (Platform-9a, PR 1).

Decides when to push unresolved HIGH/URGENT controller items to the
operator's remote channel (e.g., Telegram) when the fleet is idle or
unattended.  This module is **transport-agnostic** — it never imports
Telegram, MCP, or any I/O library.  The caller is responsible for
actually sending the alert.

Key design points:

- ``evaluate_push_needed()`` is a **pure function**: no I/O, no side
  effects.  It takes pre-loaded data and returns a list of items that
  should be pushed.
- Push state tracks per-item-id last-pushed timestamps, push counts,
  and severity at time of push to enable dedup and backoff.
- Re-push triggers: (a) new item never pushed, (b) cooldown elapsed,
  (c) severity escalated since last push.

Usage::

    from bid_euchre.ops.alert_push import (
        evaluate_push_needed,
        load_push_state,
        record_push,
        save_push_state,
    )

    items_to_push = evaluate_push_needed(fleet_status, idle_status, push_state)
    for item in items_to_push:
        # ... send via Telegram or other transport ...
        record_push(push_state, item.item_id, item.severity)
    save_push_state(push_state)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.control_plane import (
    SEVERITY_HIGH,
    SEVERITY_URGENT,
    STATE_OPEN,
    ActionableItem,
    FleetStatus,
)
from bid_euchre.ops.idle_detector import IdleStatus

logger = logging.getLogger("ops.alert_push")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RUNTIME_DIR = Path(".claude/runtime")
PUSH_STATE_FILE = "alert_push_state.json"

# Default cooldown: don't re-push the same item within this many minutes.
DEFAULT_COOLDOWN_MINUTES = 15.0

# Severities eligible for push (only HIGH and URGENT).
PUSHABLE_SEVERITIES = frozenset({SEVERITY_HIGH, SEVERITY_URGENT})

# Severity ranking for escalation detection.
_SEVERITY_RANK: dict[str, int] = {
    "info": 0,
    "warn": 1,
    "high": 2,
    "urgent": 3,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class PushItemRecord:
    """Tracking record for a single item's push history.

    Attributes:
        item_id: The controller item_id being tracked.
        last_pushed_at: ISO 8601 timestamp of the most recent push.
        push_count: Total number of times this item has been pushed.
        severity_at_push: The severity level at the time of the last push.
    """

    item_id: str
    last_pushed_at: str
    push_count: int = 0
    severity_at_push: str = ""


@dataclass
class PushState:
    """Complete push tracking state.

    Stored at ``.claude/runtime/alert_push_state.json``.  Each entry in
    ``items`` tracks a single item_id's push history.
    """

    items: dict[str, PushItemRecord] = field(default_factory=dict)
    last_evaluation_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": {k: asdict(v) for k, v in self.items.items()},
            "last_evaluation_at": self.last_evaluation_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PushState:
        items: dict[str, PushItemRecord] = {}
        for k, v in data.get("items", {}).items():
            items[k] = PushItemRecord(**v)
        return cls(
            items=items,
            last_evaluation_at=data.get("last_evaluation_at", ""),
        )


# ---------------------------------------------------------------------------
# Pure evaluation
# ---------------------------------------------------------------------------


def _severity_escalated(previous: str, current: str) -> bool:
    """Return True if ``current`` severity is higher than ``previous``."""
    return _SEVERITY_RANK.get(current, 0) > _SEVERITY_RANK.get(previous, 0)


def evaluate_push_needed(
    fleet_status: FleetStatus,
    idle_status: IdleStatus,
    push_state: PushState,
    *,
    cooldown_minutes: float = DEFAULT_COOLDOWN_MINUTES,
    now: datetime | None = None,
) -> list[ActionableItem]:
    """Determine which items need to be pushed to the remote channel.

    This is a **pure function** — no I/O, no Telegram calls.

    Rules:
    1. If the fleet is **not idle**, return empty (operator is at terminal).
    2. Only consider **open** items with severity HIGH or URGENT.
    3. For each eligible item:
       a. If never pushed → include.
       b. If severity escalated since last push → include (bypass cooldown).
       c. If cooldown elapsed since last push → include.
       d. Otherwise → skip (dedup).

    Args:
        fleet_status: Current controller projection.
        idle_status: Current fleet idle determination.
        push_state: Previously tracked push history.
        cooldown_minutes: Minimum minutes between re-pushes for the same item.
        now: Override for current time (for testing).

    Returns:
        List of ``ActionableItem`` instances that should be pushed.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Rule 1: No push when fleet is active.
    if not idle_status.idle:
        return []

    now_ts = now.timestamp()
    to_push: list[ActionableItem] = []

    for item in fleet_status.items:
        # Rule 2: Only open HIGH/URGENT items.
        if item.state != STATE_OPEN:
            continue
        if item.severity not in PUSHABLE_SEVERITIES:
            continue

        record = push_state.items.get(item.item_id)

        if record is None:
            # Rule 3a: Never pushed → include.
            to_push.append(item)
            continue

        # Rule 3b: Severity escalated → include (bypass cooldown).
        if _severity_escalated(record.severity_at_push, item.severity):
            to_push.append(item)
            continue

        # Rule 3c: Cooldown elapsed → include.
        try:
            last_ts = datetime.fromisoformat(record.last_pushed_at).timestamp()
        except (ValueError, TypeError):
            # Corrupt timestamp — treat as never pushed.
            to_push.append(item)
            continue

        elapsed_minutes = (now_ts - last_ts) / 60.0
        if elapsed_minutes >= cooldown_minutes:
            to_push.append(item)
            continue

        # Rule 3d: Within cooldown, same severity → skip.

    return to_push


# ---------------------------------------------------------------------------
# Push state mutation
# ---------------------------------------------------------------------------


def record_push(
    push_state: PushState,
    item_id: str,
    severity: str,
    *,
    now: datetime | None = None,
) -> None:
    """Record that an item was pushed to the remote channel.

    Updates the push state in place (does NOT persist to disk — the caller
    should call ``save_push_state()`` after all pushes).

    Args:
        push_state: The mutable push state to update.
        item_id: The item that was pushed.
        severity: The severity of the item at push time.
        now: Override for current time (for testing).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    existing = push_state.items.get(item_id)
    count = (existing.push_count if existing else 0) + 1

    push_state.items[item_id] = PushItemRecord(
        item_id=item_id,
        last_pushed_at=now.isoformat(),
        push_count=count,
        severity_at_push=severity,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _push_state_path(runtime_dir: Path | None = None) -> Path:
    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR
    return runtime_dir / PUSH_STATE_FILE


def load_push_state(runtime_dir: Path | None = None) -> PushState:
    """Load push state from disk.

    Returns a fresh ``PushState`` if the file doesn't exist or is corrupt.
    """
    path = _push_state_path(runtime_dir)
    if not path.exists():
        return PushState()
    try:
        data = json.loads(path.read_text())
        return PushState.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Could not load push state from %s: %s", path, exc)
        return PushState()


def save_push_state(
    push_state: PushState,
    runtime_dir: Path | None = None,
) -> Path:
    """Atomically write push state to disk."""
    path = _push_state_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = push_state.to_dict()
    # Atomic write via temp file + rename.
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), suffix=".tmp", prefix="alert_push_state_"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return path
