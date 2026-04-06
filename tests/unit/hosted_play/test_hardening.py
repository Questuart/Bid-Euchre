"""Tests for B8 pilot launch hardening features.

Covers:
1. Abandon-on-create for prior active matches (#2467)
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
    abandon_player_active_matches,
    expire_stale_matches,
)
from web.db import (
    Match,
    Player,
    create_tables,
    init_engine,
    make_session_factory,
)

# Number of prior active matches to create in tests that verify the
# abandon-on-create behavior (historically tied to the removed
# MAX_ACTIVE_MATCHES_PER_PLAYER constant; now a plain test constant).
_PRIOR_ACTIVE_MATCHES = 5

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
    """Insert a Player row (onboarding already complete)."""
    player = Player(
        link_uuid=str(uuid.uuid4()),
        nickname=nickname,
        onboarding_complete=1,
    )
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
# 1. Abandon-on-create for prior active matches (#2467)
# ===================================================================


class TestSelectAiAbandonsPriorMatches:
    """select_ai abandons all prior active matches (#2467)."""

    def test_select_ai_abandons_prior_active_matches(self, client, app):
        """POST /play/{uuid}/select-ai abandons all active matches and
        creates a new one (#2467).

        The historical per-player rate limit (``check_match_limit`` /
        ``MAX_ACTIVE_MATCHES_PER_PLAYER``) was removed because select_ai
        now abandons all active matches before creating the new match —
        there can never be more than one active match per player.
        """
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            for _ in range(_PRIOR_ACTIVE_MATCHES):
                _create_match(session, player.id)
            session.commit()
            link_uuid = player.link_uuid
        finally:
            session.close()

        resp = client.post(
            f"/play/{link_uuid}/select-ai",
            data={"model_id": "olsa"},
        )
        # Should succeed — all prior active matches are abandoned first
        assert resp.status_code == 200

        # Verify: exactly one active match remains (the new one)
        session = app.state.session_factory()
        try:
            active = (
                session.query(Match)
                .filter_by(player_id=player.id, status="active")
                .all()
            )
            assert len(active) == 1

            # All others should be abandoned
            abandoned = (
                session.query(Match)
                .filter_by(player_id=player.id, status="abandoned")
                .all()
            )
            assert len(abandoned) == _PRIOR_ACTIVE_MATCHES
        finally:
            session.close()


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
# 4. Prior-match cleanup on select-ai (#2211, superseded by #2467)
# ===================================================================


class TestSelectAiRecoversFromPriorActiveMatches:
    """select_ai recovers from pre-existing active matches (#2211, #2467).

    Historical note: #2211 added an age-based per-player cleanup that
    ran before the per-player rate limit check. #2467 replaced both
    with an unconditional ``abandon_player_active_matches`` call, and
    the dead helpers were removed in #2500. This integration test
    continues to prove the end-to-end behavior: a player with many
    pre-existing active matches can still start a new one.
    """

    def test_select_ai_succeeds_with_many_prior_active_matches(self, tmp_path):
        """Select-ai succeeds even when the player has many prior active matches."""
        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        # Pre-populate: create a player with several prior active matches.
        db_engine = init_engine(db_url)
        create_tables(db_engine)
        sf = make_session_factory(db_engine)
        session = sf()
        player = _create_player(session)
        for _ in range(_PRIOR_ACTIVE_MATCHES):
            m = _create_match(session, player.id)
            m.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        session.commit()
        link_uuid = player.link_uuid
        session.close()
        db_engine.dispose()

        # Start the app and try to select AI — should succeed because
        # abandon_player_active_matches clears the prior matches first.
        config = make_hosted_play_test_config(tmp_path, database_url=db_url)
        app = create_app(config=config)
        with TestClient(app) as client:
            resp = client.post(
                f"/play/{link_uuid}/select-ai",
                data={"model_id": "bud_bot"},
            )
            # Should succeed (200), not be rate-limited (429)
            assert resp.status_code == 200


# ===================================================================
# 7. Abandon all active matches for a player (#2467)
# ===================================================================


class TestAbandonPlayerActiveMatches:
    """abandon_player_active_matches marks ALL active matches as abandoned,
    regardless of age (#2467)."""

    def test_abandons_all_active_matches(self):
        """All active matches for a player are abandoned, including recent ones."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()

        player = _create_player(session)
        # Create matches of varying ages — all should be abandoned
        recent = _create_match(session, player.id)
        recent.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        old = _create_match(session, player.id)
        old.created_at = datetime.now(timezone.utc) - timedelta(hours=3)
        session.commit()

        count = abandon_player_active_matches(session, player.id)
        session.commit()

        assert count == 2
        session.refresh(recent)
        session.refresh(old)
        assert recent.status == "abandoned"
        assert recent.completed_at is not None
        assert old.status == "abandoned"
        assert old.completed_at is not None
        session.close()

    def test_does_not_touch_other_players(self):
        """Only the specified player's matches are abandoned."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()

        player_a = _create_player(session)
        player_b = _create_player(session)
        match_a = _create_match(session, player_a.id)
        match_b = _create_match(session, player_b.id)
        session.commit()

        count = abandon_player_active_matches(session, player_a.id)
        session.commit()

        assert count == 1
        session.refresh(match_a)
        session.refresh(match_b)
        assert match_a.status == "abandoned"
        assert match_b.status == "active"  # Untouched
        session.close()

    def test_skips_completed_and_abandoned_matches(self):
        """Only active matches are affected — complete/abandoned are unchanged."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()

        player = _create_player(session)
        active = _create_match(session, player.id)
        complete = _create_match(session, player.id)
        complete.status = "complete"
        already_abandoned = _create_match(session, player.id)
        already_abandoned.status = "abandoned"
        session.commit()

        count = abandon_player_active_matches(session, player.id)
        session.commit()

        assert count == 1
        session.refresh(active)
        session.refresh(complete)
        session.refresh(already_abandoned)
        assert active.status == "abandoned"
        assert complete.status == "complete"
        assert already_abandoned.status == "abandoned"
        session.close()

    def test_returns_zero_when_no_active_matches(self):
        """Returns 0 when the player has no active matches."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        sf = make_session_factory(engine)
        session = sf()

        player = _create_player(session)
        session.commit()

        count = abandon_player_active_matches(session, player.id)
        assert count == 0
        session.close()
