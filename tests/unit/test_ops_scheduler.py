"""Tests for scheduler tick loop (ops/scheduler.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.scheduler import (
    SchedulerState,
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
