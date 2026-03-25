"""Tests for alert push evaluator and push state tracking (Platform-9a, PR 1).

Covers:
- Push needed when idle + open HIGH/URGENT items exist
- Push skipped when fleet is active (not idle)
- Push skipped when item already pushed within cooldown
- Push triggered when severity escalates (HIGH → URGENT)
- Push state persistence round-trip
- Empty fleet status produces no pushes
- Cooldown reset on severity change
- Corrupt / missing push state file handling
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bid_euchre.ops.alert_push import (
    DEFAULT_COOLDOWN_MINUTES,
    PUSH_STATE_FILE,
    PUSHABLE_SEVERITIES,
    PushItemRecord,
    PushState,
    evaluate_push_needed,
    load_push_state,
    record_push,
    save_push_state,
)
from bid_euchre.ops.control_plane import (
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_URGENT,
    SEVERITY_WARN,
    STATE_ACKED,
    STATE_OPEN,
    STATE_SUPPRESSED,
    ActionableItem,
    FleetStatus,
)
from bid_euchre.ops.idle_detector import IdleStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def _idle(idle: bool = True) -> IdleStatus:
    """Create an IdleStatus for testing."""
    return IdleStatus(
        idle=idle,
        idle_minutes=120.0 if idle else 5.0,
        last_meaningful_event=NOW - timedelta(hours=2)
        if idle
        else NOW - timedelta(minutes=5),
        active_lanes=[] if idle else ["author-a"],
        reason="test fixture",
    )


def _item(
    item_id: str = "abc123def456",
    severity: str = SEVERITY_HIGH,
    state: str = STATE_OPEN,
) -> ActionableItem:
    """Create an ActionableItem for testing."""
    return ActionableItem(
        item_id=item_id,
        severity=severity,
        category="lane_health",
        source="monitor",
        summary=f"Test item {item_id[:8]}",
        first_seen_at=NOW.isoformat(),
        last_seen_at=NOW.isoformat(),
        state=state,
    )


def _fleet(*items: ActionableItem) -> FleetStatus:
    """Create a FleetStatus from items."""
    return FleetStatus(
        items=list(items),
        generated_at=NOW.isoformat(),
        cycle_count=1,
    )


# ---------------------------------------------------------------------------
# evaluate_push_needed — core logic
# ---------------------------------------------------------------------------


class TestEvaluatePushNeeded:
    """Test the pure evaluation function."""

    def test_push_needed_when_idle_with_high_items(self) -> None:
        """Push is needed when fleet is idle and open HIGH items exist."""
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert len(result) == 1
        assert result[0].item_id == "abc123def456"

    def test_push_needed_when_idle_with_urgent_items(self) -> None:
        """Push is needed when fleet is idle and open URGENT items exist."""
        fleet = _fleet(_item(severity=SEVERITY_URGENT))
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert len(result) == 1

    def test_push_skipped_when_fleet_active(self) -> None:
        """No push when fleet is active (operator at terminal)."""
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(False), PushState(), now=NOW)
        assert result == []

    def test_push_skipped_for_info_items(self) -> None:
        """INFO items are never pushed."""
        fleet = _fleet(_item(severity=SEVERITY_INFO))
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert result == []

    def test_push_skipped_for_warn_items(self) -> None:
        """WARN items are never pushed."""
        fleet = _fleet(_item(severity=SEVERITY_WARN))
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert result == []

    def test_push_skipped_for_acked_items(self) -> None:
        """Acked items are not pushed even if HIGH/URGENT."""
        fleet = _fleet(_item(severity=SEVERITY_HIGH, state=STATE_ACKED))
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert result == []

    def test_push_skipped_for_suppressed_items(self) -> None:
        """Suppressed items are not pushed."""
        fleet = _fleet(_item(severity=SEVERITY_HIGH, state=STATE_SUPPRESSED))
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert result == []

    def test_empty_fleet_produces_no_pushes(self) -> None:
        """Empty fleet status produces no pushes."""
        fleet = _fleet()
        result = evaluate_push_needed(fleet, _idle(True), PushState(), now=NOW)
        assert result == []

    def test_push_skipped_within_cooldown(self) -> None:
        """Push is skipped when same item was pushed within cooldown window."""
        pushed_at = NOW - timedelta(minutes=5)  # 5 min ago, well within 15m cooldown
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_HIGH,
                ),
            }
        )
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert result == []

    def test_push_after_cooldown_elapsed(self) -> None:
        """Push is allowed once the cooldown has elapsed."""
        pushed_at = NOW - timedelta(minutes=20)  # 20 min ago, past 15m cooldown
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_HIGH,
                ),
            }
        )
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert len(result) == 1

    def test_push_on_severity_escalation_bypasses_cooldown(self) -> None:
        """Severity escalation triggers push even within cooldown window."""
        pushed_at = NOW - timedelta(minutes=5)  # Within cooldown
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_HIGH,  # Was HIGH
                ),
            }
        )
        # Now it's URGENT
        fleet = _fleet(_item(severity=SEVERITY_URGENT))
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert len(result) == 1

    def test_no_push_on_severity_downgrade(self) -> None:
        """Severity downgrade within cooldown does NOT trigger push."""
        pushed_at = NOW - timedelta(minutes=5)
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_URGENT,  # Was URGENT
                ),
            }
        )
        # Now it's HIGH (downgrade)
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert result == []

    def test_multiple_items_mixed_push_decisions(self) -> None:
        """Multiple items: some pushed, some skipped."""
        pushed_at = NOW - timedelta(minutes=5)
        state = PushState(
            items={
                "item_already_ok": PushItemRecord(
                    item_id="item_already_ok",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_HIGH,
                ),
            }
        )
        fleet = _fleet(
            _item(item_id="item_already_ok", severity=SEVERITY_HIGH),
            _item(item_id="item_new_high", severity=SEVERITY_HIGH),
            _item(item_id="item_new_urgent", severity=SEVERITY_URGENT),
            _item(item_id="item_info_skip", severity=SEVERITY_INFO),
        )
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        pushed_ids = {i.item_id for i in result}
        assert "item_new_high" in pushed_ids
        assert "item_new_urgent" in pushed_ids
        assert "item_already_ok" not in pushed_ids  # Within cooldown
        assert "item_info_skip" not in pushed_ids  # INFO not pushable

    def test_custom_cooldown_minutes(self) -> None:
        """Custom cooldown is respected."""
        pushed_at = NOW - timedelta(minutes=10)
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_HIGH,
                ),
            }
        )
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        # Default 15m → should skip (10m < 15m)
        result_default = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert result_default == []
        # Custom 5m → should push (10m > 5m)
        result_custom = evaluate_push_needed(
            fleet, _idle(True), state, cooldown_minutes=5.0, now=NOW
        )
        assert len(result_custom) == 1

    def test_corrupt_timestamp_treated_as_never_pushed(self) -> None:
        """Corrupt last_pushed_at timestamp results in re-push."""
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at="not-a-timestamp",
                    push_count=1,
                    severity_at_push=SEVERITY_HIGH,
                ),
            }
        )
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert len(result) == 1

    def test_warn_to_high_escalation_triggers_push(self) -> None:
        """Escalation from WARN → HIGH triggers push (crosses pushable threshold)."""
        pushed_at = NOW - timedelta(minutes=5)
        state = PushState(
            items={
                "abc123def456": PushItemRecord(
                    item_id="abc123def456",
                    last_pushed_at=pushed_at.isoformat(),
                    push_count=1,
                    severity_at_push=SEVERITY_WARN,
                ),
            }
        )
        fleet = _fleet(_item(severity=SEVERITY_HIGH))
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# record_push
# ---------------------------------------------------------------------------


class TestRecordPush:
    """Test push state mutation."""

    def test_record_first_push(self) -> None:
        """Recording a push for a new item creates the record."""
        state = PushState()
        record_push(state, "item_1", SEVERITY_HIGH, now=NOW)
        assert "item_1" in state.items
        assert state.items["item_1"].push_count == 1
        assert state.items["item_1"].severity_at_push == SEVERITY_HIGH
        assert state.items["item_1"].last_pushed_at == NOW.isoformat()

    def test_record_subsequent_push_increments_count(self) -> None:
        """Recording multiple pushes increments the count."""
        state = PushState()
        record_push(state, "item_1", SEVERITY_HIGH, now=NOW)
        record_push(state, "item_1", SEVERITY_HIGH, now=NOW + timedelta(minutes=20))
        assert state.items["item_1"].push_count == 2

    def test_record_push_updates_severity(self) -> None:
        """Recording a push with new severity updates severity_at_push."""
        state = PushState()
        record_push(state, "item_1", SEVERITY_HIGH, now=NOW)
        record_push(state, "item_1", SEVERITY_URGENT, now=NOW + timedelta(minutes=5))
        assert state.items["item_1"].severity_at_push == SEVERITY_URGENT

    def test_record_push_updates_timestamp(self) -> None:
        """Recording a push updates last_pushed_at."""
        state = PushState()
        t1 = NOW
        t2 = NOW + timedelta(minutes=20)
        record_push(state, "item_1", SEVERITY_HIGH, now=t1)
        record_push(state, "item_1", SEVERITY_HIGH, now=t2)
        assert state.items["item_1"].last_pushed_at == t2.isoformat()

    def test_record_push_separate_items(self) -> None:
        """Recording pushes for different items tracks them independently."""
        state = PushState()
        record_push(state, "item_a", SEVERITY_HIGH, now=NOW)
        record_push(state, "item_b", SEVERITY_URGENT, now=NOW)
        assert len(state.items) == 2
        assert state.items["item_a"].severity_at_push == SEVERITY_HIGH
        assert state.items["item_b"].severity_at_push == SEVERITY_URGENT


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    """Test push state load/save round-trip."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """Push state survives save + load cycle."""
        state = PushState()
        record_push(state, "item_1", SEVERITY_HIGH, now=NOW)
        record_push(state, "item_2", SEVERITY_URGENT, now=NOW)
        state.last_evaluation_at = NOW.isoformat()

        save_push_state(state, runtime_dir=tmp_path)
        loaded = load_push_state(runtime_dir=tmp_path)

        assert loaded.last_evaluation_at == NOW.isoformat()
        assert len(loaded.items) == 2
        assert loaded.items["item_1"].push_count == 1
        assert loaded.items["item_1"].severity_at_push == SEVERITY_HIGH
        assert loaded.items["item_2"].push_count == 1
        assert loaded.items["item_2"].severity_at_push == SEVERITY_URGENT

    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Loading from a missing file returns a fresh PushState."""
        state = load_push_state(runtime_dir=tmp_path)
        assert state.items == {}
        assert state.last_evaluation_at == ""

    def test_load_corrupt_file_returns_empty(self, tmp_path: Path) -> None:
        """Loading from a corrupt file returns a fresh PushState."""
        path = tmp_path / PUSH_STATE_FILE
        path.write_text("not valid json{{{")
        state = load_push_state(runtime_dir=tmp_path)
        assert state.items == {}

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Save creates intermediate directories if needed."""
        deep_dir = tmp_path / "nested" / "runtime"
        save_push_state(PushState(), runtime_dir=deep_dir)
        assert (deep_dir / PUSH_STATE_FILE).exists()

    def test_save_is_valid_json(self, tmp_path: Path) -> None:
        """Saved file is valid JSON with expected structure."""
        state = PushState()
        record_push(state, "item_x", SEVERITY_HIGH, now=NOW)
        save_push_state(state, runtime_dir=tmp_path)

        raw = (tmp_path / PUSH_STATE_FILE).read_text()
        data = json.loads(raw)
        assert "items" in data
        assert "item_x" in data["items"]
        assert data["items"]["item_x"]["push_count"] == 1


# ---------------------------------------------------------------------------
# Integration: evaluate + record + re-evaluate
# ---------------------------------------------------------------------------


class TestEvaluateRecordCycle:
    """Test the full evaluate → record → re-evaluate cycle."""

    def test_full_cycle_dedup(self) -> None:
        """After recording a push, re-evaluation skips the item within cooldown."""
        fleet = _fleet(
            _item(item_id="item_a", severity=SEVERITY_HIGH),
            _item(item_id="item_b", severity=SEVERITY_URGENT),
        )
        state = PushState()

        # First evaluation: both items should be pushed.
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert len(result) == 2

        # Record pushes.
        for item in result:
            record_push(state, item.item_id, item.severity, now=NOW)

        # Re-evaluate within cooldown: nothing to push.
        result2 = evaluate_push_needed(
            fleet, _idle(True), state, now=NOW + timedelta(minutes=5)
        )
        assert result2 == []

        # Re-evaluate after cooldown: both items pushed again.
        result3 = evaluate_push_needed(
            fleet, _idle(True), state, now=NOW + timedelta(minutes=20)
        )
        assert len(result3) == 2

    def test_escalation_mid_cooldown(self) -> None:
        """Severity escalation triggers re-push even within cooldown."""
        item = _item(item_id="item_a", severity=SEVERITY_HIGH)
        fleet = _fleet(item)
        state = PushState()

        # Push the HIGH item.
        result = evaluate_push_needed(fleet, _idle(True), state, now=NOW)
        assert len(result) == 1
        record_push(state, "item_a", SEVERITY_HIGH, now=NOW)

        # Escalate to URGENT and re-evaluate within cooldown.
        escalated_item = _item(item_id="item_a", severity=SEVERITY_URGENT)
        fleet2 = _fleet(escalated_item)
        result2 = evaluate_push_needed(
            fleet2, _idle(True), state, now=NOW + timedelta(minutes=5)
        )
        assert len(result2) == 1
        assert result2[0].severity == SEVERITY_URGENT


# ---------------------------------------------------------------------------
# Default cooldown constant
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify exported constants."""

    def test_default_cooldown(self) -> None:
        assert DEFAULT_COOLDOWN_MINUTES == 15.0

    def test_pushable_severities(self) -> None:
        assert SEVERITY_HIGH in PUSHABLE_SEVERITIES
        assert SEVERITY_URGENT in PUSHABLE_SEVERITIES
        assert SEVERITY_INFO not in PUSHABLE_SEVERITIES
        assert SEVERITY_WARN not in PUSHABLE_SEVERITIES
