"""Tests for failure classification and recovery templates (ops/recovery.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.recovery import (
    RECOVERY_TEMPLATES,
    FailureClassification,
    RecoveryTemplate,
    classify_failure,
    format_recovery_json,
    format_recovery_text,
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
                    "event_type": "ci_success",
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
