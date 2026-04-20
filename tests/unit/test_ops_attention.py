"""Tests for the PR-MSG-2 delivery-policy helper and PR-MSG-4 broker.

PR-MSG-2 proves the immediate-send nudge policy in
:mod:`bid_euchre.ops.attention`:

- Low/normal ``progress`` messages: **no nudge**
- ``blocker``: **nudge**
- ``escalation``: **nudge**
- ``supervisor_alert`` at priority ``high``: **nudge**
- ``supervisor_alert`` at priority ``urgent``: **nudge**
- ``supervisor_alert`` at priority ``normal`` / ``low``: **no nudge**
- ``send_message`` failure: **no nudge attempted**

PR-MSG-4 proves the broker daemon:

- Cursor resumes on restart (byte-offset persistence)
- Deferred ticket transitions (pending → nudged, pending → deferred →
  nudged, pending → abandoned)
- Safe / unsafe poke decisions (mocked pane state)
- Pidfile single-instance guard
- Exactly-once nudge per message_sent event across crash-restart

The architectural invariant is that ``send_with_attention`` wraps (not
replaces) ``send_message``, so all durability guarantees still hold and
no tmux coupling leaks into the bus layer.  The broker reuses existing
pane-state helpers rather than inventing new ones.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bid_euchre.ops.attention import (
    COMPACTION_MIN_BYTES,
    COMPACTION_TERMINAL_RETENTION_HOURS,
    COMPACTION_TERMINAL_RETENTION_MAX,
    MAX_ATTEMPTS,
    AttentionState,
    DeferredTicket,
    acquire_pidfile,
    compact_tickets,
    get_status,
    load_tickets,
    pending_tickets,
    read_cursor,
    read_pidfile,
    release_pidfile,
    run_once,
    send_with_attention,
    should_nudge_for_message,
    write_cursor,
)
from bid_euchre.ops.message_bus import create_message, shared_bus_root
from bid_euchre.ops.worker_pool import PoolAction

_ATTENTION = "bid_euchre.ops.attention"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus_root(tmp_path: Path) -> Path:
    """Isolated bus root for each test."""
    return shared_bus_root(tmp_path / "message_bus")


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Isolated events directory for each test."""
    d = tmp_path / "events"
    d.mkdir()
    return d


def _nudge_ok(lane_id: str) -> PoolAction:
    return PoolAction(
        action="inbox_nudge",
        lane_id=lane_id,
        reason=f"Sent /inbox-poll to {lane_id}",
        executed=True,
    )


# ---------------------------------------------------------------------------
# should_nudge_for_message — pure policy table
# ---------------------------------------------------------------------------


class TestShouldNudgeForMessage:
    """Cover the policy decision function directly, no IO."""

    @pytest.mark.parametrize("priority", ["low", "normal", "high", "urgent"])
    def test_blocker_always_nudges(self, priority: str) -> None:
        assert should_nudge_for_message("blocker", priority) is True

    @pytest.mark.parametrize("priority", ["low", "normal", "high", "urgent"])
    def test_escalation_always_nudges(self, priority: str) -> None:
        assert should_nudge_for_message("escalation", priority) is True

    def test_supervisor_alert_high_nudges(self) -> None:
        assert should_nudge_for_message("supervisor_alert", "high") is True

    def test_supervisor_alert_urgent_nudges(self) -> None:
        assert should_nudge_for_message("supervisor_alert", "urgent") is True

    @pytest.mark.parametrize("priority", ["low", "normal"])
    def test_supervisor_alert_low_normal_does_not_nudge(self, priority: str) -> None:
        assert should_nudge_for_message("supervisor_alert", priority) is False

    @pytest.mark.parametrize("priority", ["low", "normal", "high", "urgent"])
    def test_progress_never_nudges(self, priority: str) -> None:
        assert should_nudge_for_message("progress", priority) is False

    @pytest.mark.parametrize(
        "msg_type",
        ["assignment", "ack", "completion", "recovery"],
    )
    def test_other_types_never_nudge(self, msg_type: str) -> None:
        # All priorities — these message types never trigger a nudge.
        for priority in ("low", "normal", "high", "urgent"):
            assert should_nudge_for_message(msg_type, priority) is False


# ---------------------------------------------------------------------------
# send_with_attention — end-to-end policy wiring
# ---------------------------------------------------------------------------


