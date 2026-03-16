"""
Card exchange phase for moon bids in Bid Euchre.

When a player wins the auction with a moon bid, they exchange 2 cards with
their partner before trick play begins. The mooner gives their 2 worst cards
and receives the partner's 2 best cards (for the declared contract).
"""

from typing import List, Optional, Tuple

from ..core.cards import (
    Card,
    effective_suit,
    is_left_bower,
    is_right_bower,
)


def _card_value_for_discard(
    card: Card,
    contract_type: str,
    trump_suit: Optional[str],
    hand: List[Card],
) -> Tuple:
    """
    Compute a sortable value for a card from the mooner's perspective.

    Lower value = worse card = better candidate for discarding.

    For suit contracts:
      - Bowers are highest value (right > left)
      - Trump cards by rank
      - Aces of non-trump suits
      - Non-trump cards: prefer keeping cards in longer suits, higher ranks

    For high contracts:
      - A > K > Q > J > T (standard rank order)

    For low contracts:
      - T > J > Q > K > A (inverted rank order — tens are strongest)
    """
    rank_order_high = {"T": 0, "J": 1, "Q": 2, "K": 3, "A": 4}
    rank_order_low = {"A": 0, "K": 1, "Q": 2, "J": 3, "T": 4}

    if contract_type == "suit" and trump_suit is not None:
        # Right bower: highest possible value
        if is_right_bower(card, trump_suit):
            return (4, 99, 99)
        # Left bower: second highest
        if is_left_bower(card, trump_suit):
            return (4, 98, 99)

        eff = effective_suit(card, trump_suit, contract_type)

        if eff == trump_suit:
            # Other trump: valued by rank
            return (3, rank_order_high[card.rank], 0)

        # Non-trump: count cards in this suit (effective suit) to measure suit length
        suit_length = sum(
            1 for c in hand if effective_suit(c, trump_suit, contract_type) == eff
        )
        # Aces are more valuable
        rank_val = rank_order_high[card.rank]
        # Prefer keeping longer-suit cards (more likely to follow suit)
        # and higher-rank cards within a suit
        return (1, rank_val, suit_length)

    elif contract_type == "high":
        return (1, rank_order_high[card.rank], 0)

    elif contract_type == "low":
        return (1, rank_order_low[card.rank], 0)

    else:
        raise ValueError(f"Unknown contract_type: {contract_type}")


def _select_mooner_discards(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str],
    n_cards: int = 2,
) -> List[int]:
    """
    Select indices of the n worst cards in the mooner's hand to discard.

    Returns indices sorted descending (so popping from hand works without
    index shifting).
    """
    # Compute value for each card
    card_values = [
        (_card_value_for_discard(card, contract_type, trump_suit, hand), i)
        for i, card in enumerate(hand)
    ]
    # Sort by value ascending — worst cards first
    card_values.sort(key=lambda x: x[0])

    # Take the n worst
    indices = [idx for _, idx in card_values[:n_cards]]
    # Sort descending for safe removal
    return sorted(indices, reverse=True)


def _card_value_for_partner(
    card: Card,
    contract_type: str,
    trump_suit: Optional[str],
) -> Tuple:
    """
    Compute a sortable value for a card from the partner's perspective
    (selecting best cards to give to mooner).

    Higher value = better card for the mooner = should be given.

    For suit contracts:
      - Bowers first (right > left)
      - Other trump by rank
      - Aces of non-trump suits

    For high contracts:
      - A > K > ... (aces first, then kings)

    For low contracts:
      - T > J > ... (tens first, then jacks)
    """
    rank_order_high = {"T": 0, "J": 1, "Q": 2, "K": 3, "A": 4}
    rank_order_low = {"A": 0, "K": 1, "Q": 2, "J": 3, "T": 4}

    if contract_type == "suit" and trump_suit is not None:
        if is_right_bower(card, trump_suit):
            return (4, 99)
        if is_left_bower(card, trump_suit):
            return (4, 98)

        eff = effective_suit(card, trump_suit, contract_type)
        if eff == trump_suit:
            return (3, rank_order_high[card.rank])

        # Non-trump aces are valuable
        if card.rank == "A":
            return (2, 0)

        # Other non-trump cards ranked normally
        return (1, rank_order_high[card.rank])

    elif contract_type == "high":
        return (1, rank_order_high[card.rank])

    elif contract_type == "low":
        return (1, rank_order_low[card.rank])

    else:
        raise ValueError(f"Unknown contract_type: {contract_type}")


