"""
Partner bidding context features extracted from auction_transcript.

These features capture information about the partner's bidding behavior
during the auction phase. They are separate from hand evaluation features
(hand_eval.py) because they depend on auction state, not just cards.

Features:
    partner_bid_level: Highest bid level partner made (0 if passed/no action)
    partner_passed: 1 if partner explicitly passed, 0 otherwise
    partner_suit_match: 1 if partner bid same contract family as observer context
    partner_bid_confidence: partner_bid_level / 10 (normalized to [0, 1])
"""

from __future__ import annotations

from typing import Any


def extract_partner_features(
    seat: int,
    auction_transcript: tuple[dict, ...] | list[dict],
    observer_best_contract: str | None = None,
) -> dict[str, Any]:
    """Extract partner bidding context features from auction transcript.

    Args:
        seat: Observer's seat index (0-3).
        auction_transcript: Sequence of auction entry dicts, each with keys:
            seat (int), action (str: "BID" or "PASS"),
            tricks_bid (int), contract_type (str|None), trump (str|None).
        observer_best_contract: Contract family the observer is evaluating
            ("suit", "high", or "low"). Used for partner_suit_match.
            If None, partner_suit_match defaults to 0.

    Returns:
        Dict with 4 features:
            partner_bid_level (int): 0-10, highest bid partner made
            partner_passed (int): 0 or 1
            partner_suit_match (int): 0 or 1
            partner_bid_confidence (float): 0.0-1.0
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

    partner_bid_confidence = partner_bid_level / 10.0

    return {
        "partner_bid_level": partner_bid_level,
        "partner_passed": partner_passed,
        "partner_suit_match": partner_suit_match,
        "partner_bid_confidence": partner_bid_confidence,
    }


# Canonical feature names for schema validation and filtering
PARTNER_FEATURE_NAMES = [
    "partner_bid_level",
    "partner_passed",
    "partner_suit_match",
    "partner_bid_confidence",
]
