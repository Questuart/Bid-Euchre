# Dockerfile — Bid Euchre Browser Game
#
# Thin production image: Python 3.12, hosted extras only, uvicorn entrypoint.
# No dev deps, no data/runs, no experiment infrastructure.
#
# Build:  docker build -t bideuchre-web .
# Run:    docker run -p 8000:8000 -e DATABASE_URL=sqlite:///hosted_play.db bideuchre-web

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

EXPOSE 8000

# Uvicorn entrypoint — create_app() is a factory function
CMD ["uv", "run", "uvicorn", "web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
