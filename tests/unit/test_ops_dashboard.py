"""Tests for dashboard-first supervision surface (ops/dashboard.py)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.dashboard import (
    AttentionItem,
    DashboardSection,
    DashboardView,
    InboxHighlight,
    _derive_attention_items,
    build_dashboard_view,
    default_visibility,
    effective_visibility,
    format_dashboard_json,
    format_dashboard_text,
    set_lane_visibility,
)
from bid_euchre.ops.status import LaneStatus, StatusReport

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
    return rd


def _write_json(directory: Path, filename: str, data: dict) -> None:
    (directory / filename).write_text(json.dumps(data, indent=2))


def _derive_test_lane_class(lane_id: str) -> str:
    """Mirror ``worktrees.derive_lane_class`` logic for test helpers."""
    if lane_id == "ops":
        return "ops"
    if lane_id == "review":
        return "review"
    if lane_id.startswith("analyst"):
        return "analyst"
    if lane_id.endswith("-scratch"):
        return "scratch"
    if lane_id.startswith("author") or lane_id.startswith("flex"):
        return "author"
    return lane_id


def _make_lane(
    lane_id: str,
    *,
    state: str = "idle",
    attention_needed: bool = False,
    attention_reason: str | None = None,
    visibility: str | None = None,
    current_task_title: str | None = None,
    linked_pr: int | None = None,
    branch: str = "main",
    has_active_session: bool = False,
    session_task: str | None = None,
    last_progress: str | None = None,
    liveness_source: str | None = None,
    current_step: str | None = None,
) -> LaneStatus:
    """Create a LaneStatus for testing."""
    return LaneStatus(
        lane_id=lane_id,
        lane_class=_derive_test_lane_class(lane_id),
        worktree_path=f"/tmp/{lane_id}",
        branch=branch,
        lifecycle_class="persistent",
        has_active_session=has_active_session,
        session_task=session_task,
        state=state,
        visibility=visibility,
        attention_needed=attention_needed,
        attention_reason=attention_reason,
        current_task_title=current_task_title,
        linked_pr=linked_pr,
        last_progress=last_progress,
        liveness_source=liveness_source,
        current_step=current_step,
    )


# ---------------------------------------------------------------------------
# Tests: default_visibility
# ---------------------------------------------------------------------------


class TestDefaultVisibility:
    """Tests for default_visibility()."""

    def test_foreground_lanes(self) -> None:
        assert default_visibility("dashboard") == "foreground"
        assert default_visibility("orchestrator") == "foreground"
        assert default_visibility("ops") == "foreground"
        assert default_visibility("review") == "foreground"
        assert default_visibility("issues") == "foreground"

    def test_author_lanes_default_background(self) -> None:
        assert default_visibility("author-a") == "background"
        assert default_visibility("author-b") == "background"
        assert default_visibility("author-scratch") == "background"

    def test_unknown_lane_default_background(self) -> None:
        assert default_visibility("custom-lane") == "background"


# ---------------------------------------------------------------------------
# Tests: effective_visibility
# ---------------------------------------------------------------------------


class TestEffectiveVisibility:
    """Tests for effective_visibility()."""

    def test_explicit_overrides_default(self) -> None:
        lane = _make_lane("author-a", visibility="foreground")
        assert effective_visibility(lane) == "foreground"

    def test_explicit_hidden(self) -> None:
        lane = _make_lane("ops", visibility="hidden")
        assert effective_visibility(lane) == "hidden"

    def test_none_falls_back_to_default(self) -> None:
        lane = _make_lane("ops", visibility=None)
        assert effective_visibility(lane) == "foreground"

    def test_none_author_falls_back_to_background(self) -> None:
        lane = _make_lane("author-a", visibility=None)
        assert effective_visibility(lane) == "background"

    def test_invalid_visibility_falls_back(self) -> None:
        lane = _make_lane("ops", visibility="invalid_value")
        assert effective_visibility(lane) == "foreground"


# ---------------------------------------------------------------------------
# Tests: set_lane_visibility
# ---------------------------------------------------------------------------


class TestSetLaneVisibility:
    """Tests for set_lane_visibility()."""

    def test_set_visibility_updates_entry(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {"lane_id": "ops", "worktree_path": "/tmp/ops", "branch": "main"},
        )
        result = set_lane_visibility("ops", "hidden", runtime_dir)
        assert result is True

        # Verify the file was updated
        data = json.loads((runtime_dir / "worktree_registry" / "ops.json").read_text())
        assert data["visibility"] == "hidden"

    def test_set_visibility_lane_not_found(self, runtime_dir: Path) -> None:
        result = set_lane_visibility("nonexistent", "foreground", runtime_dir)
        assert result is False

    def test_set_visibility_invalid_value(self, runtime_dir: Path) -> None:
        with pytest.raises(ValueError, match="Invalid visibility"):
            set_lane_visibility("ops", "invalid", runtime_dir)

    def test_set_visibility_no_registry_dir(self, tmp_path: Path) -> None:
        rd = tmp_path / "empty_runtime"
        rd.mkdir()
        result = set_lane_visibility("ops", "foreground", rd)
        assert result is False


# ---------------------------------------------------------------------------
# Tests: _derive_attention_items
# ---------------------------------------------------------------------------


class TestDeriveAttentionItems:
    """Tests for _derive_attention_items()."""

    def test_empty_report(self) -> None:
        report = StatusReport()
        items = _derive_attention_items(report)
        assert items == []

    def test_blocked_lane_is_high(self) -> None:
        report = StatusReport(
            lanes=[
                _make_lane(
                    "author-a",
                    state="blocked",
                    attention_needed=True,
                    attention_reason="blocked: CI failing",
                ),
            ]
        )
        items = _derive_attention_items(report)
        assert len(items) == 1
        assert items[0].severity == "high"
        assert items[0].lane_id == "author-a"

    def test_stale_lane_is_low(self) -> None:
        """Individual stale lanes are low severity, not medium (#1775)."""
        report = StatusReport(
            lanes=[
                _make_lane(
                    "author-b",
                    state="stale",
                    attention_needed=True,
                    attention_reason="stale heartbeat",
                ),
            ]
        )
        items = _derive_attention_items(report)
        # Individual stale → low; fleet-wide all-stale → high
        low_items = [i for i in items if i.severity == "low"]
        assert len(low_items) == 1
        assert low_items[0].lane_id == "author-b"

    def test_idle_lane_is_low(self) -> None:
        report = StatusReport(
            lanes=[
                _make_lane(
                    "ops",
                    state="idle",
                    attention_needed=True,
                    attention_reason="persistent lane idle",
                ),
            ]
        )
        items = _derive_attention_items(report)
        assert len(items) == 1
        assert items[0].severity == "low"

    def test_severity_ordering(self) -> None:
        """Blocked → high; stale/idle → low.  Fleet alert also high (#1775)."""
        report = StatusReport(
            lanes=[
                _make_lane(
                    "review",
                    state="idle",
                    attention_needed=True,
                    attention_reason="idle lane",
                ),
                _make_lane(
                    "author-a",
                    state="blocked",
                    attention_needed=True,
                    attention_reason="blocked",
                ),
                _make_lane(
                    "author-b",
                    state="stale",
                    attention_needed=True,
                    attention_reason="stale",
                ),
            ]
        )
        items = _derive_attention_items(report)
        # blocked author-a → high, stale author-b → low, idle review → low
        # Plus: author-a is blocked (not idle/stale) so not all worker lanes
        # are idle — no fleet alert.
        high_items = [i for i in items if i.severity == "high"]
        low_items = [i for i in items if i.severity == "low"]
        assert len(high_items) == 1
        assert high_items[0].lane_id == "author-a"
        assert len(low_items) == 2
        # High items come first in sort order
        assert items[0].severity == "high"

    def test_no_attention_lanes_skipped(self) -> None:
        report = StatusReport(
            lanes=[
                _make_lane("ops", state="active", attention_needed=False),
                _make_lane("author-a", state="active", attention_needed=False),
            ]
        )
        items = _derive_attention_items(report)
        assert items == []

    def test_all_worker_lanes_idle_triggers_fleet_alert(self) -> None:
        """HIGH fleet alert when ALL author/analyst lanes are idle/stale (#1775)."""
        report = StatusReport(
            lanes=[
                _make_lane(
                    "author-a",
                    state="stale",
                    attention_needed=True,
                    attention_reason="stale heartbeat",
                ),
                _make_lane(
                    "author-b",
                    state="idle",
                    attention_needed=True,
                    attention_reason="persistent lane idle",
                ),
            ]
        )
        items = _derive_attention_items(report)
        fleet_items = [i for i in items if i.lane_id == "fleet"]
        assert len(fleet_items) == 1
        assert fleet_items[0].severity == "high"
        assert "worker lanes" in fleet_items[0].reason

    def test_some_active_worker_lanes_no_fleet_alert(self) -> None:
        """No fleet alert when some worker lanes are active (#1775)."""
        report = StatusReport(
            lanes=[
                _make_lane(
                    "author-a",
                    state="active",
                    attention_needed=False,
                ),
                _make_lane(
                    "author-b",
                    state="stale",
                    attention_needed=True,
                    attention_reason="stale heartbeat",
                ),
            ]
        )
        items = _derive_attention_items(report)
        fleet_items = [i for i in items if i.lane_id == "fleet"]
        assert len(fleet_items) == 0

    def test_control_plane_excluded_from_fleet_check(self) -> None:
        """Control-plane lanes (ops, review) don't count for fleet alert (#1775)."""
        report = StatusReport(
            lanes=[
                # Control-plane lanes — idle, but shouldn't trigger fleet alert
                _make_lane(
                    "ops",
                    state="idle",
                    attention_needed=True,
                    attention_reason="persistent lane idle",
                ),
                _make_lane(
                    "review",
                    state="idle",
                    attention_needed=True,
                    attention_reason="persistent lane idle",
                ),
            ]
        )
        items = _derive_attention_items(report)
        fleet_items = [i for i in items if i.lane_id == "fleet"]
        # ops (lane_class="ops") and review (lane_class="review") are not
        # worker-class lanes, so no fleet alert should fire.
        assert len(fleet_items) == 0

    def test_analyst_lanes_included_in_fleet_check(self) -> None:
        """Analyst lanes are worker-class and count for fleet alert (#1775)."""
        report = StatusReport(
            lanes=[
                _make_lane(
                    "analyst-a",
                    state="stale",
                    attention_needed=True,
                    attention_reason="stale heartbeat",
                ),
            ]
        )
        items = _derive_attention_items(report)
        fleet_items = [i for i in items if i.lane_id == "fleet"]
        assert len(fleet_items) == 1
        assert fleet_items[0].severity == "high"

    def test_no_worker_lanes_no_fleet_alert(self) -> None:
        """No fleet alert when there are no worker lanes at all (#1775)."""
        report = StatusReport(
            lanes=[
                _make_lane(
                    "ops",
                    state="idle",
                    attention_needed=True,
                    attention_reason="persistent lane idle",
                ),
            ]
        )
        items = _derive_attention_items(report)
        fleet_items = [i for i in items if i.lane_id == "fleet"]
        assert len(fleet_items) == 0


# ---------------------------------------------------------------------------
# Tests: build_dashboard_view
# ---------------------------------------------------------------------------


class TestBuildDashboardView:
    """Tests for build_dashboard_view()."""

    def test_empty_state(self, runtime_dir: Path) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)
        assert isinstance(view, DashboardView)
        assert view.foreground.lanes == []
        assert view.background.lanes == []
        assert view.attention_items == []
        assert view.active_task_count == 0
        assert view.blocked_task_count == 0

    def test_lanes_grouped_by_visibility(self, runtime_dir: Path) -> None:
        # Create registry entries for ops (foreground) and author-a (background)
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {
                "lane_id": "ops",
                "lane_class": "ops",
                "worktree_path": "/tmp/ops",
                "branch": "main",
                "class": "persistent",
            },
        )
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/author-a",
                "branch": "feat/something",
                "class": "persistent",
            },
        )

        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)

        fg_ids = [lane.lane_id for lane in view.foreground.lanes]
        bg_ids = [lane.lane_id for lane in view.background.lanes]

        assert "ops" in fg_ids
        assert "author-a" in bg_ids
        assert "author-a" not in fg_ids

    def test_hidden_lanes_excluded(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {
                "lane_id": "ops",
                "lane_class": "ops",
                "worktree_path": "/tmp/ops",
                "branch": "main",
                "class": "persistent",
                "visibility": "hidden",
            },
        )

        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)

        all_ids = [lane.lane_id for lane in view.foreground.lanes] + [
            lane.lane_id for lane in view.background.lanes
        ]
        assert "ops" not in all_ids

    def test_explicit_foreground_override(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/author-a",
                "branch": "main",
                "class": "persistent",
                "visibility": "foreground",
            },
        )

        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)

        fg_ids = [lane.lane_id for lane in view.foreground.lanes]
        assert "author-a" in fg_ids


