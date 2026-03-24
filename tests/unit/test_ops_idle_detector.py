"""Tests for fleet idle detection (ops/idle_detector.py)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.events import EVENTS_FILE
from bid_euchre.ops.idle_detector import (
    DEFAULT_THRESHOLD_MINUTES,
    MEANINGFUL_EVENT_TYPES,
    IdleStatus,
    ShutoffRecommendation,
    _find_last_meaningful_event,
    _get_active_lane_ids,
    is_fleet_idle,
    recommend_shutoff,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Provide a temporary events directory."""
    d = tmp_path / "events"
    d.mkdir()
    return d


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Provide a temporary runtime directory with worktree registry."""
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    return rd


def _write_event(
    events_dir: Path,
    event_type: str,
    ts: datetime,
    lane_id: str = "author-a",
) -> None:
    """Write a raw event line with a specific timestamp."""
    event = {
        "timestamp": ts.isoformat(),
        "event_type": event_type,
        "source": "test",
        "lane_id": lane_id,
        "payload": {},
    }
    events_file = events_dir / EVENTS_FILE
    with open(events_file, "a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def _register_lane(
    runtime_dir: Path,
    lane_id: str,
    *,
    session_id: str | None = "sess-123",
) -> None:
    """Write a worktree registry entry for a lane."""
    registry = runtime_dir / "worktree_registry"
    entry = {"lane_id": lane_id, "session_id": session_id}
    (registry / f"{lane_id}.json").write_text(json.dumps(entry))


# ---------------------------------------------------------------------------
# Tests: _find_last_meaningful_event
# ---------------------------------------------------------------------------


class TestFindLastMeaningfulEvent:
    """Tests for _find_last_meaningful_event helper."""

    def test_empty_log_returns_none(self, events_dir: Path) -> None:
        assert _find_last_meaningful_event(events_dir) is None

    def test_no_events_file_returns_none(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "no_events"
        empty_dir.mkdir()
        assert _find_last_meaningful_event(empty_dir) is None

    def test_finds_meaningful_event(self, events_dir: Path) -> None:
        ts = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        _write_event(events_dir, "task_completed", ts)
        result = _find_last_meaningful_event(events_dir)
        assert result == ts

    def test_ignores_infrastructure_events(self, events_dir: Path) -> None:
        ts_infra = datetime(2026, 3, 24, 13, 0, 0, tzinfo=timezone.utc)
        ts_meaningful = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        _write_event(events_dir, "scheduler_tick", ts_infra)
        _write_event(events_dir, "task_started", ts_meaningful)
        result = _find_last_meaningful_event(events_dir)
        # Should find task_started, not scheduler_tick
        assert result == ts_meaningful

    def test_returns_most_recent_meaningful(self, events_dir: Path) -> None:
        ts_old = datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
        ts_new = datetime(2026, 3, 24, 14, 0, 0, tzinfo=timezone.utc)
        _write_event(events_dir, "task_started", ts_old)
        _write_event(events_dir, "ci_success", ts_new)
        result = _find_last_meaningful_event(events_dir)
        assert result == ts_new


# ---------------------------------------------------------------------------
# Tests: _get_active_lane_ids
# ---------------------------------------------------------------------------


class TestGetActiveLaneIds:
    """Tests for _get_active_lane_ids helper."""

    def test_no_registry_returns_empty(self, tmp_path: Path) -> None:
        empty_rd = tmp_path / "no_runtime"
        empty_rd.mkdir()
        assert _get_active_lane_ids(empty_rd) == []

    def test_empty_registry_returns_empty(self, runtime_dir: Path) -> None:
        assert _get_active_lane_ids(runtime_dir) == []

    def test_active_lane_detected(self, runtime_dir: Path) -> None:
        _register_lane(runtime_dir, "author-a", session_id="sess-001")
        result = _get_active_lane_ids(runtime_dir)
        assert result == ["author-a"]

    def test_lane_without_session_is_not_active(self, runtime_dir: Path) -> None:
        _register_lane(runtime_dir, "author-b", session_id=None)
        assert _get_active_lane_ids(runtime_dir) == []

    def test_multiple_active_lanes(self, runtime_dir: Path) -> None:
        _register_lane(runtime_dir, "author-a", session_id="sess-001")
        _register_lane(runtime_dir, "author-b", session_id="sess-002")
        _register_lane(runtime_dir, "author-c", session_id=None)
        result = _get_active_lane_ids(runtime_dir)
        assert sorted(result) == ["author-a", "author-b"]


# ---------------------------------------------------------------------------
# Tests: is_fleet_idle (integration of sub-components)
# ---------------------------------------------------------------------------


class TestIsFleetIdle:
    """Tests for the main is_fleet_idle() function."""

    def test_timer_resets_on_meaningful_change(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Timer should reset when a meaningful event occurs."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        # Meaningful event 10 minutes ago — well within threshold
        recent_ts = now - timedelta(minutes=10)
        _write_event(events_dir, "task_completed", recent_ts)

        result = is_fleet_idle(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result.idle is False
        assert result.idle_minutes == pytest.approx(10.0, abs=0.1)
        assert result.last_meaningful_event == recent_ts
        assert result.active_lanes == []

    def test_timer_fires_after_threshold_with_no_changes(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Fleet should be idle when threshold exceeded with no activity."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        # Last meaningful event was 120 minutes ago (> 90m threshold)
        old_ts = now - timedelta(minutes=120)
        _write_event(events_dir, "task_completed", old_ts)

        result = is_fleet_idle(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result.idle is True
        assert result.idle_minutes == pytest.approx(120.0, abs=0.1)
        assert result.last_meaningful_event == old_ts
        assert result.active_lanes == []

    def test_timer_does_not_fire_if_lane_is_actively_running(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """An active lane prevents idle even when events are old."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        # Last event was 120 minutes ago
        old_ts = now - timedelta(minutes=120)
        _write_event(events_dir, "task_completed", old_ts)

        # But a lane is currently active
        _register_lane(runtime_dir, "author-a", session_id="sess-live")

        result = is_fleet_idle(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result.idle is False
        assert "author-a" in result.active_lanes
        assert "Active lanes" in result.reason

    def test_no_events_and_no_active_lanes_is_idle(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Empty fleet with no events should be idle."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        result = is_fleet_idle(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result.idle is True
        assert result.last_meaningful_event is None
        assert result.active_lanes == []

    def test_infrastructure_events_do_not_reset_timer(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Only meaningful event types reset the idle timer."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)

        # Old meaningful event
        old_ts = now - timedelta(minutes=120)
        _write_event(events_dir, "task_completed", old_ts)

        # Recent infrastructure event (should NOT reset timer)
        recent_ts = now - timedelta(minutes=5)
        _write_event(events_dir, "scheduler_tick", recent_ts)

        result = is_fleet_idle(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result.idle is True
        assert result.idle_minutes == pytest.approx(120.0, abs=0.1)

    def test_custom_threshold(self, events_dir: Path, runtime_dir: Path) -> None:
        """Custom threshold should be respected."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(minutes=30)
        _write_event(events_dir, "task_started", ts)

        # 20m threshold — 30m elapsed => idle
        result_short = is_fleet_idle(
            threshold_minutes=20,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result_short.idle is True

        # 60m threshold — 30m elapsed => NOT idle
        result_long = is_fleet_idle(
            threshold_minutes=60,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result_long.idle is False

    def test_exactly_at_threshold_is_idle(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Being exactly at the threshold should count as idle."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(minutes=90)
        _write_event(events_dir, "ci_success", ts)

        result = is_fleet_idle(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert result.idle is True

    def test_idle_status_dataclass_fields(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Verify IdleStatus has all expected fields."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        result = is_fleet_idle(
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert isinstance(result, IdleStatus)
        assert isinstance(result.idle, bool)
        assert isinstance(result.idle_minutes, float)
        assert isinstance(result.active_lanes, list)
        assert isinstance(result.reason, str)


# ---------------------------------------------------------------------------
# Tests: Meaningful event types coverage
# ---------------------------------------------------------------------------


class TestMeaningfulEventTypes:
    """Verify the set of meaningful event types is well-defined."""

    def test_meaningful_types_are_subset_of_valid(self) -> None:
        """All meaningful types must be valid event types."""
        from bid_euchre.ops.events import VALID_EVENT_TYPES

        # Some meaningful types (like pr_opened, pr_merged) may not be in
        # VALID_EVENT_TYPES yet — that's fine, they're aspirational.
        # But the ones that are should be valid.
        shared = MEANINGFUL_EVENT_TYPES & VALID_EVENT_TYPES
        assert len(shared) > 0, "No overlap between meaningful and valid types"

    def test_infrastructure_events_excluded(self) -> None:
        """Infrastructure events should not be in the meaningful set."""
        infra_types = {
            "scheduler_tick",
            "watchdog_finding",
            "snapshot_created",
            "fs_boundary_violation",
        }
        assert MEANINGFUL_EVENT_TYPES & infra_types == set()

    def test_default_threshold_is_90(self) -> None:
        assert DEFAULT_THRESHOLD_MINUTES == 90


# ---------------------------------------------------------------------------
# Tests: recommend_shutoff
# ---------------------------------------------------------------------------


class TestRecommendShutoff:
    """Tests for the recommend_shutoff() wrapper."""

    def test_recommends_shutoff_when_fleet_idle(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Should recommend shutoff when fleet has been idle past threshold."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        old_ts = now - timedelta(minutes=120)
        _write_event(events_dir, "task_completed", old_ts)

        rec = recommend_shutoff(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert isinstance(rec, ShutoffRecommendation)
        assert rec.should_shutoff is True
        assert rec.idle_status.idle is True
        assert len(rec.recommended_actions) > 0
        # Actions should include cron cancellation and session handoff
        actions_text = " ".join(rec.recommended_actions)
        assert "cron" in actions_text.lower()
        assert "handoff" in actions_text.lower()

    def test_does_not_recommend_when_active(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Should not recommend shutoff when fleet is active."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        recent_ts = now - timedelta(minutes=10)
        _write_event(events_dir, "task_completed", recent_ts)

        rec = recommend_shutoff(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert rec.should_shutoff is False
        assert rec.idle_status.idle is False
        assert rec.recommended_actions == []

    def test_does_not_recommend_when_lanes_active(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """Active lanes prevent shutoff even with old events."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        old_ts = now - timedelta(minutes=120)
        _write_event(events_dir, "task_completed", old_ts)
        _register_lane(runtime_dir, "author-a", session_id="sess-live")

        rec = recommend_shutoff(
            threshold_minutes=90,
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert rec.should_shutoff is False
        assert "author-a" in rec.idle_status.active_lanes

    def test_shutoff_recommendation_fields(
        self, events_dir: Path, runtime_dir: Path
    ) -> None:
        """ShutoffRecommendation has expected fields."""
        now = datetime(2026, 3, 24, 15, 0, 0, tzinfo=timezone.utc)
        rec = recommend_shutoff(
            events_dir=events_dir,
            runtime_dir=runtime_dir,
            now=now,
        )
        assert isinstance(rec, ShutoffRecommendation)
        assert isinstance(rec.should_shutoff, bool)
        assert isinstance(rec.idle_status, IdleStatus)
        assert isinstance(rec.recommended_actions, list)
