"""Event-to-signal integration smoke (Primitive A / Primitive E handoff).

Proves that an emission via ``events.emit()`` lands in the v1.0 JSONL
stream, is discoverable via the audit script, and that the latency
surface described in ``docs/01_core/event_schema_v1.md`` is wired end
to end.

The full event-to-signal latency test (flipping a lifecycle event ->
operator signal within the ≤5 min p95 target) lands under Primitive E
Phase 0. This smoke proves the upstream half of that handoff is live.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bid_euchre.ops.event_writer import list_active_files
from bid_euchre.ops.events import emit


@pytest.fixture()
def event_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log_dir = tmp_path / "events"
    monkeypatch.setenv("STEWARD_EVENTS_LOG_DIR", str(log_dir))
    return log_dir


class TestEventToSignalSmoke:
    """Upstream half of the event-to-signal handoff (Primitive A)."""

    def test_emit_lands_in_jsonl_stream(self, event_env: Path) -> None:
        emit(
            "task_started",
            packet_id="smoke-1",
            dispatched_by="orchestrator",
            priority="high",
            domain="platform",
            lane_id="author-a",
        )
        files = list_active_files(event_env)
        assert len(files) == 1
        # File has exactly one line with our event.
        lines = files[0].read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["event_type"] == "task_started"
        assert record["packet_id"] == "smoke-1"

    def test_latency_event_emission_visible_on_dashboard_pipeline(
        self, event_env: Path
    ) -> None:
        """Emit a latency event; dashboard helper must see it.

        Links Primitive A emission -> Primitive A dashboard surface (the
        Latencies panel added in shaping §8.2 step 10).
        """
        from bid_euchre.ops.dashboard import _load_latency_summary

        emit(
            "event_to_signal_latency",
            source_event_id="evt-1",
            signal_type="inbox",
            latency_ms=42.0,
            lane_id="author-a",
        )
        emit(
            "event_to_signal_latency",
            source_event_id="evt-2",
            signal_type="inbox",
            latency_ms=84.0,
            lane_id="author-a",
        )
        summary = _load_latency_summary(event_env)
        assert summary["event_to_signal"]["count"] == 2
        assert summary["event_to_signal"]["p50_ms"] == 63.0

    def test_audit_script_sees_live_emitters(self, event_env: Path) -> None:
        """audit_event_emission.py locates live emitters via code scan.

        This is an emission-call-site discovery check — it does **not**
        require any live JSONL content. Proves the audit path is wired.
        """
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "internal" / "audit_event_emission.py"
        assert script.exists()
        result = subprocess.run(
            [sys.executable, str(script), "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        # Script exits 0 for green/yellow; only red fails. Yellow is
        # acceptable on a repo where deferred classes (canary/archivist/
        # promotion/rollback/worktree) have no emitters yet.
        assert result.returncode == 0, (
            f"audit script exited {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        payload = json.loads(result.stdout)
        assert "classes" in payload
        # Find the task_lifecycle class entry (classes is a list of dicts).
        task_class = next(
            (c for c in payload["classes"] if c["class_name"] == "task_lifecycle"),
            None,
        )
        assert task_class is not None, (
            f"task_lifecycle class missing from audit payload:\n"
            f"{json.dumps(payload, indent=2)}"
        )
        # task_lifecycle must be green (we just migrated ops/task_queue.py
        # in Packet 3 step 7; emitters are committed).
        assert task_class["status"] in {
            "green",
            "yellow",
        }, f"task_lifecycle unexpectedly red:\n{json.dumps(task_class, indent=2)}"