# ---------------------------------------------------------------------------
# Tests: format_dashboard_text
# ---------------------------------------------------------------------------


class TestFormatDashboardText:
    """Tests for format_dashboard_text()."""

    def test_empty_view(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
        )
        text = format_dashboard_text(view, now=now)
        assert "=== Steward Dashboard ===" in text
        assert "Foreground Lanes (0)" in text
        assert "Background Lanes (0 total" in text
        assert "(none)" in text

    def test_lanes_rendered(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(
                title="Foreground Lanes",
                lanes=[
                    _make_lane(
                        "ops",
                        state="active",
                        has_active_session=True,
                        session_task="monitoring",
                        branch="main",
                    ),
                ],
            ),
            background=DashboardSection(
                title="Background Lanes",
                lanes=[
                    _make_lane("author-a", state="idle", branch="feat/foo"),
                ],
            ),
        )
        text = format_dashboard_text(view, now=now)
        assert "Foreground Lanes (1)" in text
        assert "ops" in text
        assert "monitoring" in text
        assert "Background Lanes (1 total" in text
        assert "author-a" in text

    def test_attention_items_rendered(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
            attention_items=[
                AttentionItem(
                    lane_id="author-a",
                    severity="high",
                    reason="blocked: CI failing",
                    suggested_action="inspect CI output",
                ),
            ],
        )
        text = format_dashboard_text(view, now=now)
        assert "Attention (1)" in text
        assert "[high] author-a: blocked: CI failing" in text
        assert "-> inspect CI output" in text

    def test_inbox_highlights_rendered(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
            inbox_highlights=[
                InboxHighlight(
                    lane_id="orchestrator",
                    unacked_count=3,
                    oldest_unacked_age="15m ago",
                ),
            ],
        )
        text = format_dashboard_text(view, now=now)
        assert "Inbox (3 unacked)" in text
        assert "orchestrator: 3 unacked messages" in text
        assert "(oldest: 15m ago)" in text

    def test_single_unacked_message_grammar(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
            inbox_highlights=[
                InboxHighlight(lane_id="ops", unacked_count=1, oldest_unacked_age=None),
            ],
        )
        text = format_dashboard_text(view, now=now)
        assert "1 unacked message" in text
        # Should NOT say "messages" for count=1
        lines = text.split("\n")
        inbox_line = [l for l in lines if "ops:" in l and "unacked" in l][0]
        assert "messages" not in inbox_line

    def test_task_queue_rendered(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
            task_queue_summary={
                "total": 2,
                "packets": [
                    {"status": "dispatched", "title": "Fix bug", "owner": "author-a"},
                    {"status": "pending", "title": "Write docs", "owner": None},
                ],
            },
            active_task_count=3,
            blocked_task_count=1,
        )
        text = format_dashboard_text(view, now=now)
        assert "Tasks: 3 active, 1 blocked" in text
        assert "Task Queue: 2 packets" in text

    def test_token_economy_zero_tokens_per_commit(self) -> None:
        """Zero tokens_per_commit should render as '0 tok/commit', not '—'."""
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
            token_economy={
                "overview": {
                    "total_tokens": 100_000,
                    "session_count": 5,
                    "total_git_commits": 3,
                    "tokens_per_hour": 5000,
                    "output_input_ratio": 2.1,
                    "net_lines": 42,
                },
                "top_lanes": [
                    {
                        "lane_id": "author-a",
                        "total_tokens": 50_000,
                        "tokens_per_commit": 0.0,
                    },
                    {
                        "lane_id": "author-b",
                        "total_tokens": 30_000,
                        "tokens_per_commit": 15_000.0,
                    },
                    {
                        "lane_id": "author-c",
                        "total_tokens": 20_000,
                        "tokens_per_commit": None,
                    },
                ],
            },
        )
        text = format_dashboard_text(view, now=now)
        # Zero should show as "0 tok/commit", not "—"
        assert "0 tok/commit" in text
        # None should show as "—"
        lines = text.split("\n")
        author_c_line = [l for l in lines if "author-c" in l][0]
        assert "—" in author_c_line
        # Non-zero should show the value
        assert "15,000 tok/commit" in text


