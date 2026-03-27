"""Tests for the durable event log (ops/events.py)."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.events import (
    ARCHIVE_FILE,
    EVENTS_FILE,
    LOCK_FILE,
    VALID_EVENT_TYPES,
    append_event,
    drain_events,
    read_events,
)


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Provide a temporary events directory."""
    d = tmp_path / "events"
    d.mkdir()
    return d


class TestAppendEvent:
    """Tests for append_event()."""

    def test_creates_events_file(self, events_dir: Path) -> None:
        append_event("task_completed", "test", "author-a", {}, events_dir)
        assert (events_dir / EVENTS_FILE).exists()

    def test_appends_valid_jsonl(self, events_dir: Path) -> None:
        append_event("task_completed", "test", "author-a", {"k": "v"}, events_dir)
        append_event("ci_failure", "test", "ops", {"pr": 42}, events_dir)

        lines = (events_dir / EVENTS_FILE).read_text().strip().split("\n")
        assert len(lines) == 2

        event1 = json.loads(lines[0])
        assert event1["event_type"] == "task_completed"
        assert event1["source"] == "test"
        assert event1["lane_id"] == "author-a"
        assert event1["payload"] == {"k": "v"}
        assert "timestamp" in event1

        event2 = json.loads(lines[1])
        assert event2["event_type"] == "ci_failure"
        assert event2["payload"] == {"pr": 42}

    def test_returns_event_dict(self, events_dir: Path) -> None:
        result = append_event(
            "session_started", "launcher", "review", {"task": "test"}, events_dir
        )
        assert result["event_type"] == "session_started"
        assert result["source"] == "launcher"
        assert result["lane_id"] == "review"
        assert result["payload"] == {"task": "test"}

    def test_rejects_unknown_event_type(self, events_dir: Path) -> None:
        with pytest.raises(ValueError, match="Unknown event_type"):
            append_event("totally_bogus", "test", "ops", {}, events_dir)

    def test_creates_directory_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "events"
        append_event("task_completed", "test", "ops", {}, nested)
        assert (nested / EVENTS_FILE).exists()

    def test_all_valid_event_types_accepted(self, events_dir: Path) -> None:
        for etype in VALID_EVENT_TYPES:
            append_event(etype, "test", "ops", {}, events_dir)
        events = read_events(events_dir, limit=len(VALID_EVENT_TYPES) + 1)
        assert len(events) == len(VALID_EVENT_TYPES)


class TestReadEvents:
    """Tests for read_events()."""

    def test_empty_dir_returns_empty(self, events_dir: Path) -> None:
        assert read_events(events_dir) == []

    def test_returns_most_recent_first(self, events_dir: Path) -> None:
        append_event("task_completed", "a", "ops", {"i": 1}, events_dir)
        append_event("ci_failure", "b", "ops", {"i": 2}, events_dir)
        append_event("session_started", "c", "ops", {"i": 3}, events_dir)

        events = read_events(events_dir)
        assert len(events) == 3
        assert events[0]["payload"]["i"] == 3
        assert events[2]["payload"]["i"] == 1

    def test_limit(self, events_dir: Path) -> None:
        for i in range(10):
            append_event("task_completed", "test", "ops", {"i": i}, events_dir)

        events = read_events(events_dir, limit=3)
        assert len(events) == 3
        # Most recent first
        assert events[0]["payload"]["i"] == 9

    def test_filter_by_event_type(self, events_dir: Path) -> None:
        append_event("task_completed", "test", "ops", {}, events_dir)
        append_event("ci_failure", "test", "ops", {}, events_dir)
        append_event("task_completed", "test", "ops", {}, events_dir)

        events = read_events(events_dir, event_type="ci_failure")
        assert len(events) == 1
        assert events[0]["event_type"] == "ci_failure"

    def test_filter_by_lane_id(self, events_dir: Path) -> None:
        append_event("task_completed", "test", "author-a", {}, events_dir)
        append_event("task_completed", "test", "ops", {}, events_dir)
        append_event("ci_failure", "test", "author-a", {}, events_dir)

        events = read_events(events_dir, lane_id="author-a")
        assert len(events) == 2
        assert all(e["lane_id"] == "author-a" for e in events)

    def test_filter_by_since(self, events_dir: Path) -> None:
        # Write events with known timestamps
        events_file = events_dir / EVENTS_FILE
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=2)
        recent = now - timedelta(minutes=5)

        for ts in [old, recent, now]:
            event = {
                "timestamp": ts.isoformat(),
                "event_type": "task_completed",
                "source": "test",
                "lane_id": "ops",
                "payload": {"ts": ts.isoformat()},
            }
            with open(events_file, "a") as f:
                f.write(json.dumps(event) + "\n")

        cutoff = now - timedelta(hours=1)
        events = read_events(events_dir, since=cutoff)
        assert len(events) == 2

    def test_skips_malformed_lines(self, events_dir: Path) -> None:
        events_file = events_dir / EVENTS_FILE
        with open(events_file, "w") as f:
            f.write("not json at all\n")
            f.write(
                json.dumps(
                    {
                        "event_type": "ci_failure",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "source": "x",
                        "lane_id": "ops",
                        "payload": {},
                    }
                )
                + "\n"
            )

        events = read_events(events_dir)
        assert len(events) == 1

    def test_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_events(tmp_path / "no_such_dir") == []


