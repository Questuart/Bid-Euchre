"""Durable task packet queue for orchestrator-to-author delegation.

Provides the core data contract for Platform-2 orchestrator intake:
- ``TaskPacket`` — a unit of delegated work
- ``TaskAck`` — user acknowledgment after preview (approve/edit/redirect/reject)
- ``TaskResult`` — completion record from the executing lane

Storage is file-based under ``.claude/runtime/task_queue/``:
- ``{packet_id}.json`` — active task packets
- ``{packet_id}.ack.json`` — acknowledgments
- ``{packet_id}.result.json`` — completion results
- ``archive/`` — completed/rejected packets (moved on finalization)
"""

from __future__ import annotations

import fcntl
import json
import logging
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.task_queue")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TASK_QUEUE_DIR = Path(".claude/runtime/task_queue")

VALID_STATUSES = frozenset(
    {
        "pending",
        "previewing",
        "approved",
        "dispatched",
        "completed",
        "rejected",
        "redirected",
    }
)

VALID_PRIORITIES = frozenset({"low", "normal", "high"})

VALID_ACK_ACTIONS = frozenset({"approve", "edit", "redirect", "reject"})

VALID_RESULT_STATUSES = frozenset({"completed", "failed", "blocked"})

# Known author lanes that can receive dispatched work.
KNOWN_AUTHOR_LANES = frozenset(
    {
        "author-a",
        "author-b",
        "author-c",
        "author-d",
        "author-scratch",
    }
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskPacket:
    """A unit of delegated work from orchestrator to an author lane.

    Frozen to enforce immutability — updates create new packets or
    use the ack/result sidecar files.
    """

    packet_id: str
    title: str
    description: str
    owner: str | None
    created_by: str
    created_at: str
    status: str
    scope_declared: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    priority: str = "normal"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status {self.status!r}; expected one of {sorted(VALID_STATUSES)}"
            )
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority {self.priority!r}; expected one of {sorted(VALID_PRIORITIES)}"
            )
        if self.owner is not None and self.owner not in KNOWN_AUTHOR_LANES:
            raise ValueError(
                f"Unknown owner lane {self.owner!r}; expected one of {sorted(KNOWN_AUTHOR_LANES)}"
            )


@dataclass(frozen=True)
class TaskAck:
    """User acknowledgment after previewing a task packet.

    Records the user's decision: approve, edit, redirect, or reject.
    """

    packet_id: str
    action: str
    edited_fields: dict[str, Any] = field(default_factory=dict)
    redirect_to: str | None = None
    acked_at: str = ""
    acked_by: str = "user"

    def __post_init__(self) -> None:
        if self.action not in VALID_ACK_ACTIONS:
            raise ValueError(
                f"Invalid ack action {self.action!r}; expected one of {sorted(VALID_ACK_ACTIONS)}"
            )
        if self.action == "redirect" and not self.redirect_to:
            raise ValueError("redirect_to is required when action is 'redirect'")
        if self.redirect_to and self.redirect_to not in KNOWN_AUTHOR_LANES:
            raise ValueError(
                f"Unknown redirect target {self.redirect_to!r}; "
                f"expected one of {sorted(KNOWN_AUTHOR_LANES)}"
            )


@dataclass(frozen=True)
class TaskResult:
    """Completion record from the executing lane."""

    packet_id: str
    status: str
    summary: str
    pr_number: int | None = None
    completed_at: str = ""
    completed_by: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_RESULT_STATUSES:
            raise ValueError(
                f"Invalid result status {self.status!r}; "
                f"expected one of {sorted(VALID_RESULT_STATUSES)}"
            )


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_packet(
    title: str,
    description: str,
    *,
    owner: str | None = None,
    created_by: str = "orchestrator",
    scope_declared: list[str] | None = None,
    validation: list[str] | None = None,
    priority: str = "normal",
    metadata: dict[str, Any] | None = None,
) -> TaskPacket:
    """Create a new TaskPacket with generated ID and timestamp."""
    return TaskPacket(
        packet_id=uuid.uuid4().hex[:12],
        title=title,
        description=description,
        owner=owner,
        created_by=created_by,
        created_at=_now_iso(),
        status="pending",
        scope_declared=scope_declared or [],
        validation=validation or [],
        priority=priority,
        metadata=metadata or {},
    )


