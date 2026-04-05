"""Production startup entrypoint for the Bid Euchre browser game.

Launches uvicorn with the :func:`web.app.create_app` factory, reading
host/port/worker configuration from environment variables.

Environment variables
---------------------

====================  ===========  ========================================
Variable              Default      Purpose
====================  ===========  ========================================
``HOST``              ``0.0.0.0``  Bind address
``PORT``              ``8000``     Bind port (Render injects ``$PORT``)
``WEB_WORKERS``       ``1``        Uvicorn worker count
``LOG_LEVEL``         ``info``     Uvicorn log level
``LOG_FORMAT``        ``text``     ``text`` or ``json`` (structured output)
====================  ===========  ========================================

Usage::

    # Direct execution
    python -m web.start

    # Via module path
    uv run python -m web.start

    # Render/Docker (PORT injected by platform)
    python -m web.start
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Parse environment and launch uvicorn."""
    # Lazy import so the module can be imported without triggering
    # uvicorn installation checks at import time.
    import uvicorn

    from web.log_config import configure_logging

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    workers = int(os.environ.get("WEB_WORKERS", "1"))
    log_level = os.environ.get("LOG_LEVEL", "info").lower()
    log_format = os.environ.get("LOG_FORMAT", "text").lower()

    # Configure structured logging before uvicorn starts.
    configure_logging(log_format=log_format, log_level=log_level)

    # Validate workers — uvicorn requires >= 1
    if workers < 1:
        print(f"WEB_WORKERS must be >= 1, got {workers}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Starting Bid Euchre web server: "
        f"host={host} port={port} workers={workers} log_level={log_level}"
    )

    uvicorn.run(
        "web.app:create_app",
        factory=True,
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
