"""Unit tests for ``bid_euchre.ops.event_taxonomy``.

Covers:

- :func:`categorize_error` — taxonomy coverage for all five buckets,
  priority ordering, null/empty input handling.
- :func:`build_status_message` — specialized formatters per event type,
  generic fallback, no-newline invariant, defensive behavior.
- :func:`incident_fingerprint` — determinism, normalization, null-input
  ``None`` return, extra-kwargs order independence.

Per shaping §6.2: taxonomy helpers must be demonstrable before Packet 3
closes; this test file is the verification surface.
"""

from __future__ import annotations

import pytest

from bid_euchre.ops import event_taxonomy as et

# ---------------------------------------------------------------------------
# categorize_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_str,expected",
    [
        ("KeyboardInterrupt", "interrupted"),
        ("received SIGINT", "interrupted"),
        ("aborted by user", "interrupted"),
        ("Ctrl-C pressed", "interrupted"),
        ("Operation timed out after 30s", "timeout"),
        ("deadline exceeded", "timeout"),
        ("task timeout", "timeout"),
        ("Permission denied: /etc/shadow", "permission_denied"),
        ("EACCES", "permission_denied"),
        ("EPERM", "permission_denied"),
        ("forbidden endpoint", "permission_denied"),
        ("Access denied", "permission_denied"),
        ("unauthorized request", "permission_denied"),
        ("Traceback (most recent call last)", "execution_error"),
        ("ValueError: bad x", "execution_error"),
        ("exited with non-zero status", "execution_error"),
        ("Exception in thread", "execution_error"),
        ("Something unknown happened", "other"),
        ("", "other"),
    ],
)
def test_categorize_error_mapping(error_str: str, expected: str) -> None:
    assert et.categorize_error(error_str) == expected


def test_categorize_error_none_is_other() -> None:
    assert et.categorize_error(None) == "other"


def test_categorize_error_interrupted_beats_execution_error() -> None:
    """'KeyboardInterrupt' contains 'error' in a traceback; interrupted wins."""
    msg = "Traceback...\nKeyboardInterrupt"
    assert et.categorize_error(msg) == "interrupted"


def test_categorize_error_timeout_beats_execution_error() -> None:
    """'timed out' wins over generic 'error' text."""
    msg = "Error: operation timed out after 30s"
    assert et.categorize_error(msg) == "timeout"


def test_categorize_error_permission_denied_beats_execution_error() -> None:
    msg = "OSError: Permission denied"
    assert et.categorize_error(msg) == "permission_denied"


def test_error_categories_is_closed_vocabulary() -> None:
    assert et.ERROR_CATEGORIES == (
        "interrupted",
        "timeout",
        "permission_denied",
        "execution_error",
        "other",
    )


def test_categorize_error_output_is_always_in_closed_vocab() -> None:
    samples = [
        "KeyboardInterrupt",
        "timed out",
        "Permission denied",
        "ValueError: x",
        "foo bar baz",
        "",
        None,
    ]
    for s in samples:
        assert et.categorize_error(s) in et.ERROR_CATEGORIES


def test_categorize_error_exported_private_alias_exists() -> None:
    """Shaping §3.6 specifies the exact internal name `_categorize_error`."""
    assert et._categorize_error is et.categorize_error


# ---------------------------------------------------------------------------
# build_status_message — specialized formatters
# ---------------------------------------------------------------------------


def test_status_message_task_started() -> None:
    msg = et.build_status_message(
        {
            "event_type": "task_started",
            "packet_id": "abc123def456",
            "title": "Implement feature X",
            "dispatched_by": "orchestrator",
        }
    )
    assert "abc123def456" in msg
    assert "Implement feature X" in msg
    assert "orchestrator" in msg


def test_status_message_task_completed_with_pr() -> None:
    msg = et.build_status_message(
        {
            "event_type": "task_completed",
            "packet_id": "xyz789",
            "outcome": "success",
            "pr_number": 9999,
        }
    )
    assert "xyz789" in msg
    assert "success" in msg
    assert "9999" in msg


def test_status_message_task_completed_without_pr() -> None:
    msg = et.build_status_message(
        {
            "event_type": "task_completed",
            "packet_id": "xyz789",
            "outcome": "failed",
        }
    )
    assert "xyz789" in msg
    assert "failed" in msg
    assert "PR" not in msg


def test_status_message_post_tool_use_failure() -> None:
    msg = et.build_status_message(
        {
            "event_type": "post_tool_use_failure",
            "tool_name": "Bash",
            "error_category": "timeout",
        }
    )
    assert "Bash" in msg
    assert "timeout" in msg


def test_status_message_stop_failure() -> None:
    msg = et.build_status_message(
        {
            "event_type": "stop_failure",
            "failure_category": "permission_denied",
        }
    )
    assert "permission_denied" in msg


def test_status_message_canary_run_complete() -> None:
    msg = et.build_status_message(
        {
            "event_type": "canary_run_complete",
            "canary_run_id": "r-001",
            "scenarios_passed": 8,
            "scenarios_total": 10,
        }
    )
    assert "r-001" in msg
    assert "8/10" in msg


