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

import json
import logging
import os
import shutil
import tempfile
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

# Known execution domains for routing.  ``None`` means "unspecified" and
# the orchestrator may assign one later.
KNOWN_DOMAINS: frozenset[str] = frozenset({"platform", "browser-game"})

VALID_ACK_ACTIONS = frozenset({"approve", "edit", "redirect", "reject"})

VALID_RESULT_STATUSES = frozenset({"completed", "failed", "blocked"})

# ---------------------------------------------------------------------------
# Routing metadata contract (issue #2169 — token-economy Slice C)
# ---------------------------------------------------------------------------
#
# TaskPacket.metadata remains dict[str, Any] to preserve the frozen dataclass
# extension point, but four keys are reserved for routing/learning inputs.
# Downstream consumers (fixed-policy controls, advisory dispatch scorer,
# outcome-join reporting) rely on these keys being stable and, when present,
# being drawn from the documented value spaces below.
#
# All keys are OPTIONAL. A packet without any routing metadata is always
# legal and never rejected. Validation is advisory via
# :func:`validate_routing_metadata`; the TaskPacket dataclass itself does not
# enforce routing-key typing so existing callers that store unrelated metadata
# keep working without change.
#
# Key semantics:
#   task_type           — coarse classification used by the advisor scorer
#                         and outcome rollups. Must be a non-empty str when
#                         present; preferred values are in VALID_TASK_TYPES
#                         (advisory — unknown values are a warning, not a
#                         hard error, so the taxonomy can evolve without
#                         breaking legacy packets).
#   complexity_estimate — integer 1..5 inclusive, orchestrator-assigned at
#                         dispatch time. Higher = more complex.
#   model_hint          — preferred model tier for the task. Known values in
#                         VALID_MODEL_HINTS; unknown values are a warning.
#   effort_hint         — preferred effort envelope (token budget / think
#                         depth). Known values in VALID_EFFORT_HINTS.
#
ROUTING_METADATA_KEYS: frozenset[str] = frozenset(
    {"task_type", "complexity_estimate", "model_hint", "effort_hint"}
)

# Preferred task_type taxonomy. Unknown values do not hard-fail — they are
# surfaced by validate_routing_metadata() as advisory warnings so downstream
# reporting can highlight unknowns without blocking dispatch.
VALID_TASK_TYPES: frozenset[str] = frozenset(
    {
        "docs",
        "tests",
        "convention",
        "feature",
        "bugfix",
        "ops",
        "review",
        "investigation",
        "refactor",
    }
)

# Known model hints. The steward runs on Claude Code; these mirror the
# public Claude 4 model tier names. Unknown values are a warning, not an
# error — the enum is expected to evolve with model releases.
VALID_MODEL_HINTS: frozenset[str] = frozenset({"opus", "sonnet", "haiku"})

# Effort hints. Represent the orchestrator's budget intent; the worker lane
# may still adjust within its own policy.
VALID_EFFORT_HINTS: frozenset[str] = frozenset({"low", "medium", "high"})

# Complexity estimate is an integer 1..5 inclusive.
MIN_COMPLEXITY: int = 1
MAX_COMPLEXITY: int = 5

# ---------------------------------------------------------------------------
# Lane topology — provided by the adapter layer
# ---------------------------------------------------------------------------


def get_known_lanes() -> frozenset[str]:
    """Return the set of known author lanes from the lane config adapter.

    This replaces the former module-level ``KNOWN_AUTHOR_LANES`` constant.
    Lane topology is now owned by
    :class:`~bid_euchre.ops.adapters.bid_euchre.BidEuchreLaneConfig`
    and accessed via the singleton accessor.
    """
    from bid_euchre.ops.adapters.bid_euchre import get_lane_config

    return get_lane_config().known_lanes()


def _get_legacy_lanes() -> frozenset[str]:
    """Return the set of legacy/retired lane identifiers."""
    from bid_euchre.ops.adapters.bid_euchre import get_lane_config

    return get_lane_config().legacy_lanes()


# Backward-compatible re-export.  External callers that imported
# ``KNOWN_AUTHOR_LANES`` from this module will continue to work, but
# should migrate to ``get_known_lanes()`` for future portability.
KNOWN_AUTHOR_LANES: frozenset[str] = get_known_lanes()

_LEGACY_AUTHOR_LANES: frozenset[str] = _get_legacy_lanes()

