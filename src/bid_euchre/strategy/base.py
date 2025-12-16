"""
Base strategy class and shared utilities.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from ..core.cards import (
    Card,
    effective_suit,
    rank_strength,
    is_right_bower,
    is_left_bower,
)


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


def card_value_for_dump(
    card: Card,
    contract_type: str,
    trump_suit: Optional[str],
) -> int:
    """
    Heuristic "cost" of spending this card.

    Higher value = more precious, so we avoid dumping it if possible.
    Used by greedy strategies to determine which cards to conserve.
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