def create_ack(
    packet_id: str,
    action: str,
    *,
    edited_fields: dict[str, Any] | None = None,
    redirect_to: str | None = None,
    acked_by: str = "user",
) -> TaskAck:
    """Create a TaskAck for a given packet."""
    return TaskAck(
        packet_id=packet_id,
        action=action,
        edited_fields=edited_fields or {},
        redirect_to=redirect_to,
        acked_at=_now_iso(),
        acked_by=acked_by,
    )


def create_result(
    packet_id: str,
    status: str,
    summary: str,
    *,
    pr_number: int | None = None,
    completed_by: str = "",
) -> TaskResult:
    """Create a TaskResult for a given packet."""
    return TaskResult(
        packet_id=packet_id,
        status=status,
        summary=summary,
        pr_number=pr_number,
        completed_at=_now_iso(),
        completed_by=completed_by,
    )


# ---------------------------------------------------------------------------
# Queue root
# ---------------------------------------------------------------------------


def shared_task_root(runtime_dir: Path | None = None) -> Path:
    """Return the shared task queue root directory, creating it if needed.

    Args:
        runtime_dir: Override for the runtime directory root.
            Defaults to ``.claude/runtime/task_queue``.

    Returns:
        Path to the task queue directory.
    """
    root = runtime_dir or DEFAULT_TASK_QUEUE_DIR
    root.mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# File I/O helpers (atomic write with flock)