def test_status_message_canary_run_fail() -> None:
    msg = et.build_status_message(
        {
            "event_type": "canary_run_fail",
            "canary_run_id": "r-002",
            "scenarios_failed": 3,
        }
    )
    assert "FAILED" in msg
    assert "r-002" in msg
    assert "3" in msg


def test_status_message_notification_with_severity() -> None:
    msg = et.build_status_message(
        {
            "event_type": "notification",
            "severity": "error",
            "message": "Lane author-a timed out during /start-task",
        }
    )
    assert "[error]" in msg
    assert "author-a" in msg


def test_status_message_promotion_start_and_complete() -> None:
    s = et.build_status_message(
        {"event_type": "promotion_start", "surface_id": "primitive-a"}
    )
    assert "Promotion started" in s
    assert "primitive-a" in s
    c = et.build_status_message(
        {"event_type": "promotion_complete", "surface_id": "primitive-a"}
    )
    assert "Promotion complete" in c


def test_status_message_rollback_triggered() -> None:
    msg = et.build_status_message(
        {
            "event_type": "rollback_triggered",
            "surface_id": "review_driver",
            "reason": "precheck regression",
        }
    )
    assert "Rollback" in msg
    assert "review_driver" in msg
    assert "precheck regression" in msg


def test_status_message_generic_fallback() -> None:
    msg = et.build_status_message(
        {"event_type": "unregistered_event", "lane_id": "author-a"}
    )
    assert "unregistered_event" in msg
    assert "author-a" in msg


def test_status_message_empty_event_type() -> None:
    # No event_type → fallback; should not crash
    msg = et.build_status_message({"lane_id": "author-a"})
    assert "author-a" in msg


def test_status_message_always_single_line() -> None:
    """Embedded newlines must be stripped per shaping §3.7 one-line contract."""
    msg = et.build_status_message(
        {
            "event_type": "notification",
            "severity": "info",
            "message": "multi\nline\nmessage",
        }
    )
    assert "\n" not in msg


def test_status_message_defensive_on_missing_fields() -> None:
    """Formatter receives partial record; must not raise."""
    # task_started with no packet_id, no title, no dispatched_by
    msg = et.build_status_message({"event_type": "task_started"})
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_status_message_long_title_truncated() -> None:
    long_title = "x" * 200
    msg = et.build_status_message(
        {
            "event_type": "task_started",
            "packet_id": "abc",
            "title": long_title,
        }
    )
    # Ellipsis inserted at ~80 chars
    assert "…" in msg


def test_status_message_exported_private_alias_exists() -> None:
    """Shaping §3.7 specifies exact internal name `_build_status_message`."""
    assert et._build_status_message is et.build_status_message


# ---------------------------------------------------------------------------
# incident_fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_none_for_empty_inputs() -> None:
    assert et.incident_fingerprint() is None
    assert (
        et.incident_fingerprint(event_type=None, error_category=None, signature=None)
        is None
    )
    assert (
        et.incident_fingerprint(event_type="", error_category="", signature="") is None
    )


def test_fingerprint_deterministic_for_same_input() -> None:
    a = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="Operation timed out after 30s",
    )
    b = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="Operation timed out after 30s",
    )
    assert a == b


def test_fingerprint_normalization_collapses_whitespace() -> None:
    a = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="Operation timed out after 30s",
    )
    b = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="  Operation   timed out    after 30s  ",
    )
    assert a == b


def test_fingerprint_normalization_masks_absolute_paths() -> None:
    a = et.incident_fingerprint(
        event_type="post_tool_use_failure",
        error_category="execution_error",
        signature="Error reading /tmp/pytest-of-alice/worktree-123/foo.py",
    )
    b = et.incident_fingerprint(
        event_type="post_tool_use_failure",
        error_category="execution_error",
        signature="Error reading /tmp/pytest-of-bob/worktree-999/foo.py",
    )
    assert a == b  # Different paths hash to same fingerprint


def test_fingerprint_differs_on_different_signature() -> None:
    a = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="A timed out",
    )
    b = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="B timed out",
    )
    assert a != b


def test_fingerprint_differs_on_different_category() -> None:
    a = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="x",
    )
    b = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="execution_error",
        signature="x",
    )
    assert a != b


def test_fingerprint_extra_fields_order_independent() -> None:
    a = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="x",
        tool_name="Bash",
        lane_id="author-a",
    )
    b = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="x",
        lane_id="author-a",
        tool_name="Bash",
    )
    assert a == b


def test_fingerprint_extra_fields_affect_hash() -> None:
    a = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="x",
        tool_name="Bash",
    )
    b = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="x",
        tool_name="Edit",
    )
    assert a != b


def test_fingerprint_is_16_hex_chars() -> None:
    fp = et.incident_fingerprint(
        event_type="stop_failure",
        error_category="timeout",
        signature="x",
    )
    assert fp is not None
    assert len(fp) == 16
    int(fp, 16)  # must be valid hex


def test_fingerprint_only_extra_still_produces_hash() -> None:
    """Rare case: no principal inputs but extra kwargs present."""
    fp = et.incident_fingerprint(lane_id="author-a")
    assert fp is not None
    assert len(fp) == 16
