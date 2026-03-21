"""Durable lane-to-lane communication bus (Platform-3, v1 foundation).

Provides the core data contract for structured inter-lane messaging:
- ``BusMessage`` — a frozen dataclass representing a single message
- Append-only JSONL audit trail at ``<shared_root>/message_bus/messages.jsonl``
- Per-lane JSONL inbox files at ``<shared_root>/message_bus/inbox/<lane_id>.jsonl``
- Delivery semantics: ack, resolve, TTL expiry, dead-letter

Storage layout::

    <shared_root>/message_bus/
        messages.jsonl          # Global audit trail (append-only)
        .messages.lock          # flock file for audit trail
        inbox/
            orchestrator.jsonl  # Per-lane inbox
            author-a.jsonl
            review.jsonl
            ...

The bus stores and queries messages. It does not actively push or poll.
Delivery automation (supervisor checking inboxes, retry loops) belongs to
later platform slices.

Cross-worktree visibility is guaranteed via ``shared_bus_root()``, which
derives the path from ``git rev-parse --git-common-dir``.
"""

from __future__ import annotations

import fcntl
import functools
import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.message_bus")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BUS_DIR = Path(".claude/runtime/message_bus")
MESSAGES_FILE = "messages.jsonl"
LOCK_FILE = ".messages.lock"
INBOX_DIR = "inbox"

VALID_MESSAGE_TYPES = frozenset(
    {
        "assignment",
        "ack",
        "progress",
        "blocker",
        "completion",
        "escalation",
        "recovery",
        "supervisor_alert",
    }
)

VALID_MESSAGE_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})

VALID_MESSAGE_STATUSES = frozenset(
    {
        "pending",
        "delivered",
        "acked",
        "resolved",
        "expired",
        "dead_lettered",
    }
)

# Valid status transitions for the message lifecycle.
VALID_MESSAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"delivered", "acked", "expired", "dead_lettered"}),
    "delivered": frozenset({"acked", "expired", "dead_lettered"}),
    "acked": frozenset({"resolved"}),
    "resolved": frozenset(),  # terminal
    "expired": frozenset(),  # terminal
    "dead_lettered": frozenset(),  # terminal
}

# Default delivery policy
DEFAULT_MAX_RETRIES = 3
DEFAULT_TTL_SECONDS: int | None = None  # No expiry by default


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BusMessage:
    """A single lane-to-lane message on the communication bus.

    Frozen to enforce immutability — status updates create new records
    in the inbox (append-only JSONL).

    The 16-field contract follows the governing plan's message schema
    (lines 326–345).
    """

    message_id: str
    thread_id: str | None
    task_id: str | None  # Links to TaskPacket.packet_id
    from_lane: str
    to_lane: str
    message_type: str
    priority: str
    status: str
    created_at: str  # ISO 8601
    acked_at: str | None
    resolved_at: str | None
    requires_human: bool
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    source_transport: str = "bus"
    parent_message_id: str | None = None

    def __post_init__(self) -> None:
        if self.message_type not in VALID_MESSAGE_TYPES:
            raise ValueError(
                f"Invalid message_type {self.message_type!r}; "
                f"expected one of {sorted(VALID_MESSAGE_TYPES)}"
            )
        if self.priority not in VALID_MESSAGE_PRIORITIES:
            raise ValueError(
                f"Invalid priority {self.priority!r}; "
                f"expected one of {sorted(VALID_MESSAGE_PRIORITIES)}"
            )
        if self.status not in VALID_MESSAGE_STATUSES:
            raise ValueError(
                f"Invalid status {self.status!r}; "
                f"expected one of {sorted(VALID_MESSAGE_STATUSES)}"
            )


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_message(
    from_lane: str,
    to_lane: str,
    message_type: str,
    summary: str,
    *,
    thread_id: str | None = None,
    task_id: str | None = None,
    priority: str = "normal",
    requires_human: bool = False,
    payload: dict[str, Any] | None = None,
    source_transport: str = "bus",
    parent_message_id: str | None = None,
) -> BusMessage:
    """Create a new BusMessage with generated ID and timestamp.

    Delivery policy defaults (max_retries, ttl_seconds) are stored in
    ``payload`` to keep the core schema stable.
    """
    base_payload = payload or {}
    # Inject delivery policy defaults if not already set
    if "max_retries" not in base_payload:
        base_payload["max_retries"] = DEFAULT_MAX_RETRIES
    if "retry_count" not in base_payload:
        base_payload["retry_count"] = 0
    if "ttl_seconds" not in base_payload:
        base_payload["ttl_seconds"] = DEFAULT_TTL_SECONDS

    return BusMessage(
        message_id=uuid.uuid4().hex[:16],
        thread_id=thread_id,
        task_id=task_id,
        from_lane=from_lane,
        to_lane=to_lane,
        message_type=message_type,
        priority=priority,
        status="pending",
        created_at=_now_iso(),
        acked_at=None,
        resolved_at=None,
        requires_human=requires_human,
        summary=summary,
        payload=base_payload,
        source_transport=source_transport,
        parent_message_id=parent_message_id,
    )


