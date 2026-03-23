"""Tests for ops worker pool lifecycle management (Platform-7)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bid_euchre.ops.worker_pool import (
    DEFAULT_TMUX_SESSION,
    IDLE_PARK_MINUTES,
    LANE_DOMAINS,
    MAX_ACTIVE_AUTHORS,
    PARKED_RETIRE_MINUTES,
    POOL_STATUSES,
    PoolAction,
    PoolSnapshot,
    WorkerState,
    _classify_pool_status,
    _get_lane_task_id,
    _managed_lanes,
    _minutes_since,
    _probe_tmux_pane,
    _resolve_agent_name,
    _resolve_tmux_target,
    dispatch_to_worker,
    format_action_text,
    format_actions_json,
    format_pool_json,
    format_pool_text,
    get_lane_domain,
    nudge_pane,
    park_worker,
    retire_worker,
    run_pool_maintenance,
    select_worker,
    take_pool_snapshot,
    wake_worker,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temp runtime directory with standard subdirs."""
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "session_metadata").mkdir(parents=True)
    (rd / "task_state").mkdir(parents=True)
    (rd / "events").mkdir(parents=True)
    (rd / "task_queue").mkdir(parents=True)
    return rd


def _write_json(directory: Path, filename: str, data: dict) -> None:
    (directory / filename).write_text(json.dumps(data, indent=2))


def _make_worker(
    lane_id: str = "author-a",
    pool_status: str = "idle",
    health: str = "idle",
    current_task_id: str | None = None,
    last_activity: str | None = None,
    visibility: str = "background",
    tmux_alive: bool = True,
    session_handle: str | None = None,
    domain: str | None = None,
) -> WorkerState:
    """Create a WorkerState for testing."""
    return WorkerState(
        lane_id=lane_id,
        pool_status=pool_status,
        health=health,
        current_task_id=current_task_id,
        last_activity=last_activity,
        visibility=visibility,
        tmux_alive=tmux_alive,
        session_handle=session_handle,
        domain=domain,
    )


def _make_pool(
    workers: list[WorkerState] | None = None,
    timestamp: str = "2026-03-22T12:00:00+00:00",
) -> PoolSnapshot:
    """Create a PoolSnapshot for testing."""
    if workers is None:
        workers = []
    active = sum(1 for w in workers if w.pool_status == "active")
    idle = sum(1 for w in workers if w.pool_status == "idle")
    parked = sum(1 for w in workers if w.pool_status == "parked")
    retired = sum(1 for w in workers if w.pool_status == "retired")
    return PoolSnapshot(
        timestamp=timestamp,
        workers=workers,
        active_count=active,
        idle_count=idle,
        parked_count=parked,
        retired_count=retired,
        available_capacity=max(0, MAX_ACTIVE_AUTHORS - active),
    )


# Patch targets: since the functions use deferred imports (``from X import Y``
# inside the function body), we must patch at the *source* module path so that
# the fresh import picks up the mock.
_DASHBOARD = "bid_euchre.ops.dashboard"
_STATUS = "bid_euchre.ops.status"
_SUPERVISOR = "bid_euchre.ops.supervisor"
_TASK_QUEUE = "bid_euchre.ops.task_queue"
_WORKER_POOL = "bid_euchre.ops.worker_pool"


# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------


class TestConstants:
    """Test module-level constants."""

    def test_max_active_authors(self) -> None:
        assert MAX_ACTIVE_AUTHORS == 12

    def test_idle_park_minutes(self) -> None:
        assert IDLE_PARK_MINUTES == 15

    def test_parked_retire_minutes(self) -> None:
        assert PARKED_RETIRE_MINUTES == 60

    def test_default_tmux_session(self) -> None:
        assert DEFAULT_TMUX_SESSION == "steward"

    def test_pool_statuses(self) -> None:
        assert POOL_STATUSES == {"active", "idle", "parked", "retired"}

    def test_managed_lanes(self) -> None:
        lanes = _managed_lanes()
        assert "author-a" in lanes
        assert "author-b" in lanes
        assert "author-scratch" in lanes
        assert "brws-author-a" in lanes
        assert "flex-a" in lanes
        assert len(lanes) == 12


class TestResolveAgentName:
    """Test _resolve_agent_name()."""

    def test_author_a(self) -> None:
        assert _resolve_agent_name("author-a") == "steward-author-a"

    def test_author_scratch(self) -> None:
        assert _resolve_agent_name("author-scratch") == "steward-author-scratch"

    def test_author_b(self) -> None:
        assert _resolve_agent_name("author-b") == "steward-author-b"


class TestMinutesSince:
    """Test _minutes_since()."""

    def test_none_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        assert _minutes_since(None, now) is None

    def test_empty_string(self) -> None:
        now = datetime.now(timezone.utc)
        assert _minutes_since("", now) is None

    def test_valid_timestamp(self) -> None:
        now = datetime(2026, 3, 22, 12, 30, 0, tzinfo=timezone.utc)
        ts = "2026-03-22T12:00:00+00:00"
        result = _minutes_since(ts, now)
        assert result is not None
        assert abs(result - 30.0) < 0.01

    def test_z_suffix(self) -> None:
        now = datetime(2026, 3, 22, 12, 15, 0, tzinfo=timezone.utc)
        ts = "2026-03-22T12:00:00Z"
        result = _minutes_since(ts, now)
        assert result is not None
        assert abs(result - 15.0) < 0.01

    def test_invalid_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        assert _minutes_since("not-a-date", now) is None


