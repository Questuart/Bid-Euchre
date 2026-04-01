"""Leaderboard stats aggregation for the browser game.

Computes player performance metrics from completed match and hand data.
All queries operate on the hosted-play SQLAlchemy models — no raw SQL.

The leaderboard is a product-facing feature: metrics optimize for player
comprehension and engagement, not research-report statistical fidelity.
Research-parity optimization (bootstrap CIs, effect sizes, p-values) is
explicitly out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import Hand, Match, Player

# Human is always seat 0; human's team is (seat 0, seat 2) = team 0.
HUMAN_TEAM = 0


@dataclass(frozen=True)
class PlayerStats:
    """Aggregated performance metrics for a single player."""

    player_id: int
    nickname: str | None

    # Primary ranking metric
    net_eppd: float  # net expected points per deal

    # Default visible columns
    games_won: int
    win_rate: float  # 0.0–1.0
    avg_margin_victory: float  # average score margin when winning
    matches_played: int

    # Secondary columns
    hands_played: int
    avg_match_margin: float  # average match score margin (all matches)
    bid_rate: float  # fraction of hands where player's team won the bid
    make_rate: float  # fraction of contracts made when declaring
    avg_bid_level: float  # average bid level when declaring
    moon_call_rate: float  # fraction of hands with a moon bid
    moon_make_rate: float  # fraction of moon contracts made
    loner_call_rate: float  # fraction of hands with a loner bid
    loner_make_rate: float  # fraction of loner contracts made


def compute_player_stats(session: Session, player_id: int) -> PlayerStats | None:
    """Compute aggregated stats for a single player.

    Returns ``None`` if the player has no completed matches.
    """
    player = session.query(Player).get(player_id)
    if player is None:
        return None

    # Completed matches for this player
    completed_matches = (
        session.query(Match).filter_by(player_id=player_id, status="complete").all()
    )

    if not completed_matches:
        return None

    matches_played = len(completed_matches)
    match_ids = [m.id for m in completed_matches]

    # Win/loss from matches (human is team 0 — score_human vs score_ai)
    games_won = sum(1 for m in completed_matches if m.score_human > m.score_ai)
    win_rate = games_won / matches_played if matches_played > 0 else 0.0

    # Score margins
    margins = [m.score_human - m.score_ai for m in completed_matches]
    avg_match_margin = sum(margins) / len(margins) if margins else 0.0
    winning_margins = [mg for mg in margins if mg > 0]
    avg_margin_victory = (
        sum(winning_margins) / len(winning_margins) if winning_margins else 0.0
    )

    # Completed hands across all completed matches
    completed_hands = (
        session.query(Hand)
        .filter(Hand.match_id.in_(match_ids), Hand.status == "complete")
        .all()
    )
    hands_played = len(completed_hands)

    # Net EPPD: total net points / total hands
    if hands_played > 0:
        total_net_points = sum(h.points_team0 - h.points_team1 for h in completed_hands)
        net_eppd = total_net_points / hands_played
    else:
        net_eppd = 0.0

    # Bidding stats — human team is team 0, bidder_seat in (0, 2)
    declaring_hands = [
        h
        for h in completed_hands
        if h.bidder_seat is not None and h.bidder_seat in (0, 2)
    ]
    bid_rate = len(declaring_hands) / hands_played if hands_played > 0 else 0.0

    # Make rate: when declaring, did team 0 make the contract?
    # Made = tricks_team0 >= winning_bid_n
    made_contracts = [
        h
        for h in declaring_hands
        if h.winning_bid_n is not None and h.tricks_team0 >= h.winning_bid_n
    ]
    make_rate = len(made_contracts) / len(declaring_hands) if declaring_hands else 0.0

    # Average bid level when declaring
    bid_levels = [
        h.winning_bid_n for h in declaring_hands if h.winning_bid_n is not None
    ]
    avg_bid_level = sum(bid_levels) / len(bid_levels) if bid_levels else 0.0

    # Moon stats
    moon_hands = [h for h in completed_hands if h.winning_bid_type == "moon"]
    moon_declaring = [h for h in moon_hands if h.bidder_seat in (0, 2)]
    moon_call_rate = len(moon_declaring) / hands_played if hands_played > 0 else 0.0
    moon_made = [
        h
        for h in moon_declaring
        if h.winning_bid_n is not None and h.tricks_team0 >= h.winning_bid_n
    ]
    moon_make_rate = len(moon_made) / len(moon_declaring) if moon_declaring else 0.0

    # Loner stats
    loner_hands = [h for h in completed_hands if h.winning_bid_type == "loner"]
    loner_declaring = [h for h in loner_hands if h.bidder_seat in (0, 2)]
    loner_call_rate = len(loner_declaring) / hands_played if hands_played > 0 else 0.0
    loner_made = [
        h
        for h in loner_declaring
        if h.winning_bid_n is not None and h.tricks_team0 >= h.winning_bid_n
    ]
    loner_make_rate = len(loner_made) / len(loner_declaring) if loner_declaring else 0.0

    return PlayerStats(
        player_id=player_id,
        nickname=player.nickname,
        net_eppd=round(net_eppd, 3),
        games_won=games_won,
        win_rate=round(win_rate, 3),
        avg_margin_victory=round(avg_margin_victory, 1),
        matches_played=matches_played,
        hands_played=hands_played,
        avg_match_margin=round(avg_match_margin, 1),
        bid_rate=round(bid_rate, 3),
        make_rate=round(make_rate, 3),
        avg_bid_level=round(avg_bid_level, 1),
        moon_call_rate=round(moon_call_rate, 3),
        moon_make_rate=round(moon_make_rate, 3),
        loner_call_rate=round(loner_call_rate, 3),
        loner_make_rate=round(loner_make_rate, 3),
    )


def get_leaderboard(
    session: Session,
    *,
    min_matches: int = 1,
) -> list[PlayerStats]:
    """Return leaderboard rankings sorted by net_eppd descending.

    Only includes players with at least *min_matches* completed matches.
    """
    # Find all players with completed matches
    player_match_counts = (
        session.query(Match.player_id, func.count(Match.id).label("n"))
        .filter_by(status="complete")
        .group_by(Match.player_id)
        .having(func.count(Match.id) >= min_matches)
        .all()
    )

    stats_list: list[PlayerStats] = []
    for player_id, _count in player_match_counts:
        stats = compute_player_stats(session, player_id)
        if stats is not None:
            stats_list.append(stats)

    # Sort by net_eppd descending (primary ranking metric)
    stats_list.sort(key=lambda s: s.net_eppd, reverse=True)
    return stats_list
