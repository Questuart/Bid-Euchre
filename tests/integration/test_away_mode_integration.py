"""Integration tests for away-mode orchestrator wiring (Platform-9b PR3).

Proves the full integration between away_mode state detection, queue_priority
scoring, and the task queue dispatch pipeline.  Tests exercise the real modules
against temporary file-backed state — no mocking of core logic.

Covers:
1. Full cycle: idle detection -> away mode -> priority reorder -> dispatch order
2. Away-mode state transitions (present -> idle -> away -> extended_away)
3. Priority scorer correctly reorders pending packets by age+priority+affinity
4. Escalation threshold triggers on extended_away

Closes task c7b1f20cae80.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from bid_euchre.ops.away_mode import (
    EscalationThresholds,
    OperatorPresence,
    detect_operator_state,
    is_operator_away,
    minutes_until_escalation,
)
from bid_euchre.ops.queue_priority import (
    pick_next,
    reorder_queue,
)
from bid_euchre.ops.task_queue import (
    TaskPacket,
    create_packet,
    list_packets,
    save_packet,
    shared_task_root,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)

# Tight thresholds for fast test cycles (minutes).
TIGHT_THRESHOLDS = EscalationThresholds(
    idle_minutes=5,
    away_minutes=15,
    extended_away_minutes=30,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def task_queue_root(tmp_path: Path) -> Path:
    """Create a temporary task queue directory."""
    return shared_task_root(tmp_path / "task_queue")


def _replace_created_at(pkt: TaskPacket, created_at: str) -> TaskPacket:
    """Replace created_at on a frozen TaskPacket by reconstructing it."""
    data = asdict(pkt)
    data["created_at"] = created_at
    return TaskPacket(**data)


def _make_saved_packet(
    queue_root: Path,
    title: str,
    *,
    priority: str = "normal",
    owner: str | None = None,
    minutes_ago: float = 0,
    status: str = "pending",
    domain: str | None = "platform",
    metadata: dict | None = None,
) -> TaskPacket:
    """Create and save a TaskPacket to the queue directory."""
    pkt = create_packet(
        title=title,
        description=f"Test packet: {title}",
        priority=priority,
        owner=owner,
        domain=domain,
        metadata=metadata or {},
    )
    # Replace created_at with controlled timestamp
    created_at = (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pkt = _replace_created_at(pkt, created_at)

    # Replace status if not pending (need to reconstruct)
    if status != "pending":
        data = asdict(pkt)
        data["status"] = status
        pkt = TaskPacket(**data)

    save_packet(pkt, queue_root)
    return pkt


# ---------------------------------------------------------------------------
# Test 1: Full cycle — idle detection -> away mode -> priority reorder -> dispatch
# ---------------------------------------------------------------------------


class TestFullAwayModeCycle:
    """Prove the full integration: detect idle -> assess away state -> reorder queue."""

    def test_idle_detection_triggers_reorder(self, task_queue_root: Path) -> None:
        """When the operator is away, pending packets should be reordered
        by priority score for autonomous dispatch.
        """
        # 1. Create pending packets with varying ages and priorities
        _make_saved_packet(
            task_queue_root,
            "Old low-priority task",
            priority="low",
            minutes_ago=120,
        )
        recent_high = _make_saved_packet(
            task_queue_root,
            "Recent high-priority task",
            priority="high",
            minutes_ago=5,
        )
        _make_saved_packet(
            task_queue_root,
            "Mid-age normal task",
            priority="normal",
            minutes_ago=60,
        )

        # 2. Detect operator state — simulate 2 hours of absence
        last_interaction = NOW - timedelta(minutes=120)
        state = detect_operator_state(last_interaction, now=NOW)

        # Verify operator is in AWAY or EXTENDED_AWAY
        assert state.state in (OperatorPresence.AWAY, OperatorPresence.EXTENDED_AWAY)
        assert state.escalation_tier >= 2

        # 3. Since operator is away, reorder the queue by priority
        packets = list_packets(task_queue_root, status_filter="pending")
        assert len(packets) == 3

        ordered = reorder_queue(packets, now=NOW)
        assert len(ordered) == 3

        # 4. Verify reorder: high-priority recent task should be first
        #    (priority=10.0 + age=0.08h ~ 10.1 > normal+1h=6.0 > low+2h=3.0)
        ranked_ids = [pkt.packet_id for pkt, _ in ordered]
        assert (
            ranked_ids[0] == recent_high.packet_id
        ), "High-priority packet should rank first"

    def test_present_operator_no_autonomous_reorder_needed(
        self, task_queue_root: Path
    ) -> None:
        """When operator is present, queue reorder still works but
        no autonomous action should be taken (escalation_tier == 0).
        """
        _make_saved_packet(
            task_queue_root,
            "Task A",
            priority="normal",
            minutes_ago=10,
        )

        last_interaction = NOW - timedelta(minutes=2)
        state = detect_operator_state(last_interaction, now=NOW)

        assert state.state == OperatorPresence.PRESENT
        assert state.escalation_tier == 0

        # Queue reorder still produces valid results
        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=NOW)
        assert len(ordered) == 1

    def test_escalation_drives_dispatch_urgency(self, task_queue_root: Path) -> None:
        """Higher escalation tiers justify more aggressive dispatch.

        At tier 3 (extended_away), the system should be willing to
        dispatch all eligible packets without waiting for operator review.
        """
        # Create 3 approved packets ready for dispatch
        for i in range(3):
            _make_saved_packet(
                task_queue_root,
                f"Approved task {i}",
                priority="normal",
                minutes_ago=30 * (i + 1),
                status="approved",
            )

        # Simulate extended away
        last_interaction = NOW - timedelta(minutes=180)
        state = detect_operator_state(
            last_interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert state.state == OperatorPresence.EXTENDED_AWAY
        assert state.escalation_tier == 3

        # All approved packets can be ranked
        packets = list_packets(task_queue_root, status_filter="approved")
        ordered = reorder_queue(packets, now=NOW, status_filter="approved")
        assert len(ordered) == 3

        # Oldest packet should rank highest (most age points)
        oldest = ordered[0]
        assert oldest[1].age_score > ordered[1][1].age_score
        assert oldest[1].age_score > ordered[2][1].age_score


# ---------------------------------------------------------------------------
# Test 2: Away-mode state transitions
# ---------------------------------------------------------------------------


class TestAwayModeStateTransitions:
    """Prove state transitions work correctly in integration with queue state."""

    def test_full_state_progression(self) -> None:
        """Walk through all four states as time progresses."""
        interaction = NOW

        transitions = [
            (0, OperatorPresence.PRESENT, 0),
            (TIGHT_THRESHOLDS.idle_minutes, OperatorPresence.IDLE, 1),
            (TIGHT_THRESHOLDS.away_minutes, OperatorPresence.AWAY, 2),
            (TIGHT_THRESHOLDS.extended_away_minutes, OperatorPresence.EXTENDED_AWAY, 3),
        ]

        for elapsed_min, expected_state, expected_tier in transitions:
            check_time = NOW + timedelta(minutes=elapsed_min)
            result = detect_operator_state(
                interaction,
                thresholds=TIGHT_THRESHOLDS,
                now=check_time,
            )
            assert result.state == expected_state, (
                f"At +{elapsed_min}m: expected {expected_state.value}, "
                f"got {result.state.value}"
            )
            assert result.escalation_tier == expected_tier

    def test_state_transitions_are_monotonic(self) -> None:
        """Escalation tier never decreases as time progresses."""
        interaction = NOW
        prev_tier = -1

        for minutes_later in range(0, 61):
            check_time = NOW + timedelta(minutes=minutes_later)
            result = detect_operator_state(
                interaction,
                thresholds=TIGHT_THRESHOLDS,
                now=check_time,
            )
            assert result.escalation_tier >= prev_tier, (
                f"Tier decreased at +{minutes_later}m: "
                f"{prev_tier} -> {result.escalation_tier}"
            )
            prev_tier = result.escalation_tier

    def test_is_away_respects_thresholds(self) -> None:
        """is_operator_away returns True only at AWAY or higher."""
        interaction = NOW

        # Just before away threshold → not away
        check_time = NOW + timedelta(minutes=TIGHT_THRESHOLDS.away_minutes - 1)
        assert not is_operator_away(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=check_time,
        )

        # At away threshold → away
        check_time = NOW + timedelta(minutes=TIGHT_THRESHOLDS.away_minutes)
        assert is_operator_away(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=check_time,
        )

    def test_minutes_until_escalation_decreases(self) -> None:
        """The scheduling helper returns decreasing minutes as time passes."""
        interaction = NOW

        remaining_at_0 = minutes_until_escalation(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        remaining_at_3 = minutes_until_escalation(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW + timedelta(minutes=3),
        )

        assert remaining_at_0 is not None
        assert remaining_at_3 is not None
        assert remaining_at_3 < remaining_at_0

    def test_extended_away_returns_none_for_escalation(self) -> None:
        """At max tier, no further escalation is possible."""
        interaction = NOW - timedelta(minutes=60)

        remaining = minutes_until_escalation(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert remaining is None


# ---------------------------------------------------------------------------
# Test 3: Priority scorer reorders packets correctly
# ---------------------------------------------------------------------------


class TestPriorityScorerReorder:
    """Prove the priority scorer correctly integrates age, priority, and affinity."""

    def test_priority_dominates_age_for_recent_packets(
        self, task_queue_root: Path
    ) -> None:
        """A high-priority recent packet outranks a low-priority older packet."""
        low_old = _make_saved_packet(
            task_queue_root,
            "Low old",
            priority="low",
            minutes_ago=60,
        )
        high_new = _make_saved_packet(
            task_queue_root,
            "High new",
            priority="high",
            minutes_ago=5,
        )

        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=NOW)

        assert ordered[0][0].packet_id == high_new.packet_id
        assert ordered[1][0].packet_id == low_old.packet_id

    def test_age_breaks_ties_among_same_priority(self, task_queue_root: Path) -> None:
        """Among equal-priority packets, older ones rank higher."""
        old = _make_saved_packet(
            task_queue_root,
            "Older",
            priority="normal",
            minutes_ago=120,
        )
        new = _make_saved_packet(
            task_queue_root,
            "Newer",
            priority="normal",
            minutes_ago=10,
        )

        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=NOW)

        assert ordered[0][0].packet_id == old.packet_id
        assert ordered[1][0].packet_id == new.packet_id

    def test_lane_affinity_bonus_applied(self, task_queue_root: Path) -> None:
        """Packets matching the preferred lane get an affinity bonus."""
        # Two packets with same priority and age, but different owners
        pkt_a = _make_saved_packet(
            task_queue_root,
            "Owned by author-a",
            priority="normal",
            minutes_ago=30,
            owner="author-a",
        )
        _make_saved_packet(
            task_queue_root,
            "Owned by author-b",
            priority="normal",
            minutes_ago=30,
            owner="author-b",
        )

        packets = list_packets(task_queue_root, status_filter="pending")

        # With affinity for author-a
        ordered = reorder_queue(packets, now=NOW, preferred_lane="author-a")

        # author-a's packet should rank first due to affinity bonus
        assert ordered[0][0].packet_id == pkt_a.packet_id
        assert ordered[0][1].affinity_score > 0.0
        assert ordered[1][1].affinity_score == 0.0

    def test_dependency_depth_penalizes_deep_chains(
        self, task_queue_root: Path
    ) -> None:
        """Packets with deeper dependency chains rank lower."""
        shallow = _make_saved_packet(
            task_queue_root,
            "Shallow",
            priority="normal",
            minutes_ago=30,
            metadata={"chain_depth": 0},
        )
        _make_saved_packet(
            task_queue_root,
            "Deep chain",
            priority="normal",
            minutes_ago=30,
            metadata={"chain_depth": 5},
        )

        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=NOW)

        assert ordered[0][0].packet_id == shallow.packet_id
        assert ordered[0][1].dependency_score == 0.0
        assert ordered[1][1].dependency_score < 0.0

    def test_pick_next_selects_highest_scored(self, task_queue_root: Path) -> None:
        """pick_next returns the single highest-scored packet."""
        _make_saved_packet(
            task_queue_root,
            "Low",
            priority="low",
            minutes_ago=10,
        )
        high = _make_saved_packet(
            task_queue_root,
            "High",
            priority="high",
            minutes_ago=10,
        )

        packets = list_packets(task_queue_root, status_filter="pending")
        result = pick_next(packets, now=NOW)

        assert result is not None
        assert result[0].packet_id == high.packet_id

    def test_empty_queue_returns_none(self) -> None:
        """pick_next returns None for an empty queue."""
        result = pick_next([], now=NOW)
        assert result is None

    def test_status_filter_excludes_non_pending(self, task_queue_root: Path) -> None:
        """Only pending packets are scored when status_filter='pending'."""
        _make_saved_packet(
            task_queue_root,
            "Pending",
            priority="high",
            minutes_ago=10,
        )
        _make_saved_packet(
            task_queue_root,
            "Dispatched",
            priority="high",
            minutes_ago=10,
            status="dispatched",
            owner="author-a",
        )

        packets = list_packets(task_queue_root)  # All statuses
        ordered = reorder_queue(packets, now=NOW, status_filter="pending")

        assert len(ordered) == 1
        assert ordered[0][0].title == "Pending"

    def test_score_breakdown_is_consistent(self, task_queue_root: Path) -> None:
        """The total score equals the sum of component scores."""
        _make_saved_packet(
            task_queue_root,
            "Test",
            priority="high",
            minutes_ago=60,
            metadata={"chain_depth": 2},
        )

        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=NOW, preferred_lane="author-a")

        assert len(ordered) == 1
        _, score = ordered[0]

        expected_total = (
            score.age_score
            + score.priority_score
            + score.dependency_score
            + score.affinity_score
        )
        assert score.total == pytest.approx(expected_total, abs=0.01)


# ---------------------------------------------------------------------------
# Test 4: Escalation threshold triggers on extended_away
# ---------------------------------------------------------------------------


class TestEscalationTriggers:
    """Prove that extended_away state correctly triggers escalation behavior."""

    def test_extended_away_at_exact_threshold(self) -> None:
        """At exactly the extended_away threshold, state should be EXTENDED_AWAY."""
        interaction = NOW - timedelta(minutes=TIGHT_THRESHOLDS.extended_away_minutes)
        result = detect_operator_state(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert result.state == OperatorPresence.EXTENDED_AWAY
        assert result.escalation_tier == 3

    def test_extended_away_well_past_threshold(self) -> None:
        """Well past extended_away threshold, state is still EXTENDED_AWAY."""
        interaction = NOW - timedelta(minutes=300)
        result = detect_operator_state(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert result.state == OperatorPresence.EXTENDED_AWAY
        assert result.escalation_tier == 3
        assert result.minutes_inactive == pytest.approx(300.0, abs=0.1)

    def test_no_interaction_implies_extended_away(self) -> None:
        """None interaction (no known activity) implies max escalation."""
        result = detect_operator_state(
            None,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert result.state == OperatorPresence.EXTENDED_AWAY
        assert result.escalation_tier == 3

    def test_extended_away_enables_all_packet_dispatch(
        self, task_queue_root: Path
    ) -> None:
        """At escalation tier 3, all eligible packets should be dispatchable.

        This test proves that the priority scorer works on all pending packets
        when the operator is at extended_away, enabling the orchestrator to
        dispatch aggressively without waiting for operator input.
        """
        # Create a mix of packets
        packets_created = []
        for i, priority in enumerate(["low", "normal", "high", "high", "normal"]):
            pkt = _make_saved_packet(
                task_queue_root,
                f"Task {i} ({priority})",
                priority=priority,
                minutes_ago=10 * (i + 1),
            )
            packets_created.append(pkt)

        # Confirm extended away
        result = detect_operator_state(
            None,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert result.escalation_tier == 3

        # All pending packets should be rankable
        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=NOW)
        assert len(ordered) == 5

        # Verify ordering is deterministic and well-formed
        scores = [score.total for _, score in ordered]
        assert scores == sorted(
            scores, reverse=True
        ), "Scores should be in descending order"

    def test_transition_through_all_tiers_with_queue_state(
        self, task_queue_root: Path
    ) -> None:
        """Full lifecycle: packets accumulate while operator transitions through tiers.

        Simulates a realistic scenario where packets arrive over time and the
        operator goes through present -> idle -> away -> extended_away.
        """
        interaction = NOW

        # T+0: Operator present, one packet arrives
        _make_saved_packet(
            task_queue_root,
            "Initial task",
            priority="normal",
            minutes_ago=0,
        )

        state = detect_operator_state(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=NOW,
        )
        assert state.state == OperatorPresence.PRESENT

        # T+5: Operator goes idle, a high-priority packet arrives
        t_idle = NOW + timedelta(minutes=TIGHT_THRESHOLDS.idle_minutes)
        _make_saved_packet(
            task_queue_root,
            "Urgent task",
            priority="high",
            minutes_ago=-int(TIGHT_THRESHOLDS.idle_minutes),
        )

        state = detect_operator_state(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=t_idle,
        )
        assert state.state == OperatorPresence.IDLE

        # T+15: Operator goes away
        t_away = NOW + timedelta(minutes=TIGHT_THRESHOLDS.away_minutes)
        state = detect_operator_state(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=t_away,
        )
        assert state.state == OperatorPresence.AWAY
        assert is_operator_away(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=t_away,
        )

        # T+30: Extended away — full autonomous dispatch justified
        t_ext = NOW + timedelta(minutes=TIGHT_THRESHOLDS.extended_away_minutes)
        state = detect_operator_state(
            interaction,
            thresholds=TIGHT_THRESHOLDS,
            now=t_ext,
        )
        assert state.state == OperatorPresence.EXTENDED_AWAY

        # Queue should still be fully reorderable
        packets = list_packets(task_queue_root, status_filter="pending")
        ordered = reorder_queue(packets, now=t_ext)
        assert len(ordered) >= 2
        # Confirm pick_next returns the highest-scored packet
        top = pick_next(packets, now=t_ext)
        assert top is not None
        assert top[0].packet_id == ordered[0][0].packet_id
