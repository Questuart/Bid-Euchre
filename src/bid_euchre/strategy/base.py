"""
Base strategy class and shared utilities.
"""

import hashlib
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ..core.cards import (
    Card,
    effective_suit,
    is_left_bower,
    is_right_bower,
    rank_strength,
)


class Strategy(ABC):
    """Abstract base class for Bid Euchre strategies.

    Subclasses should set a ``VERSION`` class attribute (semver string)
    that is bumped on every behavioral change.  See
    ``docs/02_agent/STRATEGY_VERSIONING.md`` for bump rules.
    """

    # Default version for strategies that have not opted into versioning.
    # Concrete subclasses override this with their own semver string.
    VERSION: str = "0.0.0"

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

    def decide_bid(
        self,
        hand: List[Card],
        current_high_bid: int,
        current_winner_index: Optional[int],
        partner_index: int,
        player_index: int,
    ) -> Tuple[int, Optional[str], Optional[str]]:
        """
        Decide how many tricks to bid and for which contract.

        Args:
            hand: List of cards in player's hand
            current_high_bid: The current highest bid so far
            current_winner_index: Index of player who holds the high bid
            partner_index: Index of this player's partner
            player_index: Index of this player (0-3)

        Returns:
            Tuple of (bid_amount, contract_type, trump_suit)
            If bid_amount <= current_high_bid, it's treated as a PASS.
        """
        # Default: Always pass
        return 0, None, None

    def on_hand_start(
        self,
        starting_hand: List[Card],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> None:
        """
        Called at the start of each hand to initialize state.

        Override this to reset per-hand tracking state. This hook is called
        once per unique strategy instance (deduplicated by instance identity)
        before any choose_card calls for that hand.

        Args:
            starting_hand: The player's initial 10-card hand (copy, safe to store)
            contract_type: "suit", "high", or "low"
            trump_suit: Trump suit for "suit" contracts, None otherwise
            player_index: Index of this player (0-3)
        """
        pass

    def observe_play(
        self,
        player_index: int,
        card: Card,
        trick_plays: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
    ) -> None:
        """
        Called after each card is played to track game state.

        Override this to track played cards, infer voids, etc. This hook is
        called once per unique strategy instance (deduplicated by instance
        identity) after each card is added to the trick.

        Args:
            player_index: The player who played the card (0-3)
            card: The card that was played
            trick_plays: All plays in the current trick so far (including this one)
            contract_type: "suit", "high", or "low"
            trump_suit: Trump suit for "suit" contracts, None otherwise
        """
        pass

    def fingerprint(self) -> str:
        """Return a short hex digest identifying this strategy's version and config.

        The fingerprint is derived from the class name, ``VERSION``, and the
        instance ``name``.  Subclasses with extra configuration (feature flags,
        artifact paths, etc.) should override and include those values.

        Returns:
            8-character hex digest (first 8 chars of SHA-256).
        """
        parts = [
            type(self).__name__,
            type(self).VERSION,
            self.name,
        ]
        blob = "|".join(parts).encode()
        return hashlib.sha256(blob).hexdigest()[:8]

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