class TestSendWithAttentionPolicy:
    """Prove the required 7 policy cases from the PR-MSG-2 task packet."""

    def test_low_priority_progress_does_not_nudge(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Case 1: low/normal progress — durable write, NO nudge."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="progress",
            summary="low-prio progress heartbeat",
            priority="low",
        )
        with patch(f"{_ATTENTION}.nudge_inbox") as mock_nudge:
            mid = send_with_attention(msg, bus_root, events_dir=events_dir)
        assert mid == msg.message_id
        mock_nudge.assert_not_called()

    def test_normal_priority_progress_does_not_nudge(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Case 1b: normal progress (the common path) also does NOT nudge."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="progress",
            summary="normal-prio progress heartbeat",
            priority="normal",
        )
        with patch(f"{_ATTENTION}.nudge_inbox") as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_not_called()

    def test_blocker_nudges(self, bus_root: Path, events_dir: Path) -> None:
        """Case 2: blocker — nudges recipient."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="blocker",
            summary="Cannot proceed — waiting on decision",
            priority="high",
        )
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=_nudge_ok("orchestrator"),
        ) as mock_nudge:
            mid = send_with_attention(msg, bus_root, events_dir=events_dir)
        assert mid == msg.message_id
        mock_nudge.assert_called_once_with("orchestrator")

    def test_escalation_nudges(self, bus_root: Path, events_dir: Path) -> None:
        """Case 3: escalation — nudges recipient."""
        msg = create_message(
            from_lane="ops-monitor",
            to_lane="orchestrator",
            message_type="escalation",
            summary="Approval stall on author-b",
            priority="urgent",
        )
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=_nudge_ok("orchestrator"),
        ) as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_called_once_with("orchestrator")

    def test_supervisor_alert_high_nudges(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Case 4: supervisor_alert high — nudges recipient."""
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="Monitor: 2 HIGH findings",
            priority="high",
        )
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=_nudge_ok("orchestrator"),
        ) as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_called_once_with("orchestrator")

    def test_supervisor_alert_urgent_nudges(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Case 5: supervisor_alert urgent — nudges recipient."""
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="Fleet-wide incident",
            priority="urgent",
        )
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=_nudge_ok("orchestrator"),
        ) as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_called_once_with("orchestrator")

    def test_supervisor_alert_normal_does_not_nudge(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Case 6: supervisor_alert normal priority — does NOT nudge.

        This is the most important negative case: routine info rollups ride
        the durable-only path to avoid turning every monitor cycle into a
        pane interruption.
        """
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="Monitor: 0 HIGH, 0 warn, 3 info findings (all nominal)",
            priority="normal",
        )
        with patch(f"{_ATTENTION}.nudge_inbox") as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_not_called()

    def test_supervisor_alert_low_does_not_nudge(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Case 6b: supervisor_alert low priority — does NOT nudge."""
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            summary="Low-priority heartbeat",
            priority="low",
        )
        with patch(f"{_ATTENTION}.nudge_inbox") as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_not_called()


# ---------------------------------------------------------------------------
# send_with_attention — failure semantics
# ---------------------------------------------------------------------------


class TestSendWithAttentionFailureSemantics:
    """Prove: no-nudge-on-send-failure, and best-effort nudge swallows errors."""

    def test_send_failure_prevents_nudge(self, bus_root: Path) -> None:
        """Case 7: send_message raises — nudge is never attempted."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="blocker",  # would normally nudge
            summary="Blocker that never lands",
            priority="urgent",
        )
        with (
            patch(
                f"{_ATTENTION}.send_message",
                side_effect=OSError("audit-trail IO failure"),
            ) as mock_send,
            patch(f"{_ATTENTION}.nudge_inbox") as mock_nudge,
        ):
            with pytest.raises(OSError, match="audit-trail IO failure"):
                send_with_attention(msg, bus_root)
        mock_send.assert_called_once()
        mock_nudge.assert_not_called()

    def test_value_error_from_send_prevents_nudge(self, bus_root: Path) -> None:
        """Duplicate-ID ValueError from send_message — no nudge."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="escalation",
            summary="Escalation that would nudge",
            priority="urgent",
        )
        with (
            patch(
                f"{_ATTENTION}.send_message",
                side_effect=ValueError("Duplicate message_id"),
            ),
            patch(f"{_ATTENTION}.nudge_inbox") as mock_nudge,
        ):
            with pytest.raises(ValueError, match="Duplicate message_id"):
                send_with_attention(msg, bus_root)
        mock_nudge.assert_not_called()

    def test_nudge_failure_is_swallowed(self, bus_root: Path, events_dir: Path) -> None:
        """nudge_inbox raising never masks the durable send_message result."""
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="blocker",
            summary="Blocker with flaky tmux",
            priority="high",
        )
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            side_effect=RuntimeError("tmux exploded"),
        ) as mock_nudge:
            # Must NOT raise — best-effort policy.
            mid = send_with_attention(msg, bus_root, events_dir=events_dir)
        assert mid == msg.message_id
        mock_nudge.assert_called_once_with("orchestrator")

    def test_nudge_not_executed_is_logged_but_returned(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """If nudge_inbox returns executed=False, send_with_attention still
        returns the durable message_id without raising.
        """
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="escalation",
            summary="Escalation when pane is missing",
            priority="urgent",
        )
        failed_nudge = PoolAction(
            action="inbox_nudge",
            lane_id="orchestrator",
            reason="pane not found",
            executed=False,
            error="nudge_failed",
        )
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=failed_nudge,
        ) as mock_nudge:
            mid = send_with_attention(msg, bus_root, events_dir=events_dir)
        assert mid == msg.message_id
        mock_nudge.assert_called_once()


# ---------------------------------------------------------------------------
# send_with_attention — parameter forwarding
# ---------------------------------------------------------------------------


class TestSendWithAttentionForwarding:
    """Prove kwargs are wired through to send_message and nudge_inbox."""

    def test_forwards_deduplicate_flag(self, bus_root: Path, events_dir: Path) -> None:
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="progress",
            summary="Dedupe test",
            priority="normal",
        )
        with patch(
            f"{_ATTENTION}.send_message",
            return_value=msg.message_id,
        ) as mock_send:
            send_with_attention(
                msg,
                bus_root,
                events_dir=events_dir,
                deduplicate=True,
            )
        mock_send.assert_called_once_with(
            msg,
            bus_root,
            events_dir=events_dir,
            deduplicate=True,
        )

    def test_forwards_tmux_overrides_to_nudge(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="blocker",
            summary="Blocker with custom tmux",
            priority="urgent",
        )
        runtime = Path("/tmp/custom-runtime")
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=_nudge_ok("orchestrator"),
        ) as mock_nudge:
            send_with_attention(
                msg,
                bus_root,
                events_dir=events_dir,
                tmux_session="alt-session",
                runtime_dir=runtime,
            )
        mock_nudge.assert_called_once_with(
            "orchestrator",
            tmux_session="alt-session",
            runtime_dir=runtime,
        )

    def test_durable_write_actually_happens(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """Round-trip sanity: the message appears in the recipient inbox even
        when the nudge is short-circuited (durable path is never skipped)."""
        from bid_euchre.ops.message_bus import read_inbox

        msg = create_message(
            from_lane="author-a",
            to_lane="orchestrator",
            message_type="blocker",
            summary="End-to-end durability check",
            priority="high",
        )

        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=_nudge_ok("orchestrator"),
        ):
            send_with_attention(msg, bus_root, events_dir=events_dir)

        inbox = read_inbox("orchestrator", bus_root)
        assert len(inbox) == 1
        assert inbox[0]["message_id"] == msg.message_id
        assert inbox[0]["message_type"] == "blocker"


# ---------------------------------------------------------------------------
# Module invariant: the bus layer must not grow tmux coupling
# ---------------------------------------------------------------------------


class TestBusBoundaryInvariant:
    """Regression-locks on the architectural constraint from PR-MSG-2."""

    def test_message_bus_send_message_has_no_nudge_parameter(self) -> None:
        """send_message must NOT accept a nudge_recipient kwarg.

        This is the core invariant from PR-MSG-2: delivery policy lives in
        attention.py, not in the durable bus layer.
        """
        import inspect

        from bid_euchre.ops.message_bus import send_message

        sig = inspect.signature(send_message)
        params = set(sig.parameters.keys())
        # Explicitly forbid any "nudge"-style kwarg creeping in.
        for forbidden in (
            "nudge_recipient",
            "nudge",
            "nudge_on_send",
            "tmux_session",
        ):
            assert (
                forbidden not in params
            ), f"send_message signature must stay tmux-free; found {forbidden!r}"

    def test_attention_module_exports_both_helpers(self) -> None:
        """Public API check — both helpers are reachable as documented."""
        import bid_euchre.ops.attention as attention_mod

        assert hasattr(attention_mod, "send_with_attention")
        assert hasattr(attention_mod, "should_nudge_for_message")

    def test_attention_module_imports_without_cycle(self) -> None:
        """Import smoke test (also enforced by the validation shell cmd)."""
        # A fresh import_module call would just return the cached module;
        # the meaningful check is that our imports completed at module load.
        import importlib

        mod = importlib.import_module("bid_euchre.ops.attention")
        assert mod.send_with_attention is send_with_attention
        assert mod.should_nudge_for_message is should_nudge_for_message


# ---------------------------------------------------------------------------
# Regression: nudge target is always msg.to_lane
# ---------------------------------------------------------------------------


class TestNudgeTargetsRecipient:
    def test_nudge_targets_to_lane_not_from_lane(
        self, bus_root: Path, events_dir: Path
    ) -> None:
        """The nudge must wake the recipient, not the sender.

        A bug here would ping the original sender's pane and never notify
        the lane that actually needs to react.
        """
        msg = create_message(
            from_lane="author-c",
            to_lane="review",
            message_type="blocker",
            summary="Review needed on stuck PR",
            priority="urgent",
        )
        # Note: MagicMock returns a MagicMock (truthy) for attribute access.
        # We only need to ensure the target is correct.
        fake_action = MagicMock(executed=True, reason="ok")
        with patch(
            f"{_ATTENTION}.nudge_inbox",
            return_value=fake_action,
        ) as mock_nudge:
            send_with_attention(msg, bus_root, events_dir=events_dir)
        mock_nudge.assert_called_once()
        called_lane = mock_nudge.call_args.args[0]
        assert called_lane == "review"


# ---------------------------------------------------------------------------
# PR-MSG-4: Attention broker daemon
# ---------------------------------------------------------------------------


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Isolated runtime root for broker tests."""
    rt = tmp_path / "runtime"
    rt.mkdir()
    (rt / "events").mkdir()
    return rt


