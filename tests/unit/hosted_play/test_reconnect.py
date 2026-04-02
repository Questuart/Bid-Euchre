"""Tests for session reconnect — cookie-based active match detection.

Covers:
1. Middleware helpers: cookie extraction, player lookup, cookie setting
2. Landing page reconnect detection (cookie present → reconnect prompt)
3. Landing page fallback (no cookie or no active match → invite form)
4. Cookie setting on successful code redemption
5. Cookie setting on legacy /new route
"""

from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import (
    create_test_invite_code,
    create_test_match,
    create_test_player,
    make_hosted_play_test_config,
)
from web.app import create_app
from web.middleware import (
    PLAYER_COOKIE_NAME,
    lookup_active_match,
    set_player_cookie,
)

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


def _get_session_factory(client):
    """Get session_factory from a started app (via client)."""
    return client.app.state.session_factory


# ===================================================================
# 1. Middleware Helpers — Unit Tests
# ===================================================================


class TestSetPlayerCookie:
    """set_player_cookie attaches the correct cookie to a response."""

    def test_cookie_is_set_on_response(self):
        """Cookie appears in response with correct attributes."""
        from fastapi.responses import JSONResponse

        resp = JSONResponse(content={})
        link = str(uuid.uuid4())
        set_player_cookie(resp, link)

        raw_headers = dict(resp.headers)
        assert "set-cookie" in raw_headers
        cookie_header = raw_headers["set-cookie"]
        assert PLAYER_COOKIE_NAME in cookie_header
        assert link in cookie_header
        assert "httponly" in cookie_header.lower()
        assert "samesite=lax" in cookie_header.lower()


class TestLookupActiveMatch:
    """lookup_active_match finds the player's active match from the DB."""

    def test_returns_none_for_unknown_player(self, client):
        """Unknown link_uuid → None."""
        session = _get_session_factory(client)()
        try:
            result = lookup_active_match(session, "nonexistent-uuid")
            assert result is None
        finally:
            session.close()

    def test_returns_none_when_no_nickname(self, client):
        """Player without nickname → None (incomplete onboarding)."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname=None)
            create_test_match(session, player_id=player.id, status="active")
            session.commit()

            result = lookup_active_match(session, player.link_uuid)
            assert result is None
        finally:
            session.close()

    def test_returns_none_when_no_active_match(self, client):
        """Player with only completed matches → None."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="Alice")
            create_test_match(session, player_id=player.id, status="complete")
            session.commit()

            result = lookup_active_match(session, player.link_uuid)
            assert result is None
        finally:
            session.close()

    def test_returns_match_info_when_active(self, client):
        """Player with active match → dict with link_uuid, nickname, match_uuid."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="Bob")
            match = create_test_match(session, player_id=player.id, status="active")
            session.commit()

            result = lookup_active_match(session, player.link_uuid)
            assert result is not None
            assert result["link_uuid"] == player.link_uuid
            assert result["nickname"] == "Bob"
            assert result["match_uuid"] == match.match_uuid
        finally:
            session.close()


# ===================================================================
# 2. Landing Page — Reconnect Detection
# ===================================================================


class TestLandingReconnect:
    """Landing page shows reconnect prompt when cookie indicates active match."""

    def _setup_player_with_active_match(self, client):
        """Create a player with nickname and active match, return link_uuid."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="ReconnectPlayer")
            create_test_match(session, player_id=player.id, status="active")
            session.commit()
            return player.link_uuid
        finally:
            session.close()

    def test_reconnect_prompt_shown(self, client):
        """Cookie with active match → reconnect prompt rendered."""
        link_uuid = self._setup_player_with_active_match(client)
        client.cookies.set(PLAYER_COOKIE_NAME, link_uuid)

        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "reconnect-prompt" in body
        assert "Welcome back" in body
        assert "ReconnectPlayer" in body
        assert f"/play/{link_uuid}" in body

    def test_invite_form_when_no_cookie(self, client):
        """No cookie → standard invite code form."""
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "invite-code-form" in body
        assert "reconnect-prompt" not in body

    def test_invite_form_when_stale_cookie(self, client):
        """Cookie with unknown player → standard invite code form."""
        client.cookies.set(PLAYER_COOKIE_NAME, "nonexistent-uuid-12345")
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "invite-code-form" in body
        assert "reconnect-prompt" not in body

    def test_invite_form_when_no_active_match(self, client):
        """Cookie for player with only completed matches → invite form."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="DonePlayer")
            create_test_match(session, player_id=player.id, status="complete")
            session.commit()
            link_uuid = player.link_uuid
        finally:
            session.close()

        client.cookies.set(PLAYER_COOKIE_NAME, link_uuid)
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "invite-code-form" in body
        assert "reconnect-prompt" not in body

    def test_reconnect_has_different_code_option(self, client):
        """Reconnect prompt includes a 'Use Different Code' fallback."""
        link_uuid = self._setup_player_with_active_match(client)
        client.cookies.set(PLAYER_COOKIE_NAME, link_uuid)

        resp = client.get("/")
        body = resp.text
        assert "invite-code-fallback" in body
        assert "Use Different Code" in body


# ===================================================================
# 3. Cookie Setting on Code Redemption
# ===================================================================


class TestCookieOnRedemption:
    """Invite code redemption sets the player session cookie."""

    def test_cookie_set_on_new_code_entry(self, client):
        """Entering a fresh invite code sets the player cookie."""
        session = _get_session_factory(client)()
        try:
            invite = create_test_invite_code(session)
            session.commit()
            code = invite.code
        finally:
            session.close()

        resp = client.post(
            "/enter-code",
            data={"code": code},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 200)
        cookie_header = resp.headers.get("set-cookie", "")
        assert PLAYER_COOKIE_NAME in cookie_header

    def test_cookie_set_on_redeemed_code_reentry(self, client):
        """Re-entering an already-redeemed code still sets the cookie."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="ExistingPlayer")
            invite = create_test_invite_code(
                session,
                status="redeemed",
                player_id=player.id,
            )
            session.commit()
            code = invite.code
        finally:
            session.close()

        resp = client.post(
            "/enter-code",
            data={"code": code},
            follow_redirects=False,
        )
        cookie_header = resp.headers.get("set-cookie", "")
        assert PLAYER_COOKIE_NAME in cookie_header