class TestTokenEconomyStoreStatusRendering:
    """Dashboard header rendering for token-economy store staleness.

    Regression guards for Slice A of the token-economy restart plan:
    - Fresh / missing status → plain "Token Economy" header (no marker).
    - Stale store → "[STALE: <age>]" marker.
    - Missing attributions → "attributions missing" suffix in marker.
    - Empty store (``token_economy == {}``) → section hidden entirely.
    """

    def _make_view(self, *, token_economy: dict | None = None) -> DashboardView:
        now = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)
        return DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="Foreground Lanes", lanes=[]),
            background=DashboardSection(title="Background Lanes", lanes=[]),
            token_economy=token_economy or {},
        )

    def _overview_stub(self) -> dict:
        return {
            "overview": {
                "total_tokens": 100_000,
                "session_count": 5,
                "total_git_commits": 3,
                "tokens_per_hour": 5000,
                "output_input_ratio": 2.1,
                "net_lines": 42,
            },
            "top_lanes": [],
        }

    def test_fresh_store_renders_plain_header(self) -> None:
        te = self._overview_stub()
        te["store_status"] = {
            "exists": True,
            "empty": False,
            "stale": False,
            "usage_file_mtime": "2026-04-20T11:50:00+00:00",
            "age_seconds": 600.0,
            "stale_threshold_seconds": 3600,
            "session_count": 5,
            "attributions_present": True,
            "last_import_timestamp": "2026-04-20T11:50:00+00:00",
            "store_path": "/tmp/store",
        }
        view = self._make_view(token_economy=te)
        text = format_dashboard_text(view)
        # Plain header, no STALE marker
        assert "Token Economy" in text
        assert "STALE" not in text
        assert "attributions missing" not in text

    def test_missing_store_status_renders_plain_header(self) -> None:
        """Back-compat: token_economy without store_status key renders unmarked."""
        te = self._overview_stub()
        # No "store_status" key at all
        view = self._make_view(token_economy=te)
        text = format_dashboard_text(view)
        assert "Token Economy" in text
        assert "STALE" not in text

    def test_stale_store_renders_stale_marker(self) -> None:
        te = self._overview_stub()
        # 7200 seconds = 2h → marker should contain "2h"
        te["store_status"] = {
            "exists": True,
            "empty": False,
            "stale": True,
            "usage_file_mtime": "2026-04-20T10:00:00+00:00",
            "age_seconds": 7200.0,
            "stale_threshold_seconds": 3600,
            "session_count": 5,
            "attributions_present": True,
            "last_import_timestamp": "2026-04-20T10:00:00+00:00",
            "store_path": "/tmp/store",
        }
        view = self._make_view(token_economy=te)
        text = format_dashboard_text(view)
        assert "Token Economy [STALE:" in text
        # 2h window should surface
        assert "2h" in text.split("Token Economy [STALE:")[1].split("]")[0]
        # attributions_present=True → no attributions suffix
        assert "attributions missing" not in text

    def test_stale_store_missing_attributions_adds_suffix(self) -> None:
        te = self._overview_stub()
        te["store_status"] = {
            "exists": True,
            "empty": False,
            "stale": True,
            "usage_file_mtime": "2026-04-20T09:00:00+00:00",
            "age_seconds": 10800.0,
            "stale_threshold_seconds": 3600,
            "session_count": 5,
            "attributions_present": False,
            "last_import_timestamp": None,
            "store_path": "/tmp/store",
        }
        view = self._make_view(token_economy=te)
        text = format_dashboard_text(view)
        assert "Token Economy [STALE:" in text
        assert "attributions missing" in text

    def test_empty_store_hides_section(self) -> None:
        """Empty token_economy dict hides the whole section — contract preservation."""
        view = self._make_view(token_economy={})
        text = format_dashboard_text(view)
        # No Token Economy header at all
        assert "Token Economy" not in text


