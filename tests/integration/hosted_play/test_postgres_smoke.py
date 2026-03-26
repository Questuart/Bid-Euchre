"""Postgres deployment smoke tests for the hosted browser game.

Validates that the web application works correctly with both SQLite (always)
and Postgres (when ``TEST_POSTGRES_URL`` is set).  These tests exercise the
full app lifecycle — config loading, engine/table creation, match creation
via HTTP, and the ``/ready`` probe — to catch driver or DDL issues that only
surface with a real Postgres backend.

**Running locally without Postgres:**

    uv run python -m pytest tests/integration/hosted_play/ -v

All tests that require a live Postgres instance are skipped automatically
when ``TEST_POSTGRES_URL`` is not set.

**Running with Postgres:**

Requires the ``hosted`` extra for the ``psycopg`` driver::

    uv sync --extra dev --extra hosted
    TEST_POSTGRES_URL="postgresql+psycopg://user:pass@localhost/test_bideuchre" \
        uv run python -m pytest tests/integration/hosted_play/ -v

Each test process creates an isolated database (``<dbname>_pid<PID>``) to
prevent cross-contamination when running with ``pytest-xdist`` or multiple
sessions.  The database pointed to by ``TEST_POSTGRES_URL`` is used only as
a template for the connection parameters — no tables are created in it
directly.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.integration

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.app import create_app
from web.config import HostedPlayConfig, override_config
from web.db import (
    Match,
    Player,
    create_tables,
    init_engine,
    make_session_factory,
)

# ---------------------------------------------------------------------------
# Markers and helpers
# ---------------------------------------------------------------------------

_PG_URL = os.environ.get("TEST_POSTGRES_URL")

requires_postgres = pytest.mark.skipif(
    _PG_URL is None,
    reason="TEST_POSTGRES_URL not set — skipping Postgres tests",
)


def _sqlite_url(tmp_path) -> str:
    """Return a file-backed SQLite URL for a given tmp_path."""
    return f"sqlite:///{tmp_path / 'smoke.db'}"


def _isolated_pg_params() -> tuple[str, str, str]:
    """Derive a process-isolated Postgres database from ``TEST_POSTGRES_URL``.

    Returns:
        (isolated_url, admin_url, db_name) — the unique database URL for
        this test process, an admin URL (connected to ``postgres``) for
        CREATE/DROP DATABASE commands, and the isolated database name.
    """
    assert _PG_URL is not None
    base = make_url(_PG_URL)
    db_name = f"{base.database}_pid{os.getpid()}"
    isolated = base.set(database=db_name)
    admin = base.set(database="postgres")
    return str(isolated), str(admin), db_name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_config(tmp_path):
    """HostedPlayConfig backed by a file-based SQLite database."""
    return make_hosted_play_test_config(tmp_path, database_url=_sqlite_url(tmp_path))


@pytest.fixture()
def pg_config(tmp_path):
    """HostedPlayConfig backed by an isolated per-process Postgres database."""
    isolated_url, _admin, _db = _isolated_pg_params()
    return make_hosted_play_test_config(tmp_path, database_url=isolated_url)


@pytest.fixture()
def pg_engine():
    """SQLAlchemy engine connected to a per-process isolated Postgres database.

    Creates a fresh database named ``<base>_pid<PID>`` and drops it on
    teardown, preventing cross-contamination between parallel test processes.
    """
    isolated_url, admin_url, db_name = _isolated_pg_params()

    # Create isolated database via the admin connection
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    engine = init_engine(isolated_url)
    create_tables(engine)
    yield engine

    # Teardown — dispose engine then drop the isolated database
    engine.dispose()
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    admin_engine.dispose()


# ---------------------------------------------------------------------------
# SQLite-only tests (always run)
# ---------------------------------------------------------------------------


class TestSQLiteSmokeAlwaysRuns:
    """Baseline smoke: these tests run on every CI build (no Postgres needed)."""

    def test_init_engine_sqlite(self, tmp_path):
        """init_engine accepts a SQLite URL and creates a usable engine."""
        engine = init_engine(_sqlite_url(tmp_path))
        create_tables(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"players", "matches", "hands", "decisions"} <= tables
        engine.dispose()

    def test_app_lifecycle_sqlite(self, sqlite_config):
        """Full app startup/shutdown cycle with SQLite."""
        app = create_app(config=sqlite_config)
        try:
            with TestClient(app) as client:
                # Health probe
                resp = client.get("/health")
                assert resp.status_code == 200
                assert resp.json()["status"] == "ok"

                # Readiness probe (exercises DB SELECT 1)
                resp = client.get("/ready")
                assert resp.status_code == 200
                assert resp.json()["status"] == "ready"
        finally:
            override_config(None)

    def test_match_creation_sqlite(self, sqlite_config):
        """POST /new creates a match and redirects (SQLite)."""
        app = create_app(config=sqlite_config)
        try:
            with TestClient(app) as client:
                resp = client.post("/new", follow_redirects=False)
                assert resp.status_code in (302, 307)
                location = resp.headers.get("location", "")
                assert "/play/" in location
        finally:
            override_config(None)

    def test_database_url_env_var_sqlite(self, monkeypatch, tmp_path):
        """DATABASE_URL env var is respected for SQLite."""
        url = _sqlite_url(tmp_path)
        monkeypatch.setenv("DATABASE_URL", url)
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == url

    def test_database_url_env_var_postgres_format(self, monkeypatch):
        """DATABASE_URL env var with Postgres format is parsed correctly."""
        pg_url = "postgresql+psycopg://user:pass@db.host:5432/mydb"
        monkeypatch.setenv("DATABASE_URL", pg_url)
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == pg_url

    def test_database_url_default(self, monkeypatch):
        """Missing DATABASE_URL falls back to local SQLite."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == "sqlite:///hosted_play.db"

    def test_startup_entrypoint_defaults(self, monkeypatch):
        """web.start.main() reads env vars and calls uvicorn.run correctly."""
        mock_run = MagicMock()
        monkeypatch.setattr("uvicorn.run", mock_run)
        # Clear env vars so main() uses defaults
        for var in ("HOST", "PORT", "WEB_WORKERS", "LOG_LEVEL"):
            monkeypatch.delenv(var, raising=False)

        from web.start import main

        main()

        mock_run.assert_called_once_with(
            "web.app:create_app",
            factory=True,
            host="0.0.0.0",
            port=8000,
            workers=1,
            log_level="info",
        )

    def test_startup_entrypoint_custom_env(self, monkeypatch):
        """web.start.main() honours custom environment overrides."""
        mock_run = MagicMock()
        monkeypatch.setattr("uvicorn.run", mock_run)
        monkeypatch.setenv("HOST", "127.0.0.1")
        monkeypatch.setenv("PORT", "9090")
        monkeypatch.setenv("WEB_WORKERS", "4")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        from web.start import main

        main()

        mock_run.assert_called_once_with(
            "web.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=9090,
            workers=4,
            log_level="debug",
        )


