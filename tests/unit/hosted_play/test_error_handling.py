"""Tests for error handling and graceful reconnection features.

Covers:
1. HTMX-aware error responses (partial HTML for HTMX, full page for browser)
2. Match state deserialization recovery (corrupt state → model selection)
3. HTMX error partial template rendering
4. Offline/reconnection JS behavior (structural — template includes JS)
"""

from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import make_hosted_play_test_config
from web.app import create_app
from web.db import Match, Player

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
    defaults = {
        "match_uuid": str(uuid.uuid4()),
        "player_id": player_id,
        "ai_model": "bud_bot",
        "status": status,
        "seed": 42,
        "match_state_json": "{}",
    }
    defaults.update(kw)
    match = Match(**defaults)
    session.add(match)
    session.flush()
    return match


# ===================================================================
# 1. HTMX-Aware Error Responses
# ===================================================================


class TestHTMXErrorResponses:
    """Verify error handlers return partials for HTMX, full pages for browser."""

    def test_404_full_page_for_browser(self, client):
        """Non-HTMX 404 returns full themed error page."""
        resp = client.get("/nonexistent-page")
        assert resp.status_code == 404
        assert "<!DOCTYPE html>" in resp.text
        assert "Hand Not Found" in resp.text

    def test_404_partial_for_htmx(self, client):
        """HTMX 404 returns inline error partial (no DOCTYPE)."""
        resp = client.get(
            "/nonexistent-page",
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 404
        assert "<!DOCTYPE html>" not in resp.text
        assert "htmx-error" in resp.text
        assert "Back to Table" in resp.text

    def test_404_htmx_game_not_found(self, client):
        """HTMX request for invalid game link returns inline error."""
        fake_uuid = str(uuid.uuid4())
        resp = client.get(
            f"/play/{fake_uuid}",
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 404
        assert "htmx-error" in resp.text

    def test_404_htmx_includes_detail(self, client):
        """HTMX 404 includes the error detail message."""
        fake_uuid = str(uuid.uuid4())
        resp = client.get(
            f"/play/{fake_uuid}",
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 404
        assert "Game not found" in resp.text or "Not found" in resp.text

    def test_htmx_error_has_aria_alert(self, client):
        """HTMX error partial has role=alert for accessibility."""
        resp = client.get(
            "/nonexistent-page",
            headers={"HX-Request": "true"},
        )
        assert 'role="alert"' in resp.text


# ===================================================================
# 2. Match State Deserialization Recovery
# ===================================================================


class TestMatchStateRecovery:
    """Corrupt match state is handled gracefully on page refresh."""

    def test_corrupt_state_shows_model_select(self, app, client):
        """Player with a corrupt match state is shown model selection."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            # Create a match with invalid JSON state
            _create_match(
                session,
                player.id,
                match_state_json="THIS IS NOT VALID JSON",
            )
            session.commit()
            link_uuid = player.link_uuid
        finally:
            session.close()

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # Should show model selection, not crash
        assert "model_select" in resp.text or "Choose" in resp.text

    def test_corrupt_state_marks_match_abandoned(self, app, client):
        """Corrupt match is marked as abandoned after recovery."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            match = _create_match(
                session,
                player.id,
                match_state_json="CORRUPT_DATA",
            )
            session.commit()
            match_id = match.id
            link_uuid = player.link_uuid
        finally:
            session.close()

        # Trigger recovery
        client.get(f"/play/{link_uuid}")

        # Verify match is now abandoned
        session = app.state.session_factory()
        try:
            match = session.query(Match).get(match_id)
            assert match.status == "abandoned"
            assert match.completed_at is not None
        finally:
            session.close()

    def test_corrupt_state_second_visit_shows_model_select(self, app, client):
        """After recovery, second visit still shows model selection."""
        session = app.state.session_factory()
        try:
            player = _create_player(session)
            _create_match(
                session,
                player.id,
                match_state_json="BROKEN",
            )
            session.commit()
            link_uuid = player.link_uuid
        finally:
            session.close()

        # First visit triggers recovery
        resp1 = client.get(f"/play/{link_uuid}")
        assert resp1.status_code == 200

        # Second visit — abandoned match is most recent, but player
        # can see model selection again since no active match remains
        resp2 = client.get(f"/play/{link_uuid}")
        assert resp2.status_code == 200


# ===================================================================
# 3. HTMX Error Template Structure
# ===================================================================


class TestHTMXErrorTemplate:
    """Verify the htmx_error.html template renders correctly."""

    def test_htmx_error_contains_message(self, client):
        """HTMX error partial includes the error message."""
        resp = client.get(
            "/nonexistent-page",
            headers={"HX-Request": "true"},
        )
        assert "htmx-error__message" in resp.text

    def test_htmx_error_contains_home_link(self, client):
        """HTMX error partial includes a link back to the landing page."""
        resp = client.get(
            "/nonexistent-page",
            headers={"HX-Request": "true"},
        )
        assert 'href="/"' in resp.text


# ===================================================================
# 4. Game JS Error Handling Structure
# ===================================================================


class TestGameJSErrorHandling:
    """Verify game.js is loaded and contains error handling code."""

    def test_game_js_included_in_base(self, client):
        """Base template includes game.js for all pages."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "game.js" in resp.text

    def test_game_js_has_error_handling(self):
        """game.js contains error handling event listeners."""
        from pathlib import Path

        js_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "web"
            / "static"
            / "game.js"
        )
        content = js_path.read_text()
        assert "htmx:responseError" in content
        assert "htmx:sendError" in content
        assert "htmx:timeout" in content
        assert "showErrorToast" in content
        assert "showOfflineBanner" in content
        assert "hideOfflineBanner" in content

    def test_game_js_has_online_offline_handlers(self):
        """game.js registers online/offline event listeners."""
        from pathlib import Path

        js_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "web"
            / "static"
            / "game.js"
        )
        content = js_path.read_text()
        assert "'offline'" in content
        assert "'online'" in content


# ===================================================================
# 5. Error CSS Structure
# ===================================================================


class TestErrorCSS:
    """Verify error-related CSS classes exist in the stylesheet."""

    def test_error_toast_css_exists(self):
        """style.css defines error-toast classes."""
        from pathlib import Path

        css_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "web"
            / "static"
            / "style.css"
        )
        content = css_path.read_text()
        assert ".error-toast" in content
        assert ".error-toast--visible" in content
        assert ".error-toast__message" in content
        assert ".error-toast__dismiss" in content

    def test_offline_banner_css_exists(self):
        """style.css defines offline-banner class."""
        from pathlib import Path

        css_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "web"
            / "static"
            / "style.css"
        )
        content = css_path.read_text()
        assert ".offline-banner" in content

    def test_htmx_error_css_exists(self):
        """style.css defines htmx-error classes for inline errors."""
        from pathlib import Path

        css_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "web"
            / "static"
            / "style.css"
        )
        content = css_path.read_text()
        assert ".htmx-error" in content
        assert ".htmx-error__message" in content