# ---------------------------------------------------------------------------
# Shared bus root — canonical across all worktrees
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _resolve_git_common_bus_root() -> Path:
    """Resolve the message bus root from git's common directory.

    Same pattern as ``shared_queue_root()`` in ``review_queue.py``.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (Path.cwd() / git_common).resolve()
            else:
                git_common = git_common.resolve()
            main_root = git_common.parent
            return main_root / ".claude" / "runtime" / "message_bus"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return DEFAULT_BUS_DIR


def shared_bus_root(bus_dir: Path | None = None) -> Path:
    """Return the canonical message bus root shared across all worktrees.

    Resolution order:

    1. Explicit ``bus_dir`` parameter (test override).
    2. ``BID_EUCHRE_BUS_DIR`` environment variable.
    3. Derived from ``git rev-parse --git-common-dir`` (cached).
    4. Falls back to :data:`DEFAULT_BUS_DIR`.

    Creates the directory structure if it doesn't exist.
    """
    if bus_dir is not None:
        root = bus_dir
    else:
        env_override = os.environ.get("BID_EUCHRE_BUS_DIR")
        if env_override:
            root = Path(env_override)
        else:
            root = _resolve_git_common_bus_root()

    root.mkdir(parents=True, exist_ok=True)
    (root / INBOX_DIR).mkdir(exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# JSONL audit trail
# ---------------------------------------------------------------------------


def _append_jsonl(path: Path, data: dict[str, Any], lock_path: Path) -> None:
    """Append a JSON line to a file under flock protection.

    Same flock pattern as ``append_event()`` in ``events.py``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(path, "a") as f:
                f.write(json.dumps(data, sort_keys=True, default=str) + "\n")
                f.flush()
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)


def append_message(msg: BusMessage, bus_root: Path | None = None) -> None:
    """Append a message to the global audit trail JSONL."""
    root = shared_bus_root(bus_root)
    audit_path = root / MESSAGES_FILE
    lock_path = root / LOCK_FILE
    _append_jsonl(audit_path, asdict(msg), lock_path)
    logger.debug("Audit trail appended: %s", msg.message_id)


