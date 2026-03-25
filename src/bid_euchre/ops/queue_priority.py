"""Queue priority scoring and auto-reorder logic (Platform-9b PR1).

Pure scoring functions for ordering pending task packets in the queue.
Scores are computed from four dimensions:

1. **Age** — older packets score higher (prevents starvation)
2. **Priority field** — high > normal > low (explicit urgency signal)
3. **Dependency chain depth** — fewer blockers score higher (ready-to-run first)
4. **Lane affinity** — packets matching a preferred lane score higher

All functions are pure (no I/O, no file access). The queue_priority module
reads ``TaskPacket`` data via its public fields only and never imports
file-based queue operations.

Usage::

    from bid_euchre.ops.queue_priority import score_packet, reorder_queue

    scored = score_packet(packet, now=datetime.now(timezone.utc))
    ordered = reorder_queue(packets, now=datetime.now(timezone.utc))
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Protocol — duck-typed TaskPacket interface (avoids circular imports)
# ---------------------------------------------------------------------------


class PacketLike(Protocol):
    """Minimal interface for a task packet used by the scoring functions.

    This protocol avoids importing ``TaskPacket`` directly, keeping the
    module dependency-free and easy to test with plain dataclasses.
    """

    @property
    def packet_id(self) -> str: ...

    @property
    def priority(self) -> str: ...

    @property
    def created_at(self) -> str: ...

    @property
    def owner(self) -> str | None: ...

    @property
    def metadata(self) -> dict[str, Any]: ...

    @property
    def status(self) -> str: ...


# ---------------------------------------------------------------------------
# Score weights (tunable)
# ---------------------------------------------------------------------------

# Points per hour of queue age.  A packet waiting 4 hours gains +4.0 age
# points.  Capped at ``MAX_AGE_HOURS`` to prevent unbounded growth.
AGE_WEIGHT_PER_HOUR: float = 1.0

# Maximum hours of age that contribute to scoring.
MAX_AGE_HOURS: float = 48.0

# Base score for each priority level.  Higher = dispatched sooner.
PRIORITY_SCORES: dict[str, float] = {
    "high": 10.0,
    "normal": 5.0,
    "low": 1.0,
}

# Penalty per dependency chain link.  A packet with chain_depth=3 loses
# 3 × DEPENDENCY_PENALTY points, pushing it behind shallower packets.
DEPENDENCY_PENALTY: float = 2.0

# Maximum chain depth that incurs penalty (avoids runaway subtraction).
MAX_CHAIN_DEPTH: int = 10

# Bonus when the packet's owner matches the preferred lane.
LANE_AFFINITY_BONUS: float = 3.0


# ---------------------------------------------------------------------------
# Score result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorityScore:
    """Breakdown of a packet's priority score.

    Attributes:
        packet_id: Identifying packet.
        total: Aggregate score (higher = sooner).
        age_score: Contribution from queue age.
        priority_score: Contribution from the priority field.
        dependency_score: Penalty from dependency chain depth.
        affinity_score: Bonus from lane affinity match.
    """

    packet_id: str
    total: float
    age_score: float
    priority_score: float
    dependency_score: float
    affinity_score: float


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

    Handles both ``2026-03-25T07:20:49Z`` and ``2026-03-25T07:20:49+00:00``
    formats.  Falls back to naive parsing with UTC assumption.
    """
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(ts)
        # Ensure timezone-aware (treat naive as UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        # Best-effort: treat as UTC
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _age_hours(created_at: str, now: datetime) -> float:
    """Return the age of a packet in fractional hours, capped at MAX_AGE_HOURS."""
    created = _parse_iso(created_at)
    delta = (now - created).total_seconds() / 3600.0
    return min(max(delta, 0.0), MAX_AGE_HOURS)


def _chain_depth(packet: PacketLike) -> int:
    """Extract dependency chain depth from packet metadata.

    Looks for ``metadata["chain_depth"]`` (int).  Defaults to 0 if absent.
    Clamped to [0, MAX_CHAIN_DEPTH].
    """
    raw = packet.metadata.get("chain_depth", 0)
    try:
        depth = int(raw)
    except (TypeError, ValueError):
        depth = 0
    return min(max(depth, 0), MAX_CHAIN_DEPTH)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_packet(
    packet: PacketLike,
    *,
    now: datetime | None = None,
    preferred_lane: str | None = None,
) -> PriorityScore:
    """Compute a priority score for a single task packet.

    Args:
        packet: A task packet (or any object satisfying ``PacketLike``).
        now: Reference time for age calculation.  Defaults to UTC now.
        preferred_lane: If the packet's ``owner`` matches this lane,
            an affinity bonus is applied.

    Returns:
        A ``PriorityScore`` with the breakdown and total.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    age_h = _age_hours(packet.created_at, now)
    age_score = age_h * AGE_WEIGHT_PER_HOUR

    priority_score = PRIORITY_SCORES.get(packet.priority, PRIORITY_SCORES["normal"])

    depth = _chain_depth(packet)
    dependency_score = -(depth * DEPENDENCY_PENALTY)

    affinity_score = 0.0
    if preferred_lane and packet.owner == preferred_lane:
        affinity_score = LANE_AFFINITY_BONUS

    total = age_score + priority_score + dependency_score + affinity_score

    return PriorityScore(
        packet_id=packet.packet_id,
        total=total,
        age_score=age_score,
        priority_score=priority_score,
        dependency_score=dependency_score,
        affinity_score=affinity_score,
    )


def reorder_queue(
    packets: list[PacketLike],
    *,
    now: datetime | None = None,
    preferred_lane: str | None = None,
    status_filter: str | None = "pending",
) -> list[tuple[PacketLike, PriorityScore]]:
    """Score and sort packets by descending priority score.

    Args:
        packets: List of task packets to score and order.
        now: Reference time for age calculation.
        preferred_lane: Lane to apply affinity bonus for.
        status_filter: If set, only include packets with this status.
            Pass ``None`` to include all packets regardless of status.

    Returns:
        List of ``(packet, score)`` tuples sorted by descending total score.
        Ties are broken by ``created_at`` ascending (FIFO among equal scores).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    scored: list[tuple[PacketLike, PriorityScore]] = []
    for pkt in packets:
        if status_filter is not None and pkt.status != status_filter:
            continue
        ps = score_packet(pkt, now=now, preferred_lane=preferred_lane)
        scored.append((pkt, ps))

    # Sort by total descending, then created_at ascending for tie-breaking
    scored.sort(key=lambda x: (-x[1].total, x[0].created_at))
    return scored


def pick_next(
    packets: list[PacketLike],
    *,
    now: datetime | None = None,
    preferred_lane: str | None = None,
    status_filter: str | None = "pending",
) -> tuple[PacketLike, PriorityScore] | None:
    """Return the highest-priority packet ready for dispatch.

    Convenience wrapper around ``reorder_queue`` that returns just the
    top-ranked packet (or ``None`` if no eligible packets exist).
    """
    ordered = reorder_queue(
        packets,
        now=now,
        preferred_lane=preferred_lane,
        status_filter=status_filter,
    )
    return ordered[0] if ordered else None
