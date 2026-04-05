"""Integration tests for RequestLoggingMiddleware and JSON log formatter.

Verifies:
- Every HTTP request produces request_start and request_complete log entries
- Each entry includes request_id, method, path, status_code, duration_ms
- request_id is available via contextvars to route handlers
- JSON format activatable via LOG_FORMAT=json
- Health/ready endpoints are excluded from INFO-level logging (DEBUG only)
"""

from __future__ import annotations

import json
import logging

from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.app import create_app
from web.log_config import JSONFormatter, configure_logging
from web.middleware import get_request_id, request_id_var

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_client(tmp_path):
    """Create a test app + client."""
    config = make_hosted_play_test_config(tmp_path)
    app = create_app(config=config)
    return TestClient(app), app


# ---------------------------------------------------------------------------
# RequestLoggingMiddleware
# ---------------------------------------------------------------------------


class TestRequestLoggingMiddleware:
    """Verify the request logging middleware produces structured log entries."""

    def test_request_produces_start_and_complete_logs(self, tmp_path, caplog):
        """Every HTTP request must emit request_start and request_complete."""
        client, _ = _make_test_client(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="web.middleware"):
            client.get("/health")

        messages = [r.message for r in caplog.records if r.name == "web.middleware"]
        start_msgs = [m for m in messages if "request_start" in m]
        complete_msgs = [m for m in messages if "request_complete" in m]

        assert len(start_msgs) >= 1, f"No request_start log found. Messages: {messages}"
        assert (
            len(complete_msgs) >= 1
        ), f"No request_complete log found. Messages: {messages}"

    def test_log_entry_contains_required_fields(self, tmp_path, caplog):
        """Log entries must include method, path, and request_id."""
        client, _ = _make_test_client(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="web.middleware"):
            client.get("/health")

        start_records = [
            r
            for r in caplog.records
            if r.name == "web.middleware" and "request_start" in r.message
        ]
        assert start_records, "No request_start record found"
        start_msg = start_records[0].message
        assert "method=GET" in start_msg
        assert "path=/health" in start_msg
        assert "request_id=" in start_msg

        complete_records = [
            r
            for r in caplog.records
            if r.name == "web.middleware" and "request_complete" in r.message
        ]
        assert complete_records, "No request_complete record found"
        complete_msg = complete_records[0].message
        assert "status_code=" in complete_msg
        assert "duration_ms=" in complete_msg

    def test_request_id_is_consistent_across_start_and_complete(self, tmp_path, caplog):
        """The same request_id must appear in both start and complete entries."""
        client, _ = _make_test_client(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="web.middleware"):
            client.get("/health")

        middleware_records = [r for r in caplog.records if r.name == "web.middleware"]

        def _extract_rid(msg: str) -> str:
            for part in msg.split():
                if part.startswith("request_id="):
                    return part.split("=", 1)[1]
            return ""

        rids = {_extract_rid(r.message) for r in middleware_records}
        # Remove empty strings (shouldn't happen, but be defensive)
        rids.discard("")
        assert len(rids) == 1, f"Expected exactly one request_id, got {rids}"

    def test_health_endpoint_logged_at_debug(self, tmp_path, caplog):
        """Health/ready paths must log at DEBUG, not INFO."""
        client, _ = _make_test_client(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="web.middleware"):
            client.get("/health")
            client.get("/ready")

        health_records = [
            r
            for r in caplog.records
            if r.name == "web.middleware" and "/health" in r.message
        ]
        ready_records = [
            r
            for r in caplog.records
            if r.name == "web.middleware" and "/ready" in r.message
        ]

        for rec in health_records:
            assert (
                rec.levelno == logging.DEBUG
            ), f"/health logged at {rec.levelname}, expected DEBUG"
        for rec in ready_records:
            assert (
                rec.levelno == logging.DEBUG
            ), f"/ready logged at {rec.levelname}, expected DEBUG"

    def test_non_health_endpoint_logged_at_info(self, tmp_path, caplog):
        """Non-health paths must log at INFO level.

        Uses the full lifespan context (``with TestClient(...)``) so that
        ``app.state.templates`` is populated and the landing route can render.
        """
        config = make_hosted_play_test_config(tmp_path)
        app = create_app(config=config)
        with TestClient(app) as client:
            with caplog.at_level(logging.DEBUG, logger="web.middleware"):
                # Landing page — should be INFO
                client.get("/")

        landing_records = [
            r
            for r in caplog.records
            if r.name == "web.middleware"
            and "request_start" in r.message
            and "path=/" in r.message
            # Exclude /health, /ready which also start with /
            and "/health" not in r.message
            and "/ready" not in r.message
        ]
        assert landing_records, "No INFO-level record for landing page"
        for rec in landing_records:
            assert (
                rec.levelno == logging.INFO
            ), f"Landing logged at {rec.levelname}, expected INFO"

    def test_request_id_resets_between_requests(self, tmp_path, caplog):
        """Each request must get a unique request_id."""
        client, _ = _make_test_client(tmp_path)
        with caplog.at_level(logging.DEBUG, logger="web.middleware"):
            client.get("/health")
            client.get("/ready")

        def _extract_rid(msg: str) -> str:
            for part in msg.split():
                if part.startswith("request_id="):
                    return part.split("=", 1)[1]
            return ""

        start_records = [
            r
            for r in caplog.records
            if r.name == "web.middleware" and "request_start" in r.message
        ]
        rids = [_extract_rid(r.message) for r in start_records]
        assert len(rids) >= 2, f"Expected 2+ start records, got {len(rids)}"
        assert rids[0] != rids[1], "Different requests got the same request_id"


# ---------------------------------------------------------------------------
# get_request_id() — context variable access
# ---------------------------------------------------------------------------


class TestGetRequestId:
    """Verify get_request_id() returns the correct value."""

    def test_returns_empty_outside_request(self):
        """Outside a request context, get_request_id() returns empty string."""
        assert get_request_id() == ""

    def test_returns_value_after_set(self):
        """After setting the ContextVar, get_request_id() returns the value."""
        token = request_id_var.set("test-rid-123")
        try:
            assert get_request_id() == "test-rid-123"
        finally:
            request_id_var.reset(token)


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """Verify the JSON formatter produces valid, structured output."""

    def test_format_produces_valid_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert "timestamp" in parsed

    def test_includes_request_id_when_present(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="with request id",
            args=(),
            exc_info=None,
        )
        record.request_id = "abc-123"  # type: ignore[attr-defined]
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["request_id"] == "abc-123"

    def test_omits_request_id_when_empty(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="no request id",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "request_id" not in parsed

    def test_includes_exception_info(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "boom" in parsed["exception"]


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    """Verify configure_logging wires the correct formatter."""

    def test_json_format_installs_json_formatter(self):
        configure_logging(log_format="json", log_level="INFO")
        root = logging.getLogger()
        try:
            assert any(
                isinstance(h.formatter, JSONFormatter) for h in root.handlers
            ), "JSONFormatter not found on root logger handlers"
        finally:
            # Restore default text logging to avoid polluting other tests
            configure_logging(log_format="text", log_level="INFO")

    def test_text_format_does_not_use_json_formatter(self):
        configure_logging(log_format="text", log_level="INFO")
        root = logging.getLogger()
        assert not any(
            isinstance(h.formatter, JSONFormatter) for h in root.handlers
        ), "JSONFormatter should not be present for text format"