# ===================================================================
# 4. Cookie Setting on Legacy /new Route
# ===================================================================


class TestCookieOnLegacyNew:
    """Legacy /new route sets the player session cookie."""

    def test_cookie_set_on_new(self, client):
        """POST /new sets the player cookie on the redirect response."""
        resp = client.post("/new", follow_redirects=False)
        assert resp.status_code == 302
        cookie_header = resp.headers.get("set-cookie", "")
        assert PLAYER_COOKIE_NAME in cookie_header


# ===================================================================
# 5. Cookie Clobber Protection (Fixes #2069)
# ===================================================================


class TestCookieClobberProtection:
    """Visiting /play/{link_uuid} should not clobber an existing cookie
    belonging to a different player.

    Uses players with nicknames but no matches — the cookie logic fires
    before match rendering, so model_select is sufficient to test the
    cookie behavior.
    """

    def test_no_clobber_when_different_cookie_exists(self, client):
        """Existing cookie for player A is NOT overwritten when visiting player B's game page."""
        session = _get_session_factory(client)()
        try:
            player_a = create_test_player(session, nickname="Alice")
            player_b = create_test_player(session, nickname="Bob")
            session.commit()
            link_a = player_a.link_uuid
            link_b = player_b.link_uuid
        finally:
            session.close()

        # Alice has her cookie set
        client.cookies.set(PLAYER_COOKIE_NAME, link_a)

        # Alice visits Bob's game page (e.g. shared link)
        resp = client.get(f"/play/{link_b}", follow_redirects=False)
        assert resp.status_code == 200

        # The response should NOT set a cookie (no clobbering)
        cookie_header = resp.headers.get("set-cookie", "")
        assert (
            link_b not in cookie_header
        ), "Cookie should not be clobbered with a different player's link"

    def test_cookie_set_when_no_existing_cookie(self, client):
        """Cookie IS set when visiting /play/ with no existing cookie."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="Charlie")
            session.commit()
            link = player.link_uuid
        finally:
            session.close()

        # No cookie set — visiting the game page should backfill it
        resp = client.get(f"/play/{link}", follow_redirects=False)
        assert resp.status_code == 200
        cookie_header = resp.headers.get("set-cookie", "")
        assert link in cookie_header, "Cookie should be set for first-time visitors"

    def test_cookie_preserved_when_same_player(self, client):
        """Cookie IS refreshed when visiting own game page."""
        session = _get_session_factory(client)()
        try:
            player = create_test_player(session, nickname="Diana")
            session.commit()
            link = player.link_uuid
        finally:
            session.close()

        # Diana has her own cookie and visits her own game
        client.cookies.set(PLAYER_COOKIE_NAME, link)
        resp = client.get(f"/play/{link}", follow_redirects=False)
        assert resp.status_code == 200
        cookie_header = resp.headers.get("set-cookie", "")
        assert (
            link in cookie_header
        ), "Cookie should be refreshed for same-player visits"
