"""Tests for Signal 0 (lane heartbeat) and process-tree reconciler in status.py.

Covers the consumer half of issue #2415 (PR 2/3) — the writer half (PR #2686)
is exercised by ``tests/unit/test_lane_heartbeat.py``.  These tests verify
that:

- A fresh heartbeat file produces ``state = "likely_active"`` with
  ``liveness_source = "heartbeat"``.
- A stale heartbeat (exists but past threshold) contributes a stale
  candidate, which may be overridden by fresher signals from S1-S5 or by
  the process-tree reconciler.
- A missing / malformed heartbeat file falls through to S1-S5 so
  back-compat with pre-PR-2686 sessions is preserved.
- The process-tree reconciler only upgrades stale/idle results to
  ``likely_active`` and never downgrades a fresh signal.
- Reads respect cross-worktree heartbeat-file locations (each lane's hook
  writes into its own worktree).

Tests use ``tmp_path`` to build a realistic per-lane heartbeat layout and
monkey-patch ``_detect_background_validation`` to avoid invoking tmux/pgrep.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from bid_euchre.ops.lane_heartbeat import write_heartbeat
from bid_euchre.ops.status import (
    _LivenessProbe,
    _probe_fallback_liveness,
    _resolve_heartbeat_dir,
    synthesize_lane_activity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def now_utc() -> datetime:
    """Frozen reference time for deterministic freshness math."""
    return datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def lane_worktree(tmp_path: Path) -> Path:
    """Create a per-lane worktree layout with .claude/runtime/lane_status."""
    wt = tmp_path / "Bid-Euchre-steward-author-b"
    (wt / ".claude" / "runtime" / "lane_status").mkdir(parents=True)
    return wt


def _write_lane_heartbeat(
    worktree: Path,
    lane_id: str,
    *,
    updated_at: str,
    last_tool: str | None = "Bash",
    phase: str | None = "implementing",
    pid: int = 12345,
) -> Path:
    """Write a heartbeat JSON file directly for controlled aging in tests.

    We sidestep ``write_heartbeat`` because the writer always uses
    ``datetime.now(utc)`` and we need to pin the timestamp to a known past
    value to exercise the stale path.
    """
    path = worktree / ".claude" / "runtime" / "lane_status" / f"{lane_id}.json"
    payload = {
        "schema_version": 1,
        "lane_id": lane_id,
        "pid": pid,
        "session_id": "test-session",
        "updated_at": updated_at,
        "last_tool": last_tool,
        "phase": phase,
        "extras": {"cwd": str(worktree)},
    }
    path.write_text(json.dumps(payload))
    return path


# ---------------------------------------------------------------------------
# _resolve_heartbeat_dir precedence
# ---------------------------------------------------------------------------


class TestResolveHeartbeatDir:
    """Heartbeat directory precedence: worktree > runtime_dir > CWD default."""

    def test_worktree_path_wins(self, tmp_path: Path) -> None:
        wt = tmp_path / "lane-worktree"
        wt.mkdir()
        resolved = _resolve_heartbeat_dir(str(wt), Path("/somewhere/else"))
        assert resolved == wt / ".claude" / "runtime" / "lane_status"

    def test_runtime_dir_fallback(self, tmp_path: Path) -> None:
        rt = tmp_path / "runtime"
        rt.mkdir()
        resolved = _resolve_heartbeat_dir(None, rt)
        assert resolved == rt / "lane_status"

    def test_none_none_defers_to_reader(self) -> None:
        """With no worktree and no runtime_dir, return None so read_heartbeat's
        own default (CWD-relative) takes effect."""
        assert _resolve_heartbeat_dir(None, None) is None


# ---------------------------------------------------------------------------
# Signal 0: fresh/stale/missing heartbeat
# ---------------------------------------------------------------------------


class TestSignalZeroFresh:
    """Fresh heartbeat → likely_active with liveness_source='heartbeat'."""

    def test_fresh_heartbeat_wins_over_stale_event(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # Heartbeat 30s ago ⇒ fresh. Event 60min ago ⇒ stale.
        # Expectation: probe returns 'likely_active' via heartbeat,
        # not stale via events.
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(seconds=30)).isoformat(),
        )
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": (now_utc - timedelta(minutes=60)).isoformat(),
            }
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=events,
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is True
        assert probe.is_stale is False
        assert probe.source == "heartbeat"
        assert "last_tool=Bash" in probe.detail

    def test_boundary_exactly_at_threshold_is_fresh(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # is_fresh uses <= threshold_seconds. At exactly 30min it should
        # still be considered fresh per the documented boundary.
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(minutes=30)).isoformat(),
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is True
        assert probe.source == "heartbeat"


class TestSignalZeroStale:
    """Stale heartbeat contributes a stale candidate, not a fresh result."""

    def test_stale_heartbeat_only_yields_stale_candidate(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # Heartbeat 45min ago ⇒ past 30min threshold. No other signals.
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(minutes=45)).isoformat(),
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is False
        assert probe.is_stale is True
        assert probe.source == "heartbeat"

    def test_stale_heartbeat_with_fresher_event_prefers_event(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # Heartbeat 45min ago (stale). Event 10min ago (fresh).
        # Expectation: probe returns 'likely_active' via events (S1 short
        # circuits once a fresh signal is found).
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(minutes=45)).isoformat(),
        )
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": (now_utc - timedelta(minutes=10)).isoformat(),
            }
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=events,
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is True
        assert probe.source == "events"


class TestSignalZeroMissingOrMalformed:
    """Missing / malformed heartbeat ⇒ fall-through preserves S1-S5 behavior."""

    def test_missing_heartbeat_falls_through_to_events(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # No heartbeat file at all. Event 10min ago drives the probe.
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": (now_utc - timedelta(minutes=10)).isoformat(),
            }
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=events,
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is True
        assert probe.source == "events"

    def test_malformed_heartbeat_treated_as_missing(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # File exists but contains garbage JSON. read_heartbeat returns
        # None, so the probe falls through to S1-S5.
        path = lane_worktree / ".claude" / "runtime" / "lane_status" / "author-b.json"
        path.write_text("{ this is not json")
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is False
        assert probe.is_stale is False
        assert probe.source is None

    def test_heartbeat_with_bad_timestamp_contributes_no_signal(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        # Valid JSON but unparseable updated_at — treat as if we had no
        # heartbeat (both fresh and stale paths guard on _parse_iso).
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at="not-a-timestamp",
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        # No signal ⇒ genuinely idle.
        assert probe.is_likely_live is False
        assert probe.is_stale is False
        assert probe.source is None


# ---------------------------------------------------------------------------
# Process-tree reconciler (opt-in, upgrade-only)
# ---------------------------------------------------------------------------


class TestProcessTreeReconciler:
    """Reconciler only upgrades stale/idle; never downgrades a fresh signal."""

    def test_reconciler_disabled_by_default(
        self,
        lane_worktree: Path,
        now_utc: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With check_process_tree=False (default), the reconciler never
        runs even when pgrep would return a live pytest."""

        calls: list[str] = []

        def fake_detect(*_args: Any, **_kwargs: Any) -> bool:
            calls.append("detect")
            return True

        monkeypatch.setattr(
            "bid_euchre.ops.monitor._detect_background_validation",
            fake_detect,
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
            # check_process_tree defaults to False
        )
        assert probe.is_likely_live is False
        assert probe.source is None
        assert calls == []

    def test_reconciler_upgrades_idle_to_likely_active(
        self,
        lane_worktree: Path,
        now_utc: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No heartbeat, no events, but pytest is running ⇒
        likely_active via process_tree."""

        monkeypatch.setattr(
            "bid_euchre.ops.monitor._detect_background_validation",
            lambda *a, **kw: True,
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
            check_process_tree=True,
        )
        assert probe.is_likely_live is True
        assert probe.is_stale is False
        assert probe.source == "process_tree"

    def test_reconciler_upgrades_stale_heartbeat_to_process_tree(
        self,
        lane_worktree: Path,
        now_utc: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hook-stalled (stale heartbeat) but make/pytest still alive ⇒
        liveness_source flips to process_tree."""

        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(minutes=45)).isoformat(),
        )
        monkeypatch.setattr(
            "bid_euchre.ops.monitor._detect_background_validation",
            lambda *a, **kw: True,
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
            check_process_tree=True,
        )
        assert probe.is_likely_live is True
        assert probe.source == "process_tree"

    def test_reconciler_never_runs_when_fresh_signal_exists(
        self,
        lane_worktree: Path,
        now_utc: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fresh heartbeat short-circuits before the reconciler is reached.
        Protects the "upgrade-only" invariant: with a fresh signal the
        reconciler never runs — not even to re-confirm."""

        calls: list[str] = []

        def should_not_be_called(*_args: Any, **_kwargs: Any) -> bool:
            calls.append("detect")
            return False

        monkeypatch.setattr(
            "bid_euchre.ops.monitor._detect_background_validation",
            should_not_be_called,
        )
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(seconds=10)).isoformat(),
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
            check_process_tree=True,
        )
        assert probe.is_likely_live is True
        assert probe.source == "heartbeat"
        assert calls == [], "Reconciler must not run when a fresh data signal exists"

    def test_reconciler_failure_is_swallowed(
        self,
        lane_worktree: Path,
        now_utc: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the process-tree probe raises, the probe must still return
        a stale/idle result — subprocess errors cannot corrupt status."""

        def boom(*_args: Any, **_kwargs: Any) -> bool:
            raise RuntimeError("tmux not available")

        monkeypatch.setattr(
            "bid_euchre.ops.monitor._detect_background_validation",
            boom,
        )
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now_utc,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
            check_process_tree=True,
        )
        # With no other signals and reconciler-raise, the probe returns
        # the default idle result.
        assert probe.is_likely_live is False
        assert probe.is_stale is False
        assert probe.source is None


