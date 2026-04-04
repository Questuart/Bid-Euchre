"""Tests for web.app — FastAPI application setup and lifespan."""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.ai_manager import AIManager
from web.app import create_app
from web.config import HostedPlayConfig
from web.db import InviteCode

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app(tmp_path):
    """Create a test app with a file-based SQLite DB."""
    config = make_hosted_play_test_config(tmp_path)
    return create_app(config=config)


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Verify create_app returns a properly configured FastAPI instance."""

    def test_returns_fastapi_instance(self, tmp_path):
        app = _make_app(tmp_path)
        # FastAPI is a Starlette subclass
        assert hasattr(app, "routes")
        assert app.title == "Bid Euchre Browser Game"
        assert app.version == "0.1.0"

    def test_cors_middleware_registered(self, tmp_path):
        app = _make_app(tmp_path)
        # Verify CORSMiddleware specifically (not just any middleware)
        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_cors_honors_configured_origins(self, tmp_path):
        """CORS middleware should use allowed_origins from config, not hardcoded '*'."""
        db_path = tmp_path / "test.db"
        config = make_hosted_play_test_config(
            tmp_path,
            database_url=f"sqlite:///{db_path}",
            allowed_origins=["https://app.example.com", "https://staging.example.com"],
        )
        app = create_app(config=config)
        cors_mw = [m for m in app.user_middleware if m.cls is CORSMiddleware]
        assert len(cors_mw) == 1
        assert cors_mw[0].kwargs["allow_origins"] == [
            "https://app.example.com",
            "https://staging.example.com",
        ]

    def test_cors_default_wildcard(self, tmp_path):
        """Default config (no ALLOWED_ORIGINS) should still produce ['*']."""
        app = _make_app(tmp_path)
        cors_mw = [m for m in app.user_middleware if m.cls is CORSMiddleware]
        assert len(cors_mw) == 1
        assert cors_mw[0].kwargs["allow_origins"] == ["*"]


# ---------------------------------------------------------------------------
# Lifespan — app.state
# ---------------------------------------------------------------------------


class TestLifespan:
    """Verify lifespan populates app.state correctly."""

    def test_state_has_config(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app):
            assert hasattr(app.state, "config")
            assert isinstance(app.state.config, HostedPlayConfig)

    def test_state_has_engine(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app):
            assert hasattr(app.state, "engine")
            assert isinstance(app.state.engine, Engine)

    def test_state_has_session_factory(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app):
            assert hasattr(app.state, "session_factory")
            # Factory should be callable and produce a Session
            session = app.state.session_factory()
            assert isinstance(session, Session)
            session.close()

    def test_state_has_ai_manager(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app):
            assert hasattr(app.state, "ai_manager")
            assert isinstance(app.state.ai_manager, AIManager)

    def test_engine_disposed_after_shutdown(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app):
            engine = app.state.engine
        # After exiting the TestClient context, engine.dispose() has run.
        # Assert the pool was fully disposed — no connections remain at all,
        # not just zero checked-out.
        pool = engine.pool
        assert (
            pool.checkedout() == 0
        ), f"Expected 0 checked-out, got {pool.checkedout()}"
        assert pool.checkedin() == 0, f"Expected 0 checked-in, got {pool.checkedin()}"

    def test_auto_seeds_invite_code_on_fresh_db(self, tmp_path):
        """Fresh database should get one auto-seeded invite code."""
        app = _make_app(tmp_path)
        with TestClient(app):
            session = app.state.session_factory()
            try:
                codes = session.query(InviteCode).all()
                assert len(codes) == 1
                assert codes[0].status == "active"
                assert codes[0].label == "auto-seed"
                assert len(codes[0].code) > 0
            finally:
                session.close()

    def test_auto_seed_is_idempotent(self, tmp_path):
        """If invite codes already exist, no new ones are seeded."""
        app = _make_app(tmp_path)
        # First startup: creates the seed code
        with TestClient(app):
            session = app.state.session_factory()
            try:
                count_after_first = session.query(InviteCode).count()
                assert count_after_first == 1
            finally:
                session.close()
        # Second startup on same DB: should not add another code
        app2 = create_app(config=make_hosted_play_test_config(tmp_path))
        with TestClient(app2):
            session2 = app2.state.session_factory()
            try:
                count_after_second = session2.query(InviteCode).count()
                assert count_after_second == 1
            finally:
                session2.close()


# ---------------------------------------------------------------------------
# Router inclusion
# ---------------------------------------------------------------------------


class TestRouterInclusion:
    """Verify that game routes are accessible through the app."""

    def test_landing_page_accessible(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/")
            assert resp.status_code == 200

    def test_create_game_accessible(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app) as client:
            resp = client.post("/new", follow_redirects=False)
            assert resp.status_code == 302

    def test_unknown_route_returns_404(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/nonexistent")
            assert resp.status_code == 404

    def test_htmx_404_returns_200_for_swap(self, tmp_path):
        """HTMX 1.x ignores non-2xx; error partials must return 200."""
        app = _make_app(tmp_path)
        with TestClient(app) as client:
            resp = client.get("/nonexistent", headers={"HX-Request": "true"})
            assert resp.status_code == 200
            assert "htmx-error" in resp.text


# ---------------------------------------------------------------------------
# Onboarding migration (lifespan step 1b)
# ---------------------------------------------------------------------------

# SQL for the old players table schema (before the onboarding_complete column
# was added to the ORM model).  We create this manually so we can test that
# the ALTER TABLE migration in lifespan() works on a pre-existing DB.
_OLD_PLAYERS_DDL = """\
CREATE TABLE players (
    id INTEGER PRIMARY KEY,
    link_uuid VARCHAR NOT NULL UNIQUE,
    nickname VARCHAR,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
)
"""


def _create_legacy_db(db_path) -> str:
    """Create a SQLite DB with the old players schema (no onboarding_complete).

    Also creates the other tables the app requires so lifespan() can run
    its full startup sequence without hitting missing-table errors.

    Returns the ``sqlite:///`` database URL.
    """
    url = f"sqlite:///{db_path}"
    engine = create_engine(url, echo=False)
    with engine.begin() as conn:
        # Players table WITHOUT onboarding_complete
        conn.execute(text(_OLD_PLAYERS_DDL))

        # Minimal stubs for other required tables.  lifespan() calls
        # create_tables() which is idempotent (CREATE TABLE IF NOT EXISTS),
        # so these just need to exist with the right names to avoid the
        # inspector / migration from failing before we get to test it.
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS matches ("
                "  id INTEGER PRIMARY KEY,"
                "  match_uuid VARCHAR NOT NULL UNIQUE,"
                "  player_id INTEGER NOT NULL REFERENCES players(id),"
                "  ai_model VARCHAR NOT NULL,"
                "  status VARCHAR NOT NULL,"
                "  seed INTEGER NOT NULL,"
                "  score_human INTEGER NOT NULL DEFAULT 0,"
                "  score_ai INTEGER NOT NULL DEFAULT 0,"
                "  hands_played INTEGER NOT NULL DEFAULT 0,"
                "  current_hand_number INTEGER NOT NULL DEFAULT 0,"
                "  match_state_json TEXT NOT NULL,"
                "  created_at DATETIME NOT NULL DEFAULT (datetime('now')),"
                "  completed_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS hands ("
                "  id INTEGER PRIMARY KEY,"
                "  match_id INTEGER NOT NULL REFERENCES matches(id),"
                "  hand_number INTEGER NOT NULL,"
                "  deal_id INTEGER NOT NULL,"
                "  dealer_seat INTEGER NOT NULL,"
                "  status VARCHAR NOT NULL,"
                "  hand_state_json TEXT NOT NULL DEFAULT '{}',"
                "  created_at DATETIME NOT NULL DEFAULT (datetime('now')),"
                "  completed_at DATETIME"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS decisions ("
                "  id INTEGER PRIMARY KEY,"
                "  match_id INTEGER NOT NULL REFERENCES matches(id),"
                "  hand_id INTEGER NOT NULL REFERENCES hands(id),"
                "  turn_number INTEGER NOT NULL,"
                "  seat INTEGER NOT NULL,"
                "  phase VARCHAR NOT NULL,"
                "  actor_type VARCHAR NOT NULL,"
                "  decision_source VARCHAR NOT NULL,"
                "  legal_actions_json TEXT NOT NULL,"
                "  chosen_action_json TEXT NOT NULL,"
                "  game_state_json TEXT NOT NULL,"
                "  decision_time_ms INTEGER,"
                "  created_at DATETIME NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS invite_codes ("
                "  id INTEGER PRIMARY KEY,"
                "  code VARCHAR NOT NULL UNIQUE,"
                "  status VARCHAR NOT NULL DEFAULT 'active',"
                "  label VARCHAR,"
                "  created_at DATETIME NOT NULL DEFAULT (datetime('now'))"
                ")"
            )
        )
    engine.dispose()
    return url


class TestOnboardingMigration:
    """Tests for the onboarding_complete startup migration (lifespan step 1b).

    The migration in ``web/app.lifespan()`` detects whether the ``players``
    table is missing the ``onboarding_complete`` column and, if so:

    1. ALTER TABLEs to add it (``INTEGER NOT NULL DEFAULT 0``).
    2. Sets ``onboarding_complete = 1`` for all players that already have a
       nickname (so returning players are not forced through onboarding).
    """

    def test_fresh_db_already_has_column(self, tmp_path):
        """On a brand-new DB, create_tables includes onboarding_complete;
        migration is a no-op and no errors occur."""
        app = _make_app(tmp_path)
        with TestClient(app):
            engine = app.state.engine
            cols = {c["name"] for c in sa_inspect(engine).get_columns("players")}
            assert "onboarding_complete" in cols

    def test_migration_adds_column_to_legacy_db(self, tmp_path):
        """Starting the app against a legacy DB (no onboarding_complete column)
        adds the column via ALTER TABLE."""
        db_path = tmp_path / "legacy.db"
        db_url = _create_legacy_db(db_path)
        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app):
            engine = app.state.engine
            cols = {c["name"] for c in sa_inspect(engine).get_columns("players")}
            assert "onboarding_complete" in cols

    def test_migration_marks_nicknamed_players_complete(self, tmp_path):
        """Players who already have a nickname get onboarding_complete=1."""
        db_path = tmp_path / "legacy.db"
        db_url = _create_legacy_db(db_path)

        # Pre-populate with a player who has a nickname
        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO players (link_uuid, nickname) "
                    "VALUES ('uuid-with-nick', 'Alice')"
                )
            )
        engine.dispose()

        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app):
            session = app.state.session_factory()
            try:
                row = session.execute(
                    text(
                        "SELECT onboarding_complete FROM players "
                        "WHERE link_uuid = 'uuid-with-nick'"
                    )
                ).fetchone()
                assert row is not None
                assert row[0] == 1
            finally:
                session.close()

    def test_migration_leaves_unnicknamed_players_incomplete(self, tmp_path):
        """Players without a nickname stay onboarding_complete=0."""
        db_path = tmp_path / "legacy.db"
        db_url = _create_legacy_db(db_path)

        # Pre-populate with a player who has no nickname
        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO players (link_uuid, nickname) "
                    "VALUES ('uuid-no-nick', NULL)"
                )
            )
        engine.dispose()

        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app):
            session = app.state.session_factory()
            try:
                row = session.execute(
                    text(
                        "SELECT onboarding_complete FROM players "
                        "WHERE link_uuid = 'uuid-no-nick'"
                    )
                ).fetchone()
                assert row is not None
                assert row[0] == 0
            finally:
                session.close()

    def test_migration_mixed_players(self, tmp_path):
        """Both nicknamed and un-nicknamed players are migrated correctly."""
        db_path = tmp_path / "legacy.db"
        db_url = _create_legacy_db(db_path)

        engine = create_engine(db_url)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO players (link_uuid, nickname) VALUES "
                    "('uuid-alice', 'Alice'), "
                    "('uuid-bob', NULL), "
                    "('uuid-carol', 'Carol')"
                )
            )
        engine.dispose()

        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app):
            session = app.state.session_factory()
            try:
                rows = session.execute(
                    text(
                        "SELECT link_uuid, onboarding_complete FROM players "
                        "ORDER BY link_uuid"
                    )
                ).fetchall()
                result = {r[0]: r[1] for r in rows}
                assert result["uuid-alice"] == 1
                assert result["uuid-bob"] == 0
                assert result["uuid-carol"] == 1
            finally:
                session.close()

    def test_migration_idempotent_on_second_startup(self, tmp_path):
        """Running the app twice on the same DB does not fail or duplicate
        the column (second run is a no-op)."""
        db_path = tmp_path / "legacy.db"
        db_url = _create_legacy_db(db_path)

        # First startup — triggers migration
        config1 = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app1 = create_app(config=config1)
        with TestClient(app1):
            pass  # lifespan runs migration

        # Second startup — column already present, migration skipped
        config2 = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app2 = create_app(config=config2)
        with TestClient(app2):
            engine = app2.state.engine
            cols = [c["name"] for c in sa_inspect(engine).get_columns("players")]
            # Column should exist exactly once (no duplicate)
            assert cols.count("onboarding_complete") == 1

    def test_migration_empty_legacy_db(self, tmp_path):
        """Migration succeeds on a legacy DB with zero players."""
        db_path = tmp_path / "legacy.db"
        db_url = _create_legacy_db(db_path)

        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app):
            engine = app.state.engine
            cols = {c["name"] for c in sa_inspect(engine).get_columns("players")}
            assert "onboarding_complete" in cols
