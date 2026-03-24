"""Unit tests for the remote exchange audit trail (Platform-8b, SP-4-06)."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.audit_trail import (
    VALID_DIRECTIONS,
    VALID_EXCHANGE_TYPES,
    AuditRecord,
    append_record,
    audit_edit,
    audit_inbound,
    audit_react,
    audit_reply,
    content_hash,
    content_preview,
    create_record,
    normalize_timestamp,
    parse_channel_tag,
    read_records,
)

# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_deterministic(self) -> None:
        """Same input always produces same hash."""
        assert content_hash("hello") == content_hash("hello")

    def test_known_value(self) -> None:
        """Verify against known SHA-256 digest."""
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        assert content_hash("hello") == expected

    def test_different_inputs(self) -> None:
        """Different inputs produce different hashes."""
        assert content_hash("hello") != content_hash("world")

    def test_empty_string(self) -> None:
        """Empty string is hashable."""
        h = content_hash("")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex length


# ---------------------------------------------------------------------------
# content_preview
# ---------------------------------------------------------------------------


class TestContentPreview:
    def test_short_text_unchanged(self) -> None:
        assert content_preview("short") == "short"

    def test_exact_limit(self) -> None:
        text = "x" * 200
        assert content_preview(text) == text  # No truncation

    def test_truncation(self) -> None:
        text = "x" * 300
        result = content_preview(text)
        assert result == "x" * 200 + "…"
        assert len(result) == 201  # 200 chars + ellipsis

    def test_custom_limit(self) -> None:
        text = "hello world"
        result = content_preview(text, max_len=5)
        assert result == "hello…"

    def test_empty_string(self) -> None:
        assert content_preview("") == ""


# ---------------------------------------------------------------------------
# AuditRecord
# ---------------------------------------------------------------------------


class TestAuditRecord:
    def _make_record(self, **overrides: object) -> AuditRecord:
        defaults = {
            "exchange_id": "test-id-1234",
            "timestamp": "2026-03-24T06:00:00+00:00",
            "direction": "inbound",
            "channel_source": "telegram",
            "sender_identity": "user123",
            "exchange_type": "message",
            "content_hash": content_hash("test message"),
            "content_preview": "test message",
            "chat_id": "8122530898",
            "message_id": "42",
            "metadata": {},
        }
        defaults.update(overrides)
        return AuditRecord(**defaults)

    def test_frozen(self) -> None:
        record = self._make_record()
        with pytest.raises(AttributeError):
            record.direction = "outbound"  # type: ignore[misc]

    def test_valid_directions(self) -> None:
        for d in VALID_DIRECTIONS:
            record = self._make_record(direction=d)
            assert record.direction == d

    def test_invalid_direction(self) -> None:
        with pytest.raises(ValueError, match="Invalid direction"):
            self._make_record(direction="sideways")

    def test_valid_exchange_types(self) -> None:
        for et in VALID_EXCHANGE_TYPES:
            record = self._make_record(exchange_type=et)
            assert record.exchange_type == et

    def test_invalid_exchange_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid exchange_type"):
            self._make_record(exchange_type="teleport")

    def test_message_id_optional(self) -> None:
        record = self._make_record(message_id=None)
        assert record.message_id is None

    def test_metadata_default_empty(self) -> None:
        record = AuditRecord(
            exchange_id="id",
            timestamp="2026-01-01T00:00:00+00:00",
            direction="inbound",
            channel_source="telegram",
            sender_identity="user",
            exchange_type="message",
            content_hash="abc",
            content_preview="hello",
            chat_id="123",
        )
        assert record.metadata == {}

    def test_serialization_round_trip(self) -> None:
        original = self._make_record(metadata={"reply_to": "99", "extra": True})
        d = original.to_dict()
        restored = AuditRecord.from_dict(d)
        assert restored == original

    def test_to_dict_types(self) -> None:
        record = self._make_record()
        d = record.to_dict()
        assert isinstance(d, dict)
        assert d["exchange_id"] == "test-id-1234"
        assert d["direction"] == "inbound"
        assert d["metadata"] == {}


# ---------------------------------------------------------------------------
# create_record helper
# ---------------------------------------------------------------------------


class TestCreateRecord:
    def test_auto_fields(self) -> None:
        record = create_record(
            direction="outbound",
            channel_source="telegram",
            sender_identity="orchestrator",
            exchange_type="reply",
            content="Hello operator!",
            chat_id="8122530898",
        )
        # Auto-generated fields
        assert len(record.exchange_id) == 36  # UUID4
        assert record.timestamp  # Non-empty
        assert record.content_hash == content_hash("Hello operator!")
        assert record.content_preview == "Hello operator!"
        assert record.metadata == {}

    def test_explicit_timestamp(self) -> None:
        ts = "2026-03-24T12:00:00+00:00"
        record = create_record(
            direction="inbound",
            channel_source="telegram",
            sender_identity="user",
            exchange_type="message",
            content="test",
            chat_id="123",
            timestamp=ts,
        )
        assert record.timestamp == ts

    def test_with_metadata(self) -> None:
        meta = {"reply_to": "42", "files": ["/tmp/photo.jpg"]}
        record = create_record(
            direction="outbound",
            channel_source="telegram",
            sender_identity="orchestrator",
            exchange_type="reply",
            content="See attachment",
            chat_id="123",
            metadata=meta,
        )
        assert record.metadata == meta


# ---------------------------------------------------------------------------
# append_record + read_records
# ---------------------------------------------------------------------------


class TestAppendAndRead:
    def test_append_and_read(self, tmp_path: Path) -> None:
        record = create_record(
            direction="inbound",
            channel_source="telegram",
            sender_identity="user123",
            exchange_type="message",
            content="Hello bot",
            chat_id="8122530898",
            message_id="1",
        )
        append_record(record, audit_dir=tmp_path)

        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1
        assert records[0] == record

    def test_multiple_records(self, tmp_path: Path) -> None:
        for i in range(5):
            record = create_record(
                direction="inbound" if i % 2 == 0 else "outbound",
                channel_source="telegram",
                sender_identity="user" if i % 2 == 0 else "orchestrator",
                exchange_type="message" if i % 2 == 0 else "reply",
                content=f"Message {i}",
                chat_id="123",
                message_id=str(i),
            )
            append_record(record, audit_dir=tmp_path)

        records = read_records(audit_dir=tmp_path)
        assert len(records) == 5

    def test_empty_log(self, tmp_path: Path) -> None:
        records = read_records(audit_dir=tmp_path)
        assert records == []

    def test_jsonl_format(self, tmp_path: Path) -> None:
        record = create_record(
            direction="outbound",
            channel_source="telegram",
            sender_identity="orchestrator",
            exchange_type="reply",
            content="hi",
            chat_id="123",
        )
        append_record(record, audit_dir=tmp_path)

        jsonl_path = tmp_path / "remote_exchanges.jsonl"
        assert jsonl_path.exists()

        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["direction"] == "outbound"
        assert data["exchange_type"] == "reply"

    def test_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "audit"
        record = create_record(
            direction="inbound",
            channel_source="telegram",
            sender_identity="user",
            exchange_type="message",
            content="test",
            chat_id="123",
        )
        append_record(record, audit_dir=nested)

        records = read_records(audit_dir=nested)
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


class TestFiltering:
    @pytest.fixture()
    def populated_dir(self, tmp_path: Path) -> Path:
        """Create an audit dir with mixed inbound/outbound records."""
        records_data = [
            (
                "inbound",
                "telegram",
                "user1",
                "message",
                "Hello",
                "2026-03-24T01:00:00+00:00",
            ),
            (
                "outbound",
                "telegram",
                "orchestrator",
                "reply",
                "Hi there",
                "2026-03-24T02:00:00+00:00",
            ),
            (
                "inbound",
                "telegram",
                "user1",
                "message",
                "Status?",
                "2026-03-24T03:00:00+00:00",
            ),
            (
                "outbound",
                "telegram",
                "orchestrator",
                "react",
                "👍",
                "2026-03-24T04:00:00+00:00",
            ),
            (
                "outbound",
                "telegram",
                "orchestrator",
                "reply",
                "All good",
                "2026-03-24T05:00:00+00:00",
            ),
        ]
        for direction, source, sender, etype, content, ts in records_data:
            record = create_record(
                direction=direction,
                channel_source=source,
                sender_identity=sender,
                exchange_type=etype,
                content=content,
                chat_id="123",
                timestamp=ts,
            )
            append_record(record, audit_dir=tmp_path)
        return tmp_path

    def test_filter_by_direction_inbound(self, populated_dir: Path) -> None:
        records = read_records(audit_dir=populated_dir, direction="inbound")
        assert len(records) == 2
        assert all(r.direction == "inbound" for r in records)

    def test_filter_by_direction_outbound(self, populated_dir: Path) -> None:
        records = read_records(audit_dir=populated_dir, direction="outbound")
        assert len(records) == 3
        assert all(r.direction == "outbound" for r in records)

    def test_filter_by_channel_source(self, populated_dir: Path) -> None:
        records = read_records(audit_dir=populated_dir, channel_source="telegram")
        assert len(records) == 5  # All are telegram

        records = read_records(audit_dir=populated_dir, channel_source="discord")
        assert len(records) == 0

    def test_filter_by_since(self, populated_dir: Path) -> None:
        since = datetime(2026, 3, 24, 3, 0, 0, tzinfo=timezone.utc)
        records = read_records(audit_dir=populated_dir, since=since)
        assert len(records) == 3  # Records at 03:00, 04:00, 05:00

    def test_filter_combined(self, populated_dir: Path) -> None:
        since = datetime(2026, 3, 24, 2, 0, 0, tzinfo=timezone.utc)
        records = read_records(
            audit_dir=populated_dir,
            direction="outbound",
            since=since,
        )
        assert len(records) == 3  # Outbound at 02:00, 04:00, 05:00

    def test_limit(self, populated_dir: Path) -> None:
        records = read_records(audit_dir=populated_dir, limit=2)
        assert len(records) == 2
        # Should be the last 2 records (most recent)
        assert records[0].content_preview == "👍"  # 04:00
        assert records[1].content_preview == "All good"  # 05:00

    def test_limit_larger_than_total(self, populated_dir: Path) -> None:
        records = read_records(audit_dir=populated_dir, limit=100)
        assert len(records) == 5


# ---------------------------------------------------------------------------
# Concurrent-write safety (flock)
# ---------------------------------------------------------------------------


class TestConcurrentWrite:
    def test_concurrent_appends(self, tmp_path: Path) -> None:
        """Multiple threads writing simultaneously should not corrupt the file."""
        n_threads = 10
        n_per_thread = 20
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(n_per_thread):
                    record = create_record(
                        direction="outbound",
                        channel_source="telegram",
                        sender_identity=f"thread-{thread_id}",
                        exchange_type="reply",
                        content=f"Thread {thread_id} message {i}",
                        chat_id="123",
                        message_id=f"{thread_id}-{i}",
                    )
                    append_record(record, audit_dir=tmp_path)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent writes produced errors: {errors}"

        # Verify all records are present and parseable
        records = read_records(audit_dir=tmp_path)
        assert len(records) == n_threads * n_per_thread

        # Verify JSONL file is not corrupted (each line is valid JSON)
        jsonl_path = tmp_path / "remote_exchanges.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == n_threads * n_per_thread
        for line_no, line in enumerate(lines, 1):
            try:
                json.loads(line)
            except json.JSONDecodeError:
                pytest.fail(f"Corrupted JSONL at line {line_no}: {line!r}")


# ---------------------------------------------------------------------------
# Malformed data resilience
# ---------------------------------------------------------------------------


class TestMalformedData:
    def test_malformed_jsonl_skipped(self, tmp_path: Path) -> None:
        """Malformed lines in the JSONL file are skipped gracefully."""
        jsonl_path = tmp_path / "remote_exchanges.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        # Write a valid record, a corrupt line, and another valid record
        valid_record = create_record(
            direction="inbound",
            channel_source="telegram",
            sender_identity="user",
            exchange_type="message",
            content="valid",
            chat_id="123",
            timestamp="2026-03-24T01:00:00+00:00",
        )
        with open(jsonl_path, "w") as f:
            f.write(json.dumps(valid_record.to_dict(), sort_keys=True) + "\n")
            f.write("THIS IS NOT JSON\n")
            f.write(json.dumps(valid_record.to_dict(), sort_keys=True) + "\n")

        records = read_records(audit_dir=tmp_path)
        # Both valid records should parse (they have the same exchange_id so
        # they'll both come back); the corrupt line is skipped.
        assert len(records) == 2

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        jsonl_path = tmp_path / "remote_exchanges.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        valid_record = create_record(
            direction="inbound",
            channel_source="telegram",
            sender_identity="user",
            exchange_type="message",
            content="valid",
            chat_id="123",
        )
        with open(jsonl_path, "w") as f:
            f.write("\n\n")
            f.write(json.dumps(valid_record.to_dict(), sort_keys=True) + "\n")
            f.write("\n")

        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Outbound audit wrappers (SP-4-06 PR 2)
# ---------------------------------------------------------------------------


class TestAuditReply:
    def test_basic_reply(self, tmp_path: Path) -> None:
        record = audit_reply(
            chat_id="8122530898",
            body="Hello operator!",
            audit_dir=tmp_path,
        )
        assert record.direction == "outbound"
        assert record.exchange_type == "reply"
        assert record.channel_source == "telegram"
        assert record.sender_identity == "orchestrator"
        assert record.chat_id == "8122530898"
        assert record.content_hash == content_hash("Hello operator!")
        assert record.content_preview == "Hello operator!"
        assert record.metadata == {}

    def test_reply_with_reply_to(self, tmp_path: Path) -> None:
        record = audit_reply(
            chat_id="123",
            body="Got it",
            reply_to="42",
            audit_dir=tmp_path,
        )
        assert record.metadata["reply_to"] == "42"

    def test_reply_with_files(self, tmp_path: Path) -> None:
        record = audit_reply(
            chat_id="123",
            body="See attached",
            files=["/tmp/photo.jpg", "/tmp/doc.pdf"],
            audit_dir=tmp_path,
        )
        assert record.metadata["files"] == ["/tmp/photo.jpg", "/tmp/doc.pdf"]

    def test_reply_with_reply_to_and_files(self, tmp_path: Path) -> None:
        record = audit_reply(
            chat_id="123",
            body="Here you go",
            reply_to="99",
            files=["/tmp/report.pdf"],
            audit_dir=tmp_path,
        )
        assert record.metadata["reply_to"] == "99"
        assert record.metadata["files"] == ["/tmp/report.pdf"]

    def test_reply_persisted(self, tmp_path: Path) -> None:
        """Verify the record is actually appended to the JSONL file."""
        audit_reply(chat_id="123", body="test", audit_dir=tmp_path)
        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1
        assert records[0].exchange_type == "reply"
        assert records[0].direction == "outbound"

    def test_reply_returns_record(self, tmp_path: Path) -> None:
        """audit_reply returns the same record that was persisted."""
        returned = audit_reply(chat_id="123", body="check", audit_dir=tmp_path)
        persisted = read_records(audit_dir=tmp_path)
        assert len(persisted) == 1
        assert returned == persisted[0]

    def test_reply_long_body_preview_truncated(self, tmp_path: Path) -> None:
        long_body = "x" * 500
        record = audit_reply(chat_id="123", body=long_body, audit_dir=tmp_path)
        assert record.content_preview == "x" * 200 + "…"
        assert record.content_hash == content_hash(long_body)


class TestAuditReact:
    def test_basic_react(self, tmp_path: Path) -> None:
        record = audit_react(
            chat_id="8122530898",
            message_id="42",
            emoji="👍",
            audit_dir=tmp_path,
        )
        assert record.direction == "outbound"
        assert record.exchange_type == "react"
        assert record.channel_source == "telegram"
        assert record.sender_identity == "orchestrator"
        assert record.chat_id == "8122530898"
        assert record.message_id == "42"
        assert record.metadata["emoji"] == "👍"
        assert record.content_hash == content_hash("👍")
        assert record.content_preview == "👍"

    def test_react_persisted(self, tmp_path: Path) -> None:
        audit_react(chat_id="123", message_id="10", emoji="🎉", audit_dir=tmp_path)
        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1
        assert records[0].exchange_type == "react"
        assert records[0].metadata["emoji"] == "🎉"

    def test_react_returns_record(self, tmp_path: Path) -> None:
        returned = audit_react(
            chat_id="123", message_id="10", emoji="✅", audit_dir=tmp_path
        )
        persisted = read_records(audit_dir=tmp_path)
        assert len(persisted) == 1
        assert returned == persisted[0]


class TestAuditEdit:
    def test_basic_edit(self, tmp_path: Path) -> None:
        record = audit_edit(
            chat_id="8122530898",
            message_id="42",
            body="Updated message text",
            audit_dir=tmp_path,
        )
        assert record.direction == "outbound"
        assert record.exchange_type == "edit"
        assert record.channel_source == "telegram"
        assert record.sender_identity == "orchestrator"
        assert record.chat_id == "8122530898"
        assert record.message_id == "42"
        assert record.content_hash == content_hash("Updated message text")
        assert record.content_preview == "Updated message text"

    def test_edit_persisted(self, tmp_path: Path) -> None:
        audit_edit(
            chat_id="123",
            message_id="10",
            body="corrected text",
            audit_dir=tmp_path,
        )
        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1
        assert records[0].exchange_type == "edit"
        assert records[0].direction == "outbound"

    def test_edit_returns_record(self, tmp_path: Path) -> None:
        returned = audit_edit(
            chat_id="123",
            message_id="10",
            body="fixed",
            audit_dir=tmp_path,
        )
        persisted = read_records(audit_dir=tmp_path)
        assert len(persisted) == 1
        assert returned == persisted[0]

    def test_edit_long_body_preview_truncated(self, tmp_path: Path) -> None:
        long_body = "y" * 400
        record = audit_edit(
            chat_id="123",
            message_id="5",
            body=long_body,
            audit_dir=tmp_path,
        )
        assert record.content_preview == "y" * 200 + "…"
        assert record.content_hash == content_hash(long_body)


class TestOutboundWrapperIntegration:
    """Cross-wrapper tests verifying they coexist in the same audit log."""

    def test_mixed_outbound_sequence(self, tmp_path: Path) -> None:
        """All three wrapper types write to the same log and can be read back."""
        audit_reply(chat_id="123", body="Hello", audit_dir=tmp_path)
        audit_react(chat_id="123", message_id="1", emoji="👍", audit_dir=tmp_path)
        audit_edit(chat_id="123", message_id="2", body="Updated", audit_dir=tmp_path)

        records = read_records(audit_dir=tmp_path)
        assert len(records) == 3
        types = [r.exchange_type for r in records]
        assert types == ["reply", "react", "edit"]
        assert all(r.direction == "outbound" for r in records)

    def test_outbound_filter(self, tmp_path: Path) -> None:
        """Outbound wrappers can be filtered from a mixed log."""
        # Add an inbound record manually
        inbound = create_record(
            direction="inbound",
            channel_source="telegram",
            sender_identity="user",
            exchange_type="message",
            content="operator says hi",
            chat_id="123",
        )
        append_record(inbound, audit_dir=tmp_path)

        # Add outbound via wrappers
        audit_reply(chat_id="123", body="reply text", audit_dir=tmp_path)
        audit_react(chat_id="123", message_id="1", emoji="🎉", audit_dir=tmp_path)

        all_records = read_records(audit_dir=tmp_path)
        assert len(all_records) == 3

        outbound = read_records(audit_dir=tmp_path, direction="outbound")
        assert len(outbound) == 2
        assert all(r.direction == "outbound" for r in outbound)


# ---------------------------------------------------------------------------
# parse_channel_tag (SP-4-06 PR 3)
# ---------------------------------------------------------------------------


class TestParseChannelTag:
    def test_valid_tag(self) -> None:
        tag = '<channel source="telegram" chat_id="123" message_id="42" user="alice" ts="2026-03-24T06:00:00Z">'
        result = parse_channel_tag(tag)
        assert result == {
            "source": "telegram",
            "chat_id": "123",
            "message_id": "42",
            "user": "alice",
            "ts": "2026-03-24T06:00:00Z",
        }

    def test_self_closing_tag(self) -> None:
        tag = '<channel source="telegram" chat_id="999" />'
        result = parse_channel_tag(tag)
        assert result["source"] == "telegram"
        assert result["chat_id"] == "999"

    def test_minimal_tag(self) -> None:
        """Tag with only source attribute."""
        tag = '<channel source="telegram">'
        result = parse_channel_tag(tag)
        assert result == {"source": "telegram"}

    def test_missing_attributes_handled_gracefully(self) -> None:
        """Tag with fewer attributes than expected returns only what's present."""
        tag = '<channel source="telegram" chat_id="123">'
        result = parse_channel_tag(tag)
        assert result == {"source": "telegram", "chat_id": "123"}
        # Missing keys are simply absent, not errored
        assert "message_id" not in result
        assert "user" not in result
        assert "ts" not in result

    def test_not_a_channel_tag(self) -> None:
        """Non-channel tag returns empty dict."""
        assert parse_channel_tag("<div>hello</div>") == {}
        assert parse_channel_tag("plain text") == {}
        assert parse_channel_tag("") == {}

    def test_whitespace_handling(self) -> None:
        """Leading/trailing whitespace is stripped before parsing."""
        tag = '  <channel source="telegram" chat_id="42">  '
        result = parse_channel_tag(tag)
        assert result["source"] == "telegram"
        assert result["chat_id"] == "42"

    def test_multiline_tag(self) -> None:
        """Tag split across multiple lines."""
        tag = (
            '<channel source="telegram"\n'
            '         chat_id="123"\n'
            '         message_id="42"\n'
            '         user="bob"\n'
            '         ts="2026-03-24T12:00:00Z">'
        )
        result = parse_channel_tag(tag)
        assert result["source"] == "telegram"
        assert result["chat_id"] == "123"
        assert result["message_id"] == "42"
        assert result["user"] == "bob"

    def test_extra_attributes(self) -> None:
        """Unknown attributes are still extracted."""
        tag = '<channel source="telegram" chat_id="123" image_path="/tmp/photo.jpg">'
        result = parse_channel_tag(tag)
        assert result["image_path"] == "/tmp/photo.jpg"

    def test_body_text_not_parsed_as_attributes(self) -> None:
        """Quoted key=value patterns in body text must not be extracted as tag attrs."""
        tag = (
            '<channel source="telegram" chat_id="123">'
            'Body with some="value" and key="other" inside'
            "</channel>"
        )
        result = parse_channel_tag(tag)
        assert result == {"source": "telegram", "chat_id": "123"}
        assert "some" not in result
        assert "key" not in result

    def test_body_with_angle_brackets(self) -> None:
        """Body text containing angle brackets should not confuse the parser."""
        tag = (
            '<channel source="telegram" chat_id="42">'
            'User says: 2 > 1 and foo="bar" is valid'
            "</channel>"
        )
        result = parse_channel_tag(tag)
        assert result == {"source": "telegram", "chat_id": "42"}

    def test_tag_without_body(self) -> None:
        """A tag with no body and closing > still parses correctly."""
        tag = '<channel source="telegram" chat_id="100" user="bob">'
        result = parse_channel_tag(tag)
        assert result == {"source": "telegram", "chat_id": "100", "user": "bob"}


