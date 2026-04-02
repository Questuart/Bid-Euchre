"""Tests for the comments board feature.

Covers:
- Comment model creation and constraints
- GET /comments/{link_uuid} page rendering
- GET /comments/{link_uuid}/list HTMX partial
- POST /play/{link_uuid}/comment submission
- Validation (empty, too long, unknown player)
- Newest-first ordering
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.unit.hosted_play.conftest import (
    create_test_player,
    make_hosted_play_test_config,
)
from web.app import create_app
from web.db import Comment

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path):
    return make_hosted_play_test_config(tmp_path)


@pytest.fixture()
def app(config):
    return create_app(config=config)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def _create_player(app, nickname: str | None = "Tester") -> str:
    """Create a player directly in the DB, return link_uuid."""
    session = app.state.session_factory()
    try:
        player = create_test_player(session, nickname=nickname)
        session.commit()
        return player.link_uuid
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Comment model tests
# ---------------------------------------------------------------------------


class TestCommentModel:
    """Test Comment DB model constraints."""

    def test_create_comment(self, client, app):
        """Comment with valid content is persisted."""
        session = app.state.session_factory()
        try:
            player = create_test_player(session, nickname="Alice")
            session.commit()

            comment = Comment(player_id=player.id, content="Great game!")
            session.add(comment)
            session.commit()

            saved = session.query(Comment).first()
            assert saved is not None
            assert saved.content == "Great game!"
            assert saved.player_id == player.id
            assert saved.created_at is not None
            assert saved.match_id is None
        finally:
            session.close()

    def test_comment_repr(self, client, app):
        """Comment repr includes id and player_id."""
        session = app.state.session_factory()
        try:
            player = create_test_player(session, nickname="Alice")
            session.commit()

            comment = Comment(player_id=player.id, content="Test")
            session.add(comment)
            session.commit()

            assert "Comment" in repr(comment)
            assert str(comment.player_id) in repr(comment)
        finally:
            session.close()


# ---------------------------------------------------------------------------
# GET /comments/{link_uuid} — full page
# ---------------------------------------------------------------------------


class TestCommentsPage:
    """Test the comments page route."""

    def test_comments_page_renders(self, client, app):
        """Comments page renders for a valid player."""
        link_uuid = _create_player(app, "Alice")
        resp = client.get(f"/comments/{link_uuid}")
        assert resp.status_code == 200
        assert "Comments" in resp.text
        assert "No comments yet" in resp.text

    def test_comments_page_shows_comments(self, client, app):
        """Comments page shows existing comments."""
        link_uuid = _create_player(app, "Alice")

        # Post a comment first
        client.post(
            f"/play/{link_uuid}/comment",
            data={"content": "Hello world!"},
        )

        resp = client.get(f"/comments/{link_uuid}")
        assert resp.status_code == 200
        assert "Hello world!" in resp.text
        assert "Alice" in resp.text

    def test_comments_page_unknown_player(self, client):
        """Unknown link_uuid returns 404."""
        resp = client.get("/comments/nonexistent-uuid")
        assert resp.status_code == 404

    def test_comments_tab_active(self, client, app):
        """Comments tab is marked active on comments page."""
        link_uuid = _create_player(app, "Alice")
        resp = client.get(f"/comments/{link_uuid}")
        assert "header-nav__tab--active" in resp.text
        # Check that the active tab is the Comments one
        assert f'/comments/{link_uuid}"' in resp.text


# ---------------------------------------------------------------------------
# GET /comments/{link_uuid}/list — HTMX partial
# ---------------------------------------------------------------------------


class TestCommentsListPartial:
    """Test the HTMX comments list partial."""

    def test_empty_list(self, client, app):
        """Empty comment list shows placeholder."""
        link_uuid = _create_player(app, "Alice")
        resp = client.get(f"/comments/{link_uuid}/list")
        assert resp.status_code == 200
        assert "No comments yet" in resp.text

    def test_list_with_comments(self, client, app):
        """Comment list shows posted comments."""
        link_uuid = _create_player(app, "Alice")

        # Post comments
        client.post(f"/play/{link_uuid}/comment", data={"content": "First!"})
        client.post(f"/play/{link_uuid}/comment", data={"content": "Second!"})

        resp = client.get(f"/comments/{link_uuid}/list")
        assert resp.status_code == 200
        assert "First!" in resp.text
        assert "Second!" in resp.text

    def test_unknown_player_returns_404(self, client):
        """Unknown link_uuid returns 404."""
        resp = client.get("/comments/nonexistent-uuid/list")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /play/{link_uuid}/comment — submission
# ---------------------------------------------------------------------------


class TestPostComment:
    """Test comment submission."""

    def test_post_comment_success(self, client, app):
        """Valid comment is saved and redirects (non-HTMX)."""
        link_uuid = _create_player(app, "Alice")
        resp = client.post(
            f"/play/{link_uuid}/comment",
            data={"content": "Nice hand!"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert f"/comments/{link_uuid}" in resp.headers["location"]

        # Verify comment was saved
        session = app.state.session_factory()
        try:
            count = session.query(Comment).count()
            assert count == 1
            comment = session.query(Comment).first()
            assert comment.content == "Nice hand!"
        finally:
            session.close()

    def test_post_comment_htmx(self, client, app):
        """HTMX submission returns the updated list partial."""
        link_uuid = _create_player(app, "Alice")
        resp = client.post(
            f"/play/{link_uuid}/comment",
            data={"content": "HTMX comment"},
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "HTMX comment" in resp.text
        assert "Alice" in resp.text

    def test_post_comment_strips_whitespace(self, client, app):
        """Leading/trailing whitespace is stripped."""
        link_uuid = _create_player(app, "Alice")
        client.post(
            f"/play/{link_uuid}/comment",
            data={"content": "  trimmed  "},
            headers={"HX-Request": "true"},
        )

        session = app.state.session_factory()
        try:
            comment = session.query(Comment).first()
            assert comment is not None
            assert comment.content == "trimmed"
        finally:
            session.close()

    def test_post_comment_too_long(self, client, app):
        """Comment exceeding max length is rejected (no DB insert)."""
        link_uuid = _create_player(app, "Alice")
        long_content = "x" * 501
        resp = client.post(
            f"/play/{link_uuid}/comment",
            data={"content": long_content},
            headers={"HX-Request": "true"},
        )
        # Should still return 200 (HTMX) but not save
        assert resp.status_code == 200

        session = app.state.session_factory()
        try:
            assert session.query(Comment).count() == 0
        finally:
            session.close()

    def test_post_empty_comment(self, client, app):
        """Whitespace-only comment is rejected."""
        link_uuid = _create_player(app, "Alice")
        resp = client.post(
            f"/play/{link_uuid}/comment",
            data={"content": "   "},
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200

        session = app.state.session_factory()
        try:
            assert session.query(Comment).count() == 0
        finally:
            session.close()

    def test_post_comment_unknown_player(self, client):
        """Comment from unknown player returns 404."""
        resp = client.post(
            "/play/nonexistent-uuid/comment",
            data={"content": "Hello"},
        )
        assert resp.status_code == 404

    def test_comments_newest_first(self, client, app):
        """Comments are ordered newest first."""
        link_uuid = _create_player(app, "Alice")

        client.post(f"/play/{link_uuid}/comment", data={"content": "First"})
        client.post(f"/play/{link_uuid}/comment", data={"content": "Second"})
        client.post(f"/play/{link_uuid}/comment", data={"content": "Third"})

        resp = client.get(f"/comments/{link_uuid}/list")
        text = resp.text
        # "Third" should appear before "First" in the HTML
        assert text.index("Third") < text.index("First")

    def test_comments_from_multiple_players(self, client, app):
        """Comments from different players show correct nicknames."""
        link_uuid_a = _create_player(app, "Alice")
        link_uuid_b = _create_player(app, "Bob")

        client.post(f"/play/{link_uuid_a}/comment", data={"content": "Hi from Alice"})
        client.post(f"/play/{link_uuid_b}/comment", data={"content": "Hi from Bob"})

        resp = client.get(f"/comments/{link_uuid_a}/list")
        assert "Alice" in resp.text
        assert "Bob" in resp.text
        assert "Hi from Alice" in resp.text
        assert "Hi from Bob" in resp.text

    def test_anonymous_player_comment(self, client, app):
        """Player without nickname shows as Anonymous."""
        link_uuid = _create_player(app, nickname=None)

        client.post(
            f"/play/{link_uuid}/comment",
            data={"content": "Anon here"},
            headers={"HX-Request": "true"},
        )

        resp = client.get(f"/comments/{link_uuid}/list")
        assert "Anonymous" in resp.text
        assert "Anon here" in resp.text
