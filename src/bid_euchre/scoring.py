"""
Points-based scoring utilities for Bid Euchre.

This module provides deterministic scoring calculations for bid euchre games.
"""

from typing import Optional


def compute_points(
    winning_bid: Optional[int],
    bidder_position: Optional[int],
    tricks_team0: int,
    tricks_team1: int,
    bid_type: str = "regular",
) -> tuple[int, int]:
    """
    Compute points for both teams based on euchre scoring rules.

    Args:
        winning_bid: The winning bid amount, or None if no bidding occurred
        bidder_position: The seat position (0-3) of the winning bidder, or None if no bidding
        tricks_team0: Number of tricks taken by team 0 (seats 0, 2)
        tricks_team1: Number of tricks taken by team 1 (seats 1, 3)
        bid_type: Type of bid — "regular", "moon", or "loner" (default "regular")

    Returns:
        Tuple of (points_team0, points_team1)

    Scoring rules:
    - If no bidding occurred (winning_bid or bidder_position is None):
      Both teams get their tricks taken as points
    - bid_type="regular":
      - Make (bid_team_tricks >= winning_bid): bid team gets tricks, defending gets tricks
      - Set (bid_team_tricks < winning_bid): bid team gets -winning_bid, defending gets tricks
    - bid_type="moon":
      - Make (bid_team_tricks == 10): declaring team gets +20
      - Fail (bid_team_tricks < 10): declaring team gets -20
      - Defending team always gets their tricks won
    - bid_type="loner":
      - Make (bid_team_tricks == 10): declaring team gets +40
      - Fail (bid_team_tricks < 10): declaring team gets -40
      - Defending team always gets their tricks won
    """
    # No bidding case: both teams get their tricks
    if winning_bid is None or bidder_position is None:
        return tricks_team0, tricks_team1

    # Determine which team made the bid
    bid_team_is_team0 = bidder_position in (0, 2)
    bid_team_tricks = tricks_team0 if bid_team_is_team0 else tricks_team1
    non_bid_team_tricks = tricks_team1 if bid_team_is_team0 else tricks_team0

    if bid_type == "moon":
        # Moon: must win all 10 tricks for +20, else -20
        if bid_team_tricks == 10:
            bid_team_points = 20
        else:
            bid_team_points = -20
        if bid_team_is_team0:
            return bid_team_points, non_bid_team_tricks
        else:
            return non_bid_team_tricks, bid_team_points

    if bid_type == "loner":
        # Loner: must win all 10 tricks for +40, else -40
        if bid_team_tricks == 10:
            bid_team_points = 40
        else:
            bid_team_points = -40
        if bid_team_is_team0:
            return bid_team_points, non_bid_team_tricks
        else:
            return non_bid_team_tricks, bid_team_points

    if bid_type != "regular":
        raise ValueError(
            f"Invalid bid_type: {bid_type!r}. Must be 'regular', 'moon', or 'loner'."
        )

    # Regular bid scoring
    if bid_team_tricks >= winning_bid:
        # Bid made: bid team gets their tricks, non-bid team gets their tricks
        if bid_team_is_team0:
            return bid_team_tricks, non_bid_team_tricks
        else:
            return non_bid_team_tricks, bid_team_tricks
    else:
        # Bid set: bid team gets -winning_bid, non-bid team gets their tricks
        negative_bid = -winning_bid
        if bid_team_is_team0:
            return negative_bid, non_bid_team_tricks
        else:
            return non_bid_team_tricks, negative_bid
