#!/usr/bin/env bash
# Production startup wrapper for the Bid Euchre browser game.
#
# This script is the Docker CMD / Render start command. It:
#   1. Prints diagnostic info (Python version, key env vars)
#   2. Delegates to the Python entrypoint (web.start) which handles
#      DB init (via the FastAPI lifespan) and uvicorn startup.
#
# Environment variables consumed by this script or web.start:
#   HOST          — bind address   (default: 0.0.0.0)
#   PORT          — bind port      (default: 8000, Render injects $PORT)
#   WEB_WORKERS   — worker count   (default: 1)
#   LOG_LEVEL     — uvicorn level  (default: info)
#   DATABASE_URL  — SQLAlchemy DSN (default: sqlite:///hosted_play.db)
#
# Usage:
#   ./scripts/start_hosted.sh          # direct
#   docker run -p 8000:8000 bideuchre  # via Dockerfile CMD

set -euo pipefail

echo "=== Bid Euchre Hosted Game Startup ==="
echo "Python: $(python --version 2>&1)"
echo "Host:   ${HOST:-0.0.0.0}"
echo "Port:   ${PORT:-8000}"
echo "Workers: ${WEB_WORKERS:-1}"
echo "DB URL: ${DATABASE_URL:-(sqlite default)}"
echo "======================================="

exec python -m web.start
