"""Leaderboard stats aggregation for the browser game.

Computes player performance metrics from match and hand data, including
hands from in-progress matches so stats update after every hand.

All queries operate on the hosted-play SQLAlchemy models — no raw SQL.

The leaderboard is a product-facing feature: metrics optimize for player
comprehension and engagement, not research-report statistical fidelity.
Research-parity optimization (bootstrap CIs, effect sizes, p-values) is
explicitly out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import Hand, Match, Player

# Human is always seat 0; human's team is (seat 0, seat 2) = team 0.
HUMAN_TEAM = 0

# Match statuses that contribute hands to leaderboard stats.
_LEADERBOARD_MATCH_STATUSES = ("active", "complete")


# ---------------------------------------------------------------------------
# Metric definitions — display metadata for the leaderboard UI
# ---------------------------------------------------------------------------


class MetricDef(NamedTuple):
    """Display metadata for a single leaderboard metric."""

    label: str  # Short column header
    tooltip: str  # Plain-English explanation
    format: str  # "pct" | "int" | "float1" | "float3" | "signed_float1"
    category: str  # "primary" | "default" | "secondary"


#: Metric definitions keyed by PlayerStats field name.
#: The template iterates these to build headers, tooltips, and formatting.
METRIC_DEFINITIONS: dict[str, MetricDef] = {
    "net_eppd": MetricDef(
        label="Net EPPD",
        tooltip=(
            "Net Expected Points Per Deal — your average point advantage "
            "per hand. Positive means you're outscoring opponents."
        ),
        format="signed_float3",
        category="primary",
    ),
    "games_won": MetricDef(
        label="Won",
        tooltip="Total games (matches) won.",
        format="int_games",
        category="default",
    ),
    "win_rate": MetricDef(
        label="Win %",
        tooltip="Percentage of completed games you won.",
        format="pct",
        category="default",
    ),
    "avg_margin_victory": MetricDef(
        label="Avg Margin",
        tooltip="Average score margin in games you won (points).",
        format="float1",
        category="default",
    ),
    "matches_played": MetricDef(
        label="Matches",
        tooltip="Total completed matches played.",
        format="int",
        category="default",
    ),
    "hands_played": MetricDef(
        label="Hands",
        tooltip="Total hands played across all matches (including in-progress).",
        format="int",
        category="secondary",
    ),
    "avg_match_margin": MetricDef(
        label="Match Margin",
        tooltip="Average score margin across all completed matches (positive = winning).",
        format="signed_float1",
        category="secondary",
    ),
    "bid_rate": MetricDef(
        label="Bid %",
        tooltip="Percentage of hands where your team won the auction and declared.",
        format="pct",
        category="secondary",
    ),
    "make_rate": MetricDef(
        label="Make %",
        tooltip="Percentage of your contracts that made (took enough tricks).",
        format="pct",
        category="secondary",
    ),
    "avg_bid_level": MetricDef(
        label="Avg Bid",
        tooltip="Average number of tricks bid when your team declares.",
        format="float1",
        category="secondary",
    ),
    "moon_call_rate": MetricDef(
        label="Moon %",
        tooltip="Percentage of hands where your team called a moon (bid all 10 tricks).",
        format="pct",
        category="secondary",
    ),
    "moon_make_rate": MetricDef(
        label="Moon Make",
        tooltip="Percentage of your moon bids that were successfully made.",
        format="pct",
        category="secondary",
    ),
    "loner_call_rate": MetricDef(
        label="Loner %",
        tooltip="Percentage of hands where your team called a loner (solo play).",
        format="pct",
        category="secondary",
    ),
    "loner_make_rate": MetricDef(
        label="Loner Make",
        tooltip="Percentage of your loner bids that were successfully made.",
        format="pct",
        category="secondary",
    ),
}


def format_metric(value: int | float, fmt: str) -> str:
    """Format a metric value for display using its format specifier.

    Format codes:
    - ``"pct"`` — fraction (0.0–1.0) → ``"65%"``
    - ``"int"`` — integer count → ``"5"``
    - ``"int_games"`` — integer game count → ``"5 games"`` / ``"1 game"``
    - ``"float1"`` — one decimal → ``"3.2"``
    - ``"float3"`` — three decimals → ``"1.234"``
    - ``"signed_float1"`` — one decimal with +/- sign → ``"+3.2"``
    - ``"signed_float3"`` — three decimals with +/- sign → ``"+1.234"``
    """
    if fmt == "pct":
        return f"{value * 100:.0f}%"
    elif fmt == "int":
        return str(int(value))
    elif fmt == "int_games":
        n = int(value)
        return f"{n} game" if n == 1 else f"{n} games"
    elif fmt == "float1":
        return f"{value:.1f}"
    elif fmt == "float3":
        return f"{value:.3f}"
    elif fmt == "signed_float1":
        return f"{value:+.1f}" if value != 0 else "0.0"
    elif fmt == "signed_float3":
        return f"{value:+.3f}" if value != 0 else "0.000"
    else:
        return str(value)


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
    avg_match_margin: float  # average match score margin (completed matches)
    bid_rate: float  # fraction of hands where player's team won the bid
    make_rate: float  # fraction of contracts made when declaring
    avg_bid_level: float  # average bid level when declaring
    moon_call_rate: float  # fraction of hands with a moon bid
    moon_make_rate: float  # fraction of moon contracts made
    loner_call_rate: float  # fraction of hands with a loner bid
    loner_make_rate: float  # fraction of loner contracts made


def compute_player_stats(session: Session, player_id: int) -> PlayerStats | None:
    """Compute aggregated stats for a single player.

    Returns ``None`` if the player has no completed hands.

    Hand-level metrics (net_eppd, bid_rate, make_rate, etc.) include hands
    from both active and completed matches so the leaderboard updates after
    every hand.  Match-level metrics (games_won, win_rate, margins) use
    completed matches only — you can't "win" an in-progress game.
    """
    player = session.query(Player).get(player_id)
    if player is None:
        return None

    # All matches that contribute hands (active + complete)
    all_matches = (
        session.query(Match)
        .filter(
            Match.player_id == player_id,
            Match.status.in_(_LEADERBOARD_MATCH_STATUSES),
        )
        .all()
    )

    if not all_matches:
        return None

    all_match_ids = [m.id for m in all_matches]

    # Completed hands across active + completed matches
    completed_hands = (
        session.query(Hand)
        .filter(Hand.match_id.in_(all_match_ids), Hand.status == "complete")
        .all()
    )
    hands_played = len(completed_hands)

    if hands_played == 0:
        return None

    # --- Match-level metrics (completed matches only) ---
    completed_matches = [m for m in all_matches if m.status == "complete"]
    matches_played = len(completed_matches)

    games_won = sum(1 for m in completed_matches if m.score_human > m.score_ai)
    win_rate = games_won / matches_played if matches_played > 0 else 0.0

    margins = [m.score_human - m.score_ai for m in completed_matches]
    avg_match_margin = sum(margins) / len(margins) if margins else 0.0
    winning_margins = [mg for mg in margins if mg > 0]
    avg_margin_victory = (
        sum(winning_margins) / len(winning_margins) if winning_margins else 0.0
    )

    # --- Hand-level metrics (all completed hands) ---

    # Net EPPD: total net points / total hands
    total_net_points = sum(h.points_team0 - h.points_team1 for h in completed_hands)
    net_eppd = total_net_points / hands_played

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
    min_hands: int = 1,
) -> list[PlayerStats]:
    """Return leaderboard rankings sorted by net_eppd descending.

    Only includes players with at least *min_hands* completed hands
    (across both active and completed matches).  This means players
    appear on the leaderboard after their very first completed hand,
    even during their first match.
    """
    # Find all players with enough completed hands across active+complete matches
    player_hand_counts = (
        session.query(Match.player_id, func.count(Hand.id).label("n"))
        .join(Hand, Hand.match_id == Match.id)
        .filter(
            Match.status.in_(_LEADERBOARD_MATCH_STATUSES),
            Hand.status == "complete",
        )
        .group_by(Match.player_id)
        .having(func.count(Hand.id) >= min_hands)
        .all()
    )

    stats_list: list[PlayerStats] = []
    for player_id, _count in player_hand_counts:
        stats = compute_player_stats(session, player_id)
        if stats is not None:
            stats_list.append(stats)

    # Sort by net_eppd descending (primary ranking metric)
    stats_list.sort(key=lambda s: s.net_eppd, reverse=True)
    return stats_list