class TestClassifyPoolStatus:
    """Test _classify_pool_status()."""

    def test_hidden_tmux_alive_is_parked(self) -> None:
        lane = MagicMock(state="idle")
        assert _classify_pool_status(lane, "idle", False, True, "hidden") == "parked"

    def test_hidden_tmux_dead_is_retired(self) -> None:
        lane = MagicMock(state="idle")
        assert _classify_pool_status(lane, "idle", False, False, "hidden") == "retired"

    def test_active_task_is_active(self) -> None:
        lane = MagicMock(state="idle")
        assert (
            _classify_pool_status(lane, "healthy", True, True, "foreground") == "active"
        )

    def test_active_state_no_task_is_idle(self) -> None:
        """BD-001: active state without a task should be idle (dispatchable)."""
        lane = MagicMock(state="active")
        assert (
            _classify_pool_status(lane, "healthy", False, True, "foreground") == "idle"
        )

    def test_likely_active_no_task_is_idle(self) -> None:
        """BD-001: likely_active state without a task should be idle (dispatchable)."""
        lane = MagicMock(state="likely_active")
        assert (
            _classify_pool_status(lane, "healthy", False, True, "background") == "idle"
        )

    def test_active_state_with_task_is_active(self) -> None:
        """Active state WITH a task should still be active."""
        lane = MagicMock(state="active")
        assert (
            _classify_pool_status(lane, "healthy", True, True, "foreground") == "active"
        )

    def test_likely_active_with_task_is_active(self) -> None:
        """likely_active state WITH a task should still be active."""
        lane = MagicMock(state="likely_active")
        assert (
            _classify_pool_status(lane, "healthy", True, True, "background") == "active"
        )

    def test_no_task_background_is_idle(self) -> None:
        lane = MagicMock(state="idle")
        assert _classify_pool_status(lane, "idle", False, True, "background") == "idle"


# ---------------------------------------------------------------------------
# _get_lane_task_id — task_queue_root correctness
# ---------------------------------------------------------------------------