def _write_events(runtime_dir: Path, events: list[dict]) -> None:
    """Append a list of event dicts to events.jsonl (creates file if absent)."""
    events_file = runtime_dir / "events" / "events.jsonl"
    with open(events_file, "a") as f:
        for ev in events:
            f.write(json.dumps(ev, sort_keys=True) + "\n")


def _msg_sent_event(
    *,
    to_lane: str,
    message_type: str,
    priority: str = "high",
    from_lane: str = "author-a",
    message_id: str | None = None,
) -> dict:
    """Build a synthetic message_sent event matching the events.jsonl schema."""
    return {
        "timestamp": "2026-04-20T18:00:00+00:00",
        "event_type": "message_sent",
        "source": "ops.message_bus",
        "lane_id": from_lane,
        "payload": {
            "message_id": message_id or f"mid-{to_lane}-{message_type}",
            "message_type": message_type,
            "priority": priority,
            "to_lane": to_lane,
            "task_id": None,
            "thread_id": None,
        },
    }


def _safe_pane(_lane_id: str) -> tuple[str, str]:
    return ("safe", "idle")


def _busy_pane(_lane_id: str) -> tuple[str, str]:
    return ("busy", "active_work_detected")


def _missing_pane(_lane_id: str) -> tuple[str, str]:
    return ("missing", "pane_not_found")


