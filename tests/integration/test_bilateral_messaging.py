"""Integration tests for bilateral lane-to-lane messaging.

Proves end-to-end bilateral messaging works across all lane pool types:
- Platform pool (author-a/b/c/d)
- Browser-game pool (brws-author-a/b/c/d)
- Flex pool (flex-a/b/c)

Each test exercises the full send → deliver → read → ack cycle using
the real message_bus module against a temporary bus root.

Expanded coverage includes:
- Priority-aware delivery (read_inbox_prioritized)
- Messages surviving compaction
- Full lifecycle transitions (delivered → acked → resolved)
- Error cases (invalid types, invalid transitions, duplicate IDs)
- Escalation, TTL expiry, and dead-letter mechanics
- Bulk operations and content dedup
- Inbox statistics

Closes #1570.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.message_bus import (
    VALID_MESSAGE_PRIORITIES,
    VALID_MESSAGE_STATUSES,
    VALID_MESSAGE_TRANSITIONS,
    VALID_MESSAGE_TYPES,
    BusMessage,
    ack_message,
    bulk_ack_messages,
    check_ack_status,
    check_dead_letters,
    check_expired,
    compact_inbox,
    create_message,
    escalate_unacked,
    inbox_stats,
    mark_delivered,
    query_unresolved,
    read_inbox,
    read_inbox_prioritized,
    resolve_message,
    send_message,
    shared_bus_root,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus_root(tmp_path: Path) -> Path:
    """Create a temporary bus root with inbox directory."""
    root = tmp_path / "message_bus"
    return shared_bus_root(root)


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Create a temporary events directory for event emission."""
    d = tmp_path / "events"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Lane representatives for each pool type
# ---------------------------------------------------------------------------

PLATFORM_LANES = ["author-a", "author-b", "author-c", "author-d"]
BROWSER_GAME_LANES = [
    "brws-author-a",
    "brws-author-b",
    "brws-author-c",
    "brws-author-d",
]
FLEX_LANES = ["flex-a", "flex-b", "flex-c"]

# Pick one representative from each pool for parameterized tests
POOL_REPRESENTATIVES = [
    pytest.param("author-a", id="platform"),
    pytest.param("brws-author-a", id="browser-game"),
    pytest.param("flex-a", id="flex"),
]

