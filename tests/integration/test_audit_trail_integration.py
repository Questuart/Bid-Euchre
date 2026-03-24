"""Integration tests for the remote exchange audit trail (Platform-8b, SP-4-06 PR 4).

Tests end-to-end round trips, concurrent writers, large-volume throughput,
and mixed-direction filtering across the full audit trail stack.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.audit_trail import (
    append_record,
    audit_edit,
    audit_inbound,
    audit_react,
    audit_reply,
    content_hash,
    create_record,
    read_records,
)

# ---------------------------------------------------------------------------
# 1. Full round-trip: inbound → outbound → read_records → verify sequence
# ---------------------------------------------------------------------------


class TestFullRoundTrip:
    """End-to-end conversation flow: inbound message → outbound reply → verify."""

    def test_inbound_then_reply_sequence(self, tmp_path: Path) -> None:
        """Simulates an operator question followed by an orchestrator reply."""
        # Operator sends a message
        inbound_rec = audit_inbound(
            chat_id="8122530898",
            message_id="100",
            user="operator",
            content="What's the fleet status?",
            ts="2026-03-24T10:00:00+00:00",
            audit_dir=tmp_path,
        )

        # Orchestrator replies
        outbound_rec = audit_reply(
            chat_id="8122530898",
            body="All 12 lanes nominal. 3 PRs in review.",
            reply_to="100",
            audit_dir=tmp_path,
        )

        # Read back all records
        records = read_records(audit_dir=tmp_path)
        assert len(records) == 2

        # Verify chronological order
        assert records[0].exchange_id == inbound_rec.exchange_id
        assert records[1].exchange_id == outbound_rec.exchange_id

        # Verify directions
        assert records[0].direction == "inbound"
        assert records[1].direction == "outbound"

        # Verify content hashes are distinct
        assert records[0].content_hash != records[1].content_hash

        # Verify reply metadata links back to original message
        assert records[1].metadata.get("reply_to") == "100"

    def test_multi_turn_conversation(self, tmp_path: Path) -> None:
        """Multi-turn conversation with mixed exchange types."""
        # Turn 1: operator asks
        audit_inbound(
            chat_id="123",
            message_id="1",
            user="operator",
            content="Deploy status?",
            ts="2026-03-24T10:00:00+00:00",
            audit_dir=tmp_path,
        )

        # Turn 2: orchestrator acknowledges with reaction
        audit_react(
            chat_id="123",
            message_id="1",
            emoji="👀",
            audit_dir=tmp_path,
        )

        # Turn 3: orchestrator replies
        audit_reply(
            chat_id="123",
            body="Checking now...",
            reply_to="1",
            audit_dir=tmp_path,
        )

        # Turn 4: orchestrator edits the reply with the actual status
        audit_edit(
            chat_id="123",
            message_id="2",
            body="All clear — 0 stalled lanes, CI green.",
            audit_dir=tmp_path,
        )

        # Turn 5: operator follows up
        audit_inbound(
            chat_id="123",
            message_id="3",
            user="operator",
            content="Great, thanks!",
            ts="2026-03-24T10:05:00+00:00",
            audit_dir=tmp_path,
        )

        records = read_records(audit_dir=tmp_path)
        assert len(records) == 5

        # Verify the exchange type sequence
        expected_types = ["message", "react", "reply", "edit", "message"]
        assert [r.exchange_type for r in records] == expected_types

        # Verify direction sequence
        expected_dirs = ["inbound", "outbound", "outbound", "outbound", "inbound"]
        assert [r.direction for r in records] == expected_dirs

    def test_round_trip_serialization_integrity(self, tmp_path: Path) -> None:
        """Verify that records survive the full write → JSONL → read cycle."""
        original = audit_inbound(
            chat_id="999",
            message_id="42",
            user="test_user",
            content="Serialization test with special chars: <>&\"'",
            metadata={"attachment_file_id": "abc123"},
            ts="2026-03-24T12:00:00+00:00",
            audit_dir=tmp_path,
        )

        # Read back and compare
        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1
        restored = records[0]

        # All fields must match
        assert restored.exchange_id == original.exchange_id
        assert restored.timestamp == original.timestamp
        assert restored.direction == original.direction
        assert restored.channel_source == original.channel_source
        assert restored.sender_identity == original.sender_identity
        assert restored.exchange_type == original.exchange_type
        assert restored.content_hash == original.content_hash
        assert restored.content_preview == original.content_preview
        assert restored.chat_id == original.chat_id
        assert restored.message_id == original.message_id
        assert restored.metadata == original.metadata

    def test_round_trip_content_hash_verifiable(self, tmp_path: Path) -> None:
        """Content hash stored in the record matches recomputation."""
        msg = "Verify hash integrity across the full pipeline"
        rec = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user",
            content=msg,
            audit_dir=tmp_path,
        )

        records = read_records(audit_dir=tmp_path)
        assert records[0].content_hash == content_hash(msg)
        assert records[0].content_hash == rec.content_hash


# ---------------------------------------------------------------------------
# 2. Concurrent writers: multiple threads → verify no data loss
# ---------------------------------------------------------------------------


class TestConcurrentWriters:
    """Verify flock-based concurrent write safety at integration level."""

    def test_concurrent_mixed_writers(self, tmp_path: Path) -> None:
        """Multiple threads using different wrapper functions simultaneously."""
        n_threads = 8
        n_per_thread = 25
        total_expected = n_threads * n_per_thread
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(n_per_thread):
                    # Rotate through all 4 wrapper functions
                    variant = i % 4
                    if variant == 0:
                        audit_inbound(
                            chat_id="123",
                            message_id=f"t{thread_id}-m{i}",
                            user=f"thread-{thread_id}",
                            content=f"Inbound from thread {thread_id} msg {i}",
                            audit_dir=tmp_path,
                        )
                    elif variant == 1:
                        audit_reply(
                            chat_id="123",
                            body=f"Reply from thread {thread_id} msg {i}",
                            audit_dir=tmp_path,
                        )
                    elif variant == 2:
                        audit_react(
                            chat_id="123",
                            message_id=f"t{thread_id}-m{i}",
                            emoji="👍",
                            audit_dir=tmp_path,
                        )
                    else:
                        audit_edit(
                            chat_id="123",
                            message_id=f"t{thread_id}-m{i}",
                            body=f"Edit from thread {thread_id} msg {i}",
                            audit_dir=tmp_path,
                        )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent writes produced errors: {errors}"

        # Verify all records present
        records = read_records(audit_dir=tmp_path)
        assert len(records) == total_expected

        # Verify JSONL file integrity — every line must be valid JSON
        jsonl_path = tmp_path / "remote_exchanges.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == total_expected
        for line_no, line in enumerate(lines, 1):
            try:
                json.loads(line)
            except json.JSONDecodeError:
                pytest.fail(f"Corrupted JSONL at line {line_no}: {line!r}")

    def test_concurrent_writers_unique_ids(self, tmp_path: Path) -> None:
        """All records from concurrent writes have unique exchange_ids."""
        n_threads = 6
        n_per_thread = 20
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(n_per_thread):
                    audit_inbound(
                        chat_id="123",
                        message_id=f"t{thread_id}-{i}",
                        user=f"thread-{thread_id}",
                        content=f"Message {i} from thread {thread_id}",
                        audit_dir=tmp_path,
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

        records = read_records(audit_dir=tmp_path)
        ids = [r.exchange_id for r in records]
        assert len(ids) == len(set(ids)), "Duplicate exchange_ids found"

    def test_concurrent_readers_and_writers(self, tmp_path: Path) -> None:
        """Readers operating concurrently with writers should not crash."""
        n_writers = 4
        n_per_writer = 20
        n_readers = 3
        read_results: list[int] = []
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(n_per_writer):
                    audit_inbound(
                        chat_id="123",
                        message_id=f"t{thread_id}-{i}",
                        user=f"writer-{thread_id}",
                        content=f"Msg {i}",
                        audit_dir=tmp_path,
                    )
            except Exception as exc:
                errors.append(exc)

        def reader(_reader_id: int) -> None:
            try:
                # Small delay to let some writes happen first
                time.sleep(0.01)
                records = read_records(audit_dir=tmp_path)
                read_results.append(len(records))
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(t,)) for t in range(n_writers)
        ] + [threading.Thread(target=reader, args=(r,)) for r in range(n_readers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent read/write errors: {errors}"
        # Readers should have gotten some non-negative count
        assert all(r >= 0 for r in read_results)

        # Final read should have all records
        final_records = read_records(audit_dir=tmp_path)
        assert len(final_records) == n_writers * n_per_writer


# ---------------------------------------------------------------------------
# 3. Large-volume test: 1000+ records → verify read performance
# ---------------------------------------------------------------------------


class TestLargeVolume:
    """Verify the audit trail handles large volumes without data loss or corruption."""

    def test_1000_records_write_and_read(self, tmp_path: Path) -> None:
        """Write 1000+ records and verify all are readable and intact."""
        n_records = 1200

        written_ids: list[str] = []
        for i in range(n_records):
            if i % 2 == 0:
                rec = audit_inbound(
                    chat_id="123",
                    message_id=str(i),
                    user="bulk_user",
                    content=f"Bulk message number {i}",
                    audit_dir=tmp_path,
                )
            else:
                rec = audit_reply(
                    chat_id="123",
                    body=f"Bulk reply number {i}",
                    audit_dir=tmp_path,
                )
            written_ids.append(rec.exchange_id)

        # Read all records back
        records = read_records(audit_dir=tmp_path)
        assert len(records) == n_records

        # Verify all IDs match
        read_ids = [r.exchange_id for r in records]
        assert read_ids == written_ids

        # Verify no duplicate IDs
        assert len(set(read_ids)) == n_records

    def test_large_volume_filtering_performance(self, tmp_path: Path) -> None:
        """Filtered reads on large volumes should return correct subsets."""
        n_inbound = 600
        n_outbound = 400
        total = n_inbound + n_outbound

        for i in range(n_inbound):
            audit_inbound(
                chat_id="123",
                message_id=str(i),
                user="user",
                content=f"Inbound {i}",
                audit_dir=tmp_path,
            )
        for i in range(n_outbound):
            audit_reply(
                chat_id="123",
                body=f"Outbound {i}",
                audit_dir=tmp_path,
            )

        # Unfiltered — all records
        all_records = read_records(audit_dir=tmp_path)
        assert len(all_records) == total

        # Filter inbound only
        inbound = read_records(audit_dir=tmp_path, direction="inbound")
        assert len(inbound) == n_inbound
        assert all(r.direction == "inbound" for r in inbound)

        # Filter outbound only
        outbound = read_records(audit_dir=tmp_path, direction="outbound")
        assert len(outbound) == n_outbound
        assert all(r.direction == "outbound" for r in outbound)

    def test_large_volume_limit(self, tmp_path: Path) -> None:
        """Limit parameter works correctly on large datasets."""
        n_records = 500
        for i in range(n_records):
            audit_inbound(
                chat_id="123",
                message_id=str(i),
                user="user",
                content=f"Msg {i}",
                audit_dir=tmp_path,
            )

        # Read with limit
        limited = read_records(audit_dir=tmp_path, limit=10)
        assert len(limited) == 10

        # Should be the last 10 records
        all_records = read_records(audit_dir=tmp_path)
        assert limited == all_records[-10:]

    def test_large_volume_jsonl_integrity(self, tmp_path: Path) -> None:
        """Every line in the JSONL file is valid JSON after large-volume writes."""
        n_records = 1000

        for i in range(n_records):
            record = create_record(
                direction="inbound" if i % 3 != 0 else "outbound",
                channel_source="telegram",
                sender_identity=f"user_{i % 10}",
                exchange_type="message" if i % 3 != 0 else "reply",
                content=f"Record {i}: {'x' * (i % 50)}",
                chat_id=str(100 + i % 5),
                message_id=str(i),
            )
            append_record(record, audit_dir=tmp_path)

        jsonl_path = tmp_path / "remote_exchanges.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == n_records

        for line_no, line in enumerate(lines, 1):
            try:
                data = json.loads(line)
                # Every record must have required fields
                assert "exchange_id" in data
                assert "direction" in data
                assert "content_hash" in data
            except json.JSONDecodeError:
                pytest.fail(f"Corrupted JSONL at line {line_no}: {line!r}")


# ---------------------------------------------------------------------------
# 4. Mixed direction filtering: inbound + outbound → filter → verify
# ---------------------------------------------------------------------------


class TestMixedDirectionFiltering:
    """Verify filtering by direction, channel source, time, and combinations."""

    @pytest.fixture()
    def mixed_log(self, tmp_path: Path) -> Path:
        """Populate an audit log with a realistic mixed conversation."""
        # Simulate a conversation with interleaved directions
        exchanges = [
            # (direction, wrapper_func, kwargs)
            (
                "inbound",
                "audit_inbound",
                {
                    "chat_id": "8122530898",
                    "message_id": "1",
                    "user": "operator",
                    "content": "Morning status check",
                    "ts": "2026-03-24T08:00:00+00:00",
                },
            ),
            (
                "outbound",
                "audit_react",
                {
                    "chat_id": "8122530898",
                    "message_id": "1",
                    "emoji": "👀",
                },
            ),
            (
                "outbound",
                "audit_reply",
                {
                    "chat_id": "8122530898",
                    "body": "Good morning! Fleet status: 12/12 lanes up.",
                    "reply_to": "1",
                },
            ),
            (
                "inbound",
                "audit_inbound",
                {
                    "chat_id": "8122530898",
                    "message_id": "2",
                    "user": "operator",
                    "content": "Any stalled PRs?",
                    "ts": "2026-03-24T08:01:00+00:00",
                },
            ),
            (
                "outbound",
                "audit_reply",
                {
                    "chat_id": "8122530898",
                    "body": "PR #1542 has been in review for 45min. Nudging.",
                },
            ),
            (
                "outbound",
                "audit_edit",
                {
                    "chat_id": "8122530898",
                    "message_id": "5",
                    "body": "PR #1542 review complete — merging now.",
                },
            ),
            (
                "inbound",
                "audit_inbound",
                {
                    "chat_id": "8122530898",
                    "message_id": "3",
                    "user": "operator",
                    "content": "Perfect. Stepping away for an hour.",
                    "ts": "2026-03-24T08:05:00+00:00",
                },
            ),
        ]

        for _, func_name, kwargs in exchanges:
            func = {
                "audit_inbound": audit_inbound,
                "audit_reply": audit_reply,
                "audit_react": audit_react,
                "audit_edit": audit_edit,
            }[func_name]
            func(audit_dir=tmp_path, **kwargs)

        return tmp_path

    def test_total_record_count(self, mixed_log: Path) -> None:
        """All 7 records present in the log."""
        records = read_records(audit_dir=mixed_log)
        assert len(records) == 7

    def test_filter_inbound_only(self, mixed_log: Path) -> None:
        """Filter returns only inbound records."""
        inbound = read_records(audit_dir=mixed_log, direction="inbound")
        assert len(inbound) == 3
        assert all(r.direction == "inbound" for r in inbound)
        assert all(r.exchange_type == "message" for r in inbound)
        assert all(r.sender_identity == "operator" for r in inbound)

    def test_filter_outbound_only(self, mixed_log: Path) -> None:
        """Filter returns only outbound records."""
        outbound = read_records(audit_dir=mixed_log, direction="outbound")
        assert len(outbound) == 4
        assert all(r.direction == "outbound" for r in outbound)
        # Verify all 3 outbound types present
        types = {r.exchange_type for r in outbound}
        assert types == {"reply", "react", "edit"}

    def test_filter_by_channel_source(self, mixed_log: Path) -> None:
        """All records are telegram; filtering by discord returns empty."""
        telegram = read_records(audit_dir=mixed_log, channel_source="telegram")
        assert len(telegram) == 7

        discord = read_records(audit_dir=mixed_log, channel_source="discord")
        assert len(discord) == 0

    def test_filter_by_time_range(self, mixed_log: Path) -> None:
        """Time-based filtering works for inbound records with explicit timestamps."""
        since = datetime(2026, 3, 24, 8, 1, 0, tzinfo=timezone.utc)
        recent = read_records(audit_dir=mixed_log, since=since)
        # Inbound at 08:01 and 08:05 pass the filter; outbound records with
        # auto-generated timestamps (current time) also pass since they're
        # after the 'since' cutoff.
        # The key assertion: at minimum the 2 later inbound records are present
        inbound_recent = [r for r in recent if r.direction == "inbound"]
        assert len(inbound_recent) >= 2

    def test_combined_direction_and_time(self, mixed_log: Path) -> None:
        """Combined direction + time filter narrows correctly."""
        since = datetime(2026, 3, 24, 8, 2, 0, tzinfo=timezone.utc)
        inbound_recent = read_records(
            audit_dir=mixed_log,
            direction="inbound",
            since=since,
        )
        # Only the 08:05 inbound message passes both filters
        assert len(inbound_recent) == 1
        assert (
            inbound_recent[0].content_preview == "Perfect. Stepping away for an hour."
        )

    def test_limit_with_direction_filter(self, mixed_log: Path) -> None:
        """Limit applies after direction filtering."""
        outbound = read_records(audit_dir=mixed_log, direction="outbound", limit=2)
        assert len(outbound) == 2
        # Should be the last 2 outbound records
        all_outbound = read_records(audit_dir=mixed_log, direction="outbound")
        assert outbound == all_outbound[-2:]

    def test_multi_chat_filtering(self, tmp_path: Path) -> None:
        """Records from different chats can coexist and be filtered."""
        # Chat A
        audit_inbound(
            chat_id="111",
            message_id="1",
            user="alice",
            content="Hello from chat A",
            audit_dir=tmp_path,
        )
        audit_reply(
            chat_id="111",
            body="Reply to chat A",
            audit_dir=tmp_path,
        )

        # Chat B
        audit_inbound(
            chat_id="222",
            message_id="1",
            user="bob",
            content="Hello from chat B",
            audit_dir=tmp_path,
        )

        all_records = read_records(audit_dir=tmp_path)
        assert len(all_records) == 3

        # read_records doesn't filter by chat_id directly, but we can verify
        # records from both chats are present
        chat_ids = {r.chat_id for r in all_records}
        assert chat_ids == {"111", "222"}

    def test_multi_channel_source_filtering(self, tmp_path: Path) -> None:
        """Records from different channel sources can be filtered."""
        # Telegram inbound
        audit_inbound(
            chat_id="123",
            message_id="1",
            user="tg_user",
            content="From Telegram",
            channel_source="telegram",
            audit_dir=tmp_path,
        )

        # Discord inbound (future-proofing)
        audit_inbound(
            chat_id="456",
            message_id="1",
            user="dc_user",
            content="From Discord",
            channel_source="discord",
            audit_dir=tmp_path,
        )

        all_records = read_records(audit_dir=tmp_path)
        assert len(all_records) == 2

        telegram_only = read_records(audit_dir=tmp_path, channel_source="telegram")
        assert len(telegram_only) == 1
        assert telegram_only[0].sender_identity == "tg_user"

        discord_only = read_records(audit_dir=tmp_path, channel_source="discord")
        assert len(discord_only) == 1
        assert discord_only[0].sender_identity == "dc_user"