# ---------------------------------------------------------------------------
# synthesize_lane_activity integration
# ---------------------------------------------------------------------------


class TestSynthesizeWithHeartbeat:
    """End-to-end: heartbeat signal propagates into LaneStatus."""

    def test_lane_becomes_likely_active_from_fresh_heartbeat(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(seconds=5)).isoformat(),
        )
        lanes = [
            {
                "lane_id": "author-b",
                "lane_class": "author",
                "worktree_path": str(lane_worktree),
                "branch": "feat/x",
                "class": "persistent",
                "session_id": None,
                "last_active": None,
            }
        ]
        result = synthesize_lane_activity(
            lanes, {}, {}, [], now=now_utc, check_worktree=False
        )
        lane = result[0]
        assert lane.state == "likely_active"
        assert lane.liveness_source == "heartbeat"
        assert lane.attention_needed is False

    def test_lane_without_heartbeat_preserves_legacy_idle(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        """Regression guard: when no heartbeat file exists and no other
        signal fires, the lane stays at its prior classification (idle)."""
        lanes = [
            {
                "lane_id": "author-b",
                "lane_class": "author",
                "worktree_path": str(lane_worktree),  # no heartbeat written
                "branch": "feat/x",
                "class": "persistent",
                "session_id": None,
                "last_active": None,
            }
        ]
        result = synthesize_lane_activity(
            lanes, {}, {}, [], now=now_utc, check_worktree=False
        )
        lane = result[0]
        assert lane.state == "idle"
        assert lane.liveness_source is None

    def test_fresh_heartbeat_suppresses_stale_attention(
        self,
        lane_worktree: Path,
        now_utc: datetime,
    ) -> None:
        """Core F1 fix: a lane whose only non-heartbeat signals are >30min
        stale must render as likely_active (not stale) and not raise the
        attention flag.  This is the failure mode that drove #2415."""
        _write_lane_heartbeat(
            lane_worktree,
            "author-b",
            updated_at=(now_utc - timedelta(seconds=20)).isoformat(),
        )
        lanes = [
            {
                "lane_id": "author-b",
                "lane_class": "author",
                "worktree_path": str(lane_worktree),
                "branch": "feat/x",
                "class": "persistent",
                "session_id": None,
                # last_active 60min ago — would have flipped to stale pre-PR-2
                "last_active": (now_utc - timedelta(minutes=60)).isoformat(),
            }
        ]
        result = synthesize_lane_activity(
            lanes, {}, {}, [], now=now_utc, check_worktree=False
        )
        lane = result[0]
        assert lane.state == "likely_active"
        assert lane.attention_needed is False


# ---------------------------------------------------------------------------
# write_heartbeat round-trip (integration smoke)
# ---------------------------------------------------------------------------


class TestWriteReadRoundTrip:
    """End-to-end: real write_heartbeat feeds the probe correctly."""

    def test_fresh_write_reads_as_likely_active(
        self,
        lane_worktree: Path,
    ) -> None:
        hb_dir = lane_worktree / ".claude" / "runtime" / "lane_status"
        write_heartbeat(
            "author-b",
            tool_name="Bash",
            phase="implementing",
            runtime_dir=hb_dir,
        )
        now = datetime.now(timezone.utc)
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now,
            stale_minutes=30,
            worktree_path=str(lane_worktree),
            check_worktree=False,
        )
        assert probe.is_likely_live is True
        assert probe.source == "heartbeat"


# ---------------------------------------------------------------------------
# _LivenessProbe sanity
# ---------------------------------------------------------------------------


def test_liveness_probe_shape_unchanged() -> None:
    """Guard against accidental API drift on the probe result type.

    PR 3/3 and downstream consumers depend on these four attributes."""
    probe = _LivenessProbe(
        is_likely_live=True, is_stale=False, source="heartbeat", detail="x"
    )
    assert probe.is_likely_live is True
    assert probe.is_stale is False
    assert probe.source == "heartbeat"
    assert probe.detail == "x"
