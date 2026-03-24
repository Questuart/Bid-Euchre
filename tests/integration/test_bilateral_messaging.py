"""Integration tests for bilateral lane-to-lane messaging.

Proves end-to-end bilateral messaging works across all lane pool types:
- Platform pool (author-a/b/c/d)
- Browser-game pool (brws-author-a/b/c/d)
- Flex pool (flex-a/b/c)

Each test exercises the full send → deliver → read → ack cycle using
the real message_bus module against a temporary bus root.

Closes #1570.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.message_bus import (
    ack_message,
    create_message,
    read_inbox,
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
