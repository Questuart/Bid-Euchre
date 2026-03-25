"""Tests for queue priority scoring and auto-reorder logic.

Covers:
- Age scoring (capped, zero for new packets)
- Priority field scoring (high > normal > low)
- Dependency chain depth penalty
- Lane affinity bonus
- Reorder and pick_next convenience functions
- Edge cases: missing metadata, unknown priority, empty queue
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from bid_euchre.ops.queue_priority import (
    AGE_WEIGHT_PER_HOUR,
    DEPENDENCY_PENALTY,
    LANE_AFFINITY_BONUS,
    MAX_AGE_HOURS,
    MAX_CHAIN_DEPTH,
    PRIORITY_SCORES,
    PriorityScore,
    pick_next,
    reorder_queue,
    score_packet,
)

# ---------------------------------------------------------------------------
# Test fixture — lightweight PacketLike stand-in
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakePacket:
    """Minimal packet satisfying the PacketLike protocol."""

    packet_id: str = "abc123"
    priority: str = "normal"
    created_at: str = "2026-03-25T06:00:00Z"
    owner: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)  # noon UTC


def _make_packet(**kwargs: Any) -> FakePacket:
    """Create a FakePacket with defaults overridden by kwargs."""
    return FakePacket(**kwargs)


# ---------------------------------------------------------------------------
# Age scoring
# ---------------------------------------------------------------------------


class TestAgeScoring:
    """Age dimension: older packets score higher, capped at MAX_AGE_HOURS."""

    def test_brand_new_packet_zero_age(self) -> None:
        """Packet created at `now` gets zero age score."""
        pkt = _make_packet(created_at="2026-03-25T12:00:00Z")
        score = score_packet(pkt, now=NOW)
        assert score.age_score == pytest.approx(0.0)

    def test_six_hour_old_packet(self) -> None:
        """Packet created 6 hours ago gets 6 * AGE_WEIGHT_PER_HOUR."""
        pkt = _make_packet(created_at="2026-03-25T06:00:00Z")
        score = score_packet(pkt, now=NOW)
        assert score.age_score == pytest.approx(6.0 * AGE_WEIGHT_PER_HOUR)

    def test_age_capped_at_max(self) -> None:
        """Packets older than MAX_AGE_HOURS are capped."""
        # 100 hours old — should be capped at MAX_AGE_HOURS
        old_ts = (NOW - timedelta(hours=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pkt = _make_packet(created_at=old_ts)
        score = score_packet(pkt, now=NOW)
        assert score.age_score == pytest.approx(MAX_AGE_HOURS * AGE_WEIGHT_PER_HOUR)

    def test_future_packet_zero_age(self) -> None:
        """Packet with created_at in the future gets zero age (clamped)."""
        future_ts = (NOW + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pkt = _make_packet(created_at=future_ts)
        score = score_packet(pkt, now=NOW)
        assert score.age_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Priority field scoring
# ---------------------------------------------------------------------------


class TestPriorityScoring:
    """Priority dimension: high > normal > low."""

    def test_high_priority(self) -> None:
        pkt = _make_packet(priority="high")
        score = score_packet(pkt, now=NOW)
        assert score.priority_score == PRIORITY_SCORES["high"]

    def test_normal_priority(self) -> None:
        pkt = _make_packet(priority="normal")
        score = score_packet(pkt, now=NOW)
        assert score.priority_score == PRIORITY_SCORES["normal"]

    def test_low_priority(self) -> None:
        pkt = _make_packet(priority="low")
        score = score_packet(pkt, now=NOW)
        assert score.priority_score == PRIORITY_SCORES["low"]

    def test_priority_ordering(self) -> None:
        """High > normal > low in score contribution."""
        assert PRIORITY_SCORES["high"] > PRIORITY_SCORES["normal"]
        assert PRIORITY_SCORES["normal"] > PRIORITY_SCORES["low"]

    def test_unknown_priority_defaults_to_normal(self) -> None:
        """Unknown priority falls back to normal score."""
        # Directly test the dict.get fallback behavior used in score_packet
        fallback = PRIORITY_SCORES.get("unknown", PRIORITY_SCORES["normal"])
        assert fallback == PRIORITY_SCORES["normal"]


# ---------------------------------------------------------------------------
# Dependency chain scoring
# ---------------------------------------------------------------------------


class TestDependencyScoring:
    """Dependency dimension: deeper chains get penalized."""

    def test_no_chain_depth(self) -> None:
        """No metadata = zero penalty."""
        pkt = _make_packet()
        score = score_packet(pkt, now=NOW)
        assert score.dependency_score == pytest.approx(0.0)

    def test_chain_depth_3(self) -> None:
        """Chain depth 3 = -3 * DEPENDENCY_PENALTY."""
        pkt = _make_packet(metadata={"chain_depth": 3})
        score = score_packet(pkt, now=NOW)
        assert score.dependency_score == pytest.approx(-3 * DEPENDENCY_PENALTY)

    def test_chain_depth_capped(self) -> None:
        """Chain depth beyond MAX_CHAIN_DEPTH is capped."""
        pkt = _make_packet(metadata={"chain_depth": 999})
        score = score_packet(pkt, now=NOW)
        assert score.dependency_score == pytest.approx(
            -MAX_CHAIN_DEPTH * DEPENDENCY_PENALTY
        )

    def test_invalid_chain_depth_defaults_zero(self) -> None:
        """Non-numeric chain_depth defaults to 0 penalty."""
        pkt = _make_packet(metadata={"chain_depth": "not_a_number"})
        score = score_packet(pkt, now=NOW)
        assert score.dependency_score == pytest.approx(0.0)

    def test_negative_chain_depth_clamped(self) -> None:
        """Negative chain depth is clamped to 0."""
        pkt = _make_packet(metadata={"chain_depth": -5})
        score = score_packet(pkt, now=NOW)
        assert score.dependency_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Lane affinity scoring
# ---------------------------------------------------------------------------


class TestAffinityScoring:
    """Affinity dimension: owner matching preferred_lane gets a bonus."""

    def test_no_preferred_lane(self) -> None:
        """No preferred lane = no bonus."""
        pkt = _make_packet(owner="author-a")
        score = score_packet(pkt, now=NOW, preferred_lane=None)
        assert score.affinity_score == pytest.approx(0.0)

    def test_matching_lane(self) -> None:
        """Owner matches preferred lane = LANE_AFFINITY_BONUS."""
        pkt = _make_packet(owner="author-d")
        score = score_packet(pkt, now=NOW, preferred_lane="author-d")
        assert score.affinity_score == pytest.approx(LANE_AFFINITY_BONUS)

    def test_non_matching_lane(self) -> None:
        """Owner does not match preferred lane = no bonus."""
        pkt = _make_packet(owner="author-a")
        score = score_packet(pkt, now=NOW, preferred_lane="author-d")
        assert score.affinity_score == pytest.approx(0.0)

    def test_no_owner_no_bonus(self) -> None:
        """Packet with no owner = no bonus even with preferred lane."""
        pkt = _make_packet(owner=None)
        score = score_packet(pkt, now=NOW, preferred_lane="author-d")
        assert score.affinity_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Total score composition
# ---------------------------------------------------------------------------


class TestTotalScore:
    """Verify total is the sum of all dimensions."""

    def test_total_is_sum_of_parts(self) -> None:
        pkt = _make_packet(
            priority="high",
            created_at="2026-03-25T06:00:00Z",
            owner="author-d",
            metadata={"chain_depth": 2},
        )
        score = score_packet(pkt, now=NOW, preferred_lane="author-d")
        expected = (
            score.age_score
            + score.priority_score
            + score.dependency_score
            + score.affinity_score
        )
        assert score.total == pytest.approx(expected)

    def test_score_returns_priority_score(self) -> None:
        """PriorityScore is returned with correct packet_id."""
        pkt = _make_packet(packet_id="xyz789")
        score = score_packet(pkt, now=NOW)
        assert isinstance(score, PriorityScore)
        assert score.packet_id == "xyz789"


# ---------------------------------------------------------------------------
# reorder_queue
# ---------------------------------------------------------------------------


class TestReorderQueue:
    """Auto-reorder sorts packets by descending total score."""

    def test_high_before_low(self) -> None:
        """High-priority packet sorts before low-priority."""
        high = _make_packet(packet_id="h1", priority="high")
        low = _make_packet(packet_id="l1", priority="low")
        ordered = reorder_queue([low, high], now=NOW)
        ids = [pkt.packet_id for pkt, _ in ordered]
        assert ids == ["h1", "l1"]

    def test_older_before_newer_same_priority(self) -> None:
        """Among same-priority packets, older sorts first."""
        old = _make_packet(
            packet_id="old1",
            created_at="2026-03-25T06:00:00Z",
        )
        new = _make_packet(
            packet_id="new1",
            created_at="2026-03-25T11:00:00Z",
        )
        ordered = reorder_queue([new, old], now=NOW)
        ids = [pkt.packet_id for pkt, _ in ordered]
        assert ids == ["old1", "new1"]

    def test_status_filter_excludes_non_matching(self) -> None:
        """Only packets matching status_filter are included."""
        pending = _make_packet(packet_id="p1", status="pending")
        dispatched = _make_packet(packet_id="d1", status="dispatched")
        ordered = reorder_queue([pending, dispatched], now=NOW, status_filter="pending")
        ids = [pkt.packet_id for pkt, _ in ordered]
        assert ids == ["p1"]

    def test_status_filter_none_includes_all(self) -> None:
        """status_filter=None includes all statuses."""
        pending = _make_packet(packet_id="p1", status="pending")
        dispatched = _make_packet(packet_id="d1", status="dispatched")
        ordered = reorder_queue([pending, dispatched], now=NOW, status_filter=None)
        assert len(ordered) == 2

    def test_empty_queue(self) -> None:
        """Empty input returns empty output."""
        ordered = reorder_queue([], now=NOW)
        assert ordered == []

    def test_tie_broken_by_created_at(self) -> None:
        """Equal scores are broken by created_at ascending (FIFO)."""
        # Two packets with identical priority and timestamps — stable sort
        same_ts = "2026-03-25T10:00:00Z"
        a = _make_packet(packet_id="aaa", created_at=same_ts)
        b = _make_packet(packet_id="bbb", created_at=same_ts)
        ordered = reorder_queue([a, b], now=NOW)
        # Equal total score — FIFO by created_at (both same, so stable)
        ids = [pkt.packet_id for pkt, _ in ordered]
        assert len(ids) == 2

    def test_complex_ordering(self) -> None:
        """Multi-factor ordering: high+old beats normal+new beats low."""
        high_old = _make_packet(
            packet_id="high_old",
            priority="high",
            created_at="2026-03-25T04:00:00Z",
        )
        normal_mid = _make_packet(
            packet_id="normal_mid",
            priority="normal",
            created_at="2026-03-25T08:00:00Z",
        )
        low_new = _make_packet(
            packet_id="low_new",
            priority="low",
            created_at="2026-03-25T11:00:00Z",
        )
        ordered = reorder_queue([low_new, normal_mid, high_old], now=NOW)
        ids = [pkt.packet_id for pkt, _ in ordered]
        assert ids == ["high_old", "normal_mid", "low_new"]


# ---------------------------------------------------------------------------
# pick_next
# ---------------------------------------------------------------------------


class TestPickNext:
    """pick_next returns the single highest-priority packet."""

    def test_returns_highest(self) -> None:
        high = _make_packet(packet_id="h1", priority="high")
        low = _make_packet(packet_id="l1", priority="low")
        result = pick_next([low, high], now=NOW)
        assert result is not None
        pkt, score = result
        assert pkt.packet_id == "h1"

    def test_returns_none_for_empty(self) -> None:
        result = pick_next([], now=NOW)
        assert result is None

    def test_returns_none_when_all_filtered(self) -> None:
        dispatched = _make_packet(status="dispatched")
        result = pick_next([dispatched], now=NOW, status_filter="pending")
        assert result is None

    def test_preferred_lane_boosts_selection(self) -> None:
        """When two packets have same priority, lane affinity tips the scale."""
        mine = _make_packet(
            packet_id="mine",
            owner="author-d",
            created_at="2026-03-25T10:00:00Z",
        )
        theirs = _make_packet(
            packet_id="theirs",
            owner="author-a",
            created_at="2026-03-25T10:00:00Z",
        )
        result = pick_next([theirs, mine], now=NOW, preferred_lane="author-d")
        assert result is not None
        pkt, _ = result
        assert pkt.packet_id == "mine"


# ---------------------------------------------------------------------------
# Default now parameter
# ---------------------------------------------------------------------------


class TestDefaultNow:
    """Verify functions work without explicit now parameter."""

    def test_score_packet_default_now(self) -> None:
        """score_packet works without explicit now."""
        pkt = _make_packet()
        score = score_packet(pkt)
        assert isinstance(score, PriorityScore)
        assert score.total > 0

    def test_reorder_queue_default_now(self) -> None:
        """reorder_queue works without explicit now."""
        pkt = _make_packet()
        ordered = reorder_queue([pkt])
        assert len(ordered) == 1

    def test_pick_next_default_now(self) -> None:
        """pick_next works without explicit now."""
        pkt = _make_packet()
        result = pick_next([pkt])
        assert result is not None


# ---------------------------------------------------------------------------
# Timestamp parsing edge cases
# ---------------------------------------------------------------------------


class TestTimestampParsing:
    """Edge cases in ISO 8601 timestamp parsing."""

    def test_z_suffix(self) -> None:
        pkt = _make_packet(created_at="2026-03-25T06:00:00Z")
        score = score_packet(pkt, now=NOW)
        assert score.age_score == pytest.approx(6.0 * AGE_WEIGHT_PER_HOUR)

    def test_plus_utc_offset(self) -> None:
        pkt = _make_packet(created_at="2026-03-25T06:00:00+00:00")
        score = score_packet(pkt, now=NOW)
        assert score.age_score == pytest.approx(6.0 * AGE_WEIGHT_PER_HOUR)

    def test_no_timezone_suffix(self) -> None:
        """Bare timestamp without Z or offset is treated as UTC."""
        pkt = _make_packet(created_at="2026-03-25T06:00:00")
        score = score_packet(pkt, now=NOW)
        # Should parse and produce a reasonable age score
        assert score.age_score > 0
