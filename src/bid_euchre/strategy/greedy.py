"""
Greedy strategies with 1-trick lookahead.

These strategies try to win the current trick if possible,
with variations that add partner awareness and trump conservation.
"""

from typing import List, Tuple, Optional

from .base import Strategy, card_value_for_dump
from ..core.cards import Card, effective_suit
from ..core.rules import trick_winner, get_legal_indices


class GreedyStrategy(Strategy):
    """
    Greedy strategy with 1-trick lookahead.
    
    Strategy:
    - When LEADING: Play the highest-value card to establish dominance
    - When FOLLOWING:
      * If any legal card wins the trick: play the cheapest winning card
      * Otherwise: dump the cheapest legal card
    
    Strengths:
    - Simple and fast
    - Treats trump/bowers as valuable
    
    Weaknesses:
    - No partner awareness (may overkill partner's winning card)
    - No multi-trick lookahead
    - Myopic (doesn't consider future tricks)
    """

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
        """Choose card with 1-trick lookahead."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # SPECIAL CASE: When leading, play highest value card
        if not plays_so_far:
            return max(legal_indices, key=card_value)

        # FOLLOWING: For each legal card, check if it currently wins the trick
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

        # If we have any card that is currently winning, play the cheapest winner
        if winning_candidates:
            return min(winning_candidates, key=card_value)

        # Otherwise, dump the cheapest legal card
        return min(legal_indices, key=card_value)


class ImprovedGreedyStrategy(Strategy):
    """
    Improved greedy strategy with partner awareness and trump conservation.
    
    Improvements over GreedyStrategy:
    1. Partner awareness - don't overkill partner's winning card
    2. Trump conservation - save trump when losing to set up future tricks
    3. Decision logging - optional debug output
    
    Strategy:
    - When LEADING: Play highest value card
    - When FOLLOWING:
      * If partner is winning: dump cheapest legal card (don't overkill)
      * If we can win: play cheapest winning card
      * If we can't win and have trump: save trump for later, dump offsuit
      * Otherwise: dump cheapest legal card
    
    Strengths:
    - Partner-aware (doesn't waste cards overkilling partner)
    - Trump conservation (saves strong cards when losing)
    
    Weaknesses:
    - Still mostly myopic (only 1-trick lookahead)
    - Conservative bias (may miss aggressive opportunities)
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
        """Choose card with partner awareness and trump conservation."""
        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # SPECIAL CASE: When leading, play highest value card (same as fixed greedy)
        if not plays_so_far:
            choice = max(legal_indices, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "leading",
                    "action": "play_highest",
                    "card": str(hand[choice]),
                })
            return choice

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
        # Phase 3: Trump conservation - save trump for future tricks
        if len(hand) > 1 and contract_type == "suit" and trump_suit is not None:
            # Check if we have trump
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


# Legacy function interface (for backwards compatibility)
def choose_card_basic(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    contract_type: str,
    trump_suit: Optional[str],
    player_index: int,
) -> int:
    """
    Legacy function interface for basic strategy.
    Kept for backwards compatibility.
    """
    from .baselines import BasicStrategy
    return BasicStrategy().choose_card(hand, plays_so_far, contract_type, trump_suit, player_index)


def choose_card_greedy(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    contract_type: str,
    trump_suit: Optional[str],
    player_index: int,
) -> int:
    """
    Legacy function interface for greedy strategy.
    Kept for backwards compatibility.
    """
    return GreedyStrategy().choose_card(hand, plays_so_far, contract_type, trump_suit, player_index)

