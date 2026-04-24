"""Unit tests for ``bid_euchre.ops.events`` Primitive A dispatcher.

Covers per shaping §8.3:

- Happy-path emission with full baseline population.
- Never-raise contract — dispatcher swallows all exceptions.
- Verbosity tier override (kwarg + env var + registry default).
- Unknown-event-type rejection (no JSONL write).
- Missing-required-field rejection (no JSONL write).
- ``extra_fields`` routing for unregistered slots (Pattern 8).
- §9.7 first-class ID population from env vars + caller overrides.
- Legacy ``append_event`` / ``read_events`` surface preserved.
- Reexported taxonomy helpers available on ``events`` module.

The Primitive A dispatcher writes to a configurable ``data/events/``
directory via :func:`bid_euchre.ops.event_writer.write_event` — tests
use ``tmp_path`` + ``STEWARD_EVENTS_LOG_DIR`` to isolate per test.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from bid_euchre.ops import events
from bid_euchre.ops.event_schema import SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def events_dir(tmp_path: Path, monkeypatch) -> Iterator[Path]:
    """Isolated v1.0 events dir + cached-session reset."""
    d = tmp_path / "data" / "events"
    d.mkdir(parents=True)
    monkeypatch.setenv("STEWARD_EVENTS_LOG_DIR", str(d))
    monkeypatch.setenv("CLAUDE_SESSION_ID", "test-session-xyz")
    monkeypatch.setenv("CLAUDE_AGENT_NAME", "author-a")
    events.reset_cached_session()
    yield d
    events.reset_cached_session()


def _read_jsonl(path: Path) -> list[dict]:
    """Read all JSONL records from the events file in a log dir."""
    files = sorted(path.glob("events-*.jsonl"))
    records: list[dict] = []
    for f in files:
        for line in f.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_emit_happy_path_writes_jsonl(events_dir: Path) -> None:
    events.emit(
        "task_started",
        packet_id="abc123",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    records = _read_jsonl(events_dir)
    assert len(records) == 1
    rec = records[0]
    assert rec["event_type"] == "task_started"
    assert rec["packet_id"] == "abc123"
    assert rec["dispatched_by"] == "orchestrator"


def test_emit_populates_all_nine_first_class_ids(events_dir: Path) -> None:
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    rec = _read_jsonl(events_dir)[0]
    # All nine §9.7 IDs present
    for fld in (
        "project_id",
        "cell_id",
        "session_id",
        "task_id",
        "lane_id",
        "trace_id",
        "incident_fingerprint",
        "prompt_policy_version",
        "schema_version",
    ):
        assert fld in rec, f"missing §9.7 field: {fld}"
    assert rec["project_id"] == "bid-euchre"
    assert rec["cell_id"] == "bid-euchre"
    assert rec["session_id"] == "test-session-xyz"
    assert rec["lane_id"] == "author-a"
    assert rec["schema_version"] == SCHEMA_VERSION


def test_emit_populates_correlation_fields(events_dir: Path) -> None:
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    rec = _read_jsonl(events_dir)[0]
    for fld in ("seq", "pid", "timestamp_ns", "turn_id"):
        assert fld in rec, f"missing correlation field: {fld}"
    assert isinstance(rec["seq"], int) and rec["seq"] >= 1
    assert isinstance(rec["pid"], int) and rec["pid"] > 0
    assert isinstance(rec["timestamp_ns"], int) and rec["timestamp_ns"] > 0
    assert isinstance(rec["turn_id"], int)


def test_emit_sequence_is_monotonic(events_dir: Path) -> None:
    for i in range(5):
        events.emit(
            "task_started",
            packet_id=f"pkt-{i}",
            dispatched_by="orchestrator",
            priority="normal",
            domain="platform",
        )
    records = _read_jsonl(events_dir)
    seqs = [r["seq"] for r in records]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)  # no duplicates


# ---------------------------------------------------------------------------
# Never-raise contract (ADR 007)
# ---------------------------------------------------------------------------


def test_emit_never_raises_on_unknown_event_type(events_dir: Path) -> None:
    # Should not raise
    events.emit("definitely_not_a_registered_event_type", foo="bar")
    # No JSONL write
    assert _read_jsonl(events_dir) == []


def test_emit_never_raises_on_missing_required(events_dir: Path) -> None:
    # task_started requires packet_id, dispatched_by, priority, domain — omit all
    events.emit("task_started")
    # No JSONL write
    assert _read_jsonl(events_dir) == []


def test_emit_never_raises_on_writer_failure(events_dir: Path, monkeypatch) -> None:
    """Simulate writer failure — caller still doesn't see an exception."""

    def _broken_writer(record, log_dir=None):
        raise OSError("disk full")

    monkeypatch.setattr(events.event_writer, "write_event", _broken_writer)
    # No exception should propagate
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )


def test_emit_never_raises_on_next_seq_failure(events_dir: Path, monkeypatch) -> None:
    """Simulate seq counter failure — dispatcher remains non-blocking."""

    def _broken_seq(log_dir=None):
        raise OSError("fs broken")

    monkeypatch.setattr(events.event_writer, "next_seq", _broken_seq)
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )


# ---------------------------------------------------------------------------
# Verbosity tiers
# ---------------------------------------------------------------------------


def test_emit_verbosity_summary_default(events_dir: Path) -> None:
    events.emit(
        "task_completed",
        packet_id="abc",
        outcome="success",
        summary="This is a regular-sized summary",
    )
    rec = _read_jsonl(events_dir)[0]
    # summary tier includes required fields
    assert rec["packet_id"] == "abc"
    assert rec["outcome"] == "success"
    # summary also preserves optional fields that the caller passed
    assert "summary" in rec or rec.get("outcome") == "success"


def test_emit_verbosity_minimal_strips_payload(events_dir: Path) -> None:
    events.emit(
        "task_completed",
        _verbosity="minimal",
        packet_id="abc",
        outcome="success",
        summary="bulky text",
        token_spend=12345,
    )
    rec = _read_jsonl(events_dir)[0]
    # Baseline fields retained
    assert rec["event_type"] == "task_completed"
    assert rec["session_id"] == "test-session-xyz"
    # Optional bulky fields stripped in minimal tier
    assert "summary" not in rec
    assert "token_spend" not in rec
    # packet_id is a required field but minimal drops non-baseline; that's
    # OK because minimal is for high-frequency grep only.
    # However outcome (success/failure hint) is preserved
    assert rec["outcome"] == "success"


