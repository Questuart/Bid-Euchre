"""Tests for the leaderboard stats aggregation and route.

Covers:
- PlayerStats computation from completed match/hand data
- Leaderboard ranking (sorted by net_eppd descending)
- Default and secondary column partitioning
- Access gating (404 for unknown UUIDs)
- Route integration via the FastAPI test client
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from web.db import Hand, Match, Player
from web.leaderboard import compute_player_stats, get_leaderboard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(session, *, nickname: str = "TestPlayer") -> Player:
    """Create a player with a unique link_uuid."""
    player = Player(link_uuid=str(uuid.uuid4()), nickname=nickname)
    session.add(player)
    session.flush()
    return player


def _make_match(
    session,
    player: Player,
    *,
    status: str = "complete",
    score_human: int = 52,
    score_ai: int = 30,
    hands_played: int = 10,
) -> Match:
    """Create a match for the given player."""
    match = Match(
        match_uuid=str(uuid.uuid4()),
        player_id=player.id,
        ai_model="heuristic",
        status=status,
        seed=42,
        score_human=score_human,
        score_ai=score_ai,
        hands_played=hands_played,
        match_state_json="{}",
        completed_at=datetime.now(timezone.utc) if status == "complete" else None,
    )
    session.add(match)
    session.flush()
    return match


def _make_hand(
    session,
    match: Match,
    *,
    hand_number: int = 0,
    status: str = "complete",
    bidder_seat: int | None = 0,
    winning_bid_n: int | None = 6,
    winning_bid_type: str | None = "regular",
    tricks_team0: int = 7,
    tricks_team1: int = 3,
    points_team0: int = 6,
    points_team1: int = 3,
) -> Hand:
    """Create a hand under the given match."""
    hand = Hand(
        match_id=match.id,
        hand_number=hand_number,
        deal_id=hand_number,
        dealer_seat=0,
        status=status,
        bidder_seat=bidder_seat,
        winning_bid_n=winning_bid_n,
        winning_bid_type=winning_bid_type,
        tricks_team0=tricks_team0,
        tricks_team1=tricks_team1,
        points_team0=points_team0,
        points_team1=points_team1,
        hand_state_json="{}",
        completed_at=datetime.now(timezone.utc) if status == "complete" else None,
    )
    session.add(hand)
    session.flush()
    return hand


# ---------------------------------------------------------------------------
# compute_player_stats tests
# ---------------------------------------------------------------------------


class TestComputePlayerStats:
    """Unit tests for compute_player_stats."""

    def test_returns_none_for_unknown_player(self, db_session):
        result = compute_player_stats(db_session, player_id=999)
        assert result is None

    def test_returns_none_for_no_completed_matches(self, db_session):
        player = _make_player(db_session)
        _make_match(db_session, player, status="active")
        result = compute_player_stats(db_session, player.id)
        assert result is None

    def test_basic_stats_single_match(self, db_session):
        player = _make_player(db_session, nickname="Alice")
        match = _make_match(
            db_session, player, score_human=52, score_ai=30, hands_played=5
        )

        # 3 hands where human team (seats 0,2) declared and made
        for i in range(3):
            _make_hand(
                db_session,
                match,
                hand_number=i,
                bidder_seat=0,
                winning_bid_n=6,
                tricks_team0=7,
                tricks_team1=3,
                points_team0=6,
                points_team1=3,
            )
        # 2 hands where AI team (seat 1) declared
        for i in range(3, 5):
            _make_hand(
                db_session,
                match,
                hand_number=i,
                bidder_seat=1,
                winning_bid_n=5,
                tricks_team0=4,
                tricks_team1=6,
                points_team0=4,
                points_team1=5,
            )

        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        assert stats.nickname == "Alice"
        assert stats.matches_played == 1
        assert stats.games_won == 1  # 52 > 30
        assert stats.win_rate == 1.0
        assert stats.hands_played == 5

        # net_eppd = (3*6 + 2*4 - 3*3 - 2*5) / 5 = (18+8-9-10)/5 = 7/5 = 1.4
        assert stats.net_eppd == 1.4

        # bid_rate = 3 declaring / 5 total
        assert stats.bid_rate == 0.6

        # make_rate = 3 made / 3 declaring (all made: 7 >= 6)
        assert stats.make_rate == 1.0

        # avg_bid_level = 6.0
        assert stats.avg_bid_level == 6.0

    def test_losing_match(self, db_session):
        player = _make_player(db_session)
        _make_match(db_session, player, score_human=20, score_ai=52)
        _make_hand(
            db_session,
            db_session.query(Match).first(),
            points_team0=-5,
            points_team1=5,
        )
        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        assert stats.games_won == 0
        assert stats.win_rate == 0.0
        assert stats.avg_margin_victory == 0.0  # no wins
        assert stats.net_eppd == -10.0  # (-5 - 5) / 1

    def test_moon_and_loner_stats(self, db_session):
        player = _make_player(db_session)
        match = _make_match(db_session, player)

        # Moon hand (human declares, makes)
        _make_hand(
            db_session,
            match,
            hand_number=0,
            bidder_seat=0,
            winning_bid_n=10,
            winning_bid_type="moon",
            tricks_team0=10,
            tricks_team1=0,
            points_team0=20,
            points_team1=0,
        )

        # Loner hand (human declares, set)
        _make_hand(
            db_session,
            match,
            hand_number=1,
            bidder_seat=2,  # partner seat, still team 0
            winning_bid_n=10,
            winning_bid_type="loner",
            tricks_team0=5,
            tricks_team1=5,
            points_team0=-10,
            points_team1=5,
        )

        # Regular hand
        _make_hand(
            db_session,
            match,
            hand_number=2,
            bidder_seat=1,  # AI declares
            winning_bid_n=5,
            winning_bid_type="regular",
            tricks_team0=4,
            tricks_team1=6,
            points_team0=4,
            points_team1=5,
        )

        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        assert stats.hands_played == 3
        assert stats.moon_call_rate == pytest.approx(1 / 3, abs=0.001)
        assert stats.moon_make_rate == 1.0  # 1 moon called, 1 made
        assert stats.loner_call_rate == pytest.approx(1 / 3, abs=0.001)
        assert stats.loner_make_rate == 0.0  # 1 loner called, 0 made (5 < 10)

    def test_multiple_matches(self, db_session):
        player = _make_player(db_session)

        # Match 1: win
        m1 = _make_match(
            db_session, player, score_human=52, score_ai=20, hands_played=5
        )
        for i in range(5):
            _make_hand(
                db_session,
                m1,
                hand_number=i,
                points_team0=6,
                points_team1=2,
            )

        # Match 2: loss
        m2 = _make_match(
            db_session, player, score_human=10, score_ai=52, hands_played=5
        )
        for i in range(5):
            _make_hand(
                db_session,
                m2,
                hand_number=i + 10,  # unique hand numbers
                points_team0=-2,
                points_team1=6,
            )

        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        assert stats.matches_played == 2
        assert stats.games_won == 1
        assert stats.win_rate == 0.5
        assert stats.hands_played == 10

        # net_eppd = (5*6 + 5*(-2) - 5*2 - 5*6) / 10 = (30-10-10-30)/10 = -2.0
        assert stats.net_eppd == -2.0

        # avg_match_margin: (52-20 + 10-52) / 2 = (32 + -42) / 2 = -5.0
        assert stats.avg_match_margin == -5.0

    def test_returns_dataclass_fields(self, db_session):
        """Verify all expected fields are present on PlayerStats."""
        player = _make_player(db_session)
        match = _make_match(db_session, player)
        _make_hand(db_session, match)
        db_session.flush()

        stats = compute_player_stats(db_session, player.id)
        assert stats is not None

        expected_fields = {
            "player_id",
            "nickname",
            "net_eppd",
            "games_won",
            "win_rate",
            "avg_margin_victory",
            "matches_played",
            "hands_played",
            "avg_match_margin",
            "bid_rate",
            "make_rate",
            "avg_bid_level",
            "moon_call_rate",
            "moon_make_rate",
            "loner_call_rate",
            "loner_make_rate",
        }
        actual_fields = {f.name for f in stats.__dataclass_fields__.values()}
        assert expected_fields == actual_fields


# ---------------------------------------------------------------------------
# get_leaderboard tests
# ---------------------------------------------------------------------------


class TestGetLeaderboard:
    """Tests for the leaderboard ranking function."""

    def test_empty_leaderboard(self, db_session):
        rankings = get_leaderboard(db_session)
        assert rankings == []

    def test_sorts_by_net_eppd_descending(self, db_session):
        # Player A: high net_eppd
        player_a = _make_player(db_session, nickname="HighEppd")
        match_a = _make_match(db_session, player_a, score_human=52, score_ai=10)
        _make_hand(db_session, match_a, points_team0=10, points_team1=2)

        # Player B: low net_eppd
        player_b = _make_player(db_session, nickname="LowEppd")
        match_b = _make_match(db_session, player_b, score_human=20, score_ai=52)
        _make_hand(
            db_session,
            match_b,
            hand_number=1,
            points_team0=-5,
            points_team1=5,
        )

        db_session.flush()
        rankings = get_leaderboard(db_session)

        assert len(rankings) == 2
        assert rankings[0].nickname == "HighEppd"
        assert rankings[1].nickname == "LowEppd"
        assert rankings[0].net_eppd > rankings[1].net_eppd

    def test_min_matches_filter(self, db_session):
        # Player with 1 match
        player = _make_player(db_session, nickname="OneMatch")
        match = _make_match(db_session, player)
        _make_hand(db_session, match)

        db_session.flush()

        # min_matches=1 includes them
        assert len(get_leaderboard(db_session, min_matches=1)) == 1

        # min_matches=2 excludes them
        assert len(get_leaderboard(db_session, min_matches=2)) == 0

    def test_excludes_active_only_players(self, db_session):
        player = _make_player(db_session, nickname="ActiveOnly")
        _make_match(db_session, player, status="active")
        db_session.flush()

        rankings = get_leaderboard(db_session)
        assert len(rankings) == 0


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


class TestLeaderboardRoute:
    """Route-level tests for GET /leaderboard/{link_uuid}."""

    @pytest.fixture()
    def app_and_client(self, tmp_path):
        """FastAPI test client with lifespan (DB, templates, AI loaded)."""
        from starlette.testclient import TestClient

        from tests.unit.hosted_play.conftest import make_hosted_play_test_config
        from web.app import create_app

        config = make_hosted_play_test_config(tmp_path)
        app = create_app(config)
        with TestClient(app) as client:
            yield app, client

    def test_leaderboard_returns_200_for_valid_player(self, app_and_client):
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="Tester")
            session.commit()
            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert "Leaderboard" in resp.text
        finally:
            session.close()

    def test_leaderboard_returns_404_for_unknown_uuid(self, app_and_client):
        _app, client = app_and_client
        resp = client.get(f"/leaderboard/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_leaderboard_shows_rankings(self, app_and_client):
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="RankedPlayer")
            match = _make_match(session, player, score_human=52, score_ai=20)
            _make_hand(
                session,
                match,
                points_team0=5,
                points_team1=2,
            )
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert "RankedPlayer" in resp.text
            assert "Net EPPD" in resp.text
        finally:
            session.close()

    def test_leaderboard_shows_empty_message(self, app_and_client):
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="NewPlayer")
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert "No completed matches yet" in resp.text
        finally:
            session.close()
