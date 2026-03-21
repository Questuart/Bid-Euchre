"""Tests for scheduler tick loop and daemon mode (ops/scheduler.py)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.scheduler import (
    DEFAULT_CHECKS,
    MAX_DAEMON_ITERATIONS,
    DaemonResult,
    SchedulerState,
    _evaluate_retries_for_findings,
    daemon,
    format_daemon_json,
    format_daemon_text,
    format_tick_json,
    format_tick_text,
    load_scheduler_state,
    save_scheduler_state,
    tick,
)


@pytest.fixture()
def scheduler_dir(tmp_path: Path) -> Path:
    """Temporary scheduler state directory."""
    d = tmp_path / "scheduler"
    d.mkdir()
    return d


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Temporary runtime directory with subdirs."""
    rd = tmp_path / "runtime"
    (rd / "task_state").mkdir(parents=True)
    (rd / "worktree_registry").mkdir(parents=True)
    return rd


@pytest.fixture()
def plans_dir(tmp_path: Path) -> Path:
    """Temporary plans directory."""
    d = tmp_path / "plans"
    d.mkdir()
    return d


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Temporary events directory."""
    d = tmp_path / "events"
    d.mkdir()
    return d


class TestSchedulerState:
    """Tests for load/save scheduler state."""

    def test_default_state(self, scheduler_dir: Path) -> None:
        state = load_scheduler_state(scheduler_dir)
        assert state.last_tick is None
        assert state.tick_count == 0
        assert len(state.due_checks) > 0

    def test_round_trip(self, scheduler_dir: Path) -> None:
        state = SchedulerState(
            last_tick="2026-03-18T12:00:00+00:00",
            last_health_pass="2026-03-18T11:55:00+00:00",
            tick_count=42,
            due_checks=["heartbeats", "task_progress"],
            last_error=None,
        )
        save_scheduler_state(state, scheduler_dir)
        loaded = load_scheduler_state(scheduler_dir)

        assert loaded.last_tick == state.last_tick
        assert loaded.last_health_pass == state.last_health_pass
        assert loaded.tick_count == 42
        assert loaded.due_checks == ["heartbeats", "task_progress"]

    def test_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "scheduler"
        state = SchedulerState(tick_count=1)
        path = save_scheduler_state(state, nested)
        assert path.exists()

    def test_malformed_file_returns_default(self, scheduler_dir: Path) -> None:
        (scheduler_dir / "state.json").write_text("not json{{{")
        state = load_scheduler_state(scheduler_dir)
        assert state.tick_count == 0


class TestTick:
    """Tests for tick()."""

    def test_basic_tick(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        result = tick(runtime_dir, plans_dir, scheduler_dir, events_dir, now=now)

        assert result.tick_number == 1
        assert len(result.checks_run) > 0
        assert result.events_emitted >= 1  # At least the tick event
        assert result.errors == []

        # State should be persisted
        state = load_scheduler_state(scheduler_dir)
        assert state.tick_count == 1
        assert state.last_tick is not None

    def test_tick_increments_count(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)

        r1 = tick(runtime_dir, plans_dir, scheduler_dir, events_dir, now=now)
        assert r1.tick_number == 1

        r2 = tick(runtime_dir, plans_dir, scheduler_dir, events_dir, now=now)
        assert r2.tick_number == 2

    def test_tick_with_stale_heartbeat(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)

        # Create a stale heartbeat
        hb_dir = plans_dir / "test_rung"
        hb_dir.mkdir()
        (hb_dir / "heartbeat").write_text((now - timedelta(minutes=20)).isoformat())

        result = tick(runtime_dir, plans_dir, scheduler_dir, events_dir, now=now)

        assert len(result.findings) >= 1
        assert any(f.severity == "critical" for f in result.findings)
        # Should NOT record last_health_pass when there are critical findings
        state = load_scheduler_state(scheduler_dir)
        assert state.last_health_pass is None

    def test_tick_clean_records_health_pass(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        tick(runtime_dir, plans_dir, scheduler_dir, events_dir, now=now)

        state = load_scheduler_state(scheduler_dir)
        assert state.last_health_pass is not None

    def test_tick_emits_events(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod
        from bid_euchre.ops.events import read_events

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        tick(runtime_dir, plans_dir, scheduler_dir, events_dir, now=now)

        events = read_events(events_dir)
        tick_events = [e for e in events if e["event_type"] == "scheduler_tick"]
        assert len(tick_events) == 1
        assert tick_events[0]["payload"]["tick_number"] == 1


class TestFormatters:
    """Tests for tick result formatters."""

    def test_text_format(self) -> None:
        from bid_euchre.ops.scheduler import TickResult

        result = TickResult(
            checks_run=["heartbeats"],
            findings=[],
            events_emitted=1,
            errors=[],
            tick_number=5,
        )
        text = format_tick_text(result)
        assert "Tick #5" in text
        assert "heartbeats" in text

    def test_json_format(self) -> None:
        from bid_euchre.ops.scheduler import TickResult

        result = TickResult(
            checks_run=["heartbeats"],
            findings=[],
            events_emitted=1,
            errors=[],
            tick_number=5,
        )
        data = format_tick_json(result)
        assert data["tick_number"] == 5
        assert data["findings_count"] == 0


# ---- Phase 3D: Daemon mode tests ----


class TestDaemonConstants:
    """Tests for daemon constants."""

    def test_max_iterations_cap(self) -> None:
        assert MAX_DAEMON_ITERATIONS == 1000

    def test_default_checks_includes_phase3d(self) -> None:
        """DEFAULT_CHECKS must include all Phase 3D watchdog names."""
        assert "ci_stuck" in DEFAULT_CHECKS
        assert "subagent_failures" in DEFAULT_CHECKS
        assert "scope_drift" in DEFAULT_CHECKS
        # Also verify Phase 3A checks are still present
        assert "heartbeats" in DEFAULT_CHECKS
        assert "task_progress" in DEFAULT_CHECKS
        assert "worktree_health" in DEFAULT_CHECKS


class TestDaemon:
    """Tests for daemon()."""

    def _noop_sleep(self, _seconds: float) -> None:
        """No-op sleep for testing."""
        pass

    def test_basic_daemon(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        result = daemon(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            scheduler_dir=scheduler_dir,
            events_dir=events_dir,
            max_iterations=3,
            _sleep_fn=self._noop_sleep,
        )

        assert result.ticks_completed == 3
        assert result.stopped_reason == "max_iterations"
        assert result.errors == []

        # Scheduler state should show 3 ticks
        state = load_scheduler_state(scheduler_dir)
        assert state.tick_count == 3

    def test_daemon_enforces_hard_cap(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        # Request more than MAX_DAEMON_ITERATIONS
        result = daemon(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            scheduler_dir=scheduler_dir,
            events_dir=events_dir,
            max_iterations=MAX_DAEMON_ITERATIONS + 100,
            _sleep_fn=self._noop_sleep,
        )

        assert result.ticks_completed == MAX_DAEMON_ITERATIONS

    def test_daemon_stops_on_repeated_errors(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Daemon stops after 3 consecutive errors."""
        call_count = 0

        def failing_tick(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"tick error {call_count}")

        from bid_euchre.ops import scheduler as sched_mod

        monkeypatch.setattr(sched_mod, "tick", failing_tick)

        result = daemon(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            scheduler_dir=scheduler_dir,
            events_dir=events_dir,
            max_iterations=10,
            _sleep_fn=self._noop_sleep,
        )

        assert result.stopped_reason == "error"
        assert len(result.errors) >= 3

    def test_daemon_survives_intermittent_errors(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Daemon does NOT stop when errors are separated by successes.

        Regression test: cumulative error counting stopped the daemon after
        3 total errors spread across many ticks. With consecutive semantics,
        only 3 errors in a row should trigger shutdown.
        """
        call_count = 0

        def intermittent_tick(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Fail on ticks 1, 3, 5 (separated by successes on 2, 4, 6)
            if call_count % 2 == 1:
                raise RuntimeError(f"intermittent error {call_count}")
            # Import to return a valid TickResult on success
            from bid_euchre.ops.scheduler import TickResult

            return TickResult(
                checks_run=[],
                findings=[],
                events_emitted=0,
                errors=[],
                tick_number=call_count,
            )

        from bid_euchre.ops import scheduler as sched_mod

        monkeypatch.setattr(sched_mod, "tick", intermittent_tick)

        result = daemon(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            scheduler_dir=scheduler_dir,
            events_dir=events_dir,
            max_iterations=6,
            _sleep_fn=self._noop_sleep,
        )

        # Should complete all 6 ticks (not stop early from cumulative errors)
        assert result.stopped_reason == "max_iterations"
        # 3 errors total, but never 3 consecutive
        assert len(result.errors) == 3

    def test_daemon_accumulates_findings(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        result = daemon(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            scheduler_dir=scheduler_dir,
            events_dir=events_dir,
            max_iterations=2,
            _sleep_fn=self._noop_sleep,
        )

        # Each tick emits at least a scheduler_tick event
        assert result.total_events_emitted >= 2

    def test_daemon_warnings_do_not_trigger_shutdown(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """tick_result.errors (watchdog warnings) must NOT count toward
        the consecutive-error shutdown threshold.

        Regression test: the daemon previously conflated tick_result.errors
        (non-fatal warnings from a successful tick) with actual exceptions.
        5 consecutive ticks with warnings would trigger shutdown (>= 3).
        After the fix, only exceptions increment the counter.
        """
        call_count = 0

        def warning_tick(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            from bid_euchre.ops.scheduler import TickResult

            return TickResult(
                checks_run=["heartbeats"],
                findings=[],
                events_emitted=0,
                errors=[f"watchdog warning {call_count}"],  # Non-fatal
                tick_number=call_count,
            )

        from bid_euchre.ops import scheduler as sched_mod

        monkeypatch.setattr(sched_mod, "tick", warning_tick)

        result = daemon(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            scheduler_dir=scheduler_dir,
            events_dir=events_dir,
            max_iterations=5,
            _sleep_fn=self._noop_sleep,
        )

        # All 5 ticks must complete — warnings are not fatal
        assert result.ticks_completed == 5
        assert result.stopped_reason == "max_iterations"
        # Warnings are still accumulated in result.errors
        assert len(result.errors) == 5


class TestDaemonFormatters:
    """Tests for daemon result formatters."""

    def test_text_format(self) -> None:
        result = DaemonResult(
            ticks_completed=5,
            total_findings=3,
            critical_findings=1,
            total_events_emitted=10,
            errors=[],
            stopped_reason="max_iterations",
        )
        text = format_daemon_text(result)
        assert "Daemon Run Summary" in text
        assert "5" in text
        assert "max_iterations" in text

    def test_json_format(self) -> None:
        result = DaemonResult(
            ticks_completed=5,
            total_findings=3,
            critical_findings=1,
            total_events_emitted=10,
            errors=["err1"],
            stopped_reason="error",
        )
        data = format_daemon_json(result)
        assert data["ticks_completed"] == 5
        assert data["critical_findings"] == 1
        assert data["stopped_reason"] == "error"
        assert len(data["errors"]) == 1


# ---- Retry evaluation in tick (#930) ----


class TestEvaluateRetriesForFindings:
    """Tests for _evaluate_retries_for_findings() and its integration in tick()."""

    @pytest.fixture()
    def events_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "events"
        d.mkdir()
        return d

    def test_emits_retry_for_subagent_failures(self, events_dir: Path) -> None:
        """Subagent failure findings trigger retry event emission."""
        from bid_euchre.ops.events import read_events
        from bid_euchre.ops.watchdogs import WatchdogFinding

        # Pre-populate event log with task failures (needed for policy eval)
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 1"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:01:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 2"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        # Create a subagent failure finding
        findings = [
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="author-a:t1",
                message="Task t1 failed 2 times",
                threshold="3 failures",
                recommended_action="Reroute",
            ),
        ]

        emitted = _evaluate_retries_for_findings(findings, events_dir)
        assert emitted == 1

        # Verify the retry_attempted event was written
        events = read_events(events_dir)
        retry_events = [e for e in events if e["event_type"] == "retry_attempted"]
        assert len(retry_events) == 1
        assert retry_events[0]["payload"]["task_id"] == "t1"
        assert retry_events[0]["lane_id"] == "author-a"

    def test_no_retry_without_subagent_findings(self, events_dir: Path) -> None:
        """Non-subagent findings do not trigger retry evaluation."""
        from bid_euchre.ops.watchdogs import WatchdogFinding

        findings = [
            WatchdogFinding(
                watchdog_name="heartbeat_check",
                severity="critical",
                target="plans/sub/heartbeat",
                message="Stale heartbeat",
                threshold="5min",
                recommended_action="Check process",
            ),
        ]

        emitted = _evaluate_retries_for_findings(findings, events_dir)
        assert emitted == 0

    def test_empty_findings_returns_zero(self, events_dir: Path) -> None:
        emitted = _evaluate_retries_for_findings([], events_dir)
        assert emitted == 0

    def test_malformed_target_skipped(self, events_dir: Path) -> None:
        """Findings with unparseable targets are skipped gracefully."""
        from bid_euchre.ops.watchdogs import WatchdogFinding

        findings = [
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="no-colon-here",
                message="Bad target",
                threshold="3 failures",
                recommended_action="Reroute",
            ),
        ]

        emitted = _evaluate_retries_for_findings(findings, events_dir)
        assert emitted == 0

    def test_dedup_skips_already_retried_tasks(self, events_dir: Path) -> None:
        """Tasks with existing retry_attempted events are not re-emitted."""
        from bid_euchre.ops.watchdogs import WatchdogFinding

        # Pre-populate with task failures AND an existing retry_attempted event
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 1"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:01:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 2"},
                }
            ),
            # Existing retry event — should prevent re-emission
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:02:00Z",
                    "event_type": "retry_attempted",
                    "source": "ops.retry",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "retry_count": 2},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        findings = [
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="author-a:t1",
                message="Task t1 failed 2 times",
                threshold="3 failures",
                recommended_action="Reroute",
            ),
        ]

        emitted = _evaluate_retries_for_findings(findings, events_dir)
        assert emitted == 0, "Should skip t1 — retry_attempted already exists"

    def test_dedup_allows_new_tasks(self, events_dir: Path) -> None:
        """Dedup only blocks previously-retried tasks, not new ones."""
        from bid_euchre.ops.events import read_events
        from bid_euchre.ops.watchdogs import WatchdogFinding

        events_file = events_dir / "events.jsonl"
        lines = [
            # t1 already retried
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:00:00Z",
                    "event_type": "retry_attempted",
                    "source": "ops.retry",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "retry_count": 1},
                }
            ),
            # t2 has failures but no retry event yet
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:01:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-b",
                    "payload": {"task_id": "t2", "details": "error"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        findings = [
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="author-a:t1",
                message="Task t1 still failing",
                threshold="3 failures",
                recommended_action="Reroute",
            ),
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="author-b:t2",
                message="Task t2 failed",
                threshold="3 failures",
                recommended_action="Retry",
            ),
        ]

        emitted = _evaluate_retries_for_findings(findings, events_dir)
        # t1 should be skipped (already retried), t2 should emit
        assert emitted == 1

        events = read_events(events_dir)
        new_retry_events = [
            e
            for e in events
            if e["event_type"] in ("retry_attempted", "task_rerouted")
            and e["payload"].get("task_id") == "t2"
        ]
        assert len(new_retry_events) == 1

    def test_tick_integrates_retry_evaluation(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        scheduler_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full tick with subagent failures emits retry events."""
        from bid_euchre.ops import worktrees as wt_mod
        from bid_euchre.ops.events import read_events

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)

        # The watchdog reads events from runtime_dir / "events", and tick
        # also writes events there. Use that directory for both.
        tick_events_dir = runtime_dir / "events"
        tick_events_dir.mkdir(exist_ok=True)

        # Pre-populate event log with repeated task failures
        events_file = tick_events_dir / "events.jsonl"
        lines = []
        for i in range(3):
            lines.append(
                json.dumps(
                    {
                        "timestamp": f"2026-03-20T10:0{i}:00Z",
                        "event_type": "task_failed",
                        "source": "hook",
                        "lane_id": "author-a",
                        "payload": {"task_id": "t1", "details": f"error {i}"},
                    }
                )
            )
        events_file.write_text("\n".join(lines) + "\n")

        tick(runtime_dir, plans_dir, scheduler_dir, tick_events_dir, now=now)

        # The tick should have produced retry events via the
        # subagent_failures watchdog finding 3 failures for t1
        events = read_events(tick_events_dir)
        retry_events = [
            e
            for e in events
            if e["event_type"] in ("retry_attempted", "task_rerouted", "escalation")
        ]
        # 3 failures with default max_retries=3 means reroute
        assert len(retry_events) >= 1

    def test_dedup_skips_already_escalated_tasks(self, events_dir: Path) -> None:
        """Tasks with existing escalation events are not re-processed (#1045)."""
        from bid_euchre.ops.watchdogs import WatchdogFinding

        # Pre-populate with task failures AND an existing escalation event
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 1"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:01:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 2"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:02:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 3"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:03:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 4"},
                }
            ),
            # Existing escalation event -- should prevent re-emission
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:04:00Z",
                    "event_type": "escalation",
                    "source": "ops.retry",
                    "lane_id": "author-a",
                    "payload": {
                        "task_id": "t1",
                        "retry_count": 4,
                        "last_failure": "error 4",
                        "details": "Task t1 exceeded retry cap",
                    },
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        findings = [
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="author-a:t1",
                message="Task t1 failed 4 times",
                threshold="3 failures",
                recommended_action="Escalate",
            ),
        ]

        emitted = _evaluate_retries_for_findings(findings, events_dir)
        assert emitted == 0, "Should skip t1 -- escalation event already exists"

    def test_non_dict_events_skipped(
        self, events_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-dict event entries must be skipped gracefully (#1081)."""
        from bid_euchre.ops import events as events_mod
        from bid_euchre.ops.watchdogs import WatchdogFinding

        real_read = events_mod.read_events

        def patched_read(events_dir_arg, limit=200):
            results = real_read(events_dir_arg, limit=limit)
            # Inject non-dict entries (simulating corrupt data)
            return results + ["not a dict", 42, None]  # type: ignore[list-item]

        monkeypatch.setattr(events_mod, "read_events", patched_read)

        # Pre-populate with a valid failure event
        events_file = events_dir / "events.jsonl"
        events_file.write_text(
            json.dumps(
                {
                    "timestamp": "2026-03-20T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 1"},
                }
            )
            + "\n"
        )

        findings = [
            WatchdogFinding(
                watchdog_name="subagent_failure_check",
                severity="warning",
                target="author-a:t1",
                message="Task t1 failed",
                threshold="3 failures",
                recommended_action="Retry",
            ),
        ]

        # Should not crash despite non-dict events in the log
        emitted = _evaluate_retries_for_findings(findings, events_dir)
        assert isinstance(emitted, int)

    def test_events_are_always_dicts(self, events_dir: Path) -> None:
        """Verify read_events() returns list[dict], validating dead-branch removal (#1042)."""
        from bid_euchre.ops.events import append_event, read_events

        # Write a few events of different types
        append_event(
            event_type="retry_attempted",
            source="test",
            lane_id="test-lane",
            payload={"task_id": "t1"},
            events_dir=events_dir,
        )
        append_event(
            event_type="escalation",
            source="test",
            lane_id="test-lane",
            payload={"task_id": "t2"},
            events_dir=events_dir,
        )

        events = read_events(events_dir)
        assert len(events) >= 2
        for evt in events:
            assert isinstance(evt, dict), f"Expected dict, got {type(evt)}"
