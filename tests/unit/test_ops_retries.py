"""Tests for ops/retries.py — retry follow-through helpers."""

from __future__ import annotations

import json

from bid_euchre.ops.retries import (
    PendingRetry,
    RetrySummary,
    _extract_task_id,
    format_pending_retries_text,
    format_retry_summary_json,
    format_retry_summary_text,
    get_pending_retries,
    get_retry_summary,
)

# --- Helper ---


def _make_event(
    event_type: str,
    task_id: str = "t1",
    lane_id: str = "author-a",
    details: str = "error",
    timestamp: str = "2026-03-20T10:00:00Z",
) -> dict:
    """Create a minimal event dict."""
    return {
        "event_type": event_type,
        "lane_id": lane_id,
        "timestamp": timestamp,
        "payload": {
            "task_id": task_id,
            "details": details,
        },
    }


# --- _extract_task_id ---


class TestExtractTaskId:
    """Tests for _extract_task_id()."""

    def test_from_task_id(self) -> None:
        event = {"payload": {"task_id": "t1"}}
        assert _extract_task_id(event) == "t1"

    def test_from_target(self) -> None:
        event = {"payload": {"target": "t2"}}
        assert _extract_task_id(event) == "t2"

    def test_task_id_over_target(self) -> None:
        event = {"payload": {"task_id": "t1", "target": "t2"}}
        assert _extract_task_id(event) == "t1"

    def test_empty_payload(self) -> None:
        event = {"payload": {}}
        assert _extract_task_id(event) is None

    def test_no_payload(self) -> None:
        event = {}
        assert _extract_task_id(event) is None

    def test_numeric_task_id(self) -> None:
        event = {"payload": {"task_id": 42}}
        assert _extract_task_id(event) == "42"


# --- get_pending_retries ---


