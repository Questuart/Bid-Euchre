"""Durable event log + Primitive A emit() dispatcher.

This module exposes two surfaces:

1. **Legacy API** (``append_event`` / ``read_events`` / ``drain_events``,
   :data:`VALID_EVENT_TYPES`, :data:`DEFAULT_EVENTS_DIR`) — the
   ``.claude/runtime/events/events.jsonl`` pipeline used by 25+ existing
   consumers. Preserved as-is for backward compatibility during the
   Phase 0 rollout; migration to :func:`emit` is incremental.

2. **Primitive A v1.0 dispatcher** (:func:`emit`) — the single public
   entry point for steward event emission per shaping §3.1. Writes to
   ``data/events/events-{YYYY-MM-DD}-{NNN}.jsonl`` via
   :mod:`bid_euchre.ops.event_writer`, validates against
   :data:`~bid_euchre.ops.event_schema.EVENT_FIELD_REGISTRY`, fills the
   §9.7 first-class IDs + §2.4 correlation fields on every record, and
   is **non-blocking + never-raises** per ADR 007.

New emitters MUST use :func:`emit`. Legacy emitters may migrate
incrementally; the two pipelines coexist until Primitive A proves out.

Storage (legacy): ``.claude/runtime/events/events.jsonl``
Storage (v1.0):   ``data/events/events-{YYYY-MM-DD}-{NNN}.jsonl``
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import sys
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops import event_taxonomy, event_writer
from bid_euchre.ops.event_schema import (
    BASELINE_FIELDS,
    EVENT_FIELD_REGISTRY,
    SCHEMA_VERSION,
    VERBOSITY_TIERS,
    get_spec,
    is_known_event_type,
)

logger = logging.getLogger("ops.events")

VALID_EVENT_TYPES = frozenset(
    {
        "task_started",
        "task_completed",
        "task_failed",
        "task_blocked",
        "ci_failure",
        "ci_success",
        "ci_timeout",
        "heartbeat_stale",
        "heartbeat_ok",
        "review_outcome",
        "plan_review_outcome",
        "worktree_created",
        "worktree_removed",
        "worktree_quarantined",
        "worktree_archived",
        "escalation",
        "recovery_action",
        "retry_attempted",
        "task_rerouted",
        "session_started",
        "session_ended",
        "watchdog_finding",
        "scheduler_tick",
        "snapshot_created",
        "snapshot_rolled_back",
        "skill_promoted",
        "skill_disabled",
        "fs_boundary_violation",
        "fs_boundary_exception",
        "pr_comment_ingested",
        "review_request",
        "review_verdict",
        "message_sent",
        "message_delivered",
        "message_acked",
        "message_resolved",
        "message_expired",
        "message_dead_lettered",
        "fleet_idle_shutoff",
        # Slice E (#2169): shadow-mode dispatch advisor recommendation log.
        # Emitted once per dispatch call; never alters the dispatched lane_id.
        "dispatch_recommendation",
    }
)

DEFAULT_EVENTS_DIR = Path(".claude/runtime/events")
EVENTS_FILE = "events.jsonl"
ARCHIVE_FILE = "events.archive.jsonl"
LOCK_FILE = ".events.lock"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def append_event(
    event_type: str,
    source: str,
    lane_id: str,
    payload: dict[str, Any],
    events_dir: Path | None = None,
) -> dict[str, Any]:
    """Append one event to the durable event log.

    Args:
        event_type: Must be one of ``VALID_EVENT_TYPES``.
        source: Identifier for the producer (e.g., ``"ops.tick"``, ``"hook.post-task"``).
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        payload: Arbitrary structured payload data.
        events_dir: Override for events directory. Defaults to
            ``.claude/runtime/events``.

    Returns:
        The event dict that was written.

    Raises:
        ValueError: If ``event_type`` is not in ``VALID_EVENT_TYPES``.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Unknown event_type {event_type!r}. "
            f"Valid types: {sorted(VALID_EVENT_TYPES)}"
        )

    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    event = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "source": source,
        "lane_id": lane_id,
        "payload": payload,
    }

    events_dir.mkdir(parents=True, exist_ok=True)
    lock_path = events_dir / LOCK_FILE
    events_file = events_dir / EVENTS_FILE

    # Lock a dedicated lock file instead of the data file.  drain_events()
    # replaces the data file via rename, which would invalidate an flock
    # held on the old inode — see #938.
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(events_file, "a") as f:
                f.write(json.dumps(event, sort_keys=True) + "\n")
                f.flush()
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    logger.debug("Event appended: %s from %s", event_type, source)
    return event