class TestDrainEvents:
    """Tests for drain_events()."""

    def test_drain_all(self, events_dir: Path) -> None:
        for i in range(5):
            append_event("task_completed", "test", "ops", {"i": i}, events_dir)

        drained = drain_events(events_dir)
        assert drained == 5

        # Active log should be empty
        assert read_events(events_dir) == []

        # Archive should have 5 events
        archive = events_dir / "events.archive.jsonl"
        assert archive.exists()
        lines = archive.read_text().strip().split("\n")
        assert len(lines) == 5

    def test_drain_up_to_timestamp(self, events_dir: Path) -> None:
        events_file = events_dir / EVENTS_FILE
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=2)
        recent = now - timedelta(minutes=5)

        for ts in [old, recent, now]:
            event = {
                "timestamp": ts.isoformat(),
                "event_type": "task_completed",
                "source": "test",
                "lane_id": "ops",
                "payload": {},
            }
            with open(events_file, "a") as f:
                f.write(json.dumps(event) + "\n")

        cutoff = now - timedelta(hours=1)
        drained = drain_events(events_dir, up_to=cutoff)
        assert drained == 1

        remaining = read_events(events_dir)
        assert len(remaining) == 2

    def test_drain_empty_log(self, events_dir: Path) -> None:
        assert drain_events(events_dir) == 0

    def test_drain_appends_to_existing_archive(self, events_dir: Path) -> None:
        # First batch
        append_event("task_completed", "test", "ops", {"batch": 1}, events_dir)
        drain_events(events_dir)

        # Second batch
        append_event("ci_failure", "test", "ops", {"batch": 2}, events_dir)
        drain_events(events_dir)

        archive = events_dir / "events.archive.jsonl"
        lines = archive.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_drain_nonexistent_dir(self, tmp_path: Path) -> None:
        assert drain_events(tmp_path / "no_such") == 0

    def test_drain_archive_written_after_active_rename(self, events_dir: Path) -> None:
        """Archive append happens AFTER active log rename (H1 crash safety).

        Verify that after drain, the active log contains only kept events
        and archive contains only drained events — no duplication.
        """
        events_file = events_dir / EVENTS_FILE
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=2)

        # Write 2 old events (will be drained) and 1 recent (will be kept)
        for ts in [old, old + timedelta(minutes=1), now]:
            event = {
                "timestamp": ts.isoformat(),
                "event_type": "task_completed",
                "source": "test",
                "lane_id": "ops",
                "payload": {"ts": ts.isoformat()},
            }
            with open(events_file, "a") as f:
                f.write(json.dumps(event) + "\n")

        cutoff = now - timedelta(hours=1)
        drained = drain_events(events_dir, up_to=cutoff)
        assert drained == 2

        # Active log should have exactly 1 event (the recent one)
        remaining = read_events(events_dir)
        assert len(remaining) == 1

        # Archive should have exactly 2 events
        archive = events_dir / ARCHIVE_FILE
        assert archive.exists()
        archive_lines = [
            l for l in archive.read_text().strip().split("\n") if l.strip()
        ]
        assert len(archive_lines) == 2

    def test_drain_serializes_with_concurrent_append(self, events_dir: Path) -> None:
        """drain_events() holds lock, preventing concurrent append loss (M7).

        Appends that start during drain must complete after drain releases
        the lock, ensuring the appended event survives.
        """
        # Write initial events
        for i in range(3):
            append_event("task_completed", "test", "ops", {"i": i}, events_dir)

        drain_started = threading.Event()
        drain_done = threading.Event()
        append_done = threading.Event()

        def do_drain() -> None:
            drain_started.set()
            drain_events(events_dir)
            drain_done.set()

        def do_append() -> None:
            # Wait for drain to start, then try appending
            drain_started.wait(timeout=5)
            # Small delay to let drain acquire lock — generous for slow CI.
            time.sleep(0.2)
            append_event(
                "ci_failure", "concurrent", "ops", {"concurrent": True}, events_dir
            )
            append_done.set()

        t1 = threading.Thread(target=do_drain)
        t2 = threading.Thread(target=do_append)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert drain_done.is_set(), "drain should complete"
        assert append_done.is_set(), "append should complete"

        # The concurrent append should survive (written to the new active log
        # after drain released the lock and renamed the file).
        remaining = read_events(events_dir)
        assert len(remaining) >= 1
        # At least the concurrent event should be present
        concurrent_events = [
            e for e in remaining if e.get("payload", {}).get("concurrent") is True
        ]
        assert len(concurrent_events) == 1


class TestLockFile:
    """Tests for dedicated lock file (#938)."""

    def test_append_creates_lock_file(self, events_dir: Path) -> None:
        """append_event creates the dedicated lock file."""
        append_event("task_completed", "test", "ops", {}, events_dir)
        assert (events_dir / LOCK_FILE).exists()

    def test_drain_creates_lock_file(self, events_dir: Path) -> None:
        """drain_events creates the dedicated lock file."""
        append_event("task_completed", "test", "ops", {}, events_dir)
        # Remove lock file to verify drain recreates it
        lock_path = events_dir / LOCK_FILE
        lock_path.unlink()
        drain_events(events_dir)
        assert lock_path.exists()

    def test_append_after_drain_not_lost(self, events_dir: Path) -> None:
        """An event appended immediately after drain is not lost (#938).

        Before the fix, append_event could lock the old inode (pre-rename)
        and write to an unlinked file.  With the dedicated lock file, both
        sides lock the same object regardless of renames.
        """
        # Populate and drain
        for i in range(3):
            append_event("task_completed", "test", "ops", {"i": i}, events_dir)
        drained = drain_events(events_dir)
        assert drained == 3

        # Append immediately after drain
        append_event("ci_failure", "post-drain", "ops", {"survived": True}, events_dir)

        # The post-drain event must be readable
        events = read_events(events_dir)
        assert len(events) == 1
        assert events[0]["payload"]["survived"] is True
