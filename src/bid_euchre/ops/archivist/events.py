"""Archivist event emission — thin wrapper over Primitive A event-writer.

Per Primitive D shaping §4.1.5 and §4.2.4, archivist runs emit four event
types into Primitive A's canonical event schema:

- ``archivist_candidate_proposed`` — a candidate file entry was written
- ``archivist_candidate_promoted`` — operator moved a candidate to KB
- ``archivist_candidate_rejected`` — operator rejected a candidate
- ``archivist_gc_proposed`` — GC-mode proposal written

Emission is **flag-gated** behind the ``ENABLE_D_EVENT_EMISSION`` env var
(default ``"0"``). Flag flip to ``"1"`` is a 1-line follow-up PR after
Primitive A's event-writer helper lands and registers the archivist event
types in ``VALID_EVENT_TYPES``. This mirrors the Primitive C coordination
pattern for ``kb_artifact_promoted`` (C shaping §6.3).

The flag-gate prevents premature emission attempts that would raise
``ValueError`` against an unregistered event type.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.archivist.events")

# Environment variable name; default is OFF.
EMISSION_ENV_VAR = "ENABLE_D_EVENT_EMISSION"

# Lane-identity env var — resolved at emit-time when the caller does not
# pass ``lane_id`` explicitly. The fallback string is deliberately a
# non-lane-ish identifier so that the portability audit's
# ``lane-name-in-code`` regex does not flag this file (see
# ``scripts/internal/audit_portability.py`` for the pattern).
LANE_ID_ENV_VAR = "CLAUDE_AGENT_NAME"
_LANE_ID_FALLBACK = "unknown"

# Archivist event type names (pinned to Primitive A shaping §286-289).
EVENT_CANDIDATE_PROPOSED = "archivist_candidate_proposed"
EVENT_CANDIDATE_PROMOTED = "archivist_candidate_promoted"
EVENT_CANDIDATE_REJECTED = "archivist_candidate_rejected"
EVENT_GC_PROPOSED = "archivist_gc_proposed"


def emission_enabled() -> bool:
    """Return True if ``ENABLE_D_EVENT_EMISSION`` is set to a truthy value.

    Truthy values: ``"1"``, ``"true"``, ``"yes"`` (case-insensitive). Any
    other value (including unset) returns False.
    """
    raw = os.environ.get(EMISSION_ENV_VAR, "0").strip().lower()
    return raw in {"1", "true", "yes"}


def _resolve_lane_id(explicit: str | None) -> str:
    """Resolve the lane-id for an emission.

    Precedence: explicit arg > ``CLAUDE_AGENT_NAME`` env var > fallback.
    Keeping the literal lane names out of this module eliminates
    `lane-name-in-code` portability-audit hits (Pattern 9 / §10.9 Pattern
    10 back-pressure); callers that want a specific lane_id pass it in.
    """
    if explicit is not None:
        return explicit
    env_value = os.environ.get(LANE_ID_ENV_VAR)
    if env_value:
        return env_value
    return _LANE_ID_FALLBACK


def emit_candidate_proposed(
    candidate_path: Path,
    candidate_class: str,
    source_event_ids: list[str],
    *,
    source: str = "ops.archivist",
    lane_id: str | None = None,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit an ``archivist_candidate_proposed`` event when flag is enabled.

    Returns the event dict when emission fires, or ``None`` when the
    emission flag is off (default). Any exception raised by the underlying
    writer is propagated — callers wrap this in best-effort logic where
    archivist success must not depend on event-writer availability.

    Args:
        candidate_path: full path to the dated candidate file
        candidate_class: one of ``"lessons"``, ``"gc"``, ``"postmortem"``
        source_event_ids: trace/event IDs that triggered the candidate
        source: event source identifier
        lane_id: lane owning the event emission; when ``None`` (default)
            the runtime resolves it from ``CLAUDE_AGENT_NAME``.
        events_dir: optional override for event directory
    """
    if not emission_enabled():
        logger.debug(
            "Emission disabled (%s=off); skipping %s",
            EMISSION_ENV_VAR,
            EVENT_CANDIDATE_PROPOSED,
        )
        return None
    return _append(
        EVENT_CANDIDATE_PROPOSED,
        source=source,
        lane_id=_resolve_lane_id(lane_id),
        payload={
            "candidate_path": str(candidate_path),
            "candidate_class": candidate_class,
            "source_event_ids": list(source_event_ids),
        },
        events_dir=events_dir,
    )


def emit_candidate_promoted(
    candidate_path: Path,
    promoted_path: Path,
    operator: str,
    *,
    source: str = "ops.archivist",
    lane_id: str | None = None,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit an ``archivist_candidate_promoted`` event when flag is enabled.

    ``lane_id`` defaults to the ``CLAUDE_AGENT_NAME`` env var when None.
    """
    if not emission_enabled():
        return None
    return _append(
        EVENT_CANDIDATE_PROMOTED,
        source=source,
        lane_id=_resolve_lane_id(lane_id),
        payload={
            "candidate_path": str(candidate_path),
            "promoted_path": str(promoted_path),
            "operator": operator,
        },
        events_dir=events_dir,
    )


def emit_candidate_rejected(
    candidate_path: Path,
    rejection_reason: str,
    operator: str,
    *,
    source: str = "ops.archivist",
    lane_id: str | None = None,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit an ``archivist_candidate_rejected`` event when flag is enabled.

    ``lane_id`` defaults to the ``CLAUDE_AGENT_NAME`` env var when None.
    """
    if not emission_enabled():
        return None
    return _append(
        EVENT_CANDIDATE_REJECTED,
        source=source,
        lane_id=_resolve_lane_id(lane_id),
        payload={
            "candidate_path": str(candidate_path),
            "rejection_reason": rejection_reason,
            "operator": operator,
        },
        events_dir=events_dir,
    )


def emit_gc_proposed(
    candidate_path: Path,
    gc_class: str,
    target_paths: list[str],
    *,
    source: str = "ops.archivist",
    lane_id: str | None = None,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit an ``archivist_gc_proposed`` event when flag is enabled.

    ``gc_class`` is one of ``stale``, ``dead-skill``, ``obsolete-policy``,
    ``orphan``, ``expired`` (shape §4.2.4). ``lane_id`` defaults to the
    ``CLAUDE_AGENT_NAME`` env var when None.
    """
    if not emission_enabled():
        return None
    return _append(
        EVENT_GC_PROPOSED,
        source=source,
        lane_id=_resolve_lane_id(lane_id),
        payload={
            "candidate_path": str(candidate_path),
            "gc_class": gc_class,
            "target_paths": list(target_paths),
        },
        events_dir=events_dir,
    )


def _append(
    event_type: str,
    *,
    source: str,
    lane_id: str,
    payload: dict[str, Any],
    events_dir: Path | None,
) -> dict[str, Any]:
    """Dispatch to the Primitive A event-writer.

    Imported lazily so a missing/partially-installed events module does
    not hard-break import of the archivist package. Under flag-off (the
    default), this function is never called; the flag-on pathway assumes
    A's event-writer has registered the archivist event types.
    """
    from bid_euchre.ops.events import append_event

    return append_event(
        event_type=event_type,
        source=source,
        lane_id=lane_id,
        payload=payload,
        events_dir=events_dir,
    )