def read_events(
    events_dir: Path | None = None,
    *,
    since: datetime | None = None,
    event_type: str | None = None,
    lane_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read and filter events from the log.

    Args:
        events_dir: Override for events directory.
        since: Only return events after this timestamp.
        event_type: Filter to this event type.
        lane_id: Filter to this lane.
        limit: Maximum number of events to return (most recent first).

    Returns:
        List of event dicts, most recent first, up to ``limit``.
    """
    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    events_file = events_dir / EVENTS_FILE
    if not events_file.exists():
        return []

    # Use a bounded deque to keep only the last `limit` matching events,
    # avoiding O(N) memory for the full log when limit is small (M2).
    matched: deque[dict[str, Any]] = deque(maxlen=limit)
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed event line: %s", line[:100])
                continue

            # Apply filters
            if event_type is not None and event.get("event_type") != event_type:
                continue
            if lane_id is not None and event.get("lane_id") != lane_id:
                continue
            if since is not None:
                try:
                    event_time = datetime.fromisoformat(event["timestamp"])
                    if event_time <= since:
                        continue
                except (KeyError, ValueError):
                    continue

            matched.append(event)

    # Most recent first
    result = list(matched)
    result.reverse()
    return result


def drain_events(
    events_dir: Path | None = None,
    *,
    up_to: datetime | None = None,
) -> int:
    """Archive processed events from the active log.

    Moves events with timestamps <= ``up_to`` from the active log to
    the archive file. If ``up_to`` is None, drains all events.

    Crash safety (H1):
        The active log is updated via atomic rename *before* archive append.
        If a crash occurs between rename and archive append, drained events
        are removed from the active log but missing from the archive. This
        is acceptable because (a) events are advisory, not transactional,
        and (b) the archive is best-effort historical storage.

    Concurrency (M7):
        An exclusive ``fcntl.flock()`` is held for the entire
        read→filter→rename→archive cycle, serializing drain with concurrent
        ``append_event()`` calls that acquire the same lock.

    Args:
        events_dir: Override for events directory.
        up_to: Drain events up to this timestamp. None drains all.

    Returns:
        Number of events drained.
    """
    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    events_file = events_dir / EVENTS_FILE
    archive_file = events_dir / ARCHIVE_FILE

    if not events_file.exists():
        return 0

    to_drain: list[str] = []
    to_keep: list[str] = []

    # Lock a dedicated lock file (same one used by append_event) so that
    # concurrent appenders cannot write to an inode that is about to be
    # replaced by rename — see #938.
    lock_path = events_dir / LOCK_FILE
    with open(lock_path, "a") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        try:
            with open(events_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    if up_to is None:
                        to_drain.append(line)
                        continue

                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event["timestamp"])
                        if event_time <= up_to:
                            to_drain.append(line)
                        else:
                            to_keep.append(line)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        # Keep malformed lines in active log
                        to_keep.append(line)

            if not to_drain:
                return 0

            # 1. Write remaining events to temp file (while holding lock)
            tmp_file = events_file.with_suffix(".tmp")
            with open(tmp_file, "w") as tmp:
                for line in to_keep:
                    tmp.write(line + "\n")

            # 2. Atomic rename: removes drained events from active log.
            #    Done BEFORE archive append so crash can only lose archive
            #    entries (best-effort), never duplicate them.
            tmp_file.rename(events_file)

            # 3. Append drained events to archive (best-effort historical)
            with open(archive_file, "a") as af:
                for line in to_drain:
                    af.write(line + "\n")
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)

    logger.info("Drained %d events to archive", len(to_drain))
    return len(to_drain)


# ===========================================================================
# Primitive A v1.0 — emit() dispatcher
# ===========================================================================

# Per shaping §3.1-§3.4 + ADR 007:
# - One public entry point: emit(event_type, **fields) -> None
# - One internal dispatch function: _dispatch(event_record) -> None
# - Non-blocking + never-raises (exceptions caught + logged to stderr)
# - Registry-driven contract (unknown event_type logged, no JSONL write)
# - Baseline fields (§9.7 IDs + §2.4 correlation) populated by dispatcher
# - Pattern 8: unknown fields routed to extra_fields (bug marker)
# - Verbosity tiers: minimal / summary / full

# ===========================================================================

_PROJECT_ID = "bid-euchre"
"""Constant per shaping §2.3 row 1 — identifies the cell; portable to
future multi-cell pipelines."""

_CELL_ID = "bid-euchre"
"""Constant per shaping §2.3 row 2 — distinct field for adapter contract
clarity, currently equal to ``_PROJECT_ID``."""

# Cached per-session values. Populated lazily in ``_session_id()`` /
# ``_prompt_policy_version()`` to avoid doing env lookups at import time.
_CACHED_SESSION_ID: str | None = None
_CACHED_PROMPT_POLICY_VERSION: str | None = None


def _session_id() -> str:
    """Return the cached session_id per §2.3 row 3.

    Reads ``CLAUDE_SESSION_ID`` env var, falling back to a UUID4 when
    unset (e.g., headless scripts). The value is cached for the process
    lifetime so subsequent emissions in the same process share a stable
    session_id.
    """
    global _CACHED_SESSION_ID
    if _CACHED_SESSION_ID is None:
        env_val = os.environ.get("CLAUDE_SESSION_ID")
        _CACHED_SESSION_ID = env_val if env_val else str(uuid.uuid4())
    return _CACHED_SESSION_ID


def _lane_id() -> str | None:
    """Return the lane_id per §2.3 row 5 (``CLAUDE_AGENT_NAME`` env var)."""
    return os.environ.get("CLAUDE_AGENT_NAME")


def _prompt_policy_version() -> str:
    """Return the cached prompt_policy_version per §2.3 row 8.

    Phase 0: returns ``"unset"`` since Primitive B.3 registry is a
    separate deliverable. When B.3 lands, this helper will read the
    registry version instead.
    """
    global _CACHED_PROMPT_POLICY_VERSION
    if _CACHED_PROMPT_POLICY_VERSION is None:
        _CACHED_PROMPT_POLICY_VERSION = os.environ.get(
            "STEWARD_PROMPT_POLICY_VERSION", "unset"
        )
    return _CACHED_PROMPT_POLICY_VERSION


def _resolve_verbosity(requested: str | None) -> str:
    """Return the effective verbosity tier for this emission.

    Resolution order per shaping §3.3:

    1. Explicit ``_verbosity`` kwarg to :func:`emit`.
    2. ``STEWARD_EVENTS_VERBOSITY`` env var.
    3. ``EventTypeSpec.verbosity_default`` from the registry.
    4. ``"summary"`` (ultimate fallback).
    """
    if requested and requested in VERBOSITY_TIERS:
        return requested
    env_val = os.environ.get("STEWARD_EVENTS_VERBOSITY")
    if env_val and env_val in VERBOSITY_TIERS:
        return env_val
    return "summary"


def _log_fallback(msg: str, *args: Any) -> None:
    """Stderr fallback logger per shaping §2.7 never-raises contract.

    Uses stderr directly (not :mod:`logging`) so a misconfigured logger
    can't swallow the signal. The emit path must never propagate
    exceptions to the caller, so this is the last-resort channel.
    """
    try:
        formatted = msg % args if args else msg
        print(f"[ops.events] {formatted}", file=sys.stderr)
    except Exception:  # pragma: no cover — defensive
        pass


def _validate_and_split_fields(
    event_type: str,
    caller_fields: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Split caller-supplied fields into (known, extra, missing_required).

    Per shaping §3.4:

    - Registry-declared required/optional fields land in ``known``.
    - §9.7 first-class IDs + correlation baseline — not caller-owned;
      the dispatcher populates these. If the caller passes them, we
      honor the override but log a debug note.
    - Anything else lands in ``extra_fields`` (Pattern 8 marker).

    Returns a tuple of:
        (known_fields_dict, extra_fields_dict, missing_required_list)

    ``missing_required`` names fields the registry marks as required
    but which the caller omitted. The dispatcher refuses to emit when
    this list is non-empty (per shaping §3.4).
    """
    spec = get_spec(event_type)
    known: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    missing: list[str] = []

    if spec is None:
        # Unknown event type — caller should never reach here; guarded in emit.
        return caller_fields, {}, []

    # Partition caller fields into known-to-registry vs extra_fields.
    registered_slots = set(spec.required_fields) | set(spec.optional_fields)
    # Baseline fields (§9.7 IDs + correlation + event_type) are dispatcher-
    # owned; caller overrides are honored but land in known.
    for key, value in caller_fields.items():
        if key in BASELINE_FIELDS or key in registered_slots:
            known[key] = value
        else:
            extra[key] = value

    # Missing-required check — baseline fields excluded (dispatcher fills).
    for req in spec.required_fields:
        if req in BASELINE_FIELDS:
            continue
        if req not in caller_fields:
            missing.append(req)

    return known, extra, missing


def _populate_baseline(
    event_type: str,
    caller_fields: dict[str, Any],
    log_dir: Path,
) -> dict[str, Any]:
    """Build the baseline field block for a new event record.

    Per shaping §2.3 + §2.4 — every record carries the 9 §9.7 IDs + 4
    correlation fields + ``event_type``. Caller-supplied values for
    these fields override the dispatcher defaults (useful for
    worktree-create events where the lane_id is the *target* lane,
    not the emitting lane).
    """
    # §9.7 first-class IDs
    baseline: dict[str, Any] = {
        "event_type": event_type,
        "project_id": caller_fields.get("project_id", _PROJECT_ID),
        "cell_id": caller_fields.get("cell_id", _CELL_ID),
        "session_id": caller_fields.get("session_id", _session_id()),
        "task_id": caller_fields.get("task_id"),
        "lane_id": caller_fields.get("lane_id", _lane_id()),
        "trace_id": caller_fields.get("trace_id"),
        "incident_fingerprint": caller_fields.get("incident_fingerprint"),
        "prompt_policy_version": caller_fields.get(
            "prompt_policy_version", _prompt_policy_version()
        ),
        "schema_version": caller_fields.get("schema_version", SCHEMA_VERSION),
    }
    # §2.4 correlation fields
    baseline["seq"] = caller_fields.get("seq") or event_writer.next_seq(log_dir=log_dir)
    baseline["pid"] = caller_fields.get("pid") or os.getpid()
    baseline["timestamp_ns"] = caller_fields.get("timestamp_ns") or time.time_ns()
    baseline["turn_id"] = caller_fields.get(
        "turn_id", event_writer.get_turn_id(log_dir=log_dir)
    )
    return baseline


def _apply_verbosity(event_record: dict[str, Any], tier: str) -> dict[str, Any]:
    """Apply verbosity-tier truncation to the event record.

    - ``minimal``: baseline only (IDs + correlation + event_type + a
      tiny ``success``/``failure`` flag if derivable).
    - ``summary``: baseline + required fields (large payloads truncated).
    - ``full``: everything — including ``extra_fields``.
    """
    if tier == "full":
        return event_record

    baseline_keys = set(BASELINE_FIELDS)

    if tier == "minimal":
        kept = {k: v for k, v in event_record.items() if k in baseline_keys}
        # Preserve a minimal success/failure hint if present.
        for hint in ("success", "outcome", "error_category"):
            if hint in event_record:
                kept[hint] = event_record[hint]
        return kept

    # summary tier: baseline + required + truncated large strings
    spec = get_spec(event_record.get("event_type", ""))
    if spec is None:
        return event_record

    keep_keys = baseline_keys | set(spec.required_fields) | {"extra_fields"}
    summary: dict[str, Any] = {}
    for key, value in event_record.items():
        if key in keep_keys:
            summary[key] = _truncate_large(value)
    return summary


_SUMMARY_TRUNCATE_CHARS = 2000


def _truncate_large(value: Any) -> Any:
    """Truncate very large string values for the ``summary`` tier."""
    if isinstance(value, str) and len(value) > _SUMMARY_TRUNCATE_CHARS:
        return value[: _SUMMARY_TRUNCATE_CHARS - 1] + "…"
    return value


def _dispatch(event_record: dict[str, Any], log_dir: Path) -> None:
    """Internal dispatch. Writes event_record to JSONL. Never-raises."""
    try:
        event_writer.write_event(event_record, log_dir=log_dir)
    except (
        Exception
    ) as exc:  # pragma: no cover — defensive; writer is never-raises already
        _log_fallback(
            "write_event failed for %s: %s",
            event_record.get("event_type", "?"),
            exc,
        )


def _env_events_log_dir() -> Path:
    """Resolve the v1.0 events log dir per shaping §3.2.

    Defaults to ``data/events/``; overridable via
    ``STEWARD_EVENTS_LOG_DIR``.
    """
    override = os.environ.get("STEWARD_EVENTS_LOG_DIR")
    if override:
        return Path(override)
    return Path("data/events")


def emit(
    event_type: str,
    *,
    _verbosity: str | None = None,
    **fields: Any,
) -> None:
    """Emit one event record to the Primitive A v1.0 JSONL pipeline.

    This is the single public entry point per shaping §3.1. Callers
    invoke it with the event type and event-type-specific fields; the
    dispatcher fills the §9.7 first-class IDs + §2.4 correlation fields,
    validates against :data:`EVENT_FIELD_REGISTRY`, applies verbosity,
    and writes a JSONL line.

    **Never raises.** Per ADR 007 adopted pattern, any exception during
    the dispatch path is caught and logged to stderr — the calling hook
    or tool must never crash because of a misbehaving emitter.

    Args:
        event_type: Must be a key of
            :data:`~bid_euchre.ops.event_schema.EVENT_FIELD_REGISTRY`.
        _verbosity: Optional per-call override: ``"minimal"`` |
            ``"summary"`` | ``"full"``. Falls back to
            ``STEWARD_EVENTS_VERBOSITY`` env var, then the registry
            default, then ``"summary"``.
        **fields: Event-type-specific fields. Caller-supplied §9.7 IDs
            override dispatcher defaults. Fields outside the registry
            are routed to ``extra_fields`` (Pattern 8 bug-marker).

    Examples:
        >>> emit(
        ...     "task_started",
        ...     packet_id="abc123",
        ...     dispatched_by="orchestrator",
        ...     priority="high",
        ...     domain="platform",
        ... )  # doctest: +SKIP
    """
    try:
        log_dir = _env_events_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        # 1. Unknown-event-type gate (shaping §3.4).
        if not is_known_event_type(event_type):
            _log_fallback(
                "rejected unknown event_type %r; no JSONL write. Registry "
                "has %d known types.",
                event_type,
                len(EVENT_FIELD_REGISTRY),
            )
            return

        # 2. Split caller fields into (known, extra, missing_required).
        known, extra, missing = _validate_and_split_fields(event_type, fields)
        if missing:
            _log_fallback(
                "rejected %s emission: missing required fields %s",
                event_type,
                sorted(missing),
            )
            return

        # 3. Populate baseline §9.7 IDs + §2.4 correlation fields.
        baseline = _populate_baseline(event_type, known, log_dir)

        # 4. Build the full record. Baseline first (dispatcher-owned keys),
        #    then caller-supplied known slots, then extra_fields if any.
        record: dict[str, Any] = {}
        record.update(baseline)
        for key, value in known.items():
            if key not in baseline:
                record[key] = value
        if extra:
            # Merge with any caller-supplied extra_fields dict.
            existing_extra = record.pop("extra_fields", None) or {}
            if isinstance(existing_extra, dict):
                merged_extra = {**existing_extra, **extra}
            else:
                merged_extra = dict(extra)
            record["extra_fields"] = merged_extra

        # 5. Apply verbosity tier.
        tier = _resolve_verbosity(_verbosity)
        record = _apply_verbosity(record, tier)

        # 6. Dispatch to JSONL writer.
        _dispatch(record, log_dir)
    except Exception as exc:  # pragma: no cover — outer never-raises guard
        _log_fallback("emit(%s) unexpected failure: %s", event_type, exc)


def reset_cached_session() -> None:
    """Test helper — clear cached session_id / prompt_policy_version.

    Pure test surface: production code should never call this. Allows
    test fixtures to exercise emit() across multiple "sessions" within a
    single process.
    """
    global _CACHED_SESSION_ID, _CACHED_PROMPT_POLICY_VERSION
    _CACHED_SESSION_ID = None
    _CACHED_PROMPT_POLICY_VERSION = None


# Re-export taxonomy helpers for downstream convenience (consumers that
# emit fail/incident events typically want ``categorize_error`` +
# ``incident_fingerprint`` available on the same import).
categorize_error = event_taxonomy.categorize_error
build_status_message = event_taxonomy.build_status_message
incident_fingerprint = event_taxonomy.incident_fingerprint
