"""Unit tests for the inbox-completion-inject UserPromptSubmit hook.

Tests the Python script directly (imported by path) with mocked message bus
functions.  The hook reads the orchestrator inbox for unacked completion
messages and injects them as additionalContext.

Closes #1986.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PY = REPO_ROOT / ".claude" / "hooks" / "inbox-completion-inject.py"
HOOK_SH = REPO_ROOT / ".claude" / "hooks" / "inbox-completion-inject.sh"


@pytest.fixture(scope="module")
def hook() -> ModuleType:
    """Import the hook script as a module."""
    spec = importlib.util.spec_from_file_location("inbox_completion_inject", HOOK_PY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["inbox_completion_inject"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completion_msg(
    *,
    from_lane: str = "author-a",
    summary: str = "Done: PR #100 opened",
    task_id: str = "abc123def456",
    message_id: str = "msg001",
    status: str = "delivered",
) -> dict:
    """Create a minimal completion message dict as returned by read_inbox."""
    return {
        "message_id": message_id,
        "from_lane": from_lane,
        "to_lane": "orchestrator",
        "message_type": "completion",
        "summary": summary,
        "task_id": task_id,
        "status": status,
        "priority": "normal",
        "created_at": "2026-04-01T12:00:00Z",
    }


def _make_msg(
    message_type: str,
    *,
    from_lane: str = "author-a",
    summary: str = "(generic summary)",
    task_id: str = "abc123def456",
    message_id: str = "msg001",
    status: str = "delivered",
    priority: str = "normal",
) -> dict:
    """Create a generic inbox message dict for arbitrary types/priorities."""
    return {
        "message_id": message_id,
        "from_lane": from_lane,
        "to_lane": "orchestrator",
        "message_type": message_type,
        "summary": summary,
        "task_id": task_id,
        "status": status,
        "priority": priority,
        "created_at": "2026-04-01T12:00:00Z",
    }


def _mock_read_delivered(msgs: list[dict]):
    """Return a ``read_inbox`` side_effect that emits *msgs* for delivered only."""

    def _side_effect(*a, **kw):
        return msgs if kw.get("status") == "delivered" else []

    return _side_effect


# ---------------------------------------------------------------------------
# Tests: no output cases
# ---------------------------------------------------------------------------


class TestNoOutput:
    """Cases where the hook should produce no output and exit 0."""

    def test_no_completions(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook exits cleanly when no unacked completions exist."""
        mock_read = MagicMock(return_value=[])
        mock_ack = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "bid_euchre.ops.message_bus": MagicMock(
                    read_inbox=mock_read, ack_message=mock_ack
                ),
            },
        ):
            # Re-import to pick up the mock
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""

    def test_import_error_graceful(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook exits cleanly if bid_euchre.ops.message_bus can't be imported."""
        # Setting a sys.modules entry to None causes ImportError on `from ... import`
        with patch.dict("sys.modules", {"bid_euchre.ops.message_bus": None}):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""


class TestCompletionInjection:
    """Cases where the hook should inject additionalContext."""

    def test_single_completion(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook injects context for a single completion message."""
        msgs = [_make_completion_msg()]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["additionalContext"]
        assert "LANE COMPLETIONS (1 unacked)" in ctx
        assert "[author-a] Done: PR #100 opened" in ctx
        assert "[task:abc123def456]" in ctx

    def test_multiple_completions(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook injects all unacked completions."""
        msgs = [
            _make_completion_msg(
                from_lane="author-a",
                summary="Done: PR #100 opened",
                message_id="msg001",
            ),
            _make_completion_msg(
                from_lane="author-b",
                summary="Done: PR #101 opened",
                message_id="msg002",
                task_id="def789ghi012",
            ),
        ]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["additionalContext"]
        assert "LANE COMPLETIONS (2 unacked)" in ctx
        assert "[author-a]" in ctx
        assert "[author-b]" in ctx
        assert "PR #100" in ctx
        assert "PR #101" in ctx

    def test_auto_acks_injected_messages(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook auto-acks messages after injecting them."""
        msgs = [
            _make_completion_msg(message_id="msg001"),
            _make_completion_msg(message_id="msg002", from_lane="author-b"),
        ]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        # Verify both messages were acked
        assert mock_ack.call_count == 2
        acked_ids = {call.args[0] for call in mock_ack.call_args_list}
        assert acked_ids == {"msg001", "msg002"}
        # All acks should target the orchestrator lane
        for call in mock_ack.call_args_list:
            assert call.args[1] == "orchestrator"

    def test_ack_failure_does_not_block(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook still outputs context even if ack_message raises."""
        msgs = [_make_completion_msg(message_id="msg001")]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch(
                "bid_euchre.ops.message_bus.ack_message",
                side_effect=Exception("ack failed"),
            ),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        # Should still output the context despite ack failure
        output = json.loads(captured.out)
        assert "LANE COMPLETIONS" in output["additionalContext"]

    def test_no_task_id_omits_suffix(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook omits [task:...] suffix when task_id is empty."""
        msgs = [_make_completion_msg(task_id="")]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["additionalContext"]
        assert "[task:" not in ctx

    def test_pending_status_also_captured(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook captures messages in both 'delivered' and 'pending' states."""
        delivered_msgs = [_make_completion_msg(message_id="msg001", status="delivered")]
        pending_msgs = [
            _make_completion_msg(
                message_id="msg002",
                from_lane="author-c",
                summary="Done: PR #102 opened",
                status="pending",
            )
        ]

        def mock_read(*a, **kw):
            if kw.get("status") == "delivered":
                return delivered_msgs
            elif kw.get("status") == "pending":
                return pending_msgs
            return []

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=mock_read,
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["additionalContext"]
        assert "LANE COMPLETIONS (2 unacked)" in ctx
        assert "[author-a]" in ctx
        assert "[author-c]" in ctx

    def test_output_is_valid_json(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook output is always valid JSON when completions exist."""
        msgs = [_make_completion_msg(summary='Done: PR #100 with "quotes" & specials')]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output, dict)
        assert "additionalContext" in output
        assert isinstance(output["additionalContext"], str)

    def test_dispatch_hint_in_context(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Hook includes a hint to review PRs and dispatch new work."""
        msgs = [_make_completion_msg()]

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=lambda *a, **kw: msgs
                if kw.get("status") == "delivered"
                else [],
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            result = hook.main()

        assert result == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        ctx = output["additionalContext"]
        assert "reviewing their PRs" in ctx or "dispatch" in ctx.lower()


# ---------------------------------------------------------------------------
# Tests: broadened selection + conditional ack (PR-MSG-3)
# ---------------------------------------------------------------------------


class TestBroadenedSelectionAndAck:
    """Ensure blockers / escalations / high+urgent alerts surface but stay unacked.

    The critical invariant of PR-MSG-3 is that auto-ack is scoped to
    ``completion`` only.  Auto-acking a blocker or escalation would silently
    drop an action item that still needs orchestrator attention.
    """

    # -- blocker -----------------------------------------------------------

    def test_blocker_surfaces_but_not_acked(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        msg = _make_msg(
            "blocker",
            from_lane="author-c",
            summary="Blocked: rebase conflict on foo.py",
            message_id="blk001",
            priority="high",
        )
        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([msg]),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        output = json.loads(capsys.readouterr().out)
        ctx = output["additionalContext"]
        assert "BLOCKERS (1 unacked)" in ctx
        assert "[author-c]" in ctx
        assert "rebase conflict on foo.py" in ctx
        # CRITICAL: blockers must never be auto-acked.
        mock_ack.assert_not_called()

    # -- escalation --------------------------------------------------------

    def test_escalation_surfaces_but_not_acked(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        msg = _make_msg(
            "escalation",
            from_lane="monitor",
            summary="Stale blocker: author-d has been idle >30m",
            message_id="esc001",
            priority="urgent",
        )
        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([msg]),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        output = json.loads(capsys.readouterr().out)
        ctx = output["additionalContext"]
        assert "ESCALATIONS (1 unacked)" in ctx
        assert "Stale blocker" in ctx
        # CRITICAL: escalations must never be auto-acked.
        mock_ack.assert_not_called()

    # -- supervisor_alert priority gating ---------------------------------

    def test_urgent_supervisor_alert_surfaces_but_not_acked(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        msg = _make_msg(
            "supervisor_alert",
            from_lane="ops",
            summary="Away-mode triggered: operator unreachable",
            message_id="alrt001",
            priority="urgent",
        )
        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([msg]),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        output = json.loads(capsys.readouterr().out)
        ctx = output["additionalContext"]
        assert "URGENT ALERTS (1 unacked)" in ctx
        assert "<urgent>" in ctx
        assert "operator unreachable" in ctx
        # CRITICAL: urgent alerts must never be auto-acked.
        mock_ack.assert_not_called()

    def test_high_supervisor_alert_surfaces_but_not_acked(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        msg = _make_msg(
            "supervisor_alert",
            from_lane="ops",
            summary="Permission stall risk: author-b waiting 5m",
            message_id="alrt002",
            priority="high",
        )
        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([msg]),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        output = json.loads(capsys.readouterr().out)
        ctx = output["additionalContext"]
        assert "URGENT ALERTS (1 unacked)" in ctx
        assert "<high>" in ctx
        # CRITICAL: high-priority alerts must never be auto-acked.
        mock_ack.assert_not_called()

    def test_normal_priority_supervisor_alert_is_not_surfaced(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Normal/low-priority supervisor_alerts do NOT bubble up to the prompt.

        They belong to cron-batch processing, not prompt-boundary interrupts.
        """
        msg = _make_msg(
            "supervisor_alert",
            from_lane="ops",
            summary="Nightly heartbeat: fleet idle",
            message_id="alrt003",
            priority="normal",
        )
        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([msg]),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        # Silent exit when only low-priority alerts are present.
        assert capsys.readouterr().out.strip() == ""
        mock_ack.assert_not_called()

    def test_low_priority_supervisor_alert_is_not_surfaced(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        msg = _make_msg(
            "supervisor_alert",
            summary="FYI heartbeat",
            message_id="alrt004",
            priority="low",
        )
        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([msg]),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        assert capsys.readouterr().out.strip() == ""
        mock_ack.assert_not_called()

    # -- mixed inbox -------------------------------------------------------

    def test_mixed_inbox_only_completions_are_acked(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """All four types surface, but only completion IDs pass to ack_message.

        This is the single most important regression guard for PR-MSG-3.
        """
        completion = _make_completion_msg(message_id="cmp001")
        blocker = _make_msg(
            "blocker",
            from_lane="author-b",
            summary="Blocked: schema mismatch",
            message_id="blk002",
            priority="high",
        )
        escalation = _make_msg(
            "escalation",
            from_lane="monitor",
            summary="Escalation: lane idle 45m",
            message_id="esc002",
            priority="urgent",
        )
        urgent_alert = _make_msg(
            "supervisor_alert",
            from_lane="ops",
            summary="Fleet CPU > 95%",
            message_id="alrt005",
            priority="urgent",
        )
        # A normal-priority supervisor_alert should be filtered out entirely.
        normal_alert = _make_msg(
            "supervisor_alert",
            from_lane="ops",
            summary="Heartbeat",
            message_id="alrt006",
            priority="normal",
        )

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered(
                    [completion, blocker, escalation, urgent_alert, normal_alert]
                ),
            ),
            patch("bid_euchre.ops.message_bus.ack_message") as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        ctx = json.loads(capsys.readouterr().out)["additionalContext"]

        # All four actionable sections appear.
        assert "ESCALATIONS (1 unacked)" in ctx
        assert "BLOCKERS (1 unacked)" in ctx
        assert "URGENT ALERTS (1 unacked)" in ctx
        assert "LANE COMPLETIONS (1 unacked)" in ctx
        # The normal-priority supervisor_alert must NOT appear.
        assert "Heartbeat" not in ctx

        # Exactly one ack call, and it targets the completion message.
        assert mock_ack.call_count == 1
        acked_ids = {call.args[0] for call in mock_ack.call_args_list}
        assert acked_ids == {"cmp001"}

    def test_section_ordering_most_urgent_first(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """Escalations appear before blockers, alerts, and completions."""
        completion = _make_completion_msg(message_id="cmp010")
        blocker = _make_msg(
            "blocker",
            from_lane="author-b",
            summary="Blocked: conflict",
            message_id="blk010",
        )
        escalation = _make_msg(
            "escalation",
            from_lane="monitor",
            summary="Escalation: stuck lane",
            message_id="esc010",
        )
        urgent_alert = _make_msg(
            "supervisor_alert",
            summary="Fleet alert",
            message_id="alrt010",
            priority="urgent",
        )

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered(
                    [completion, blocker, escalation, urgent_alert]
                ),
            ),
            patch("bid_euchre.ops.message_bus.ack_message"),
        ):
            hook.main()

        ctx = json.loads(capsys.readouterr().out)["additionalContext"]

        # Verify section ordering: ESCALATIONS < BLOCKERS < URGENT ALERTS < LANE COMPLETIONS.
        i_esc = ctx.index("ESCALATIONS")
        i_blk = ctx.index("BLOCKERS")
        i_alrt = ctx.index("URGENT ALERTS")
        i_cmp = ctx.index("LANE COMPLETIONS")
        assert i_esc < i_blk < i_alrt < i_cmp

    def test_ack_exception_does_not_surface_error(
        self, hook: ModuleType, capsys: pytest.CaptureFixture
    ) -> None:
        """If ack_message raises for a completion, the hook still succeeds
        and non-completion action items remain unacked (obviously)."""
        completion = _make_completion_msg(message_id="cmp020")
        blocker = _make_msg(
            "blocker",
            summary="Blocked: test",
            message_id="blk020",
        )

        with (
            patch(
                "bid_euchre.ops.message_bus.read_inbox",
                side_effect=_mock_read_delivered([completion, blocker]),
            ),
            patch(
                "bid_euchre.ops.message_bus.ack_message",
                side_effect=Exception("bus write failed"),
            ) as mock_ack,
        ):
            result = hook.main()

        assert result == 0
        ctx = json.loads(capsys.readouterr().out)["additionalContext"]
        assert "LANE COMPLETIONS" in ctx
        assert "BLOCKERS" in ctx
        # Only the completion's ack was attempted — blocker never reached ack.
        assert mock_ack.call_count == 1
        assert mock_ack.call_args.args[0] == "cmp020"


# ---------------------------------------------------------------------------
# Tests: shell wrapper selection heuristic
# ---------------------------------------------------------------------------


class TestShellWrapperHeuristic:
    """Verify the wrapper's fast-guard grep recognizes the broadened type set."""

    def test_shell_wrapper_greps_all_actionable_types(self) -> None:
        contents = HOOK_SH.read_text()
        # The widened selection must be reflected in the wrapper's fast guard
        # so non-completion types actually reach the Python delegate.
        assert "completion" in contents
        assert "blocker" in contents
        assert "escalation" in contents
        assert "supervisor_alert" in contents


# ---------------------------------------------------------------------------
# Tests: hook infrastructure
# ---------------------------------------------------------------------------


class TestHookInfrastructure:
    """Verify hook files exist and are properly configured."""

    def test_python_script_exists(self) -> None:
        assert HOOK_PY.exists(), f"Missing {HOOK_PY}"

    def test_shell_wrapper_exists(self) -> None:
        assert HOOK_SH.exists(), f"Missing {HOOK_SH}"

    def test_shell_wrapper_executable(self) -> None:
        import os
        import stat

        mode = os.stat(HOOK_SH).st_mode
        assert mode & stat.S_IXUSR, f"{HOOK_SH} is not executable"

    def test_hook_registered_in_settings(self) -> None:
        settings_path = REPO_ROOT / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {})
        user_prompt = hooks.get("UserPromptSubmit", [])
        assert len(user_prompt) > 0, "No UserPromptSubmit hooks registered"

        # Find our hook
        found = False
        for entry in user_prompt:
            for hook_entry in entry.get("hooks", []):
                if "inbox-completion-inject" in hook_entry.get("command", ""):
                    found = True
                    assert hook_entry["timeout"] <= 10, "Hook timeout must be <= 10s"
        assert found, "inbox-completion-inject hook not found in UserPromptSubmit"
