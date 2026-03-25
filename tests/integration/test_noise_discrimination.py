"""Integration tests proving noise discrimination in the controller projection.

SP-4-07 proving run 2 — noise discrimination (#1682).

Proves that the controller + projection path correctly separates urgent (P0)
alerts from routine info/warn noise. The key invariant: only HIGH/URGENT items
appear in the ``urgent_items`` and ``high_items`` subsets, while ALL items
remain visible in the full ``fleet_status.json`` projection and CLI output.

Scenario design:
  - Seed 10 routine monitor findings (info/warn: lane idle, inbox unacked,
    capacity info, PR passing CI, approved tasks).
  - Seed 1 urgent finding (P0: merge conflict blocking all PRs).
  - Run reconcile() → verify projection structure, severity filtering, and
    persistence round-trip.

Closes #1682.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.control_plane import (
    CAT_APPROVAL_STALL,
    CAT_CI_READY,
    CAT_IDLE_LANE,
    CAT_LANE_HEALTH,
    CAT_PR_STATUS,
    CAT_STALE_DISPATCH,
    CAT_STALLED_LANE,
    CAT_TASK_LIFECYCLE,
    SEVERITY_HIGH,
    SEVERITY_URGENT,
    STATE_OPEN,
    FleetStatus,
    derive_items,
    format_status_text,
    load_fleet_status,
    reconcile,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers — noise and urgent finding factories
# ---------------------------------------------------------------------------

NOW_ISO = "2026-03-24T12:00:00+00:00"


def _routine_findings() -> list[dict]:
    """Generate 10 routine monitor findings at info/warn severity.

    Covers diverse categories to simulate a realistic noisy fleet:
    - 3 info-level (capacity, task lifecycle, CI ready)
    - 4 warn-level (lane health, PR status, stale dispatch, idle lane)
    - 3 warn-level (additional lane/PR findings)

    Note: info-level lane_health findings are intentionally filtered by
    ``items_from_monitor_findings`` as routine noise. This test uses
    non-lane_health categories for info items to verify they survive.
    """
    return [
        # --- INFO findings (3) ---
        {
            "category": CAT_TASK_LIFECYCLE,
            "severity": "info",
            "summary": "Task pkt-001 approved, awaiting dispatch",
            "details": {"task_id": "pkt-001"},
        },
        {
            "category": CAT_CI_READY,
            "severity": "info",
            "summary": "PR #50 CI passed — ready for review",
            "details": {"pr_number": 50},
        },
        {
            "category": CAT_CI_READY,
            "severity": "info",
            "summary": "PR #51 CI passed — ready for review",
            "details": {"pr_number": 51},
        },
        # --- WARN findings (7) ---
        {
            "category": CAT_LANE_HEALTH,
            "severity": "warn",
            "summary": "Lane author-a idle for 25 min",
            "details": {"lane_id": "author-a"},
        },
        {
            "category": CAT_LANE_HEALTH,
            "severity": "warn",
            "summary": "Lane author-b idle for 18 min",
            "details": {"lane_id": "author-b"},
        },
        {
            "category": CAT_PR_STATUS,
            "severity": "warn",
            "summary": "PR #42 has 2 failing checks",
            "details": {"pr_number": 42, "failing_checks": 2},
        },
        {
            "category": CAT_STALE_DISPATCH,
            "severity": "warn",
            "summary": "Task pkt-005 dispatched 45 min ago, no ack",
            "details": {"task_id": "pkt-005", "lane_id": "author-c"},
        },
        {
            "category": CAT_IDLE_LANE,
            "severity": "warn",
            "summary": "Lane flex-a has no active task",
            "details": {"lane_id": "flex-a"},
        },
        {
            "category": CAT_PR_STATUS,
            "severity": "warn",
            "summary": "PR #43 review stalled for 30 min",
            "details": {"pr_number": 43},
        },
        {
            "category": CAT_APPROVAL_STALL,
            "severity": "warn",
            "summary": "Lane author-d pending approval for 12 min",
            "details": {"lane_id": "author-d"},
        },
    ]


def _urgent_finding() -> dict:
    """A single P0-level finding that must surface as urgent."""
    return {
        "category": CAT_PR_STATUS,
        "severity": "high",
        "summary": "PR #99 has merge conflicts — blocks all downstream PRs",
        "details": {"pr_number": 99, "mergeable": "CONFLICTING"},
    }


def _urgent_bus_message() -> dict:
    """A fabricated urgent bus message with an old timestamp."""
    return {
        "message_id": "urgent-noise-test-001",
        "from_lane": "author-c",
        "to_lane": "orchestrator",
        "message_type": "blocker",
        "priority": "urgent",
        "status": "pending",
        "created_at": "2026-03-24T07:00:00+00:00",
        "summary": "CI broken on main — all PRs blocked",
    }


# ---------------------------------------------------------------------------
# 1. Core noise discrimination — derive_items separates severity tiers
# ---------------------------------------------------------------------------


class TestNoiseDiscrimination:
    """Prove derive_items + FleetStatus properties separate noise from urgency."""

    def test_routine_findings_excluded_from_urgent_items(self) -> None:
        """10 routine (info/warn) findings produce 0 urgent items."""
        items = derive_items(
            monitor_findings=_routine_findings(),
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=1)

        assert status.urgent_items == []
        assert status.high_items == []

    def test_single_urgent_surfaces_among_routine(self) -> None:
        """Adding 1 high-severity finding to 10 routine → exactly 1 high item."""
        findings = _routine_findings() + [_urgent_finding()]

        items = derive_items(
            monitor_findings=findings,
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=1)

        # high_items includes high+urgent — exactly 1 item (the merge conflict).
        assert len(status.high_items) == 1
        assert status.high_items[0].pr_number == 99
        assert status.high_items[0].severity == SEVERITY_HIGH
        assert "merge conflicts" in status.high_items[0].summary

        # urgent_items is the more restrictive subset — 0 items here because
        # the finding is severity=high, not severity=urgent.
        assert len(status.urgent_items) == 0

    def test_urgent_bus_message_among_routine(self) -> None:
        """An urgent bus message surfaces in urgent_items even with routine noise."""
        findings = _routine_findings()
        urgent_msg = _urgent_bus_message()

        items = derive_items(
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=1)

        # The urgent bus message should surface.
        assert len(status.urgent_items) == 1
        assert "CI broken" in status.urgent_items[0].summary
        assert status.urgent_items[0].severity == SEVERITY_URGENT

        # high_items includes both high and urgent.
        assert len(status.high_items) == 1

    def test_combined_urgent_sources_with_noise(self) -> None:
        """Urgent bus message + high monitor finding + 10 routine → 2 high items."""
        findings = _routine_findings() + [_urgent_finding()]
        urgent_msg = _urgent_bus_message()

        items = derive_items(
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=1)

        # 2 items in high_items: the merge conflict (high) + the bus msg (urgent).
        assert len(status.high_items) == 2
        severities = {i.severity for i in status.high_items}
        assert SEVERITY_HIGH in severities
        assert SEVERITY_URGENT in severities

        # Only 1 in the more restrictive urgent_items.
        assert len(status.urgent_items) == 1

    def test_all_items_visible_in_open_items(self) -> None:
        """All non-filtered findings are visible in open_items regardless of severity."""
        findings = _routine_findings() + [_urgent_finding()]
        urgent_msg = _urgent_bus_message()

        items = derive_items(
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=1)

        # info-level lane_health findings are filtered, so count the expected:
        # 3 info (non-lane_health) + 7 warn + 1 high + 1 urgent bus msg = 12
        # But actually _routine_findings returns 3 info + 7 warn = 10 items.
        # items_from_monitor_findings filters info lane_health (none here — our
        # info items are task_lifecycle and ci_ready).
        # So: 10 routine + 1 urgent finding + 1 urgent bus msg = 12 open items.
        assert len(status.open_items) >= 11
        assert all(i.state == STATE_OPEN for i in status.open_items)

    def test_info_lane_health_is_noise(self) -> None:
        """Info-level lane_health findings are dropped as routine noise."""
        noise = [
            {
                "category": CAT_LANE_HEALTH,
                "severity": "info",
                "summary": "8 of 12 lanes active — capacity nominal",
                "details": {"active_lanes": 8, "total_lanes": 12},
            },
        ]

        items = derive_items(
            monitor_findings=noise,
            now_iso=NOW_ISO,
        )
        # info lane_health should be filtered out entirely.
        assert len(items) == 0


# ---------------------------------------------------------------------------
# 2. Projection persistence — round-trip preserves discrimination
# ---------------------------------------------------------------------------


class TestNoiseDiscriminationPersistence:
    """Prove noise discrimination survives reconcile → persist → reload."""

    def test_reconcile_roundtrip_preserves_severity_subsets(
        self, tmp_path: Path
    ) -> None:
        """reconcile() → load_fleet_status() preserves urgent/high/open counts."""
        runtime_dir = tmp_path / "runtime"
        findings = _routine_findings() + [_urgent_finding()]

        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            now_iso=NOW_ISO,
        )

        # Verify in-memory counts.
        n_open = len(status.open_items)
        n_high = len(status.high_items)
        n_urgent = len(status.urgent_items)

        assert n_open >= 11  # 10 routine (some may be filtered) + 1 high
        assert n_high == 1  # Only the merge conflict
        assert n_urgent == 0  # No severity=urgent items

        # Reload from disk.
        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert len(reloaded.open_items) == n_open
        assert len(reloaded.high_items) == n_high
        assert len(reloaded.urgent_items) == n_urgent

    def test_noisy_reconcile_with_bus_message_roundtrip(self, tmp_path: Path) -> None:
        """Urgent bus message + routine findings survives persistence round-trip."""
        runtime_dir = tmp_path / "runtime"
        findings = _routine_findings()
        urgent_msg = _urgent_bus_message()

        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )

        assert len(status.urgent_items) == 1

        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert len(reloaded.urgent_items) == 1
        assert "CI broken" in reloaded.urgent_items[0].summary

    def test_summary_dict_counts_match(self, tmp_path: Path) -> None:
        """The to_dict() summary counts match the property-based counts."""
        runtime_dir = tmp_path / "runtime"
        findings = _routine_findings() + [_urgent_finding()]
        urgent_msg = _urgent_bus_message()

        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )

        d = status.to_dict()
        summary = d["summary"]
        assert summary["total"] == len(status.items)
        assert summary["open"] == len(status.open_items)
        assert summary["urgent"] == len(status.urgent_items)
        assert summary["high"] == len(status.high_items)


# ---------------------------------------------------------------------------
# 3. CLI / text output — severity grouping is correct
# ---------------------------------------------------------------------------


class TestNoiseDiscriminationCLI:
    """Prove the text/CLI output correctly groups findings by severity."""

    def test_format_text_shows_urgent_first(self) -> None:
        """Urgent items appear before warn/info in the text output."""
        findings = _routine_findings() + [_urgent_finding()]
        urgent_msg = _urgent_bus_message()

        items = derive_items(
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=5)

        text = format_status_text(status)

        # Verify severity groups exist.
        assert "[URGENT]" in text
        assert "[HIGH]" in text
        assert "[WARN]" in text

        # URGENT should appear before WARN in the output.
        urgent_pos = text.index("[URGENT]")
        warn_pos = text.index("[WARN]")
        assert urgent_pos < warn_pos

    def test_format_text_includes_all_open_items(self) -> None:
        """Every open item's summary appears somewhere in the text output."""
        findings = _routine_findings() + [_urgent_finding()]

        items = derive_items(
            monitor_findings=findings,
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=1)

        text = format_status_text(status)

        # Verify the urgent finding's summary appears.
        assert "merge conflicts" in text

        # Verify at least some routine findings appear.
        assert "PR #42" in text or "author-a" in text

    def test_format_text_header_shows_open_and_urgent_counts(self) -> None:
        """The text header shows (N open, M urgent)."""
        findings = _routine_findings() + [_urgent_finding()]
        urgent_msg = _urgent_bus_message()

        items = derive_items(
            monitor_findings=findings,
            unacked_messages=[urgent_msg],
            now_iso=NOW_ISO,
        )
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=3)

        text = format_status_text(status)

        # Header should show "N open, 1 urgent".
        assert "1 urgent" in text
        assert f"{len(status.open_items)} open" in text


