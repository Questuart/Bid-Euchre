from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import random
from ..core.cards import (
    Card,
    effective_suit,
    rank_strength,
    is_right_bower,
    is_left_bower,
)
from ..core.rules import trick_winner, get_legal_indices


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
    # Get legal plays using single source of truth
    legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

    # Play the lowest-ranked legal card
    def card_rank(idx: int) -> int:
        return rank_strength(hand[idx], contract_type)

    return min(legal_indices, key=card_rank)


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
    # Get legal plays using single source of truth
    legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

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
        return min(winning_candidates, key=card_value)

    # Otherwise, dump the cheapest legal card
    return min(legal_indices, key=card_value)


class ImprovedGreedyStrategy(Strategy):
    """
    Improved greedy strategy with:
    1. Partner awareness - don't overkill partner's winning card
    2. 2-trick lookahead - consider cards remaining after this trick
    3. Trump establishment - value setting up future tricks
    """

    def __init__(self, name: str = "improved_greedy", debug: bool = False):
        super().__init__(name)
        self.debug = debug
        self.decision_log = []

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose card with partner awareness and 2-trick lookahead."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        # Phase 1: Check partner awareness
        partner_winning = False
        if len(plays_so_far) >= 1:
            # Determine current winner
            current_winner = trick_winner(
                plays_so_far,
                contract_type=contract_type,
                trump_suit=trump_suit,
            )
            # Partner is 2 positions away (0↔2, 1↔3)
            partner_index = (player_index + 2) % 4
            partner_winning = (current_winner == partner_index)

        # Find cards that win the trick
        winning_candidates = []
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

        # Phase 2: Decision logic with partner awareness
        if partner_winning:
            # Partner is currently winning - don't overkill
            # Play the cheapest legal card (let partner take it)
            choice = min(legal_indices, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "partner_winning",
                    "action": "dump_cheap",
                    "card": str(hand[choice]),
                })
            return choice

        if winning_candidates:
            # We can win - play cheapest winning card
            choice = min(winning_candidates, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "can_win",
                    "action": "play_cheap_winner",
                    "card": str(hand[choice]),
                })
            return choice

        # Can't win - decide between dumping and setting up
        # Phase 3: 2-trick lookahead - consider remaining cards
        if len(hand) > 1 and contract_type == "suit" and trump_suit is not None:
            # Check if we have strong trump for future tricks
            trump_cards = [
                idx for idx in legal_indices
                if effective_suit(hand[idx], trump_suit, contract_type) == trump_suit
            ]

            # If we're losing this trick and have trump, save it
            if trump_cards:
                # Dump non-trump if possible
                non_trump = [idx for idx in legal_indices if idx not in trump_cards]
                if non_trump:
                    choice = min(non_trump, key=card_value)
                    if self.debug:
                        self.decision_log.append({
                            "scenario": "cant_win_save_trump",
                            "action": "dump_offsuit",
                            "card": str(hand[choice]),
                        })
                    return choice

        # Default: dump cheapest card
        choice = min(legal_indices, key=card_value)
        if self.debug:
            self.decision_log.append({
                "scenario": "default_dump",
                "action": "dump_cheap",
                "card": str(hand[choice]),
            })
        return choice


class RandomLegalStrategy(Strategy):
    """Strategy that chooses uniformly at random among legal moves."""

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
    """Strategy that always plays the lowest-ranked legal card."""

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
            For AlwaysLowest, we'll use min of this value.
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
    """Strategy that always plays the highest-ranked legal card."""

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
            For AlwaysHighest, we'll use max of this value.
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