class TestGetLaneTaskId:
    """Test _get_lane_task_id() passes task_queue subdirectory, not runtime_dir."""

    @patch(f"{_TASK_QUEUE}.list_packets", return_value=[])
    def test_passes_task_queue_subdir(
        self,
        mock_list: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Verify list_packets receives runtime_dir/'task_queue', not runtime_dir."""
        result = _get_lane_task_id("author-a", runtime_dir)
        assert result is None
        mock_list.assert_called_once()
        actual_root = mock_list.call_args[0][0]
        assert actual_root == runtime_dir / "task_queue"

    @patch(f"{_TASK_QUEUE}.list_packets", return_value=[])
    def test_none_runtime_dir_passes_none(
        self,
        mock_list: MagicMock,
    ) -> None:
        """When runtime_dir is None, pass None so shared_task_root() defaults."""
        _get_lane_task_id("author-a", None)
        mock_list.assert_called_once()
        actual_root = mock_list.call_args[0][0]
        assert actual_root is None

    @patch(f"{_TASK_QUEUE}.list_packets")
    def test_returns_packet_id(
        self,
        mock_list: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        mock_list.return_value = [
            TaskPacket(
                packet_id="pkt42",
                title="Test",
                description="d",
                owner="author-a",
                created_by="orchestrator",
                created_at="2026-03-22T12:00:00Z",
                status="dispatched",
            )
        ]
        result = _get_lane_task_id("author-a", runtime_dir)
        assert result == "pkt42"


# ---------------------------------------------------------------------------
# Probe tmux pane
# ---------------------------------------------------------------------------


class TestResolveTmuxTarget:
    """Test _resolve_tmux_target() registry-based target resolution."""

    def test_registry_with_window_and_pane(self, tmp_path: Path) -> None:
        """When registry has tmux_window and tmux_pane, use them."""
        registry_dir = tmp_path / "worktree_registry"
        registry_dir.mkdir()
        entry = {"tmux_window": "platform", "tmux_pane": "1"}
        (registry_dir / "author-a.json").write_text(json.dumps(entry))
        result = _resolve_tmux_target("author-a", "steward", tmp_path)
        assert result == "steward:platform.1"

    def test_registry_missing_falls_back(self, tmp_path: Path) -> None:
        """When registry file is missing, fall back to session:lane_id."""
        result = _resolve_tmux_target("author-a", "steward", tmp_path)
        assert result == "steward:author-a"

    def test_registry_no_pane_falls_back(self, tmp_path: Path) -> None:
        """When registry has window but no pane, fall back."""
        registry_dir = tmp_path / "worktree_registry"
        registry_dir.mkdir()
        entry = {"tmux_window": "platform"}
        (registry_dir / "author-a.json").write_text(json.dumps(entry))
        result = _resolve_tmux_target("author-a", "steward", tmp_path)
        assert result == "steward:author-a"

    def test_registry_pane_zero_is_valid(self, tmp_path: Path) -> None:
        """Pane index 0 should not be treated as falsy.

        Even though production uses 1-based indices (pane-base-index=1),
        the function must handle 0 without treating it as a missing value.
        """
        registry_dir = tmp_path / "worktree_registry"
        registry_dir.mkdir()
        entry = {"tmux_window": "central-ops", "tmux_pane": "0"}
        (registry_dir / "orchestrator.json").write_text(json.dumps(entry))
        result = _resolve_tmux_target("orchestrator", "steward", tmp_path)
        assert result == "steward:central-ops.0"


class TestProbeTmuxPane:
    """Test _probe_tmux_pane() with mocked subprocess.

    The function now uses ``tmux display-message -t <target> -p #{pane_pid}``
    to probe pane liveness, with the target resolved from registry metadata.
    """

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_pane_alive(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")
        assert _probe_tmux_pane("author-a", "steward") is True

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_pane_not_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert _probe_tmux_pane("author-a", "steward") is False

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_tmux_not_available(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("tmux not found")
        assert _probe_tmux_pane("author-a", "steward") is False

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_tmux_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert _probe_tmux_pane("author-a", "steward") is False

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_tmux_timeout(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)
        assert _probe_tmux_pane("author-a", "steward") is False

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_empty_stdout(self, mock_run: MagicMock) -> None:
        """Pane exists but pid is empty — treat as not alive."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert _probe_tmux_pane("author-a", "steward") is False

    def test_with_registry_target(self, tmp_path: Path) -> None:
        """When registry provides window.pane, probe targets that."""
        registry_dir = tmp_path / "worktree_registry"
        registry_dir.mkdir()
        entry = {"tmux_window": "platform", "tmux_pane": "1"}
        (registry_dir / "author-a.json").write_text(json.dumps(entry))
        with patch(f"{_WORKER_POOL}.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")
            result = _probe_tmux_pane("author-a", "steward", runtime_dir=tmp_path)
            assert result is True
            # Verify it targeted the correct 1-based pane
            call_args = mock_run.call_args[0][0]
            assert "steward:platform.1" in call_args


# ---------------------------------------------------------------------------
# Select worker
# ---------------------------------------------------------------------------


class TestSelectWorker:
    """Test select_worker() priority logic."""

    def test_preferred_lane_idle(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle"),
                _make_worker("author-b", "idle"),
            ]
        )
        assert select_worker(pool, preferred_lane="author-b") == "author-b"

    def test_preferred_lane_parked(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle"),
                _make_worker("author-b", "parked"),
            ]
        )
        assert select_worker(pool, preferred_lane="author-b") == "author-b"

    def test_preferred_lane_active_skipped(self) -> None:
        """If preferred lane is active, fall through to idle."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle"),
                _make_worker("author-b", "active", current_task_id="t1"),
            ]
        )
        assert select_worker(pool, preferred_lane="author-b") == "author-a"

    def test_idle_before_parked(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "parked"),
                _make_worker("author-b", "idle"),
            ]
        )
        assert select_worker(pool) == "author-b"

    def test_parked_before_retired(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "retired"),
                _make_worker("author-b", "parked"),
            ]
        )
        assert select_worker(pool) == "author-b"

    def test_retired_selected_as_last_resort(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "retired"),
            ]
        )
        assert select_worker(pool) == "author-a"

    def test_no_capacity(self) -> None:
        """At MAX_ACTIVE_AUTHORS, returns None."""
        # Create 12 active workers to fill the dual-domain layout capacity
        lane_ids = [
            "author-a",
            "author-b",
            "author-c",
            "author-d",
            "author-scratch",
            "brws-author-a",
            "brws-author-b",
            "brws-author-c",
            "brws-author-d",
            "flex-a",
            "flex-b",
            "flex-c",
        ]
        workers = [
            _make_worker(lid, "active", current_task_id=f"t{i}")
            for i, lid in enumerate(lane_ids)
        ]
        pool = _make_pool(workers)
        assert pool.available_capacity == 0
        assert select_worker(pool) is None

    def test_critical_health_skipped(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", health="critical"),
                _make_worker("author-b", "idle", health="healthy"),
            ]
        )
        assert select_worker(pool) == "author-b"

    def test_all_critical_returns_none(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", health="critical"),
            ]
        )
        assert select_worker(pool) is None

    def test_empty_pool(self) -> None:
        pool = _make_pool([])
        assert select_worker(pool) is None

    def test_preferred_lane_not_in_pool(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle"),
            ]
        )
        assert select_worker(pool, preferred_lane="author-z") == "author-a"

    def test_preferred_retired(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle"),
                _make_worker("author-b", "retired"),
            ]
        )
        assert select_worker(pool, preferred_lane="author-b") == "author-b"


# ---------------------------------------------------------------------------
# Domain routing
# ---------------------------------------------------------------------------


class TestDomainRouting:
    """Test domain-aware select_worker() routing."""

    def test_get_lane_domain(self) -> None:
        """get_lane_domain returns configured domain or None."""
        assert get_lane_domain("author-a") == "platform"
        assert get_lane_domain("author-scratch") is None
        assert get_lane_domain("brws-author-a") == "browser-game"
        assert get_lane_domain("flex-a") is None
        assert get_lane_domain("unknown-lane") is None

    def test_lane_domains_constant(self) -> None:
        """LANE_DOMAINS covers all known author lanes."""
        from bid_euchre.ops.task_queue import KNOWN_AUTHOR_LANES

        assert set(LANE_DOMAINS.keys()) == set(KNOWN_AUTHOR_LANES)

    def test_same_domain_preferred(self) -> None:
        """Same-domain lane selected over flex lane."""
        pool = _make_pool(
            [
                _make_worker("author-scratch", "idle", domain=None),  # flex
                _make_worker("author-a", "idle", domain="platform"),
            ]
        )
        assert select_worker(pool, domain="platform") == "author-a"

    def test_flex_used_when_no_same_domain(self) -> None:
        """Flex lane selected when no same-domain lanes available."""
        pool = _make_pool(
            [
                _make_worker(
                    "author-a", "active", domain="platform", current_task_id="t1"
                ),
                _make_worker("author-scratch", "idle", domain=None),  # flex
            ]
        )
        assert select_worker(pool, domain="platform") == "author-scratch"

    def test_cross_domain_rejected_by_default(self) -> None:
        """Cross-domain lanes not selected without allow_cross_domain."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
            ]
        )
        assert select_worker(pool, domain="browser-game") is None

    def test_cross_domain_allowed_with_override(self) -> None:
        """Cross-domain lanes selected when allow_cross_domain=True."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
            ]
        )
        result = select_worker(pool, domain="browser-game", allow_cross_domain=True)
        assert result == "author-a"

    def test_no_domain_selects_any(self) -> None:
        """When domain=None, all lanes are eligible (backward compat)."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
                _make_worker("author-b", "idle", domain="browser-game"),
            ]
        )
        # Should pick first idle regardless of domain
        assert select_worker(pool, domain=None) == "author-a"

    def test_domain_routing_prefers_idle_same_domain_over_parked(self) -> None:
        """Idle same-domain preferred over parked same-domain."""
        pool = _make_pool(
            [
                _make_worker("author-a", "parked", domain="platform"),
                _make_worker("author-b", "idle", domain="platform"),
            ]
        )
        assert select_worker(pool, domain="platform") == "author-b"

    def test_domain_routing_parked_same_domain_over_idle_flex(self) -> None:
        """Parked same-domain NOT preferred over idle flex — idle tier wins."""
        pool = _make_pool(
            [
                _make_worker("author-a", "parked", domain="platform"),
                _make_worker("author-scratch", "idle", domain=None),
            ]
        )
        # Idle (any domain-compatible) should beat parked
        assert select_worker(pool, domain="platform") == "author-scratch"

    def test_preferred_lane_domain_incompatible(self) -> None:
        """Preferred lane skipped if domain-incompatible."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
                _make_worker("author-b", "idle", domain="browser-game"),
            ]
        )
        # author-b is browser-game, but we want platform — should skip it
        result = select_worker(pool, preferred_lane="author-b", domain="platform")
        assert result == "author-a"

    def test_preferred_lane_domain_compatible(self) -> None:
        """Preferred lane selected when domain-compatible."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
                _make_worker("author-b", "idle", domain="platform"),
            ]
        )
        result = select_worker(pool, preferred_lane="author-b", domain="platform")
        assert result == "author-b"

    def test_flex_preferred_lane(self) -> None:
        """Flex preferred lane is domain-compatible with any domain."""
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
                _make_worker("author-scratch", "idle", domain=None),
            ]
        )
        result = select_worker(
            pool, preferred_lane="author-scratch", domain="browser-game"
        )
        assert result == "author-scratch"

    def test_worker_state_domain_field(self) -> None:
        """WorkerState has domain field."""
        w = _make_worker("author-a", "idle", domain="platform")
        assert w.domain == "platform"
        w_flex = _make_worker("author-scratch", "idle", domain=None)
        assert w_flex.domain is None


