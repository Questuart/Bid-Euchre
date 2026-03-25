"""Integration tests for Platform-9a PR3 — Telegram alert push cycle.

Tests the full push pipeline: seed findings → reconcile → evaluate push →
format message → record push state → audit trail.  No actual Telegram calls —
tests verify the state and audit artifacts produced by the push cycle.

Covers exit criteria:
- E1: Unresolved HIGH/URGENT items pushed when fleet is idle
- E2: Push dedup prevents repeated alerts within cooldown
- E3: Severity escalation triggers re-push within cooldown
- E7: All pushes recorded in audit trail
- E8: Push suppressed when STEWARD_TELEGRAM_ENABLED=0
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.alert_push import (
    PushState,
    load_push_state,
    record_push,
)
from bid_euchre.ops.audit_trail import read_records
from bid_euchre.ops.control_plane import (
    SEVERITY_HIGH,
    SEVERITY_URGENT,
    STATE_OPEN,
    ActionableItem,
    FleetStatus,
    reconcile,
)
from bid_euchre.ops.idle_detector import IdleStatus
from bid_euchre.ops.telegram_push import (
    PushResult,
    format_alert_push,
    is_push_enabled,
    prepare_alert_push,
    run_push_cycle,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def _make_item(
    *,
    item_id: str = "aabbccdd1234",
    severity: str = SEVERITY_HIGH,
    summary: str = "Approval stall on author-b",
    lane_id: str = "author-b",
    recommended_action: str = "Nudge author-b or re-dispatch",
) -> ActionableItem:
    return ActionableItem(
        item_id=item_id,
        severity=severity,
        category="approval_stall",
        source="monitor",
        summary=summary,
        first_seen_at=_NOW.isoformat(),
        last_seen_at=_NOW.isoformat(),
        state=STATE_OPEN,
        lane_id=lane_id,
        recommended_action=recommended_action,
    )


def _idle_status(idle: bool = True) -> IdleStatus:
    return IdleStatus(
        idle=idle,
        idle_minutes=95.0 if idle else 5.0,
        last_meaningful_event=_NOW - timedelta(minutes=95) if idle else _NOW,
        active_lanes=[] if idle else ["author-a"],
        reason="Fleet idle" if idle else "Fleet active",
    )


def _fleet_status(*items: ActionableItem) -> FleetStatus:
    return FleetStatus(
        items=list(items),
        generated_at=_NOW.isoformat(),
        cycle_count=1,
    )


# ---------------------------------------------------------------------------
# E1: Push fires when idle + unresolved HIGH/URGENT items exist
# ---------------------------------------------------------------------------


class TestPushFiresWhenIdle:
    """Full push cycle: idle fleet + HIGH item → push result produced."""

    def test_push_prepares_message_for_high_item(self, tmp_path: Path) -> None:
        """A single HIGH item in idle fleet produces a PushResult."""
        item = _make_item()
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        push_state = PushState()
        audit_dir = tmp_path / "audit_trail"

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )

        assert result is not None
        assert isinstance(result, PushResult)
        assert result.chat_id == "12345"
        assert len(result.items_pushed) == 1
        assert result.items_pushed[0].item_id == item.item_id
        assert "aabbccdd" in result.message
        assert "Approval stall" in result.message

    def test_push_prepares_message_for_urgent_item(self, tmp_path: Path) -> None:
        """URGENT items are also pushed."""
        item = _make_item(severity=SEVERITY_URGENT)
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        push_state = PushState()
        audit_dir = tmp_path / "audit_trail"

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )

        assert result is not None
        assert len(result.items_pushed) == 1
        assert "URGENT" in result.message

    def test_no_push_when_fleet_active(self, tmp_path: Path) -> None:
        """No push when the fleet is actively running."""
        item = _make_item()
        status = _fleet_status(item)
        idle = _idle_status(idle=False)
        push_state = PushState()

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            runtime_dir=tmp_path,
        )

        assert result is None

    def test_no_push_for_empty_fleet(self, tmp_path: Path) -> None:
        """No push when there are no items."""
        status = _fleet_status()
        idle = _idle_status(idle=True)
        push_state = PushState()

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            runtime_dir=tmp_path,
        )

        assert result is None


# ---------------------------------------------------------------------------
# E2: Push dedup prevents repeated alerts within cooldown
# ---------------------------------------------------------------------------


class TestPushDedup:
    """After pushing, the same item is not re-pushed within cooldown."""

    def test_no_repush_within_cooldown(self, tmp_path: Path) -> None:
        """Item pushed 5 minutes ago is NOT re-pushed (cooldown=15m)."""
        item = _make_item()
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        push_state = PushState()
        audit_dir = tmp_path / "audit_trail"

        # First push — should succeed.
        first_push_time = _NOW - timedelta(minutes=5)
        result1 = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=first_push_time,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )
        assert result1 is not None

        # Second push 5 minutes later — within cooldown, should be None.
        result2 = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            cooldown_minutes=15.0,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )
        assert result2 is None

    def test_repush_after_cooldown_expires(self, tmp_path: Path) -> None:
        """Item pushed 20 minutes ago IS re-pushed (cooldown=15m)."""
        item = _make_item()
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        push_state = PushState()
        audit_dir = tmp_path / "audit_trail"

        # First push.
        first_push_time = _NOW - timedelta(minutes=20)
        result1 = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=first_push_time,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )
        assert result1 is not None

        # Second push 20 minutes later — cooldown expired.
        result2 = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            cooldown_minutes=15.0,
            now=_NOW,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )
        assert result2 is not None


# ---------------------------------------------------------------------------
# E3: Severity escalation triggers re-push within cooldown
# ---------------------------------------------------------------------------


class TestSeverityEscalation:
    """Severity escalation bypasses cooldown."""

    def test_escalation_bypasses_cooldown(self, tmp_path: Path) -> None:
        """Item pushed as HIGH 5m ago, now URGENT → re-push within cooldown."""
        # First push with HIGH severity.
        push_state = PushState()
        record_push(
            push_state, "aabbccdd1234", SEVERITY_HIGH, now=_NOW - timedelta(minutes=5)
        )

        # Now the item is URGENT.
        item = _make_item(severity=SEVERITY_URGENT)
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        audit_dir = tmp_path / "audit_trail"

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            cooldown_minutes=15.0,
            now=_NOW,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )
        assert result is not None
        assert len(result.items_pushed) == 1
        assert result.items_pushed[0].severity == SEVERITY_URGENT


# ---------------------------------------------------------------------------
# E7: Audit trail records outbound pushes
# ---------------------------------------------------------------------------


class TestAuditTrail:
    """Push cycle creates audit records for every outbound push."""

    def test_audit_record_created_after_push(self, tmp_path: Path) -> None:
        """After a push, the audit trail contains one outbound reply record."""
        item = _make_item()
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        push_state = PushState()
        audit_dir = tmp_path / "audit_trail"

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )
        assert result is not None

        # Read audit records.
        records = read_records(audit_dir=audit_dir)
        assert len(records) == 1
        rec = records[0]
        assert rec.direction == "outbound"
        assert rec.channel_source == "telegram"
        assert rec.exchange_type == "reply"
        assert rec.chat_id == "12345"
        assert rec.metadata.get("purpose") == "alert_push"
        assert rec.metadata.get("item_count") == 1
        assert item.item_id in rec.metadata.get("item_ids", [])

    def test_push_state_persisted_after_push(self, tmp_path: Path) -> None:
        """Push state is saved to disk after a push cycle."""
        item = _make_item()
        status = _fleet_status(item)
        idle = _idle_status(idle=True)
        push_state = PushState()
        audit_dir = tmp_path / "audit_trail"

        prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="12345",
            now=_NOW,
            runtime_dir=tmp_path,
            audit_dir=audit_dir,
        )

        # Reload from disk and verify.
        reloaded = load_push_state(runtime_dir=tmp_path)
        assert item.item_id in reloaded.items
        rec = reloaded.items[item.item_id]
        assert rec.push_count == 1
        assert rec.severity_at_push == SEVERITY_HIGH


# ---------------------------------------------------------------------------
# E8: Push suppressed when STEWARD_TELEGRAM_ENABLED=0
# ---------------------------------------------------------------------------


class TestKillSwitch:
    """Push is suppressed when the env var kill switch is off."""

    def test_push_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When STEWARD_TELEGRAM_ENABLED is not set, push is disabled."""
        monkeypatch.delenv("STEWARD_TELEGRAM_ENABLED", raising=False)
        assert not is_push_enabled()

    def test_push_disabled_when_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When STEWARD_TELEGRAM_ENABLED=0, push is disabled."""
        monkeypatch.setenv("STEWARD_TELEGRAM_ENABLED", "0")
        assert not is_push_enabled()

    def test_push_enabled_when_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When STEWARD_TELEGRAM_ENABLED=1, push is enabled."""
        monkeypatch.setenv("STEWARD_TELEGRAM_ENABLED", "1")
        assert is_push_enabled()

    def test_run_push_cycle_returns_none_when_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_push_cycle returns None immediately when Telegram is disabled."""
        monkeypatch.setenv("STEWARD_TELEGRAM_ENABLED", "0")
        result = run_push_cycle(runtime_dir=tmp_path)
        assert result is None

    def test_run_push_cycle_returns_none_when_no_chat_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_push_cycle returns None when no chat ID is configured."""
        monkeypatch.setenv("STEWARD_TELEGRAM_ENABLED", "1")
        monkeypatch.delenv("STEWARD_ALERT_PUSH_CHAT_ID", raising=False)
        result = run_push_cycle(runtime_dir=tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Format output
# ---------------------------------------------------------------------------


class TestFormatAlertPush:
    """Tests for the alert message formatting."""

    def test_empty_items_returns_empty(self) -> None:
        assert format_alert_push([]) == ""

    def test_format_includes_item_id_prefix(self) -> None:
        item = _make_item(item_id="deadbeef0000")
        msg = format_alert_push([item])
        assert "deadbeef" in msg

    def test_format_includes_severity(self) -> None:
        item = _make_item(severity=SEVERITY_HIGH)
        msg = format_alert_push([item])
        assert "HIGH" in msg

    def test_format_includes_ack_instructions(self) -> None:
        item = _make_item()
        msg = format_alert_push([item])
        assert "ack" in msg.lower()
        assert "mute" in msg.lower()

    def test_format_includes_recommended_action(self) -> None:
        item = _make_item(recommended_action="Re-nudge the lane")
        msg = format_alert_push([item])
        assert "Re-nudge the lane" in msg

    def test_format_multiple_items(self) -> None:
        items = [
            _make_item(item_id="aaa111000000", summary="Issue 1"),
            _make_item(item_id="bbb222000000", summary="Issue 2"),
        ]
        msg = format_alert_push(items)
        assert "2 item(s)" in msg
        assert "aaa11100" in msg
        assert "bbb22200" in msg


# ---------------------------------------------------------------------------
# Full reconcile → push cycle
# ---------------------------------------------------------------------------


class TestFullReconcileToPush:
    """End-to-end: reconcile produces fleet status → push cycle runs."""

    def test_reconcile_then_push(self, tmp_path: Path) -> None:
        """After reconcile seeds a HIGH item, the push cycle picks it up."""
        from bid_euchre.ops.events import append_event

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        events_dir = runtime_dir / "events"
        events_dir.mkdir()
        audit_dir = runtime_dir / "audit_trail"

        # Seed a meaningful event in the past so idle detector thinks we're idle.
        append_event(
            event_type="task_started",
            source="test",
            lane_id="author-a",
            payload={"task_id": "test-task"},
            events_dir=events_dir,
        )

        # Create a HIGH monitor finding to be reconciled.
        from bid_euchre.ops.monitor import MonitorFinding

        finding = MonitorFinding(
            category="approval_stall",
            severity="high",
            summary="author-b has no pending review after 45m",
            details={"lane": "author-b"},
        )

        # Reconcile to generate fleet_status.json.
        reconcile(
            runtime_dir=runtime_dir,
            monitor_finding_objects=[finding],
            now_iso=_NOW.isoformat(),
        )

        # Verify fleet status was created with at least one HIGH item.
        from bid_euchre.ops.control_plane import load_fleet_status

        status = load_fleet_status(runtime_dir)
        assert status is not None
        high_items = [
            i
            for i in status.items
            if i.severity in (SEVERITY_HIGH, SEVERITY_URGENT) and i.state == STATE_OPEN
        ]
        assert len(high_items) >= 1

        # Now run the push evaluator against the reconciled status.
        idle = _idle_status(idle=True)
        push_state = PushState()

        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=push_state,
            chat_id="99999",
            now=_NOW,
            runtime_dir=runtime_dir,
            audit_dir=audit_dir,
        )

        assert result is not None
        assert len(result.items_pushed) >= 1
        assert result.chat_id == "99999"

        # Verify audit record.
        records = read_records(audit_dir=audit_dir)
        assert any(
            r.direction == "outbound" and r.metadata.get("purpose") == "alert_push"
            for r in records
        )
