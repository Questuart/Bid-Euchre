"""
Greedy strategies with 1-trick lookahead.

These strategies try to win the current trick if possible,
with variations that add partner awareness and trump conservation.
"""

from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

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
    double-deck card tracking, position-aware aggression, and smart leads/discards.

    Improvements over GreedyStrategy:
    1. Partner awareness - don't overkill partner's winning card
    2. Trump conservation - save trump when losing to set up future tricks
    3. Card awareness - track played cards (double-deck correct) for "sure winners"
    4. Void inference - track which seats are void in which suits
    5. Position-aware aggression - take likely wins in 3rd seat
    6. Smart leads - lead Aces, draw trump appropriately, use longest suit
    7. Smart discards - prefer shortest suit to create voids
    8. Decision logging - optional debug output

    "Sure winner" accounting for double deck: each card exists 2x, so a card
    is only a sure winner when all copies of higher cards are accounted for.

    Strengths:
    - Partner-aware (doesn't waste cards overkilling partner)
    - Card-aware (tracks what's been played to make informed decisions)
    - Position-aware (takes likely wins in advantageous positions)
    - Human-like leads and discards

    Weaknesses:
    - Deterministic (no randomness for variety)
    - No multi-trick lookahead beyond "sure winner" logic
    """

    def __init__(self, name: str = "glutton", debug: bool = False):
        super().__init__(name)
        self.debug = debug
        self.decision_log: List[dict] = []
        # Double-deck aware tracking (each card exists 0-2 times)
        self._seen_counts: Dict[Card, int] = {}
        # Void inference: which seats are void in which effective suits
        self._void_suits_by_seat: Dict[int, Set[str]] = {
            0: set(),
            1: set(),
            2: set(),
            3: set(),
        }
        # Contract context (set by on_hand_start)
        self._contract_type: str = "high"
        self._trump_suit: Optional[str] = None
        self._player_index: int = 0

    def on_hand_start(
        self,
        starting_hand: List[Card],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> None:
        """Reset per-hand state at the start of each hand."""
        self._seen_counts = {}
        self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
        self._contract_type = contract_type
        self._trump_suit = trump_suit
        self._player_index = player_index
        if self.debug:
            self.decision_log = []

    def observe_play(
        self,
        player_index: int,
        card: Card,
        trick_plays: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
    ) -> None:
        """Track played cards and infer voids from play patterns."""
        # Increment seen count (clamp at 2 for double deck)
        self._seen_counts[card] = min(2, self._seen_counts.get(card, 0) + 1)

        # Infer voids: if a player didn't follow suit, they're void in led suit
        if len(trick_plays) >= 1:
            led_suit = effective_suit(trick_plays[0][1], trump_suit, contract_type)
            played_eff = effective_suit(card, trump_suit, contract_type)
            if played_eff != led_suit:
                self._void_suits_by_seat[player_index].add(led_suit)

    def _threat_copies_remaining(
        self,
        card: Card,
        led_suit: str,
        hand: List[Card],
    ) -> int:
        """Count how many copies of cards that beat `card` are still unaccounted for."""
        beating = cards_that_beat(card, led_suit, self._trump_suit, self._contract_type)
        hand_counter = Counter(hand)
        total = 0
        for threat in beating:
            seen = self._seen_counts.get(threat, 0)
            in_hand = hand_counter.get(threat, 0)
            remaining = max(0, 2 - seen - in_hand)
            total += remaining
        return total

    def _is_sure_winner(
        self,
        candidate: Card,
        plays_so_far: List[Tuple[int, Card]],
        hand: List[Card],
    ) -> bool:
        """
        Returns True if candidate cannot be beaten by any remaining card.

        Double-deck correct: a card is a sure winner only when all copies
        of higher-ranked cards are either seen or in our hand.
        """
        # Determine led suit
        if plays_so_far:
            led_suit = effective_suit(
                plays_so_far[0][1], self._trump_suit, self._contract_type
            )
        else:
            led_suit = effective_suit(candidate, self._trump_suit, self._contract_type)

        # Get all cards that could beat our candidate
        beating_cards = cards_that_beat(
            candidate, led_suit, self._trump_suit, self._contract_type
        )

        # For each threat, check if all copies are accounted for
        hand_counter = Counter(hand)
        for threat in beating_cards:
            seen = self._seen_counts.get(threat, 0)
            in_hand = hand_counter.get(threat, 0)
            remaining = 2 - seen - in_hand
            if remaining > 0:
                return False  # At least one copy of this threat still exists

        return True

    def _count_effective_suit(self, hand: List[Card], suit: str) -> int:
        """Count cards in hand that belong to the given effective suit."""
        return sum(
            1
            for c in hand
            if effective_suit(c, self._trump_suit, self._contract_type) == suit
        )

    def _get_suit_counts(self, hand: List[Card]) -> Dict[str, int]:
        """Get count of cards by effective suit in hand."""
        counts: Dict[str, int] = {}
        for c in hand:
            eff = effective_suit(c, self._trump_suit, self._contract_type)
            counts[eff] = counts.get(eff, 0) + 1
        return counts

    def _choose_lead(
        self,
        hand: List[Card],
        legal_indices: List[int],
    ) -> int:
        """Choose which card to lead with human-like heuristics."""

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        suit_counts = self._get_suit_counts(hand)

        if self._contract_type == "suit" and self._trump_suit is not None:
            # SUIT CONTRACT LEADS

            # 1. Look for non-trump Aces
            non_trump_aces = [
                idx
                for idx in legal_indices
                if hand[idx].rank == "A"
                and effective_suit(hand[idx], self._trump_suit, self._contract_type)
                != self._trump_suit
            ]
            if non_trump_aces:
                # Prefer Ace from shortest non-trump suit (to create void potential)
                def ace_priority(idx: int) -> Tuple[int, int]:
                    eff = effective_suit(
                        hand[idx], self._trump_suit, self._contract_type
                    )
                    return (suit_counts.get(eff, 0), -card_value(idx))

                return min(non_trump_aces, key=ace_priority)

            # 2. Draw trump if holding >= 4 trumps and NOT holding both bowers
            trump_count = self._count_effective_suit(hand, self._trump_suit)
            trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                == self._trump_suit
            ]
            if trump_count >= 4 and trump_indices:
                # Check for both bowers
                from ..core.cards import is_left_bower, is_right_bower

                has_right = any(
                    is_right_bower(hand[idx], self._trump_suit) for idx in trump_indices
                )
                has_left = any(
                    is_left_bower(hand[idx], self._trump_suit) for idx in trump_indices
                )
                if not (has_right and has_left):
                    # Lead lowest trump to draw trump without burning top cards
                    return min(trump_indices, key=card_value)

            # 3. Lead from longest non-trump suit, highest card in that suit
            non_trump_suits = [s for s in suit_counts if s != self._trump_suit]
            if non_trump_suits:
                longest_suit = max(non_trump_suits, key=lambda s: suit_counts.get(s, 0))
                longest_suit_indices = [
                    idx
                    for idx in legal_indices
                    if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                    == longest_suit
                ]
                if longest_suit_indices:
                    return max(longest_suit_indices, key=card_value)

            # Fallback: highest value card
            return max(legal_indices, key=card_value)

        else:
            # HIGH / LOW CONTRACT LEADS
            #
            # HIGH: lead strongest card to establish dominance (A first)
            # LOW:  lead weakest card to conserve strong cards (T, J)
            #       for following plays where they win tricks efficiently
            select = min if self._contract_type == "low" else max
            if suit_counts:
                longest_suit = max(
                    suit_counts.keys(), key=lambda s: suit_counts.get(s, 0)
                )
                longest_suit_indices = [
                    idx for idx in legal_indices if hand[idx].suit == longest_suit
                ]
                if longest_suit_indices:
                    return select(longest_suit_indices, key=card_value)

            # Fallback
            return select(legal_indices, key=card_value)

    def _choose_discard(
        self,
        hand: List[Card],
        legal_indices: List[int],
    ) -> int:
        """Choose which card to discard with smart void-creation logic."""

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        # Get suit distribution
        suit_counts = self._get_suit_counts(hand)

        if self._contract_type == "suit" and self._trump_suit is not None:
            # Prefer non-trump cards
            non_trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                != self._trump_suit
            ]

            if non_trump_indices:
                # Prefer shortest non-trump suit (to create/strengthen voids)
                def discard_priority(idx: int) -> Tuple[int, int]:
                    eff = effective_suit(
                        hand[idx], self._trump_suit, self._contract_type
                    )
                    # Lower suit count = better (creating void)
                    # Lower card value = better (save strong cards)
                    return (suit_counts.get(eff, 0), card_value(idx))

                return min(non_trump_indices, key=discard_priority)

            # Only trump left - discard cheapest
            return min(legal_indices, key=card_value)

        else:
            # HIGH / LOW - no trump, so void creation has no benefit
            # Just discard the cheapest card (lowest value)
            return min(legal_indices, key=card_value)

    def _should_trump_in(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        player_index: int,
    ) -> bool:
        """
        Returns True if we should consider trumping in to protect partner.

        Conditions (ALL must be true):
        - Suit contract with trump
        - Not leading (plays_so_far not empty)
        - We are void in led suit (can't follow)
        - We have trump in hand
        - We are 3rd seat (4th seat opponent plays after us)
        - 4th seat is void in led suit AND might have trump

        This protects partner from having their winning card trumped by 4th seat.
        """
        # Guard: must be suit contract with trump
        if self._contract_type != "suit" or self._trump_suit is None:
            return False

        # Guard: must be following (not leading)
        if not plays_so_far:
            return False

        # Get led suit
        led_suit = effective_suit(
            plays_so_far[0][1], self._trump_suit, self._contract_type
        )

        # Check if we're void in led suit (can't follow)
        can_follow = any(
            effective_suit(hand[idx], self._trump_suit, self._contract_type) == led_suit
            for idx in range(len(hand))
        )
        if can_follow:
            return False  # Can follow suit, not a trump-in decision

        # Check if we have trump
        trump_in_hand = any(
            effective_suit(c, self._trump_suit, self._contract_type) == self._trump_suit
            for c in hand
        )
        if not trump_in_hand:
            return False  # No trump to play

        # Position check: only 3rd seat needs to worry about 4th seat
        pos = len(plays_so_far)
        if pos != 2:
            return False  # Only 3rd seat considers this logic

        # Check 4th seat's void status
        fourth_seat = (player_index + 1) % 4
        fourth_void_in_led = led_suit in self._void_suits_by_seat[fourth_seat]
        fourth_might_have_trump = (
            self._trump_suit not in self._void_suits_by_seat[fourth_seat]
        )

        # If 4th seat is void in led suit and might have trump, we should trump in
        return fourth_void_in_led and fourth_might_have_trump

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose card with partner awareness and opportunistic winning.

        Key strategy difference from Greedy:
        - When partner is winning: dump cheapest card (don't overkill) -- this is the edge
        - Otherwise: play like Greedy (take any winner available)

        This gives Glutton a consistent edge by saving cards when partner
        has the trick locked, while still being aggressive when needed.
        """
        # Fallback reset if on_hand_start wasn't called (backward compatibility)
        if len(hand) == 10 and not plays_so_far:
            self._seen_counts = {}
            self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
            self._contract_type = contract_type
            self._trump_suit = trump_suit
            self._player_index = player_index

        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # SPECIAL CASE: When leading, use smart lead selection
        if not plays_so_far:
            choice = self._choose_lead(hand, legal_indices)
            if self.debug:
                self.decision_log.append(
                    {
                        "scenario": "leading",
                        "action": "smart_lead",
                        "card": str(hand[choice]),
                    }
                )
            return choice

        # FOLLOWING: For each legal card, check if it currently wins the trick
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

        # Calculate partner_winning FIRST (needed for both 3rd-seat and partner logic)
        partner_index = (player_index + 2) % 4
        current_winner = trick_winner(
            plays_so_far,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )
        partner_winning = current_winner == partner_index

        # POSITION-AWARE AGGRESSION: In 3rd seat with low threat count, take the trick
        # Only when partner is NOT winning (otherwise defer to partner awareness)
        pos = len(plays_so_far)  # 0=lead, 1=2nd, 2=3rd, 3=4th
        if pos == 2 and winning_candidates and not partner_winning:
            # Find cheapest winner and check threat count
            best_winner_idx = min(winning_candidates, key=card_value)
            best_winner = hand[best_winner_idx]
            led_suit = effective_suit(plays_so_far[0][1], trump_suit, contract_type)
            threats = self._threat_copies_remaining(best_winner, led_suit, hand)

            # Trump gating: only aggressive trump-in if hand is small or trump-heavy
            is_trump_winner = (
                contract_type == "suit"
                and trump_suit is not None
                and effective_suit(best_winner, trump_suit, contract_type) == trump_suit
            )
            can_gate = (
                len(hand) <= 6
                or self._count_effective_suit(hand, trump_suit or "") >= 3
            )

            if threats <= 1:
                # Only take if not a trump play, or if gating conditions allow
                if not is_trump_winner or can_gate:
                    if self.debug:
                        self.decision_log.append(
                            {
                                "scenario": "3rd_seat_aggression",
                                "action": "take_likely_win",
                                "card": str(best_winner),
                                "threats": threats,
                            }
                        )
                    return best_winner_idx

        # PARTNER AWARENESS: Don't overkill partner's winning card

        if partner_winning:
            # Step 5: Check if partner is vulnerable to 4th seat
            if pos == 2:  # We're 3rd seat, 4th seat opponent plays after
                # Find sure winners among our winning candidates
                sure_winners = [
                    idx
                    for idx in winning_candidates
                    if self._is_sure_winner(hand[idx], plays_so_far, hand)
                ]
                if sure_winners:
                    # Cover partner with cheapest sure winner
                    choice = min(sure_winners, key=card_value)
                    if self.debug:
                        self.decision_log.append(
                            {
                                "scenario": "partner_vulnerable_cover",
                                "action": "play_sure_winner",
                                "card": str(hand[choice]),
                            }
                        )
                    return choice

                # Probabilistic trump-in: protect partner from 4th seat trump
                if self._should_trump_in(hand, plays_so_far, player_index):
                    # Find cheapest trump winner
                    trump_winners = [
                        idx
                        for idx in winning_candidates
                        if effective_suit(hand[idx], trump_suit, contract_type)
                        == trump_suit
                    ]
                    if trump_winners:
                        choice = min(trump_winners, key=card_value)
                        if self.debug:
                            self.decision_log.append(
                                {
                                    "scenario": "probabilistic_trump_cover",
                                    "action": "trump_to_protect_partner",
                                    "card": str(hand[choice]),
                                }
                            )
                        return choice

            # Partner safe or no sure winner — smart discard
            choice = self._choose_discard(hand, legal_indices)
            if self.debug:
                self.decision_log.append(
                    {
                        "scenario": "partner_winning",
                        "action": "smart_discard",
                        "card": str(hand[choice]),
                    }
                )
            return choice

        # If we have any card that is currently winning, play the cheapest winner
        if winning_candidates:
            choice = min(winning_candidates, key=card_value)
            if self.debug:
                self.decision_log.append(
                    {
                        "scenario": "can_win",
                        "action": "play_cheap_winner",
                        "card": str(hand[choice]),
                    }
                )
            return choice

        # Otherwise, smart discard (prefer shortest suit for voids)
        choice = self._choose_discard(hand, legal_indices)
        if self.debug:
            self.decision_log.append(
                {
                    "scenario": "cant_win",
                    "action": "smart_discard",
                    "card": str(hand[choice]),
                }
            )
        return choice


class GluttonIsolatedStrategy(Strategy):
    """
    Feature-isolated Glutton strategy for A/B testing individual improvements.

    Each feature can be enabled/disabled independently to measure its impact:
    - smart_leads: Use heuristic lead selection (Aces, draw trump, longest suit)
    - smart_discards: Prefer shortest suit to create voids
    - third_seat_aggression: Take tricks in 3rd seat when threat count ≤1
    - partner_awareness: Don't overkill partner's winning card
    - sure_winner_cover: Cover vulnerable partner with guaranteed winner
    - partner_check: Skip 3rd-seat aggression when partner winning (PR#227)
    - trump_gating: Only aggressive trump if hand ≤6 or trump ≥3 (PR#227)
    - probabilistic_trump_in: Trump to protect partner from void 4th seat (PR#228)

    With all features disabled, this behaves identically to GreedyStrategy.
    """

    def __init__(
        self,
        name: str = "glutton_isolated",
        debug: bool = False,
        # Feature flags - all default to False for isolation testing
        smart_leads: bool = False,
        smart_discards: bool = False,
        third_seat_aggression: bool = False,
        partner_awareness: bool = False,
        sure_winner_cover: bool = False,
        partner_check: bool = False,
        trump_gating: bool = False,
        probabilistic_trump_in: bool = False,
    ):
        super().__init__(name)
        self.debug = debug
        self.decision_log: List[dict] = []

        # Feature flags
        self._smart_leads = smart_leads
        self._smart_discards = smart_discards
        self._third_seat_aggression = third_seat_aggression
        self._partner_awareness = partner_awareness
        self._sure_winner_cover = sure_winner_cover
        self._partner_check = partner_check
        self._trump_gating = trump_gating
        self._probabilistic_trump_in = probabilistic_trump_in

        # Double-deck aware tracking (each card exists 0-2 times)
        self._seen_counts: Dict[Card, int] = {}
        # Void inference: which seats are void in which effective suits
        self._void_suits_by_seat: Dict[int, Set[str]] = {
            0: set(),
            1: set(),
            2: set(),
            3: set(),
        }
        # Contract context (set by on_hand_start)
        self._contract_type: str = "high"
        self._trump_suit: Optional[str] = None
        self._player_index: int = 0

    def on_hand_start(
        self,
        starting_hand: List[Card],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> None:
        """Reset per-hand state at the start of each hand."""
        self._seen_counts = {}
        self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
        self._contract_type = contract_type
        self._trump_suit = trump_suit
        self._player_index = player_index
        if self.debug:
            self.decision_log = []

    def observe_play(
        self,
        player_index: int,
        card: Card,
        trick_plays: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
    ) -> None:
        """Track played cards and infer voids from play patterns."""
        # Increment seen count (clamp at 2 for double deck)
        self._seen_counts[card] = min(2, self._seen_counts.get(card, 0) + 1)

        # Infer voids: if a player didn't follow suit, they're void in led suit
        if len(trick_plays) >= 1:
            led_suit = effective_suit(trick_plays[0][1], trump_suit, contract_type)
            played_eff = effective_suit(card, trump_suit, contract_type)
            if played_eff != led_suit:
                self._void_suits_by_seat[player_index].add(led_suit)

    def _threat_copies_remaining(
        self,
        card: Card,
        led_suit: str,
        hand: List[Card],
    ) -> int:
        """Count how many copies of cards that beat `card` are still unaccounted for."""
        beating = cards_that_beat(card, led_suit, self._trump_suit, self._contract_type)
        hand_counter = Counter(hand)
        total = 0
        for threat in beating:
            seen = self._seen_counts.get(threat, 0)
            in_hand = hand_counter.get(threat, 0)
            remaining = max(0, 2 - seen - in_hand)
            total += remaining
        return total

    def _is_sure_winner(
        self,
        candidate: Card,
        plays_so_far: List[Tuple[int, Card]],
        hand: List[Card],
    ) -> bool:
        """Returns True if candidate cannot be beaten by any remaining card."""
        if plays_so_far:
            led_suit = effective_suit(
                plays_so_far[0][1], self._trump_suit, self._contract_type
            )
        else:
            led_suit = effective_suit(candidate, self._trump_suit, self._contract_type)

        beating_cards = cards_that_beat(
            candidate, led_suit, self._trump_suit, self._contract_type
        )
        hand_counter = Counter(hand)
        for threat in beating_cards:
            seen = self._seen_counts.get(threat, 0)
            in_hand = hand_counter.get(threat, 0)
            remaining = 2 - seen - in_hand
            if remaining > 0:
                return False
        return True

    def _count_effective_suit(self, hand: List[Card], suit: str) -> int:
        """Count cards in hand that belong to the given effective suit."""
        return sum(
            1
            for c in hand
            if effective_suit(c, self._trump_suit, self._contract_type) == suit
        )

    def _get_suit_counts(self, hand: List[Card]) -> Dict[str, int]:
        """Get count of cards by effective suit in hand."""
        counts: Dict[str, int] = {}
        for c in hand:
            eff = effective_suit(c, self._trump_suit, self._contract_type)
            counts[eff] = counts.get(eff, 0) + 1
        return counts

    def _choose_lead_smart(
        self,
        hand: List[Card],
        legal_indices: List[int],
    ) -> int:
        """Choose which card to lead with human-like heuristics."""

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        suit_counts = self._get_suit_counts(hand)

        if self._contract_type == "suit" and self._trump_suit is not None:
            # 1. Look for non-trump Aces
            non_trump_aces = [
                idx
                for idx in legal_indices
                if hand[idx].rank == "A"
                and effective_suit(hand[idx], self._trump_suit, self._contract_type)
                != self._trump_suit
            ]
            if non_trump_aces:

                def ace_priority(idx: int) -> Tuple[int, int]:
                    eff = effective_suit(
                        hand[idx], self._trump_suit, self._contract_type
                    )
                    return (suit_counts.get(eff, 0), -card_value(idx))

                return min(non_trump_aces, key=ace_priority)

            # 2. Draw trump if holding >= 4 trumps and NOT holding both bowers
            trump_count = self._count_effective_suit(hand, self._trump_suit)
            trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                == self._trump_suit
            ]
            if trump_count >= 4 and trump_indices:
                from ..core.cards import is_left_bower, is_right_bower

                has_right = any(
                    is_right_bower(hand[idx], self._trump_suit) for idx in trump_indices
                )
                has_left = any(
                    is_left_bower(hand[idx], self._trump_suit) for idx in trump_indices
                )
                if not (has_right and has_left):
                    return min(trump_indices, key=card_value)

            # 3. Lead from longest non-trump suit
            non_trump_suits = [s for s in suit_counts if s != self._trump_suit]
            if non_trump_suits:
                longest_suit = max(non_trump_suits, key=lambda s: suit_counts.get(s, 0))
                longest_suit_indices = [
                    idx
                    for idx in legal_indices
                    if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                    == longest_suit
                ]
                if longest_suit_indices:
                    return max(longest_suit_indices, key=card_value)

            return max(legal_indices, key=card_value)

        else:
            # HIGH / LOW CONTRACT LEADS
            if suit_counts:
                longest_suit = max(
                    suit_counts.keys(), key=lambda s: suit_counts.get(s, 0)
                )
                longest_suit_indices = [
                    idx for idx in legal_indices if hand[idx].suit == longest_suit
                ]
                if longest_suit_indices:
                    return max(longest_suit_indices, key=card_value)
            return max(legal_indices, key=card_value)

    def _choose_discard_smart(
        self,
        hand: List[Card],
        legal_indices: List[int],
    ) -> int:
        """Choose which card to discard with smart void-creation logic."""

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        suit_counts = self._get_suit_counts(hand)

        if self._contract_type == "suit" and self._trump_suit is not None:
            non_trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                != self._trump_suit
            ]

            if non_trump_indices:

                def discard_priority(idx: int) -> Tuple[int, int]:
                    eff = effective_suit(
                        hand[idx], self._trump_suit, self._contract_type
                    )
                    return (suit_counts.get(eff, 0), card_value(idx))

                return min(non_trump_indices, key=discard_priority)

            return min(legal_indices, key=card_value)

        else:
            return min(legal_indices, key=card_value)

    def _should_trump_in(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        player_index: int,
    ) -> bool:
        """Returns True if we should consider trumping in to protect partner."""
        if self._contract_type != "suit" or self._trump_suit is None:
            return False
        if not plays_so_far:
            return False

        led_suit = effective_suit(
            plays_so_far[0][1], self._trump_suit, self._contract_type
        )

        can_follow = any(
            effective_suit(hand[idx], self._trump_suit, self._contract_type) == led_suit
            for idx in range(len(hand))
        )
        if can_follow:
            return False

        trump_in_hand = any(
            effective_suit(c, self._trump_suit, self._contract_type) == self._trump_suit
            for c in hand
        )
        if not trump_in_hand:
            return False

        pos = len(plays_so_far)
        if pos != 2:
            return False

        fourth_seat = (player_index + 1) % 4
        fourth_void_in_led = led_suit in self._void_suits_by_seat[fourth_seat]
        fourth_might_have_trump = (
            self._trump_suit not in self._void_suits_by_seat[fourth_seat]
        )

        return fourth_void_in_led and fourth_might_have_trump

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        """Choose card with configurable feature flags."""
        # Fallback reset if on_hand_start wasn't called
        if len(hand) == 10 and not plays_so_far:
            self._seen_counts = {}
            self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
            self._contract_type = contract_type
            self._trump_suit = trump_suit
            self._player_index = player_index

        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # LEADING
        if not plays_so_far:
            if self._smart_leads:
                return self._choose_lead_smart(hand, legal_indices)
            else:
                # Greedy: highest value card
                return max(legal_indices, key=card_value)

        # FOLLOWING: Find winning candidates
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

        # Calculate partner status (needed for multiple features)
        partner_index = (player_index + 2) % 4
        current_winner = trick_winner(
            plays_so_far,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )
        partner_winning = current_winner == partner_index

        pos = len(plays_so_far)  # 0=lead, 1=2nd, 2=3rd, 3=4th

        # 3RD SEAT AGGRESSION
        if self._third_seat_aggression and pos == 2 and winning_candidates:
            # Partner check: skip if partner is winning (PR#227)
            skip_for_partner = self._partner_check and partner_winning

            if not skip_for_partner:
                best_winner_idx = min(winning_candidates, key=card_value)
                best_winner = hand[best_winner_idx]
                led_suit = effective_suit(plays_so_far[0][1], trump_suit, contract_type)
                threats = self._threat_copies_remaining(best_winner, led_suit, hand)

                if threats <= 1:
                    # Trump gating check (PR#227)
                    if self._trump_gating:
                        is_trump_winner = (
                            contract_type == "suit"
                            and trump_suit is not None
                            and effective_suit(best_winner, trump_suit, contract_type)
                            == trump_suit
                        )
                        can_gate = (
                            len(hand) <= 6
                            or self._count_effective_suit(hand, trump_suit or "") >= 3
                        )
                        if is_trump_winner and not can_gate:
                            pass  # Skip this aggression
                        else:
                            return best_winner_idx
                    else:
                        return best_winner_idx

        # PARTNER AWARENESS
        if self._partner_awareness and partner_winning:
            # Sure winner cover
            if self._sure_winner_cover and pos == 2:
                sure_winners = [
                    idx
                    for idx in winning_candidates
                    if self._is_sure_winner(hand[idx], plays_so_far, hand)
                ]
                if sure_winners:
                    return min(sure_winners, key=card_value)

                # Probabilistic trump-in (PR#228)
                if self._probabilistic_trump_in and self._should_trump_in(
                    hand, plays_so_far, player_index
                ):
                    trump_winners = [
                        idx
                        for idx in winning_candidates
                        if effective_suit(hand[idx], trump_suit, contract_type)
                        == trump_suit
                    ]
                    if trump_winners:
                        return min(trump_winners, key=card_value)

            # Smart discard when partner winning
            if self._smart_discards:
                return self._choose_discard_smart(hand, legal_indices)
            else:
                return min(legal_indices, key=card_value)

        # Standard winning logic
        if winning_candidates:
            return min(winning_candidates, key=card_value)

        # Discard
        if self._smart_discards:
            return self._choose_discard_smart(hand, legal_indices)
        else:
            return min(legal_indices, key=card_value)


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

    return BasicStrategy().choose_card(
        hand, plays_so_far, contract_type, trump_suit, player_index
    )


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
    return GreedyStrategy().choose_card(
        hand, plays_so_far, contract_type, trump_suit, player_index
    )
