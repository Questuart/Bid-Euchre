"""Structured JSON log formatter for production deployment.

Provides a :class:`JSONFormatter` that emits one JSON object per log
record, and a :func:`configure_logging` helper that wires it into the
root logger when ``LOG_FORMAT=json`` is set.

The formatter is intentionally minimal — stdlib ``logging`` only, no
third-party dependencies (structlog, loguru, etc.).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects.

    Includes ``request_id`` from the record's extras when present (set by
    :class:`web.middleware.RequestLoggingMiddleware` via a
    :class:`~logging.Filter`).
    """

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        log_data: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include request_id when the middleware filter injects it.
        request_id = getattr(record, "request_id", "")
        if request_id:
            log_data["request_id"] = request_id

        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def configure_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """Set up root logger with the appropriate formatter.

    Parameters
    ----------
    log_format:
        ``"json"`` for structured JSON output (production),
        ``"text"`` for human-readable output (development).
    log_level:
        Standard Python log level name (``DEBUG``, ``INFO``, etc.).
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate output when called
    # multiple times (e.g. tests calling create_app repeatedly).
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s  %(message)s")
        )
    root.addHandler(handler)
