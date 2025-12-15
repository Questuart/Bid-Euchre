from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from ..core.cards import (
    Card,
    effective_suit,
    rank_strength,
    is_right_bower,
    is_left_bower,
)
from ..core.rules import trick_winner


class Strategy(ABC):
    """Abstract base class for Bid Euchre strategies."""

    def __init__(self, name: str = "unnamed"):
        self.name = name

    @abstractmethod
    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """
        Choose which card to play from the given hand.

        Args:
            hand: List of cards in player's hand
            plays_so_far: List of (player_index, card) tuples played so far in trick
            contract_type: "suit", "high", or "low"
            trump_suit: Trump suit for "suit" contracts, None otherwise
            player_index: Index of this player (0-3)

        Returns:
            Index of card to play from hand
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        return str(self)


class BasicStrategy(Strategy):
    """Basic strategy: play lowest card in suit, or lowest card overall."""

    def __init__(self, name: str = "basic"):
        super().__init__(name)

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        return choose_card_basic(hand, plays_so_far, contract_type, trump_suit, player_index)


class GreedyStrategy(Strategy):
    """Greedy strategy: choose card that wins trick if possible, otherwise dump lowest value card."""

    def __init__(self, name: str = "greedy"):
        super().__init__(name)

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        return choose_card_greedy(hand, plays_so_far, contract_type, trump_suit, player_index)


# Legacy function interface (for backwards compatibility)
def choose_card_basic(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    contract_type: str,
    trump_suit: Optional[str],
    player_index: int,
) -> int:
    """
    Very simple bot:
    - If you can follow the led suit, play your lowest-ranked card in that suit.
    - If you cannot follow suit, play your lowest-ranked card overall.

    Ignores trump/bower value beyond rank ordering.
    Returns the INDEX in `hand` of the chosen card.
    """

    # Determine led suit
    if plays_so_far:
        _, lead_card = plays_so_far[0]
        led_suit = effective_suit(lead_card, trump_suit, contract_type)
    else:
        led_suit = None

    # 1) Try to follow suit with lowest-rank card
    best_idx: Optional[int] = None
    best_rank: Optional[int] = None

    if led_suit is not None:
        for i, c in enumerate(hand):
            if effective_suit(c, trump_suit, contract_type) == led_suit:
                r = rank_strength(c, contract_type)
                if best_rank is None or r < best_rank:
                    best_rank = r
                    best_idx = i

        if best_idx is not None:
            return best_idx

    # 2) If we can't follow suit, play overall lowest-ranked card
    best_idx = None
    best_rank = None
    for i, c in enumerate(hand):
        r = rank_strength(c, contract_type)
        if best_rank is None or r < best_rank:
            best_rank = r
            best_idx = i

    assert best_idx is not None  # hand must be non-empty when called
    return best_idx


def _card_value_for_dump(
    card: Card,
    contract_type: str,
    trump_suit: Optional[str],
) -> int:
    """
    Heuristic "cost" of spending this card.

    Higher value = more precious, so we avoid dumping it if possible.
    """
    base = rank_strength(card, contract_type)

    if contract_type == "suit" and trump_suit is not None:
        eff = effective_suit(card, trump_suit, contract_type)
        if eff == trump_suit:
            # Trump is more precious than offsuit at the same rank
            base += 10
            # Bump bowers even higher
            if is_right_bower(card, trump_suit):
                base += 5
            elif is_left_bower(card, trump_suit):
                base += 4

    return base


def choose_card_greedy(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    contract_type: str,
    trump_suit: Optional[str],
    player_index: int,
) -> int:
    """
    Greedy trick-level bot:

    - Determine the set of legal cards (must follow led suit if possible).
    - For each legal card, simulate adding it to the trick and see who currently
      wins the trick (using trick_winner on the partial trick).
    - If any legal card is currently winning:
        *play the cheapest winning card* by _card_value_for_dump.
    - Otherwise:
        *play the cheapest legal card* by _card_value_for_dump (dump trash).

    This is still myopic (no lookahead across tricks), but much less dumb than
    always throwing the lowest rank, and it treats trump/bowers as valuable.
    """

    # Determine led suit, if any
    if plays_so_far:
        _, lead_card = plays_so_far[0]
        led_suit = effective_suit(lead_card, trump_suit, contract_type)
    else:
        led_suit = None

    # Build list of legal indices given follow-suit rule
    legal_indices: List[int] = []

    if led_suit is not None:
        follow_indices = [
            i for i, c in enumerate(hand)
            if effective_suit(c, trump_suit, contract_type) == led_suit
        ]
        if follow_indices:
            legal_indices = follow_indices
        else:
            legal_indices = list(range(len(hand)))
    else:
        # On lead, anything goes
        legal_indices = list(range(len(hand)))

    assert legal_indices, "There must be at least one legal card to play"

    # For each legal card, check if it currently wins the trick
    winning_candidates: List[int] = []
    for idx in legal_indices:
        card = hand[idx]
        provisional_plays = plays_so_far + [(player_index, card)]
        winner = trick_winner(
            provisional_plays,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )
        if winner == player_index:
            winning_candidates.append(idx)

    def card_value(idx: int) -> int:
        return _card_value_for_dump(hand[idx], contract_type, trump_suit)

    # If we have any card that is currently winning, play the cheapest winner
    if winning_candidates:
        best_idx = min(winning_candidates, key=card_value)
        return best_idx

    # Otherwise, dump the cheapest legal card
    best_idx = min(legal_indices, key=card_value)
    return best_idx