# Valid state transitions for the task packet lifecycle.
# Enforced by transition_status() to prevent incoherent state from
# misbehaving agents.
#
# The pending state allows both preview (non-trivial) and direct approval
# (trivial tasks that skip preview per orchestrator profile guidelines).
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"previewing", "approved", "rejected", "redirected"}),
    "previewing": frozenset({"approved", "rejected", "redirected"}),
    "approved": frozenset({"dispatched", "rejected"}),
    "dispatched": frozenset({"completed"}),
    "completed": frozenset(),  # terminal
    "rejected": frozenset(),  # terminal
    "redirected": frozenset(),  # terminal
}


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
    domain: str | None = None
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
        _lanes = get_known_lanes()
        if self.owner is not None and self.owner not in _lanes:
            raise ValueError(
                f"Unknown owner lane {self.owner!r}; expected one of {sorted(_lanes)}"
            )
        if self.domain is not None and self.domain not in KNOWN_DOMAINS:
            raise ValueError(
                f"Unknown domain {self.domain!r}; expected one of {sorted(KNOWN_DOMAINS)} or None"
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
        _ack_lanes = get_known_lanes()
        if self.redirect_to and self.redirect_to not in _ack_lanes:
            raise ValueError(
                f"Unknown redirect target {self.redirect_to!r}; "
                f"expected one of {sorted(_ack_lanes)}"
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


def _normalize_task_payload(data: dict[str, Any], path: str) -> dict[str, Any] | None:
    """Normalize legacy packet payloads before dataclass validation.

    Legacy `.claude/runtime/task_queue/*.json` artifacts from earlier
    lane layouts can include retired lane names (for example
    ``author-scratch``). Those packets should remain visible for audit
    history but must not fail queue reads that support supervisor
    dashboards and status checks.
    """
    normalized = dict(data)

    owner = normalized.get("owner")
    if owner in _LEGACY_AUTHOR_LANES:
        logger.debug(
            "Retaining legacy packet owner %r in %s with legacy compatibility",
            owner,
            path,
        )
        normalized["owner"] = None

    return normalized


def create_packet(
    title: str,
    description: str,
    *,
    owner: str | None = None,
    created_by: str = "orchestrator",
    scope_declared: list[str] | None = None,
    validation: list[str] | None = None,
    priority: str = "normal",
    domain: str | None = None,
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
        domain=domain,
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
    """Write JSON data atomically using a unique temporary file + rename.

    Uses ``tempfile.mkstemp`` to create a unique temp file in the target
    directory, avoiding races when multiple writers target the same path
    concurrently.  Relies on POSIX ``rename()`` atomicity for crash safety.
    No cross-process locking — last writer wins in concurrent scenarios.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
            f.write("\n")
        Path(tmp_name).rename(path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
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
        return TaskPacket(**_normalize_task_payload(data, f"{packet_id}.json"))
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
    domain_filter: str | None = None,
) -> list[TaskPacket]:
    """List all active TaskPackets in the queue.

    Args:
        root: Override for the task queue root directory.
        status_filter: If set, only return packets with this status.
        owner_filter: If set, only return packets assigned to this lane.
        domain_filter: If set, only return packets with this domain.

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
            pkt = TaskPacket(**_normalize_task_payload(data, path.name))
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping invalid packet %s: %s", path.name, exc)
            continue

        if status_filter and pkt.status != status_filter:
            continue
        if owner_filter and pkt.owner != owner_filter:
            continue
        if domain_filter and pkt.domain != domain_filter:
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

    # Validate the transition against the state machine
    allowed = VALID_TRANSITIONS.get(pkt.status, frozenset())
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition {pkt.status!r} -> {new_status!r} for "
            f"packet {packet_id!r}; allowed targets from {pkt.status!r}: "
            f"{sorted(allowed) if allowed else '(terminal state)'}"
        )

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
            domain=pkt.domain,
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
        rejected_pkt = transition_status(ack.packet_id, "rejected", root)
        archive_packet(ack.packet_id, root)
        logger.info("Rejected and archived %s", ack.packet_id)
        return rejected_pkt  # Return the final state before archive

    return None


# ---------------------------------------------------------------------------
# Routing metadata accessors and validation (issue #2169 — Slice C)
# ---------------------------------------------------------------------------
#
# These helpers are the stable public surface for reading routing metadata
# off a TaskPacket. Use them instead of indexing ``packet.metadata`` directly
# so that future schema migrations (e.g. promoting routing keys to top-level
# fields) can be made in one place.


def get_task_type(packet: TaskPacket) -> str | None:
    """Return the packet's ``task_type`` routing metadata, or ``None`` if absent.

    Unknown values are returned as-is; the taxonomy is advisory, not
    enforced (see :func:`validate_routing_metadata`).
    """
    value = packet.metadata.get("task_type")
    if value is None:
        return None
    # Defensive cast: JSON round-trips can produce non-str values for legacy
    # packets. Treat anything that isn't a non-empty string as absent.
    if not isinstance(value, str) or not value:
        return None
    return value


def get_complexity(packet: TaskPacket) -> int | None:
    """Return the packet's ``complexity_estimate`` or ``None`` if absent/invalid.

    Values outside ``1..5`` are treated as absent so callers never consume a
    bad value silently.
    """
    value = packet.metadata.get("complexity_estimate")
    if value is None:
        return None
    # JSON integers survive round-trip; reject bool (which is an int subclass
    # in Python) and any non-integer to keep the scorer input type-safe.
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < MIN_COMPLEXITY or value > MAX_COMPLEXITY:
        return None
    return value


def get_model_hint(packet: TaskPacket) -> str | None:
    """Return the packet's ``model_hint`` or ``None`` if absent.

    Unknown values are returned as-is; callers that must restrict to
    :data:`VALID_MODEL_HINTS` should filter after reading.
    """
    value = packet.metadata.get("model_hint")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return None
    return value


def get_effort_hint(packet: TaskPacket) -> str | None:
    """Return the packet's ``effort_hint`` or ``None`` if absent."""
    value = packet.metadata.get("effort_hint")
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return None
    return value


def validate_routing_metadata(
    metadata: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Validate routing metadata keys against the documented contract.

    Returns a ``(errors, warnings)`` tuple:

    - **errors** — type/range violations that reject a user-facing create
      call (e.g. ``complexity_estimate=7``, ``task_type=42``).  CLI callers
      should surface these as a non-zero exit.
    - **warnings** — values that are well-typed but outside the currently
      known enum (unknown ``task_type``, unknown ``model_hint`` /
      ``effort_hint``).  Downstream reporting can highlight these without
      blocking dispatch, which keeps the taxonomy evolvable.

    This function is intentionally *not* called from ``TaskPacket.__post_init__``
    — existing callers that store arbitrary metadata keys must keep working.
    Enforcement happens at the CLI ``task create`` boundary so new packets
    land with clean routing metadata while archived packets remain loadable.
    """
    errors: list[str] = []
    warnings: list[str] = []

    task_type = metadata.get("task_type")
    if task_type is not None:
        if not isinstance(task_type, str) or not task_type:
            errors.append(f"task_type must be a non-empty string, got {task_type!r}")
        elif task_type not in VALID_TASK_TYPES:
            warnings.append(
                f"task_type {task_type!r} is not in the preferred taxonomy "
                f"{sorted(VALID_TASK_TYPES)}"
            )

    complexity = metadata.get("complexity_estimate")
    if complexity is not None:
        # bool is a subclass of int — reject it explicitly so True doesn't
        # become complexity 1.
        if isinstance(complexity, bool) or not isinstance(complexity, int):
            errors.append(
                f"complexity_estimate must be an int in "
                f"[{MIN_COMPLEXITY}, {MAX_COMPLEXITY}], got {complexity!r}"
            )
        elif complexity < MIN_COMPLEXITY or complexity > MAX_COMPLEXITY:
            errors.append(
                f"complexity_estimate {complexity} outside allowed range "
                f"[{MIN_COMPLEXITY}, {MAX_COMPLEXITY}]"
            )

    model_hint = metadata.get("model_hint")
    if model_hint is not None:
        if not isinstance(model_hint, str) or not model_hint:
            errors.append(f"model_hint must be a non-empty string, got {model_hint!r}")
        elif model_hint not in VALID_MODEL_HINTS:
            warnings.append(
                f"model_hint {model_hint!r} not in known set "
                f"{sorted(VALID_MODEL_HINTS)}"
            )

    effort_hint = metadata.get("effort_hint")
    if effort_hint is not None:
        if not isinstance(effort_hint, str) or not effort_hint:
            errors.append(
                f"effort_hint must be a non-empty string, got {effort_hint!r}"
            )
        elif effort_hint not in VALID_EFFORT_HINTS:
            errors.append(
                f"effort_hint {effort_hint!r} not in allowed set "
                f"{sorted(VALID_EFFORT_HINTS)}"
            )

    return errors, warnings


def update_packet_metadata(
    packet_id: str,
    updates: dict[str, Any],
    root: Path | None = None,
) -> TaskPacket | None:
    """Update metadata fields on an existing packet.

    Merges *updates* into the packet's ``metadata`` dict and re-saves.
    Does **not** change the packet status — this is a data-only mutation.

    Args:
        packet_id: The packet to update.
        updates: Key-value pairs to merge into ``metadata``.
        root: Override for the task queue root directory.

    Returns:
        The updated packet, or None if the packet was not found.
    """
    pkt = load_packet(packet_id, root)
    if pkt is None:
        logger.warning("Cannot update metadata: packet %s not found", packet_id)
        return None

    merged = {**pkt.metadata, **updates}
    data = asdict(pkt)
    data["metadata"] = merged
    updated = TaskPacket(**data)
    save_packet(updated, root)
    logger.info("Updated metadata on %s: %s", packet_id, list(updates.keys()))
    return updated


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
    by_domain: dict[str, int] = {}
    packet_summaries: list[dict[str, Any]] = []

    for pkt in packets:
        by_status[pkt.status] = by_status.get(pkt.status, 0) + 1
        owner_key = pkt.owner or "(unassigned)"
        by_owner[owner_key] = by_owner.get(owner_key, 0) + 1
        domain_key = pkt.domain or "(unspecified)"
        by_domain[domain_key] = by_domain.get(domain_key, 0) + 1
        packet_summaries.append(
            {
                "packet_id": pkt.packet_id,
                "title": pkt.title,
                "status": pkt.status,
                "owner": pkt.owner,
                "priority": pkt.priority,
                "domain": pkt.domain,
                "created_at": pkt.created_at,
            }
        )

    return {
        "total": len(packets),
        "by_status": by_status,
        "by_owner": by_owner,
        "by_domain": by_domain,
        "packets": packet_summaries,
    }
