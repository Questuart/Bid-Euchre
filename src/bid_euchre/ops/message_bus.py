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
from collections.abc import Callable, Sequence
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
DEFAULT_TTL_SECONDS: int = 86400  # 24-hour expiry by default

# Inbox compaction policy — thresholds and retention
#
# Auto-compaction fires when a read_inbox call encounters more raw JSONL
# lines than this threshold.  It is transparent: the caller gets the same
# results, but the file is rewritten with only the deduplicated/kept
# records.  This prevents inbox files from growing unboundedly in long
# steward sessions.
AUTO_COMPACT_RAW_THRESHOLD: int = 200

# Retention tiers for handled messages during compaction:
#   - Active (pending, delivered): always kept
#   - Handled (acked): kept for COMPACT_HANDLED_MAX_AGE_HOURS
#   - Terminal (resolved, expired, dead_lettered): kept for COMPACT_TERMINAL_MAX_AGE_HOURS
COMPACT_HANDLED_MAX_AGE_HOURS: float = 4.0
COMPACT_TERMINAL_MAX_AGE_HOURS: float = 1.0


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
    base_payload = {**(payload or {})}
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


def _expire_stale_on_read(
    by_id: dict[str, dict[str, Any]],
    lane_id: str,
    bus_root: Path,
    *,
    now: float | None = None,
) -> None:
    """Lazily expire messages past their TTL during a read operation.

    Mutates *by_id* in-place: any message that has exceeded its
    ``payload.ttl_seconds`` is transitioned to ``expired`` and the dict
    value is replaced with the updated record.  This avoids the need
    for a separate ``check_expired()`` sweep for the common 24-hour case.

    Only non-terminal messages with a numeric ``ttl_seconds`` are checked.
    """
    current_time = now if now is not None else time.time()
    skip = {"resolved", "expired", "dead_lettered", "acked"}

    for mid, rec in list(by_id.items()):
        if rec.get("status") in skip:
            continue
        ttl = rec.get("payload", {}).get("ttl_seconds")
        if ttl is None:
            continue
        created = rec.get("created_at", "")
        try:
            created_ts = datetime.fromisoformat(created).timestamp()
        except (ValueError, TypeError):
            continue
        if current_time - created_ts > ttl:
            updated = _update_inbox_status(mid, lane_id, "expired", bus_root)
            if updated:
                by_id[mid] = updated
                logger.debug("Auto-expired message %s on read (TTL=%s)", mid, ttl)