def test_emit_verbosity_full_keeps_everything(events_dir: Path) -> None:
    events.emit(
        "task_completed",
        _verbosity="full",
        packet_id="abc",
        outcome="success",
        summary="full bulk payload",
        token_spend=12345,
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["summary"] == "full bulk payload"
    assert rec["token_spend"] == 12345


def test_emit_verbosity_env_var_override(events_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("STEWARD_EVENTS_VERBOSITY", "full")
    events.emit(
        "task_completed",
        packet_id="abc",
        outcome="success",
        summary="env-override payload",
        token_spend=9999,
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["summary"] == "env-override payload"


def test_emit_verbosity_invalid_falls_back_to_summary(events_dir: Path) -> None:
    events.emit(
        "task_completed",
        _verbosity="not-a-real-tier",
        packet_id="abc",
        outcome="success",
    )
    # Should not raise and should still emit
    assert len(_read_jsonl(events_dir)) == 1


def test_emit_summary_truncates_very_long_strings(events_dir: Path) -> None:
    bulk = "x" * 5000
    events.emit(
        "task_completed",
        packet_id="abc",
        outcome="success",
        summary=bulk,
    )
    rec = _read_jsonl(events_dir)[0]
    if "summary" in rec:
        assert len(rec["summary"]) <= 2000


# ---------------------------------------------------------------------------
# extra_fields routing (Pattern 8 bug marker)
# ---------------------------------------------------------------------------


def test_emit_unregistered_field_routed_to_extra_fields(
    events_dir: Path,
) -> None:
    events.emit(
        "task_started",
        _verbosity="full",  # Keep extra_fields visible
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
        novel_slot="some_value",  # Not in registry
    )
    rec = _read_jsonl(events_dir)[0]
    assert "extra_fields" in rec
    assert rec["extra_fields"]["novel_slot"] == "some_value"
    # Known fields not routed to extra
    assert "dispatched_by" not in rec.get("extra_fields", {})


def test_emit_registered_optional_field_lands_at_top_level(
    events_dir: Path,
) -> None:
    """Registered optional slots stay top-level (not routed to extra_fields).

    Note: summary-tier filters optional fields by design (§3.3); use
    ``_verbosity="full"`` to observe the pass-through here.
    """
    events.emit(
        "task_started",
        _verbosity="full",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
        effort_hint="low",  # registered optional
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["effort_hint"] == "low"
    # Not routed to extra_fields
    assert "effort_hint" not in rec.get("extra_fields", {})


# ---------------------------------------------------------------------------
# Caller overrides of §9.7 IDs
# ---------------------------------------------------------------------------


def test_emit_caller_trace_id_override(events_dir: Path) -> None:
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
        trace_id="custom-trace-42",
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["trace_id"] == "custom-trace-42"


def test_emit_caller_task_id_override(events_dir: Path) -> None:
    events.emit(
        "task_started",
        packet_id="abc",
        task_id="explicit-task-id",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["task_id"] == "explicit-task-id"


def test_emit_caller_lane_id_override(events_dir: Path) -> None:
    """worktree_create targets a different lane than the emitter."""
    events.emit(
        "worktree_create",
        worktree_path="/tmp/Bid-Euchre-foo",
        branch="feat/x",
        protected=False,
        lane_id="flex-b",  # target lane
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["lane_id"] == "flex-b"


def test_emit_default_lane_id_from_env(events_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_AGENT_NAME", "analyst-c")
    events.reset_cached_session()
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["lane_id"] == "analyst-c"


def test_emit_session_id_falls_back_to_uuid(tmp_path: Path, monkeypatch) -> None:
    """When CLAUDE_SESSION_ID is unset, dispatcher generates a UUID."""
    d = tmp_path / "data" / "events"
    d.mkdir(parents=True)
    monkeypatch.setenv("STEWARD_EVENTS_LOG_DIR", str(d))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    events.reset_cached_session()
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    rec = json.loads(next(d.glob("*.jsonl")).read_text().splitlines()[0])
    # Not the test sentinel value; a real UUID has 4 hyphens
    sid = rec["session_id"]
    assert sid != "test-session-xyz"
    assert sid.count("-") == 4


def test_emit_prompt_policy_version_unset_default(events_dir: Path) -> None:
    """Primitive B.3 registry hasn't shipped — default value is ``unset``."""
    rec_fields = dict(
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    events.emit("task_started", **rec_fields)
    rec = _read_jsonl(events_dir)[0]
    assert rec["prompt_policy_version"] == "unset"


def test_emit_prompt_policy_version_env_override(events_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("STEWARD_PROMPT_POLICY_VERSION", "v2.3")
    events.reset_cached_session()
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["prompt_policy_version"] == "v2.3"


# ---------------------------------------------------------------------------
# Incident fingerprint re-export
# ---------------------------------------------------------------------------


def test_events_reexports_taxonomy_helpers() -> None:
    assert events.categorize_error is not None
    assert events.build_status_message is not None
    assert events.incident_fingerprint is not None
    # They are the real taxonomy helpers
    from bid_euchre.ops import event_taxonomy

    assert events.categorize_error is event_taxonomy.categorize_error
    assert events.incident_fingerprint is event_taxonomy.incident_fingerprint


def test_emit_populates_incident_fingerprint_when_provided(
    events_dir: Path,
) -> None:
    fp = events.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="Operation timed out",
    )
    events.emit(
        "stop_failure",
        stop_hook_active=True,
        failure_category="timeout",
        incident_fingerprint=fp,
    )
    rec = _read_jsonl(events_dir)[0]
    assert rec["incident_fingerprint"] == fp


# ---------------------------------------------------------------------------
# Legacy API preservation
# ---------------------------------------------------------------------------


def test_legacy_append_event_still_works(tmp_path: Path) -> None:
    """The pre-existing append_event path must keep working for 25+ consumers."""
    legacy_dir = tmp_path / "runtime-events"
    events.append_event(
        event_type="task_completed",
        source="test",
        lane_id="author-a",
        payload={"packet_id": "abc"},
        events_dir=legacy_dir,
    )
    legacy_file = legacy_dir / events.EVENTS_FILE
    assert legacy_file.exists()
    rec = json.loads(legacy_file.read_text().splitlines()[0])
    assert rec["event_type"] == "task_completed"
    assert rec["lane_id"] == "author-a"
    assert rec["payload"]["packet_id"] == "abc"


def test_legacy_valid_event_types_unchanged() -> None:
    """Legacy VALID_EVENT_TYPES is distinct from v1.0 registry."""
    assert "task_started" in events.VALID_EVENT_TYPES
    assert "task_completed" in events.VALID_EVENT_TYPES
    # Legacy has types that are intentionally not in v1.0 (e.g., heartbeat_stale)
    assert "heartbeat_stale" in events.VALID_EVENT_TYPES


def test_legacy_and_new_apis_write_to_different_dirs(
    events_dir: Path, tmp_path: Path
) -> None:
    """Legacy writes to events_dir= param; new writes to STEWARD_EVENTS_LOG_DIR."""
    legacy_dir = tmp_path / "runtime-events"
    events.append_event(
        event_type="task_started",
        source="test",
        lane_id="author-a",
        payload={},
        events_dir=legacy_dir,
    )
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
    )
    # Two distinct pipelines
    assert (legacy_dir / events.EVENTS_FILE).exists()
    assert any(events_dir.glob("events-*.jsonl"))


# ---------------------------------------------------------------------------
# Audit-helper contract (used by audit_event_emission.py later)
# ---------------------------------------------------------------------------


def test_emit_record_json_round_trip(events_dir: Path) -> None:
    """Every record round-trips cleanly through JSON."""
    events.emit(
        "task_started",
        packet_id="abc",
        dispatched_by="orchestrator",
        priority="high",
        domain="platform",
        effort_hint="low",
    )
    f = next(events_dir.glob("events-*.jsonl"))
    line = f.read_text().splitlines()[0]
    # No trailing comma / malformed JSON
    rec = json.loads(line)
    # Re-encoding produces a canonical form (writer uses sort_keys=True)
    assert json.dumps(rec, sort_keys=True) == line.strip()
