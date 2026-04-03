"""Tests for failure classification, recovery templates, and retry/reroute policy (ops/recovery.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.recovery import (
    DEFAULT_MAX_RETRIES,
    PERSISTENT_LANES,
    RECOVERY_TEMPLATES,
    FailureClassification,
    RecoveryTemplate,
    RetryPolicy,
    _resolution_target,
    classify_failure,
    emit_retry_event,
    evaluate_retry_policy,
    format_recovery_json,
    format_recovery_text,
    format_retry_policy_json,
    format_retry_policy_text,
    get_active_failures,
)


class TestRecoveryTemplates:
    """Tests for the RECOVERY_TEMPLATES catalog."""

    def test_all_templates_have_required_fields(self) -> None:
        for key, template in RECOVERY_TEMPLATES.items():
            assert isinstance(
                template, RecoveryTemplate
            ), f"{key} is not RecoveryTemplate"
            assert template.name, f"{key} has empty name"
            assert template.description, f"{key} has empty description"
            assert len(template.steps) > 0, f"{key} has no steps"
            assert isinstance(
                template.auto_remediable, bool
            ), f"{key} auto_remediable not bool"

    def test_expected_templates_exist(self) -> None:
        expected = {
            "ci_failure",
            "task_failed",
            "task_blocked",
            "heartbeat_stale",
            "worktree_quarantined",
            "escalation",
            "auth_failure",
            "review_lane_stall",
        }
        assert expected == set(RECOVERY_TEMPLATES.keys())

    def test_ci_failure_is_auto_remediable(self) -> None:
        assert RECOVERY_TEMPLATES["ci_failure"].auto_remediable is True

    def test_escalation_is_not_auto_remediable(self) -> None:
        assert RECOVERY_TEMPLATES["escalation"].auto_remediable is False


class TestClassifyFailure:
    """Tests for classify_failure()."""

    def test_ci_failure_classification(self) -> None:
        event = {
            "event_type": "ci_failure",
            "lane_id": "author-a",
            "payload": {"details": "ruff check found 2 issues", "target": "PR #900"},
        }
        result = classify_failure(event)
        assert result.failure_type == "ci_failure"
        assert result.severity == "warning"
        assert result.target == "PR #900"
        assert result.details == "ruff check found 2 issues"
        assert result.template is not None
        assert result.template.name == "CI Failure"

    def test_heartbeat_stale_is_critical(self) -> None:
        event = {
            "event_type": "heartbeat_stale",
            "lane_id": "author-b",
            "payload": {"message": "No heartbeat for 10 min"},
        }
        result = classify_failure(event)
        assert result.severity == "critical"
        assert result.template is not None
        assert result.template.name == "Stale Heartbeat"

    def test_escalation_is_critical(self) -> None:
        event = {
            "event_type": "escalation",
            "lane_id": "ops",
            "payload": {"details": "Repeated failures on task X"},
        }
        result = classify_failure(event)
        assert result.severity == "critical"

    def test_unknown_event_type_gets_info_severity(self) -> None:
        event = {
            "event_type": "some_new_type",
            "lane_id": "ops",
            "payload": {"details": "something happened"},
        }
        result = classify_failure(event)
        assert result.severity == "info"
        assert result.template is None

    def test_missing_payload_uses_defaults(self) -> None:
        event = {"event_type": "task_blocked", "lane_id": "author-a"}
        result = classify_failure(event)
        assert result.target == "author-a"  # falls back to lane_id
        assert result.failure_type == "task_blocked"
        assert result.template is not None

    def test_target_from_payload_takes_precedence(self) -> None:
        event = {
            "event_type": "task_failed",
            "lane_id": "author-a",
            "payload": {"target": "task-uuid-123"},
        }
        result = classify_failure(event)
        assert result.target == "task-uuid-123"


class TestResolutionTarget:
    """Tests for _resolution_target()."""

    def test_payload_target_takes_precedence(self) -> None:
        event = {
            "lane_id": "author-a",
            "payload": {"target": "PR #100", "worktree_path": "/tmp/wt"},
        }
        assert _resolution_target(event) == "PR #100"

    def test_worktree_path_used_when_no_target(self) -> None:
        """Worktree events use worktree_path as fallback target (#922)."""
        event = {
            "event_type": "worktree_quarantined",
            "lane_id": "author-a",
            "payload": {"worktree_path": "/tmp/wt-ephemeral"},
        }
        assert _resolution_target(event) == "/tmp/wt-ephemeral"

    def test_lane_id_fallback(self) -> None:
        event = {"lane_id": "ops", "payload": {}}
        assert _resolution_target(event) == "ops"

    def test_unknown_when_nothing_available(self) -> None:
        event = {"payload": {}}
        assert _resolution_target(event) == "unknown"


class TestGetActiveFailures:
    """Tests for get_active_failures()."""

    @pytest.fixture()
    def events_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "events"
        d.mkdir()
        return d

    def test_empty_events(self, events_dir: Path) -> None:
        failures = get_active_failures(events_dir)
        assert failures == []

    def test_filters_failure_events_only(self, events_dir: Path) -> None:
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"details": "lint failed"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:01:00Z",
                    "event_type": "session_started",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:02:00Z",
                    "event_type": "task_blocked",
                    "source": "scheduler",
                    "lane_id": "author-b",
                    "payload": {"details": "missing dependency"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 2
        types = {f.failure_type for f in failures}
        assert types == {"ci_failure", "task_blocked"}

    def test_resolved_failure_excluded(self, events_dir: Path) -> None:
        """ci_failure followed by ci_success for same target → resolved (F6)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"details": "lint failed"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "ci_success",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 0

    def test_newer_failure_after_resolution_still_active(
        self, events_dir: Path
    ) -> None:
        """ci_success then ci_failure (newer) → failure is active (F6)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_success",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"details": "test failed"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 1
        assert failures[0].failure_type == "ci_failure"

    def test_different_target_not_resolved(self, events_dir: Path) -> None:
        """ci_failure(PR#1) + ci_success(PR#2) → failure still active (F6)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"details": "lint failed", "target": "PR #100"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "ci_success",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"target": "PR #200"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 1
        assert failures[0].target == "PR #100"

    def test_task_completed_resolves_task_failed(self, events_dir: Path) -> None:
        """task_completed resolves both task_failed and task_blocked (F6)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "scheduler",
                    "lane_id": "author-a",
                    "payload": {"details": "build error"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:01:00Z",
                    "event_type": "task_blocked",
                    "source": "scheduler",
                    "lane_id": "author-a",
                    "payload": {"details": "blocked by dependency"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "task_completed",
                    "source": "scheduler",
                    "lane_id": "author-a",
                    "payload": {},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 0

    def test_heartbeat_ok_resolves_heartbeat_stale(self, events_dir: Path) -> None:
        """heartbeat_ok resolves heartbeat_stale for same lane (F6)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "heartbeat_stale",
                    "source": "watchdog",
                    "lane_id": "author-b",
                    "payload": {"message": "No heartbeat for 10 min"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "heartbeat_ok",
                    "source": "watchdog",
                    "lane_id": "author-b",
                    "payload": {},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 0

    def test_worktree_resolved_by_path_not_lane(self, events_dir: Path) -> None:
        """worktree_archived resolves quarantine on same path, not same lane (#922)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            # Quarantine on worktree A
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "worktree_quarantined",
                    "source": "ops",
                    "lane_id": "author-a",
                    "payload": {
                        "worktree_path": "/tmp/wt-a",
                        "details": "dirty",
                    },
                }
            ),
            # Quarantine on worktree B (same lane!)
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:01:00Z",
                    "event_type": "worktree_quarantined",
                    "source": "ops",
                    "lane_id": "author-a",
                    "payload": {
                        "worktree_path": "/tmp/wt-b",
                        "details": "stale",
                    },
                }
            ),
            # Archive worktree A only
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "worktree_archived",
                    "source": "ops",
                    "lane_id": "author-a",
                    "payload": {"worktree_path": "/tmp/wt-a"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        # Only worktree B should still be active
        assert len(failures) == 1
        assert failures[0].target == "/tmp/wt-b"

    def test_mixed_resolved_and_unresolved(self, events_dir: Path) -> None:
        """Some failures resolved, others not → only unresolved returned (F6)."""
        events_file = events_dir / "events.jsonl"
        lines = [
            # Old ci_failure — will be resolved
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"details": "lint failed"},
                }
            ),
            # ci_success resolves the ci_failure
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:02:00Z",
                    "event_type": "ci_success",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {},
                }
            ),
            # Unresolved escalation on a different lane
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:03:00Z",
                    "event_type": "escalation",
                    "source": "watchdog",
                    "lane_id": "ops",
                    "payload": {"details": "repeated failures"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 1
        assert failures[0].failure_type == "escalation"

    def test_most_recent_first(self, events_dir: Path) -> None:
        events_file = events_dir / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "a",
                    "payload": {"details": "first"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T11:00:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "b",
                    "payload": {"details": "second"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")

        failures = get_active_failures(events_dir)
        assert len(failures) == 2
        # read_events returns most recent first
        assert failures[0].failure_type == "task_failed"
        assert failures[1].failure_type == "ci_failure"


class TestFormatters:
    """Tests for format_recovery_text() and format_recovery_json()."""

    def test_text_no_failures(self) -> None:
        text = format_recovery_text([])
        assert "All clear" in text
        assert "Recovery Guidance" in text

    def test_text_with_failures(self) -> None:
        failures = [
            FailureClassification(
                failure_type="ci_failure",
                severity="warning",
                target="PR #100",
                details="lint failed",
                template=RECOVERY_TEMPLATES["ci_failure"],
            ),
        ]
        text = format_recovery_text(failures)
        assert "Active failures: 1" in text
        assert "ci_failure" in text
        assert "lint failed" in text
        assert "ruff check" in text  # from template steps

    def test_text_critical_severity_icon(self) -> None:
        failures = [
            FailureClassification(
                failure_type="heartbeat_stale",
                severity="critical",
                target="author-a",
                details="no heartbeat",
                template=RECOVERY_TEMPLATES["heartbeat_stale"],
            ),
        ]
        text = format_recovery_text(failures)
        assert "[!!!]" in text

    def test_json_format(self) -> None:
        failures = [
            FailureClassification(
                failure_type="task_blocked",
                severity="warning",
                target="task-1",
                details="missing dep",
                template=RECOVERY_TEMPLATES["task_blocked"],
            ),
        ]
        data = format_recovery_json(failures)
        assert len(data) == 1
        assert data[0]["failure_type"] == "task_blocked"
        assert data[0]["severity"] == "warning"
        assert data[0]["template"]["name"] == "Task Blocked"
        assert isinstance(data[0]["template"]["steps"], list)

    def test_json_no_template(self) -> None:
        failures = [
            FailureClassification(
                failure_type="unknown",
                severity="info",
                target="?",
                details="something",
                template=None,
            ),
        ]
        data = format_recovery_json(failures)
        assert data[0]["template"] is None


# ---- Phase 3D: Retry/Reroute Policy Tests ----


class TestRetryPolicyConstants:
    """Tests for retry policy constants."""

    def test_default_max_retries(self) -> None:
        assert DEFAULT_MAX_RETRIES == 3

    def test_persistent_lanes_defined(self) -> None:
        assert len(PERSISTENT_LANES) >= 2
        assert "author-a" in PERSISTENT_LANES


class TestEvaluateRetryPolicy:
    """Tests for evaluate_retry_policy()."""

    def test_no_failures_returns_retry(self) -> None:
        policy = evaluate_retry_policy("task-1", [])
        assert policy.action == "retry"
        assert policy.retry_count == 0
        assert policy.reroute_to is None

    def test_below_cap_returns_retry(self) -> None:
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-1", "details": "error 1"},
            },
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-1", "details": "error 2"},
            },
        ]
        policy = evaluate_retry_policy("task-1", events, max_retries=3)
        assert policy.action == "retry"
        assert policy.retry_count == 2

    def test_at_cap_returns_reroute(self) -> None:
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-1", "details": f"error {i}"},
            }
            for i in range(3)
        ]
        policy = evaluate_retry_policy(
            "task-1", events, max_retries=3, current_lane="author-a"
        )
        assert policy.action == "reroute"
        assert policy.retry_count == 3
        assert policy.reroute_to is not None
        assert policy.reroute_to != "author-a"

    def test_above_cap_returns_escalate(self) -> None:
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-1", "details": f"error {i}"},
            }
            for i in range(5)
        ]
        policy = evaluate_retry_policy("task-1", events, max_retries=3)
        assert policy.action == "escalate"
        assert policy.retry_count == 5
        assert policy.reroute_to is None

    def test_ignores_other_task_failures(self) -> None:
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-1", "details": "err"},
            },
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-2", "details": "err"},
            },
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-2", "details": "err"},
            },
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-2", "details": "err"},
            },
        ]
        policy = evaluate_retry_policy("task-1", events, max_retries=3)
        assert policy.action == "retry"
        assert policy.retry_count == 1

    def test_ignores_non_failure_events(self) -> None:
        events = [
            {
                "event_type": "task_completed",
                "lane_id": "author-a",
                "payload": {"task_id": "task-1"},
            },
            {
                "event_type": "ci_success",
                "lane_id": "author-a",
                "payload": {"pr_number": 100},
            },
        ]
        policy = evaluate_retry_policy("task-1", events)
        assert policy.action == "retry"
        assert policy.retry_count == 0

    def test_reroute_avoids_current_lane(self) -> None:
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-b",
                "payload": {"task_id": "t1", "details": "err"},
            }
            for _ in range(3)
        ]
        policy = evaluate_retry_policy(
            "t1", events, max_retries=3, current_lane="author-b"
        )
        assert policy.action == "reroute"
        assert policy.reroute_to is not None
        assert policy.reroute_to != "author-b"

    def test_reasons_populated(self) -> None:
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "t1", "details": "err"},
            }
            for _ in range(3)
        ]
        policy = evaluate_retry_policy("t1", events, max_retries=3)
        assert len(policy.reasons) >= 1
        assert any("retry cap" in r.lower() for r in policy.reasons)

    def test_last_failure_from_most_recent(self) -> None:
        """Most recent failure detail is captured (events are most-recent-first)."""
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "t1", "details": "most recent error"},
            },
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"task_id": "t1", "details": "older error"},
            },
        ]
        policy = evaluate_retry_policy("t1", events)
        assert policy.last_failure == "most recent error"

    def test_uses_target_fallback(self) -> None:
        """Uses 'target' field when 'task_id' is absent."""
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "payload": {"target": "task-x", "details": "boom"},
            }
            for _ in range(3)
        ]
        policy = evaluate_retry_policy("task-x", events, max_retries=3)
        assert policy.retry_count == 3
        assert policy.action == "reroute"


