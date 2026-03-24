"""Durable audit trail for remote channel exchanges (Platform-8b).

Records every inbound and outbound remote exchange (Telegram, future Discord)
to a repo-owned JSONL file for cross-session traceability and incident forensics.

Storage layout::

    .claude/runtime/audit_trail/
        remote_exchanges.jsonl    # Append-only audit log
        .remote_exchanges.lock    # flock file

The audit trail is separate from the lane-to-lane message bus. It captures
external channel traffic (operator ↔ orchestrator via Telegram), not internal
lane communication.

Design decisions:
- Content hash + preview (not full content) to limit sensitive data exposure
- Reuses the flock+JSONL pattern from ``message_bus.py`` and ``events.py``
- No event emission in v1 — append-only; dashboard integration deferred
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.audit_trail")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_AUDIT_DIR = Path(".claude/runtime/audit_trail")
EXCHANGES_FILE = "remote_exchanges.jsonl"
LOCK_FILE = ".remote_exchanges.lock"

VALID_DIRECTIONS = frozenset({"inbound", "outbound"})

VALID_EXCHANGE_TYPES = frozenset(
    {
        "message",
        "reply",
        "react",
        "edit",
        "download_attachment",
        "permission_relay_observed",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of *text*.

    >>> content_hash("hello")
    '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_preview(text: str, max_len: int = 200) -> str:
    """Return the first *max_len* characters of *text*, adding '…' if truncated.

    >>> content_preview("short")
    'short'
    >>> len(content_preview("x" * 300)) <= 201  # 200 chars + ellipsis
    True
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# Regex for extracting attributes from a <channel ...> XML-style tag.
# Matches key="value" pairs (double-quoted only, no nested quotes).
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def parse_channel_tag(tag_text: str) -> dict[str, str]:
    """Parse a ``<channel source="..." ...>`` XML tag and extract attributes.

    Accepts the tag format injected by the Telegram plugin::

        <channel source="telegram" chat_id="123" message_id="42"
                 user="alice" ts="2026-03-24T06:00:00Z">

    The closing ``>`` is optional (self-closing ``/>`` is also accepted).

    Args:
        tag_text: Raw tag text, e.g. from a system-reminder message.

    Returns:
        Dict mapping attribute names to their string values.
        Returns an empty dict if *tag_text* does not look like a channel tag.
    """
    tag_text = tag_text.strip()
    if not tag_text.startswith("<channel"):
        return {}
    return dict(_ATTR_RE.findall(tag_text))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditRecord:
    """One recorded remote exchange.

    All fields are set at creation time and never mutated.
    """

    exchange_id: str
    timestamp: str
    direction: str
    channel_source: str
    sender_identity: str
    exchange_type: str
    content_hash: str
    content_preview: str
    chat_id: str
    message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"Invalid direction {self.direction!r}. "
                f"Must be one of: {sorted(VALID_DIRECTIONS)}"
            )
        if self.exchange_type not in VALID_EXCHANGE_TYPES:
            raise ValueError(
                f"Invalid exchange_type {self.exchange_type!r}. "
                f"Must be one of: {sorted(VALID_EXCHANGE_TYPES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for JSON encoding."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditRecord:
        """Deserialize from a dict (e.g. parsed from JSONL)."""
        return cls(**data)


def create_record(
    direction: str,
    channel_source: str,
    sender_identity: str,
    exchange_type: str,
    content: str,
    chat_id: str,
    message_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> AuditRecord:
    """Create a new :class:`AuditRecord` with auto-generated ID, hash, and preview.

    This is the preferred constructor — it computes ``exchange_id``,
    ``content_hash``, and ``content_preview`` automatically.
    """
    return AuditRecord(
        exchange_id=str(uuid.uuid4()),
        timestamp=timestamp or _now_iso(),
        direction=direction,
        channel_source=channel_source,
        sender_identity=sender_identity,
        exchange_type=exchange_type,
        content_hash=content_hash(content),
        content_preview=content_preview(content),
        chat_id=chat_id,
        message_id=message_id,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _append_jsonl(path: Path, data: dict[str, Any], lock_path: Path) -> None:
    """Append a JSON line to a file under flock protection.

    Same flock pattern as ``message_bus._append_jsonl()`` and
    ``events.append_event()``.
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


def append_record(record: AuditRecord, audit_dir: Path | None = None) -> None:
    """Append an :class:`AuditRecord` to the audit trail JSONL file.

    Args:
        record: The audit record to persist.
        audit_dir: Override for audit trail directory. Defaults to
            ``.claude/runtime/audit_trail``.
    """
    if audit_dir is None:
        audit_dir = DEFAULT_AUDIT_DIR

    exchanges_path = audit_dir / EXCHANGES_FILE
    lock_path = audit_dir / LOCK_FILE

    _append_jsonl(exchanges_path, record.to_dict(), lock_path)
    logger.debug(
        "Audit record appended: %s (%s)", record.exchange_id, record.exchange_type
    )


# ---------------------------------------------------------------------------
# Outbound audit wrappers
# ---------------------------------------------------------------------------


def audit_reply(
    chat_id: str,
    body: str,
    reply_to: str | None = None,
    files: list[str] | None = None,
    audit_dir: Path | None = None,
) -> AuditRecord:
    """Log an outbound reply to the audit trail.

    Creates an :class:`AuditRecord` with ``direction="outbound"`` and
    ``exchange_type="reply"``, appends it, and returns it.

    Args:
        chat_id: Telegram chat ID the reply is sent to.
        body: The reply text content.
        reply_to: Optional message ID being replied to.
        files: Optional list of file paths attached to the reply.
        audit_dir: Override for audit trail directory.

    Returns:
        The persisted :class:`AuditRecord`.
    """
    metadata: dict[str, Any] = {}
    if reply_to is not None:
        metadata["reply_to"] = reply_to
    if files:
        metadata["files"] = files

    record = create_record(
        direction="outbound",
        channel_source="telegram",
        sender_identity="orchestrator",
        exchange_type="reply",
        content=body,
        chat_id=chat_id,
        metadata=metadata if metadata else None,
    )
    append_record(record, audit_dir=audit_dir)
    return record


def audit_react(
    chat_id: str,
    message_id: str,
    emoji: str,
    audit_dir: Path | None = None,
) -> AuditRecord:
    """Log an outbound reaction to the audit trail.

    Creates an :class:`AuditRecord` with ``direction="outbound"`` and
    ``exchange_type="react"``, appends it, and returns it.

    Args:
        chat_id: Telegram chat ID.
        message_id: Message ID being reacted to.
        emoji: The emoji reaction.
        audit_dir: Override for audit trail directory.

    Returns:
        The persisted :class:`AuditRecord`.
    """
    record = create_record(
        direction="outbound",
        channel_source="telegram",
        sender_identity="orchestrator",
        exchange_type="react",
        content=emoji,
        chat_id=chat_id,
        message_id=message_id,
        metadata={"emoji": emoji},
    )
    append_record(record, audit_dir=audit_dir)
    return record


def audit_edit(
    chat_id: str,
    message_id: str,
    body: str,
    audit_dir: Path | None = None,
) -> AuditRecord:
    """Log an outbound message edit to the audit trail.

    Creates an :class:`AuditRecord` with ``direction="outbound"`` and
    ``exchange_type="edit"``, appends it, and returns it.

    Args:
        chat_id: Telegram chat ID.
        message_id: Message ID being edited.
        body: The new message text after editing.
        audit_dir: Override for audit trail directory.

    Returns:
        The persisted :class:`AuditRecord`.
    """
    record = create_record(
        direction="outbound",
        channel_source="telegram",
        sender_identity="orchestrator",
        exchange_type="edit",
        content=body,
        chat_id=chat_id,
        message_id=message_id,
    )
    append_record(record, audit_dir=audit_dir)
    return record


# ---------------------------------------------------------------------------
# Inbound audit wrappers
# ---------------------------------------------------------------------------


def audit_inbound(
    chat_id: str,
    message_id: str,
    user: str,
    content: str,
    channel_source: str = "telegram",
    ts: str | None = None,
    metadata: dict[str, Any] | None = None,
    audit_dir: Path | None = None,
) -> AuditRecord:
    """Log an inbound message to the audit trail.

    Creates an :class:`AuditRecord` with ``direction="inbound"`` and
    ``exchange_type="message"``, appends it, and returns it.

    Args:
        chat_id: Telegram chat ID the message came from.
        message_id: Telegram message ID.
        user: Sender identity (Telegram user ID or username).
        content: The message text content.
        channel_source: Channel source identifier (default ``"telegram"``).
        ts: Optional timestamp override (ISO 8601). Defaults to current UTC time.
        metadata: Optional extra metadata dict.
        audit_dir: Override for audit trail directory.

    Returns:
        The persisted :class:`AuditRecord`.
    """
    record = create_record(
        direction="inbound",
        channel_source=channel_source,
        sender_identity=user,
        exchange_type="message",
        content=content,
        chat_id=chat_id,
        message_id=message_id,
        metadata=metadata,
        timestamp=ts,
    )
    append_record(record, audit_dir=audit_dir)
    return record


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def read_records(
    audit_dir: Path | None = None,
    *,
    direction: str | None = None,
    channel_source: str | None = None,
    since: datetime | None = None,
    limit: int | None = None,
) -> list[AuditRecord]:
    """Read audit records from the JSONL file with optional filtering.

    Args:
        audit_dir: Override for audit trail directory. Defaults to
            ``.claude/runtime/audit_trail``.
        direction: Filter by ``"inbound"`` or ``"outbound"``.
        channel_source: Filter by channel (e.g. ``"telegram"``).
        since: Only return records with timestamp >= this datetime.
        limit: Maximum number of records to return (most recent first
            after filtering; ``None`` means no limit).

    Returns:
        List of :class:`AuditRecord` instances matching the filters,
        in chronological order (oldest first). If *limit* is specified,
        returns the **last** *limit* records after filtering.
    """
    if audit_dir is None:
        audit_dir = DEFAULT_AUDIT_DIR

    exchanges_path = audit_dir / EXCHANGES_FILE

    if not exchanges_path.exists():
        return []

    records: list[AuditRecord] = []
    with open(exchanges_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSONL line in audit trail")
                continue

            # Apply filters
            if direction is not None and data.get("direction") != direction:
                continue
            if (
                channel_source is not None
                and data.get("channel_source") != channel_source
            ):
                continue
            if since is not None:
                record_ts = data.get("timestamp", "")
                try:
                    record_dt = datetime.fromisoformat(record_ts)
                    if record_dt < since:
                        continue
                except (ValueError, TypeError):
                    continue

            try:
                records.append(AuditRecord.from_dict(data))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipping invalid audit record: %s", exc)
                continue

    if limit is not None and len(records) > limit:
        records = records[-limit:]

    return records
