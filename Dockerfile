# Dockerfile — Bid Euchre Browser Game
#
# Thin production image: Python 3.12, hosted extras only, web/start.py entrypoint.
# No dev deps, no data/runs, no experiment infrastructure.
#
# Build:  docker build -t bideuchre-web .
# Run:    docker run -p 8000:8000 -e DATABASE_URL=sqlite:///hosted_play.db bideuchre-web
# Custom: docker run -e PORT=9999 -p 9999:9999 bideuchre-web

FROM python:3.12-slim AS base

# Prevent .pyc files and enable unbuffered output for logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- Install uv for fast, deterministic dependency resolution ---
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# --- Install dependencies first (cache-friendly layer ordering) ---
COPY pyproject.toml uv.lock ./

# Install only the hosted extras (no dev deps)
RUN uv sync --frozen --no-dev --extra hosted --no-install-project

# --- Copy application source ---
COPY src/ src/
COPY web/ web/

# Install the project itself (editable not needed in production)
RUN uv sync --frozen --no-dev --extra hosted

# --- Non-root user for runtime security (CIS Docker Benchmark 5.7) ---
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

# uv cache must be writable by the non-root user; the default
# ~/.cache/uv resolves to /nonexistent/.cache/uv which doesn't exist.
ENV UV_CACHE_DIR=/tmp/uv-cache

USER app

EXPOSE 8000

# Production entrypoint — reads $PORT, $HOST, $WEB_WORKERS, $LOG_LEVEL
CMD ["uv", "run", "python", "web/start.py"]
