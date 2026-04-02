"""Tests for web.app — FastAPI application setup and lifespan."""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.ai_manager import AIManager
from web.app import create_app
from web.config import HostedPlayConfig

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