class TestRetryPolicyFormatters:
    """Tests for retry policy format functions."""

    def test_text_format(self) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=2,
            max_retries=3,
            last_failure="lint error",
            action="retry",
            failure_lane="author-a",
            reasons=["Failure count (2) below retry cap (3)"],
        )
        text = format_retry_policy_text(policy)
        assert "Retry/Reroute Policy" in text
        assert "t1" in text
        assert "RETRY" in text
        assert "lint error" in text

    def test_text_format_reroute(self) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=3,
            max_retries=3,
            last_failure="crash",
            action="reroute",
            reroute_to="author-b",
            failure_lane="author-a",
            reasons=["Reached cap"],
        )
        text = format_retry_policy_text(policy)
        assert "REROUTE" in text
        assert "author-b" in text

    def test_json_format(self) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=5,
            max_retries=3,
            last_failure="fatal",
            action="escalate",
            reasons=["Over cap"],
        )
        data = format_retry_policy_json(policy)
        assert data["task_id"] == "t1"
        assert data["action"] == "escalate"
        assert data["retry_count"] == 5
        assert data["reroute_to"] is None


# ---- Retry/Reroute Event Emission (#930) ----


class TestEmitRetryEvent:
    """Tests for emit_retry_event()."""

    @pytest.fixture()
    def events_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "events"
        d.mkdir()
        return d

    def test_retry_emits_retry_attempted(self, events_dir: Path) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=1,
            max_retries=3,
            last_failure="lint error",
            action="retry",
        )
        result = emit_retry_event(policy, "author-a", events_dir)
        assert result is not None
        assert result["event_type"] == "retry_attempted"
        assert result["source"] == "ops.retry"
        assert result["lane_id"] == "author-a"
        assert result["payload"]["task_id"] == "t1"
        assert result["payload"]["retry_count"] == 1

    def test_reroute_emits_task_rerouted(self, events_dir: Path) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=3,
            max_retries=3,
            last_failure="crash",
            action="reroute",
            reroute_to="author-b",
            failure_lane="author-a",
        )
        result = emit_retry_event(policy, "author-a", events_dir)
        assert result is not None
        assert result["event_type"] == "task_rerouted"
        assert result["payload"]["source_lane"] == "author-a"
        assert result["payload"]["target_lane"] == "author-b"

    def test_escalate_emits_escalation(self, events_dir: Path) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=5,
            max_retries=3,
            last_failure="fatal",
            action="escalate",
        )
        result = emit_retry_event(policy, "ops", events_dir)
        assert result is not None
        assert result["event_type"] == "escalation"
        assert "exceeded retry cap" in result["payload"]["details"]

    def test_unknown_action_returns_none(self, events_dir: Path) -> None:
        policy = RetryPolicy(
            task_id="t1",
            retry_count=0,
            max_retries=3,
            last_failure="",
            action="unknown_action",
        )
        result = emit_retry_event(policy, "ops", events_dir)
        assert result is None

    def test_event_persisted_to_jsonl(self, events_dir: Path) -> None:
        """Verify the event is actually written to the events file."""
        from bid_euchre.ops.events import read_events

        policy = RetryPolicy(
            task_id="t1",
            retry_count=2,
            max_retries=3,
            last_failure="test error",
            action="retry",
        )
        emit_retry_event(policy, "author-a", events_dir)

        events = read_events(events_dir)
        assert len(events) == 1
        assert events[0]["event_type"] == "retry_attempted"
        assert events[0]["payload"]["task_id"] == "t1"

    def test_reroute_without_target_omits_lane_fields(self, events_dir: Path) -> None:
        """Reroute with no reroute_to does not add source/target fields."""
        policy = RetryPolicy(
            task_id="t1",
            retry_count=3,
            max_retries=3,
            last_failure="crash",
            action="reroute",
            reroute_to=None,
        )
        result = emit_retry_event(policy, "author-a", events_dir)
        assert result is not None
        assert "source_lane" not in result["payload"]
        assert "target_lane" not in result["payload"]
