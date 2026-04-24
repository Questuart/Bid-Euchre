"""Replay-compat smoke — Event Schema v1.0 (Primitive A Packet 3).

Proves that records emitted by ``bid_euchre.ops.events.emit()`` at
schema v1.0 emit cleanly, carry the expected §9.7 first-class IDs and
§2.4 correlation fields, and re-parse without loss.

This is the **smoke** companion to the full replay harness (Primitive
H.1, ``tests/reliability/replay.py``). The full harness lands in
Phase 1; the smoke ensures the v1.0 emission path is not silently
broken in the interim.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.event_schema import (
    EVENT_FIELD_REGISTRY,
    NATIVE_LIFECYCLE_EVENT_TYPES,
    SCHEMA_VERSION,
)
from bid_euchre.ops.event_writer import list_active_files
from bid_euchre.ops.events import emit

# §9.7 first-class IDs that must appear on every record.
_FIRST_CLASS_IDS = (
    "project_id",
    "cell_id",
    "session_id",
    "task_id",
    "lane_id",
    "trace_id",
    "incident_fingerprint",
    "prompt_policy_version",
    "schema_version",
)

# §2.4 correlation fields that must appear on every record.
_CORRELATION_FIELDS = ("seq", "pid", "timestamp_ns", "turn_id")


@pytest.fixture()
def isolated_events_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Give each test its own ``STEWARD_EVENTS_LOG_DIR``."""
    log_dir = tmp_path / "events"
    monkeypatch.setenv("STEWARD_EVENTS_LOG_DIR", str(log_dir))
    # Keep verbosity deterministic so optional fields survive re-parse.
    monkeypatch.setenv("STEWARD_EVENTS_VERBOSITY", "full")
    return log_dir


