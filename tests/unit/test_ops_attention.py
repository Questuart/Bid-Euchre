"""Tests for the PR-MSG-2 delivery-policy helper.

Proves the nudge policy in :mod:`bid_euchre.ops.attention`:

- Low/normal ``progress`` messages: **no nudge**
- ``blocker``: **nudge**
- ``escalation``: **nudge**
- ``supervisor_alert`` at priority ``high``: **nudge**
- ``supervisor_alert`` at priority ``urgent``: **nudge**
- ``supervisor_alert`` at priority ``normal`` / ``low``: **no nudge**
- ``send_message`` failure: **no nudge attempted**

The architectural invariant is that ``send_with_attention`` wraps (not
replaces) ``send_message``, so all durability guarantees still hold and
no tmux coupling leaks into the bus layer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bid_euchre.ops.attention import send_with_attention, should_nudge_for_message
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