def _select_partner_gifts(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str],
    n_cards: int = 2,
) -> List[int]:
    """
    Select indices of the n best cards in the partner's hand to give.

    Returns indices sorted descending (so popping from hand works without
    index shifting).
    """
    card_values = [
        (_card_value_for_partner(card, contract_type, trump_suit), i)
        for i, card in enumerate(hand)
    ]
    # Sort descending — best cards first
    card_values.sort(key=lambda x: x[0], reverse=True)

    indices = [idx for _, idx in card_values[:n_cards]]
    return sorted(indices, reverse=True)


def perform_exchange(
    mooner_hand: List[Card],
    partner_hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str],
) -> Tuple[List[Card], List[Card], List[Card], List[Card]]:
    """
    Perform 2-card exchange between mooner and partner for a moon bid.

    The mooner gives their 2 worst cards to the partner and receives
    the partner's 2 best cards (for the declared contract type).

    Args:
        mooner_hand: The mooner's 10-card hand (will not be mutated).
        partner_hand: The partner's 10-card hand (will not be mutated).
        contract_type: "suit", "high", or "low".
        trump_suit: Trump suit for suit contracts, None for high/low.

    Returns:
        (new_mooner_hand, new_partner_hand, cards_given, cards_received) where:
        - new_mooner_hand: mooner's 10-card hand after exchange
        - new_partner_hand: partner's 10-card hand after exchange
        - cards_given: cards the mooner gave to partner (mooner's 2 worst)
        - cards_received: cards the mooner received from partner (partner's 2 best)

    Raises:
        ValueError: If hand sizes are not 10 or contract_type is invalid.
    """
    if len(mooner_hand) != 10:
        raise ValueError(f"Mooner hand must have 10 cards, got {len(mooner_hand)}")
    if len(partner_hand) != 10:
        raise ValueError(f"Partner hand must have 10 cards, got {len(partner_hand)}")

    # Work on copies to avoid mutating inputs
    m_hand = list(mooner_hand)
    p_hand = list(partner_hand)

    # Select cards to exchange
    mooner_discard_indices = _select_mooner_discards(m_hand, contract_type, trump_suit)
    partner_gift_indices = _select_partner_gifts(p_hand, contract_type, trump_suit)

    # Extract the cards (pop in reverse-sorted order to preserve indices)
    mooner_discards = []
    for idx in mooner_discard_indices:
        mooner_discards.append(m_hand.pop(idx))

    partner_gifts = []
    for idx in partner_gift_indices:
        partner_gifts.append(p_hand.pop(idx))

    # Perform the swap: mooner gets partner's best, partner gets mooner's worst
    m_hand.extend(partner_gifts)
    p_hand.extend(mooner_discards)

    # Validate post-conditions
    assert len(m_hand) == 10, f"Mooner hand has {len(m_hand)} cards after exchange"
    assert len(p_hand) == 10, f"Partner hand has {len(p_hand)} cards after exchange"

    # Validate no net cards created or destroyed
    # (In a double deck, duplicates are legal, but total card count must be preserved)
    original_total = sorted(mooner_hand + partner_hand, key=lambda c: (c.suit, c.rank))
    new_total = sorted(m_hand + p_hand, key=lambda c: (c.suit, c.rank))
    assert original_total == new_total, "Exchange created or destroyed cards"

    return m_hand, p_hand, mooner_discards, partner_gifts