# ---------------------------------------------------------------------------
# Postgres tests (skipped unless TEST_POSTGRES_URL is set)
# ---------------------------------------------------------------------------


@requires_postgres
class TestPostgresSmoke:
    """Validate the hosted app works end-to-end on a real Postgres backend."""

    def test_init_engine_postgres(self, pg_engine):
        """init_engine creates tables on Postgres."""
        inspector = inspect(pg_engine)
        tables = set(inspector.get_table_names())
        assert {"players", "matches", "hands", "decisions"} <= tables

    def test_crud_round_trip(self, pg_engine):
        """Basic CRUD (Player + Match) works on Postgres."""
        factory = make_session_factory(pg_engine)
        session = factory()
        try:
            player = Player(
                link_uuid=str(uuid.uuid4()),
                nickname="PgSmokePlayer",
            )
            session.add(player)
            session.flush()
            assert player.id is not None

            match = Match(
                match_uuid=str(uuid.uuid4()),
                player_id=player.id,
                ai_model="heuristic",
                status="active",
                seed=42,
                match_state_json="{}",
            )
            session.add(match)
            session.flush()
            assert match.id is not None

            # Verify a simple query
            result = session.execute(text("SELECT count(*) FROM matches")).scalar()
            assert result == 1
        finally:
            session.rollback()
            session.close()

    def test_app_lifecycle_postgres(self, pg_config, pg_engine):
        """Full app startup/shutdown cycle with Postgres.

        Uses pg_engine fixture to ensure tables exist before the app starts.
        """
        _ = pg_engine  # fixture dependency — ensures tables exist
        app = create_app(config=pg_config)
        try:
            with TestClient(app) as client:
                # Health probe
                resp = client.get("/health")
                assert resp.status_code == 200
                assert resp.json()["status"] == "ok"

                # Readiness probe
                resp = client.get("/ready")
                assert resp.status_code == 200
                assert resp.json()["status"] == "ready"
        finally:
            override_config(None)

    def test_match_creation_postgres(self, pg_config, pg_engine):
        """POST /new creates a match and redirects (Postgres)."""
        _ = pg_engine  # fixture dependency — ensures tables exist
        app = create_app(config=pg_config)
        try:
            with TestClient(app) as client:
                resp = client.post("/new", follow_redirects=False)
                assert resp.status_code in (302, 307)
                location = resp.headers.get("location", "")
                assert "/play/" in location
        finally:
            override_config(None)

    def test_select_1_postgres(self, pg_engine):
        """SELECT 1 connectivity check on Postgres."""
        factory = make_session_factory(pg_engine)
        session = factory()
        try:
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
        finally:
            session.close()