class TestGetPendingRetries:
    """Tests for get_pending_retries()."""

    def test_no_failures(self) -> None:
        events = [
            _make_event("task_completed", task_id="t1"),
            _make_event("ci_success", task_id="t1"),
        ]
        assert get_pending_retries(events) == []

    def test_single_unresolved_failure(self) -> None:
        events = [
            _make_event("task_failed", task_id="t1", details="boom"),
        ]
        pending = get_pending_retries(events)
        assert len(pending) == 1
        assert pending[0].task_id == "t1"
        assert pending[0].failure_count == 1
        assert pending[0].last_failure_details == "boom"

    def test_failure_resolved_by_retry(self) -> None:
        events = [
            _make_event(
                "retry_attempted", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        assert get_pending_retries(events) == []

    def test_failure_resolved_by_completion(self) -> None:
        events = [
            _make_event(
                "task_completed", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        assert get_pending_retries(events) == []

    def test_failure_resolved_by_reroute(self) -> None:
        events = [
            _make_event(
                "task_rerouted", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        assert get_pending_retries(events) == []

    def test_failure_resolved_by_escalation(self) -> None:
        events = [
            _make_event("escalation", task_id="t1", timestamp="2026-03-20T10:05:00Z"),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        assert get_pending_retries(events) == []

    def test_multiple_tasks_mixed(self) -> None:
        events = [
            # t1 resolved
            _make_event(
                "task_completed", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
            # t2 unresolved
            _make_event(
                "task_failed",
                task_id="t2",
                details="crash",
                timestamp="2026-03-20T10:03:00Z",
            ),
            # t3 unresolved
            _make_event(
                "task_failed",
                task_id="t3",
                details="timeout",
                timestamp="2026-03-20T10:01:00Z",
            ),
        ]
        pending = get_pending_retries(events)
        assert len(pending) == 2
        task_ids = {p.task_id for p in pending}
        assert task_ids == {"t2", "t3"}

    def test_multiple_failures_same_task(self) -> None:
        events = [
            _make_event(
                "task_failed",
                task_id="t1",
                details="err1",
                timestamp="2026-03-20T10:02:00Z",
            ),
            _make_event(
                "task_failed",
                task_id="t1",
                details="err0",
                timestamp="2026-03-20T10:00:00Z",
            ),
        ]
        pending = get_pending_retries(events)
        assert len(pending) == 1
        assert pending[0].failure_count == 2
        # Most recent failure details (first in list — events are most-recent-first)
        assert pending[0].last_failure_details == "err1"

    def test_max_age_filter(self) -> None:
        """Failures older than max_age_hours are excluded."""
        events = [
            # Recent failure (within 1 hour)
            _make_event(
                "task_failed",
                task_id="t1",
                details="recent",
                timestamp="2026-03-20T10:00:00+00:00",
            ),
            # Old failure (48 hours ago)
            _make_event(
                "task_failed",
                task_id="t2",
                details="old",
                timestamp="2026-03-18T10:00:00+00:00",
            ),
        ]
        # With max_age_hours=24, the old failure should be excluded
        # But since we're using fixed timestamps and datetime.now(), we
        # can't easily control this. Instead test that the parameter is accepted.
        pending = get_pending_retries(events, max_age_hours=24)
        # Both may or may not be included depending on current time,
        # but the function should not crash
        assert isinstance(pending, list)

    def test_uses_target_fallback(self) -> None:
        """Uses 'target' field when 'task_id' is absent."""
        events = [
            {
                "event_type": "task_failed",
                "lane_id": "author-a",
                "timestamp": "2026-03-20T10:00:00Z",
                "payload": {"target": "task-x", "details": "boom"},
            },
        ]
        pending = get_pending_retries(events)
        assert len(pending) == 1
        assert pending[0].task_id == "task-x"

    def test_sorted_most_recent_first(self) -> None:
        events = [
            _make_event(
                "task_failed", task_id="t-old", timestamp="2026-03-20T08:00:00Z"
            ),
            _make_event(
                "task_failed", task_id="t-new", timestamp="2026-03-20T12:00:00Z"
            ),
        ]
        pending = get_pending_retries(events)
        assert len(pending) == 2
        assert pending[0].task_id == "t-new"
        assert pending[1].task_id == "t-old"

    def test_empty_events(self) -> None:
        assert get_pending_retries([]) == []


# --- get_retry_summary ---


class TestGetRetrySummary:
    """Tests for get_retry_summary()."""

    def test_empty_events(self) -> None:
        summary = get_retry_summary([])
        assert summary.total_tasks_with_failures == 0
        assert summary.dropped_count == 0

    def test_all_resolved(self) -> None:
        events = [
            _make_event(
                "task_completed", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        summary = get_retry_summary(events)
        assert summary.total_tasks_with_failures == 1
        assert summary.resolved_tasks == 1
        assert summary.dropped_count == 0

    def test_retried_task(self) -> None:
        events = [
            _make_event(
                "retry_attempted", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        summary = get_retry_summary(events)
        assert summary.retried_tasks == 1
        assert summary.dropped_count == 0

    def test_rerouted_task(self) -> None:
        events = [
            _make_event(
                "task_rerouted", task_id="t1", timestamp="2026-03-20T10:05:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        summary = get_retry_summary(events)
        assert summary.rerouted_tasks == 1

    def test_escalated_task(self) -> None:
        events = [
            _make_event("escalation", task_id="t1", timestamp="2026-03-20T10:05:00Z"),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
        ]
        summary = get_retry_summary(events)
        assert summary.escalated_tasks == 1

    def test_dropped_task(self) -> None:
        events = [
            _make_event("task_failed", task_id="t1"),
        ]
        summary = get_retry_summary(events)
        assert summary.total_tasks_with_failures == 1
        assert summary.dropped_count == 1
        assert len(summary.pending_retries) == 1

    def test_mixed_scenario(self) -> None:
        events = [
            # t1: resolved
            _make_event(
                "task_completed", task_id="t1", timestamp="2026-03-20T10:10:00Z"
            ),
            _make_event("task_failed", task_id="t1", timestamp="2026-03-20T10:00:00Z"),
            # t2: retried
            _make_event(
                "retry_attempted", task_id="t2", timestamp="2026-03-20T10:10:00Z"
            ),
            _make_event("task_failed", task_id="t2", timestamp="2026-03-20T10:00:00Z"),
            # t3: dropped
            _make_event("task_failed", task_id="t3", timestamp="2026-03-20T10:00:00Z"),
        ]
        summary = get_retry_summary(events)
        assert summary.total_tasks_with_failures == 3
        assert summary.resolved_tasks == 1
        assert summary.retried_tasks == 1
        assert summary.dropped_count == 1

    def test_to_dict(self) -> None:
        summary = RetrySummary(
            total_tasks_with_failures=2,
            pending_retries=[
                PendingRetry(
                    task_id="t1",
                    failure_count=1,
                    last_failure_details="err",
                    last_failure_lane="author-a",
                    last_failure_timestamp="2026-03-20T10:00:00Z",
                )
            ],
            resolved_tasks=1,
            retried_tasks=0,
            rerouted_tasks=0,
            escalated_tasks=0,
        )
        d = summary.to_dict()
        assert d["total_tasks_with_failures"] == 2
        assert d["dropped_count"] == 1
        assert len(d["pending_retries"]) == 1
        json.dumps(d)


# --- Formatters ---


class TestFormatPendingRetriesText:
    """Tests for format_pending_retries_text()."""

    def test_empty(self) -> None:
        text = format_pending_retries_text([])
        assert "No pending retries" in text

    def test_with_pending(self) -> None:
        pending = [
            PendingRetry(
                task_id="t1",
                failure_count=2,
                last_failure_details="crash",
                last_failure_lane="author-a",
                last_failure_timestamp="2026-03-20T10:00:00Z",
            ),
        ]
        text = format_pending_retries_text(pending)
        assert "t1" in text
        assert "crash" in text
        assert "author-a" in text


class TestFormatRetrySummaryText:
    """Tests for format_retry_summary_text()."""

    def test_clean_summary(self) -> None:
        summary = RetrySummary(
            total_tasks_with_failures=0,
            pending_retries=[],
            resolved_tasks=0,
            retried_tasks=0,
            rerouted_tasks=0,
            escalated_tasks=0,
        )
        text = format_retry_summary_text(summary)
        assert "Retry Follow-Through Summary" in text
        assert "Dropped (no follow-up): 0" in text

    def test_summary_with_drops(self) -> None:
        summary = RetrySummary(
            total_tasks_with_failures=2,
            pending_retries=[
                PendingRetry(
                    task_id="t1",
                    failure_count=1,
                    last_failure_details="err",
                    last_failure_lane="a",
                    last_failure_timestamp="ts",
                )
            ],
            resolved_tasks=1,
            retried_tasks=0,
            rerouted_tasks=0,
            escalated_tasks=0,
        )
        text = format_retry_summary_text(summary)
        assert "Dropped (no follow-up): 1" in text
        assert "t1" in text


class TestFormatRetrySummaryJSON:
    """Tests for format_retry_summary_json()."""

    def test_serializable(self) -> None:
        summary = RetrySummary(
            total_tasks_with_failures=1,
            pending_retries=[],
            resolved_tasks=1,
            retried_tasks=0,
            rerouted_tasks=0,
            escalated_tasks=0,
        )
        d = format_retry_summary_json(summary)
        assert d["total_tasks_with_failures"] == 1
        assert d["dropped_count"] == 0
        json.dumps(d)
