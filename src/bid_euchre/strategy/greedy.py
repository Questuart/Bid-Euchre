"""
Greedy strategies with 1-trick lookahead.

These strategies try to win the current trick if possible,
with variations that add partner awareness and trump conservation.
"""

from typing import List, Optional, Set, Tuple

from ..core.cards import Card, cards_that_beat, effective_suit
from ..core.rules import get_legal_indices, trick_winner
from .base import Strategy, card_value_for_dump


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


class GluttonStrategy(Strategy):
    """
    Glutton strategy with partner awareness, trump conservation,
    and card-aware "sure win" logic.

    Improvements over GreedyStrategy:
    1. Partner awareness - don't overkill partner's winning card
    2. Trump conservation - save trump when losing to set up future tricks
    3. Card awareness - track played cards to determine "sure winners"
    4. Decision logging - optional debug output

    Strategy:
    - When LEADING: Play highest value card
    - When FOLLOWING:
      * If partner is winning: dump cheapest legal card (don't overkill)
      * If we have a SURE winner (no remaining card can beat it): play cheapest sure winner
      * If 4th to act and can win: play cheapest winner (safe since no one follows)
      * Otherwise: dump cheapest legal card (don't commit uncertain cards)

    "Sure winner" means: no card remaining in play (not in our hand, not already
    played) can beat this card. For example, right bower is always a sure winner;
    left bower is a sure winner only if right bower has been played.

    Strengths:
    - Partner-aware (doesn't waste cards overkilling partner)
    - Card-aware (tracks what's been played to make informed decisions)
    - Conservative when uncertain (doesn't waste cards on risky wins)

    Weaknesses:
    - More conservative than basic greedy (may miss some aggressive opportunities)
    """

    def __init__(self, name: str = "glutton", debug: bool = False):
        super().__init__(name)
        self.debug = debug
        self.decision_log = []
        # Card tracking for sure-win logic
        self._played_cards: Set[Card] = set()

    def _is_sure_winner(
        self,
        candidate: Card,
        plays_so_far: List[Tuple[int, Card]],
        hand: List[Card],
        contract_type: str,
        trump_suit: Optional[str],
    ) -> bool:
        """
        Returns True if candidate cannot be beaten by any remaining card.

        A card is a "sure winner" if:
        1. It currently wins the trick (beats all plays_so_far)
        2. No remaining card in play (not in our hand, not already played) can beat it

        This enables conservative play: only commit to winning when guaranteed.
        """
        # Determine led suit
        if plays_so_far:
            led_suit = effective_suit(plays_so_far[0][1], trump_suit, contract_type)
        else:
            led_suit = effective_suit(candidate, trump_suit, contract_type)

        # Get all cards that could beat our candidate
        beating_cards = cards_that_beat(candidate, led_suit, trump_suit, contract_type)

        # Remove cards already played (tracked across tricks)
        remaining_threats = beating_cards - self._played_cards

        # Remove cards in our hand (we know opponents don't have them)
        remaining_threats = remaining_threats - set(hand)

        # Also remove cards played in current trick (already in plays_so_far)
        for _, card in plays_so_far:
            remaining_threats.discard(card)

        # If no threats remain, it's a sure winner
        return len(remaining_threats) == 0

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose card with partner awareness, trump conservation, and sure-win logic."""
        # Reset tracking on new hand (heuristic: full hand + leading = first trick)
        if len(hand) == 10 and not plays_so_far:
            self._played_cards = set()

        # Accumulate plays from current trick into tracking set
        for _, card in plays_so_far:
            self._played_cards.add(card)

        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # SPECIAL CASE: When leading, play highest value card
        if not plays_so_far:
            choice = max(legal_indices, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "leading",
                    "action": "play_highest",
                    "card": str(hand[choice]),
                })
            # Record our play for tracking
            self._played_cards.add(hand[choice])
            return choice

        # Phase 1: Check partner awareness
        partner_winning = False
        if len(plays_so_far) >= 1:
            current_winner = trick_winner(
                plays_so_far,
                contract_type=contract_type,
                trump_suit=trump_suit,
            )
            partner_index = (player_index + 2) % 4
            partner_winning = (current_winner == partner_index)

        # Find cards that currently win the trick
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

        # Partition winning candidates into "sure winners" and "risky winners"
        sure_winners = [
            idx for idx in winning_candidates
            if self._is_sure_winner(hand[idx], plays_so_far, hand, contract_type, trump_suit)
        ]

        # Phase 2: Decision logic with partner awareness and sure-win logic
        if partner_winning:
            # Partner is currently winning - don't overkill
            choice = min(legal_indices, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "partner_winning",
                    "action": "dump_cheap",
                    "card": str(hand[choice]),
                })
            self._played_cards.add(hand[choice])
            return choice

        if sure_winners:
            # We have a guaranteed winner - play cheapest sure winner
            choice = min(sure_winners, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "sure_win",
                    "action": "play_cheap_sure_winner",
                    "card": str(hand[choice]),
                })
            self._played_cards.add(hand[choice])
            return choice

        if len(plays_so_far) == 3 and winning_candidates:
            # Last to act (4th position) - any winner is safe, no one follows
            choice = min(winning_candidates, key=card_value)
            if self.debug:
                self.decision_log.append({
                    "scenario": "last_to_act_win",
                    "action": "play_cheap_winner",
                    "card": str(hand[choice]),
                })
            self._played_cards.add(hand[choice])
            return choice

        # Can't win safely - dump instead
        # Phase 3: Trump conservation - save trump for future tricks
        if len(hand) > 1 and contract_type == "suit" and trump_suit is not None:
            trump_cards = [
                idx for idx in legal_indices
                if effective_suit(hand[idx], trump_suit, contract_type) == trump_suit
            ]

            if trump_cards:
                non_trump = [idx for idx in legal_indices if idx not in trump_cards]
                if non_trump:
                    choice = min(non_trump, key=card_value)
                    if self.debug:
                        self.decision_log.append({
                            "scenario": "cant_win_save_trump",
                            "action": "dump_offsuit",
                            "card": str(hand[choice]),
                        })
                    self._played_cards.add(hand[choice])
                    return choice

        # Default: dump cheapest card
        choice = min(legal_indices, key=card_value)
        if self.debug:
            self.decision_log.append({
                "scenario": "default_dump",
                "action": "dump_cheap",
                "card": str(hand[choice]),
            })
        self._played_cards.add(hand[choice])
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
