"""Tests for the leaderboard stats aggregation and route.

Covers:
- PlayerStats computation from match/hand data (active + completed matches)
- In-progress match hand inclusion (live updates)
- Leaderboard ranking (sorted by net_eppd descending)
- Default and secondary column partitioning
- Metric definitions and formatting helpers
- Access gating (404 for unknown UUIDs)
- Route integration via the FastAPI test client
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from web.db import Hand, Match, Player
from web.leaderboard import (
    EXCLUDED_TEST_PLAYERS,
    METRIC_DEFINITIONS,
    PlayerStats,
    compute_ai_stats,
    compute_player_stats,
    format_metric,
    get_leaderboard,
    is_excluded_test_player,
)

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

    def test_returns_none_for_no_completed_hands(self, db_session):
        """Active match with no completed hands → None."""
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
            bidder_seat=0,  # human seat
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

    def test_ai_partner_moon_loner_included_in_team_stats(self, db_session):
        """Moon/loner declared by AI partner (seat 2) counts toward the
        human team's moon/loner stats — team-level for comparability with
        AI leaderboard rows (#2173, supersedes #2152)."""
        player = _make_player(db_session)
        match = _make_match(db_session, player)

        # AI partner declares moon (seat 2) — counts as team 0
        _make_hand(
            db_session,
            match,
            hand_number=0,
            bidder_seat=2,  # AI partner
            winning_bid_n=10,
            winning_bid_type="moon",
            tricks_team0=10,
            tricks_team1=0,
            points_team0=20,
            points_team1=0,
        )

        # AI partner declares loner (seat 2) — counts as team 0
        _make_hand(
            db_session,
            match,
            hand_number=1,
            bidder_seat=2,  # AI partner
            winning_bid_n=10,
            winning_bid_type="loner",
            tricks_team0=8,
            tricks_team1=2,
            points_team0=10,
            points_team1=2,
        )

        # Regular hand by human (baseline)
        _make_hand(
            db_session,
            match,
            hand_number=2,
            bidder_seat=0,
            winning_bid_n=6,
            winning_bid_type="regular",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=6,
            points_team1=3,
        )

        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        assert stats.hands_played == 3

        # Team-level moon/loner stats include AI partner (seat 2)
        assert stats.moon_call_rate == pytest.approx(1 / 3, abs=0.001)
        assert stats.moon_make_rate == 1.0  # 1 moon called (seat 2), made
        assert stats.loner_call_rate == pytest.approx(1 / 3, abs=0.001)
        assert stats.loner_make_rate == 0.0  # 1 loner called (seat 2), missed

        # Team-level bid stats also include partner (seat 2)
        # Declaring hands: seats 2, 2, 0 — all team 0 = 3/3
        assert stats.bid_rate == 1.0

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

    def test_includes_hands_from_active_match(self, db_session):
        """Hands from an active (in-progress) match are included in stats."""
        player = _make_player(db_session, nickname="InProgress")
        match = _make_match(
            db_session, player, status="active", score_human=0, score_ai=0
        )

        _make_hand(
            db_session,
            match,
            hand_number=0,
            bidder_seat=0,
            winning_bid_n=6,
            tricks_team0=7,
            tricks_team1=3,
            points_team0=6,
            points_team1=3,
        )
        _make_hand(
            db_session,
            match,
            hand_number=1,
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
        assert stats.nickname == "InProgress"
        assert stats.hands_played == 2
        # No completed matches → match-level stats are zero
        assert stats.matches_played == 0
        assert stats.games_won == 0
        assert stats.win_rate == 0.0
        assert stats.avg_match_margin == 0.0

        # Hand-level stats are computed from the active match's hands
        # net_eppd = ((6 - 3) + (4 - 5)) / 2 = (3 + -1) / 2 = 1.0
        assert stats.net_eppd == 1.0
        # bid_rate = 1 declaring / 2 total
        assert stats.bid_rate == 0.5

    def test_includes_hands_from_abandoned_match(self, db_session):
        """Hands from an abandoned match are retained in leaderboard stats."""
        player = _make_player(db_session, nickname="AbandonedPlayer")
        match = _make_match(
            db_session, player, status="abandoned", score_human=10, score_ai=5
        )

        _make_hand(
            db_session,
            match,
            hand_number=0,
            bidder_seat=0,
            winning_bid_n=6,
            tricks_team0=7,
            tricks_team1=3,
            points_team0=6,
            points_team1=3,
        )

        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        assert stats.nickname == "AbandonedPlayer"
        assert stats.hands_played == 1
        # Abandoned matches don't count as completed for matches_played
        assert stats.matches_played == 0
        # Hand-level stats are computed from the abandoned match's hands
        assert stats.net_eppd == 3.0  # (6 - 3) / 1

    def test_mixes_active_and_completed_match_hands(self, db_session):
        """Hands from both active and completed matches combine in stats."""
        player = _make_player(db_session, nickname="MixedPlayer")

        # Completed match
        m1 = _make_match(
            db_session,
            player,
            status="complete",
            score_human=52,
            score_ai=30,
            hands_played=1,
        )
        _make_hand(
            db_session,
            m1,
            hand_number=0,
            points_team0=6,
            points_team1=2,
        )

        # Active match (in progress)
        m2 = _make_match(
            db_session,
            player,
            status="active",
            score_human=0,
            score_ai=0,
            hands_played=1,
        )
        _make_hand(
            db_session,
            m2,
            hand_number=10,
            points_team0=4,
            points_team1=5,
        )

        db_session.flush()
        stats = compute_player_stats(db_session, player.id)

        assert stats is not None
        # Both hands counted
        assert stats.hands_played == 2
        # Only completed match for match-level stats
        assert stats.matches_played == 1
        assert stats.games_won == 1

        # net_eppd includes both: ((6-2) + (4-5)) / 2 = (4 + -1) / 2 = 1.5
        assert stats.net_eppd == 1.5

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
            "is_ai",
            "net_eppd",
            "games_won",
            "win_rate",
            "avg_margin_victory",
            "matches_played",
            "ppd",
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

    def test_min_hands_filter(self, db_session):
        # Player with 1 completed hand
        player = _make_player(db_session, nickname="OneHand")
        match = _make_match(db_session, player)
        _make_hand(db_session, match)

        db_session.flush()

        # min_hands=1 (default) includes them
        assert len(get_leaderboard(db_session, min_hands=1)) == 1

        # min_hands=2 excludes them
        assert len(get_leaderboard(db_session, min_hands=2)) == 0

    def test_excludes_active_match_with_no_hands(self, db_session):
        """Active match but zero completed hands → excluded."""
        player = _make_player(db_session, nickname="ActiveNoHands")
        _make_match(db_session, player, status="active")
        db_session.flush()

        rankings = get_leaderboard(db_session)
        assert len(rankings) == 0

    def test_includes_active_match_with_completed_hands(self, db_session):
        """Active match with completed hands → included on leaderboard."""
        player = _make_player(db_session, nickname="ActiveWithHands")
        match = _make_match(db_session, player, status="active")
        _make_hand(
            db_session,
            match,
            hand_number=0,
            points_team0=6,
            points_team1=3,
        )

        db_session.flush()
        rankings = get_leaderboard(db_session)

        assert len(rankings) == 1
        assert rankings[0].nickname == "ActiveWithHands"
        assert rankings[0].hands_played == 1
        assert rankings[0].matches_played == 0  # no completed matches yet
        assert rankings[0].games_won == 0


# ---------------------------------------------------------------------------
# Test player exclusion tests
# ---------------------------------------------------------------------------


class TestIsExcludedTestPlayer:
    """Tests for is_excluded_test_player helper."""

    def test_none_nickname_not_excluded(self):
        assert is_excluded_test_player(None) is False

    def test_exact_match_excluded(self):
        for name in EXCLUDED_TEST_PLAYERS:
            assert is_excluded_test_player(name) is True, f"{name} should be excluded"

    def test_prefix_match_excluded(self):
        assert is_excluded_test_player("FlexBot-A") is True
        assert is_excluded_test_player("FlexBot-B") is True
        assert is_excluded_test_player("FlexBot-C") is True
        assert is_excluded_test_player("FlexBot-D") is True
        assert is_excluded_test_player("FlexBot-XYZ") is True

    def test_real_player_not_excluded(self):
        assert is_excluded_test_player("Alice") is False
        assert is_excluded_test_player("Phil") is False
        assert is_excluded_test_player("Cindy") is False

    def test_case_sensitive(self):
        # Exact names are case-sensitive
        assert is_excluded_test_player("claude") is False
        assert is_excluded_test_player("CLAUDE") is True
        assert is_excluded_test_player("test") is False
        assert is_excluded_test_player("TEST") is True


class TestLeaderboardExcludesTestPlayers:
    """get_leaderboard filters out test/bot accounts."""

    def test_excludes_exact_match_player(self, db_session):
        # Real player should appear
        real = _make_player(db_session, nickname="RealPlayer")
        rmatch = _make_match(db_session, real)
        _make_hand(db_session, rmatch)

        # Test player should be filtered out
        test = _make_player(db_session, nickname="QUE-TEST")
        tmatch = _make_match(db_session, test)
        _make_hand(db_session, tmatch, hand_number=1)

        db_session.flush()
        rankings = get_leaderboard(db_session)

        assert len(rankings) == 1
        assert rankings[0].nickname == "RealPlayer"

    def test_excludes_prefix_match_player(self, db_session):
        real = _make_player(db_session, nickname="RealPlayer")
        rmatch = _make_match(db_session, real)
        _make_hand(db_session, rmatch)

        bot = _make_player(db_session, nickname="FlexBot-A")
        bmatch = _make_match(db_session, bot)
        _make_hand(db_session, bmatch, hand_number=1)

        db_session.flush()
        rankings = get_leaderboard(db_session)

        assert len(rankings) == 1
        assert rankings[0].nickname == "RealPlayer"

    def test_excludes_multiple_test_players(self, db_session):
        real = _make_player(db_session, nickname="RealPlayer")
        rmatch = _make_match(db_session, real)
        _make_hand(db_session, rmatch)

        for i, name in enumerate(["CLAUDE", "StratBot", "FlexBot-B"], start=1):
            p = _make_player(db_session, nickname=name)
            m = _make_match(db_session, p)
            _make_hand(db_session, m, hand_number=i)

        db_session.flush()
        rankings = get_leaderboard(db_session)

        assert len(rankings) == 1
        assert rankings[0].nickname == "RealPlayer"

    def test_test_player_data_still_computable(self, db_session):
        """Test player data remains in DB — compute_player_stats still works."""
        test = _make_player(db_session, nickname="QUE-TEST")
        tmatch = _make_match(db_session, test)
        _make_hand(db_session, tmatch)
        db_session.flush()

        # Direct computation still works — data is not deleted
        stats = compute_player_stats(db_session, test.id)
        assert stats is not None
        assert stats.nickname == "QUE-TEST"

        # But leaderboard filters them out
        rankings = get_leaderboard(db_session)
        assert len(rankings) == 0


# ---------------------------------------------------------------------------
# AI stats tests
# ---------------------------------------------------------------------------


class TestComputeAiStats:
    """Unit tests for compute_ai_stats (AI opponent perspective)."""

    def test_returns_none_for_unknown_model(self, db_session):
        result = compute_ai_stats(db_session, "nonexistent_model")
        assert result is None

    def test_returns_none_for_no_completed_hands(self, db_session):
        """AI model with no completed hands → None."""
        player = _make_player(db_session)
        _make_match(db_session, player, status="active")
        result = compute_ai_stats(db_session, "heuristic")
        assert result is None

    def test_basic_ai_stats(self, db_session):
        """AI stats computed from team 1 perspective."""
        player = _make_player(db_session, nickname="Alice")
        match = _make_match(
            db_session,
            player,
            score_human=30,
            score_ai=52,
            hands_played=5,
        )

        # 3 hands where human team declared
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
        # 2 hands where AI team declared and made
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
        stats = compute_ai_stats(db_session, "heuristic", display_name="Test Bot")

        assert stats is not None
        assert stats.is_ai is True
        assert stats.nickname == "Test Bot"
        assert stats.matches_played == 1
        assert stats.games_won == 1  # score_ai > score_human
        assert stats.win_rate == 1.0
        assert stats.hands_played == 5

        # net_eppd from AI (team1) perspective:
        # (3*3 + 2*5 - 3*6 - 2*4) / 5 = (9+10-18-8)/5 = -7/5 = -1.4
        assert stats.net_eppd == -1.4

        # bid_rate = 2 declaring (seat 1) / 5 total
        assert stats.bid_rate == 0.4

        # make_rate = 2 made (6 >= 5) / 2 declaring
        assert stats.make_rate == 1.0

    def test_ai_stats_aggregate_across_players(self, db_session):
        """AI stats aggregate across matches from different human players."""
        player_a = _make_player(db_session, nickname="A")
        player_b = _make_player(db_session, nickname="B")

        # Match 1: AI wins
        m1 = _make_match(
            db_session, player_a, score_human=20, score_ai=52, hands_played=2
        )
        _make_hand(
            db_session,
            m1,
            hand_number=0,
            bidder_seat=1,
            winning_bid_n=5,
            tricks_team0=3,
            tricks_team1=7,
            points_team0=3,
            points_team1=5,
        )
        _make_hand(
            db_session,
            m1,
            hand_number=1,
            bidder_seat=0,
            winning_bid_n=6,
            tricks_team0=4,
            tricks_team1=6,
            points_team0=-6,
            points_team1=6,
        )

        # Match 2: AI loses
        m2 = _make_match(
            db_session, player_b, score_human=52, score_ai=10, hands_played=2
        )
        _make_hand(
            db_session,
            m2,
            hand_number=10,
            bidder_seat=0,
            winning_bid_n=6,
            tricks_team0=8,
            tricks_team1=2,
            points_team0=6,
            points_team1=2,
        )
        _make_hand(
            db_session,
            m2,
            hand_number=11,
            bidder_seat=3,
            winning_bid_n=5,
            tricks_team0=6,
            tricks_team1=4,
            points_team0=6,
            points_team1=-5,
        )

        db_session.flush()
        stats = compute_ai_stats(db_session, "heuristic")

        assert stats is not None
        assert stats.hands_played == 4  # across both matches
        assert stats.matches_played == 2
        assert stats.games_won == 1  # only m1 won
        assert stats.win_rate == 0.5

        # net_eppd: (5+6+2+(-5) - 3+(-6)+6+6) / 4 = (8 - 9) / 4 = -0.25
        # team1 points: 5+6+2+(-5) = 8
        # team0 points: 3+(-6)+6+6 = 9
        assert stats.net_eppd == -0.25

    def test_ai_stats_uses_display_name(self, db_session):
        """display_name overrides the raw model id."""
        player = _make_player(db_session)
        match = _make_match(db_session, player)
        _make_hand(db_session, match)
        db_session.flush()

        stats = compute_ai_stats(db_session, "heuristic", display_name="Bud Bot")
        assert stats is not None
        assert stats.nickname == "Bud Bot"

    def test_ai_stats_defaults_to_model_id(self, db_session):
        """Without display_name, nickname falls back to model id."""
        player = _make_player(db_session)
        match = _make_match(db_session, player)
        _make_hand(db_session, match)
        db_session.flush()

        stats = compute_ai_stats(db_session, "heuristic")
        assert stats is not None
        assert stats.nickname == "heuristic"

    def test_ai_stats_player_id_sentinel(self, db_session):
        """AI entries use -1 as player_id sentinel."""
        player = _make_player(db_session)
        match = _make_match(db_session, player)
        _make_hand(db_session, match)
        db_session.flush()

        stats = compute_ai_stats(db_session, "heuristic")
        assert stats is not None
        assert stats.player_id == -1

    def test_ai_moon_and_loner_stats(self, db_session):
        """Moon/loner stats computed from AI team perspective."""
        player = _make_player(db_session)
        match = _make_match(db_session, player)

        # Moon hand — AI team declares, makes all 10
        _make_hand(
            db_session,
            match,
            hand_number=0,
            bidder_seat=1,
            winning_bid_n=10,
            winning_bid_type="moon",
            tricks_team0=0,
            tricks_team1=10,
            points_team0=0,
            points_team1=20,
        )

        # Loner hand — AI team declares, fails
        _make_hand(
            db_session,
            match,
            hand_number=1,
            bidder_seat=3,
            winning_bid_n=10,
            winning_bid_type="loner",
            tricks_team0=5,
            tricks_team1=5,
            points_team0=5,
            points_team1=-10,
        )

        # Regular hand — human declares
        _make_hand(
            db_session,
            match,
            hand_number=2,
            bidder_seat=0,
            winning_bid_n=5,
            winning_bid_type="regular",
            tricks_team0=6,
            tricks_team1=4,
            points_team0=5,
            points_team1=4,
        )

        db_session.flush()
        stats = compute_ai_stats(db_session, "heuristic")

        assert stats is not None
        assert stats.hands_played == 3
        assert stats.moon_call_rate == pytest.approx(1 / 3, abs=0.001)
        assert stats.moon_make_rate == 1.0  # 1 moon, all 10 tricks
        assert stats.loner_call_rate == pytest.approx(1 / 3, abs=0.001)
        assert stats.loner_make_rate == 0.0  # 1 loner, only 5 tricks


class TestLeaderboardWithAI:
    """Tests for get_leaderboard with AI opponent entries included."""

    def test_includes_ai_when_display_names_provided(self, db_session):
        """AI entries appear when ai_display_names is passed."""
        player = _make_player(db_session, nickname="Human")
        match = _make_match(db_session, player)
        _make_hand(db_session, match, points_team0=5, points_team1=3)
        db_session.flush()

        rankings = get_leaderboard(
            db_session, ai_display_names={"heuristic": "Test Bot"}
        )
        assert len(rankings) == 2
        nicknames = {r.nickname for r in rankings}
        assert "Human" in nicknames
        assert "Test Bot" in nicknames

    def test_excludes_ai_when_no_display_names(self, db_session):
        """Without ai_display_names, only human players appear."""
        player = _make_player(db_session, nickname="Human")
        match = _make_match(db_session, player)
        _make_hand(db_session, match, points_team0=5, points_team1=3)
        db_session.flush()

        rankings = get_leaderboard(db_session)
        assert len(rankings) == 1
        assert rankings[0].nickname == "Human"
        assert rankings[0].is_ai is False

    def test_ai_and_human_sorted_by_net_eppd(self, db_session):
        """AI and human entries sort together by net_eppd."""
        player = _make_player(db_session, nickname="Human")
        match = _make_match(db_session, player, score_human=52, score_ai=20)

        # Human team wins big: high positive eppd for human, negative for AI
        _make_hand(
            db_session,
            match,
            points_team0=10,
            points_team1=2,
        )
        db_session.flush()

        rankings = get_leaderboard(
            db_session, ai_display_names={"heuristic": "Test Bot"}
        )
        assert len(rankings) == 2
        # Human has positive Net PPD (10-2=8), AI has negative (-8)
        assert rankings[0].nickname == "Human"
        assert rankings[0].is_ai is False
        assert rankings[1].nickname == "Test Bot"
        assert rankings[1].is_ai is True

    def test_ai_respects_min_hands_filter(self, db_session):
        """AI entries also respect the min_hands threshold."""
        player = _make_player(db_session, nickname="Human")
        match = _make_match(db_session, player)
        _make_hand(db_session, match, points_team0=5, points_team1=3)
        db_session.flush()

        # min_hands=2 excludes both (only 1 hand each)
        rankings = get_leaderboard(
            db_session,
            min_hands=2,
            ai_display_names={"heuristic": "Test Bot"},
        )
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
            assert "Net PPD" in resp.text
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
            assert "No hands played yet" in resp.text
        finally:
            session.close()

    def test_leaderboard_has_auto_refresh(self, app_and_client):
        """Leaderboard page includes HTMX polling for live updates."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="RefreshTest")
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert 'hx-trigger="every 30s"' in resp.text
        finally:
            session.close()

    def test_leaderboard_shows_ranking_explanation(self, app_and_client):
        """Leaderboard page shows ranking explanation text."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="RankExplain")
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert "Ranked by Net PPD" in resp.text
        finally:
            session.close()

    def test_leaderboard_shows_help_button(self, app_and_client):
        """Leaderboard with data includes the help toggle button."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="HelpBtn")
            match = _make_match(session, player)
            _make_hand(session, match, points_team0=5, points_team1=2)
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert "What do these stats mean?" in resp.text
        finally:
            session.close()

    def test_leaderboard_shows_tooltips(self, app_and_client):
        """Column headers include tooltip text from metric definitions."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="Tooltips")
            match = _make_match(session, player)
            _make_hand(session, match, points_team0=5, points_team1=2)
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            # Spot check key tooltips
            assert "average point advantage" in resp.text.lower()
            assert "Percentage of completed games" in resp.text
        finally:
            session.close()

    def test_leaderboard_formats_percentages(self, app_and_client):
        """Win rate and other rates render as percentages, not decimals."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="FmtTest")
            match = _make_match(session, player, score_human=52, score_ai=20)
            _make_hand(
                session,
                match,
                bidder_seat=0,
                winning_bid_n=6,
                tricks_team0=7,
                tricks_team1=3,
                points_team0=6,
                points_team1=3,
            )
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            # Win rate should be 100% not 1.0 or 1.000
            assert "100%" in resp.text
            # games_won should show "1 game"
            assert "1 game" in resp.text
        finally:
            session.close()

    def test_leaderboard_shows_ai_opponents(self, app_and_client):
        """AI opponents appear on the leaderboard with an AI badge."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="HumanPlayer")
            # Match uses an AI model that the test roster provides
            match = _make_match(
                session,
                player,
                score_human=52,
                score_ai=20,
            )
            # Override ai_model to match the test roster
            match.ai_model = "bud_bot"
            _make_hand(
                session,
                match,
                points_team0=5,
                points_team1=2,
            )
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            # Human player present
            assert "HumanPlayer" in resp.text
            # AI opponent present with badge
            assert "Bud Bot" in resp.text
            assert "AI" in resp.text
            assert "leaderboard__ai-badge" in resp.text
        finally:
            session.close()

    def test_leaderboard_no_ai_badge_for_humans(self, app_and_client):
        """Human players do not have the AI badge in table rows."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="JustHuman")
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            # Empty leaderboard — no table body, no AI badge in rows
            assert 'title="AI opponent"' not in resp.text
        finally:
            session.close()


# ---------------------------------------------------------------------------
# format_metric tests
# ---------------------------------------------------------------------------


class TestFormatMetric:
    """Unit tests for the format_metric helper."""

    def test_pct_formats_fraction_as_percentage(self):
        assert format_metric(0.65, "pct") == "65%"
        assert format_metric(1.0, "pct") == "100%"
        assert format_metric(0.0, "pct") == "0%"

    def test_pct_rounds_to_nearest(self):
        assert format_metric(0.666, "pct") == "67%"
        assert format_metric(0.334, "pct") == "33%"

    def test_pct_avoids_false_zero(self):
        """Non-zero rates should never display as '0%'."""
        assert format_metric(0.004, "pct") == "<1%"
        assert format_metric(0.001, "pct") == "<1%"
        assert format_metric(0.009, "pct") == "<1%"

    def test_pct_avoids_false_hundred(self):
        """Non-perfect rates should never display as '100%'."""
        assert format_metric(0.996, "pct") == ">99%"
        assert format_metric(0.999, "pct") == ">99%"
        assert format_metric(0.995, "pct") == ">99%"

    def test_pct_boundary_values(self):
        """Values at exactly 1% and 99% use normal rounding."""
        assert format_metric(0.01, "pct") == "1%"
        assert format_metric(0.99, "pct") == "99%"

    def test_int_formats_as_integer(self):
        assert format_metric(5, "int") == "5"
        assert format_metric(0, "int") == "0"

    def test_int_games_singular(self):
        assert format_metric(1, "int_games") == "1 game"

    def test_int_games_plural(self):
        assert format_metric(0, "int_games") == "0 games"
        assert format_metric(5, "int_games") == "5 games"

    def test_float1(self):
        assert format_metric(3.14, "float1") == "3.1"
        assert format_metric(0.0, "float1") == "0.0"

    def test_float3(self):
        assert format_metric(1.2345, "float3") == "1.234"

    def test_signed_float1_positive(self):
        assert format_metric(3.2, "signed_float1") == "+3.2"

    def test_signed_float1_negative(self):
        assert format_metric(-2.5, "signed_float1") == "-2.5"

    def test_signed_float1_zero(self):
        assert format_metric(0.0, "signed_float1") == "0.0"

    def test_signed_float3_positive(self):
        assert format_metric(1.234, "signed_float3") == "+1.234"

    def test_signed_float3_negative(self):
        assert format_metric(-0.5, "signed_float3") == "-0.500"

    def test_signed_float3_zero(self):
        assert format_metric(0.0, "signed_float3") == "0.000"

    def test_unknown_format_falls_back_to_str(self):
        assert format_metric(42, "unknown") == "42"


# ---------------------------------------------------------------------------
# METRIC_DEFINITIONS tests
# ---------------------------------------------------------------------------


class TestMetricDefinitions:
    """Tests for the METRIC_DEFINITIONS registry."""

    def test_every_player_stats_field_has_definition(self):
        """Every numeric field on PlayerStats has a matching metric def."""
        skip = {"player_id", "nickname", "is_ai"}
        stat_fields = {
            f.name
            for f in PlayerStats.__dataclass_fields__.values()
            if f.name not in skip
        }
        assert stat_fields == set(METRIC_DEFINITIONS.keys())

    def test_categories_are_valid(self):
        valid = {"primary", "default", "secondary"}
        for key, m in METRIC_DEFINITIONS.items():
            assert m.category in valid, f"{key} has invalid category {m.category}"

    def test_exactly_one_primary(self):
        primaries = [
            k for k, m in METRIC_DEFINITIONS.items() if m.category == "primary"
        ]
        assert len(primaries) == 1
        assert primaries[0] == "net_eppd"

    def test_all_have_nonempty_tooltip(self):
        for key, m in METRIC_DEFINITIONS.items():
            assert len(m.tooltip) > 10, f"{key} tooltip too short: {m.tooltip!r}"

    def test_all_have_nonempty_label(self):
        for key, m in METRIC_DEFINITIONS.items():
            assert len(m.label) > 0, f"{key} has empty label"

    def test_all_have_nonempty_full_label(self):
        for key, m in METRIC_DEFINITIONS.items():
            assert len(m.full_label) > 0, f"{key} has empty full_label"

    def test_labels_are_abbreviated(self):
        """Column headers should be short abbreviations (≤7 chars)."""
        for key, m in METRIC_DEFINITIONS.items():
            assert (
                len(m.label) <= 7
            ), f"{key} label {m.label!r} too long for abbreviated header"

    def test_full_labels_are_longer_than_labels(self):
        """Full labels should be more descriptive than abbreviated labels."""
        for key, m in METRIC_DEFINITIONS.items():
            assert len(m.full_label) >= len(
                m.label
            ), f"{key}: full_label {m.full_label!r} shorter than label {m.label!r}"

    def test_moon_loner_tooltips_say_team_not_personal(self):
        """Moon/loner tooltips must reference 'your team', not 'personally' (#2228).

        The underlying computation uses team-level stats (seats 0,2 for
        human; seats 1,3 for AI), so the tooltip text must match.
        """
        for key in (
            "moon_call_rate",
            "moon_make_rate",
            "loner_call_rate",
            "loner_make_rate",
        ):
            tooltip = METRIC_DEFINITIONS[key].tooltip
            assert (
                "personally" not in tooltip.lower()
            ), f"{key} tooltip still says 'personally': {tooltip!r}"
            assert (
                "team" in tooltip.lower()
            ), f"{key} tooltip should reference 'team': {tooltip!r}"


# ---------------------------------------------------------------------------
# Current player highlight (#2224)
# ---------------------------------------------------------------------------


class TestLeaderboardCurrentPlayerHighlight:
    """Verify the current player's row is highlighted on the leaderboard."""

    @pytest.fixture()
    def app_and_client(self, tmp_path):
        from starlette.testclient import TestClient

        from tests.unit.hosted_play.conftest import make_hosted_play_test_config
        from web.app import create_app

        config = make_hosted_play_test_config(tmp_path)
        app = create_app(config)
        with TestClient(app) as client:
            yield app, client

    def test_current_player_row_has_highlight_class(self, app_and_client):
        """The current player's row gets the leaderboard-row--current class."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player = _make_player(session, nickname="HighlightMe")
            match = _make_match(session, player, score_human=52, score_ai=20)
            _make_hand(session, match, points_team0=5, points_team1=2)
            session.commit()

            resp = client.get(f"/leaderboard/{player.link_uuid}")
            assert resp.status_code == 200
            assert "leaderboard-row--current" in resp.text
            assert 'aria-current="true"' in resp.text
        finally:
            session.close()

    def test_other_player_row_has_no_highlight(self, app_and_client):
        """Other players' rows do not get the highlight class."""
        app, client = app_and_client
        session = app.state.session_factory()
        try:
            player1 = _make_player(session, nickname="Player1")
            player2 = _make_player(session, nickname="Player2")
            match1 = _make_match(session, player1, score_human=52, score_ai=20)
            _make_hand(session, match1, points_team0=5, points_team1=2)
            match2 = _make_match(session, player2, score_human=52, score_ai=30)
            _make_hand(session, match2, points_team0=3, points_team1=4)
            session.commit()

            # View as player1 — only player1's row should be highlighted
            resp = client.get(f"/leaderboard/{player1.link_uuid}")
            assert resp.status_code == 200
            # Exactly one <tr> should have the highlight class (CSS block also
            # contains the string, so count on the attribute pattern instead)
            assert resp.text.count('class="leaderboard-row--current"') == 1
            assert resp.text.count('aria-current="true"') == 1
        finally:
            session.close()
