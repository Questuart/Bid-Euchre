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
    AUTO_COMPACT_RAW_THRESHOLD,
    COMPACT_HANDLED_MAX_AGE_HOURS,
    COMPACT_TERMINAL_MAX_AGE_HOURS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TTL_SECONDS,
    VALID_MESSAGE_PRIORITIES,
    VALID_MESSAGE_STATUSES,
    VALID_MESSAGE_TRANSITIONS,
    VALID_MESSAGE_TYPES,
    BusMessage,
    _content_dedup_key,
    _find_content_duplicate,
    _native_content_hash,
    _tiered_cutoff,
    ack_message,
    append_message,
    bulk_ack_messages,
    check_dead_letters,
    check_expired,
    compact_all_inboxes,
    compact_inbox,
    create_message,
    import_native_inbox,
    inbox_stats,
    mark_delivered,
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
        assert msg.payload["ttl_seconds"] == DEFAULT_TTL_SECONDS

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

    def test_create_message_does_not_mutate_caller_payload(self) -> None:
        """Regression test for #1227: create_message must not mutate the caller's dict."""
        caller_payload = {"pr_number": 42}
        original_keys = set(caller_payload.keys())

        create_message("a", "b", "assignment", "test", payload=caller_payload)

        # Caller's dict must be unchanged — no delivery policy keys injected
        assert set(caller_payload.keys()) == original_keys
        assert "max_retries" not in caller_payload
        assert "retry_count" not in caller_payload
        assert "ttl_seconds" not in caller_payload


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
# Delivery semantics: mark_delivered
# ---------------------------------------------------------------------------


