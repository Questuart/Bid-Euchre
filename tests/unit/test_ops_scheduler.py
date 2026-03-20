"""Tests for scheduler tick loop and daemon mode (ops/scheduler.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.scheduler import (
    DEFAULT_CHECKS,
    MAX_DAEMON_ITERATIONS,
    DaemonResult,
    SchedulerState,
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
