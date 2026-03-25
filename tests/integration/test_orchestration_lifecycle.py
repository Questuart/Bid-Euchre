"""Integration tests for the full orchestration lifecycle.

Proves the complete dispatch→ack→progress→completion→orchestrator-ack
lifecycle works end-to-end using the real message_bus module against a
temporary bus root.  No tmux, no live Claude sessions — pure data-contract
validation.

Closes #1597.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from bid_euchre.ops.message_bus import (
    ack_message,
    check_ack_status,
    create_message,
    escalate_unacked,
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
# Test: Full orchestration lifecycle
# ---------------------------------------------------------------------------


class TestOrchestrationLifecycle:
    """Prove the full dispatch→ack→progress→completion→orchestrator-ack lifecycle."""

    def test_full_lifecycle(self, bus_root: Path, events_dir: Path) -> None:
        """Complete orchestration lifecycle in 10 steps."""

        # 1. Orchestrator creates assignment
        assign = create_message(
            from_lane="orchestrator",
            to_lane="author-a",
            message_type="assignment",
            summary="Fix bug #123",
            task_id="packet-001",
        )
        assign_id = send_message(assign, bus_root=bus_root, events_dir=events_dir)

        # 2. Lane receives assignment in inbox
        lane_inbox = read_inbox(
            "author-a", bus_root=bus_root, auto_expire=False, auto_compact=False
        )
        assert any(m["message_id"] == assign_id for m in lane_inbox)

        # 3. Lane acks the assignment
        ack_result = ack_message(
            assign_id, "author-a", bus_root=bus_root, events_dir=events_dir
        )
        assert ack_result is not None
        assert ack_result["status"] == "acked"

        # 4. Lane sends ack back to orchestrator
        ack_back = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="ack",
            summary="Task received",
            task_id="packet-001",
        )
        ack_id = send_message(ack_back, bus_root=bus_root, events_dir=events_dir)

        # 5. Lane sends progress
        progress = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="progress",
            summary="PR opened",
            task_id="packet-001",
        )
        progress_id = send_message(progress, bus_root=bus_root, events_dir=events_dir)

        # 6. Lane sends completion (high priority)
        complete = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="completion",
            summary="PR #1234 merged",
            task_id="packet-001",
            priority="high",
        )
        complete_id = send_message(complete, bus_root=bus_root, events_dir=events_dir)

        # 7. Orchestrator reads prioritized inbox — completion should be P1
        p0, p1, p2 = read_inbox_prioritized(
            "orchestrator", bus_root=bus_root, auto_expire=False, auto_compact=False
        )
        assert any(m["message_id"] == complete_id for m in p1), (
            f"Completion {complete_id} should be in P1 (high). "
            f"P0={[m['message_id'] for m in p0]}, "
            f"P1={[m['message_id'] for m in p1]}, "
            f"P2={[m['message_id'] for m in p2]}"
        )
        # ack and progress should be in P2 (normal priority)
        p2_ids = [m["message_id"] for m in p2]
        assert ack_id in p2_ids
        assert progress_id in p2_ids

        # 8. Orchestrator acks all messages
        for mid in [ack_id, progress_id, complete_id]:
            ack_message(mid, "orchestrator", bus_root=bus_root, events_dir=events_dir)

        # 9. Verify clean state — no pending messages in orchestrator inbox
        pending = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(pending) == 0, (
            f"Expected 0 pending messages, got {len(pending)}: "
            f"{[m['message_id'] for m in pending]}"
        )

        # 10. Verify check_ack_status works for the original assignment
        status = check_ack_status(assign_id, "author-a", bus_root=bus_root)
        assert status == "acked"

    def test_task_id_threading(self, bus_root: Path, events_dir: Path) -> None:
        """Messages sharing a task_id form a traceable thread."""
        task_id = "packet-thread-test"

        # Send multiple message types with same task_id
        for msg_type, summary in [
            ("assignment", "Build feature Y"),
            ("ack", "Task received"),
            ("progress", "Implementation started"),
            ("completion", "PR merged"),
        ]:
            from_lane = "orchestrator" if msg_type == "assignment" else "author-a"
            to_lane = "author-a" if msg_type == "assignment" else "orchestrator"
            msg = create_message(
                from_lane=from_lane,
                to_lane=to_lane,
                message_type=msg_type,
                summary=summary,
                task_id=task_id,
            )
            send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Read orchestrator inbox — all messages from author-a share the task_id
        inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        task_msgs = [m for m in inbox if m.get("task_id") == task_id]
        assert len(task_msgs) == 3  # ack + progress + completion
        assert {m["message_type"] for m in task_msgs} == {
            "ack",
            "progress",
            "completion",
        }


# ---------------------------------------------------------------------------
# Test: Escalation on ignored completion
# ---------------------------------------------------------------------------


class TestEscalationOnIgnoredCompletion:
    """If orchestrator ignores a completion, ops can detect and escalate."""

    def test_escalation_fires_for_stale_unacked(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Unacked messages older than the threshold trigger escalation."""

        # Send a completion from lane to orchestrator
        complete = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="completion",
            summary="PR #5678 merged",
            task_id="packet-stale",
        )
        complete_id = send_message(complete, bus_root=bus_root, events_dir=events_dir)

        # DON'T ack from orchestrator — simulate ignoring

        # Verify it's pending
        status = check_ack_status(complete_id, "orchestrator", bus_root=bus_root)
        assert status == "pending"

        # Backdate the message to simulate age > threshold
        # We'll use max_age_minutes=0 so the current time always exceeds it
        escalation_ids = escalate_unacked(
            sender_lane="author-a",
            recipient_lane="orchestrator",
            max_age_minutes=0,  # any age qualifies
            bus_root=bus_root,
            events_dir=events_dir,
        )

        # Should have at least one escalation
        assert len(escalation_ids) >= 1, (
            f"Expected escalation for unacked message {complete_id}, "
            f"got {escalation_ids}"
        )

        # Verify escalation message arrived in orchestrator's inbox
        inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            message_type="escalation",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(inbox) >= 1
        escalation = inbox[0]
        assert escalation["message_type"] == "escalation"
        assert escalation["priority"] == "urgent"
        assert escalation["parent_message_id"] == complete_id

    def test_no_escalation_when_acked(self, bus_root: Path, events_dir: Path) -> None:
        """Acked messages should NOT trigger escalation."""

        # Send and immediately ack
        msg = create_message(
            from_lane="author-b",
            to_lane="orchestrator",
            message_type="completion",
            summary="PR #9999 merged",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)
        ack_message(mid, "orchestrator", bus_root=bus_root, events_dir=events_dir)

        # Escalate should find nothing
        escalation_ids = escalate_unacked(
            sender_lane="author-b",
            recipient_lane="orchestrator",
            max_age_minutes=0,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(escalation_ids) == 0


# ---------------------------------------------------------------------------
# Test: Cross-pool lifecycle
# ---------------------------------------------------------------------------

POOL_REPRESENTATIVES = [
    pytest.param("author-a", id="platform"),
    pytest.param("brws-author-a", id="browser-game"),
    pytest.param("flex-a", id="flex"),
]


class TestCrossPoolLifecycle:
    """Same lifecycle works for browser-game and flex pool lanes."""

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_full_cycle_per_pool(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Each pool type completes the assign→ack→complete→verify cycle."""

        # 1. Orchestrator assigns
        assign = create_message(
            from_lane="orchestrator",
            to_lane=lane,
            message_type="assignment",
            summary=f"Task for {lane}",
            task_id=f"packet-{lane}",
        )
        assign_id = send_message(assign, bus_root=bus_root, events_dir=events_dir)

        # 2. Lane acks assignment
        ack_message(assign_id, lane, bus_root=bus_root, events_dir=events_dir)

        # 3. Lane sends ack back
        ack_back = create_message(
            from_lane=lane,
            to_lane="orchestrator",
            message_type="ack",
            summary=f"Received on {lane}",
            task_id=f"packet-{lane}",
        )
        ack_id = send_message(ack_back, bus_root=bus_root, events_dir=events_dir)

        # 4. Lane sends completion
        complete = create_message(
            from_lane=lane,
            to_lane="orchestrator",
            message_type="completion",
            summary=f"Done on {lane}",
            task_id=f"packet-{lane}",
        )
        complete_id = send_message(complete, bus_root=bus_root, events_dir=events_dir)

        # 5. Orchestrator sees both messages
        orch_inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        orch_ids = [m["message_id"] for m in orch_inbox]
        assert ack_id in orch_ids, f"Ack {ack_id} not in orchestrator inbox"
        assert complete_id in orch_ids, f"Completion {complete_id} not in inbox"

        # 6. Verify check_ack_status for the assignment
        status = check_ack_status(assign_id, lane, bus_root=bus_root)
        assert status == "acked"

        # 7. Orchestrator acks both messages
        ack_message(ack_id, "orchestrator", bus_root=bus_root, events_dir=events_dir)
        ack_message(
            complete_id, "orchestrator", bus_root=bus_root, events_dir=events_dir
        )

        # 8. Clean orchestrator inbox for this lane's messages
        pending = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        lane_pending = [m for m in pending if m.get("from_lane") == lane]
        assert (
            len(lane_pending) == 0
        ), f"Expected 0 pending from {lane}, got {len(lane_pending)}"

    @pytest.mark.parametrize("lane", POOL_REPRESENTATIVES)
    def test_cross_pool_isolation_during_lifecycle(
        self, lane: str, bus_root: Path, events_dir: Path
    ) -> None:
        """Messages for one pool do not leak into another pool's inbox."""
        # Send assignment to the parameterized lane
        msg = create_message(
            from_lane="orchestrator",
            to_lane=lane,
            message_type="assignment",
            summary=f"Isolated task for {lane}",
        )
        mid = send_message(msg, bus_root=bus_root, events_dir=events_dir)

        # Verify present in target lane
        target_inbox = read_inbox(
            lane, bus_root=bus_root, auto_expire=False, auto_compact=False
        )
        assert any(m["message_id"] == mid for m in target_inbox)

        # Verify absent from all other representative lanes
        all_lanes = ["author-a", "brws-author-a", "flex-a"]
        for other_lane in all_lanes:
            if other_lane == lane:
                continue
            other_inbox = read_inbox(
                other_lane,
                bus_root=bus_root,
                auto_expire=False,
                auto_compact=False,
            )
            assert not any(
                m["message_id"] == mid for m in other_inbox
            ), f"Message {mid} for {lane} leaked into {other_lane}'s inbox"


# ---------------------------------------------------------------------------
# Test: Ack/resolve transitions clear surfaced urgent items
# ---------------------------------------------------------------------------


class TestResolveTransitionsClearUrgent:
    """Ack/resolve on urgent items removes them from pending views."""

    def test_resolve_clears_urgent_items(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Urgent escalation message disappears from P0 after ack+resolve."""
        # Send an urgent escalation to orchestrator
        esc = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="escalation",
            summary="URGENT: lane stalled",
            priority="urgent",
        )
        esc_id = send_message(esc, bus_root=bus_root, events_dir=events_dir)

        # Verify it appears in P0
        p0, p1, p2 = read_inbox_prioritized(
            "orchestrator", bus_root=bus_root, auto_expire=False, auto_compact=False
        )
        assert any(m["message_id"] == esc_id for m in p0)

        # Ack the escalation
        ack_message(esc_id, "orchestrator", bus_root=bus_root, events_dir=events_dir)

        # After ack, no longer in pending inbox
        pending = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        assert not any(m["message_id"] == esc_id for m in pending)

        # Resolve it
        resolve_message(
            esc_id, "orchestrator", bus_root=bus_root, events_dir=events_dir
        )

        # After resolve, status is terminal
        from bid_euchre.ops.message_bus import check_ack_status

        status = check_ack_status(esc_id, "orchestrator", bus_root=bus_root)
        assert status == "resolved"
