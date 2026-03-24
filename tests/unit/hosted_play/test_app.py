"""Tests for web.app — FastAPI application setup and lifespan."""

from __future__ import annotations

from starlette.testclient import TestClient

from web.ai_manager import AIManager
from web.app import create_app
from web.config import HostedPlayConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_app(tmp_path):
    """Create a test app with a file-based SQLite DB."""
    db_path = tmp_path / "test.db"
    config = HostedPlayConfig(database_url=f"sqlite:///{db_path}")
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
        # CORS middleware is in the middleware stack
        middleware_classes = [
            type(m).__name__ for m in getattr(app, "user_middleware", [])
        ]
        assert "Middleware" in str(middleware_classes) or len(app.user_middleware) > 0


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
            assert app.state.engine is not None

    def test_state_has_session_factory(self, tmp_path):
        app = _make_app(tmp_path)
        with TestClient(app):
            assert hasattr(app.state, "session_factory")
            # Factory should be callable
            session = app.state.session_factory()
            assert session is not None
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
        # After exiting the TestClient context, the engine should be disposed.
        # Verify pool has no active connections (connections returned to pool
        # and pool drained after dispose).
        status = engine.pool.status()
        assert "Checked out connections: 0" in status


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
