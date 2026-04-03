"""Tests for B8 pilot launch hardening features.

Covers:
1. Rate limiting on match creation (max 5 active per player)
2. Custom error pages (404, 500)
3. Session cleanup (expire stale matches)
4. Enhanced /health endpoint (metrics)
5. Startup self-test (DB, static, templates)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.app import _run_self_test, create_app
from web.cleanup import (
    DEFAULT_MAX_MATCH_AGE,
    PLAYER_STALE_MATCH_AGE,
    expire_player_stale_matches,
    expire_stale_matches,
)
from web.db import (
    Match,
    Player,
    create_tables,
    init_engine,
    make_session_factory,
)
from web.middleware import MAX_ACTIVE_MATCHES_PER_PLAYER, check_match_limit

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path):
    """File-based SQLite config for test isolation."""
    return make_hosted_play_test_config(tmp_path)


@pytest.fixture()
def app(config):
    """FastAPI app configured with temp DB."""
    return create_app(config=config)


@pytest.fixture()
def client(app):
    """TestClient wrapping the test app."""
    with TestClient(app) as c:
        yield c


def _create_player(session, nickname="TestPlayer") -> Player:
    """Insert a Player row."""
    player = Player(link_uuid=str(uuid.uuid4()), nickname=nickname)
    session.add(player)
    session.flush()
    return player


def _create_match(session, player_id: int, status: str = "active", **kw) -> Match:
    """Insert a Match row with sensible defaults."""
    match = Match(
        match_uuid=str(uuid.uuid4()),
        player_id=player_id,
        ai_model="heuristic",
        status=status,
        seed=42,
        match_state_json="{}",
        **kw,
    )
    session.add(match)
    session.flush()
    return match


# ===================================================================
# 1. Rate Limiting — check_match_limit
# ===================================================================


class TestMatchRateLimit:
    """Rate limiting: max 5 active matches per player."""

    def test_under_limit_returns_true(self, app, client):
        """Player with fewer than MAX active matches is allowed."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            for _ in range(MAX_ACTIVE_MATCHES_PER_PLAYER - 1):
                _create_match(session, player.id)
            session.commit()
            assert check_match_limit(session, player.id) is True
        finally:
            session.close()

    def test_at_limit_returns_false(self, app, client):
        """Player with MAX active matches is rejected."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            for _ in range(MAX_ACTIVE_MATCHES_PER_PLAYER):
                _create_match(session, player.id)
            session.commit()
            assert check_match_limit(session, player.id) is False
        finally:
            session.close()

    def test_completed_matches_not_counted(self, app, client):
        """Completed matches don't count toward the limit."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            for _ in range(MAX_ACTIVE_MATCHES_PER_PLAYER):
                _create_match(session, player.id, status="complete")
            session.commit()
            assert check_match_limit(session, player.id) is True
        finally:
            session.close()

    def test_route_returns_429_when_limit_reached(self, client, app):
        """POST /play/{uuid}/select-ai returns 429 when limit exceeded."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            for _ in range(MAX_ACTIVE_MATCHES_PER_PLAYER):
                _create_match(session, player.id)
            session.commit()
            link_uuid = player.link_uuid
        finally:
            session.close()

        resp = client.post(
            f"/play/{link_uuid}/select-ai",
            data={"model_id": "olsa"},
        )
        assert resp.status_code == 429
        assert "limit" in resp.text.lower() or "Match limit" in resp.text


# ===================================================================
# 2. Custom Error Pages
# ===================================================================


class TestCustomErrorPages:
    """Custom 404 and 500 error pages with game theming."""

    def test_404_returns_themed_html(self, client):
        """Non-existent route returns a themed 404 page."""
        resp = client.get("/nonexistent-page-that-does-not-exist")
        assert resp.status_code == 404
        assert "Hand Not Found" in resp.text
        assert "Back to Table" in resp.text

    def test_404_game_link_not_found(self, client):
        """Invalid game link returns 404."""
        resp = client.get(f"/play/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_error_pages_extend_base_template(self, client):
        """Error pages inherit from base.html (have DOCTYPE, CSS link)."""
        resp = client.get("/nonexistent-page-that-does-not-exist")
        assert "<!DOCTYPE html>" in resp.text
        assert "style.css" in resp.text


# ===================================================================
# 3. Session Cleanup
# ===================================================================


class TestSessionCleanup:
    """expire_stale_matches marks old active matches as abandoned."""

    def test_expire_old_matches(self, app, client):
        """Matches older than max_age are marked abandoned."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            old_time = datetime.now(timezone.utc) - timedelta(hours=25)
            match = _create_match(session, player.id)
            match.created_at = old_time
            session.commit()

            count = expire_stale_matches(session)
            session.commit()

            assert count == 1
            session.refresh(match)
            assert match.status == "abandoned"
            assert match.completed_at is not None
        finally:
            session.close()

    def test_recent_matches_not_expired(self, app, client):
        """Matches younger than max_age are untouched."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            _create_match(session, player.id)
            session.commit()

            count = expire_stale_matches(session)
            session.commit()

            assert count == 0
        finally:
            session.close()

    def test_completed_matches_not_expired(self, app, client):
        """Already-completed matches are not re-expired."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            old_time = datetime.now(timezone.utc) - timedelta(hours=25)
            match = _create_match(session, player.id, status="complete")
            match.created_at = old_time
            session.commit()

            count = expire_stale_matches(session)
            session.commit()

            assert count == 0
            session.refresh(match)
            assert match.status == "complete"
        finally:
            session.close()

    def test_custom_max_age(self, app, client):
        """Custom max_age is respected."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            match = _create_match(session, player.id)
            match.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
            session.commit()

            # 1-hour max_age should catch this
            count = expire_stale_matches(session, max_age=timedelta(hours=1))
            session.commit()

            assert count == 1
            session.refresh(match)
            assert match.status == "abandoned"
        finally:
            session.close()

    def test_default_max_age_is_24h(self):
        """Default threshold is 24 hours."""
        assert DEFAULT_MAX_MATCH_AGE == timedelta(hours=24)


# ===================================================================
# 4. Enhanced Health Endpoint
# ===================================================================


class TestEnhancedHealth:
    """Enhanced /health endpoint reports operational metrics."""

    def test_health_returns_200(self, client):
        """Health endpoint always returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_includes_status_ok(self, client):
        """Response includes top-level status field."""
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_includes_active_matches(self, client):
        """Response includes active_matches count."""
        data = client.get("/health").json()
        assert "active_matches" in data
        assert data["active_matches"] == 0

    def test_health_includes_total_players(self, client):
        """Response includes total_players count."""
        data = client.get("/health").json()
        assert "total_players" in data
        assert data["total_players"] == 0

    def test_health_includes_db_size(self, client):
        """Response includes db_size_bytes."""
        data = client.get("/health").json()
        assert "db_size_bytes" in data
        # SQLite file should have a positive size
        assert data["db_size_bytes"] > 0

    def test_health_includes_uptime(self, client):
        """Response includes uptime_seconds."""
        data = client.get("/health").json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_counts_matches_correctly(self, app, client):
        """active_matches reflects actual DB state."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            _create_match(session, player.id, status="active")
            _create_match(session, player.id, status="active")
            _create_match(session, player.id, status="complete")
            session.commit()
        finally:
            session.close()

        data = client.get("/health").json()
        assert data["active_matches"] == 2
        assert data["total_players"] == 1


# ===================================================================
# 5. Startup Self-Test
# ===================================================================


class TestStartupSelfTest:
    """Startup self-test verifies DB, static assets, and templates."""

    def test_self_test_passes_normal(self, tmp_path):
        """Self-test passes with a properly set up environment."""
        # Set up a real engine with tables
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)

        from pathlib import Path

        web_dir = Path(__file__).resolve().parent.parent.parent.parent / "web"
        templates_dir = web_dir / "templates"
        static_dir = web_dir / "static"

        # Should not raise
        _run_self_test(engine, templates_dir, static_dir)
        engine.dispose()

    def test_self_test_fails_missing_tables(self, tmp_path):
        """Self-test fails when DB tables are missing."""
        db_path = tmp_path / "empty.db"
        engine = init_engine(f"sqlite:///{db_path}")
        # Don't create tables!

        from pathlib import Path

        web_dir = Path(__file__).resolve().parent.parent.parent.parent / "web"
        templates_dir = web_dir / "templates"
        static_dir = web_dir / "static"

        with pytest.raises(RuntimeError, match="Missing DB tables"):
            _run_self_test(engine, templates_dir, static_dir)
        engine.dispose()

    def test_self_test_fails_missing_static(self, tmp_path):
        """Self-test fails when static directory is missing."""
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)

        from pathlib import Path

        web_dir = Path(__file__).resolve().parent.parent.parent.parent / "web"
        templates_dir = web_dir / "templates"
        fake_static = tmp_path / "no_such_dir"

        with pytest.raises(RuntimeError, match="Static assets directory missing"):
            _run_self_test(engine, templates_dir, fake_static)
        engine.dispose()

    def test_self_test_fails_missing_templates(self, tmp_path):
        """Self-test fails when templates directory is missing."""
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)

        from pathlib import Path

        web_dir = Path(__file__).resolve().parent.parent.parent.parent / "web"
        static_dir = web_dir / "static"
        fake_templates = tmp_path / "no_such_dir"

        with pytest.raises(RuntimeError, match="Templates directory missing"):
            _run_self_test(engine, templates_dir=fake_templates, static_dir=static_dir)
        engine.dispose()

    def test_self_test_fails_missing_style_css(self, tmp_path):
        """Self-test fails when style.css is missing from static dir."""
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)

        from pathlib import Path

        web_dir = Path(__file__).resolve().parent.parent.parent.parent / "web"
        templates_dir = web_dir / "templates"

        # Create static dir without style.css
        empty_static = tmp_path / "static"
        empty_static.mkdir()

        with pytest.raises(RuntimeError, match="style.css not found"):
            _run_self_test(engine, templates_dir, empty_static)
        engine.dispose()

    def test_app_lifespan_runs_self_test(self, client):
        """The full app starts without self-test failure."""
        # If we get a valid response, the self-test passed during startup
        resp = client.get("/health")
        assert resp.status_code == 200


# ===================================================================
# 6. Integration — Cleanup runs on startup
# ===================================================================


class TestStartupCleanup:
    """Verify cleanup runs during app startup."""

    def test_stale_matches_cleaned_on_startup(self, tmp_path):
        """Stale matches are cleaned up when the app starts."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        # Pre-populate DB with a stale match
        engine = init_engine(db_url)
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()
        player = _create_player(session)
        stale_match = _create_match(session, player.id)
        stale_match.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        session.commit()
        match_id = stale_match.id
        session.close()
        engine.dispose()

        # Now start the app — cleanup should fire
        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app) as _client:
            # Verify the match was marked abandoned
            session = app.state.session_factory()
            try:
                match = session.query(Match).get(match_id)
                assert match.status == "abandoned"
            finally:
                session.close()