def read_inbox(
    lane_id: str,
    bus_root: Path | None = None,
    *,
    status: str | None = None,
    thread_id: str | None = None,
    message_type: str | Sequence[str] | None = None,
    limit: int = 50,
    auto_expire: bool = True,
    auto_compact: bool = True,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Read and filter a lane's inbox messages.

    Returns list of message dicts, most recent first, up to ``limit``.
    Each message_id appears once (latest record wins for status updates).

    When *auto_expire* is ``True`` (the default), messages whose
    ``payload.ttl_seconds`` has elapsed are automatically transitioned
    to ``expired`` before filtering.

    When *auto_compact* is ``True`` (the default), the inbox is
    transparently compacted if the raw JSONL line count exceeds
    ``AUTO_COMPACT_RAW_THRESHOLD``.  Compaction uses tiered retention
    so that handled and terminal messages are purged sooner than the
    default 24-hour TTL.  The compaction is best-effort: failures are
    logged but do not affect the read result.

    Args:
        message_type: Filter by message type.  Accepts a single type string,
            a sequence of type strings (matches any), or ``None`` (no filter).
        auto_compact: Trigger transparent compaction when raw inbox size
            exceeds ``AUTO_COMPACT_RAW_THRESHOLD``.  Default ``True``.
        now: Override for current time as Unix timestamp (for testing).
            Passed through to ``_expire_stale_on_read()``.
    """
    root = shared_bus_root(bus_root)
    raw = _read_inbox_raw(lane_id, root)

    # Auto-compact: if the raw inbox is large, compact before proceeding.
    # This is transparent — the caller gets the same results, but the file
    # is rewritten with only the deduplicated/kept records.
    if auto_compact and len(raw) > AUTO_COMPACT_RAW_THRESHOLD:
        try:
            compact_inbox(lane_id, root, tiered=True, now=now)
            # Re-read after compaction
            raw = _read_inbox_raw(lane_id, root)
            logger.debug(
                "Auto-compacted inbox for %s (%d raw lines exceeded threshold %d)",
                lane_id,
                len(raw),
                AUTO_COMPACT_RAW_THRESHOLD,
            )
        except Exception:
            logger.warning(
                "Auto-compaction failed for %s inbox; proceeding with uncompacted data",
                lane_id,
                exc_info=True,
            )

    # Deduplicate: latest record per message_id wins
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    # Lazily expire stale messages before applying user filters
    if auto_expire:
        _expire_stale_on_read(by_id, lane_id, root, now=now)

    # Normalise message_type filter to a frozenset for O(1) lookups
    type_filter: frozenset[str] | None = None
    if message_type is not None:
        if isinstance(message_type, str):
            type_filter = frozenset({message_type})
        else:
            type_filter = frozenset(message_type)

    # Apply filters
    from collections import deque

    matched: deque[dict[str, Any]] = deque(maxlen=limit)
    for rec in by_id.values():
        if status is not None and rec.get("status") != status:
            continue
        if thread_id is not None and rec.get("thread_id") != thread_id:
            continue
        if type_filter is not None and rec.get("message_type") not in type_filter:
            continue
        matched.append(rec)

    result = list(matched)
    result.reverse()
    return result


# ---------------------------------------------------------------------------
# Priority-grouped inbox read
# ---------------------------------------------------------------------------

# Mapping from priority field values to tier indices (P0/P1/P2).
_PRIORITY_TO_TIER: dict[str, int] = {
    "urgent": 0,  # P0 — interrupt-worthy
    "high": 1,  # P1 — next-cycle processing
    "normal": 2,  # P2 — batch processing
    "low": 2,  # P2 — batch processing
}


def read_inbox_prioritized(
    lane_id: str,
    bus_root: Path | None = None,
    *,
    status: str | None = "pending",
    auto_expire: bool = True,
    auto_compact: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Read inbox grouped by priority tier.

    Returns ``(p0, p1, p2)`` where:

    - **p0** = ``urgent`` priority messages (interrupt-worthy)
    - **p1** = ``high`` priority messages (next-cycle processing)
    - **p2** = ``normal`` / ``low`` priority messages (batch processing)

    Each tier list is ordered most-recent-first, matching ``read_inbox()``.
    """
    messages = read_inbox(
        lane_id,
        bus_root,
        status=status,
        auto_expire=auto_expire,
        auto_compact=auto_compact,
    )

    p0: list[dict[str, Any]] = []
    p1: list[dict[str, Any]] = []
    p2: list[dict[str, Any]] = []
    buckets = (p0, p1, p2)

    for msg in messages:
        tier = _PRIORITY_TO_TIER.get(msg.get("priority", "normal"), 2)
        buckets[tier].append(msg)

    return p0, p1, p2


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


def _content_dedup_key(msg: BusMessage) -> tuple[str, str, str, str]:
    """Return a content-based dedup key for a message.

    Two messages are considered content-duplicates when they share the same
    ``(to_lane, from_lane, message_type, summary)`` tuple.  This prevents
    repeated verdict notifications, test artifacts, and other noise from
    accumulating in the recipient's inbox.
    """
    return (msg.to_lane, msg.from_lane, msg.message_type, msg.summary)


def send_message(
    msg: BusMessage,
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
    deduplicate: bool = False,
) -> str:
    """Send a message: write to audit trail + recipient inbox, emit event.

    Enforces duplicate suppression: if a message with the same message_id
    already exists in the audit trail, the send is rejected.

    When *deduplicate* is ``True``, content-based dedup is applied: if a
    non-terminal message with the same ``(to_lane, from_lane, message_type,
    summary)`` already exists in the recipient's inbox, the new message is
    silently dropped and the existing message's ID is returned.

    Args:
        msg: The message to send.
        bus_root: Override for bus root directory.
        events_dir: Override for events directory (for testing).
        deduplicate: Enable content-based duplicate suppression.

    Returns:
        The message_id of the sent (or existing duplicate) message.

    Raises:
        ValueError: If a message with the same ID already exists.
    """
    root = shared_bus_root(bus_root)

    # Content-based dedup: check recipient inbox for existing match
    if deduplicate:
        existing = _find_content_duplicate(msg, root)
        if existing is not None:
            logger.debug(
                "Content-dedup suppressed message %s (existing: %s)",
                msg.message_id,
                existing,
            )
            return existing

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


def _find_content_duplicate(msg: BusMessage, bus_root: Path) -> str | None:
    """Check the recipient inbox for a non-terminal content-duplicate.

    Returns the existing message_id if found, else ``None``.
    """
    raw = _read_inbox_raw(msg.to_lane, bus_root)

    # Deduplicate: latest record per message_id
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    terminal = {"resolved", "expired", "dead_lettered"}
    key = _content_dedup_key(msg)

    for mid, rec in by_id.items():
        if rec.get("status") in terminal:
            continue
        existing_key = (
            rec.get("to_lane", ""),
            rec.get("from_lane", ""),
            rec.get("message_type", ""),
            rec.get("summary", ""),
        )
        if existing_key == key:
            return mid

    return None


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


def mark_delivered(
    message_id: str,
    lane_id: str,
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Mark a message as delivered in a lane's inbox.

    Transitions the message from ``pending`` to ``delivered``.
    This is the public API for cross-module callers (e.g. worker_pool)
    that need to record successful delivery without reaching into private
    inbox internals.

    Args:
        message_id: The message to mark as delivered.
        lane_id: The lane whose inbox contains the message.
        bus_root: Override for bus root directory.
        events_dir: Override for events directory (for testing).

    Returns:
        The updated record, or None if message not found.
    """
    root = shared_bus_root(bus_root)
    updated = _update_inbox_status(
        message_id,
        lane_id,
        "delivered",
        root,
    )

    if updated is not None:
        try:
            from bid_euchre.ops.events import append_event

            append_event(
                "message_delivered",
                "ops.message_bus",
                lane_id,
                {"message_id": message_id},
                events_dir=events_dir,
            )
        except Exception:
            logger.warning("Failed to emit message_delivered event for %s", message_id)

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


def bulk_ack_messages(
    lane_id: str,
    filter_fn: Callable[[dict[str, Any]], bool],
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Acknowledge all messages in a lane's inbox that match *filter_fn*.

    Only messages in ack-able states (``pending`` or ``delivered``) are
    considered.  Messages already acked, resolved, or terminal are skipped.

    Args:
        lane_id: The lane whose inbox to scan.
        filter_fn: Predicate receiving a message dict; return ``True`` to ack.
        bus_root: Override for bus root directory.
        events_dir: Override for events directory (for testing).

    Returns:
        List of acked message dicts.
    """
    root = shared_bus_root(bus_root)
    raw = _read_inbox_raw(lane_id, root)

    # Deduplicate: latest record per message_id wins
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    ackable = {"pending", "delivered"}
    acked: list[dict[str, Any]] = []
    for mid, rec in by_id.items():
        if rec.get("status") not in ackable:
            continue
        if not filter_fn(rec):
            continue
        updated = _update_inbox_status(
            mid, lane_id, "acked", root, extra_fields={"acked_at": _now_iso()}
        )
        if updated is not None:
            acked.append(updated)
            try:
                from bid_euchre.ops.events import append_event

                append_event(
                    "message_acked",
                    "ops.message_bus",
                    lane_id,
                    {"message_id": mid, "bulk": True},
                    events_dir=events_dir,
                )
            except Exception:
                logger.warning("Failed to emit message_acked event for %s", mid)

    if acked:
        logger.info("Bulk-acked %d message(s) for %s", len(acked), lane_id)
    return acked


def resolve_message(
    message_id: str,
    lane_id: str,
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Resolve a message (mark as completed/handled).

    Sets status to ``resolved`` and records ``resolved_at`` timestamp.

    Returns the updated record, or None if not found.
    """
    root = shared_bus_root(bus_root)
    updated = _update_inbox_status(
        message_id,
        lane_id,
        "resolved",
        root,
        extra_fields={"resolved_at": _now_iso()},
    )

    if updated is not None:
        try:
            from bid_euchre.ops.events import append_event

            append_event(
                "message_resolved",
                "ops.message_bus",
                lane_id,
                {"message_id": message_id},
                events_dir=events_dir,
            )
        except Exception:
            logger.warning("Failed to emit message_resolved event for %s", message_id)

    return updated


def check_ack_status(
    message_id: str,
    recipient_lane: str,
    bus_root: Path | None = None,
) -> str | None:
    """Check if a message was acked by the recipient.

    Looks up the latest record for *message_id* in *recipient_lane*'s inbox
    and returns the current status string (``'pending'``, ``'acked'``,
    ``'resolved'``, etc.) or ``None`` if the message is not found.

    This lets a sender verify that the recipient has acknowledged a message
    without reading the full inbox.

    Args:
        message_id: The ID of the message to check.
        recipient_lane: The lane whose inbox to look in.
        bus_root: Override for bus root directory.

    Returns:
        The current status string, or ``None`` if the message is not found.
    """
    root = shared_bus_root(bus_root)
    raw = _read_inbox_raw(recipient_lane, root)

    # Deduplicate: latest record per message_id wins
    latest: dict[str, Any] | None = None
    for rec in raw:
        if rec.get("message_id") == message_id:
            latest = rec

    if latest is None:
        return None

    return latest.get("status", "pending")


def escalate_unacked(
    sender_lane: str,
    recipient_lane: str,
    max_age_minutes: int = 10,
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
) -> list[str]:
    """Find unacked outbound messages older than *max_age_minutes* and escalate.

    Scans the *recipient_lane*'s inbox for messages sent by *sender_lane*
    that are still in ``pending`` or ``delivered`` status and whose
    ``created_at`` timestamp is older than *max_age_minutes*.

    For each such message an escalation message is created (priority ``urgent``,
    type ``escalation``) referencing the original via ``parent_message_id``,
    and sent to the recipient.

    Args:
        sender_lane: The lane that sent the original messages.
        recipient_lane: The lane whose inbox to scan for unacked messages.
        max_age_minutes: Age threshold in minutes before escalation fires.
        bus_root: Override for bus root directory.
        events_dir: Override for events directory (for testing).

    Returns:
        List of escalation message IDs sent.
    """
    root = shared_bus_root(bus_root)
    raw = _read_inbox_raw(recipient_lane, root)

    # Deduplicate: latest record per message_id wins
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    cutoff_ts = time.time() - (max_age_minutes * 60)
    unacked_statuses = {"pending", "delivered"}
    escalation_ids: list[str] = []

    for mid, rec in by_id.items():
        # Only look at messages from the sender to the recipient
        if rec.get("from_lane") != sender_lane:
            continue
        if rec.get("status") not in unacked_statuses:
            continue
        # Don't escalate escalation messages (avoid infinite chains)
        if rec.get("message_type") == "escalation":
            continue

        created = rec.get("created_at", "")
        try:
            created_ts = datetime.fromisoformat(created).timestamp()
        except (ValueError, TypeError):
            continue

        if created_ts > cutoff_ts:
            continue  # Not old enough yet

        # Create and send an escalation message
        esc_msg = create_message(
            from_lane=sender_lane,
            to_lane=recipient_lane,
            message_type="escalation",
            summary=f"ESCALATION: unacked message {mid} (original: {rec.get('summary', '?')})",
            priority="urgent",
            parent_message_id=mid,
            payload={
                "original_message_id": mid,
                "original_summary": rec.get("summary", ""),
            },
        )
        esc_id = send_message(esc_msg, root, events_dir=events_dir)
        escalation_ids.append(esc_id)
        logger.info(
            "Escalated unacked message %s from %s to %s",
            mid,
            sender_lane,
            recipient_lane,
        )

    return escalation_ids


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

    current_time = now if now is not None else time.time()
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


# ---------------------------------------------------------------------------
# Inbox compaction (purge terminal messages)
# ---------------------------------------------------------------------------


def _tiered_cutoff(status: str, current_time: float, max_age_hours: float) -> float:
    """Return the cutoff timestamp for a message based on its status tier.

    Tiered retention policy:

    - **Handled** (``acked``): shorter retention — the recipient has
      acknowledged the message so it is no longer actionable.  Default
      ``COMPACT_HANDLED_MAX_AGE_HOURS`` (4 h).
    - **Terminal** (``resolved``, ``expired``, ``dead_lettered``): shortest
      retention — fully resolved lifecycle.  Default
      ``COMPACT_TERMINAL_MAX_AGE_HOURS`` (1 h).

    When the caller passes an explicit ``max_age_hours`` that is *shorter*
    than the tier default, the caller's value wins (most-restrictive).
    """
    terminal = {"resolved", "expired", "dead_lettered"}

    if status in terminal:
        tier_hours = min(COMPACT_TERMINAL_MAX_AGE_HOURS, max_age_hours)
    elif status == "acked":
        tier_hours = min(COMPACT_HANDLED_MAX_AGE_HOURS, max_age_hours)
    else:
        tier_hours = max_age_hours

    return current_time - (tier_hours * 3600)


def compact_inbox(
    lane_id: str,
    bus_root: Path | None = None,
    *,
    max_age_hours: float = 24.0,
    now: float | None = None,
    tiered: bool = True,
) -> dict[str, Any]:
    """Compact a lane's inbox by removing old handled messages.

    Rewrites the per-lane inbox JSONL file, keeping only:

    - **Active** messages (``pending``, ``delivered``) — always kept.
    - **Handled** messages (``acked``) — kept for
      ``COMPACT_HANDLED_MAX_AGE_HOURS`` (default 4 h) when *tiered* is
      ``True``, otherwise ``max_age_hours``.
    - **Terminal** messages (``resolved``, ``expired``, ``dead_lettered``)
      — kept for ``COMPACT_TERMINAL_MAX_AGE_HOURS`` (default 1 h) when
      *tiered* is ``True``, otherwise ``max_age_hours``.

    The global audit trail (``messages.jsonl``) is **not** touched.

    Deduplication is applied during compaction: only the latest record per
    ``message_id`` is retained (the inbox is append-only, so multiple
    records may exist for the same message as its status changed).

    Args:
        lane_id: The lane whose inbox to compact.
        bus_root: Override for bus root directory.
        max_age_hours: Fallback age limit for handled messages (default 24 h).
            When *tiered* is ``True`` the per-status tier defaults take
            precedence unless ``max_age_hours`` is shorter.
        now: Override for current time as Unix timestamp (for testing).
        tiered: Apply tiered retention (shorter for acked/terminal).
            Default ``True``.

    Returns:
        Dict with keys: ``lane_id``, ``before`` (raw line count),
        ``after`` (deduplicated retained count), ``removed`` (unique
        messages purged).
    """
    root = shared_bus_root(bus_root)
    inbox = _inbox_path(lane_id, root)
    lock = _inbox_lock_path(lane_id, root)

    if not inbox.exists():
        return {"lane_id": lane_id, "before": 0, "after": 0, "removed": 0}

    current_time = now or time.time()
    # Messages that have been handled — safe to purge when old enough.
    # Includes acked (handled but not yet resolved) and all terminal states.
    purgeable = {"acked", "resolved", "expired", "dead_lettered"}

    # Read under lock to prevent concurrent writes during compaction
    with open(lock, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            raw = []
            with open(inbox) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            before_count = len(raw)

            # Deduplicate: latest record per message_id wins
            by_id: dict[str, dict[str, Any]] = {}
            for rec in raw:
                mid = rec.get("message_id")
                if mid:
                    by_id[mid] = rec

            # Partition: keep vs remove
            kept: list[dict[str, Any]] = []
            removed_count = 0
            for mid, rec in by_id.items():
                status = rec.get("status", "pending")
                if status not in purgeable:
                    kept.append(rec)
                    continue

                # Handled message — check age against tier-appropriate cutoff
                created = rec.get("created_at", "")
                try:
                    created_ts = datetime.fromisoformat(created).timestamp()
                except (ValueError, TypeError):
                    # Can't parse timestamp — keep to be safe
                    kept.append(rec)
                    continue

                if tiered:
                    cutoff_ts = _tiered_cutoff(status, current_time, max_age_hours)
                else:
                    cutoff_ts = current_time - (max_age_hours * 3600)

                if created_ts < cutoff_ts:
                    removed_count += 1
                else:
                    kept.append(rec)

            # Rewrite the inbox file atomically (write tmp then rename)
            tmp_path = inbox.with_suffix(".jsonl.tmp")
            with open(tmp_path, "w") as f:
                for rec in kept:
                    f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
                f.flush()
            tmp_path.rename(inbox)

        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    logger.info(
        "Compacted inbox for %s: %d raw -> %d kept (%d removed)",
        lane_id,
        before_count,
        len(kept),
        removed_count,
    )
    return {
        "lane_id": lane_id,
        "before": before_count,
        "after": len(kept),
        "removed": removed_count,
    }


def compact_all_inboxes(
    bus_root: Path | None = None,
    *,
    max_age_hours: float = 24.0,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Compact all per-lane inbox files.

    Iterates over every ``*.jsonl`` file in the inbox directory and
    calls :func:`compact_inbox` for each.

    Args:
        bus_root: Override for bus root directory.
        max_age_hours: Remove terminal messages older than this (default 24h).
        now: Override for current time as Unix timestamp (for testing).

    Returns:
        List of per-lane compaction result dicts.
    """
    root = shared_bus_root(bus_root)
    inbox_dir = root / INBOX_DIR
    if not inbox_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for inbox_file in sorted(inbox_dir.glob("*.jsonl")):
        lane_id = inbox_file.stem
        if lane_id.startswith("."):
            continue  # Skip lock files and temp files
        result = compact_inbox(lane_id, root, max_age_hours=max_age_hours, now=now)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Native inbox bridge
# ---------------------------------------------------------------------------

#: Default path for Claude native team inboxes.
DEFAULT_NATIVE_INBOX_DIR = Path.home() / ".claude" / "teams" / "default" / "inboxes"


def _native_content_hash(entry: dict[str, Any]) -> str:
    """Compute a stable content hash for a native inbox entry.

    Uses (from, timestamp, summary, text) as the dedup key.  This is stable
    across reruns as long as the native inbox entry hasn't changed.
    """
    import hashlib

    key = (
        f"{entry.get('from', '')}|{entry.get('timestamp', '')}"
        f"|{entry.get('summary', '')}|{entry.get('text', '')}"
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def import_native_inbox(
    lane_id: str,
    *,
    native_dir: Path | None = None,
    bus_root: Path | None = None,
    events_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Import messages from a Claude native inbox into the repo-owned bus.

    Reads ``<native_dir>/<lane_id>.json``, converts each entry to a
    :class:`BusMessage`, and sends it via :func:`send_message`.
    Deduplicates using a content hash stored in ``payload.native_hash``
    so the function is safe to rerun (idempotent).

    Args:
        lane_id: Lane whose native inbox to import.
        native_dir: Override for the native inbox directory.
        bus_root: Override for the bus root directory.
        events_dir: Override for events directory (for testing).

    Returns:
        List of newly imported message dicts (skips already-imported ones).
    """
    native_path = (native_dir or DEFAULT_NATIVE_INBOX_DIR) / f"{lane_id}.json"
    if not native_path.exists():
        logger.debug("No native inbox file for %s at %s", lane_id, native_path)
        return []

    try:
        with open(native_path) as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read native inbox for %s: %s", lane_id, exc)
        return []

    if not isinstance(entries, list):
        logger.warning("Native inbox for %s is not a JSON array", lane_id)
        return []

    # Use a dedicated lock for the native import cycle to prevent concurrent
    # imports from inserting duplicates.  This is separate from the inbox lock
    # (which send_message acquires internally) to avoid deadlock.
    root = shared_bus_root(bus_root)
    import_lock = root / INBOX_DIR / f".{lane_id}.native_import.lock"
    import_lock.parent.mkdir(parents=True, exist_ok=True)

    imported: list[dict[str, Any]] = []
    with open(import_lock, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            # Read existing inbox to find already-imported hashes
            existing_raw = _read_inbox_raw(lane_id, root)
            existing_hashes: set[str] = set()
            for rec in existing_raw:
                payload = rec.get("payload", {})
                native_hash = payload.get("native_hash")
                if native_hash:
                    existing_hashes.add(native_hash)

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                content_hash = _native_content_hash(entry)
                if content_hash in existing_hashes:
                    continue

                # Map native fields to BusMessage
                from_lane = entry.get("from", "unknown")
                summary = entry.get("summary", "")
                text = entry.get("text", "")
                native_timestamp = entry.get("timestamp", "")

                msg = BusMessage(
                    message_id=uuid.uuid4().hex[:16],
                    thread_id=None,
                    task_id=None,
                    from_lane=from_lane,
                    to_lane=lane_id,
                    message_type="progress",  # best-fit generic type
                    priority="normal",
                    status="pending",
                    created_at=_now_iso(),  # import time, not native time
                    acked_at=None,
                    resolved_at=None,
                    requires_human=False,
                    summary=summary[:200] if summary else text[:200],
                    payload={
                        "native_hash": content_hash,
                        "native_text": text,
                        "native_read": entry.get("read", False),
                        "native_timestamp": native_timestamp,
                        "max_retries": DEFAULT_MAX_RETRIES,
                        "retry_count": 0,
                        "ttl_seconds": DEFAULT_TTL_SECONDS,
                    },
                    source_transport="claude_native",
                )

                try:
                    send_message(msg, bus_root, events_dir=events_dir)
                    imported.append(asdict(msg))
                    existing_hashes.add(content_hash)
                except (ValueError, OSError) as exc:
                    logger.warning(
                        "Failed to import native message for %s (hash=%s): %s",
                        lane_id,
                        content_hash,
                        exc,
                    )
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    logger.info(
        "Imported %d native message(s) for %s (%d skipped as duplicates)",
        len(imported),
        lane_id,
        len(entries) - len(imported),
    )
    return imported