# ---------------------------------------------------------------------------
# Tests: format_dashboard_json
# ---------------------------------------------------------------------------


class TestFormatDashboardJson:
    """Tests for format_dashboard_json()."""

    def test_json_structure(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(
                title="Foreground Lanes",
                lanes=[_make_lane("ops", state="active")],
            ),
            background=DashboardSection(
                title="Background Lanes",
                lanes=[_make_lane("author-a", state="idle")],
            ),
            attention_items=[
                AttentionItem(
                    lane_id="author-a",
                    severity="low",
                    reason="idle",
                ),
            ],
            inbox_highlights=[
                InboxHighlight(
                    lane_id="ops",
                    unacked_count=2,
                ),
            ],
            active_task_count=5,
            blocked_task_count=0,
            warning_count=1,
        )
        result = format_dashboard_json(view)

        # Check top-level keys
        assert "generated_at" in result
        assert "summary" in result
        assert "foreground" in result
        assert "background" in result
        assert "attention_items" in result
        assert "inbox_highlights" in result

        # Check summary
        summary = result["summary"]
        assert summary["foreground_lanes"] == 1
        assert summary["background_lanes"] == 1
        assert summary["attention_items"] == 1
        assert summary["inbox_unacked"] == 2
        assert summary["active_tasks"] == 5
        assert summary["blocked_tasks"] == 0
        assert summary["warnings"] == 1

        # Check lane data
        assert len(result["foreground"]["lanes"]) == 1
        assert result["foreground"]["lanes"][0]["lane_id"] == "ops"
        assert len(result["background"]["lanes"]) == 1
        assert result["background"]["lanes"][0]["lane_id"] == "author-a"

    def test_json_serializable(self) -> None:
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = DashboardView(
            generated_at=now.isoformat(),
            foreground=DashboardSection(title="FG", lanes=[]),
            background=DashboardSection(title="BG", lanes=[]),
        )
        result = format_dashboard_json(view)
        # Should not raise
        serialized = json.dumps(result, indent=2)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["generated_at"] == now.isoformat()


