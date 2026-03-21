"""Tests for the Platform-3 communication bus module.

Covers: BusMessage creation/validation, JSONL audit trail round-trip,
per-lane inbox read/write, send/ack/resolve delivery semantics,
TTL expiry, dead-letter handling, duplicate suppression, inbox stats,
and shared root resolution.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.ops.message_bus import (
    DEFAULT_MAX_RETRIES,
    VALID_MESSAGE_PRIORITIES,
    VALID_MESSAGE_STATUSES,
    VALID_MESSAGE_TRANSITIONS,
    VALID_MESSAGE_TYPES,
    BusMessage,
    ack_message,
    append_message,
    check_dead_letters,
    check_expired,
    create_message,
    inbox_stats,
    query_unresolved,
    read_inbox,
    read_messages,
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
# BusMessage creation and validation
# ---------------------------------------------------------------------------


class TestBusMessageCreation:
    """Test BusMessage creation and field validation."""

    def test_create_message_defaults(self) -> None:
        msg = create_message(
            "orchestrator", "author-a", "assignment", "Fix the scoring bug"
        )
        assert msg.from_lane == "orchestrator"
        assert msg.to_lane == "author-a"
        assert msg.message_type == "assignment"
        assert msg.summary == "Fix the scoring bug"
        assert msg.status == "pending"
        assert msg.priority == "normal"
        assert msg.requires_human is False
        assert msg.source_transport == "bus"
        assert msg.acked_at is None
        assert msg.resolved_at is None
        assert msg.thread_id is None
        assert msg.task_id is None
        assert msg.parent_message_id is None
        assert len(msg.message_id) == 16
        assert msg.created_at  # Non-empty

    def test_create_message_with_all_fields(self) -> None:
        msg = create_message(
            "author-a",
            "review",
            "completion",
            "PR #42 ready for review",
            thread_id="thread-001",
            task_id="pkt-abc123",
            priority="high",
            requires_human=True,
            payload={"pr_number": 42},
            source_transport="hook",
            parent_message_id="parent-msg-001",
        )
        assert msg.thread_id == "thread-001"
        assert msg.task_id == "pkt-abc123"
        assert msg.priority == "high"
        assert msg.requires_human is True
        assert msg.source_transport == "hook"
        assert msg.parent_message_id == "parent-msg-001"
        assert msg.payload["pr_number"] == 42
        # Delivery policy defaults injected
        assert msg.payload["max_retries"] == DEFAULT_MAX_RETRIES
        assert msg.payload["retry_count"] == 0

    def test_invalid_message_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid message_type"):
            BusMessage(
                message_id="test",
                thread_id=None,
                task_id=None,
                from_lane="a",
                to_lane="b",
                message_type="invalid_type",
                priority="normal",
                status="pending",
                created_at="2026-01-01T00:00:00Z",
                acked_at=None,
                resolved_at=None,
                requires_human=False,
                summary="test",
            )

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid priority"):
            BusMessage(
                message_id="test",
                thread_id=None,
                task_id=None,
                from_lane="a",
                to_lane="b",
                message_type="assignment",
                priority="critical",
                status="pending",
                created_at="2026-01-01T00:00:00Z",
                acked_at=None,
                resolved_at=None,
                requires_human=False,
                summary="test",
            )

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            BusMessage(
                message_id="test",
                thread_id=None,
                task_id=None,
                from_lane="a",
                to_lane="b",
                message_type="assignment",
                priority="normal",
                status="invalid_status",
                created_at="2026-01-01T00:00:00Z",
                acked_at=None,
                resolved_at=None,
                requires_human=False,
                summary="test",
            )

    def test_all_valid_message_types(self) -> None:
        for mtype in VALID_MESSAGE_TYPES:
            msg = create_message("a", "b", mtype, "test")
            assert msg.message_type == mtype

    def test_all_valid_priorities(self) -> None:
        for p in VALID_MESSAGE_PRIORITIES:
            msg = create_message("a", "b", "assignment", "test", priority=p)
            assert msg.priority == p

    def test_all_valid_statuses(self) -> None:
        for s in VALID_MESSAGE_STATUSES:
            msg = BusMessage(
                message_id="test",
                thread_id=None,
                task_id=None,
                from_lane="a",
                to_lane="b",
                message_type="assignment",
                priority="normal",
                status=s,
                created_at="2026-01-01T00:00:00Z",
                acked_at=None,
                resolved_at=None,
                requires_human=False,
                summary="test",
            )
            assert msg.status == s

    def test_frozen_immutability(self) -> None:
        msg = create_message("a", "b", "assignment", "test")
        with pytest.raises(AttributeError):
            msg.status = "acked"  # type: ignore[misc]

    def test_delivery_policy_defaults_in_payload(self) -> None:
        msg = create_message("a", "b", "assignment", "test")
        assert msg.payload["max_retries"] == DEFAULT_MAX_RETRIES
        assert msg.payload["retry_count"] == 0
        assert msg.payload["ttl_seconds"] is None

    def test_custom_delivery_policy_preserved(self) -> None:
        msg = create_message(
            "a",
            "b",
            "assignment",
            "test",
            payload={"max_retries": 5, "ttl_seconds": 600},
        )
        assert msg.payload["max_retries"] == 5
        assert msg.payload["ttl_seconds"] == 600
        assert msg.payload["retry_count"] == 0


# ---------------------------------------------------------------------------
# Shared bus root
# ---------------------------------------------------------------------------


class TestSharedBusRoot:
    """Test shared_bus_root directory creation."""

    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        root = shared_bus_root(tmp_path / "bus")
        assert root.exists()
        assert (root / "inbox").exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        root1 = shared_bus_root(tmp_path / "bus")
        root2 = shared_bus_root(tmp_path / "bus")
        assert root1 == root2

    def test_env_override(self, tmp_path: Path) -> None:
        env_dir = tmp_path / "env_bus"
        with patch.dict("os.environ", {"BID_EUCHRE_BUS_DIR": str(env_dir)}):
            # Clear LRU cache to pick up env var
            from bid_euchre.ops.message_bus import _resolve_git_common_bus_root

            _resolve_git_common_bus_root.cache_clear()
            root = shared_bus_root()
            assert root == env_dir
            assert root.exists()


# ---------------------------------------------------------------------------
# JSONL audit trail
# ---------------------------------------------------------------------------


class TestAuditTrail:
    """Test append-only JSONL audit trail."""

    def test_append_and_read(self, bus_root: Path) -> None:
        msg = create_message("orchestrator", "author-a", "assignment", "Do task")
        append_message(msg, bus_root)

        records = read_messages(bus_root)
        assert len(records) == 1
        assert records[0]["message_id"] == msg.message_id
        assert records[0]["summary"] == "Do task"

    def test_read_empty_trail(self, bus_root: Path) -> None:
        assert read_messages(bus_root) == []

    def test_multiple_messages_most_recent_first(self, bus_root: Path) -> None:
        msg1 = create_message("a", "b", "assignment", "First")
        msg2 = create_message("c", "d", "progress", "Second")
        append_message(msg1, bus_root)
        append_message(msg2, bus_root)

        records = read_messages(bus_root)
        assert len(records) == 2
        # Most recent first
        assert records[0]["summary"] == "Second"
        assert records[1]["summary"] == "First"

    def test_filter_by_from_lane(self, bus_root: Path) -> None:
        append_message(
            create_message("orchestrator", "author-a", "assignment", "A"), bus_root
        )
        append_message(
            create_message("author-a", "review", "completion", "B"), bus_root
        )

        records = read_messages(bus_root, from_lane="orchestrator")
        assert len(records) == 1
        assert records[0]["summary"] == "A"

    def test_filter_by_to_lane(self, bus_root: Path) -> None:
        append_message(
            create_message("orchestrator", "author-a", "assignment", "A"), bus_root
        )
        append_message(
            create_message("orchestrator", "author-b", "assignment", "B"), bus_root
        )

        records = read_messages(bus_root, to_lane="author-b")
        assert len(records) == 1
        assert records[0]["summary"] == "B"

    def test_filter_by_thread_id(self, bus_root: Path) -> None:
        append_message(
            create_message("a", "b", "assignment", "T1", thread_id="thread-1"),
            bus_root,
        )
        append_message(
            create_message("a", "b", "progress", "T2", thread_id="thread-2"),
            bus_root,
        )

        records = read_messages(bus_root, thread_id="thread-1")
        assert len(records) == 1
        assert records[0]["summary"] == "T1"

    def test_filter_by_message_type(self, bus_root: Path) -> None:
        append_message(create_message("a", "b", "assignment", "A"), bus_root)
        append_message(create_message("a", "b", "blocker", "B"), bus_root)

        records = read_messages(bus_root, message_type="blocker")
        assert len(records) == 1
        assert records[0]["summary"] == "B"

    def test_filter_by_since(self, bus_root: Path) -> None:
        msg = create_message("a", "b", "assignment", "Old")
        append_message(msg, bus_root)

        # Filter after creation time should exclude it
        future = datetime(2099, 1, 1, tzinfo=timezone.utc)
        records = read_messages(bus_root, since=future)
        assert len(records) == 0

    def test_limit_respected(self, bus_root: Path) -> None:
        for i in range(10):
            append_message(create_message("a", "b", "progress", f"Msg {i}"), bus_root)

        records = read_messages(bus_root, limit=3)
        assert len(records) == 3

    def test_malformed_lines_skipped(self, bus_root: Path) -> None:
        """Malformed JSONL lines are skipped gracefully."""
        audit_path = bus_root / "messages.jsonl"
        audit_path.write_text("not valid json\n")
        append_message(create_message("a", "b", "assignment", "Valid"), bus_root)

        records = read_messages(bus_root)
        assert len(records) == 1
        assert records[0]["summary"] == "Valid"


# ---------------------------------------------------------------------------
# Per-lane inbox
# ---------------------------------------------------------------------------


class TestInbox:
    """Test per-lane inbox read/write."""

    def test_read_empty_inbox(self, bus_root: Path) -> None:
        assert read_inbox("nonexistent-lane", bus_root) == []

    def test_send_populates_inbox(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message("orchestrator", "author-a", "assignment", "Task 1")
        send_message(msg, bus_root, events_dir=events_dir)

        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["message_id"] == msg.message_id
        assert inbox[0]["summary"] == "Task 1"

    def test_inbox_deduplicates_by_message_id(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """When a message status is updated, the latest record wins."""
        msg = create_message("orchestrator", "author-a", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)

        # Ack updates the inbox with a new record
        ack_message(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "acked"

    def test_inbox_filter_by_status(self, bus_root: Path, events_dir: Path) -> None:
        msg1 = create_message("a", "target", "assignment", "Pending one")
        msg2 = create_message("a", "target", "progress", "Will be acked")
        send_message(msg1, bus_root, events_dir=events_dir)
        send_message(msg2, bus_root, events_dir=events_dir)
        ack_message(msg2.message_id, "target", bus_root, events_dir=events_dir)

        pending = read_inbox("target", bus_root, status="pending")
        assert len(pending) == 1
        assert pending[0]["summary"] == "Pending one"

        acked = read_inbox("target", bus_root, status="acked")
        assert len(acked) == 1
        assert acked[0]["summary"] == "Will be acked"

    def test_inbox_filter_by_thread(self, bus_root: Path, events_dir: Path) -> None:
        msg1 = create_message("a", "b", "assignment", "Thread A", thread_id="ta")
        msg2 = create_message("a", "b", "assignment", "Thread B", thread_id="tb")
        send_message(msg1, bus_root, events_dir=events_dir)
        send_message(msg2, bus_root, events_dir=events_dir)

        result = read_inbox("b", bus_root, thread_id="ta")
        assert len(result) == 1
        assert result[0]["thread_id"] == "ta"

    def test_inbox_filter_by_message_type(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg1 = create_message("a", "b", "assignment", "Assign")
        msg2 = create_message("a", "b", "blocker", "Block")
        send_message(msg1, bus_root, events_dir=events_dir)
        send_message(msg2, bus_root, events_dir=events_dir)

        result = read_inbox("b", bus_root, message_type="blocker")
        assert len(result) == 1
        assert result[0]["message_type"] == "blocker"

    def test_query_unresolved(self, bus_root: Path, events_dir: Path) -> None:
        msg1 = create_message("a", "target", "assignment", "Active")
        msg2 = create_message("a", "target", "progress", "Will resolve")
        send_message(msg1, bus_root, events_dir=events_dir)
        send_message(msg2, bus_root, events_dir=events_dir)

        # Ack and resolve msg2
        ack_message(msg2.message_id, "target", bus_root, events_dir=events_dir)
        resolve_message(msg2.message_id, "target", bus_root)

        unresolved = query_unresolved("target", bus_root)
        assert len(unresolved) == 1
        assert unresolved[0]["message_id"] == msg1.message_id


# ---------------------------------------------------------------------------
# Delivery semantics: send
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Test send_message delivery semantics."""

    def test_send_writes_audit_trail_and_inbox(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg = create_message("orchestrator", "author-a", "assignment", "Work")
        mid = send_message(msg, bus_root, events_dir=events_dir)
        assert mid == msg.message_id

        # Audit trail
        trail = read_messages(bus_root)
        assert len(trail) == 1
        assert trail[0]["message_id"] == mid

        # Inbox
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["message_id"] == mid

    def test_send_emits_event(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message("orchestrator", "author-a", "assignment", "Work")
        send_message(msg, bus_root, events_dir=events_dir)

        events_file = events_dir / "events.jsonl"
        assert events_file.exists()
        lines = events_file.read_text().strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event_type"] == "message_sent"
        assert event["payload"]["message_id"] == msg.message_id

    def test_duplicate_suppression(self, bus_root: Path, events_dir: Path) -> None:
        """Sending the same message_id twice raises ValueError."""
        msg = create_message("a", "b", "assignment", "Original")
        send_message(msg, bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Duplicate message_id"):
            send_message(msg, bus_root, events_dir=events_dir)


# ---------------------------------------------------------------------------
# Delivery semantics: ack
# ---------------------------------------------------------------------------


class TestAckMessage:
    """Test ack_message delivery semantics."""

    def test_ack_updates_inbox(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)

        result = ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)
        assert result is not None
        assert result["status"] == "acked"
        assert result["acked_at"] is not None

    def test_ack_emits_event(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)

        events_file = events_dir / "events.jsonl"
        lines = events_file.read_text().strip().split("\n")
        assert len(lines) == 2  # message_sent + message_acked
        ack_event = json.loads(lines[1])
        assert ack_event["event_type"] == "message_acked"

    def test_ack_nonexistent_returns_none(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        result = ack_message(
            "nonexistent", "some-lane", bus_root, events_dir=events_dir
        )
        assert result is None

    def test_ack_already_acked_raises(self, bus_root: Path, events_dir: Path) -> None:
        """Acking an already-acked message raises (acked -> acked not valid)."""
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)


# ---------------------------------------------------------------------------
# Delivery semantics: resolve
# ---------------------------------------------------------------------------


class TestResolveMessage:
    """Test resolve_message delivery semantics."""

    def test_resolve_after_ack(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)

        result = resolve_message(msg.message_id, "b", bus_root)
        assert result is not None
        assert result["status"] == "resolved"
        assert result["resolved_at"] is not None

    def test_resolve_without_ack_raises(self, bus_root: Path, events_dir: Path) -> None:
        """Cannot resolve a pending message (must ack first)."""
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            resolve_message(msg.message_id, "b", bus_root)

    def test_resolve_already_resolved_raises(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)
        resolve_message(msg.message_id, "b", bus_root)

        with pytest.raises(ValueError, match="Invalid transition"):
            resolve_message(msg.message_id, "b", bus_root)


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


class TestCheckExpired:
    """Test TTL expiry detection."""

    def test_expired_message_detected(self, bus_root: Path, events_dir: Path) -> None:
        """A message with ttl_seconds in the past is marked expired."""
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Urgent task",
            payload={"ttl_seconds": 60},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # Simulate time passing well beyond TTL
        future_time = time.time() + 3600  # 1 hour later
        expired = check_expired(bus_root, events_dir=events_dir, now=future_time)
        assert len(expired) == 1
        assert expired[0]["message_id"] == msg.message_id
        assert expired[0]["status"] == "expired"

    def test_non_expired_message_not_detected(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """A message within its TTL is not expired."""
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Patient task",
            payload={"ttl_seconds": 86400},  # 24 hours
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # Check immediately (well within TTL)
        expired = check_expired(bus_root, events_dir=events_dir, now=time.time())
        assert len(expired) == 0

    def test_no_ttl_never_expires(self, bus_root: Path, events_dir: Path) -> None:
        """Messages without ttl_seconds never expire."""
        msg = create_message("a", "b", "assignment", "Forever task")
        send_message(msg, bus_root, events_dir=events_dir)

        far_future = time.time() + 365 * 24 * 3600  # 1 year
        expired = check_expired(bus_root, events_dir=events_dir, now=far_future)
        assert len(expired) == 0

    def test_expired_emits_event(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message(
            "a", "b", "assignment", "Short-lived", payload={"ttl_seconds": 1}
        )
        send_message(msg, bus_root, events_dir=events_dir)

        check_expired(bus_root, events_dir=events_dir, now=time.time() + 100)

        events_file = events_dir / "events.jsonl"
        lines = events_file.read_text().strip().split("\n")
        expired_events = [
            json.loads(l)
            for l in lines
            if json.loads(l)["event_type"] == "message_expired"
        ]
        assert len(expired_events) == 1

    def test_already_expired_not_re_expired(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Running check_expired twice doesn't double-expire."""
        msg = create_message(
            "a", "b", "assignment", "One-time", payload={"ttl_seconds": 1}
        )
        send_message(msg, bus_root, events_dir=events_dir)

        future = time.time() + 100
        expired1 = check_expired(bus_root, events_dir=events_dir, now=future)
        assert len(expired1) == 1

        expired2 = check_expired(bus_root, events_dir=events_dir, now=future + 100)
        assert len(expired2) == 0  # Already expired, skip


# ---------------------------------------------------------------------------
# Dead-letter handling
# ---------------------------------------------------------------------------


class TestCheckDeadLetters:
    """Test dead-letter detection when max_retries exceeded."""

    def test_dead_letter_on_max_retries(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Failing task",
            payload={"max_retries": 2, "retry_count": 3},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        dead = check_dead_letters(bus_root, events_dir=events_dir)
        assert len(dead) == 1
        assert dead[0]["message_id"] == msg.message_id
        assert dead[0]["status"] == "dead_lettered"

    def test_no_dead_letter_within_retries(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Still trying",
            payload={"max_retries": 5, "retry_count": 2},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        dead = check_dead_letters(bus_root, events_dir=events_dir)
        assert len(dead) == 0

    def test_dead_letter_emits_event(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Exhausted",
            payload={"max_retries": 1, "retry_count": 5},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        check_dead_letters(bus_root, events_dir=events_dir)

        events_file = events_dir / "events.jsonl"
        lines = events_file.read_text().strip().split("\n")
        dl_events = [
            json.loads(l)
            for l in lines
            if json.loads(l)["event_type"] == "message_dead_lettered"
        ]
        assert len(dl_events) == 1

    def test_already_dead_lettered_not_re_processed(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Done",
            payload={"max_retries": 1, "retry_count": 5},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        dead1 = check_dead_letters(bus_root, events_dir=events_dir)
        assert len(dead1) == 1

        dead2 = check_dead_letters(bus_root, events_dir=events_dir)
        assert len(dead2) == 0  # Already processed


# ---------------------------------------------------------------------------
# Transition map integrity
# ---------------------------------------------------------------------------


class TestTransitionMap:
    """Test the message status transition map for consistency."""

    def test_all_statuses_have_transitions(self) -> None:
        assert set(VALID_MESSAGE_TRANSITIONS.keys()) == VALID_MESSAGE_STATUSES

    def test_all_targets_are_valid_statuses(self) -> None:
        for source, targets in VALID_MESSAGE_TRANSITIONS.items():
            for target in targets:
                assert (
                    target in VALID_MESSAGE_STATUSES
                ), f"Transition {source!r} -> {target!r}: target not a valid status"

    def test_terminal_states_have_no_transitions(self) -> None:
        for terminal in ("resolved", "expired", "dead_lettered"):
            assert VALID_MESSAGE_TRANSITIONS[terminal] == frozenset(), (
                f"{terminal!r} should be terminal but allows: "
                f"{VALID_MESSAGE_TRANSITIONS[terminal]}"
            )


# ---------------------------------------------------------------------------
# Inbox stats
# ---------------------------------------------------------------------------


class TestInboxStats:
    """Test inbox_stats summary."""

    def test_empty_stats(self, bus_root: Path) -> None:
        stats = inbox_stats(bus_root)
        assert stats["lanes"] == []

    def test_stats_with_messages(self, bus_root: Path, events_dir: Path) -> None:
        send_message(
            create_message("a", "author-a", "assignment", "M1"),
            bus_root,
            events_dir=events_dir,
        )
        send_message(
            create_message("a", "author-a", "progress", "M2"),
            bus_root,
            events_dir=events_dir,
        )
        send_message(
            create_message("a", "author-b", "assignment", "M3"),
            bus_root,
            events_dir=events_dir,
        )

        stats = inbox_stats(bus_root)
        lanes = {ln["lane_id"]: ln for ln in stats["lanes"]}
        assert "author-a" in lanes
        assert "author-b" in lanes
        assert lanes["author-a"]["total"] == 2
        assert lanes["author-b"]["total"] == 1


# ---------------------------------------------------------------------------
# End-to-end smoke: full message lifecycle
# ---------------------------------------------------------------------------


class TestE2ESmoke:
    """End-to-end smoke test for the happy path."""

    def test_send_ack_resolve_lifecycle(self, bus_root: Path, events_dir: Path) -> None:
        # 1. Orchestrator sends assignment
        msg = create_message(
            "orchestrator",
            "author-a",
            "assignment",
            "Fix scoring bug",
            thread_id="task-thread-001",
            task_id="pkt-abc123",
        )
        mid = send_message(msg, bus_root, events_dir=events_dir)

        # 2. Author-a sees it in inbox
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "pending"

        # 3. Author-a acknowledges
        ack_result = ack_message(mid, "author-a", bus_root, events_dir=events_dir)
        assert ack_result is not None
        assert ack_result["status"] == "acked"

        # 4. Inbox now shows acked
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "acked"

        # 5. Query unresolved still returns it (acked is not terminal)
        unresolved = query_unresolved("author-a", bus_root)
        assert len(unresolved) == 1

        # 6. Author-a resolves (work done)
        resolve_result = resolve_message(mid, "author-a", bus_root)
        assert resolve_result is not None
        assert resolve_result["status"] == "resolved"

        # 7. No more unresolved
        unresolved = query_unresolved("author-a", bus_root)
        assert len(unresolved) == 0

        # 8. Audit trail has the original message
        trail = read_messages(bus_root)
        assert len(trail) == 1
        assert trail[0]["task_id"] == "pkt-abc123"

    def test_multi_lane_thread(self, bus_root: Path, events_dir: Path) -> None:
        """Multiple messages in the same thread across lanes."""
        thread = "task-42"

        # Orchestrator -> author-a
        m1 = create_message(
            "orchestrator",
            "author-a",
            "assignment",
            "Start task",
            thread_id=thread,
            task_id="pkt42",
        )
        send_message(m1, bus_root, events_dir=events_dir)

        # Author-a -> orchestrator (progress)
        m2 = create_message(
            "author-a",
            "orchestrator",
            "progress",
            "50% done",
            thread_id=thread,
            task_id="pkt42",
            parent_message_id=m1.message_id,
        )
        send_message(m2, bus_root, events_dir=events_dir)

        # Author-a -> orchestrator (completion)
        m3 = create_message(
            "author-a",
            "orchestrator",
            "completion",
            "PR #99 ready",
            thread_id=thread,
            task_id="pkt42",
            parent_message_id=m2.message_id,
        )
        send_message(m3, bus_root, events_dir=events_dir)

        # Thread query on audit trail
        thread_msgs = read_messages(bus_root, thread_id=thread)
        assert len(thread_msgs) == 3

        # Each lane's inbox has the right messages
        assert len(read_inbox("author-a", bus_root)) == 1
        assert len(read_inbox("orchestrator", bus_root)) == 2
