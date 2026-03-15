"""
Auction context features extracted from auction_transcript.

These features capture information about other players' bidding behavior
during the auction phase. They are separate from hand evaluation features
(hand_eval.py) because they depend on auction state, not just cards.

v7 features (backward-compatible):
    partner_bid_level: Highest bid level partner made (0 if passed/no action)
    partner_passed: 1 if partner explicitly passed, 0 otherwise
    partner_suit_match: 1 if partner bid same contract family as observer context

v2 features (R1, suit-relative channels):
    partner_level_same_suit: Partner's bid level in same suit as observer (0 if none)
    partner_level_same_color: Partner's bid level in same-color suit (0 if none)
    partner_level_off_color: Partner's bid level in off-color suit (0 if none)
    partner_level_high: Partner's bid level for high contract (0 if none)
    partner_level_low: Partner's bid level for low contract (0 if none)
    partner_passed: 1 if partner explicitly passed, 0 otherwise

R2 opponent features (suit-relative, same template as v2 partner):
    opp_{side}_level_same_suit: Opponent's bid level in same suit (0 if none)
    opp_{side}_level_same_color: Opponent's bid level in same-color suit (0 if none)
    opp_{side}_level_off_color: Opponent's bid level in off-color suit (0 if none)
    opp_{side}_level_high: Opponent's bid level for high contract (0 if none)
    opp_{side}_level_low: Opponent's bid level for low contract (0 if none)
    opp_{side}_passed: 1 if opponent explicitly passed, 0 otherwise
    where {side} is "left" or "right"
"""

from __future__ import annotations

from typing import Any

from ..core.cards import SAME_COLOR_SUIT


def extract_partner_features(
    seat: int,
    auction_transcript: tuple[dict, ...] | list[dict],
    observer_best_contract: str | None = None,
) -> dict[str, Any]:
    """Extract partner bidding context features from auction transcript (v7).

    Args:
        seat: Observer's seat index (0-3).
        auction_transcript: Sequence of auction entry dicts, each with keys:
            seat (int), action (str: "BID" or "PASS"),
            tricks_bid (int), contract_type (str|None), trump (str|None).
        observer_best_contract: Contract family the observer is evaluating
            ("suit", "high", or "low"). Used for partner_suit_match.
            If None, partner_suit_match defaults to 0.

    Returns:
        Dict with 3 features:
            partner_bid_level (int): 0-10, highest bid partner made
            partner_passed (int): 0 or 1
            partner_suit_match (int): 0 or 1
    """
    partner_seat = (seat + 2) % 4

    partner_bid_level = 0
    partner_passed = 0
    partner_contract_type = None

    for entry in auction_transcript:
        if entry["seat"] != partner_seat:
            continue
        if entry["action"] == "PASS":
            partner_passed = 1
        elif entry["action"] == "BID":
            bid_level = entry.get("tricks_bid", 0)
            if bid_level > partner_bid_level:
                partner_bid_level = bid_level
                partner_contract_type = entry.get("contract_type")

    # Suit match: did partner bid the same contract family as observer?
    partner_suit_match = 0
    if observer_best_contract is not None and partner_contract_type is not None:
        partner_suit_match = int(partner_contract_type == observer_best_contract)

    return {
        "partner_bid_level": partner_bid_level,
        "partner_passed": partner_passed,
        "partner_suit_match": partner_suit_match,
    }


# Canonical v7 feature names for schema validation and filtering
PARTNER_FEATURE_NAMES = [
    "partner_bid_level",
    "partner_passed",
    "partner_suit_match",
]


def _extract_player_features(
    target_seat: int,
    auction_transcript: tuple[dict, ...] | list[dict],
    observer_contract_type: str | None,
    observer_trump_suit: str | None,
    prefix: str,
) -> dict[str, Any]:
    """Extract suit-relative bidding features for a single player.

    Shared helper used by both partner (v2) and opponent feature extractors.
    Produces 6 features with the given prefix:
        {prefix}_level_same_suit, {prefix}_level_same_color,
        {prefix}_level_off_color, {prefix}_level_high,
        {prefix}_level_low, {prefix}_passed.

    Args:
        target_seat: The seat index (0-3) of the player to extract features for.
        auction_transcript: Sequence of auction entry dicts.
        observer_contract_type: Contract family the observer is evaluating
            ("suit", "high", "low", or None).
        observer_trump_suit: Trump suit letter for suit contracts, None otherwise.
        prefix: Feature name prefix (e.g., "partner", "opp_left", "opp_right").

    Returns:
        Dict with 6 features using the given prefix.
    """
    passed = 0
    level_same_suit = 0
    level_same_color = 0
    level_off_color = 0
    level_high = 0
    level_low = 0

    for entry in auction_transcript:
        if entry["seat"] != target_seat:
            continue
        if entry["action"] == "PASS":
            passed = 1
        elif entry["action"] == "BID":
            bid_level = entry.get("tricks_bid", 0)
            bid_contract = entry.get("contract_type")
            bid_trump = entry.get("trump")

            if bid_contract == "high":
                level_high = max(level_high, bid_level)
            elif bid_contract == "low":
                level_low = max(level_low, bid_level)
            elif bid_contract == "suit" and bid_trump is not None:
                # Classify suit relationship only when observer has a suit contract
                if observer_contract_type == "suit" and observer_trump_suit is not None:
                    if bid_trump == observer_trump_suit:
                        level_same_suit = max(level_same_suit, bid_level)
                    elif bid_trump == SAME_COLOR_SUIT.get(observer_trump_suit):
                        level_same_color = max(level_same_color, bid_level)
                    else:
                        level_off_color = max(level_off_color, bid_level)
                # For non-suit observer contracts, suit bids go nowhere
                # (suit channels stay 0, which is correct — no suit relevance)

    return {
        f"{prefix}_level_same_suit": level_same_suit,
        f"{prefix}_level_same_color": level_same_color,
        f"{prefix}_level_off_color": level_off_color,
        f"{prefix}_level_high": level_high,
        f"{prefix}_level_low": level_low,
        f"{prefix}_passed": passed,
    }