ALL_POOL_REPRESENTATIVES = [
    ("author-a", "platform"),
    ("brws-author-a", "browser-game"),
    ("flex-a", "flex"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send_and_verify(
    *,
    from_lane: str,
    to_lane: str,
    msg_type: str,
    summary: str,
    bus_root: Path,
    events_dir: Path,
) -> str:
    """Send a message and verify it appears in the recipient's inbox.

    Returns the message_id.
    """
    msg = create_message(
        from_lane=from_lane,
        to_lane=to_lane,
        message_type=msg_type,
        summary=summary,
    )
    mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

    # Verify in recipient inbox
    inbox = read_inbox(
        to_lane, bus_root=bus_root, auto_expire=False, auto_compact=False
    )
    ids = [m["message_id"] for m in inbox]
    assert mid in ids, f"Message {mid} not found in {to_lane}'s inbox. Found: {ids}"

    # Verify message fields
    received = next(m for m in inbox if m["message_id"] == mid)
    assert received["from_lane"] == from_lane
    assert received["to_lane"] == to_lane
    assert received["message_type"] == msg_type
    assert received["summary"] == summary
    assert received["status"] == "pending"

    return mid


# ---------------------------------------------------------------------------
# Test: Orchestrator → Author lane (all 3 pools)
# ---------------------------------------------------------------------------


class TestOrchestratorToAuthor:
    """Orchestrator sends an assignment to each pool type's lane."""

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_orchestrator_sends_assignment(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Orchestrator → author lane: assignment appears in inbox."""
        mid = _send_and_verify(
            from_lane="orchestrator",
            to_lane=lane,
            msg_type="assignment",
            summary=f"Task dispatched to {lane}",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert mid  # non-empty

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_orchestrator_assignment_starts_pending(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Messages start in pending status before acknowledgement."""
        mid = _send_and_verify(
            from_lane="orchestrator",
            to_lane=lane,
            msg_type="assignment",
            summary=f"Pending check for {lane}",
            bus_root=bus_root,
            events_dir=events_dir,
        )

        inbox = read_inbox(
            lane,
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        found = [m for m in inbox if m["message_id"] == mid]
        assert len(found) == 1
        assert found[0]["status"] == "pending"
        assert found[0]["acked_at"] is None


# ---------------------------------------------------------------------------
# Test: Author lane → Orchestrator (all 3 pools)
# ---------------------------------------------------------------------------


class TestAuthorToOrchestrator:
    """Author lanes send ack/progress/completion back to orchestrator."""

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_author_sends_ack(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Author lane → orchestrator: ack message appears in inbox."""
        mid = _send_and_verify(
            from_lane=lane,
            to_lane="orchestrator",
            msg_type="ack",
            summary=f"Task received by {lane}",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert mid

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_author_sends_progress(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Author lane → orchestrator: progress update delivered."""
        mid = _send_and_verify(
            from_lane=lane,
            to_lane="orchestrator",
            msg_type="progress",
            summary=f"Implementation 50% complete on {lane}",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert mid

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_author_sends_completion(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Author lane → orchestrator: completion message delivered."""
        mid = _send_and_verify(
            from_lane=lane,
            to_lane="orchestrator",
            msg_type="completion",
            summary=f"PR merged by {lane}",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert mid

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_author_sends_blocker(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Author lane → orchestrator: blocker escalation delivered."""
        mid = _send_and_verify(
            from_lane=lane,
            to_lane="orchestrator",
            msg_type="blocker",
            summary=f"Scope conflict on {lane}",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert mid


# ---------------------------------------------------------------------------
# Test: Ops → Orchestrator (supervisor alerts)
# ---------------------------------------------------------------------------


class TestOpsToOrchestrator:
    """Ops lane sends supervisor_alert to orchestrator."""

    def test_ops_sends_supervisor_alert(self, bus_root: Path, events_dir: Path) -> None:
        """Ops → orchestrator: supervisor_alert delivered and readable."""
        mid = _send_and_verify(
            from_lane="ops",
            to_lane="orchestrator",
            msg_type="supervisor_alert",
            summary="Lane author-a stalled for 15 min",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert mid

    def test_ops_alert_high_priority(self, bus_root: Path, events_dir: Path) -> None:
        """Ops supervisor_alert can use high priority."""
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="CI red on 3 lanes",
            priority="high",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        found = next(m for m in inbox if m["message_id"] == mid)
        assert found["priority"] == "high"
        assert found["message_type"] == "supervisor_alert"


# ---------------------------------------------------------------------------
# Test: Ack / unack state tracking
# ---------------------------------------------------------------------------


class TestAckStateTracking:
    """Verify ack/unack state transitions work correctly."""

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_ack_transitions_status(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Acking a message transitions it from pending → acked."""
        # Send assignment to lane
        msg = create_message(
            from_lane="orchestrator",
            to_lane=lane,
            message_type="assignment",
            summary=f"Ack test for {lane}",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Verify starts as pending
        inbox_before = read_inbox(
            lane,
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        before = next(m for m in inbox_before if m["message_id"] == mid)
        assert before["status"] == "pending"
        assert before["acked_at"] is None

        # Ack it
        result = ack_message(mid, lane, bus_root=bus_root, events_dir=events_dir)
        assert result is not None
        assert result["status"] == "acked"
        assert result["acked_at"] is not None

        # Verify inbox now shows acked
        inbox_after = read_inbox(
            lane,
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        after = next(m for m in inbox_after if m["message_id"] == mid)
        assert after["status"] == "acked"
        assert after["acked_at"] is not None

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_unacked_messages_filterable(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Can filter inbox to show only unacked (pending/delivered) messages."""
        # Send two messages
        msg1 = create_message(
            from_lane="orchestrator",
            to_lane=lane,
            message_type="assignment",
            summary=f"First task for {lane}",
        )
        mid1 = send_message(msg1, bus_root=bus_root, events_dir=events_dir)

        msg2 = create_message(
            from_lane="orchestrator",
            to_lane=lane,
            message_type="assignment",
            summary=f"Second task for {lane}",
        )
        mid2 = send_message(msg2, bus_root=bus_root, events_dir=events_dir)

        # Ack only the first
        ack_message(mid1, lane, bus_root=bus_root, events_dir=events_dir)

        # Filter for pending only
        pending = read_inbox(
            lane,
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        pending_ids = [m["message_id"] for m in pending]
        assert mid2 in pending_ids
        assert mid1 not in pending_ids

        # Filter for acked only
        acked = read_inbox(
            lane,
            bus_root=bus_root,
            status="acked",
            auto_expire=False,
            auto_compact=False,
        )
        acked_ids = [m["message_id"] for m in acked]
        assert mid1 in acked_ids
        assert mid2 not in acked_ids

    def test_ack_nonexistent_returns_none(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Acking a nonexistent message_id returns None."""
        result = ack_message(
            "nonexistent_id_12345",
            "orchestrator",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Test: Full bilateral round-trip (all 3 pools)
# ---------------------------------------------------------------------------


class TestBilateralRoundTrip:
    """Full round-trip: orchestrator sends, lane receives and replies."""

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_full_bilateral_cycle(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Complete bilateral cycle: assign → ack → progress → completion."""
        # Step 1: Orchestrator assigns task to lane
        assign_msg = create_message(
            from_lane="orchestrator",
            to_lane=lane,
            message_type="assignment",
            summary=f"Build feature X on {lane}",
        )
        assign_id = send_message(
            assign_msg,
            bus_root=bus_root,
            events_dir=events_dir,
        )

        # Step 2: Lane receives and acks
        lane_inbox = read_inbox(
            lane,
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == assign_id for m in lane_inbox)
        ack_message(assign_id, lane, bus_root=bus_root, events_dir=events_dir)

        # Step 3: Lane sends ack back to orchestrator
        ack_msg = create_message(
            from_lane=lane,
            to_lane="orchestrator",
            message_type="ack",
            summary=f"Task received on {lane}",
            task_id=assign_id,
        )
        ack_id = send_message(
            ack_msg,
            bus_root=bus_root,
            events_dir=events_dir,
        )

        # Verify orchestrator sees the ack
        orch_inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == ack_id for m in orch_inbox)

        # Step 4: Lane sends progress
        progress_msg = create_message(
            from_lane=lane,
            to_lane="orchestrator",
            message_type="progress",
            summary=f"Implementation complete on {lane}",
            task_id=assign_id,
        )
        progress_id = send_message(
            progress_msg,
            bus_root=bus_root,
            events_dir=events_dir,
        )

        # Verify orchestrator sees progress
        orch_inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == progress_id for m in orch_inbox)

        # Step 5: Lane sends completion
        complete_msg = create_message(
            from_lane=lane,
            to_lane="orchestrator",
            message_type="completion",
            summary=f"PR merged from {lane}",
            task_id=assign_id,
        )
        complete_id = send_message(
            complete_msg,
            bus_root=bus_root,
            events_dir=events_dir,
        )

        # Final verification: orchestrator has all 3 messages from lane
        orch_inbox_final = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        orch_ids = [m["message_id"] for m in orch_inbox_final]
        assert ack_id in orch_ids
        assert progress_id in orch_ids
        assert complete_id in orch_ids

        # Verify lane's assignment is acked
        lane_inbox_final = read_inbox(
            lane,
            bus_root=bus_root,
            status="acked",
            auto_expire=False,
            auto_compact=False,
        )
        acked_ids = [m["message_id"] for m in lane_inbox_final]
        assert assign_id in acked_ids


# ---------------------------------------------------------------------------
# Test: Cross-pool messaging isolation
# ---------------------------------------------------------------------------


class TestCrossPoolIsolation:
    """Messages to one lane do not appear in another lane's inbox."""

    def test_messages_isolated_across_pools(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """A message to author-a is not visible in brws-author-a or flex-a."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Platform-only task",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Verify present in target inbox
        platform_inbox = read_inbox(
            "author-a",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == mid for m in platform_inbox)

        # Verify absent from other pools
        browser_inbox = read_inbox(
            "brws-author-a",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert not any(m["message_id"] == mid for m in browser_inbox)

        flex_inbox = read_inbox(
            "flex-a",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert not any(m["message_id"] == mid for m in flex_inbox)

    def test_each_pool_has_independent_inbox(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Each pool representative gets its own independent messages."""
        mids: dict[str, str] = {}

        for lane, pool_name in ALL_POOL_REPRESENTATIVES:
            msg = create_message(
                from_lane="orchestrator",
                to_lane=lane,
                message_type="assignment",
                summary=f"Task for {pool_name} pool",
            )
            mids[lane] = send_message(
                msg,
                bus_root=bus_root,
                events_dir=events_dir,
            )

        # Each lane sees only its own message
        for lane, _ in ALL_POOL_REPRESENTATIVES:
            inbox = read_inbox(
                lane,
                bus_root=bus_root,
                auto_expire=False,
                auto_compact=False,
            )
            inbox_ids = [m["message_id"] for m in inbox]
            # Own message present
            assert mids[lane] in inbox_ids
            # Other pool messages absent
            for other_lane, _ in ALL_POOL_REPRESENTATIVES:
                if other_lane != lane:
                    assert mids[other_lane] not in inbox_ids


# ---------------------------------------------------------------------------
# Test: Multi-message type filtering
# ---------------------------------------------------------------------------


class TestMessageTypeFiltering:
    """Verify message_type filtering works for bilateral patterns."""

    def test_filter_by_message_type(self, bus_root: Path, events_dir: Path) -> None:
        """Can filter orchestrator inbox by message type."""
        # Send different message types from different lanes
        for lane, _ in ALL_POOL_REPRESENTATIVES:
            for msg_type in ["ack", "progress", "completion"]:
                msg = create_message(
                    from_lane=lane,
                    to_lane="orchestrator",
                    message_type=msg_type,
                    summary=f"{msg_type} from {lane}",
                )
                send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Filter for acks only
        acks = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            message_type="ack",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(acks) == 3  # one from each pool
        assert all(m["message_type"] == "ack" for m in acks)

        # Filter for completions only
        completions = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            message_type="completion",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(completions) == 3
        assert all(m["message_type"] == "completion" for m in completions)

    def test_filter_supervisor_alerts(self, bus_root: Path, events_dir: Path) -> None:
        """Supervisor alerts are filterable separately from lane messages."""
        # Lane sends ack
        lane_msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Task received",
        )
        send_message(lane_msg, bus_root=bus_root, events_dir=events_dir)

        # Ops sends alert
        ops_msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="Lane stalled",
        )
        send_message(ops_msg, bus_root=bus_root, events_dir=events_dir)

        # Filter for alerts only
        alerts = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            message_type="supervisor_alert",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(alerts) == 1
        assert alerts[0]["from_lane"] == "ops"

        # Filter for acks excludes alerts
        acks = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            message_type="ack",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(acks) == 1
        assert acks[0]["from_lane"] == "author-a"


# ---------------------------------------------------------------------------
# Test: Priority-aware delivery (read_inbox_prioritized)
# ---------------------------------------------------------------------------


class TestPriorityAwareDelivery:
    """Verify priority-grouped inbox reading (P0/P1/P2 tiers)."""

    def test_urgent_in_p0_tier(self, bus_root: Path, events_dir: Path) -> None:
        """Urgent messages appear in the P0 tier."""
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="Critical: lane down",
            priority="urgent",
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        p0, p1, p2 = read_inbox_prioritized(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert len(p0) == 1
        assert p0[0]["priority"] == "urgent"
        assert len(p1) == 0
        assert len(p2) == 0

    def test_high_in_p1_tier(self, bus_root: Path, events_dir: Path) -> None:
        """High-priority messages appear in the P1 tier."""
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="CI red on 2 lanes",
            priority="high",
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        p0, p1, p2 = read_inbox_prioritized(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert len(p0) == 0
        assert len(p1) == 1
        assert p1[0]["priority"] == "high"
        assert len(p2) == 0

    def test_normal_and_low_in_p2_tier(self, bus_root: Path, events_dir: Path) -> None:
        """Normal and low priority messages both appear in P2 tier."""
        for prio in ("normal", "low"):
            msg = create_message(
                from_lane="author-a",
                to_lane="orchestrator",
                message_type="progress",
                summary=f"Update ({prio} priority)",
                priority=prio,
            )
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

        p0, p1, p2 = read_inbox_prioritized(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert len(p0) == 0
        assert len(p1) == 0
        assert len(p2) == 2

    def test_mixed_priorities_sorted_into_tiers(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Messages of different priorities are correctly bucketed."""
        priorities = ["urgent", "high", "normal", "low", "urgent"]
        for i, prio in enumerate(priorities):
            msg = create_message(
                from_lane="author-a",
                to_lane="orchestrator",
                message_type="progress",
                summary=f"Msg {i} ({prio})",
                priority=prio,
            )
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

        p0, p1, p2 = read_inbox_prioritized(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert len(p0) == 2  # 2 urgent
        assert len(p1) == 1  # 1 high
        assert len(p2) == 2  # 1 normal + 1 low


# ---------------------------------------------------------------------------
# Test: Messages survive compaction
# ---------------------------------------------------------------------------


class TestCompactionSurvival:
    """Active messages survive inbox compaction; old terminal ones are purged."""

    def test_pending_messages_survive_compaction(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Pending (active) messages are always retained after compaction."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Active task",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        result = compact_inbox("author-a", bus_root=bus_root)
        assert result["removed"] == 0

        inbox = read_inbox(
            "author-a",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == mid for m in inbox)

    def test_delivered_messages_survive_compaction(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Delivered (active) messages are always retained."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Delivered task",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        mark_delivered(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        result = compact_inbox("author-a", bus_root=bus_root)
        assert result["removed"] == 0

    def test_old_resolved_messages_purged(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Old resolved messages are removed by compaction."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Ancient resolved task",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        resolve_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        # Compact with now far in the future so the message is "old"
        future_time = time.time() + 48 * 3600  # 48 hours from now
        result = compact_inbox("author-a", bus_root=bus_root, now=future_time)
        assert result["removed"] >= 1

        inbox = read_inbox(
            "author-a",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert not any(m["message_id"] == mid for m in inbox)

    def test_recent_acked_messages_kept(self, bus_root: Path, events_dir: Path) -> None:
        """Recently acked messages are retained (within retention window)."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Recently acked",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        # Compact at current time — acked message is recent, should survive
        result = compact_inbox("author-a", bus_root=bus_root)
        assert result["removed"] == 0

        inbox = read_inbox(
            "author-a",
            bus_root=bus_root,
            status="acked",
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == mid for m in inbox)


# ---------------------------------------------------------------------------
# Test: Full lifecycle transitions
# ---------------------------------------------------------------------------


class TestLifecycleTransitions:
    """Verify the complete message lifecycle: pending → delivered → acked → resolved."""

    def test_full_lifecycle(self, bus_root: Path, events_dir: Path) -> None:
        """Walk through all four lifecycle states."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Full lifecycle test",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # pending → delivered
        delivered = mark_delivered(
            mid, "author-a", bus_root=bus_root, events_dir=events_dir
        )
        assert delivered is not None
        assert delivered["status"] == "delivered"

        # delivered → acked
        acked = ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        assert acked is not None
        assert acked["status"] == "acked"
        assert acked["acked_at"] is not None

        # acked → resolved
        resolved = resolve_message(
            mid, "author-a", bus_root=bus_root, events_dir=events_dir
        )
        assert resolved is not None
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None

    def test_check_ack_status_tracks_transitions(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """check_ack_status reflects the current lifecycle stage."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Status tracking test",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        assert check_ack_status(mid, "author-a", bus_root=bus_root) == "pending"

        mark_delivered(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        assert check_ack_status(mid, "author-a", bus_root=bus_root) == "delivered"

        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        assert check_ack_status(mid, "author-a", bus_root=bus_root) == "acked"

        resolve_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        assert check_ack_status(mid, "author-a", bus_root=bus_root) == "resolved"

    def test_check_ack_status_nonexistent(self, bus_root: Path) -> None:
        """check_ack_status returns None for unknown message IDs."""
        assert check_ack_status("nonexistent_id", "author-a", bus_root=bus_root) is None

    def test_mark_delivered_nonexistent(self, bus_root: Path, events_dir: Path) -> None:
        """mark_delivered returns None for unknown message IDs."""
        result = mark_delivered(
            "nonexistent_id", "author-a", bus_root=bus_root, events_dir=events_dir
        )
        assert result is None

    def test_resolve_nonexistent(self, bus_root: Path, events_dir: Path) -> None:
        """resolve_message returns None for unknown message IDs."""
        result = resolve_message(
            "nonexistent_id", "author-a", bus_root=bus_root, events_dir=events_dir
        )
        assert result is None


# ---------------------------------------------------------------------------
# Test: Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    """Verify that invalid operations raise appropriate errors."""

    def test_invalid_message_type_raises(self) -> None:
        """Creating a message with an invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid message_type"):
            create_message(
                from_lane="author-a",
                to_lane="orchestrator",
                message_type="invalid_type",
                summary="Should fail",
            )

    def test_invalid_priority_raises(self) -> None:
        """Creating a message with an invalid priority raises ValueError."""
        with pytest.raises(ValueError, match="Invalid priority"):
            create_message(
                from_lane="author-a",
                to_lane="orchestrator",
                message_type="ack",
                summary="Should fail",
                priority="critical",  # not a valid priority
            )

    def test_invalid_status_on_bus_message_raises(self) -> None:
        """Direct BusMessage construction with invalid status raises ValueError."""
        with pytest.raises(ValueError, match="Invalid status"):
            BusMessage(
                message_id="test123",
                thread_id=None,
                task_id=None,
                from_lane="author-a",
                to_lane="orchestrator",
                message_type="ack",
                priority="normal",
                status="invalid_status",
                created_at="2026-01-01T00:00:00Z",
                acked_at=None,
                resolved_at=None,
                requires_human=False,
                summary="Should fail",
            )

    def test_invalid_transition_acked_to_acked(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Acking an already-acked message raises ValueError."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Double ack test",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

    def test_invalid_transition_resolved_to_acked(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Cannot ack a resolved (terminal) message."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Terminal transition test",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        resolve_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

    def test_invalid_transition_pending_to_resolved(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Cannot resolve a message that hasn't been acked first."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Skip-ack test",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            resolve_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

    def test_duplicate_message_id_raises(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Sending a message with a duplicate ID raises ValueError."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="First send",
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Attempt to re-send the exact same BusMessage object (same message_id)
        with pytest.raises(ValueError, match="Duplicate message_id"):
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

    def test_valid_message_types_are_exhaustive(self) -> None:
        """Smoke: all expected message types are in the valid set."""
        expected = {
            "assignment",
            "ack",
            "progress",
            "blocker",
            "completion",
            "escalation",
            "recovery",
            "supervisor_alert",
        }
        assert VALID_MESSAGE_TYPES == expected

    def test_valid_priorities_are_exhaustive(self) -> None:
        """Smoke: all expected priorities are in the valid set."""
        expected = {"low", "normal", "high", "urgent"}
        assert VALID_MESSAGE_PRIORITIES == expected


# ---------------------------------------------------------------------------
# Test: Bulk ack
# ---------------------------------------------------------------------------


class TestBulkAck:
    """Verify bulk_ack_messages works with filter predicates."""

    def test_bulk_ack_by_message_type(self, bus_root: Path, events_dir: Path) -> None:
        """Bulk-ack all assignment messages in a lane's inbox."""
        # Send 2 assignments and 1 progress to author-a
        for summary in ("Task A", "Task B"):
            msg = create_message(
                from_lane="orchestrator",
                to_lane="author-a",
                message_type="assignment",
                summary=summary,
            )
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

        progress = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="progress",
            summary="Status update",
        )
        send_message(progress, bus_root=bus_root, events_dir=events_dir)

        # Bulk-ack only assignments
        acked = bulk_ack_messages(
            "author-a",
            lambda m: m.get("message_type") == "assignment",
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(acked) == 2
        assert all(a["status"] == "acked" for a in acked)

        # Progress message should still be pending
        pending = read_inbox(
            "author-a",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(pending) == 1
        assert pending[0]["message_type"] == "progress"

    def test_bulk_ack_skips_already_acked(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Bulk-ack does not re-ack already-acked messages."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Already acked",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        # Bulk-ack should return empty (nothing ackable)
        acked = bulk_ack_messages(
            "author-a",
            lambda m: True,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(acked) == 0

    def test_bulk_ack_empty_inbox(self, bus_root: Path, events_dir: Path) -> None:
        """Bulk-ack on empty inbox returns empty list."""
        acked = bulk_ack_messages(
            "author-a",
            lambda m: True,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert acked == []


# ---------------------------------------------------------------------------
# Test: Query unresolved
# ---------------------------------------------------------------------------


class TestQueryUnresolved:
    """Verify query_unresolved returns only non-terminal messages."""

    def test_returns_pending_and_acked(self, bus_root: Path, events_dir: Path) -> None:
        """query_unresolved includes pending and acked messages."""
        msg1 = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Pending msg",
        )
        mid1 = send_message(msg1, bus_root=bus_root, events_dir=events_dir)

        msg2 = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Acked msg",
        )
        mid2 = send_message(msg2, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid2, "author-a", bus_root=bus_root, events_dir=events_dir)

        unresolved = query_unresolved("author-a", bus_root=bus_root)
        unresolved_ids = [m["message_id"] for m in unresolved]
        assert mid1 in unresolved_ids
        assert mid2 in unresolved_ids

    def test_excludes_resolved(self, bus_root: Path, events_dir: Path) -> None:
        """query_unresolved excludes resolved messages."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Will be resolved",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)
        resolve_message(mid, "author-a", bus_root=bus_root, events_dir=events_dir)

        unresolved = query_unresolved("author-a", bus_root=bus_root)
        unresolved_ids = [m["message_id"] for m in unresolved]
        assert mid not in unresolved_ids


# ---------------------------------------------------------------------------
# Test: TTL expiry
# ---------------------------------------------------------------------------


class TestTTLExpiry:
    """Verify messages expire after their TTL."""

    def test_expired_message_transitions(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """A message past its TTL is marked expired by check_expired."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Short-lived message",
            payload={"ttl_seconds": 60},  # 60 second TTL
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Check with current time — should not be expired yet
        expired = check_expired(bus_root=bus_root, events_dir=events_dir)
        assert len(expired) == 0

        # Check with time far in the future
        future = time.time() + 3600  # 1 hour from now
        expired = check_expired(bus_root=bus_root, events_dir=events_dir, now=future)
        assert len(expired) == 1
        assert expired[0]["status"] == "expired"

    def test_non_expired_message_untouched(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """A message within its TTL is not expired."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Long-lived message",
            payload={"ttl_seconds": 86400},  # 24 hour TTL
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Check at current time — should not expire
        expired = check_expired(bus_root=bus_root, events_dir=events_dir)
        assert len(expired) == 0

        status = check_ack_status(mid, "author-a", bus_root=bus_root)
        assert status == "pending"


# ---------------------------------------------------------------------------
# Test: Dead letters
# ---------------------------------------------------------------------------


class TestDeadLetters:
    """Verify messages exceeding max_retries are dead-lettered."""

    def test_dead_letter_on_max_retries(self, bus_root: Path, events_dir: Path) -> None:
        """A message at max_retries is marked dead_lettered."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Failed delivery",
            payload={"max_retries": 3, "retry_count": 3},
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        dead = check_dead_letters(bus_root=bus_root, events_dir=events_dir)
        assert len(dead) == 1
        assert dead[0]["status"] == "dead_lettered"

    def test_below_max_retries_not_dead_lettered(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """A message below max_retries is not dead-lettered."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Retrying delivery",
            payload={"max_retries": 3, "retry_count": 2},
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        dead = check_dead_letters(bus_root=bus_root, events_dir=events_dir)
        assert len(dead) == 0


# ---------------------------------------------------------------------------
# Test: Escalation
# ---------------------------------------------------------------------------


class TestEscalation:
    """Verify unacked message escalation creates urgent follow-ups."""

    def test_escalate_old_unacked_message(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """An unacked message older than threshold triggers escalation."""
        # Send a message with an old created_at timestamp
        old_time = (
            datetime.now(timezone.utc).replace(year=2025).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        msg = BusMessage(
            message_id="old_msg_001",
            thread_id=None,
            task_id=None,
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            priority="normal",
            status="pending",
            created_at=old_time,
            acked_at=None,
            resolved_at=None,
            requires_human=False,
            summary="Ancient unacked task",
            payload={"max_retries": 3, "retry_count": 0, "ttl_seconds": 86400},
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Escalate with a short threshold (0 minutes = escalate everything)
        esc_ids = escalate_unacked(
            "orchestrator",
            "author-a",
            max_age_minutes=0,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(esc_ids) == 1

        # Verify the escalation message is in the inbox
        inbox = read_inbox(
            "author-a",
            bus_root=bus_root,
            message_type="escalation",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(inbox) == 1
        assert inbox[0]["priority"] == "urgent"
        assert "old_msg_001" in inbox[0]["summary"]

    def test_escalation_does_not_re_escalate_escalations(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Escalation messages themselves are not re-escalated."""
        old_time = (
            datetime.now(timezone.utc).replace(year=2025).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        # Send an escalation message (from orchestrator → author-a)
        esc = BusMessage(
            message_id="esc_msg_001",
            thread_id=None,
            task_id=None,
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="escalation",
            priority="urgent",
            status="pending",
            created_at=old_time,
            acked_at=None,
            resolved_at=None,
            requires_human=False,
            summary="Already escalated",
            payload={"max_retries": 3, "retry_count": 0, "ttl_seconds": 86400},
        )
        send_message(esc, bus_root=bus_root, events_dir=events_dir)

        # Should not create another escalation
        esc_ids = escalate_unacked(
            "orchestrator",
            "author-a",
            max_age_minutes=0,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(esc_ids) == 0

    def test_no_escalation_for_recently_sent(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Recent messages are not escalated."""
        msg = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Fresh message",
        )
        send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Use a long threshold (no recent message should be old enough)
        esc_ids = escalate_unacked(
            "orchestrator",
            "author-a",
            max_age_minutes=60,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(esc_ids) == 0


# ---------------------------------------------------------------------------
# Test: Content dedup
# ---------------------------------------------------------------------------


class TestContentDedup:
    """Verify content-based dedup suppresses duplicate sends."""

    def test_dedup_suppresses_identical_content(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Sending the same content twice with deduplicate=True returns existing ID."""
        msg1 = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Task received",
        )
        mid1 = send_message(
            msg1, bus_root=bus_root, events_dir=events_dir, deduplicate=True
        )

        msg2 = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Task received",
        )
        mid2 = send_message(
            msg2, bus_root=bus_root, events_dir=events_dir, deduplicate=True
        )

        # Should return the first message's ID, not create a new one
        assert mid2 == mid1

    def test_dedup_off_allows_duplicates(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Without deduplicate=True, identical content creates separate messages."""
        msg1 = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Task received (no dedup)",
        )
        mid1 = send_message(msg1, bus_root=bus_root, events_dir=events_dir)

        msg2 = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Task received (no dedup)",
        )
        mid2 = send_message(msg2, bus_root=bus_root, events_dir=events_dir)

        assert mid2 != mid1

    def test_dedup_allows_escalation_duplicates(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Escalation messages bypass content dedup even when deduplicate=True."""
        msg1 = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="escalation",
            summary="ESCALATION: unacked msg",
        )
        mid1 = send_message(
            msg1, bus_root=bus_root, events_dir=events_dir, deduplicate=True
        )

        msg2 = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="escalation",
            summary="ESCALATION: unacked msg",
        )
        mid2 = send_message(
            msg2, bus_root=bus_root, events_dir=events_dir, deduplicate=True
        )

        # Each escalation should be delivered separately
        assert mid2 != mid1


# ---------------------------------------------------------------------------
# Test: Inbox statistics
# ---------------------------------------------------------------------------


class TestInboxStats:
    """Verify inbox_stats returns accurate per-lane counts."""

    def test_stats_reflect_message_states(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """inbox_stats correctly counts messages by status."""
        # Create 2 pending and 1 acked message for author-a
        for summary in ("Task 1", "Task 2"):
            msg = create_message(
                from_lane="orchestrator",
                to_lane="author-a",
                message_type="assignment",
                summary=summary,
            )
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

        msg3 = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Task 3 (will ack)",
        )
        mid3 = send_message(msg3, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid3, "author-a", bus_root=bus_root, events_dir=events_dir)

        stats = inbox_stats(bus_root=bus_root)
        lane_data = next(
            lane for lane in stats["lanes"] if lane["lane_id"] == "author-a"
        )
        assert lane_data["total"] == 3
        assert lane_data["by_status"].get("pending", 0) == 2
        assert lane_data["by_status"].get("acked", 0) == 1

    def test_stats_empty_bus(self, bus_root: Path) -> None:
        """inbox_stats on empty bus returns empty lanes list."""
        stats = inbox_stats(bus_root=bus_root)
        assert stats["lanes"] == []

    def test_stats_multiple_lanes(self, bus_root: Path, events_dir: Path) -> None:
        """inbox_stats reports on all lanes with messages."""
        for lane in ("author-a", "brws-author-a", "orchestrator"):
            msg = create_message(
                from_lane="ops",
                to_lane=lane,
                message_type="supervisor_alert",
                summary=f"Alert for {lane}",
            )
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

        stats = inbox_stats(bus_root=bus_root)
        lane_ids = {lane["lane_id"] for lane in stats["lanes"]}
        assert "author-a" in lane_ids
        assert "brws-author-a" in lane_ids
        assert "orchestrator" in lane_ids


# ---------------------------------------------------------------------------
# Test: create_message factory defaults
# ---------------------------------------------------------------------------


class TestCreateMessageDefaults:
    """Verify create_message populates expected default fields."""

    def test_default_priority_is_normal(self) -> None:
        """Default priority is 'normal'."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert msg.priority == "normal"

    def test_default_status_is_pending(self) -> None:
        """Default status is 'pending'."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert msg.status == "pending"

    def test_delivery_policy_defaults_in_payload(self) -> None:
        """Payload includes max_retries, retry_count, ttl_seconds."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert msg.payload["max_retries"] == 3
        assert msg.payload["retry_count"] == 0
        assert msg.payload["ttl_seconds"] == 86400

    def test_custom_payload_preserved(self) -> None:
        """Custom payload fields are merged with defaults."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
            payload={"custom_key": "custom_value"},
        )
        assert msg.payload["custom_key"] == "custom_value"
        assert "max_retries" in msg.payload  # default still present

    def test_message_id_is_hex(self) -> None:
        """Message ID is a 16-char hex string."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert len(msg.message_id) == 16
        int(msg.message_id, 16)  # Should not raise

    def test_optional_fields_default_none(self) -> None:
        """Thread ID, task ID, acked_at, resolved_at default to None."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert msg.thread_id is None
        assert msg.task_id is None
        assert msg.acked_at is None
        assert msg.resolved_at is None

    def test_source_transport_default(self) -> None:
        """Default source_transport is 'bus'."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert msg.source_transport == "bus"

    def test_requires_human_default_false(self) -> None:
        """Default requires_human is False."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Test",
        )
        assert msg.requires_human is False


# ---------------------------------------------------------------------------
# Test: Valid constants (smoke)
# ---------------------------------------------------------------------------


class TestValidConstants:
    """Smoke tests for valid message bus constants."""

    def test_all_statuses_have_transitions(self) -> None:
        """Every valid status has an entry in the transition map."""
        for status in VALID_MESSAGE_STATUSES:
            assert status in VALID_MESSAGE_TRANSITIONS

    def test_transition_targets_are_valid_statuses(self) -> None:
        """All transition targets are valid statuses."""
        for _source, targets in VALID_MESSAGE_TRANSITIONS.items():
            for target in targets:
                assert target in VALID_MESSAGE_STATUSES

    def test_terminal_states_have_no_transitions(self) -> None:
        """Terminal states (resolved, expired, dead_lettered) cannot transition."""
        terminal = {"resolved", "expired", "dead_lettered"}
        for state in terminal:
            assert len(VALID_MESSAGE_TRANSITIONS[state]) == 0