# ---------------------------------------------------------------------------
# normalize_timestamp
# ---------------------------------------------------------------------------


class TestNormalizeTimestamp:
    def test_z_suffix_to_offset(self) -> None:
        assert (
            normalize_timestamp("2026-03-24T06:00:00Z") == "2026-03-24T06:00:00+00:00"
        )

    def test_offset_unchanged(self) -> None:
        assert (
            normalize_timestamp("2026-03-24T06:00:00+00:00")
            == "2026-03-24T06:00:00+00:00"
        )

    def test_non_utc_offset_converted(self) -> None:
        """Timestamps with non-UTC offsets are converted to UTC."""
        # +05:00 means 06:00 local = 01:00 UTC
        result = normalize_timestamp("2026-03-24T06:00:00+05:00")
        assert result == "2026-03-24T01:00:00+00:00"

    def test_naive_treated_as_utc(self) -> None:
        """Naive timestamps (no tz) are treated as UTC."""
        result = normalize_timestamp("2026-03-24T06:00:00")
        assert result == "2026-03-24T06:00:00+00:00"

    def test_with_microseconds(self) -> None:
        result = normalize_timestamp("2026-03-24T06:00:00.123456Z")
        assert result == "2026-03-24T06:00:00.123456+00:00"

    def test_invalid_string_passthrough(self) -> None:
        """Invalid timestamps are returned unchanged."""
        assert normalize_timestamp("not-a-date") == "not-a-date"
        assert normalize_timestamp("") == ""

    def test_non_string_passthrough(self) -> None:
        """Non-string values don't crash."""
        assert normalize_timestamp(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# audit_inbound (SP-4-06 PR 3)
# ---------------------------------------------------------------------------


class TestAuditInbound:
    def test_basic_inbound(self, tmp_path: Path) -> None:
        record = audit_inbound(
            chat_id="8122530898",
            message_id="42",
            user="operator_user",
            content="Hello bot, what's the status?",
            audit_dir=tmp_path,
        )
        assert record.direction == "inbound"
        assert record.exchange_type == "message"
        assert record.channel_source == "telegram"
        assert record.sender_identity == "operator_user"
        assert record.chat_id == "8122530898"
        assert record.message_id == "42"
        assert record.metadata == {}

    def test_content_hash_matches_sha256(self, tmp_path: Path) -> None:
        """Verify content_hash is the SHA-256 of the content text."""
        msg = "Check deployment status"
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content=msg,
            audit_dir=tmp_path,
        )
        assert record.content_hash == content_hash(msg)

    def test_content_preview(self, tmp_path: Path) -> None:
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="short message",
            audit_dir=tmp_path,
        )
        assert record.content_preview == "short message"

    def test_long_content_preview_truncated(self, tmp_path: Path) -> None:
        long_msg = "z" * 500
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content=long_msg,
            audit_dir=tmp_path,
        )
        assert record.content_preview == "z" * 200 + "…"
        assert record.content_hash == content_hash(long_msg)

    def test_custom_channel_source(self, tmp_path: Path) -> None:
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="test",
            channel_source="discord",
            audit_dir=tmp_path,
        )
        assert record.channel_source == "discord"

    def test_custom_timestamp(self, tmp_path: Path) -> None:
        ts = "2026-03-24T10:30:00+00:00"
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="test",
            ts=ts,
            audit_dir=tmp_path,
        )
        assert record.timestamp == ts

    def test_with_metadata(self, tmp_path: Path) -> None:
        meta = {"attachment_file_id": "abc123", "image_path": "/tmp/photo.jpg"}
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="see photo",
            metadata=meta,
            audit_dir=tmp_path,
        )
        assert record.metadata == meta

    def test_persisted_to_jsonl(self, tmp_path: Path) -> None:
        """Verify the record is actually appended to the JSONL file."""
        audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="test",
            audit_dir=tmp_path,
        )
        records = read_records(audit_dir=tmp_path)
        assert len(records) == 1
        assert records[0].direction == "inbound"
        assert records[0].exchange_type == "message"

    def test_returns_persisted_record(self, tmp_path: Path) -> None:
        """audit_inbound returns the same record that was persisted."""
        returned = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="check",
            audit_dir=tmp_path,
        )
        persisted = read_records(audit_dir=tmp_path)
        assert len(persisted) == 1
        assert returned == persisted[0]

    def test_z_suffix_normalized_to_offset(self, tmp_path: Path) -> None:
        """Inbound ts with Z suffix is normalized to +00:00."""
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="test",
            ts="2026-03-24T06:00:00Z",
            audit_dir=tmp_path,
        )
        assert record.timestamp == "2026-03-24T06:00:00+00:00"

    def test_offset_timestamp_unchanged(self, tmp_path: Path) -> None:
        """Inbound ts already in +00:00 form is unchanged."""
        ts = "2026-03-24T10:30:00+00:00"
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="test",
            ts=ts,
            audit_dir=tmp_path,
        )
        assert record.timestamp == ts

    def test_no_ts_uses_auto_timestamp(self, tmp_path: Path) -> None:
        """When ts is None, auto-generated timestamp is used."""
        record = audit_inbound(
            chat_id="123",
            message_id="1",
            user="user1",
            content="test",
            audit_dir=tmp_path,
        )
        # Auto-generated timestamp should be parseable and in UTC
        dt = datetime.fromisoformat(record.timestamp)
        assert dt.tzinfo is not None

    def test_inbound_outbound_coexist(self, tmp_path: Path) -> None:
        """Inbound and outbound records coexist in the same log."""
        audit_inbound(
            chat_id="123",
            message_id="1",
            user="operator",
            content="What's the status?",
            audit_dir=tmp_path,
        )
        audit_reply(chat_id="123", body="All good!", audit_dir=tmp_path)

        all_records = read_records(audit_dir=tmp_path)
        assert len(all_records) == 2

        inbound = read_records(audit_dir=tmp_path, direction="inbound")
        assert len(inbound) == 1
        assert inbound[0].sender_identity == "operator"

        outbound = read_records(audit_dir=tmp_path, direction="outbound")
        assert len(outbound) == 1
        assert outbound[0].exchange_type == "reply"
