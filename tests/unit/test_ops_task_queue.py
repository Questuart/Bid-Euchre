"""Tests for the Platform-2 task queue module.

Covers: TaskPacket/TaskAck/TaskResult creation, validation, serialization,
queue I/O, lifecycle transitions, ack handling (approve/edit/redirect/reject),
queue summary, and concurrent write safety.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from bid_euchre.ops.task_queue import (
    KNOWN_AUTHOR_LANES,
    VALID_ACK_ACTIONS,
    VALID_PRIORITIES,
    VALID_RESULT_STATUSES,
    VALID_STATUSES,
    VALID_TRANSITIONS,
    TaskPacket,
    apply_ack,
    archive_packet,
    complete_packet,
    create_ack,
    create_packet,
    create_result,
    list_packets,
    load_ack,
    load_packet,
    load_result,
    queue_summary,
    save_ack,
    save_packet,
    save_result,
    shared_task_root,
    transition_status,
    update_packet_metadata,
)

# ---------------------------------------------------------------------------
# TaskPacket construction and validation
# ---------------------------------------------------------------------------


class TestTaskPacketCreation:
    """Test TaskPacket creation and field validation."""

    def test_create_packet_defaults(self) -> None:
        pkt = create_packet("Fix bug", "Fix the scoring edge case")
        assert pkt.title == "Fix bug"
        assert pkt.description == "Fix the scoring edge case"
        assert pkt.status == "pending"
        assert pkt.priority == "normal"
        assert pkt.created_by == "orchestrator"
        assert pkt.owner is None
        assert len(pkt.packet_id) == 12
        assert pkt.created_at  # Non-empty timestamp

    def test_create_packet_with_fields(self) -> None:
        pkt = create_packet(
            "Add feature",
            "Implement new scoring mode",
            owner="author-a",
            priority="high",
            scope_declared=["src/bid_euchre/scoring.py"],
            validation=["uv run python -m pytest tests/unit/test_scoring.py"],
            metadata={"plan_ref": "SP-1-02"},
        )
        assert pkt.owner == "author-a"
        assert pkt.priority == "high"
        assert pkt.scope_declared == ["src/bid_euchre/scoring.py"]
        assert pkt.validation == ["uv run python -m pytest tests/unit/test_scoring.py"]
        assert pkt.metadata == {"plan_ref": "SP-1-02"}

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            TaskPacket(
                packet_id="test",
                title="t",
                description="d",
                owner=None,
                created_by="orchestrator",
                created_at="2026-01-01T00:00:00Z",
                status="invalid_status",
            )

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid priority"):
            TaskPacket(
                packet_id="test",
                title="t",
                description="d",
                owner=None,
                created_by="orchestrator",
                created_at="2026-01-01T00:00:00Z",
                status="pending",
                priority="urgent",
            )

    def test_invalid_owner_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown owner lane"):
            TaskPacket(
                packet_id="test",
                title="t",
                description="d",
                owner="nonexistent-lane",
                created_by="orchestrator",
                created_at="2026-01-01T00:00:00Z",
                status="pending",
            )

    def test_none_owner_is_valid(self) -> None:
        pkt = create_packet("Test", "Test desc")
        assert pkt.owner is None

    def test_all_valid_statuses(self) -> None:
        for status in VALID_STATUSES:
            pkt = TaskPacket(
                packet_id="test",
                title="t",
                description="d",
                owner=None,
                created_by="orchestrator",
                created_at="2026-01-01T00:00:00Z",
                status=status,
            )
            assert pkt.status == status

    def test_all_valid_priorities(self) -> None:
        for priority in VALID_PRIORITIES:
            pkt = create_packet("t", "d", priority=priority)
            assert pkt.priority == priority

    def test_all_valid_owners(self) -> None:
        for owner in KNOWN_AUTHOR_LANES:
            pkt = create_packet("t", "d", owner=owner)
            assert pkt.owner == owner

    def test_frozen_immutability(self) -> None:
        pkt = create_packet("t", "d")
        with pytest.raises(AttributeError):
            pkt.status = "approved"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TaskAck construction and validation
# ---------------------------------------------------------------------------


class TestTaskAckCreation:
    """Test TaskAck creation and validation."""

    def test_create_approve_ack(self) -> None:
        ack = create_ack("pkt123", "approve")
        assert ack.packet_id == "pkt123"
        assert ack.action == "approve"
        assert ack.edited_fields == {}
        assert ack.redirect_to is None
        assert ack.acked_by == "user"
        assert ack.acked_at  # Non-empty

    def test_create_edit_ack(self) -> None:
        ack = create_ack("pkt123", "edit", edited_fields={"title": "Updated title"})
        assert ack.action == "edit"
        assert ack.edited_fields == {"title": "Updated title"}

    def test_create_redirect_ack(self) -> None:
        ack = create_ack("pkt123", "redirect", redirect_to="author-c")
        assert ack.action == "redirect"
        assert ack.redirect_to == "author-c"

    def test_redirect_without_target_raises(self) -> None:
        with pytest.raises(ValueError, match="redirect_to is required"):
            create_ack("pkt123", "redirect")

    def test_redirect_to_unknown_lane_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown redirect target"):
            create_ack("pkt123", "redirect", redirect_to="nonexistent")

    def test_reject_ack(self) -> None:
        ack = create_ack("pkt123", "reject")
        assert ack.action == "reject"

    def test_invalid_action_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid ack action"):
            create_ack("pkt123", "invalid_action")

    def test_all_valid_actions(self) -> None:
        for action in VALID_ACK_ACTIONS:
            kwargs: dict = {}
            if action == "redirect":
                kwargs["redirect_to"] = "author-a"
            ack = create_ack("pkt123", action, **kwargs)
            assert ack.action == action


# ---------------------------------------------------------------------------
# TaskResult construction and validation
# ---------------------------------------------------------------------------


class TestTaskResultCreation:
    """Test TaskResult creation and validation."""

    def test_create_completed_result(self) -> None:
        result = create_result(
            "pkt123", "completed", "Successfully merged", pr_number=42
        )
        assert result.packet_id == "pkt123"
        assert result.status == "completed"
        assert result.summary == "Successfully merged"
        assert result.pr_number == 42
        assert result.completed_at  # Non-empty

    def test_create_failed_result(self) -> None:
        result = create_result("pkt123", "failed", "Tests failed")
        assert result.status == "failed"
        assert result.pr_number is None

    def test_invalid_result_status_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid result status"):
            create_result("pkt123", "invalid", "nope")

    def test_all_valid_result_statuses(self) -> None:
        for status in VALID_RESULT_STATUSES:
            result = create_result("pkt123", status, "summary")
            assert result.status == status


# ---------------------------------------------------------------------------
# Queue I/O (file-based persistence)
# ---------------------------------------------------------------------------


class TestQueueIO:
    """Test file-based queue operations."""

    def test_shared_task_root_creates_dirs(self, tmp_path: Path) -> None:
        root = shared_task_root(tmp_path / "queue")
        assert root.exists()
        assert (root / "archive").exists()

    def test_save_and_load_packet(self, tmp_path: Path) -> None:
        pkt = create_packet("Test task", "Test description", owner="author-a")
        path = save_packet(pkt, tmp_path)
        assert path.exists()

        loaded = load_packet(pkt.packet_id, tmp_path)
        assert loaded is not None
        assert loaded.packet_id == pkt.packet_id
        assert loaded.title == pkt.title
        assert loaded.owner == pkt.owner
        assert loaded.status == pkt.status

    def test_save_and_load_ack(self, tmp_path: Path) -> None:
        ack = create_ack("pkt123", "approve")
        path = save_ack(ack, tmp_path)
        assert path.exists()

        loaded = load_ack("pkt123", tmp_path)
        assert loaded is not None
        assert loaded.action == "approve"

    def test_save_and_load_result(self, tmp_path: Path) -> None:
        result = create_result("pkt123", "completed", "Done", pr_number=99)
        path = save_result(result, tmp_path)
        assert path.exists()

        loaded = load_result("pkt123", tmp_path)
        assert loaded is not None
        assert loaded.status == "completed"
        assert loaded.pr_number == 99

    def test_load_nonexistent_packet_returns_none(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert load_packet("nonexistent", tmp_path) is None

    def test_load_nonexistent_ack_returns_none(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert load_ack("nonexistent", tmp_path) is None

    def test_load_nonexistent_result_returns_none(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert load_result("nonexistent", tmp_path) is None

    def test_load_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("not valid json{{{")
        assert load_packet("corrupt", tmp_path) is None

    def test_save_packet_json_structure(self, tmp_path: Path) -> None:
        """Verify the saved JSON has the expected structure."""
        pkt = create_packet(
            "Test",
            "Description",
            owner="author-b",
            scope_declared=["src/foo.py"],
            metadata={"key": "value"},
        )
        path = save_packet(pkt, tmp_path)
        data = json.loads(path.read_text())
        assert data["packet_id"] == pkt.packet_id
        assert data["title"] == "Test"
        assert data["owner"] == "author-b"
        assert data["scope_declared"] == ["src/foo.py"]
        assert data["metadata"] == {"key": "value"}

    def test_concurrent_saves_no_collision(self, tmp_path: Path) -> None:
        """Concurrent save_packet calls must not corrupt each other.

        Regression test for #1223: _write_json_atomic previously used a
        deterministic .tmp path, so two concurrent writers to the same
        packet_id could race on the shared temp file.
        """
        pkt = create_packet("Concurrent", "d", owner="author-a")
        errors: list[Exception] = []
        barrier = threading.Barrier(4)

        def writer() -> None:
            barrier.wait()
            try:
                save_packet(pkt, tmp_path)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f"Concurrent saves raised: {errors}"

        # The final file should be valid JSON for this packet
        loaded = load_packet(pkt.packet_id, tmp_path)
        assert loaded is not None
        assert loaded.packet_id == pkt.packet_id

    def test_no_leftover_tmp_files_after_save(self, tmp_path: Path) -> None:
        """Successful saves must not leave .tmp files behind."""
        pkt = create_packet("Clean", "d")
        save_packet(pkt, tmp_path)

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"


# ---------------------------------------------------------------------------
# list_packets and filtering
# ---------------------------------------------------------------------------


class TestListPackets:
    """Test listing and filtering of queue packets."""

    def test_list_empty_queue(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert list_packets(tmp_path) == []

    def test_list_multiple_packets(self, tmp_path: Path) -> None:
        pkt1 = create_packet("Task 1", "Desc 1", owner="author-a")
        pkt2 = create_packet("Task 2", "Desc 2", owner="author-b")
        save_packet(pkt1, tmp_path)
        save_packet(pkt2, tmp_path)

        packets = list_packets(tmp_path)
        assert len(packets) == 2

    def test_list_filter_by_status(self, tmp_path: Path) -> None:
        pkt1 = create_packet("Task 1", "Desc 1")
        save_packet(pkt1, tmp_path)
        # Transition through valid flow: pending -> previewing -> approved
        transition_status(pkt1.packet_id, "previewing", tmp_path)
        transition_status(pkt1.packet_id, "approved", tmp_path)
        pkt2 = create_packet("Task 2", "Desc 2")
        save_packet(pkt2, tmp_path)

        pending = list_packets(tmp_path, status_filter="pending")
        assert len(pending) == 1
        assert pending[0].title == "Task 2"

        approved = list_packets(tmp_path, status_filter="approved")
        assert len(approved) == 1
        assert approved[0].title == "Task 1"

    def test_list_filter_by_owner(self, tmp_path: Path) -> None:
        save_packet(create_packet("Task 1", "d", owner="author-a"), tmp_path)
        save_packet(create_packet("Task 2", "d", owner="author-b"), tmp_path)

        author_a = list_packets(tmp_path, owner_filter="author-a")
        assert len(author_a) == 1
        assert author_a[0].title == "Task 1"

    def test_list_skips_sidecar_files(self, tmp_path: Path) -> None:
        """Ack and result files should not appear as packets."""
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)
        save_ack(create_ack(pkt.packet_id, "approve"), tmp_path)
        save_result(create_result(pkt.packet_id, "completed", "done"), tmp_path)

        packets = list_packets(tmp_path)
        assert len(packets) == 1


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


class TestLifecycleTransitions:
    """Test status transitions and lifecycle management."""

    def test_transition_status(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)

        # pending -> previewing (valid)
        updated = transition_status(pkt.packet_id, "previewing", tmp_path)
        assert updated is not None
        assert updated.status == "previewing"

        # previewing -> approved (valid)
        updated = transition_status(pkt.packet_id, "approved", tmp_path)
        assert updated is not None
        assert updated.status == "approved"

        # Verify persisted
        reloaded = load_packet(pkt.packet_id, tmp_path)
        assert reloaded is not None
        assert reloaded.status == "approved"

    def test_transition_pending_to_approved_direct(self, tmp_path: Path) -> None:
        """Trivial tasks can skip preview: pending -> approved."""
        pkt = create_packet("Trivial fix", "d")
        save_packet(pkt, tmp_path)

        updated = transition_status(pkt.packet_id, "approved", tmp_path)
        assert updated is not None
        assert updated.status == "approved"

    def test_transition_invalid_from_terminal_raises(self, tmp_path: Path) -> None:
        """Terminal states (completed, rejected, redirected) cannot transition."""
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "rejected", tmp_path)

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(pkt.packet_id, "approved", tmp_path)

    def test_transition_dispatched_to_pending_raises(self, tmp_path: Path) -> None:
        """Backward transitions are not allowed."""
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(pkt.packet_id, "pending", tmp_path)

    def test_transition_nonexistent_returns_none(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert transition_status("nonexistent", "approved", tmp_path) is None

    def test_transition_invalid_status_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Invalid target status"):
            transition_status("any", "bogus", tmp_path)

    def test_valid_transitions_covers_all_statuses(self) -> None:
        """Every valid status has an entry in the transition map."""
        assert set(VALID_TRANSITIONS.keys()) == VALID_STATUSES

    def test_transition_map_targets_are_valid(self) -> None:
        """All transition targets are themselves valid statuses."""
        for source, targets in VALID_TRANSITIONS.items():
            for target in targets:
                assert (
                    target in VALID_STATUSES
                ), f"Transition {source!r} -> {target!r}: target is not a valid status"

    def test_terminal_states_have_no_transitions(self) -> None:
        """Terminal states cannot transition onward."""
        for terminal in ("completed", "failed", "rejected", "redirected"):
            assert VALID_TRANSITIONS[terminal] == frozenset(), (
                f"{terminal!r} should be terminal but allows: "
                f"{VALID_TRANSITIONS[terminal]}"
            )

    def test_dispatched_to_failed_allowed(self, tmp_path: Path) -> None:
        """#2701 — reconciler transitions dispatched → failed on CLOSED PR."""
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)

        updated = transition_status(pkt.packet_id, "failed", tmp_path)
        assert updated is not None
        assert updated.status == "failed"

    def test_failed_is_terminal(self, tmp_path: Path) -> None:
        """Once failed, the packet cannot re-enter an earlier state."""
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)
        transition_status(pkt.packet_id, "failed", tmp_path)

        with pytest.raises(ValueError, match="Invalid transition"):
            transition_status(pkt.packet_id, "completed", tmp_path)

    def test_archive_packet(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)
        save_ack(create_ack(pkt.packet_id, "approve"), tmp_path)

        moved = archive_packet(pkt.packet_id, tmp_path)
        assert moved is True

        # Original should be gone
        assert load_packet(pkt.packet_id, tmp_path) is None

        # Archive should have the files
        archive_dir = tmp_path / "archive"
        assert (archive_dir / f"{pkt.packet_id}.json").exists()
        assert (archive_dir / f"{pkt.packet_id}.ack.json").exists()

    def test_archive_nonexistent_returns_false(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert archive_packet("nonexistent", tmp_path) is False


# ---------------------------------------------------------------------------
# Ack application (approve / edit / redirect / reject)
# ---------------------------------------------------------------------------


class TestApplyAck:
    """Test the apply_ack workflow for all four actions."""

    def test_approve_flow(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-a")
        save_packet(pkt, tmp_path)

        ack = create_ack(pkt.packet_id, "approve")
        result = apply_ack(ack, tmp_path)

        assert result is not None
        assert result.status == "approved"

        # Ack file should be persisted
        loaded_ack = load_ack(pkt.packet_id, tmp_path)
        assert loaded_ack is not None
        assert loaded_ack.action == "approve"

    def test_edit_flow(self, tmp_path: Path) -> None:
        pkt = create_packet("Original title", "d", owner="author-a")
        save_packet(pkt, tmp_path)

        ack = create_ack(
            pkt.packet_id,
            "edit",
            edited_fields={"title": "Edited title", "priority": "high"},
        )
        result = apply_ack(ack, tmp_path)

        assert result is not None
        assert result.status == "approved"
        assert result.title == "Edited title"
        assert result.priority == "high"

    def test_edit_cannot_change_protected_fields(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-a")
        save_packet(pkt, tmp_path)

        ack = create_ack(
            pkt.packet_id,
            "edit",
            edited_fields={"packet_id": "hacked", "created_at": "fake"},
        )
        result = apply_ack(ack, tmp_path)

        assert result is not None
        # Protected fields should NOT be changed
        assert result.packet_id == pkt.packet_id
        assert result.created_at == pkt.created_at

    def test_redirect_flow(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-a")
        save_packet(pkt, tmp_path)

        ack = create_ack(pkt.packet_id, "redirect", redirect_to="author-c")
        new_pkt = apply_ack(ack, tmp_path)

        assert new_pkt is not None
        assert new_pkt.owner == "author-c"
        assert new_pkt.packet_id != pkt.packet_id
        assert new_pkt.metadata.get("redirected_from") == pkt.packet_id

        # Original should be redirected
        original = load_packet(pkt.packet_id, tmp_path)
        assert original is not None
        assert original.status == "redirected"

    def test_reject_flow(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d")
        save_packet(pkt, tmp_path)

        ack = create_ack(pkt.packet_id, "reject")
        rejected = apply_ack(ack, tmp_path)

        # Return value should be the rejected packet (not None)
        assert rejected is not None
        assert rejected.status == "rejected"

        # After reject, packet is archived (not loadable from queue root)
        assert load_packet(pkt.packet_id, tmp_path) is None

        # Archived copy should exist
        archive_dir = tmp_path / "archive"
        assert (archive_dir / f"{pkt.packet_id}.json").exists()

    def test_apply_ack_nonexistent_packet(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        ack = create_ack("nonexistent", "approve")
        result = apply_ack(ack, tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Complete packet
# ---------------------------------------------------------------------------


class TestCompletePacket:
    """Test the complete_packet lifecycle."""

    def test_complete_and_archive(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-b")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)

        result = create_result(
            pkt.packet_id, "completed", "All tests pass", pr_number=42
        )
        complete_packet(result, tmp_path)

        # Packet is archived
        assert load_packet(pkt.packet_id, tmp_path) is None

        # Result sidecar exists in archive
        archive_dir = tmp_path / "archive"
        assert (archive_dir / f"{pkt.packet_id}.result.json").exists()

    def test_complete_with_failed_result(self, tmp_path: Path) -> None:
        """Failed result transitions packet to failed + archives with result sidecar."""
        pkt = create_packet("Task", "d", owner="author-a")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)

        result = create_result(pkt.packet_id, "failed", "Tests failed")
        final = complete_packet(result, tmp_path)

        # Packet transitioned to terminal 'failed' status (dispatched → failed
        # is a valid transition; see #2701 reconcile_dispatched_packets).
        assert final is not None
        assert final.status == "failed"

        # Packet is archived
        assert load_packet(pkt.packet_id, tmp_path) is None

        # Result sidecar in archive records the failure
        archive_dir = tmp_path / "archive"
        result_path = archive_dir / f"{pkt.packet_id}.result.json"
        assert result_path.exists()
        result_data = json.loads(result_path.read_text())
        assert result_data["status"] == "failed"

    def test_complete_with_blocked_result(self, tmp_path: Path) -> None:
        """Blocked result archives packet with dispatched status + result sidecar."""
        pkt = create_packet("Task", "d", owner="author-b")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)

        result = create_result(pkt.packet_id, "blocked", "Blocked by dependency")
        final = complete_packet(result, tmp_path)

        assert final is not None
        assert final.status == "dispatched"
        assert load_packet(pkt.packet_id, tmp_path) is None

    def test_complete_without_archive(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-a")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "approved", tmp_path)
        transition_status(pkt.packet_id, "dispatched", tmp_path)

        result = create_result(pkt.packet_id, "completed", "Done")
        complete_packet(result, tmp_path, archive=False)

        # Packet should still be in queue (not archived)
        loaded = load_packet(pkt.packet_id, tmp_path)
        assert loaded is not None
        assert loaded.status == "completed"


# ---------------------------------------------------------------------------
# Queue summary
# ---------------------------------------------------------------------------


class TestQueueSummary:
    """Test queue_summary for status enrichment."""

    def test_empty_queue_summary(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        summary = queue_summary(tmp_path)
        assert summary["total"] == 0
        assert summary["by_status"] == {}
        assert summary["by_owner"] == {}
        assert summary["packets"] == []

    def test_summary_with_packets(self, tmp_path: Path) -> None:
        save_packet(create_packet("T1", "d", owner="author-a"), tmp_path)
        save_packet(create_packet("T2", "d", owner="author-b"), tmp_path)
        pkt3 = create_packet("T3", "d", owner="author-a")
        save_packet(pkt3, tmp_path)
        # Valid transition: pending -> approved -> dispatched
        transition_status(pkt3.packet_id, "approved", tmp_path)
        transition_status(pkt3.packet_id, "dispatched", tmp_path)

        summary = queue_summary(tmp_path)
        assert summary["total"] == 3
        assert summary["by_status"]["pending"] == 2
        assert summary["by_status"]["dispatched"] == 1
        assert summary["by_owner"]["author-a"] == 2
        assert summary["by_owner"]["author-b"] == 1
        assert len(summary["packets"]) == 3

    def test_summary_unassigned_owner(self, tmp_path: Path) -> None:
        save_packet(create_packet("T1", "d"), tmp_path)  # No owner
        summary = queue_summary(tmp_path)
        assert summary["by_owner"]["(unassigned)"] == 1


# ---------------------------------------------------------------------------
# End-to-end smoke: create -> preview -> approve -> dispatch
# ---------------------------------------------------------------------------


class TestE2ESmoke:
    """End-to-end smoke test for the happy path."""

    def test_create_preview_approve_dispatch_complete(self, tmp_path: Path) -> None:
        # 1. Orchestrator creates a packet
        pkt = create_packet(
            "Fix scoring bug",
            "The low-contract scoring has an off-by-one error",
            owner="author-b",
            scope_declared=["src/bid_euchre/scoring.py"],
            validation=["uv run python -m pytest tests/unit/test_scoring.py"],
        )
        save_packet(pkt, tmp_path)
        assert pkt.status == "pending"

        # 2. Transition to previewing
        pkt = transition_status(pkt.packet_id, "previewing", tmp_path)
        assert pkt is not None
        assert pkt.status == "previewing"

        # 3. User approves
        ack = create_ack(pkt.packet_id, "approve")
        pkt = apply_ack(ack, tmp_path)
        assert pkt is not None
        assert pkt.status == "approved"

        # 4. Dispatch to author lane
        pkt = transition_status(pkt.packet_id, "dispatched", tmp_path)
        assert pkt is not None
        assert pkt.status == "dispatched"

        # 5. Author completes
        result = create_result(
            pkt.packet_id,
            "completed",
            "Fixed off-by-one in low-contract scoring",
            pr_number=1234,
            completed_by="author-b",
        )
        complete_packet(result, tmp_path)

        # 6. Verify archived
        assert load_packet(pkt.packet_id, tmp_path) is None
        summary = queue_summary(tmp_path)
        assert summary["total"] == 0

    def test_edit_then_dispatch(self, tmp_path: Path) -> None:
        """Unhappy path: user edits the packet before approval."""
        pkt = create_packet("Wrong title", "d", owner="author-a")
        save_packet(pkt, tmp_path)
        transition_status(pkt.packet_id, "previewing", tmp_path)

        # User edits title and redirects to different lane
        ack = create_ack(
            pkt.packet_id,
            "edit",
            edited_fields={"title": "Correct title", "owner": "author-b"},
        )
        edited = apply_ack(ack, tmp_path)
        assert edited is not None
        assert edited.title == "Correct title"
        assert edited.owner == "author-b"
        assert edited.status == "approved"


# ---------------------------------------------------------------------------
# update_packet_metadata
# ---------------------------------------------------------------------------


class TestUpdatePacketMetadata:
    """Test metadata update without status change."""

    def test_updates_metadata_fields(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-a")
        save_packet(pkt, tmp_path)

        updated = update_packet_metadata(pkt.packet_id, {"pr_number": 42}, tmp_path)
        assert updated is not None
        assert updated.metadata["pr_number"] == 42
        assert updated.status == pkt.status  # Status unchanged

    def test_merges_with_existing_metadata(self, tmp_path: Path) -> None:
        pkt = create_packet(
            "Task", "d", owner="author-a", metadata={"dispatched_at": "2026-01-01"}
        )
        save_packet(pkt, tmp_path)

        updated = update_packet_metadata(pkt.packet_id, {"pr_number": 99}, tmp_path)
        assert updated is not None
        assert updated.metadata["pr_number"] == 99
        assert updated.metadata["dispatched_at"] == "2026-01-01"

    def test_overwrites_existing_key(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-a", metadata={"pr_number": 1})
        save_packet(pkt, tmp_path)

        updated = update_packet_metadata(pkt.packet_id, {"pr_number": 2}, tmp_path)
        assert updated is not None
        assert updated.metadata["pr_number"] == 2

    def test_nonexistent_packet_returns_none(self, tmp_path: Path) -> None:
        shared_task_root(tmp_path)
        assert update_packet_metadata("nonexistent", {"key": "val"}, tmp_path) is None

    def test_persists_to_disk(self, tmp_path: Path) -> None:
        pkt = create_packet("Task", "d", owner="author-b")
        save_packet(pkt, tmp_path)
        update_packet_metadata(pkt.packet_id, {"pr_number": 55}, tmp_path)

        reloaded = load_packet(pkt.packet_id, tmp_path)
        assert reloaded is not None
        assert reloaded.metadata["pr_number"] == 55


# ---------------------------------------------------------------------------
# Routing metadata (issue #2169 Slice C)
# ---------------------------------------------------------------------------


class TestRoutingMetadataConstants:
    """Verify the routing metadata contract constants are stable."""

    def test_routing_keys_frozenset(self) -> None:
        from bid_euchre.ops.task_queue import ROUTING_METADATA_KEYS

        assert ROUTING_METADATA_KEYS == frozenset(
            {"task_type", "complexity_estimate", "model_hint", "effort_hint"}
        )

    def test_task_type_taxonomy_non_empty(self) -> None:
        from bid_euchre.ops.task_queue import VALID_TASK_TYPES

        # These are the values downstream callers rely on; adding values is
        # fine (advisory-only), but removing any would silently break
        # outcome rollups. Lock the current set.
        required = {"docs", "tests", "feature", "bugfix", "ops", "review"}
        assert required.issubset(VALID_TASK_TYPES)

    def test_model_hints_known(self) -> None:
        from bid_euchre.ops.task_queue import VALID_MODEL_HINTS

        assert "opus" in VALID_MODEL_HINTS
        assert "sonnet" in VALID_MODEL_HINTS

    def test_effort_hints(self) -> None:
        from bid_euchre.ops.task_queue import VALID_EFFORT_HINTS

        # "max" added by Primitive B-exec.α (B.10 effort policy) so packets
        # can carry the `max → max` tier verbatim. See
        # `.claude/rules/effort_policy.md` §"Tier vocabulary" for the mapping.
        assert VALID_EFFORT_HINTS == frozenset({"low", "medium", "high", "max"})

    def test_complexity_range_bounds(self) -> None:
        from bid_euchre.ops.task_queue import MAX_COMPLEXITY, MIN_COMPLEXITY

        assert MIN_COMPLEXITY == 1
        assert MAX_COMPLEXITY == 5


class TestRoutingMetadataAccessors:
    """Verify accessors return correctly-typed values or None."""

    def test_get_task_type_present(self) -> None:
        from bid_euchre.ops.task_queue import get_task_type

        pkt = create_packet("t", "d", metadata={"task_type": "docs"})
        assert get_task_type(pkt) == "docs"

    def test_get_task_type_absent(self) -> None:
        from bid_euchre.ops.task_queue import get_task_type

        pkt = create_packet("t", "d")
        assert get_task_type(pkt) is None

    def test_get_task_type_wrong_type_returns_none(self) -> None:
        from bid_euchre.ops.task_queue import get_task_type

        # Legacy packets may contain non-string values — accessor
        # must silently ignore them rather than raising.
        pkt = create_packet("t", "d", metadata={"task_type": 42})
        assert get_task_type(pkt) is None

    def test_get_complexity_in_range(self) -> None:
        from bid_euchre.ops.task_queue import get_complexity

        pkt = create_packet("t", "d", metadata={"complexity_estimate": 3})
        assert get_complexity(pkt) == 3

    def test_get_complexity_out_of_range_returns_none(self) -> None:
        from bid_euchre.ops.task_queue import get_complexity

        pkt = create_packet("t", "d", metadata={"complexity_estimate": 99})
        assert get_complexity(pkt) is None

    def test_get_complexity_rejects_bool(self) -> None:
        from bid_euchre.ops.task_queue import get_complexity

        # bool is an int subclass — accessor must reject it so ``True``
        # doesn't silently masquerade as complexity 1.
        pkt = create_packet("t", "d", metadata={"complexity_estimate": True})
        assert get_complexity(pkt) is None

    def test_get_model_hint(self) -> None:
        from bid_euchre.ops.task_queue import get_model_hint

        pkt = create_packet("t", "d", metadata={"model_hint": "sonnet"})
        assert get_model_hint(pkt) == "sonnet"

    def test_get_effort_hint(self) -> None:
        from bid_euchre.ops.task_queue import get_effort_hint

        pkt = create_packet("t", "d", metadata={"effort_hint": "low"})
        assert get_effort_hint(pkt) == "low"


class TestValidateRoutingMetadata:
    """validate_routing_metadata() classifies errors vs warnings correctly."""

    def test_empty_metadata_is_clean(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, warnings = validate_routing_metadata({})
        assert errors == []
        assert warnings == []

    def test_known_values_clean(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, warnings = validate_routing_metadata(
            {
                "task_type": "docs",
                "complexity_estimate": 2,
                "model_hint": "sonnet",
                "effort_hint": "low",
            }
        )
        assert errors == []
        assert warnings == []

    def test_unknown_task_type_is_warning_not_error(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, warnings = validate_routing_metadata({"task_type": "novel_work"})
        assert errors == []
        assert any("novel_work" in w for w in warnings)

    def test_unknown_model_hint_is_warning(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, warnings = validate_routing_metadata({"model_hint": "gpt-5"})
        assert errors == []
        assert any("gpt-5" in w for w in warnings)

    def test_complexity_out_of_range_is_error(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, _ = validate_routing_metadata({"complexity_estimate": 7})
        assert any("complexity_estimate" in e for e in errors)

    def test_complexity_wrong_type_is_error(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, _ = validate_routing_metadata({"complexity_estimate": "high"})
        assert any("complexity_estimate" in e for e in errors)

    def test_complexity_bool_is_error(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        # bool is an int subclass — reject True/False explicitly so it
        # cannot be smuggled through as complexity 1 / 0.
        errors, _ = validate_routing_metadata({"complexity_estimate": True})
        assert any("complexity_estimate" in e for e in errors)

    def test_task_type_wrong_type_is_error(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        errors, _ = validate_routing_metadata({"task_type": 42})
        assert any("task_type" in e for e in errors)

    def test_effort_hint_unknown_is_error(self) -> None:
        from bid_euchre.ops.task_queue import validate_routing_metadata

        # effort_hint is a tightly-bounded enum (not taxonomy-evolving),
        # so unknowns are errors, not warnings.
        errors, _ = validate_routing_metadata({"effort_hint": "yolo"})
        assert any("effort_hint" in e for e in errors)