def _record_nudge_fn(recorder: list[str]):
    """Build a nudge_fn that records each lane it was asked to nudge."""

    def _fn(lane_id: str) -> PoolAction:
        recorder.append(lane_id)
        return PoolAction(
            action="inbox_nudge",
            lane_id=lane_id,
            reason=f"fake nudge to {lane_id}",
            executed=True,
        )

    return _fn


class TestAttentionStateLayout:
    """Filesystem-layout invariants for the broker state dir."""

    def test_from_runtime_dir_uses_attention_broker_subdir(
        self, runtime_dir: Path
    ) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        assert state.root == runtime_dir / "attention_broker"
        assert state.pidfile.name == "pid"
        assert state.cursor_file.name == "cursor.json"
        assert state.tickets_file.name == "deferred_tickets.jsonl"
        assert state.failure_sentinel.name == "FAILED"
        assert state.events_file == runtime_dir / "events" / "events.jsonl"

    def test_ensure_dir_creates_directory(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        assert not state.root.exists()
        state.ensure_dir()
        assert state.root.is_dir()


class TestPidfileGuard:
    """Single-instance protection via liveness-checked pidfile."""

    def test_acquire_empty_succeeds(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        assert acquire_pidfile(state) is True
        assert state.pidfile.read_text().strip() == str(os.getpid())

    def test_stale_pidfile_is_replaced(self, runtime_dir: Path) -> None:
        """A pidfile pointing at a dead PID must be claimable."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        # PID 1 typically exists, but 999999 almost certainly does not.
        dead_pid = 999_999
        state.pidfile.write_text(f"{dead_pid}\n")
        assert acquire_pidfile(state) is True
        assert state.pidfile.read_text().strip() == str(os.getpid())

    def test_garbage_pidfile_is_replaced(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        state.pidfile.write_text("not-a-pid\n")
        assert acquire_pidfile(state) is True

    def test_live_pidfile_blocks_acquire(self, runtime_dir: Path) -> None:
        """A pidfile pointing at a LIVE process (other than us) refuses
        acquisition.

        We simulate by writing the current test process's PID as if another
        daemon owned it, then calling acquire_pidfile with a monkey-patched
        getpid() that returns a different PID.
        """
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        # The test process itself is alive — write its pid as though it were
        # "another daemon".
        owner_pid = os.getpid()
        state.pidfile.write_text(f"{owner_pid}\n")

        with patch(f"{_ATTENTION}.os.getpid", return_value=owner_pid + 1):
            assert acquire_pidfile(state) is False

    def test_release_only_removes_own_pidfile(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        foreign_pid = os.getpid() + 1
        state.pidfile.write_text(f"{foreign_pid}\n")
        release_pidfile(state)  # we are not the owner
        assert state.pidfile.exists()
        assert state.pidfile.read_text().strip() == str(foreign_pid)

    def test_release_removes_our_pidfile(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        assert acquire_pidfile(state) is True
        release_pidfile(state)
        assert not state.pidfile.exists()

    def test_read_pidfile_reports_live_only(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        state.pidfile.write_text("999999\n")  # dead
        assert read_pidfile(state) is None
        state.pidfile.write_text(f"{os.getpid()}\n")
        assert read_pidfile(state) == os.getpid()


class TestCursorResume:
    """events.jsonl byte-offset cursor persists across daemon restarts."""

    def test_cursor_default_zero(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        assert read_cursor(state) == 0

    def test_cursor_roundtrip(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        write_cursor(state, 1234)
        assert read_cursor(state) == 1234

    def test_malformed_cursor_file_falls_back_to_zero(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        state.cursor_file.write_text("not json")
        assert read_cursor(state) == 0

    def test_run_once_advances_cursor(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        state = AttentionState.from_runtime_dir(runtime_dir)
        assert read_cursor(state) == 0
        nudged: list[str] = []
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        size = (runtime_dir / "events" / "events.jsonl").stat().st_size
        assert read_cursor(state) == size
        assert nudged == ["author-b"]

    def test_run_once_does_not_replay_on_restart(self, runtime_dir: Path) -> None:
        """Second run with no new events must produce no new nudges."""
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert nudged == ["author-b"]
        # Simulate a daemon restart — the cursor persists, so the second
        # run sees no new events.
        nudged.clear()
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert nudged == []


class TestSafePokeDecision:
    """Safe / unsafe poke classifier steers the ticket transitions."""

    def test_safe_pane_nudges_immediately(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert nudged == ["author-b"]
        assert summary.nudged == 1
        assert summary.tickets_created == 1
        assert summary.pending_after == 0

    def test_busy_pane_defers_no_nudge(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_busy_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert nudged == []
        assert summary.nudged == 0
        assert summary.deferred == 1
        assert summary.pending_after == 1

    def test_missing_pane_abandons(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_missing_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert nudged == []
        assert summary.abandoned == 1
        assert summary.pending_after == 0

    def test_self_loop_is_filtered(self, runtime_dir: Path) -> None:
        """An event where sender == recipient creates no ticket."""
        ev = _msg_sent_event(
            to_lane="author-a",
            message_type="blocker",
            from_lane="author-a",
        )
        _write_events(runtime_dir, [ev])
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert summary.tickets_created == 0
        assert nudged == []

    def test_non_nudge_type_creates_no_ticket(self, runtime_dir: Path) -> None:
        """progress / ack / completion never create broker tickets."""
        events = [
            _msg_sent_event(to_lane="author-b", message_type=t)
            for t in ("progress", "ack", "completion", "assignment")
        ]
        _write_events(runtime_dir, events)
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert summary.new_events_seen == len(events)
        assert summary.tickets_created == 0
        assert nudged == []


class TestDeferredTicketTransitions:
    """Exercises the pending → deferred → nudged / abandoned transitions."""

    def test_busy_then_safe_nudges_exactly_once(self, runtime_dir: Path) -> None:
        """Cycle 1 defers (busy), cycle 2 (after retry window) nudges."""
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="escalation")],
        )
        nudged: list[str] = []

        # Cycle 1: busy → defer
        t0 = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        summary1 = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_busy_pane,
            nudge_fn=_record_nudge_fn(nudged),
            now=t0,
        )
        assert summary1.deferred == 1
        assert summary1.pending_after == 1
        assert nudged == []

        # Cycle 2: safe → nudge, at a time well past the first retry window
        t1 = t0 + timedelta(seconds=60)
        summary2 = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
            now=t1,
        )
        assert summary2.nudged == 1
        assert summary2.pending_after == 0
        assert nudged == ["author-b"]

    def test_retry_before_window_is_a_no_op(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        t0 = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_busy_pane,
            nudge_fn=_record_nudge_fn(nudged),
            now=t0,
        )
        # 1 second later — still well within the 10s first-retry window.
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
            now=t0 + timedelta(seconds=1),
        )
        # The pane is now "safe" BUT we haven't reached next_retry_at yet,
        # so nothing should fire.
        assert summary.nudged == 0
        assert summary.deferred == 0
        assert nudged == []

    def test_exhausted_retries_abandon(self, runtime_dir: Path) -> None:
        """After MAX_ATTEMPTS on a persistently busy pane, ticket is abandoned."""
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)

        for i in range(MAX_ATTEMPTS):
            run_once(
                runtime_dir=runtime_dir,
                pane_state_fn=_busy_pane,
                nudge_fn=_record_nudge_fn(nudged),
                now=now + timedelta(seconds=1000 * i),
            )

        assert nudged == []
        tickets = list(
            load_tickets(AttentionState.from_runtime_dir(runtime_dir)).values()
        )
        assert len(tickets) == 1
        assert tickets[0].status == "abandoned"
        assert tickets[0].attempts == MAX_ATTEMPTS

    def test_ticket_dedup_on_duplicate_message_id(self, runtime_dir: Path) -> None:
        """Same message_id emitted twice creates only one ticket."""
        ev = _msg_sent_event(
            to_lane="author-b",
            message_type="blocker",
            message_id="stable-id",
        )
        _write_events(runtime_dir, [ev, ev])
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert summary.tickets_created == 1
        assert nudged == ["author-b"]

    def test_pending_tickets_helper(self, runtime_dir: Path) -> None:
        """After one busy cycle, pending_tickets reports the unresolved one."""
        _write_events(
            runtime_dir,
            [
                _msg_sent_event(
                    to_lane="author-b",
                    message_type="blocker",
                    message_id="a",
                ),
                _msg_sent_event(
                    to_lane="author-c",
                    message_type="escalation",
                    message_id="b",
                ),
            ],
        )
        nudged: list[str] = []
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_busy_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        state = AttentionState.from_runtime_dir(runtime_dir)
        pending = pending_tickets(state)
        pending_lanes = {t.to_lane for t in pending}
        assert pending_lanes == {"author-b", "author-c"}
        assert all(t.status == "pending" for t in pending)


class TestTicketPersistence:
    """Ticket state survives crash-restart via append-only jsonl."""

    def test_jsonl_records_each_transition(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        t0 = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_busy_pane,
            nudge_fn=_record_nudge_fn([]),
            now=t0,
        )
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn([]),
            now=t0 + timedelta(seconds=60),
        )
        state = AttentionState.from_runtime_dir(runtime_dir)
        lines = [
            line for line in state.tickets_file.read_text().splitlines() if line.strip()
        ]
        # Three lines: initial (pending), defer, nudge.
        assert len(lines) == 3
        statuses = [json.loads(line)["status"] for line in lines]
        assert statuses == ["pending", "pending", "nudged"]

    def test_load_tickets_uses_last_entry_per_id(self, runtime_dir: Path) -> None:
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        # Simulate two transitions by hand.
        base = {
            "ticket_id": "tkt-1",
            "message_id": "mid-1",
            "to_lane": "author-b",
            "message_type": "blocker",
            "priority": "high",
            "created_at": "2026-04-20T18:00:00+00:00",
            "next_retry_at": "2026-04-20T18:00:00+00:00",
            "last_reason": "new_ticket",
        }
        with open(state.tickets_file, "w") as f:
            f.write(json.dumps({**base, "status": "pending", "attempts": 0}) + "\n")
            f.write(json.dumps({**base, "status": "nudged", "attempts": 1}) + "\n")
        tickets = load_tickets(state)
        assert set(tickets.keys()) == {"tkt-1"}
        assert tickets["tkt-1"].status == "nudged"
        assert tickets["tkt-1"].attempts == 1


class TestStatusSurface:
    """get_status() produces a readable operator snapshot."""

    def test_status_reports_no_broker_on_fresh_tree(self, runtime_dir: Path) -> None:
        status = get_status(runtime_dir=runtime_dir)
        assert status.alive is False
        assert status.pid is None
        assert status.pending_count == 0
        assert status.nudged_count == 0
        assert status.abandoned_count == 0

    def test_status_reports_pending_after_busy_cycle(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_busy_pane,
            nudge_fn=_record_nudge_fn([]),
        )
        status = get_status(runtime_dir=runtime_dir)
        assert status.pending_count == 1
        assert status.nudged_count == 0

    def test_status_reports_nudged_after_safe_cycle(self, runtime_dir: Path) -> None:
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="escalation")],
        )
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn([]),
        )
        status = get_status(runtime_dir=runtime_dir)
        assert status.pending_count == 0
        assert status.nudged_count == 1

    def test_status_last_cycle_round_trips(self, runtime_dir: Path) -> None:
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn([]),
        )
        status = get_status(runtime_dir=runtime_dir)
        assert status.last_cycle is not None
        assert "timestamp" in status.last_cycle
        assert status.last_cycle["nudged"] == 0


class TestCursorTruncation:
    """Safety net when events.jsonl is rotated / truncated."""

    def test_cursor_resets_when_file_shrinks(self, runtime_dir: Path) -> None:
        """If events.jsonl is truncated below the cursor, we restart from 0."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        events_file = runtime_dir / "events" / "events.jsonl"
        events_file.write_text("x" * 10_000)
        write_cursor(state, 9_000)
        # Truncate.
        events_file.write_text("")
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        nudged: list[str] = []
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
        )
        assert nudged == ["author-b"]


class TestDeferredTicketSerialization:
    """Direct round-trip tests for DeferredTicket.to_json / from_json."""

    def test_round_trip(self) -> None:
        ticket = DeferredTicket(
            ticket_id="tkt-abc",
            message_id="mid-1",
            to_lane="author-b",
            message_type="blocker",
            priority="urgent",
            created_at="2026-04-20T18:00:00+00:00",
            next_retry_at="2026-04-20T18:00:10+00:00",
            attempts=1,
            last_reason="deferred:active_work_detected",
            status="pending",
        )
        roundtripped = DeferredTicket.from_json(ticket.to_json())
        assert roundtripped == ticket


# ---------------------------------------------------------------------------
# Compaction — bounded ticket log (issue #2674)
# ---------------------------------------------------------------------------


def _write_ticket_lines(state: AttentionState, tickets: list[DeferredTicket]) -> None:
    """Write a list of tickets as newline-delimited JSON (overwrites)."""
    state.ensure_dir()
    with open(state.tickets_file, "w") as f:
        for ticket in tickets:
            f.write(json.dumps(ticket.to_json(), sort_keys=True) + "\n")


def _make_ticket(
    *,
    ticket_id: str,
    status: str,
    created_at: datetime,
    message_id: str | None = None,
    to_lane: str = "author-b",
    message_type: str = "blocker",
) -> DeferredTicket:
    """Build a DeferredTicket at a specific wall-clock for retention tests."""
    return DeferredTicket(
        ticket_id=ticket_id,
        message_id=message_id or f"mid-{ticket_id}",
        to_lane=to_lane,
        message_type=message_type,
        priority="high",
        created_at=created_at.isoformat(),
        next_retry_at=created_at.isoformat(),
        attempts=1 if status != "pending" else 0,
        last_reason=f"test:{status}",
        status=status,
    )


class TestCompaction:
    """Issue #2674 — bounded growth for deferred_tickets.jsonl."""

    def test_pending_tickets_always_preserved(self, runtime_dir: Path) -> None:
        """Non-terminal tickets must survive compaction unconditionally,
        even when they're far older than the terminal retention window."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        ancient = now - timedelta(days=30)
        tickets = [
            _make_ticket(
                ticket_id="tkt-old-pending", status="pending", created_at=ancient
            ),
            _make_ticket(ticket_id="tkt-new-pending", status="pending", created_at=now),
        ]
        _write_ticket_lines(state, tickets)

        compact_tickets(state, now=now)

        reloaded = load_tickets(state)
        assert set(reloaded.keys()) == {"tkt-old-pending", "tkt-new-pending"}
        assert all(t.status == "pending" for t in reloaded.values())

    def test_terminal_outside_window_is_dropped(self, runtime_dir: Path) -> None:
        """Nudged/abandoned tickets older than retention_hours are removed."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        # 48h ago — outside the default 24h window.
        old = now - timedelta(hours=48)
        tickets = [
            _make_ticket(ticket_id="tkt-old-nudged", status="nudged", created_at=old),
            _make_ticket(
                ticket_id="tkt-old-abandoned", status="abandoned", created_at=old
            ),
            # Recent pending: must be preserved.
            _make_ticket(
                ticket_id="tkt-recent-pending", status="pending", created_at=now
            ),
        ]
        _write_ticket_lines(state, tickets)

        compact_tickets(state, now=now)

        reloaded = load_tickets(state)
        assert "tkt-old-nudged" not in reloaded
        assert "tkt-old-abandoned" not in reloaded
        assert "tkt-recent-pending" in reloaded

    def test_terminal_within_window_is_retained(self, runtime_dir: Path) -> None:
        """Nudged/abandoned tickets inside the window are kept for dedup."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        # 1h ago — inside the default 24h window.
        recent = now - timedelta(hours=1)
        tickets = [
            _make_ticket(
                ticket_id="tkt-recent-nudged",
                status="nudged",
                created_at=recent,
                message_id="mid-recent",
            ),
        ]
        _write_ticket_lines(state, tickets)

        compact_tickets(state, now=now)

        reloaded = load_tickets(state)
        assert "tkt-recent-nudged" in reloaded
        assert reloaded["tkt-recent-nudged"].status == "nudged"
        # Message-id dedup must still see this ticket after compaction.
        seen_message_ids = {t.message_id for t in reloaded.values()}
        assert "mid-recent" in seen_message_ids

    def test_terminal_retention_max_caps_bulk(self, runtime_dir: Path) -> None:
        """With retention_max=10, only the 10 newest terminals survive a
        burst of 50 recent nudged tickets, even though all are in the
        time window."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        base = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)

        # 50 nudged tickets, each 1 minute apart, all within the window.
        terminals = [
            _make_ticket(
                ticket_id=f"tkt-n-{i:02d}",
                status="nudged",
                created_at=base - timedelta(minutes=i),
            )
            for i in range(50)
        ]
        _write_ticket_lines(state, terminals)

        dropped = compact_tickets(state, now=base, retention_max=10)

        reloaded = load_tickets(state)
        assert len(reloaded) == 10
        assert dropped == 40
        # The 10 newest (smallest `i`) should survive.
        surviving = sorted(reloaded.keys())
        assert surviving == [f"tkt-n-{i:02d}" for i in range(10)]

    def test_compaction_deduplicates_transitions(self, runtime_dir: Path) -> None:
        """Multiple JSONL lines for the same ticket_id collapse to one line
        (the latest status) — this is the main space savings in steady state."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        # Simulate the natural ticket lifecycle: pending -> deferred (still
        # pending) x 3 -> nudged.
        base = {
            "ticket_id": "tkt-xforms",
            "message_id": "mid-xforms",
            "to_lane": "author-b",
            "message_type": "blocker",
            "priority": "high",
            "created_at": now.isoformat(),
            "next_retry_at": now.isoformat(),
            "last_reason": "n/a",
        }
        with open(state.tickets_file, "w") as f:
            f.write(json.dumps({**base, "status": "pending", "attempts": 0}) + "\n")
            f.write(json.dumps({**base, "status": "pending", "attempts": 1}) + "\n")
            f.write(json.dumps({**base, "status": "pending", "attempts": 2}) + "\n")
            f.write(json.dumps({**base, "status": "pending", "attempts": 3}) + "\n")
            f.write(json.dumps({**base, "status": "nudged", "attempts": 4}) + "\n")

        assert len(state.tickets_file.read_text().strip().splitlines()) == 5
        dropped = compact_tickets(state, now=now)
        assert dropped == 4
        remaining = state.tickets_file.read_text().strip().splitlines()
        assert len(remaining) == 1
        reloaded = load_tickets(state)
        assert reloaded["tkt-xforms"].status == "nudged"
        assert reloaded["tkt-xforms"].attempts == 4

    def test_dedup_intact_after_compaction(self, runtime_dir: Path) -> None:
        """After compaction, re-running run_once with the same message_id
        in events.jsonl must NOT create a duplicate ticket.

        This is the invariant the retention window exists to preserve:
        terminal tickets retained in the compacted log still block a
        re-nudge for their message_id.
        """
        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)

        # Seed: one nudged ticket within retention window (message_id X).
        seed = _make_ticket(
            ticket_id="tkt-seed",
            status="nudged",
            created_at=now - timedelta(hours=1),
            message_id="stable-X",
        )
        _write_ticket_lines(state, [seed])
        # Matching cursor past the file so run_once never re-reads it.
        compact_tickets(state, now=now)
        # Confirm the dedup anchor survived.
        assert "stable-X" in {t.message_id for t in load_tickets(state).values()}

        # Now append a new event with the *same* message_id and run one cycle.
        _write_events(
            runtime_dir,
            [
                _msg_sent_event(
                    to_lane="author-b",
                    message_type="blocker",
                    message_id="stable-X",
                ),
            ],
        )
        nudged: list[str] = []
        summary = run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn(nudged),
            now=now + timedelta(seconds=5),
        )
        # Dedup worked: no new ticket, no new nudge.
        assert summary.tickets_created == 0
        assert nudged == []

    def test_size_gate_skips_small_files(self, runtime_dir: Path) -> None:
        """run_once must NOT rewrite the file when it's below the size gate."""
        _write_events(
            runtime_dir,
            [_msg_sent_event(to_lane="author-b", message_type="blocker")],
        )
        # Default threshold (50KB) is far larger than a single-ticket file.
        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn([]),
        )
        state = AttentionState.from_runtime_dir(runtime_dir)
        # Initial pending + terminal nudged lines — 2 lines, not 1 (compaction
        # would collapse to 1 if it ran).
        lines = [
            line for line in state.tickets_file.read_text().splitlines() if line.strip()
        ]
        assert len(lines) == 2, (
            "Small files must skip compaction so the per-cycle cost stays "
            "bounded by a single stat() call"
        )

    def test_size_gate_triggers_compaction_on_large_files(
        self,
        runtime_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Force the gate open with a tiny threshold and prove run_once
        actually rewrites the file end-to-end."""
        # Drop the threshold so any non-empty file triggers compaction.
        monkeypatch.setattr("bid_euchre.ops.attention.COMPACTION_MIN_BYTES", 1)

        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)

        # Preload ticket log with redundant transitions.
        base = {
            "ticket_id": "tkt-big",
            "message_id": "mid-big",
            "to_lane": "author-b",
            "message_type": "blocker",
            "priority": "high",
            "created_at": now.isoformat(),
            "next_retry_at": now.isoformat(),
            "last_reason": "n/a",
        }
        state.ensure_dir()
        with open(state.tickets_file, "w") as f:
            for i in range(10):
                f.write(json.dumps({**base, "status": "pending", "attempts": i}) + "\n")
            f.write(json.dumps({**base, "status": "nudged", "attempts": 10}) + "\n")

        run_once(
            runtime_dir=runtime_dir,
            pane_state_fn=_safe_pane,
            nudge_fn=_record_nudge_fn([]),
            now=now,
        )
        # After run_once + compaction, the duplicated transitions collapse
        # to the single terminal state.
        lines = [
            line for line in state.tickets_file.read_text().splitlines() if line.strip()
        ]
        assert len(lines) == 1
        assert json.loads(lines[0])["status"] == "nudged"

    def test_atomic_rewrite_uses_tmp_then_replace(self, runtime_dir: Path) -> None:
        """If os.replace fails mid-write, the live file must still contain
        the pre-compaction content — never a partial write."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        # Seed with a non-trivial set that compaction would shrink.
        old = now - timedelta(hours=48)
        tickets = [
            _make_ticket(ticket_id="tkt-p", status="pending", created_at=now),
            _make_ticket(ticket_id="tkt-old-t", status="nudged", created_at=old),
        ]
        _write_ticket_lines(state, tickets)
        original_bytes = state.tickets_file.read_bytes()

        tmp_path = state.tickets_file.with_suffix(".jsonl.tmp")
        assert not tmp_path.exists()

        with patch(
            f"{_ATTENTION}.os.replace",
            side_effect=OSError("simulated rename failure"),
        ):
            with pytest.raises(OSError, match="simulated rename failure"):
                compact_tickets(state, now=now)

        # Live file must be byte-for-byte the original — atomicity.
        assert state.tickets_file.read_bytes() == original_bytes
        # Tmp file cleaned up on failure.
        assert not tmp_path.exists(), "compaction must clean up tmp on failure"

    def test_atomic_rewrite_calls_fsync_before_replace(self, runtime_dir: Path) -> None:
        """Structural proof: fsync happens before os.replace on the same fd."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        _write_ticket_lines(
            state,
            [_make_ticket(ticket_id="tkt-a", status="pending", created_at=now)],
        )

        call_order: list[str] = []

        real_fsync = os.fsync
        real_replace = os.replace

        def tracked_fsync(fd: int) -> None:
            call_order.append("fsync")
            real_fsync(fd)

        def tracked_replace(src: Any, dst: Any) -> None:
            call_order.append("replace")
            real_replace(src, dst)

        with patch(f"{_ATTENTION}.os.fsync", side_effect=tracked_fsync):
            with patch(f"{_ATTENTION}.os.replace", side_effect=tracked_replace):
                compact_tickets(state, now=now)

        assert call_order == ["fsync", "replace"], (
            "compaction must fsync the tmp file before calling os.replace; "
            f"saw {call_order!r}"
        )

    def test_empty_file_is_noop(self, runtime_dir: Path) -> None:
        """Compaction on a missing / empty log returns zero drops and
        does not create a spurious empty file."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        # File does not exist.
        assert not state.tickets_file.exists()
        dropped = compact_tickets(state)
        assert dropped == 0
        # We did not create an empty file.
        assert not state.tickets_file.exists()

    def test_malformed_lines_are_dropped_on_compaction(self, runtime_dir: Path) -> None:
        """Compaction quietly drops unparseable lines (forward-compat with
        partially-corrupted logs)."""
        state = AttentionState.from_runtime_dir(runtime_dir)
        state.ensure_dir()
        now = datetime(2026, 4, 20, 18, 0, 0, tzinfo=timezone.utc)
        good = _make_ticket(ticket_id="tkt-good", status="pending", created_at=now)
        with open(state.tickets_file, "w") as f:
            f.write("this is not json\n")
            f.write(json.dumps(good.to_json(), sort_keys=True) + "\n")
            f.write('{"missing": "fields"}\n')
        compact_tickets(state, now=now)
        reloaded = load_tickets(state)
        assert set(reloaded.keys()) == {"tkt-good"}

    def test_defaults_are_reasonable(self) -> None:
        """Regression-lock the default compaction policy values.  These
        are the documented knobs operators read from logs; a silent change
        would surprise them."""
        assert (
            COMPACTION_MIN_BYTES >= 1_000
        ), "Threshold too low — would compact on every cycle"
        assert (
            COMPACTION_MIN_BYTES <= 10_000_000
        ), "Threshold too high — would never compact"
        assert COMPACTION_TERMINAL_RETENTION_HOURS >= 1.0
        assert COMPACTION_TERMINAL_RETENTION_MAX >= 50