class TestMarkDelivered:
    """Test mark_delivered public API."""

    def test_mark_delivered_updates_inbox(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg = create_message("orchestrator", "author-a", "assignment", "Work")
        send_message(msg, bus_root, events_dir=events_dir)

        result = mark_delivered(
            msg.message_id, "author-a", bus_root, events_dir=events_dir
        )
        assert result is not None
        assert result["status"] == "delivered"

    def test_mark_delivered_emits_event(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message("orchestrator", "author-a", "assignment", "Work")
        send_message(msg, bus_root, events_dir=events_dir)
        mark_delivered(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        events_file = events_dir / "events.jsonl"
        lines = events_file.read_text().strip().split("\n")
        delivered_events = [
            json.loads(line)
            for line in lines
            if json.loads(line)["event_type"] == "message_delivered"
        ]
        assert len(delivered_events) == 1
        assert delivered_events[0]["payload"]["message_id"] == msg.message_id

    def test_mark_delivered_nonexistent_returns_none(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        result = mark_delivered(
            "nonexistent", "some-lane", bus_root, events_dir=events_dir
        )
        assert result is None

    def test_mark_delivered_already_delivered_raises(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Delivering an already-delivered message raises (delivered -> delivered not valid)."""
        msg = create_message("orchestrator", "author-a", "assignment", "Work")
        send_message(msg, bus_root, events_dir=events_dir)
        mark_delivered(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            mark_delivered(msg.message_id, "author-a", bus_root, events_dir=events_dir)

    def test_mark_delivered_then_ack(self, bus_root: Path, events_dir: Path) -> None:
        """A delivered message can be acked (delivered -> acked is valid)."""
        msg = create_message("orchestrator", "author-a", "assignment", "Work")
        send_message(msg, bus_root, events_dir=events_dir)
        mark_delivered(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        result = ack_message(
            msg.message_id, "author-a", bus_root, events_dir=events_dir
        )
        assert result is not None
        assert result["status"] == "acked"


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

        result = resolve_message(msg.message_id, "b", bus_root, events_dir=events_dir)
        assert result is not None
        assert result["status"] == "resolved"
        assert result["resolved_at"] is not None

    def test_resolve_emits_event(self, bus_root: Path, events_dir: Path) -> None:
        """Regression test for #1228: resolve_message must emit message_resolved."""
        msg = create_message("a", "b", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "b", bus_root, events_dir=events_dir)
        resolve_message(msg.message_id, "b", bus_root, events_dir=events_dir)

        events_file = events_dir / "events.jsonl"
        lines = events_file.read_text().strip().split("\n")
        # Expect: message_sent, message_acked, message_resolved
        assert len(lines) == 3
        resolve_event = json.loads(lines[2])
        assert resolve_event["event_type"] == "message_resolved"
        assert resolve_event["payload"]["message_id"] == msg.message_id

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
        resolve_message(msg.message_id, "b", bus_root, events_dir=events_dir)

        with pytest.raises(ValueError, match="Invalid transition"):
            resolve_message(msg.message_id, "b", bus_root, events_dir=events_dir)


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
        """Messages with ttl_seconds=None never expire."""
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Forever task",
            payload={"ttl_seconds": None},
        )
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

    def test_zero_now_is_preserved(self, bus_root: Path, events_dir: Path) -> None:
        """now=0.0 is a valid override and must not fall through to time.time()."""
        msg = create_message(
            "a",
            "b",
            "assignment",
            "Epoch task",
            payload={"ttl_seconds": 60},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # With now=0.0 (epoch), the message was created "in the future" relative
        # to epoch, so nothing should expire.  Before the fix, now=0.0 was falsy
        # and fell through to time.time(), incorrectly expiring the message.
        expired = check_expired(bus_root, events_dir=events_dir, now=0.0)
        assert len(expired) == 0


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
        resolve_result = resolve_message(
            mid, "author-a", bus_root, events_dir=events_dir
        )
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


# ---------------------------------------------------------------------------
# Bulk ack
# ---------------------------------------------------------------------------


class TestBulkAckMessages:
    """Test bulk_ack_messages delivery semantics."""

    def test_bulk_ack_all(self, bus_root: Path, events_dir: Path) -> None:
        """Ack all pending messages in a lane."""
        m1 = create_message("a", "target", "assignment", "Task 1")
        m2 = create_message("a", "target", "progress", "Task 2")
        send_message(m1, bus_root, events_dir=events_dir)
        send_message(m2, bus_root, events_dir=events_dir)

        acked = bulk_ack_messages(
            "target", lambda _: True, bus_root, events_dir=events_dir
        )
        assert len(acked) == 2
        assert all(r["status"] == "acked" for r in acked)

    def test_bulk_ack_with_filter(self, bus_root: Path, events_dir: Path) -> None:
        """Only messages matching filter_fn are acked."""
        m1 = create_message("a", "target", "assignment", "Fix scoring bug")
        m2 = create_message("a", "target", "progress", "Test progress update")
        send_message(m1, bus_root, events_dir=events_dir)
        send_message(m2, bus_root, events_dir=events_dir)

        acked = bulk_ack_messages(
            "target",
            lambda msg: "scoring" in msg.get("summary", "").lower(),
            bus_root,
            events_dir=events_dir,
        )
        assert len(acked) == 1
        assert acked[0]["summary"] == "Fix scoring bug"

        # The other message remains pending
        inbox = read_inbox("target", bus_root, status="pending")
        assert len(inbox) == 1
        assert inbox[0]["summary"] == "Test progress update"

    def test_bulk_ack_skips_non_ackable(self, bus_root: Path, events_dir: Path) -> None:
        """Already-acked and terminal messages are not re-acked."""
        m1 = create_message("a", "target", "assignment", "Already acked")
        m2 = create_message("a", "target", "progress", "Still pending")
        send_message(m1, bus_root, events_dir=events_dir)
        send_message(m2, bus_root, events_dir=events_dir)

        # Ack m1 individually first
        ack_message(m1.message_id, "target", bus_root, events_dir=events_dir)

        # Bulk ack should only ack m2
        acked = bulk_ack_messages(
            "target", lambda _: True, bus_root, events_dir=events_dir
        )
        assert len(acked) == 1
        assert acked[0]["message_id"] == m2.message_id

    def test_bulk_ack_empty_inbox(self, bus_root: Path, events_dir: Path) -> None:
        """Bulk ack on empty inbox returns empty list."""
        acked = bulk_ack_messages(
            "empty-lane", lambda _: True, bus_root, events_dir=events_dir
        )
        assert acked == []

    def test_bulk_ack_emits_events(self, bus_root: Path, events_dir: Path) -> None:
        """Each bulk-acked message emits an event with bulk=True."""
        m1 = create_message("a", "target", "assignment", "Task 1")
        m2 = create_message("a", "target", "assignment", "Task 2")
        send_message(m1, bus_root, events_dir=events_dir)
        send_message(m2, bus_root, events_dir=events_dir)

        bulk_ack_messages("target", lambda _: True, bus_root, events_dir=events_dir)

        events_file = events_dir / "events.jsonl"
        lines = events_file.read_text().strip().split("\n")
        ack_events = [
            json.loads(line)
            for line in lines
            if json.loads(line)["event_type"] == "message_acked"
        ]
        assert len(ack_events) == 2
        assert all(ev["payload"].get("bulk") is True for ev in ack_events)


# ---------------------------------------------------------------------------
# TTL auto-expire on read
# ---------------------------------------------------------------------------


class TestTTLAutoExpireOnRead:
    """Test that read_inbox auto-expires stale messages."""

    def test_default_ttl_is_24h(self) -> None:
        """DEFAULT_TTL_SECONDS should be 86400 (24 hours)."""
        assert DEFAULT_TTL_SECONDS == 86400

    def test_auto_expire_on_read(self, bus_root: Path, events_dir: Path) -> None:
        """Messages past their TTL are expired when inbox is read."""
        msg = create_message(
            "a",
            "target",
            "assignment",
            "Short-lived task",
            payload={"ttl_seconds": 60},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # Read immediately — message should be pending
        inbox = read_inbox("target", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "pending"

        # Create another message with TTL=1 second
        msg2 = create_message(
            "a",
            "target2",
            "assignment",
            "Expiring soon",
            payload={"ttl_seconds": 1},
        )
        send_message(msg2, bus_root, events_dir=events_dir)

        # Use deterministic now= parameter instead of sleeping
        future_time = time.time() + 100  # well past 1s TTL
        inbox2 = read_inbox("target2", bus_root, now=future_time)
        assert len(inbox2) == 1
        assert inbox2[0]["status"] == "expired"

    def test_auto_expire_disabled(self, bus_root: Path, events_dir: Path) -> None:
        """When auto_expire=False, stale messages are not expired."""
        msg = create_message(
            "a",
            "target",
            "assignment",
            "Should stay pending",
            payload={"ttl_seconds": 1},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # Use deterministic now= with auto_expire=False — message stays pending
        future_time = time.time() + 100  # well past 1s TTL
        inbox = read_inbox("target", bus_root, auto_expire=False, now=future_time)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "pending"

    def test_auto_expire_does_not_touch_terminal(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Already-resolved messages are not re-expired on read."""
        msg = create_message(
            "a",
            "target",
            "assignment",
            "Resolved task",
            payload={"ttl_seconds": 1},
        )
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "target", bus_root, events_dir=events_dir)
        resolve_message(msg.message_id, "target", bus_root, events_dir=events_dir)

        # Use deterministic now= instead of sleeping
        future_time = time.time() + 100  # well past 1s TTL
        inbox = read_inbox("target", bus_root, status="resolved", now=future_time)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "resolved"

    def test_no_ttl_never_auto_expires(self, bus_root: Path, events_dir: Path) -> None:
        """Messages with ttl_seconds=None are never auto-expired on read."""
        msg = create_message(
            "a",
            "target",
            "assignment",
            "Eternal message",
            payload={"ttl_seconds": None},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # Even far in the future, no expiry
        inbox = read_inbox("target", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "pending"

    def test_zero_now_is_preserved_on_read(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """now=0.0 is a valid override and must not fall through to time.time()."""
        msg = create_message(
            "a",
            "target",
            "assignment",
            "Epoch message",
            payload={"ttl_seconds": 60},
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # With now=0.0 (epoch), the message was created "in the future" relative
        # to epoch, so auto-expire should leave it pending.  Before the fix,
        # now=0.0 was falsy and fell through to time.time().
        inbox = read_inbox("target", bus_root, now=0.0)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "pending"

    def test_new_messages_get_default_ttl(self) -> None:
        """create_message injects DEFAULT_TTL_SECONDS into payload."""
        msg = create_message("a", "b", "assignment", "Default TTL")
        assert msg.payload["ttl_seconds"] == 86400


# ---------------------------------------------------------------------------
# Native inbox bridge
# ---------------------------------------------------------------------------


class TestNativeInboxBridge:
    """Test import_native_inbox() and content hashing."""

    @pytest.fixture()
    def native_dir(self, tmp_path: Path) -> Path:
        """Create a temp native inbox directory."""
        d = tmp_path / "native_inboxes"
        d.mkdir()
        return d

    def _write_native_inbox(
        self, native_dir: Path, lane_id: str, entries: list[dict]
    ) -> Path:
        """Write a native inbox JSON file."""
        path = native_dir / f"{lane_id}.json"
        path.write_text(json.dumps(entries, indent=2))
        return path

    def test_content_hash_stable(self) -> None:
        """Same input produces the same hash."""
        entry = {
            "from": "team-lead",
            "timestamp": "2026-03-22T12:00:00Z",
            "summary": "Review approved",
        }
        h1 = _native_content_hash(entry)
        h2 = _native_content_hash(entry)
        assert h1 == h2
        assert len(h1) == 16

    def test_content_hash_different_entries(self) -> None:
        """Different entries produce different hashes."""
        entry1 = {
            "from": "team-lead",
            "timestamp": "2026-03-22T12:00:00Z",
            "summary": "Review approved",
        }
        entry2 = {
            "from": "team-lead",
            "timestamp": "2026-03-22T12:01:00Z",
            "summary": "Review approved",
        }
        assert _native_content_hash(entry1) != _native_content_hash(entry2)

    def test_content_hash_includes_text(self) -> None:
        """Entries with same metadata but different text produce different hashes."""
        entry1 = {
            "from": "team-lead",
            "timestamp": "2026-03-22T12:00:00Z",
            "summary": "Review approved",
            "text": "Looks good to merge.",
        }
        entry2 = {
            "from": "team-lead",
            "timestamp": "2026-03-22T12:00:00Z",
            "summary": "Review approved",
            "text": "Needs one more fix before merge.",
        }
        assert _native_content_hash(entry1) != _native_content_hash(entry2)

    def test_import_basic(
        self, bus_root: Path, events_dir: Path, native_dir: Path
    ) -> None:
        """Import native messages into the repo-owned bus."""
        entries = [
            {
                "from": "team-lead",
                "text": "Please fix the bug.",
                "summary": "Bug fix request",
                "timestamp": "2026-03-22T12:00:00Z",
                "read": False,
            },
            {
                "from": "orchestrator",
                "text": "Task dispatched.",
                "summary": "Task dispatch",
                "timestamp": "2026-03-22T12:01:00Z",
                "read": True,
            },
        ]
        self._write_native_inbox(native_dir, "author-a", entries)

        imported = import_native_inbox(
            "author-a",
            native_dir=native_dir,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(imported) == 2

        # Verify messages appear in the inbox
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 2

        # Verify source_transport is set
        for msg in inbox:
            assert msg["source_transport"] == "claude_native"
            assert "native_hash" in msg.get("payload", {})

    def test_import_idempotent(
        self, bus_root: Path, events_dir: Path, native_dir: Path
    ) -> None:
        """Running import twice doesn't create duplicate messages."""
        entries = [
            {
                "from": "team-lead",
                "text": "Review done.",
                "summary": "Review complete",
                "timestamp": "2026-03-22T12:00:00Z",
                "read": False,
            },
        ]
        self._write_native_inbox(native_dir, "author-b", entries)

        # First import
        imported1 = import_native_inbox(
            "author-b",
            native_dir=native_dir,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(imported1) == 1

        # Second import — should skip the duplicate
        imported2 = import_native_inbox(
            "author-b",
            native_dir=native_dir,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(imported2) == 0

        # Only 1 message in inbox
        inbox = read_inbox("author-b", bus_root)
        assert len(inbox) == 1

    def test_import_no_file(self, bus_root: Path, native_dir: Path) -> None:
        """No native file for lane returns empty list."""
        result = import_native_inbox(
            "author-z",
            native_dir=native_dir,
            bus_root=bus_root,
        )
        assert result == []

    def test_import_invalid_json(self, bus_root: Path, native_dir: Path) -> None:
        """Malformed JSON file returns empty list without crashing."""
        path = native_dir / "author-c.json"
        path.write_text("not valid json {{{")
        result = import_native_inbox(
            "author-c",
            native_dir=native_dir,
            bus_root=bus_root,
        )
        assert result == []

    def test_import_not_array(self, bus_root: Path, native_dir: Path) -> None:
        """Non-array JSON returns empty list."""
        path = native_dir / "author-d.json"
        path.write_text(json.dumps({"not": "an array"}))
        result = import_native_inbox(
            "author-d",
            native_dir=native_dir,
            bus_root=bus_root,
        )
        assert result == []

    def test_import_preserves_native_metadata(
        self, bus_root: Path, events_dir: Path, native_dir: Path
    ) -> None:
        """Imported messages carry native_text, native_read, and native_timestamp."""
        entries = [
            {
                "from": "reviewer",
                "text": "Detailed review text here.",
                "summary": "PR review",
                "timestamp": "2026-03-22T14:00:00Z",
                "read": True,
            },
        ]
        self._write_native_inbox(native_dir, "author-a", entries)
        imported = import_native_inbox(
            "author-a",
            native_dir=native_dir,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        assert len(imported) == 1
        payload = imported[0]["payload"]
        assert payload["native_text"] == "Detailed review text here."
        assert payload["native_read"] is True
        assert payload["native_timestamp"] == "2026-03-22T14:00:00Z"

        # created_at should be import time (now), not native timestamp
        created_at = imported[0]["created_at"]
        assert created_at != "2026-03-22T14:00:00Z"

    def test_import_incremental(
        self, bus_root: Path, events_dir: Path, native_dir: Path
    ) -> None:
        """New entries added to native file are imported on second run."""
        entries = [
            {
                "from": "a",
                "text": "first",
                "summary": "First",
                "timestamp": "2026-03-22T12:00:00Z",
                "read": False,
            },
        ]
        self._write_native_inbox(native_dir, "author-a", entries)
        import_native_inbox(
            "author-a",
            native_dir=native_dir,
            bus_root=bus_root,
            events_dir=events_dir,
        )

        # Add a second entry
        entries.append(
            {
                "from": "b",
                "text": "second",
                "summary": "Second",
                "timestamp": "2026-03-22T13:00:00Z",
                "read": False,
            }
        )
        self._write_native_inbox(native_dir, "author-a", entries)

        imported2 = import_native_inbox(
            "author-a",
            native_dir=native_dir,
            bus_root=bus_root,
            events_dir=events_dir,
        )
        # Only the new one
        assert len(imported2) == 1
        assert imported2[0]["summary"] == "Second"

        # Total in inbox
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 2


# ---------------------------------------------------------------------------
# Inbox compaction (purge)
# ---------------------------------------------------------------------------


class TestCompactInbox:
    """Test compact_inbox and compact_all_inboxes."""

    def test_empty_inbox_is_noop(self, bus_root: Path) -> None:
        result = compact_inbox("nonexistent-lane", bus_root)
        assert result == {
            "lane_id": "nonexistent-lane",
            "before": 0,
            "after": 0,
            "removed": 0,
        }

    def test_purges_old_acked_messages(self, bus_root: Path, events_dir: Path) -> None:
        """Acked messages older than max_age are removed."""
        # Send and ack a message
        msg = create_message("orchestrator", "author-a", "assignment", "Old task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        # Verify it's in the inbox
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["status"] == "acked"

        # Compact with now far in the future — message should be purged
        future_time = time.time() + 100_000
        result = compact_inbox(
            "author-a", bus_root, max_age_hours=24.0, now=future_time
        )
        assert result["removed"] == 1
        assert result["after"] == 0

        # Inbox should be empty
        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 0

    def test_preserves_recent_acked_messages(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Acked messages newer than max_age are kept."""
        msg = create_message("orchestrator", "author-a", "assignment", "Recent task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        # Compact with current time — message is recent, should be kept
        result = compact_inbox("author-a", bus_root, max_age_hours=24.0)
        assert result["removed"] == 0
        assert result["after"] == 1

    def test_preserves_active_messages(self, bus_root: Path, events_dir: Path) -> None:
        """Pending and delivered messages are never removed."""
        msg = create_message("orchestrator", "author-a", "assignment", "Active task")
        send_message(msg, bus_root, events_dir=events_dir)

        # Even with now far in the future, pending/delivered messages stay
        future_time = time.time() + 100_000
        result = compact_inbox("author-a", bus_root, max_age_hours=0, now=future_time)
        assert result["removed"] == 0
        assert result["after"] == 1

    def test_purges_resolved_messages(self, bus_root: Path, events_dir: Path) -> None:
        """Resolved (terminal) messages older than max_age are removed."""
        msg = create_message("orchestrator", "author-a", "assignment", "Done task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "author-a", bus_root, events_dir=events_dir)
        resolve_message(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        future_time = time.time() + 100_000
        result = compact_inbox(
            "author-a", bus_root, max_age_hours=24.0, now=future_time
        )
        assert result["removed"] == 1
        assert result["after"] == 0

    def test_deduplicates_append_only_records(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Multiple status records for the same message_id are deduplicated."""
        msg = create_message("orchestrator", "author-a", "assignment", "Multi-update")
        send_message(msg, bus_root, events_dir=events_dir)
        # Send creates 1 record, ack appends another → 2 raw records
        ack_message(msg.message_id, "author-a", bus_root, events_dir=events_dir)

        # Before compaction: 2 raw records for 1 message
        result = compact_inbox("author-a", bus_root, max_age_hours=24.0)
        assert result["before"] == 2  # 2 raw JSONL lines
        assert result["after"] == 1  # 1 deduplicated message kept
        assert result["removed"] == 0  # recent acked, not removed

    def test_compact_all_inboxes(self, bus_root: Path, events_dir: Path) -> None:
        """compact_all_inboxes processes all lane inbox files."""
        # Create messages in two different lane inboxes
        msg1 = create_message("orchestrator", "author-a", "assignment", "Task A")
        send_message(msg1, bus_root, events_dir=events_dir)
        ack_message(msg1.message_id, "author-a", bus_root, events_dir=events_dir)

        msg2 = create_message("orchestrator", "author-b", "assignment", "Task B")
        send_message(msg2, bus_root, events_dir=events_dir)
        ack_message(msg2.message_id, "author-b", bus_root, events_dir=events_dir)

        future_time = time.time() + 100_000
        results = compact_all_inboxes(bus_root, max_age_hours=24.0, now=future_time)

        assert len(results) == 2
        lane_ids = {r["lane_id"] for r in results}
        assert lane_ids == {"author-a", "author-b"}
        assert sum(r["removed"] for r in results) == 2

    def test_mixed_messages_selective_purge(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Only old handled messages are purged; active and recent kept."""
        # Old acked message
        old_msg = create_message("orchestrator", "author-a", "assignment", "Old")
        send_message(old_msg, bus_root, events_dir=events_dir)
        ack_message(old_msg.message_id, "author-a", bus_root, events_dir=events_dir)

        # Active (pending) message
        active_msg = create_message("orchestrator", "author-a", "assignment", "Active")
        send_message(active_msg, bus_root, events_dir=events_dir)

        # Compact with future time — only old acked gets purged
        future_time = time.time() + 100_000
        result = compact_inbox(
            "author-a", bus_root, max_age_hours=24.0, now=future_time
        )
        assert result["removed"] == 1  # old acked
        assert result["after"] == 1  # active pending

        inbox = read_inbox("author-a", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["summary"] == "Active"


# ---------------------------------------------------------------------------
# Multi-type inbox filter
# ---------------------------------------------------------------------------


class TestMultiTypeInboxFilter:
    """Test read_inbox with multi-type message_type filter."""

    def test_single_type_string_still_works(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Backward compat: single string filter still matches."""
        msg_a = create_message("a", "b", "assignment", "A")
        msg_b = create_message("a", "b", "completion", "B")
        send_message(msg_a, bus_root, events_dir=events_dir)
        send_message(msg_b, bus_root, events_dir=events_dir)

        result = read_inbox("b", bus_root, message_type="completion")
        assert len(result) == 1
        assert result[0]["summary"] == "B"

    def test_multi_type_list_matches_any(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """A list of types matches messages of any listed type."""
        msg_a = create_message("a", "b", "assignment", "A")
        msg_b = create_message("a", "b", "completion", "B")
        msg_c = create_message("a", "b", "blocker", "C")
        for m in (msg_a, msg_b, msg_c):
            send_message(m, bus_root, events_dir=events_dir)

        result = read_inbox("b", bus_root, message_type=["completion", "blocker"])
        assert len(result) == 2
        summaries = {r["summary"] for r in result}
        assert summaries == {"B", "C"}

    def test_multi_type_no_match_returns_empty(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Multi-type filter returns empty when no types match."""
        msg = create_message("a", "b", "assignment", "A")
        send_message(msg, bus_root, events_dir=events_dir)

        result = read_inbox("b", bus_root, message_type=["completion", "blocker"])
        assert result == []

    def test_none_type_returns_all(self, bus_root: Path, events_dir: Path) -> None:
        """message_type=None returns all messages (no filter)."""
        msg_a = create_message("a", "b", "assignment", "A")
        msg_b = create_message("a", "b", "completion", "B")
        send_message(msg_a, bus_root, events_dir=events_dir)
        send_message(msg_b, bus_root, events_dir=events_dir)

        result = read_inbox("b", bus_root, message_type=None)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Content-based dedup
# ---------------------------------------------------------------------------


class TestContentDedup:
    """Test content-based duplicate suppression in send_message."""

    def test_dedup_key_deterministic(self) -> None:
        """Same message fields produce the same dedup key."""
        msg1 = create_message("review", "orchestrator", "progress", "Verdict X")
        msg2 = create_message("review", "orchestrator", "progress", "Verdict X")
        assert _content_dedup_key(msg1) == _content_dedup_key(msg2)

    def test_dedup_key_differs_on_summary(self) -> None:
        """Different summaries produce different dedup keys."""
        msg1 = create_message("review", "orchestrator", "progress", "Verdict A")
        msg2 = create_message("review", "orchestrator", "progress", "Verdict B")
        assert _content_dedup_key(msg1) != _content_dedup_key(msg2)

    def test_dedup_suppresses_duplicate_send(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Second send with deduplicate=True returns existing ID, no new message."""
        msg1 = create_message("review", "orchestrator", "progress", "Verdict PR #42")
        send_message(msg1, bus_root, events_dir=events_dir)

        msg2 = create_message("review", "orchestrator", "progress", "Verdict PR #42")
        result_id = send_message(
            msg2, bus_root, events_dir=events_dir, deduplicate=True
        )

        assert result_id == msg1.message_id
        inbox = read_inbox("orchestrator", bus_root)
        assert len(inbox) == 1

    def test_dedup_false_allows_duplicates(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """With deduplicate=False (default), duplicates are sent normally."""
        msg1 = create_message("review", "orchestrator", "progress", "Verdict PR #42")
        send_message(msg1, bus_root, events_dir=events_dir)

        msg2 = create_message("review", "orchestrator", "progress", "Verdict PR #42")
        result_id = send_message(
            msg2, bus_root, events_dir=events_dir, deduplicate=False
        )

        assert result_id == msg2.message_id
        inbox = read_inbox("orchestrator", bus_root)
        assert len(inbox) == 2

    def test_dedup_allows_after_terminal(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """After resolving the original, a new content-duplicate can be sent."""
        msg1 = create_message("review", "orchestrator", "progress", "Verdict PR #42")
        send_message(msg1, bus_root, events_dir=events_dir)
        ack_message(msg1.message_id, "orchestrator", bus_root, events_dir=events_dir)
        resolve_message(
            msg1.message_id, "orchestrator", bus_root, events_dir=events_dir
        )

        msg2 = create_message("review", "orchestrator", "progress", "Verdict PR #42")
        result_id = send_message(
            msg2, bus_root, events_dir=events_dir, deduplicate=True
        )

        # New message sent because old one is resolved (terminal)
        assert result_id == msg2.message_id

    def test_find_content_duplicate_returns_none_on_empty(self, bus_root: Path) -> None:
        """No duplicate found in empty inbox."""
        msg = create_message("review", "orchestrator", "progress", "Test")
        assert _find_content_duplicate(msg, bus_root) is None

    def test_find_content_duplicate_ignores_different_summary(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Messages with different summaries are not duplicates."""
        msg1 = create_message("review", "orchestrator", "progress", "Verdict A")
        send_message(msg1, bus_root, events_dir=events_dir)

        msg2 = create_message("review", "orchestrator", "progress", "Verdict B")
        assert _find_content_duplicate(msg2, bus_root) is None


# ---------------------------------------------------------------------------
# Tiered compaction policy
# ---------------------------------------------------------------------------


class TestTieredCompaction:
    """Test tiered retention in compact_inbox."""

    def test_tiered_cutoff_terminal_uses_shorter_retention(self) -> None:
        """Terminal messages use COMPACT_TERMINAL_MAX_AGE_HOURS."""
        now = 100_000.0
        cutoff = _tiered_cutoff("resolved", now, max_age_hours=24.0)
        expected = now - (COMPACT_TERMINAL_MAX_AGE_HOURS * 3600)
        assert cutoff == expected

    def test_tiered_cutoff_acked_uses_handled_retention(self) -> None:
        """Acked messages use COMPACT_HANDLED_MAX_AGE_HOURS."""
        now = 100_000.0
        cutoff = _tiered_cutoff("acked", now, max_age_hours=24.0)
        expected = now - (COMPACT_HANDLED_MAX_AGE_HOURS * 3600)
        assert cutoff == expected

    def test_tiered_cutoff_caller_override_wins_when_shorter(self) -> None:
        """If caller's max_age_hours is shorter than tier default, it wins."""
        now = 100_000.0
        # Terminal tier default is 1h; caller requests 0.5h
        cutoff = _tiered_cutoff("resolved", now, max_age_hours=0.5)
        expected = now - (0.5 * 3600)
        assert cutoff == expected

    def test_tiered_compact_purges_terminal_before_acked(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Terminal messages are purged with shorter retention than acked."""
        # Create an acked message and a resolved message, both "old"
        msg_acked = create_message("o", "lane-a", "assignment", "Acked msg")
        send_message(msg_acked, bus_root, events_dir=events_dir)
        ack_message(msg_acked.message_id, "lane-a", bus_root, events_dir=events_dir)

        msg_resolved = create_message("o", "lane-a", "completion", "Resolved msg")
        send_message(msg_resolved, bus_root, events_dir=events_dir)
        ack_message(msg_resolved.message_id, "lane-a", bus_root, events_dir=events_dir)
        resolve_message(
            msg_resolved.message_id, "lane-a", bus_root, events_dir=events_dir
        )

        # Time just past the terminal retention (1h) but within handled (4h)
        future_time = time.time() + (COMPACT_TERMINAL_MAX_AGE_HOURS * 3600) + 60

        result = compact_inbox(
            "lane-a", bus_root, max_age_hours=24.0, now=future_time, tiered=True
        )
        # Resolved (terminal) is purged; acked (handled) is kept
        assert result["removed"] == 1
        assert result["after"] == 1

        inbox = read_inbox("lane-a", bus_root, auto_compact=False)
        assert len(inbox) == 1
        assert inbox[0]["summary"] == "Acked msg"

    def test_tiered_false_uses_flat_max_age(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """With tiered=False, all handled messages use the same max_age."""
        msg = create_message("o", "lane-a", "assignment", "Task")
        send_message(msg, bus_root, events_dir=events_dir)
        ack_message(msg.message_id, "lane-a", bus_root, events_dir=events_dir)

        # Time past 4h (handled tier) but within 24h (flat)
        future_time = time.time() + (COMPACT_HANDLED_MAX_AGE_HOURS * 3600) + 60

        result = compact_inbox(
            "lane-a", bus_root, max_age_hours=24.0, now=future_time, tiered=False
        )
        # With flat policy, 24h retention — message is kept
        assert result["removed"] == 0
        assert result["after"] == 1


# ---------------------------------------------------------------------------
# Auto-compaction on read_inbox
# ---------------------------------------------------------------------------


class TestAutoCompaction:
    """Test auto-compaction triggered by read_inbox."""

    def test_auto_compact_triggers_above_threshold(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Auto-compaction fires when raw line count exceeds threshold."""
        # Create many messages and ack them to inflate the inbox
        lane = "auto-compact-lane"
        for i in range(AUTO_COMPACT_RAW_THRESHOLD + 10):
            msg = create_message("o", lane, "assignment", f"Task {i}")
            send_message(msg, bus_root, events_dir=events_dir)
            ack_message(msg.message_id, lane, bus_root, events_dir=events_dir)

        # Each send + ack = 2 raw lines per message
        # Total raw lines: (threshold+10) * 2, well above threshold

        # Set time past the handled retention so acked messages get purged
        future = time.time() + (COMPACT_HANDLED_MAX_AGE_HOURS * 3600) + 60

        # read_inbox with auto_compact=True should compact transparently
        inbox = read_inbox(lane, bus_root, auto_compact=True, now=future)
        # All messages are old acked — they get purged by tiered compaction
        assert len(inbox) == 0

    def test_auto_compact_disabled(self, bus_root: Path, events_dir: Path) -> None:
        """With auto_compact=False, no compaction happens on read."""
        lane = "no-compact-lane"
        n_msgs = AUTO_COMPACT_RAW_THRESHOLD + 10
        for i in range(n_msgs):
            msg = create_message("o", lane, "assignment", f"Task {i}")
            send_message(msg, bus_root, events_dir=events_dir)
            ack_message(msg.message_id, lane, bus_root, events_dir=events_dir)

        future = time.time() + (COMPACT_HANDLED_MAX_AGE_HOURS * 3600) + 60

        # With auto_compact=False, acked messages still show up
        inbox = read_inbox(
            lane,
            bus_root,
            auto_compact=False,
            auto_expire=False,
            now=future,
            limit=n_msgs + 10,
        )
        assert len(inbox) == n_msgs

    def test_auto_compact_below_threshold_is_noop(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Below threshold, no compaction happens even with auto_compact=True."""
        lane = "small-lane"
        # Create just a few messages — well below threshold
        for i in range(5):
            msg = create_message("o", lane, "assignment", f"Task {i}")
            send_message(msg, bus_root, events_dir=events_dir)
            ack_message(msg.message_id, lane, bus_root, events_dir=events_dir)

        future = time.time() + (COMPACT_HANDLED_MAX_AGE_HOURS * 3600) + 60

        # Even though messages are old enough to purge, the threshold isn't hit
        # so auto-compact doesn't fire — messages remain
        inbox = read_inbox(lane, bus_root, auto_compact=True, now=future)
        assert len(inbox) == 5