# ---------------------------------------------------------------------------
# Tests: integration (build + format round-trip)
# ---------------------------------------------------------------------------


class TestDashboardIntegration:
    """Integration tests: build_dashboard_view -> format round-trip."""

    def test_build_and_format_text(self, runtime_dir: Path) -> None:
        """Build from empty state and verify text format doesn't crash."""
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)
        text = format_dashboard_text(view, now=now)
        assert "=== Steward Dashboard ===" in text
        assert "Tasks:" in text

    def test_build_and_format_json(self, runtime_dir: Path) -> None:
        """Build from empty state and verify JSON format is serializable."""
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)
        result = format_dashboard_json(view)
        serialized = json.dumps(result, indent=2)
        parsed = json.loads(serialized)
        assert "summary" in parsed
        assert "foreground" in parsed
        assert "background" in parsed

    def test_with_populated_lanes(self, runtime_dir: Path) -> None:
        """Build with registry entries and verify grouping."""
        _write_json(
            runtime_dir / "worktree_registry",
            "review.json",
            {
                "lane_id": "review",
                "lane_class": "review",
                "worktree_path": "/tmp/review",
                "branch": "main",
                "class": "persistent",
            },
        )
        _write_json(
            runtime_dir / "worktree_registry",
            "author-c.json",
            {
                "lane_id": "author-c",
                "lane_class": "author",
                "worktree_path": "/tmp/author-c",
                "branch": "fix/something",
                "class": "persistent",
            },
        )

        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)

        fg_ids = {lane.lane_id for lane in view.foreground.lanes}
        bg_ids = {lane.lane_id for lane in view.background.lanes}

        assert "review" in fg_ids
        assert "author-c" in bg_ids

        # Format both ways without error
        text = format_dashboard_text(view, now=now)
        assert "review" in text
        assert "author-c" in text

        result = format_dashboard_json(view)
        assert result["summary"]["foreground_lanes"] == 1
        assert result["summary"]["background_lanes"] == 1

    def test_set_visibility_round_trip(self, runtime_dir: Path) -> None:
        """Set visibility then verify dashboard respects it."""
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/author-a",
                "branch": "main",
                "class": "persistent",
            },
        )

        # Default: author-a is background
        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, now=now)
        bg_ids = {lane.lane_id for lane in view.background.lanes}
        assert "author-a" in bg_ids

        # Override to foreground
        set_lane_visibility("author-a", "foreground", runtime_dir)
        view = build_dashboard_view(runtime_dir, now=now)
        fg_ids = {lane.lane_id for lane in view.foreground.lanes}
        assert "author-a" in fg_ids

        # Override to hidden
        set_lane_visibility("author-a", "hidden", runtime_dir)
        view = build_dashboard_view(runtime_dir, now=now)
        all_ids = {lane.lane_id for lane in view.foreground.lanes} | {
            lane.lane_id for lane in view.background.lanes
        }
        assert "author-a" not in all_ids

    def test_inbox_highlights_with_messages(self, runtime_dir: Path) -> None:
        """Send messages via bus, build dashboard, verify highlights."""
        from bid_euchre.ops.message_bus import create_message, send_message

        # Set up a bus root inside the runtime_dir so it's isolated
        bus_root = runtime_dir / "message_bus"
        bus_root.mkdir(parents=True, exist_ok=True)
        (bus_root / "inbox").mkdir(exist_ok=True)

        # Send two pending messages to orchestrator
        for i in range(2):
            msg = create_message(
                from_lane="author-a",
                to_lane="orchestrator",
                message_type="completion",
                summary=f"Task {i} done",
            )
            send_message(msg, bus_root, events_dir=runtime_dir / "events")

        # Send one message to ops
        msg = create_message(
            from_lane="author-b",
            to_lane="ops",
            message_type="blocker",
            summary="CI failing",
        )
        send_message(msg, bus_root, events_dir=runtime_dir / "events")

        now = datetime(2026, 3, 21, 12, 0, 0, tzinfo=timezone.utc)
        view = build_dashboard_view(runtime_dir, bus_root=bus_root, now=now)

        # Should have inbox highlights for orchestrator (2) and ops (1)
        highlight_map = {h.lane_id: h.unacked_count for h in view.inbox_highlights}
        assert "orchestrator" in highlight_map
        assert highlight_map["orchestrator"] == 2
        assert "ops" in highlight_map
        assert highlight_map["ops"] == 1

        # Text output should mention inbox
        text = format_dashboard_text(view, now=now)
        assert "Inbox" in text
        assert "unacked" in text