class TestLaneExpansion:
    """Test expanded lane identity (SP-3-05 PR 2)."""

    def test_known_lanes_include_browser_and_flex(self) -> None:
        from bid_euchre.ops.task_queue import KNOWN_AUTHOR_LANES

        # Browser-game pool
        assert "brws-author-a" in KNOWN_AUTHOR_LANES
        assert "brws-author-d" in KNOWN_AUTHOR_LANES
        # Flex pool
        assert "flex-a" in KNOWN_AUTHOR_LANES
        assert "flex-c" in KNOWN_AUTHOR_LANES
        # Original platform pool still present
        assert "author-a" in KNOWN_AUTHOR_LANES
        assert "author-scratch" in KNOWN_AUTHOR_LANES

    def test_browser_lanes_have_browser_game_domain(self) -> None:
        assert get_lane_domain("brws-author-a") == "browser-game"
        assert get_lane_domain("brws-author-b") == "browser-game"
        assert get_lane_domain("brws-author-c") == "browser-game"
        assert get_lane_domain("brws-author-d") == "browser-game"

    def test_flex_lanes_have_none_domain(self) -> None:
        assert get_lane_domain("flex-a") is None
        assert get_lane_domain("flex-b") is None
        assert get_lane_domain("flex-c") is None

    def test_persistent_lanes_include_new_pools(self) -> None:
        from bid_euchre.ops.recovery import PERSISTENT_LANES

        assert "brws-author-a" in PERSISTENT_LANES
        assert "flex-a" in PERSISTENT_LANES

    def test_protected_worktrees_include_new_pools(self) -> None:
        from bid_euchre.ops.worktrees import PROTECTED_WORKTREE_NAMES

        assert "Bid-Euchre-steward-brws-author-a" in PROTECTED_WORKTREE_NAMES
        assert "Bid-Euchre-steward-flex-a" in PROTECTED_WORKTREE_NAMES

    def test_task_packet_accepts_browser_lane_owner(self) -> None:
        from bid_euchre.ops.task_queue import create_packet

        pkt = create_packet("test", "desc", owner="brws-author-a")
        assert pkt.owner == "brws-author-a"

    def test_task_packet_accepts_flex_lane_owner(self) -> None:
        from bid_euchre.ops.task_queue import create_packet

        pkt = create_packet("test", "desc", owner="flex-b")
        assert pkt.owner == "flex-b"

    def test_select_worker_with_browser_game_domain(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
                _make_worker("brws-author-a", "idle", domain="browser-game"),
            ]
        )
        assert select_worker(pool, domain="browser-game") == "brws-author-a"

    def test_select_worker_flex_fallback_for_browser(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle", domain="platform"),
                _make_worker("flex-a", "idle", domain=None),
            ]
        )
        assert select_worker(pool, domain="browser-game") == "flex-a"


class TestTaskPacketDomain:
    """Test domain field on TaskPacket."""

    def test_create_packet_with_domain(self) -> None:
        from bid_euchre.ops.task_queue import create_packet

        pkt = create_packet("test", "desc", domain="platform")
        assert pkt.domain == "platform"

    def test_create_packet_without_domain(self) -> None:
        from bid_euchre.ops.task_queue import create_packet

        pkt = create_packet("test", "desc")
        assert pkt.domain is None

    def test_invalid_domain_rejected(self) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        with pytest.raises(ValueError, match="Unknown domain"):
            TaskPacket(
                packet_id="x",
                title="t",
                description="d",
                owner=None,
                created_by="o",
                created_at="now",
                status="pending",
                domain="invalid",
            )

    def test_list_packets_domain_filter(self, tmp_path: Path) -> None:
        from bid_euchre.ops.task_queue import create_packet, list_packets, save_packet

        root = tmp_path / "tq"
        root.mkdir()
        (root / "archive").mkdir()

        p1 = create_packet("A", "desc", domain="platform")
        p2 = create_packet("B", "desc", domain="browser-game")
        p3 = create_packet("C", "desc")  # no domain
        save_packet(p1, root)
        save_packet(p2, root)
        save_packet(p3, root)

        plat = list_packets(root, domain_filter="platform")
        assert len(plat) == 1
        assert plat[0].domain == "platform"

        brws = list_packets(root, domain_filter="browser-game")
        assert len(brws) == 1
        assert brws[0].domain == "browser-game"

        all_pkts = list_packets(root)
        assert len(all_pkts) == 3

    def test_queue_summary_includes_domain(self, tmp_path: Path) -> None:
        from bid_euchre.ops.task_queue import (
            create_packet,
            queue_summary,
            save_packet,
        )

        root = tmp_path / "tq"
        root.mkdir()
        (root / "archive").mkdir()

        p1 = create_packet("A", "desc", domain="platform")
        save_packet(p1, root)

        summary = queue_summary(root)
        assert "by_domain" in summary
        assert summary["by_domain"]["platform"] == 1
        assert summary["packets"][0]["domain"] == "platform"


# ---------------------------------------------------------------------------
# Wake worker
# ---------------------------------------------------------------------------


