"""
Baseline strategies for comparison and testing.

These are simple, deterministic (or random) strategies that serve as:
- Sanity checks for the game engine
- Null models for strategy comparison
- Examples of different strategic approaches
"""

import random
from typing import List, Optional, Tuple

from ..core.cards import (
    Card,
    effective_suit,
    is_left_bower,
    is_right_bower,
    rank_strength,
)
from ..core.rules import get_legal_indices
from .base import Strategy


class BasicStrategy(Strategy):
    """
    Basic strategy: always play lowest-ranked legal card.

    Simple rule-based approach with no lookahead or trump consideration.
    """

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
        """Play the lowest-ranked legal card."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_rank(idx: int) -> int:
            return rank_strength(hand[idx], contract_type)

        return min(legal_indices, key=card_rank)


class RandomLegalStrategy(Strategy):
    """
    Strategy that chooses uniformly at random among legal moves.

    Serves as:
    - "No intelligence" baseline
    - Sanity check (should lose to all intelligent strategies)
    - Verification that suit-follow enforcement works
    """

    def __init__(self, name: str = "random_legal", seed: Optional[int] = None):
        super().__init__(name)
        self.rng = random.Random(seed)

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose uniformly at random among legal cards."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)
        return self.rng.choice(legal_indices)


class AlwaysLowestLegalStrategy(Strategy):
    """
    Strategy that always plays the lowest-ranked legal card.

    Extreme conservatism: never spend power unless forced.
    Useful for:
    - Testing card ordering logic (effective suit, bowers, trump ranking)
    - Baseline for "passive" play
    - Often does okay at not wasting trump, but loses by never taking initiative
    """

    def __init__(self, name: str = "always_lowest"):
        super().__init__(name)

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose the lowest-ranked legal card."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_rank(idx: int) -> float:
            """
            Return a numeric rank for a card, higher = stronger.
            Includes bower and trump logic for proper ordering.
            """
            card = hand[idx]

            # Bowers only exist in suit contracts
            if contract_type == "suit" and trump_suit is not None:
                # Right bower is strongest
                if is_right_bower(card, trump_suit):
                    return 1000.0

                # Left bower is next
                if is_left_bower(card, trump_suit):
                    return 900.0

                # Trump cards (by rank)
                eff_suit = effective_suit(card, trump_suit, contract_type)
                if eff_suit == trump_suit:
                    # Trump: A > K > Q > J > T (for non-bower J)
                    base = rank_strength(card, contract_type)
                    return 800.0 + base

            # Non-trump cards (or all cards in high/low contracts)
            base = rank_strength(card, contract_type)
            return base

        return min(legal_indices, key=card_rank)


class AlwaysHighestLegalStrategy(Strategy):
    """
    Strategy that always plays the highest-ranked legal card.

    Extreme aggression: cash everything immediately.
    Useful for:
    - Stressing trick resolution logic
    - Showing how bad "myopic max strength" is
    - Exposing waste patterns (burning bowers/trump early)

    In many trick-taking games, this looks powerful but performs poorly because it:
    - Overkills cheap tricks
    - Wastes trump when a low card would win
    - Sets partner up poorly
    """

    def __init__(self, name: str = "always_highest"):
        super().__init__(name)

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose the highest-ranked legal card."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_rank(idx: int) -> float:
            """
            Return a numeric rank for a card, higher = stronger.
            Includes bower and trump logic for proper ordering.
            """
            card = hand[idx]

            # Bowers only exist in suit contracts
            if contract_type == "suit" and trump_suit is not None:
                # Right bower is strongest
                if is_right_bower(card, trump_suit):
                    return 1000.0

                # Left bower is next
                if is_left_bower(card, trump_suit):
                    return 900.0

                # Trump cards (by rank)
                eff_suit = effective_suit(card, trump_suit, contract_type)
                if eff_suit == trump_suit:
                    # Trump: A > K > Q > J > T (for non-bower J)
                    base = rank_strength(card, contract_type)
                    return 800.0 + base

            # Non-trump cards (or all cards in high/low contracts)
            base = rank_strength(card, contract_type)
            return base

        return max(legal_indices, key=card_rank)