# ---------------------------------------------------------------------------
# Tests: --watch flag CLI integration
# ---------------------------------------------------------------------------


class TestDashboardWatchFlag:
    """Tests for the --watch / --interval CLI flags on cmd_dashboard."""

    def test_watch_args_parsed(self) -> None:
        """--watch and --interval are accepted by the argument parser."""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", "scripts/internal/ops.py", "dashboard", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--watch" in result.stdout
        assert "--interval" in result.stdout

    def test_single_shot_runs_via_cli(self, tmp_path: Path) -> None:
        """Without --watch, dashboard prints once and exits with rc=0."""
        import subprocess

        runtime_dir = tmp_path / "runtime"
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "--runtime-dir",
                str(runtime_dir),
                "dashboard",
                "--no-probe",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Steward Dashboard" in result.stdout

    def test_watch_flag_accepted(self, tmp_path: Path) -> None:
        """--watch -w and --interval are accepted without error.

        We start watch mode with a short interval and send SIGINT after
        one iteration to verify the loop starts and exits cleanly.
        """
        import signal
        import subprocess
        import time as time_mod

        proc = subprocess.Popen(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "--runtime-dir",
                str(tmp_path / "runtime"),
                "dashboard",
                "--no-probe",
                "--watch",
                "--interval",
                "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Give it time to print one iteration
        time_mod.sleep(2)
        proc.send_signal(signal.SIGINT)
        stdout, _ = proc.communicate(timeout=5)
        output = stdout.decode()
        assert "Steward Dashboard" in output
        assert "Refreshing every 1s" in output

    def test_single_shot_json_is_valid(self, tmp_path: Path) -> None:
        """Single-shot --json emits indented, parseable JSON."""
        import subprocess

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "--json",
                "--runtime-dir",
                str(tmp_path / "runtime"),
                "dashboard",
                "--no-probe",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "summary" in data
        # Indented output contains newlines
        assert "\n" in result.stdout

    def test_watch_json_emits_ndjson(self, tmp_path: Path) -> None:
        """--watch --json emits compact NDJSON (no ANSI escapes, no footer)."""
        import signal
        import subprocess
        import time as time_mod

        runtime_dir = tmp_path / "runtime"
        proc = subprocess.Popen(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "dashboard",
                "--no-probe",
                "--watch",
                "--interval",
                "1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Give it time to emit at least one line
        time_mod.sleep(2)
        proc.send_signal(signal.SIGINT)
        stdout, stderr = proc.communicate(timeout=5)
        output = stdout.decode()
        # Should NOT contain ANSI escape sequences
        assert "\033[2J" not in output
        # Should NOT contain text-mode footer
        assert "Refreshing every" not in output
        # Each non-empty line should be valid JSON
        lines = [ln for ln in output.strip().split("\n") if ln.strip()]
        assert len(lines) >= 1
        for line in lines:
            data = json.loads(line)
            assert "summary" in data
        # "Watch stopped." should go to stderr, not stdout
        assert "Watch stopped." not in output