# ---------------------------------------------------------------------------


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Write JSON data atomically using a temporary file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            json.dump(data, f, indent=2, default=str)
            f.write("\n")
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        tmp_path.rename(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read and parse a JSON file, returning None if it doesn't exist."""
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


def save_packet(packet: TaskPacket, root: Path | None = None) -> Path:
    """Persist a TaskPacket to the queue directory.

    Args:
        packet: The task packet to save.
        root: Override for the task queue root directory.

    Returns:
        Path to the written JSON file.
    """
    queue_root = shared_task_root(root)
    path = queue_root / f"{packet.packet_id}.json"
    _write_json_atomic(path, asdict(packet))
    logger.info("Saved task packet %s -> %s", packet.packet_id, path)
    return path


def save_ack(ack: TaskAck, root: Path | None = None) -> Path:
    """Persist a TaskAck to the queue directory.

    Args:
        ack: The acknowledgment to save.
        root: Override for the task queue root directory.

    Returns:
        Path to the written JSON file.
    """
    queue_root = shared_task_root(root)
    path = queue_root / f"{ack.packet_id}.ack.json"
    _write_json_atomic(path, asdict(ack))
    logger.info("Saved ack for packet %s -> %s", ack.packet_id, path)
    return path


def save_result(result: TaskResult, root: Path | None = None) -> Path:
    """Persist a TaskResult to the queue directory.

    Args:
        result: The result to save.
        root: Override for the task queue root directory.

    Returns:
        Path to the written JSON file.
    """
    queue_root = shared_task_root(root)
    path = queue_root / f"{result.packet_id}.result.json"
    _write_json_atomic(path, asdict(result))
    logger.info("Saved result for packet %s -> %s", result.packet_id, path)
    return path


def load_packet(packet_id: str, root: Path | None = None) -> TaskPacket | None:
    """Load a TaskPacket by ID from the queue directory.

    Returns None if the packet file doesn't exist.
    """
    queue_root = shared_task_root(root)
    data = _read_json(queue_root / f"{packet_id}.json")
    if data is None:
        return None
    try:
        return TaskPacket(**data)
    except (TypeError, ValueError) as exc:
        logger.warning("Invalid packet data for %s: %s", packet_id, exc)
        return None


def load_ack(packet_id: str, root: Path | None = None) -> TaskAck | None:
    """Load a TaskAck by packet ID from the queue directory."""
    queue_root = shared_task_root(root)
    data = _read_json(queue_root / f"{packet_id}.ack.json")
    if data is None:
        return None
    try:
        return TaskAck(**data)
    except (TypeError, ValueError) as exc:
        logger.warning("Invalid ack data for %s: %s", packet_id, exc)
        return None


def load_result(packet_id: str, root: Path | None = None) -> TaskResult | None:
    """Load a TaskResult by packet ID from the queue directory."""
    queue_root = shared_task_root(root)
    data = _read_json(queue_root / f"{packet_id}.result.json")
    if data is None:
        return None
    try:
        return TaskResult(**data)
    except (TypeError, ValueError) as exc:
        logger.warning("Invalid result data for %s: %s", packet_id, exc)
        return None


def list_packets(
    root: Path | None = None,
    *,
    status_filter: str | None = None,
    owner_filter: str | None = None,
) -> list[TaskPacket]:
    """List all active TaskPackets in the queue.

    Args:
        root: Override for the task queue root directory.
        status_filter: If set, only return packets with this status.
        owner_filter: If set, only return packets assigned to this lane.

    Returns:
        List of TaskPacket instances, sorted by created_at ascending.
    """
    queue_root = shared_task_root(root)
    packets: list[TaskPacket] = []

    for path in sorted(queue_root.glob("*.json")):
        # Skip sidecar files and temp files
        if path.name.endswith(".ack.json") or path.name.endswith(".result.json"):
            continue
        if path.name.endswith(".tmp"):
            continue

        data = _read_json(path)
        if data is None:
            continue
        try:
            pkt = TaskPacket(**data)
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping invalid packet %s: %s", path.name, exc)
            continue

        if status_filter and pkt.status != status_filter:
            continue
        if owner_filter and pkt.owner != owner_filter:
            continue

        packets.append(pkt)

    return sorted(packets, key=lambda p: p.created_at)


def archive_packet(packet_id: str, root: Path | None = None) -> bool:
    """Move a packet and its sidecars to the archive directory.

    Returns True if any files were moved, False if nothing to archive.
    """
    queue_root = shared_task_root(root)
    archive_dir = queue_root / "archive"
    archive_dir.mkdir(exist_ok=True)

    moved = False
    for suffix in (".json", ".ack.json", ".result.json"):
        src = queue_root / f"{packet_id}{suffix}"
        if src.exists():
            dst = archive_dir / f"{packet_id}{suffix}"
            shutil.move(str(src), str(dst))
            moved = True
            logger.info("Archived %s -> %s", src.name, dst)

    return moved


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


def transition_status(
    packet_id: str,
    new_status: str,
    root: Path | None = None,
) -> TaskPacket | None:
    """Transition a packet to a new status (non-frozen update via re-save).

    Loads the packet, validates the transition, and saves a new copy.
    Returns the updated packet, or None if the packet wasn't found.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid target status {new_status!r}; "
            f"expected one of {sorted(VALID_STATUSES)}"
        )

    pkt = load_packet(packet_id, root)
    if pkt is None:
        logger.warning("Cannot transition: packet %s not found", packet_id)
        return None

    # Build updated packet (frozen dataclass — reconstruct)
    data = asdict(pkt)
    data["status"] = new_status
    updated = TaskPacket(**data)
    save_packet(updated, root)
    logger.info("Transitioned %s: %s -> %s", packet_id, pkt.status, new_status)
    return updated


def apply_ack(
    ack: TaskAck,
    root: Path | None = None,
) -> TaskPacket | None:
    """Apply a TaskAck to its associated packet.

    Handles the four ack actions:
    - approve: transition to ``approved``
    - edit: apply edited_fields and transition to ``approved``
    - redirect: transition to ``redirected``, create new packet for target lane
    - reject: transition to ``rejected`` and archive

    Returns the primary updated packet (or the new redirected packet for
    redirect actions). Returns None if the source packet wasn't found.
    """
    save_ack(ack, root)

    pkt = load_packet(ack.packet_id, root)
    if pkt is None:
        logger.warning("Cannot apply ack: packet %s not found", ack.packet_id)
        return None

    if ack.action == "approve":
        return transition_status(ack.packet_id, "approved", root)

    elif ack.action == "edit":
        # Apply edits and transition to approved
        data = asdict(pkt)
        for key, value in ack.edited_fields.items():
            if key in data and key not in ("packet_id", "created_at", "created_by"):
                data[key] = value
        data["status"] = "approved"
        updated = TaskPacket(**data)
        save_packet(updated, root)
        logger.info("Applied edit ack to %s", ack.packet_id)
        return updated

    elif ack.action == "redirect":
        # Mark original as redirected
        transition_status(ack.packet_id, "redirected", root)
        # Create new packet for target lane
        new_pkt = create_packet(
            title=pkt.title,
            description=pkt.description,
            owner=ack.redirect_to,
            created_by=pkt.created_by,
            scope_declared=list(pkt.scope_declared),
            validation=list(pkt.validation),
            priority=pkt.priority,
            metadata={
                **pkt.metadata,
                "redirected_from": ack.packet_id,
            },
        )
        save_packet(new_pkt, root)
        logger.info(
            "Redirected %s -> new packet %s (owner=%s)",
            ack.packet_id,
            new_pkt.packet_id,
            ack.redirect_to,
        )
        return new_pkt

    elif ack.action == "reject":
        transition_status(ack.packet_id, "rejected", root)
        archive_packet(ack.packet_id, root)
        logger.info("Rejected and archived %s", ack.packet_id)
        return load_packet(ack.packet_id, root)  # Will be None (archived)

    return None


def complete_packet(
    result: TaskResult,
    root: Path | None = None,
    *,
    archive: bool = True,
) -> TaskPacket | None:
    """Record completion and optionally archive the packet.

    Returns the final packet state, or None if not found.
    """
    save_result(result, root)

    new_status = "completed" if result.status == "completed" else result.status
    # Map TaskResult statuses to TaskPacket statuses
    if new_status not in VALID_STATUSES:
        # "failed" and "blocked" are result-only statuses; keep packet as-is
        pkt = load_packet(result.packet_id, root)
        if pkt is not None and archive:
            archive_packet(result.packet_id, root)
        return pkt

    pkt = transition_status(result.packet_id, new_status, root)
    if pkt is not None and archive:
        archive_packet(result.packet_id, root)
    return pkt


# ---------------------------------------------------------------------------
# Queue summary (for status enrichment)
# ---------------------------------------------------------------------------


def queue_summary(root: Path | None = None) -> dict[str, Any]:
    """Return a summary of the current task queue state.

    Useful for status enrichment in ``status.py`` and CLI display.

    Returns:
        Dict with keys: total, by_status (counts), by_owner (counts),
        packets (list of dicts with packet_id, title, status, owner, priority).
    """
    packets = list_packets(root)
    by_status: dict[str, int] = {}
    by_owner: dict[str, int] = {}
    packet_summaries: list[dict[str, Any]] = []

    for pkt in packets:
        by_status[pkt.status] = by_status.get(pkt.status, 0) + 1
        owner_key = pkt.owner or "(unassigned)"
        by_owner[owner_key] = by_owner.get(owner_key, 0) + 1
        packet_summaries.append(
            {
                "packet_id": pkt.packet_id,
                "title": pkt.title,
                "status": pkt.status,
                "owner": pkt.owner,
                "priority": pkt.priority,
                "created_at": pkt.created_at,
            }
        )

    return {
        "total": len(packets),
        "by_status": by_status,
        "by_owner": by_owner,
        "packets": packet_summaries,
    }