# ===================================================================
# 4. Per-Player Stale Match Cleanup (#2211)
# ===================================================================


class TestPlayerStaleMatchCleanup:
    """Per-player stale match cleanup on match creation."""

    def test_expire_player_stale_matches_basic(self):
        """Stale matches for a specific player are abandoned."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()

        player = _create_player(session)
        # Create a stale match (3 hours old — exceeds 2h threshold)
        stale = _create_match(session, player.id)
        stale.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        # Create a fresh match (30 min old — within threshold)
        fresh = _create_match(session, player.id)
        fresh.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        session.commit()

        count = expire_player_stale_matches(session, player.id)
        session.commit()

        assert count == 1
        session.refresh(stale)
        session.refresh(fresh)
        assert stale.status == "abandoned"
        assert fresh.status == "active"
        session.close()

    def test_expire_player_stale_only_affects_own_matches(self):
        """Cleanup only affects the target player's matches."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()

        player_a = _create_player(session)
        player_b = _create_player(session)
        # Both have stale matches
        stale_a = _create_match(session, player_a.id)
        stale_a.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        stale_b = _create_match(session, player_b.id)
        stale_b.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        session.commit()

        # Expire only player_a's matches
        count = expire_player_stale_matches(session, player_a.id)
        session.commit()

        assert count == 1
        session.refresh(stale_a)
        session.refresh(stale_b)
        assert stale_a.status == "abandoned"
        assert stale_b.status == "active"  # Untouched
        session.close()

    def test_player_cleanup_default_threshold(self):
        """Default threshold is 2 hours."""
        assert PLAYER_STALE_MATCH_AGE == timedelta(hours=2)

    def test_cleanup_runs_before_rate_limit_on_select_ai(self, tmp_path):
        """Stale matches are cleaned up before rate limit check in select_ai (#2211)."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        # Pre-populate: create a player with MAX active matches, all stale
        db_engine = init_engine(db_url)
        create_tables(db_engine)
        sf = make_session_factory(db_engine)
        session = sf()
        player = _create_player(session)
        for _ in range(MAX_ACTIVE_MATCHES_PER_PLAYER):
            m = _create_match(session, player.id)
            m.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        session.commit()
        link_uuid = player.link_uuid
        session.close()
        db_engine.dispose()

        # Start the app and try to select AI — should succeed because stale
        # matches are cleaned up before the rate limit check.
        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app) as client:
            resp = client.post(
                f"/play/{link_uuid}/select-ai",
                data={"model_id": "bud_bot"},
            )
            # Should succeed (200), not be rate-limited (429)
            assert resp.status_code == 200