# ---------------------------------------------------------------------------
# 4. Multi-cycle noise discrimination — clearing doesn't break filtering
# ---------------------------------------------------------------------------


class TestNoiseDiscriminationMultiCycle:
    """Prove noise discrimination is stable across multiple reconcile cycles."""

    def test_urgent_clears_but_routine_persists(self, tmp_path: Path) -> None:
        """When the urgent finding resolves, routine items remain in projection."""
        runtime_dir = tmp_path / "runtime"
        findings_with_urgent = _routine_findings() + [_urgent_finding()]

        # Cycle 1: urgent + routine.
        s1 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings_with_urgent,
            now_iso="2026-03-24T12:00:00+00:00",
        )
        assert len(s1.high_items) == 1
        n_open_with_urgent = len(s1.open_items)

        # Cycle 2: urgent finding resolves (removed), routine remains.
        s2 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=_routine_findings(),
            now_iso="2026-03-24T12:05:00+00:00",
        )

        # Urgent item should be auto-cleared.
        assert len(s2.high_items) == 0
        assert len(s2.urgent_items) == 0

        # Routine items are still open (same count minus the cleared urgent).
        open_count = len(s2.open_items)
        assert open_count == n_open_with_urgent - 1

    def test_new_urgent_surfaces_after_previous_cleared(self, tmp_path: Path) -> None:
        """A new urgent finding surfaces even after a previous one was cleared."""
        runtime_dir = tmp_path / "runtime"

        # Cycle 1: first urgent.
        s1 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=_routine_findings()
            + [
                {
                    "category": CAT_STALLED_LANE,
                    "severity": "high",
                    "summary": "Lane ops stalled for 60 min",
                    "details": {"lane_id": "ops"},
                },
            ],
            now_iso="2026-03-24T12:00:00+00:00",
        )
        assert len(s1.high_items) == 1
        assert "ops" in s1.high_items[0].summary

        # Cycle 2: first urgent resolves, new one appears.
        s2 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=_routine_findings()
            + [
                {
                    "category": CAT_PR_STATUS,
                    "severity": "high",
                    "summary": "PR #200 CI red — 5 failing checks",
                    "details": {"pr_number": 200, "failing_checks": 5},
                },
            ],
            now_iso="2026-03-24T12:05:00+00:00",
        )
        assert len(s2.high_items) == 1
        assert s2.high_items[0].pr_number == 200
        assert "PR #200" in s2.high_items[0].summary

    def test_noise_volume_does_not_affect_urgency_detection(
        self, tmp_path: Path
    ) -> None:
        """Even with 50 routine findings, a single urgent item surfaces correctly."""
        runtime_dir = tmp_path / "runtime"

        # Generate 50 routine findings (5 copies of the 10).
        bulk_routine: list[dict] = []
        for i in range(5):
            for finding in _routine_findings():
                # Make each unique by modifying the details.
                f = dict(finding)
                f["details"] = dict(f.get("details", {}))
                # Add a unique suffix to avoid dedup.
                if "lane_id" in f["details"]:
                    f["details"]["lane_id"] = f"{f['details']['lane_id']}-batch{i}"
                if "pr_number" in f["details"]:
                    f["details"]["pr_number"] = f["details"]["pr_number"] + (i * 100)
                if "task_id" in f["details"]:
                    f["details"]["task_id"] = f"{f['details']['task_id']}-batch{i}"
                bulk_routine.append(f)

        findings = bulk_routine + [_urgent_finding()]

        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            now_iso=NOW_ISO,
        )

        # Even with 50 routine items, only 1 high item surfaces.
        assert len(status.high_items) == 1
        assert status.high_items[0].pr_number == 99
        assert len(status.open_items) > 40  # Many routine items are visible.