class TestWakeWorker:
    """Test wake_worker() with mocked tmux."""

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=True)
    def test_already_alive(
        self,
        mock_probe: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = wake_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        assert result.error is None
        assert "already alive" in result.reason.lower()
        mock_vis.assert_called_once_with("author-a", "foreground", runtime_dir)

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}._create_tmux_window", return_value=True)
    @patch(f"{_WORKER_POOL}._resolve_worktree_path", return_value="/tmp/wt")
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=False)
    def test_create_window(
        self,
        mock_probe: MagicMock,
        mock_resolve: MagicMock,
        mock_create: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = wake_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        assert result.error is None
        mock_create.assert_called_once_with("author-a", "/tmp/wt", DEFAULT_TMUX_SESSION)

    @patch(f"{_WORKER_POOL}._resolve_worktree_path", return_value=None)
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=False)
    def test_no_worktree(
        self,
        mock_probe: MagicMock,
        mock_resolve: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = wake_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "no_worktree"

    @patch(f"{_WORKER_POOL}._create_tmux_window", return_value=False)
    @patch(f"{_WORKER_POOL}._resolve_worktree_path", return_value="/tmp/wt")
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=False)
    def test_tmux_create_fails(
        self,
        mock_probe: MagicMock,
        mock_resolve: MagicMock,
        mock_create: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = wake_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "tmux_failed"

    def test_not_managed_lane(self, runtime_dir: Path) -> None:
        result = wake_worker("orchestrator", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "not_managed"


# ---------------------------------------------------------------------------
# Park worker
# ---------------------------------------------------------------------------


class TestParkWorker:
    """Test park_worker() with mocked dependencies."""

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value=None)
    def test_park_idle_lane(
        self,
        mock_task: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = park_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        assert result.error is None
        mock_vis.assert_called_once_with("author-a", "hidden", runtime_dir)

    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value="pkt123")
    def test_park_active_lane_blocked(
        self,
        mock_task: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = park_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "has_active_task"

    def test_park_not_managed(self, runtime_dir: Path) -> None:
        result = park_worker("review", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "not_managed"


# ---------------------------------------------------------------------------
# Retire worker
# ---------------------------------------------------------------------------


class TestRetireWorker:
    """Test retire_worker() with mocked dependencies."""

    @patch(f"{_WORKER_POOL}.subprocess.run")
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=True)
    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value=None)
    @patch(f"{_DASHBOARD}.set_lane_visibility")
    def test_retire_parked_lane(
        self,
        mock_vis: MagicMock,
        mock_task: MagicMock,
        mock_probe: MagicMock,
        mock_subprocess: MagicMock,
        runtime_dir: Path,
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=0)
        result = retire_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        mock_vis.assert_called_once_with("author-a", "hidden", runtime_dir)

    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=False)
    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value=None)
    @patch(f"{_DASHBOARD}.set_lane_visibility")
    def test_retire_already_dead(
        self,
        mock_vis: MagicMock,
        mock_task: MagicMock,
        mock_probe: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = retire_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        # No subprocess calls needed when pane is already dead

    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value="pkt456")
    def test_retire_active_lane_blocked(
        self,
        mock_task: MagicMock,
        runtime_dir: Path,
    ) -> None:
        result = retire_worker("author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "has_active_task"

    def test_retire_not_managed(self, runtime_dir: Path) -> None:
        result = retire_worker("ops", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "not_managed"


# ---------------------------------------------------------------------------
# Take pool snapshot
# ---------------------------------------------------------------------------


class TestTakePoolSnapshot:
    """Test take_pool_snapshot() with mocked dependencies."""

    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value=None)
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=False)
    @patch(f"{_SUPERVISOR}.take_snapshot")
    @patch(f"{_STATUS}.aggregate_status")
    @patch(f"{_DASHBOARD}.effective_visibility")
    def test_empty_registry(
        self,
        mock_vis: MagicMock,
        mock_status: MagicMock,
        mock_sup: MagicMock,
        mock_probe: MagicMock,
        mock_task: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.status import StatusReport

        mock_status.return_value = StatusReport()
        mock_sup.return_value = MagicMock(lane_assessments=[])

        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        pool = take_pool_snapshot(runtime_dir, now=now)

        assert pool.timestamp == now.isoformat()
        assert len(pool.workers) == 0
        assert pool.available_capacity == MAX_ACTIVE_AUTHORS

    @patch(f"{_WORKER_POOL}._get_lane_task_id")
    @patch(f"{_WORKER_POOL}._probe_tmux_pane")
    @patch(f"{_SUPERVISOR}.take_snapshot")
    @patch(f"{_STATUS}.aggregate_status")
    @patch(f"{_DASHBOARD}.effective_visibility")
    def test_mixed_lanes(
        self,
        mock_vis: MagicMock,
        mock_status: MagicMock,
        mock_sup: MagicMock,
        mock_probe: MagicMock,
        mock_task: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.status import LaneStatus, StatusReport
        from bid_euchre.ops.supervisor import LaneHealthAssessment

        # Create lanes: author-a (active), author-b (idle), orchestrator (filtered out)
        lanes = [
            LaneStatus(
                lane_id="author-a",
                lane_class="author",
                worktree_path="/tmp/author-a",
                branch="main",
                lifecycle_class="persistent",
                has_active_session=True,
                state="active",
                last_progress="2026-03-22T12:00:00Z",
            ),
            LaneStatus(
                lane_id="author-b",
                lane_class="author",
                worktree_path="/tmp/author-b",
                branch="main",
                lifecycle_class="persistent",
                has_active_session=False,
                state="idle",
            ),
            LaneStatus(
                lane_id="orchestrator",
                lane_class="orchestrator",
                worktree_path="/tmp/orch",
                branch="main",
                lifecycle_class="persistent",
                has_active_session=True,
                state="active",
            ),
        ]
        mock_status.return_value = StatusReport(lanes=lanes)
        mock_sup.return_value = MagicMock(
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="author-a", health="healthy", state="active"
                ),
                LaneHealthAssessment(lane_id="author-b", health="idle", state="idle"),
            ]
        )
        mock_vis.side_effect = (
            lambda lane: "foreground" if lane.lane_id == "author-a" else "background"
        )
        mock_probe.side_effect = lambda lid, _: lid == "author-a"
        mock_task.side_effect = (
            lambda lid, rd=None: "pkt1" if lid == "author-a" else None
        )

        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        pool = take_pool_snapshot(runtime_dir, now=now)

        # Only managed lanes (author-a, author-b), not orchestrator
        assert len(pool.workers) == 2
        lane_ids = {w.lane_id for w in pool.workers}
        assert lane_ids == {"author-a", "author-b"}

        author_a = next(w for w in pool.workers if w.lane_id == "author-a")
        assert author_a.pool_status == "active"
        assert author_a.health == "healthy"
        assert author_a.tmux_alive is True
        assert author_a.current_task_id == "pkt1"

        author_b = next(w for w in pool.workers if w.lane_id == "author-b")
        assert author_b.pool_status == "idle"

        assert pool.active_count == 1
        assert pool.idle_count == 1
        assert pool.available_capacity == MAX_ACTIVE_AUTHORS - 1

    @patch(f"{_WORKER_POOL}._get_lane_task_id", return_value=None)
    @patch(f"{_WORKER_POOL}._probe_tmux_pane", return_value=False)
    @patch(f"{_SUPERVISOR}.take_snapshot")
    @patch(f"{_STATUS}.aggregate_status")
    @patch(f"{_DASHBOARD}.effective_visibility")
    def test_supervisor_failure_degrades_gracefully(
        self,
        mock_vis: MagicMock,
        mock_status: MagicMock,
        mock_sup: MagicMock,
        mock_probe: MagicMock,
        mock_task: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.status import LaneStatus, StatusReport

        lanes = [
            LaneStatus(
                lane_id="author-a",
                lane_class="author",
                worktree_path="/tmp/author-a",
                branch="main",
                lifecycle_class="persistent",
                has_active_session=False,
                state="idle",
            ),
        ]
        mock_status.return_value = StatusReport(lanes=lanes)
        mock_sup.side_effect = RuntimeError("watchdog failed")
        mock_vis.return_value = "background"

        now = datetime(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        pool = take_pool_snapshot(runtime_dir, now=now)

        assert len(pool.workers) == 1
        # Health defaults to "idle" when supervisor fails
        assert pool.workers[0].health == "idle"


# ---------------------------------------------------------------------------
# Dispatch to worker
# ---------------------------------------------------------------------------


class TestDispatchToWorker:
    """Test dispatch_to_worker() end-to-end with mocked deps."""

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_to_idle_lane(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test task",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "idle"),
            ]
        )

        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        assert result.error is None
        assert "pkt1" in result.reason

    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_packet_not_found(
        self,
        mock_load: MagicMock,
        runtime_dir: Path,
    ) -> None:
        mock_load.return_value = None
        result = dispatch_to_worker("pkt999", "author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "packet_not_found"

    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_wrong_status(
        self,
        mock_load: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="pending",
        )
        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "wrong_status"

    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_lane_not_found(
        self,
        mock_load: MagicMock,
        mock_snapshot: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        # Empty pool -- lane_id won't be found
        mock_snapshot.return_value = _make_pool([])

        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "lane_not_found"

    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_lane_busy(
        self,
        mock_load: MagicMock,
        mock_snapshot: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "active", current_task_id="pkt0"),
            ]
        )

        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        assert result.executed is False
        assert result.error == "lane_busy"

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.wake_worker")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_wakes_parked_lane(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_wake: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "parked"),
            ]
        )
        mock_wake.return_value = PoolAction(
            action="wake",
            lane_id="author-a",
            reason="woke",
            executed=True,
        )

        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        assert result.executed is True
        mock_wake.assert_called_once()

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_uses_task_queue_subdir(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Verify load_packet/save_packet/transition_status receive task_queue subdir."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test task",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "idle"),
            ]
        )

        dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)

        expected_tq = runtime_dir / "task_queue"

        # load_packet should receive task_queue subdir
        mock_load.assert_called_once_with("pkt1", expected_tq)

        # save_packet should receive task_queue subdir
        assert mock_save.call_count == 1
        actual_save_root = mock_save.call_args[0][1]
        assert actual_save_root == expected_tq

        # transition_status should receive task_queue subdir
        mock_transition.assert_called_once_with("pkt1", "dispatched", expected_tq)

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}._resolve_worktree_path")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_copies_packet_to_worktree(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_resolve_wt: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
        tmp_path: Path,
    ) -> None:
        """After dispatch, the packet JSON is copied to the worktree task_queue."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test task",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])

        # Simulate the dispatched packet file that transition_status would write
        tq_dir = runtime_dir / "task_queue"
        tq_dir.mkdir(parents=True, exist_ok=True)
        packet_file = tq_dir / "pkt1.json"
        packet_file.write_text(
            json.dumps({"packet_id": "pkt1", "status": "dispatched"})
        )

        # Set up a fake worktree directory
        worktree_dir = tmp_path / "worktree-author-a"
        worktree_dir.mkdir()
        mock_resolve_wt.return_value = str(worktree_dir)

        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        assert result.executed is True

        # Verify the packet was copied to the worktree's task_queue
        wt_packet = worktree_dir / ".claude" / "runtime" / "task_queue" / "pkt1.json"
        assert wt_packet.exists(), "Packet JSON should be copied to worktree task_queue"
        copied_data = json.loads(wt_packet.read_text())
        assert copied_data["packet_id"] == "pkt1"

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}._resolve_worktree_path")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_succeeds_when_worktree_path_unresolved(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_resolve_wt: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Dispatch still succeeds even when worktree path cannot be resolved."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test task",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])
        mock_resolve_wt.return_value = None  # worktree path not found

        result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)
        # Dispatch should still succeed — copy is best-effort
        assert result.executed is True
        assert result.error is None


# ---------------------------------------------------------------------------
# Run pool maintenance
# ---------------------------------------------------------------------------


class TestRunPoolMaintenance:
    """Test run_pool_maintenance() with mocked deps."""

    @patch(f"{_WORKER_POOL}.retire_worker")
    @patch(f"{_WORKER_POOL}.park_worker")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    def test_park_idle_worker(
        self,
        mock_snapshot: MagicMock,
        mock_park: MagicMock,
        mock_retire: MagicMock,
        runtime_dir: Path,
    ) -> None:
        now = datetime(2026, 3, 22, 12, 30, 0, tzinfo=timezone.utc)
        # Worker idle for 20 minutes (> IDLE_PARK_MINUTES)
        last_activity = "2026-03-22T12:10:00+00:00"
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "idle", last_activity=last_activity),
            ]
        )
        mock_park.return_value = PoolAction(
            action="park",
            lane_id="author-a",
            reason="parked",
            executed=True,
        )

        actions = run_pool_maintenance(runtime_dir=runtime_dir, now=now)
        assert len(actions) == 1
        assert actions[0].action == "park"
        assert actions[0].lane_id == "author-a"
        mock_park.assert_called_once()

    @patch(f"{_WORKER_POOL}.retire_worker")
    @patch(f"{_WORKER_POOL}.park_worker")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    def test_retire_parked_worker(
        self,
        mock_snapshot: MagicMock,
        mock_park: MagicMock,
        mock_retire: MagicMock,
        runtime_dir: Path,
    ) -> None:
        now = datetime(2026, 3, 22, 14, 0, 0, tzinfo=timezone.utc)
        # Worker parked for 90 minutes (> PARKED_RETIRE_MINUTES)
        last_activity = "2026-03-22T12:30:00+00:00"
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-b", "parked", last_activity=last_activity),
            ]
        )
        mock_retire.return_value = PoolAction(
            action="retire",
            lane_id="author-b",
            reason="retired",
            executed=True,
        )

        actions = run_pool_maintenance(runtime_dir=runtime_dir, now=now)
        assert len(actions) == 1
        assert actions[0].action == "retire"
        assert actions[0].lane_id == "author-b"
        mock_retire.assert_called_once()

    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    def test_dry_run_no_execution(
        self,
        mock_snapshot: MagicMock,
        runtime_dir: Path,
    ) -> None:
        now = datetime(2026, 3, 22, 12, 30, 0, tzinfo=timezone.utc)
        last_activity = "2026-03-22T12:10:00+00:00"
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "idle", last_activity=last_activity),
            ]
        )

        actions = run_pool_maintenance(runtime_dir=runtime_dir, now=now, dry_run=True)
        assert len(actions) == 1
        assert actions[0].action == "park"
        assert actions[0].executed is False  # dry_run = no execution

    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    def test_no_actions_needed(
        self,
        mock_snapshot: MagicMock,
        runtime_dir: Path,
    ) -> None:
        now = datetime(2026, 3, 22, 12, 5, 0, tzinfo=timezone.utc)
        # Only 5 minutes idle (< IDLE_PARK_MINUTES)
        last_activity = "2026-03-22T12:00:00+00:00"
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "idle", last_activity=last_activity),
            ]
        )

        actions = run_pool_maintenance(runtime_dir=runtime_dir, now=now)
        assert len(actions) == 0

    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    def test_no_last_activity_skipped(
        self,
        mock_snapshot: MagicMock,
        runtime_dir: Path,
    ) -> None:
        now = datetime(2026, 3, 22, 12, 30, 0, tzinfo=timezone.utc)
        mock_snapshot.return_value = _make_pool(
            [
                _make_worker("author-a", "idle", last_activity=None),
            ]
        )

        actions = run_pool_maintenance(runtime_dir=runtime_dir, now=now)
        assert len(actions) == 0


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    """Test text and JSON formatters."""

    def test_format_pool_text(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "active", health="healthy", tmux_alive=True),
                _make_worker("author-b", "idle", health="idle", tmux_alive=False),
            ]
        )
        text = format_pool_text(pool)
        assert "Worker Pool" in text
        assert "author-a" in text
        assert "author-b" in text
        assert "active" in text

    def test_format_pool_text_empty(self) -> None:
        pool = _make_pool([])
        text = format_pool_text(pool)
        assert "no managed workers" in text.lower()

    def test_format_pool_json(self) -> None:
        pool = _make_pool(
            [
                _make_worker("author-a", "idle"),
            ]
        )
        data = format_pool_json(pool)
        assert data["timestamp"] == pool.timestamp
        assert data["summary"]["idle"] == 1
        assert len(data["workers"]) == 1
        assert data["workers"][0]["lane_id"] == "author-a"

    def test_format_action_text_ok(self) -> None:
        action = PoolAction(
            action="park",
            lane_id="author-a",
            reason="idle too long",
            executed=True,
        )
        text = format_action_text(action)
        assert "[OK]" in text
        assert "author-a" in text

    def test_format_action_text_skipped(self) -> None:
        action = PoolAction(
            action="wake",
            lane_id="author-b",
            reason="failed",
            executed=False,
            error="tmux_failed",
        )
        text = format_action_text(action)
        assert "[SKIPPED]" in text
        assert "tmux_failed" in text

    def test_format_actions_json(self) -> None:
        actions = [
            PoolAction(action="park", lane_id="author-a", reason="r", executed=True),
        ]
        data = format_actions_json(actions)
        assert len(data) == 1
        assert data[0]["action"] == "park"
        assert data[0]["executed"] is True


# ---------------------------------------------------------------------------
# Nudge pane
# ---------------------------------------------------------------------------


class TestNudgePane:
    """Test nudge_pane() with mocked subprocess."""

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_nudge_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        result = nudge_pane("author-a", "pkt123")
        assert result.executed is True
        assert result.action == "nudge"
        assert result.error is None
        assert "/start-task pkt123" in result.reason
        assert "steward:author-a" in result.reason
        mock_run.assert_called_once_with(
            [
                "tmux",
                "send-keys",
                "-t",
                "steward:author-a",
                "/start-task pkt123",
                "Enter",
            ],
            check=True,
            capture_output=True,
            timeout=5,
        )

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_nudge_custom_session(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        result = nudge_pane("author-b", "pkt456", tmux_session="custom")
        assert result.executed is True
        mock_run.assert_called_once_with(
            [
                "tmux",
                "send-keys",
                "-t",
                "custom:author-b",
                "/start-task pkt456",
                "Enter",
            ],
            check=True,
            capture_output=True,
            timeout=5,
        )

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_nudge_subprocess_error(self, mock_run: MagicMock) -> None:
        import subprocess as sp

        mock_run.side_effect = sp.CalledProcessError(1, "tmux")
        result = nudge_pane("author-a", "pkt123")
        assert result.executed is False
        assert result.error == "nudge_failed"
        assert result.action == "nudge"

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_nudge_timeout(self, mock_run: MagicMock) -> None:
        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired("tmux", 5)
        result = nudge_pane("author-a", "pkt123")
        assert result.executed is False
        assert result.error == "nudge_failed"

    @patch(f"{_WORKER_POOL}.subprocess.run")
    def test_nudge_tmux_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("tmux not found")
        result = nudge_pane("author-a", "pkt123")
        assert result.executed is False
        assert result.error == "nudge_failed"

    def test_nudge_uses_registry_target(self, tmp_path: Path) -> None:
        """When registry has window.pane, nudge targets that (1-based)."""
        registry_dir = tmp_path / "worktree_registry"
        registry_dir.mkdir()
        entry = {"tmux_window": "platform", "tmux_pane": "1"}
        (registry_dir / "author-a.json").write_text(json.dumps(entry))
        with patch(f"{_WORKER_POOL}.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = nudge_pane("author-a", "pkt789", runtime_dir=tmp_path)
            assert result.executed is True
            assert "steward:platform.1" in result.reason
            call_args = mock_run.call_args[0][0]
            assert call_args[3] == "steward:platform.1"


# ---------------------------------------------------------------------------
# Dispatch with nudge and inbox message
# ---------------------------------------------------------------------------


class TestDispatchNudgeIntegration:
    """Test that dispatch_to_worker() calls nudge_pane and writes inbox message."""

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.nudge_pane")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_calls_nudge(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_nudge: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Dispatch should call nudge_pane after transitioning the packet."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test Task",
            description="Do the thing",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])
        mock_nudge.return_value = PoolAction(
            action="nudge",
            lane_id="author-a",
            reason="nudged",
            executed=True,
        )

        with patch("bid_euchre.ops.message_bus.send_message", return_value="msg123"):
            with patch("bid_euchre.ops.message_bus.create_message") as mock_cm:
                mock_cm.return_value = MagicMock(message_id="msg123")
                result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)

        assert result.executed is True
        mock_nudge.assert_called_once_with(
            "author-a", "pkt1", tmux_session=DEFAULT_TMUX_SESSION
        )

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.nudge_pane")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_writes_inbox_message(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_nudge: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Dispatch should write an inbox message via message_bus."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test Task",
            description="Do the thing",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])
        mock_nudge.return_value = PoolAction(
            action="nudge",
            lane_id="author-a",
            reason="nudged",
            executed=True,
        )

        with patch(
            "bid_euchre.ops.message_bus.send_message", return_value="msg123"
        ) as mock_send:
            with patch("bid_euchre.ops.message_bus.create_message") as mock_cm:
                from bid_euchre.ops.message_bus import BusMessage

                fake_msg = BusMessage(
                    message_id="msg123",
                    thread_id=None,
                    task_id="pkt1",
                    from_lane="orchestrator",
                    to_lane="author-a",
                    message_type="assignment",
                    priority="normal",
                    status="pending",
                    created_at="2026-03-22T12:00:00Z",
                    acked_at=None,
                    resolved_at=None,
                    requires_human=False,
                    summary="Task dispatched: Test Task",
                    payload={"packet_id": "pkt1", "title": "Test Task"},
                )
                mock_cm.return_value = fake_msg
                result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)

        assert result.executed is True
        mock_cm.assert_called_once()
        mock_send.assert_called_once_with(fake_msg)

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.nudge_pane")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_succeeds_even_if_nudge_fails(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_nudge: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Dispatch should succeed even if nudge fails (nudge is best-effort)."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])
        mock_nudge.return_value = PoolAction(
            action="nudge",
            lane_id="author-a",
            reason="tmux failed",
            executed=False,
            error="nudge_failed",
        )

        with patch("bid_euchre.ops.message_bus.send_message", return_value="msg123"):
            with patch("bid_euchre.ops.message_bus.create_message") as mock_cm:
                mock_cm.return_value = MagicMock(message_id="msg123")
                result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)

        # Dispatch itself still succeeds — nudge is best-effort
        assert result.executed is True
        assert result.error is None

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.nudge_pane")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_succeeds_even_if_inbox_fails(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_nudge: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """Dispatch should succeed even if inbox message fails (best-effort)."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])
        mock_nudge.return_value = PoolAction(
            action="nudge",
            lane_id="author-a",
            reason="nudged",
            executed=True,
        )

        with patch(
            "bid_euchre.ops.message_bus.send_message",
            side_effect=RuntimeError("bus down"),
        ):
            with patch("bid_euchre.ops.message_bus.create_message") as mock_cm:
                mock_cm.return_value = MagicMock(message_id="msg123")
                result = dispatch_to_worker("pkt1", "author-a", runtime_dir=runtime_dir)

        # Dispatch itself still succeeds
        assert result.executed is True
        assert result.error is None

    @patch(f"{_DASHBOARD}.set_lane_visibility")
    @patch(f"{_WORKER_POOL}.nudge_pane")
    @patch(f"{_WORKER_POOL}.take_pool_snapshot")
    @patch(f"{_TASK_QUEUE}.transition_status")
    @patch(f"{_TASK_QUEUE}.save_packet")
    @patch(f"{_TASK_QUEUE}.load_packet")
    def test_dispatch_records_delivery_on_nudge_success(
        self,
        mock_load: MagicMock,
        mock_save: MagicMock,
        mock_transition: MagicMock,
        mock_snapshot: MagicMock,
        mock_nudge: MagicMock,
        mock_vis: MagicMock,
        runtime_dir: Path,
    ) -> None:
        """On nudge success, dispatch should update inbox message to delivered."""
        from bid_euchre.ops.task_queue import TaskPacket

        mock_load.return_value = TaskPacket(
            packet_id="pkt1",
            title="Test",
            description="Test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-22T12:00:00Z",
            status="approved",
        )
        mock_snapshot.return_value = _make_pool([_make_worker("author-a", "idle")])
        mock_nudge.return_value = PoolAction(
            action="nudge",
            lane_id="author-a",
            reason="nudged",
            executed=True,
        )

        with patch("bid_euchre.ops.message_bus.send_message", return_value="msg123"):
            with patch("bid_euchre.ops.message_bus.create_message") as mock_cm:
                mock_cm.return_value = MagicMock(message_id="msg123")
                with patch(
                    "bid_euchre.ops.message_bus._update_inbox_status"
                ) as mock_update:
                    with patch(
                        "bid_euchre.ops.message_bus.shared_bus_root"
                    ) as mock_root:
                        mock_root.return_value = Path("/tmp/bus")
                        result = dispatch_to_worker(
                            "pkt1", "author-a", runtime_dir=runtime_dir
                        )

        assert result.executed is True
        mock_update.assert_called_once_with(
            "msg123", "author-a", "delivered", Path("/tmp/bus")
        )