def read_messages(
    bus_root: Path | None = None,
    *,
    since: datetime | None = None,
    from_lane: str | None = None,
    to_lane: str | None = None,
    thread_id: str | None = None,
    message_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read and filter messages from the global audit trail.

    Returns list of message dicts, most recent first, up to ``limit``.
    """
    root = shared_bus_root(bus_root)
    audit_path = root / MESSAGES_FILE
    if not audit_path.exists():
        return []

    from collections import deque

    matched: deque[dict[str, Any]] = deque(maxlen=limit)
    with open(audit_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed audit line: %s", line[:100])
                continue

            # Apply filters
            if from_lane is not None and record.get("from_lane") != from_lane:
                continue
            if to_lane is not None and record.get("to_lane") != to_lane:
                continue
            if thread_id is not None and record.get("thread_id") != thread_id:
                continue
            if message_type is not None and record.get("message_type") != message_type:
                continue
            if since is not None:
                try:
                    msg_time = datetime.fromisoformat(record["created_at"])
                    if msg_time <= since:
                        continue
                except (KeyError, ValueError):
                    continue

            matched.append(record)

    result = list(matched)
    result.reverse()
    return result


# ---------------------------------------------------------------------------
# Per-lane inbox
# ---------------------------------------------------------------------------


def _inbox_path(lane_id: str, bus_root: Path) -> Path:
    """Return the inbox JSONL path for a lane."""
    return bus_root / INBOX_DIR / f"{lane_id}.jsonl"


def _inbox_lock_path(lane_id: str, bus_root: Path) -> Path:
    """Return the lock file path for a lane's inbox."""
    return bus_root / INBOX_DIR / f".{lane_id}.lock"


def _append_to_inbox(msg: BusMessage, bus_root: Path) -> None:
    """Append a message to the recipient lane's inbox."""
    inbox = _inbox_path(msg.to_lane, bus_root)
    lock = _inbox_lock_path(msg.to_lane, bus_root)
    _append_jsonl(inbox, asdict(msg), lock)
    logger.debug("Inbox appended for %s: %s", msg.to_lane, msg.message_id)


def _read_inbox_raw(lane_id: str, bus_root: Path) -> list[dict[str, Any]]:
    """Read all records from a lane's inbox JSONL (chronological order)."""
    inbox = _inbox_path(lane_id, bus_root)
    if not inbox.exists():
        return []

    records: list[dict[str, Any]] = []
    with open(inbox) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping malformed inbox line for %s", lane_id)
    return records


def read_inbox(
    lane_id: str,
    bus_root: Path | None = None,
    *,
    status: str | None = None,
    thread_id: str | None = None,
    message_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read and filter a lane's inbox messages.

    Returns list of message dicts, most recent first, up to ``limit``.
    Each message_id appears once (latest record wins for status updates).
    """
    root = shared_bus_root(bus_root)
    raw = _read_inbox_raw(lane_id, root)

    # Deduplicate: latest record per message_id wins
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    # Apply filters
    from collections import deque

    matched: deque[dict[str, Any]] = deque(maxlen=limit)
    for rec in by_id.values():
        if status is not None and rec.get("status") != status:
            continue
        if thread_id is not None and rec.get("thread_id") != thread_id:
            continue
        if message_type is not None and rec.get("message_type") != message_type:
            continue
        matched.append(rec)

    result = list(matched)
    result.reverse()
    return result


def query_unresolved(
    lane_id: str,
    bus_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Return pending + delivered + acked messages for a lane (not terminal)."""
    root = shared_bus_root(bus_root)
    raw = _read_inbox_raw(lane_id, root)

    # Deduplicate: latest record per message_id wins
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    terminal = {"resolved", "expired", "dead_lettered"}
    return [rec for rec in by_id.values() if rec.get("status") not in terminal]


# ---------------------------------------------------------------------------
# Delivery semantics
# ---------------------------------------------------------------------------


def send_message(
    msg: BusMessage,
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> str:
    """Send a message: write to audit trail + recipient inbox, emit event.

    Enforces duplicate suppression: if a message with the same message_id
    already exists in the audit trail, the send is rejected.

    Args:
        msg: The message to send.
        bus_root: Override for bus root directory.
        events_dir: Override for events directory (for testing).

    Returns:
        The message_id of the sent message.

    Raises:
        ValueError: If a message with the same ID already exists.
    """
    root = shared_bus_root(bus_root)

    # Duplicate suppression: check audit trail under lock
    audit_path = root / MESSAGES_FILE
    lock_path = root / LOCK_FILE

    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            # Check for duplicate
            if audit_path.exists():
                with open(audit_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            rec = json.loads(line)
                            if rec.get("message_id") == msg.message_id:
                                raise ValueError(
                                    f"Duplicate message_id {msg.message_id!r} "
                                    f"already exists in audit trail"
                                )
                        except json.JSONDecodeError:
                            continue

            # Append to audit trail (under same lock)
            with open(audit_path, "a") as f:
                f.write(json.dumps(asdict(msg), sort_keys=True, default=str) + "\n")
                f.flush()
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    # Append to recipient inbox
    _append_to_inbox(msg, root)

    # Emit event
    try:
        from bid_euchre.ops.events import append_event

        append_event(
            "message_sent",
            "ops.message_bus",
            msg.from_lane,
            {
                "message_id": msg.message_id,
                "to_lane": msg.to_lane,
                "message_type": msg.message_type,
                "thread_id": msg.thread_id,
                "task_id": msg.task_id,
            },
            events_dir=events_dir,
        )
    except Exception:
        logger.warning("Failed to emit message_sent event for %s", msg.message_id)

    logger.info(
        "Sent message %s: %s -> %s (%s)",
        msg.message_id,
        msg.from_lane,
        msg.to_lane,
        msg.message_type,
    )
    return msg.message_id


def _update_inbox_status(
    message_id: str,
    lane_id: str,
    new_status: str,
    bus_root: Path,
    *,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Update a message's status in a lane's inbox.

    Appends a new record with the updated status (append-only inbox).
    Validates the transition against VALID_MESSAGE_TRANSITIONS.

    Returns the updated record, or None if message not found.
    """
    raw = _read_inbox_raw(lane_id, bus_root)

    # Find the latest record for this message
    latest: dict[str, Any] | None = None
    for rec in raw:
        if rec.get("message_id") == message_id:
            latest = rec

    if latest is None:
        logger.warning("Message %s not found in %s inbox", message_id, lane_id)
        return None

    # Validate transition
    current_status = latest.get("status", "pending")
    allowed = VALID_MESSAGE_TRANSITIONS.get(current_status, frozenset())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition {current_status!r} -> {new_status!r} for "
            f"message {message_id!r}; allowed: {sorted(allowed) if allowed else '(terminal)'}"
        )

    # Build updated record
    updated = {**latest, "status": new_status}
    if extra_fields:
        updated.update(extra_fields)

    # Append updated record to inbox
    inbox = _inbox_path(lane_id, bus_root)
    lock = _inbox_lock_path(lane_id, bus_root)
    _append_jsonl(inbox, updated, lock)

    return updated


def ack_message(
    message_id: str,
    lane_id: str,
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Acknowledge a message in a lane's inbox.

    Sets status to ``acked`` and records ``acked_at`` timestamp.

    Returns the updated record, or None if not found.
    """
    root = shared_bus_root(bus_root)
    updated = _update_inbox_status(
        message_id,
        lane_id,
        "acked",
        root,
        extra_fields={"acked_at": _now_iso()},
    )

    if updated is not None:
        try:
            from bid_euchre.ops.events import append_event

            append_event(
                "message_acked",
                "ops.message_bus",
                lane_id,
                {"message_id": message_id},
                events_dir=events_dir,
            )
        except Exception:
            logger.warning("Failed to emit message_acked event for %s", message_id)

    return updated


def resolve_message(
    message_id: str,
    lane_id: str,
    bus_root: Path | None = None,
) -> dict[str, Any] | None:
    """Resolve a message (mark as completed/handled).

    Sets status to ``resolved`` and records ``resolved_at`` timestamp.

    Returns the updated record, or None if not found.
    """
    root = shared_bus_root(bus_root)
    return _update_inbox_status(
        message_id,
        lane_id,
        "resolved",
        root,
        extra_fields={"resolved_at": _now_iso()},
    )


def check_expired(
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Scan all inboxes for messages past their TTL and mark them expired.

    Args:
        bus_root: Override for bus root directory.
        events_dir: Override for events directory (for testing).
        now: Override for current time as Unix timestamp (for testing).

    Returns:
        List of expired message records.
    """
    root = shared_bus_root(bus_root)
    inbox_dir = root / INBOX_DIR
    if not inbox_dir.exists():
        return []

    current_time = now or time.time()
    expired_msgs: list[dict[str, Any]] = []

    for inbox_file in sorted(inbox_dir.glob("*.jsonl")):
        lane_id = inbox_file.stem
        if lane_id.startswith("."):
            continue  # Skip lock files

        raw = _read_inbox_raw(lane_id, root)

        # Deduplicate: latest record per message_id
        by_id: dict[str, dict[str, Any]] = {}
        for rec in raw:
            mid = rec.get("message_id")
            if mid:
                by_id[mid] = rec

        for mid, rec in by_id.items():
            status = rec.get("status", "pending")
            if status in ("resolved", "expired", "dead_lettered"):
                continue

            ttl = rec.get("payload", {}).get("ttl_seconds")
            if ttl is None:
                continue

            created = rec.get("created_at", "")
            try:
                created_dt = datetime.fromisoformat(created)
                created_ts = created_dt.timestamp()
            except (ValueError, TypeError):
                continue

            if current_time - created_ts > ttl:
                updated = _update_inbox_status(mid, lane_id, "expired", root)
                if updated:
                    expired_msgs.append(updated)
                    try:
                        from bid_euchre.ops.events import append_event

                        append_event(
                            "message_expired",
                            "ops.message_bus",
                            lane_id,
                            {"message_id": mid, "ttl_seconds": ttl},
                            events_dir=events_dir,
                        )
                    except Exception:
                        logger.warning(
                            "Failed to emit message_expired event for %s", mid
                        )

    return expired_msgs


def check_dead_letters(
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Scan all inboxes for messages exceeding max_retries.

    Messages with ``payload.retry_count >= payload.max_retries`` are
    marked ``dead_lettered``.

    Returns:
        List of dead-lettered message records.
    """
    root = shared_bus_root(bus_root)
    inbox_dir = root / INBOX_DIR
    if not inbox_dir.exists():
        return []

    dead_msgs: list[dict[str, Any]] = []

    for inbox_file in sorted(inbox_dir.glob("*.jsonl")):
        lane_id = inbox_file.stem
        if lane_id.startswith("."):
            continue

        raw = _read_inbox_raw(lane_id, root)

        # Deduplicate
        by_id: dict[str, dict[str, Any]] = {}
        for rec in raw:
            mid = rec.get("message_id")
            if mid:
                by_id[mid] = rec

        for mid, rec in by_id.items():
            status = rec.get("status", "pending")
            if status in ("resolved", "expired", "dead_lettered"):
                continue

            payload = rec.get("payload", {})
            max_retries = payload.get("max_retries", DEFAULT_MAX_RETRIES)
            retry_count = payload.get("retry_count", 0)

            if retry_count >= max_retries:
                updated = _update_inbox_status(mid, lane_id, "dead_lettered", root)
                if updated:
                    dead_msgs.append(updated)
                    try:
                        from bid_euchre.ops.events import append_event

                        append_event(
                            "message_dead_lettered",
                            "ops.message_bus",
                            lane_id,
                            {
                                "message_id": mid,
                                "max_retries": max_retries,
                                "retry_count": retry_count,
                            },
                            events_dir=events_dir,
                        )
                    except Exception:
                        logger.warning(
                            "Failed to emit message_dead_lettered event for %s",
                            mid,
                        )

    return dead_msgs


# ---------------------------------------------------------------------------
# Inbox summary (for status enrichment / CLI)
# ---------------------------------------------------------------------------


def inbox_stats(bus_root: Path | None = None) -> dict[str, Any]:
    """Return per-lane inbox statistics.

    Returns:
        Dict with keys: lanes (list of dicts with lane_id, total,
        by_status counts).
    """
    root = shared_bus_root(bus_root)
    inbox_dir = root / INBOX_DIR
    if not inbox_dir.exists():
        return {"lanes": []}

    lane_stats: list[dict[str, Any]] = []

    for inbox_file in sorted(inbox_dir.glob("*.jsonl")):
        lane_id = inbox_file.stem
        if lane_id.startswith("."):
            continue

        raw = _read_inbox_raw(lane_id, root)

        # Deduplicate
        by_id: dict[str, dict[str, Any]] = {}
        for rec in raw:
            mid = rec.get("message_id")
            if mid:
                by_id[mid] = rec

        by_status: dict[str, int] = {}
        for rec in by_id.values():
            s = rec.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        lane_stats.append(
            {
                "lane_id": lane_id,
                "total": len(by_id),
                "by_status": by_status,
            }
        )

    return {"lanes": lane_stats}