def extract_partner_features_v2(
    seat: int,
    auction_transcript: tuple[dict, ...] | list[dict],
    observer_contract_type: str | None = None,
    observer_trump_suit: str | None = None,
) -> dict[str, Any]:
    """Extract suit-relative partner bidding features (v2/R1).

    Replaces the 3 v7 features with 6 suit-relative channels that encode
    partner's bidding behavior relative to the observer's candidate contract.

    For suit contracts, the suit channels use SAME_COLOR_SUIT to determine
    same-suit, same-color, and off-color relationships between partner bids
    and the observer's trump suit. For high/low contracts (no suit relevance),
    the three suit channels are always 0.

    Args:
        seat: Observer's seat index (0-3).
        auction_transcript: Sequence of auction entry dicts, each with keys:
            seat (int), action (str: "BID" or "PASS"),
            tricks_bid (int), contract_type (str|None), trump (str|None).
        observer_contract_type: Contract family the observer is evaluating
            ("suit", "high", "low", or None). Controls suit-channel activation.
        observer_trump_suit: Trump suit letter for the observer's candidate
            contract (e.g., "H"). Only meaningful when observer_contract_type
            is "suit". None for high/low/pass.

    Returns:
        Dict with 6 features:
            partner_level_same_suit (int): 0-10
            partner_level_same_color (int): 0-10
            partner_level_off_color (int): 0-10
            partner_level_high (int): 0-10
            partner_level_low (int): 0-10
            partner_passed (int): 0 or 1
    """
    partner_seat = (seat + 2) % 4
    return _extract_player_features(
        partner_seat,
        auction_transcript,
        observer_contract_type,
        observer_trump_suit,
        prefix="partner",
    )


# Canonical v2 feature names (R1, 6 features)
PARTNER_FEATURE_NAMES_V2 = [
    "partner_level_same_suit",
    "partner_level_same_color",
    "partner_level_off_color",
    "partner_level_high",
    "partner_level_low",
    "partner_passed",
]


def extract_opponent_features(
    seat: int,
    auction_transcript: tuple[dict, ...] | list[dict],
    observer_contract_type: str | None = None,
    observer_trump_suit: str | None = None,
) -> dict[str, Any]:
    """Extract suit-relative opponent bidding features (R2).

    Extracts 12 features (6 per opponent) using the same suit-relative
    template as partner v2 features. Each opponent gets level channels
    for same_suit, same_color, off_color, high, low, and a passed flag.

    Left opponent: seat (observer + 1) % 4
    Right opponent: seat (observer + 3) % 4

    Args:
        seat: Observer's seat index (0-3).
        auction_transcript: Sequence of auction entry dicts, each with keys:
            seat (int), action (str: "BID" or "PASS"),
            tricks_bid (int), contract_type (str|None), trump (str|None).
        observer_contract_type: Contract family the observer is evaluating
            ("suit", "high", "low", or None). Controls suit-channel activation.
        observer_trump_suit: Trump suit letter for the observer's candidate
            contract (e.g., "H"). Only meaningful when observer_contract_type
            is "suit". None for high/low/pass.

    Returns:
        Dict with 12 features:
            opp_left_level_same_suit (int): 0-10
            opp_left_level_same_color (int): 0-10
            opp_left_level_off_color (int): 0-10
            opp_left_level_high (int): 0-10
            opp_left_level_low (int): 0-10
            opp_left_passed (int): 0 or 1
            opp_right_level_same_suit (int): 0-10
            opp_right_level_same_color (int): 0-10
            opp_right_level_off_color (int): 0-10
            opp_right_level_high (int): 0-10
            opp_right_level_low (int): 0-10
            opp_right_passed (int): 0 or 1
    """
    left_seat = (seat + 1) % 4
    right_seat = (seat + 3) % 4

    left_feats = _extract_player_features(
        left_seat,
        auction_transcript,
        observer_contract_type,
        observer_trump_suit,
        prefix="opp_left",
    )
    right_feats = _extract_player_features(
        right_seat,
        auction_transcript,
        observer_contract_type,
        observer_trump_suit,
        prefix="opp_right",
    )

    return {**left_feats, **right_feats}


# Canonical R2 opponent feature names (12 features: 6 left + 6 right)
OPPONENT_FEATURE_NAMES = [
    "opp_left_level_same_suit",
    "opp_left_level_same_color",
    "opp_left_level_off_color",
    "opp_left_level_high",
    "opp_left_level_low",
    "opp_left_passed",
    "opp_right_level_same_suit",
    "opp_right_level_same_color",
    "opp_right_level_off_color",
    "opp_right_level_high",
    "opp_right_level_low",
    "opp_right_passed",
]