def _read_all_events(log_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in list_active_files(log_dir):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    return records


class TestReplayCompatV1:
    """Smoke: v1.0 records round-trip through JSON encode → decode."""

    def test_emit_task_started_is_replayable(self, isolated_events_dir: Path) -> None:
        emit(
            "task_started",
            packet_id="abc123",
            dispatched_by="orchestrator",
            priority="high",
            domain="platform",
            lane_id="author-a",
        )
        records = _read_all_events(isolated_events_dir)
        assert len(records) == 1

        record = records[0]
        # §9.7 IDs all present (null is acceptable for the three nullable ones).
        for id_key in _FIRST_CLASS_IDS:
            assert id_key in record, f"Missing first-class ID: {id_key!r}"
        # Correlation fields present and well-typed.
        for corr_key in _CORRELATION_FIELDS:
            assert corr_key in record, f"Missing correlation field: {corr_key!r}"
            assert isinstance(record[corr_key], int)
        # Schema version is the v1.0 constant.
        assert record["schema_version"] == SCHEMA_VERSION == "1.0"
        # Event-type-specific fields landed at top level, not in extra_fields.
        assert record["event_type"] == "task_started"
        assert record["packet_id"] == "abc123"
        assert record["dispatched_by"] == "orchestrator"
        assert record["priority"] == "high"
        assert record["domain"] == "platform"
        assert record["lane_id"] == "author-a"
        # project_id + cell_id are populated by the dispatcher.
        assert record["project_id"] == "bid-euchre"
        assert record["cell_id"] == "bid-euchre"

    def test_emit_task_completed_is_replayable(self, isolated_events_dir: Path) -> None:
        emit(
            "task_completed",
            packet_id="xyz789",
            outcome="merged",
            pr_number=1234,
            lane_id="author-b",
        )
        records = _read_all_events(isolated_events_dir)
        assert len(records) == 1
        record = records[0]
        assert record["event_type"] == "task_completed"
        assert record["packet_id"] == "xyz789"
        assert record["outcome"] == "merged"
        assert record["pr_number"] == 1234
        assert record["lane_id"] == "author-b"

    def test_multi_event_seq_monotonic(self, isolated_events_dir: Path) -> None:
        """seq is strictly monotonic across consecutive emissions."""
        for i in range(5):
            emit(
                "task_started",
                packet_id=f"p{i}",
                dispatched_by="orchestrator",
                priority="medium",
                domain="platform",
                lane_id="author-a",
            )
        records = _read_all_events(isolated_events_dir)
        assert len(records) == 5
        seqs = [r["seq"] for r in records]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)  # no duplicates

    def test_unknown_event_type_does_not_write(self, isolated_events_dir: Path) -> None:
        """Unknown event types are dropped silently (never-raises)."""
        emit("not_a_real_event_type_xyz", foo="bar")
        records = _read_all_events(isolated_events_dir)
        assert records == []

    def test_emit_never_raises_on_missing_required(
        self, isolated_events_dir: Path
    ) -> None:
        """Missing required fields drop the emission but never raise."""
        # ``task_started`` requires packet_id / dispatched_by / priority /
        # domain; leaving them out must not raise.
        emit("task_started")
        records = _read_all_events(isolated_events_dir)
        assert records == []

    def test_extra_fields_routed_to_extra_fields_bucket(
        self, isolated_events_dir: Path
    ) -> None:
        """Unknown kwargs land in ``extra_fields`` (Pattern 8 bug marker)."""
        emit(
            "task_started",
            packet_id="abc",
            dispatched_by="orchestrator",
            priority="high",
            domain="platform",
            lane_id="author-a",
            # Unknown field — must route to extra_fields, not a top-level slot.
            experimental_flag="yes",
        )
        records = _read_all_events(isolated_events_dir)
        assert len(records) == 1
        record = records[0]
        assert "experimental_flag" not in record
        assert record.get("extra_fields", {}).get("experimental_flag") == "yes"

    def test_record_round_trips_through_json(self, isolated_events_dir: Path) -> None:
        """Serialize → deserialize → compare: no loss, no reshape."""
        emit(
            "task_started",
            packet_id="abc",
            dispatched_by="orchestrator",
            priority="high",
            domain="platform",
            lane_id="author-a",
        )
        records = _read_all_events(isolated_events_dir)
        assert len(records) == 1
        original = records[0]
        # Re-encode + decode; shape must survive.
        reparsed = json.loads(json.dumps(original))
        assert reparsed == original


class TestRegistryInvariantsV1:
    """Guards that lock the v1.0 registry shape for replay compatibility."""

    def test_schema_version_is_v1(self) -> None:
        assert SCHEMA_VERSION == "1.0"

    def test_registry_includes_all_native_lifecycle_types(self) -> None:
        """NATIVE_LIFECYCLE_EVENT_TYPES must all appear in the registry.

        Primitive H.1 replay assumes every native lifecycle event type is
        replayable — dropping one silently would break reconstruction of
        sessions that include the missing type.
        """
        missing = [
            t for t in NATIVE_LIFECYCLE_EVENT_TYPES if t not in EVENT_FIELD_REGISTRY
        ]
        assert missing == [], f"Missing native lifecycle types: {missing}"

    def test_task_types_require_packet_id(self) -> None:
        """``task_started`` / ``task_completed`` both require ``packet_id``.

        Replay lifecycle reconstruction depends on packet_id as the join key.
        """
        for event_type in ("task_started", "task_completed"):
            spec = EVENT_FIELD_REGISTRY[event_type]
            assert (
                "packet_id" in spec.required_fields
            ), f"{event_type} must require packet_id for replay join"

    def test_latency_events_register_latency_ms(self) -> None:
        """Latency events carry a numeric latency field at top level."""
        assert (
            "latency_ms"
            in EVENT_FIELD_REGISTRY["event_to_signal_latency"].required_fields
        )
        assert (
            "delivery_ms"
            in EVENT_FIELD_REGISTRY["bus_delivery_latency"].required_fields
        )
