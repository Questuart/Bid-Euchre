"""
Greedy/glutton strategies with 1-trick lookahead.

Contains GreedyStrategy (baseline 1-trick lookahead), GluttonStrategy
(production play strategy with partner awareness), and
GluttonIsolatedStrategy (feature-flag twin for ablation).

These strategies try to win the current trick if possible,
with variations that add partner awareness and trump conservation.
"""

import hashlib
from collections import Counter
from typing import Dict, List, Optional, Set, Tuple

from ..core.cards import Card, cards_that_beat, effective_suit
from ..core.rules import get_legal_indices, trick_winner
from .base import Strategy, card_value_for_dump

# Module-level version constant — bump on every behavior change to
# GluttonStrategy or GluttonIsolatedStrategy. See
# docs/02_agent/STRATEGY_VERSIONING.md for the semver rules and PR
# changelog template.
GLUTTON_STRATEGY_VERSION = "0.11.1"
"""Changelog:

- 0.7.0 — Initial versioned baseline (PR #2529)
- 0.8.0 — Cash-A: sure-winner lead priority, draw-trump-first,
  draw trump from the top (behind ``cash_winners_on_lead``
  flag, default False). Category: MINOR.
- 0.8.1 — Cash-A: ``_draw_trump_lead`` sure-winner-first fallback
  (prevents burning LB when second RB is still out).
  Category: PATCH.
- 0.9.0 — Gate Cash-A to high/low contracts only. Suit contracts
  suppress steps 0.5, 0.75, and the step 2 modification
  regardless of ``cash_winners_on_lead`` flag value.
  Category: MINOR.
- 0.10.0 — Suit continuity: after winning a trick as leader, prefer
  continuing the same suit if cards remain (#2506).
  Always-on (no feature flag). Category: MINOR.
- 0.11.0 — Void-backed winner leads: when both opponents are void
  in a suit, any card in that suit is a guaranteed winner
  regardless of rank (#2627). Also fixes ``observe_play``
  trick-completion detection for 3-player loner/moon tricks.
  Gated behind ``cash_winners_on_lead`` for high/low.
  Category: MINOR.
- 0.11.1 — Void-backed check skips sitting-out seats (#2654).
  In loner hands the sitting-out partner never plays a card, so
  ``_void_suits_by_seat[sit_out]`` stays empty forever. The prior
  ``all(opp void)`` check spuriously returned False whenever the
  sitting-out seat fell into a defender's ``opp_seats`` tuple,
  blocking defenders from ever firing the void-backed lead against
  a loner caller. The fix tracks ``_seats_played`` from
  ``observe_play`` and filters ``opp_seats`` to active seats once
  plays have been observed. Category: PATCH.
"""


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

    # GreedyStrategy has been frozen as a reference baseline since the
    # Glutton fork. Its decision logic never changes, so version is 1.0.0.
    VERSION = "1.0.0"

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

    # Version of the play strategy's decision logic. Read polymorphically
    # via ``type(strategy).VERSION`` by ``web/routes.py`` at match-create
    # time and stamped onto the ``matches.play_strategy_version`` column
    # for per-match cohort tracking. See
    # ``docs/02_agent/STRATEGY_VERSIONING.md`` for bump rules.
    VERSION = GLUTTON_STRATEGY_VERSION

    def __init__(
        self,
        name: str = "glutton",
        debug: bool = False,
        cash_winners_on_lead: bool = False,
    ):
        super().__init__(name)
        self.debug = debug
        # Cash-A feature flag. Default ``False`` is deliberate: merging
        # Cash-A must not change production behavior. The operator will
        # flip this to ``True`` after a manual proving run. See
        # plans/sessions/2026-04-06_ai_play_strategy_investigation.md
        # §"Recommended PR Decomposition" and the Wave 2-A task packet.
        self.cash_winners_on_lead: bool = cash_winners_on_lead
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
        # Seats that have played at least one card in the current hand.
        # Used by ``_opponents_void_in_suit`` to skip sitting-out seats in
        # loner/moon hands — a seat that never plays can never demonstrate
        # a void, so it would otherwise block void-backed checks for
        # defenders whose ``opp_seats`` tuple includes the sitting-out
        # partner (#2654).
        self._seats_played: Set[int] = set()
        # Contract context (set by on_hand_start)
        self._contract_type: str = "high"
        self._trump_suit: Optional[str] = None
        self._player_index: int = 0
        # Suit continuity tracking (#2506): after winning a trick as
        # leader, prefer continuing the same suit on the next lead.
        self._last_won_lead_suit: Optional[str] = None
        self._last_won_lead_seat: Optional[int] = None

    def fingerprint(self) -> str:
        """Include feature flags in the fingerprint.

        Two ``GluttonStrategy`` instances with different ``cash_winners_on_lead``
        settings produce different fingerprints even at the same version, because
        their play behavior differs.
        """
        parts = [
            type(self).__name__,
            type(self).VERSION,
            self.name,
            f"cash_winners_on_lead={self.cash_winners_on_lead}",
        ]
        blob = "|".join(parts).encode()
        return hashlib.sha256(blob).hexdigest()[:8]

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
        self._seats_played = set()
        self._contract_type = contract_type
        self._trump_suit = trump_suit
        self._player_index = player_index
        self._last_won_lead_suit = None
        self._last_won_lead_seat = None
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

        # Track that this seat has played at least one card this hand.
        # Used to distinguish active seats from the sitting-out partner
        # in loner/moon hands (#2654).
        self._seats_played.add(player_index)

        # Infer voids: if a player didn't follow suit, they're void in led suit
        if len(trick_plays) >= 1:
            led_suit = effective_suit(trick_plays[0][1], trump_suit, contract_type)
            played_eff = effective_suit(card, trump_suit, contract_type)
            if played_eff != led_suit:
                self._void_suits_by_seat[player_index].add(led_suit)

        # Suit continuity: detect trick completion and track whether
        # the leader won their own trick (#2506).
        # Use 3 or 4 to handle both loner/moon (3-player) and normal
        # (4-player) tricks (#2627).
        if len(trick_plays) in (3, 4):
            winner = trick_winner(
                trick_plays,
                contract_type=contract_type,
                trump_suit=trump_suit,
            )
            leader_seat = trick_plays[0][0]
            if winner == leader_seat:
                self._last_won_lead_suit = effective_suit(
                    trick_plays[0][1], trump_suit, contract_type
                )
                self._last_won_lead_seat = leader_seat
            else:
                # Leader lost — clear continuity
                self._last_won_lead_suit = None
                self._last_won_lead_seat = None

    def _opponents_void_in_suit(self, suit: str, player_index: int) -> bool:
        """Return True if every *active* logical opponent is void in the suit.

        When every active opponent has demonstrated a void (via failed
        follow-suit in ``observe_play``), any card in that suit is a
        guaranteed winner regardless of rank — opponents cannot follow suit
        and therefore cannot beat the lead (#2627).

        Loner/moon handling (#2654): the sitting-out partner never plays
        a card, so ``_void_suits_by_seat[sit_out]`` stays empty for the
        whole hand. If a defender's ``opp_seats`` tuple includes the
        sitting-out seat, the plain ``all(opp void)`` check would return
        False forever, blocking the void-backed lead even when the single
        active opponent has clearly voided the suit. To fix this, we
        filter ``opp_seats`` down to seats that have actually played a
        card this hand (``_seats_played``). In normal 4-player hands all
        opponents eventually appear in ``_seats_played`` after trick 1,
        so filtering is a no-op. In loner hands it correctly reduces the
        check to the single active opponent.

        Before any plays are observed (``_seats_played`` empty, e.g. the
        caller leading trick 1), we leave ``opp_seats`` unfiltered; no
        voids are known yet anyway, so the result is ``False`` either way.
        """
        opp_seats = ((player_index + 1) % 4, (player_index + 3) % 4)
        if self._seats_played:
            active_opp_seats = tuple(
                opp for opp in opp_seats if opp in self._seats_played
            )
        else:
            active_opp_seats = opp_seats
        if not active_opp_seats:
            return False
        return all(
            suit in self._void_suits_by_seat.get(opp, set()) for opp in active_opp_seats
        )

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

    def _opponents_might_hold_trump(self, *, seat: int) -> bool:
        """Return True if at least one opponent might still hold trump.

        Reads ``_void_suits_by_seat`` (populated by ``observe_play``)
        and treats "not inferred void in trump" as "might still hold
        trump." Conservative on hand start: before any trump lead has
        forced a reveal, the helper returns True (assume opponents have
        trump until proven otherwise). Cash-A, Fix 1b.
        """
        if self._trump_suit is None:
            return False
        opp_seats = ((seat + 1) % 4, (seat + 3) % 4)
        return any(
            self._trump_suit not in self._void_suits_by_seat.get(opp, set())
            for opp in opp_seats
        )

    def _draw_trump_lead(self, trump_indices: List[int], hand: List[Card]) -> int:
        """Lead trump: highest sure-winner trump if any, else lowest trump.

        Shared by Cash-A Fix 1b (draw trump first) and Fix 2 (draw trump
        from the top).  The previous implementation returned the highest
        ``card_value_for_dump`` trump unconditionally, which burned the
        left bower whenever the second right bower was still unaccounted
        for — see ``plans/sessions/2026-04-06_cash_a_deep_audit.md``
        §Claim 1.

        New rule:
        - If any trump in hand is a ``_is_sure_winner`` at lead position,
          lead the highest-valued sure winner (cashes the master and keeps
          pressure on opponents).
        - Otherwise, lead the lowest-valued trump to feel out the shape
          without burning a top card into the still-unaccounted master.
        """

        def value(i: int) -> int:
            return card_value_for_dump(hand[i], self._contract_type, self._trump_suit)

        sure_winner_trump = [
            i for i in trump_indices if self._is_sure_winner(hand[i], [], hand)
        ]
        if sure_winner_trump:
            return max(sure_winner_trump, key=value)
        return min(trump_indices, key=value)

    def _choose_lead(
        self,
        hand: List[Card],
        legal_indices: List[int],
        player_index: Optional[int] = None,
    ) -> int:
        """Choose which card to lead with human-like heuristics."""
        if player_index is None:
            player_index = self._player_index

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        suit_counts = self._get_suit_counts(hand)

        # Cash-A contract-type gating: only fire Cash-A behavior for
        # high/low contracts where experiment data shows +0.66 Δ tricks.
        # Suit contracts show -0.13 Δ tricks — suppress there. See
        # plans/sessions/2026-04-07_cash_a_h2h_experiment_report.md §5.
        cash_a_active = self.cash_winners_on_lead and self._contract_type in (
            "high",
            "low",
        )

        if self._contract_type == "suit" and self._trump_suit is not None:
            # SUIT CONTRACT LEADS

            from ..core.cards import is_left_bower, is_right_bower

            # 0. Both bowers + 5+ trump → lead right bower to draw trump
            trump_count = self._count_effective_suit(hand, self._trump_suit)
            trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                == self._trump_suit
            ]
            has_right = any(
                is_right_bower(hand[idx], self._trump_suit) for idx in trump_indices
            )
            has_left = any(
                is_left_bower(hand[idx], self._trump_suit) for idx in trump_indices
            )
            if has_right and has_left and trump_count >= 5:
                # Lead the right bower to draw out opponent trump
                right_bower_idx = next(
                    idx
                    for idx in trump_indices
                    if is_right_bower(hand[idx], self._trump_suit)
                )
                return right_bower_idx

            # 0.25 Suit continuity (#2506): after winning a trick as
            # leader in suit X, continue leading suit X to cash
            # established winners before switching suits.
            if (
                self._last_won_lead_suit is not None
                and self._last_won_lead_seat == player_index
            ):
                cont_suit = self._last_won_lead_suit
                cont_indices = [
                    idx
                    for idx in legal_indices
                    if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                    == cont_suit
                ]
                if cont_indices:
                    return max(cont_indices, key=card_value)

            # 0.5 NEW (Cash-A, Fix 1): Cash established sure winners first.
            # Gated by ``cash_a_active`` which suppresses Cash-A in suit
            # contracts (experiment data: -0.13 Δ). Picks the sure winner
            # from the shortest effective suit to free up length for
            # future leads, breaking ties on highest card value.
            if cash_a_active:
                sure_winner_leads = [
                    idx
                    for idx in legal_indices
                    if self._is_sure_winner(hand[idx], [], hand)
                ]
                if sure_winner_leads:

                    def _sure_lead_priority(idx: int) -> Tuple[int, int]:
                        eff = effective_suit(
                            hand[idx], self._trump_suit, self._contract_type
                        )
                        return (suit_counts.get(eff, 0), -card_value(idx))

                    return min(sure_winner_leads, key=_sure_lead_priority)

            # 0.75 NEW (Cash-A, Fix 1b): Draw opponent trump before
            # cashing side winners (Defect F). Suit contracts only.
            # Gated by ``cash_a_active`` (suppressed in suit; see §5).
            if (
                cash_a_active
                and trump_indices
                and self._opponents_might_hold_trump(seat=player_index)
            ):
                return self._draw_trump_lead(trump_indices, hand)

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
            # (trump_count, trump_indices, has_right, has_left computed in Step 0)
            if trump_count >= 4 and trump_indices:
                if not (has_right and has_left):
                    # Cash-A, Fix 2: lead highest trump to clear opponents'
                    # top trump ("draw trump from the top"). Gated by
                    # ``cash_a_active`` (suppressed in suit; see §5).
                    # Previous ``min()`` left master trump in hand until
                    # tricks 9-10 (#2506).
                    if cash_a_active:
                        return self._draw_trump_lead(trump_indices, hand)
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
            # Always lead strongest card to win the current trick.
            # In Low contracts, card_value_for_dump already inverts ranks
            # (T=4, J=3, ... A=0), so max() correctly picks the best lead.
            select = max

            # Suit continuity (#2506): after winning a trick as leader
            # in suit X, continue leading suit X before switching.
            if (
                self._last_won_lead_suit is not None
                and self._last_won_lead_seat == player_index
            ):
                cont_suit = self._last_won_lead_suit
                cont_indices = [
                    idx for idx in legal_indices if hand[idx].suit == cont_suit
                ]
                if cont_indices:
                    return select(cont_indices, key=card_value)

            # Void-backed winners (#2627): if both opponents are void in
            # a suit, any card in that suit wins regardless of rank.
            # Gated behind Cash-A (high/low only). Picks the highest-
            # value card from the voided suit to maximize trick value.
            if cash_a_active:
                void_backed = [
                    idx
                    for idx in legal_indices
                    if self._opponents_void_in_suit(hand[idx].suit, player_index)
                ]
                if void_backed:
                    return select(void_backed, key=card_value)

            if suit_counts:
                longest_suit = max(
                    suit_counts.keys(), key=lambda s: suit_counts.get(s, 0)
                )
                longest_suit_indices = [
                    idx for idx in legal_indices if hand[idx].suit == longest_suit
                ]
                if longest_suit_indices:
                    # Cash-A fallback guard: the longest-suit heuristic
                    # may skip a sure winner in a short suit. Re-check
                    # sure winners before falling through when active.
                    if cash_a_active:
                        sure_winner_leads = [
                            idx
                            for idx in legal_indices
                            if self._is_sure_winner(hand[idx], [], hand)
                        ]
                        if sure_winner_leads:
                            return max(sure_winner_leads, key=card_value)
                    return select(longest_suit_indices, key=card_value)

            # Cash-A fallback guard for the empty-suit-counts path too.
            if cash_a_active:
                sure_winner_leads = [
                    idx
                    for idx in legal_indices
                    if self._is_sure_winner(hand[idx], [], hand)
                ]
                if sure_winner_leads:
                    return max(sure_winner_leads, key=card_value)

            # Fallback
            return select(legal_indices, key=card_value)

    def _choose_discard(
        self,
        hand: List[Card],
        legal_indices: List[int],
    ) -> int:
        """Choose which card to discard — always dump the lowest-value non-trump card."""

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        if self._contract_type == "suit" and self._trump_suit is not None:
            # Prefer non-trump cards
            non_trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                != self._trump_suit
            ]

            if non_trump_indices:
                # Dump the lowest-value non-trump card.  The previous
                # void-suit sort tried to create voids by preferring
                # shorter suits, but this caused Aces to be dumped from
                # non-void suits while low cards in the "kept" suit were
                # preserved — a net trick loss.  See #2300.
                return min(non_trump_indices, key=card_value)

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
        # Defense-in-depth: clear stale inference when contract changes.
        # When on_hand_start() IS called, it already syncs these fields so
        # this check is False and observe_play() data is preserved (#2175).
        # Only fires in backward-compat path where on_hand_start was skipped.
        if contract_type != self._contract_type or trump_suit != self._trump_suit:
            self._seen_counts = {}
            self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
            self._last_won_lead_suit = None
            self._last_won_lead_seat = None
        self._contract_type = contract_type
        self._trump_suit = trump_suit

        # Fallback reset if on_hand_start wasn't called (backward compat).
        # Catches consecutive same-contract hands where change-detection
        # above doesn't fire.
        if len(hand) == 10 and not plays_so_far:
            self._seen_counts = {}
            self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
            self._contract_type = contract_type
            self._trump_suit = trump_suit
            self._player_index = player_index
            self._last_won_lead_suit = None
            self._last_won_lead_seat = None

        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # SPECIAL CASE: When leading, use smart lead selection
        if not plays_so_far:
            # Pass player_index so Cash-A Fix 1b reads the correct seat
            # even in the shared-instance deployment path where
            # self._player_index can lag on_hand_start for seats 2/3.
            choice = self._choose_lead(hand, legal_indices, player_index=player_index)
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
    - lead_bower: Lead right bower when holding both bowers + 5+ trump (PR#2167).
      Defaults to smart_leads when not explicitly set, so configs with
      smart_leads=True keep bower leads. Set False explicitly to isolate.
    - suit_continuity: After winning a trick as leader, prefer continuing
      the same suit (#2506). Defaults to False for isolation testing.

    With all features disabled, this behaves identically to GreedyStrategy.
    """

    # Shares the GluttonStrategy version — the isolated twin runs the
    # same decision logic paths, just gated by feature flags. Any
    # behavior change in one class counts as a bump for both. See
    # ``docs/02_agent/STRATEGY_VERSIONING.md``.
    VERSION = GLUTTON_STRATEGY_VERSION

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
        lead_bower: Optional[bool] = None,
        cash_winners_on_lead: bool = False,
        suit_continuity: bool = False,
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
        # Default lead_bower to smart_leads when not explicitly set,
        # so existing configs with smart_leads=True keep bower leads (#2201).
        self._lead_bower = lead_bower if lead_bower is not None else smart_leads
        # Cash-A feature flag: defaults False here so the isolated twin
        # preserves baseline behavior for A/B isolation experiments. See
        # plans/sessions/2026-04-06_ai_play_strategy_investigation.md
        # §"Acceptance Criteria" item 1.
        self.cash_winners_on_lead: bool = cash_winners_on_lead
        self._suit_continuity = suit_continuity

        # Double-deck aware tracking (each card exists 0-2 times)
        self._seen_counts: Dict[Card, int] = {}
        # Void inference: which seats are void in which effective suits
        self._void_suits_by_seat: Dict[int, Set[str]] = {
            0: set(),
            1: set(),
            2: set(),
            3: set(),
        }
        # Seats that have played at least one card in the current hand.
        # Mirror of :attr:`GluttonStrategy._seats_played` (#2654).
        self._seats_played: Set[int] = set()
        # Contract context (set by on_hand_start)
        self._contract_type: str = "high"
        self._trump_suit: Optional[str] = None
        self._player_index: int = 0
        # Suit continuity tracking (#2506)
        self._last_won_lead_suit: Optional[str] = None
        self._last_won_lead_seat: Optional[int] = None

    def fingerprint(self) -> str:
        """Include all feature flags in the fingerprint."""
        parts = [
            type(self).__name__,
            type(self).VERSION,
            self.name,
            f"smart_leads={self._smart_leads}",
            f"smart_discards={self._smart_discards}",
            f"third_seat_aggression={self._third_seat_aggression}",
            f"partner_awareness={self._partner_awareness}",
            f"sure_winner_cover={self._sure_winner_cover}",
            f"partner_check={self._partner_check}",
            f"trump_gating={self._trump_gating}",
            f"probabilistic_trump_in={self._probabilistic_trump_in}",
            f"lead_bower={self._lead_bower}",
            f"cash_winners_on_lead={self.cash_winners_on_lead}",
            f"suit_continuity={self._suit_continuity}",
        ]
        blob = "|".join(parts).encode()
        return hashlib.sha256(blob).hexdigest()[:8]

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
        self._seats_played = set()
        self._contract_type = contract_type
        self._trump_suit = trump_suit
        self._player_index = player_index
        self._last_won_lead_suit = None
        self._last_won_lead_seat = None
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

        # Track seats that have played at least one card this hand (#2654).
        self._seats_played.add(player_index)

        # Infer voids: if a player didn't follow suit, they're void in led suit
        if len(trick_plays) >= 1:
            led_suit = effective_suit(trick_plays[0][1], trump_suit, contract_type)
            played_eff = effective_suit(card, trump_suit, contract_type)
            if played_eff != led_suit:
                self._void_suits_by_seat[player_index].add(led_suit)

        # Suit continuity: detect trick completion (#2506).
        # Use 3 or 4 to handle loner/moon (3-player) tricks (#2627).
        if self._suit_continuity and len(trick_plays) in (3, 4):
            winner = trick_winner(
                trick_plays,
                contract_type=contract_type,
                trump_suit=trump_suit,
            )
            leader_seat = trick_plays[0][0]
            if winner == leader_seat:
                self._last_won_lead_suit = effective_suit(
                    trick_plays[0][1], trump_suit, contract_type
                )
                self._last_won_lead_seat = leader_seat
            else:
                self._last_won_lead_suit = None
                self._last_won_lead_seat = None

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

    def _opponents_void_in_suit(self, suit: str, player_index: int) -> bool:
        """Return True if every *active* logical opponent is void in the suit.

        Mirror of :meth:`GluttonStrategy._opponents_void_in_suit` (#2627,
        #2654 sitting-out filter).
        """
        opp_seats = ((player_index + 1) % 4, (player_index + 3) % 4)
        if self._seats_played:
            active_opp_seats = tuple(
                opp for opp in opp_seats if opp in self._seats_played
            )
        else:
            active_opp_seats = opp_seats
        if not active_opp_seats:
            return False
        return all(
            suit in self._void_suits_by_seat.get(opp, set()) for opp in active_opp_seats
        )

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

    def _opponents_might_hold_trump(self, *, seat: int) -> bool:
        """Return True if at least one opponent might still hold trump.

        Mirror of :meth:`GluttonStrategy._opponents_might_hold_trump`.
        Cash-A, Fix 1b.
        """
        if self._trump_suit is None:
            return False
        opp_seats = ((seat + 1) % 4, (seat + 3) % 4)
        return any(
            self._trump_suit not in self._void_suits_by_seat.get(opp, set())
            for opp in opp_seats
        )

    def _draw_trump_lead(self, trump_indices: List[int], hand: List[Card]) -> int:
        """Lead trump: highest sure-winner trump if any, else lowest trump.

        Mirror of :meth:`GluttonStrategy._draw_trump_lead`. Shared by
        Cash-A Fix 1b and Fix 2.  See the GluttonStrategy docstring for
        the full rationale and §Claim 1 reference.
        """

        def value(i: int) -> int:
            return card_value_for_dump(hand[i], self._contract_type, self._trump_suit)

        sure_winner_trump = [
            i for i in trump_indices if self._is_sure_winner(hand[i], [], hand)
        ]
        if sure_winner_trump:
            return max(sure_winner_trump, key=value)
        return min(trump_indices, key=value)

    def _choose_lead_smart(
        self,
        hand: List[Card],
        legal_indices: List[int],
        player_index: Optional[int] = None,
    ) -> int:
        """Choose which card to lead with human-like heuristics."""
        if player_index is None:
            player_index = self._player_index

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        suit_counts = self._get_suit_counts(hand)

        # Cash-A contract-type gating (mirrors GluttonStrategy._choose_lead).
        cash_a_active = self.cash_winners_on_lead and self._contract_type in (
            "high",
            "low",
        )

        if self._contract_type == "suit" and self._trump_suit is not None:
            from ..core.cards import is_left_bower, is_right_bower

            # Compute trump shape (used by steps 0 and 2)
            trump_count = self._count_effective_suit(hand, self._trump_suit)
            trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                == self._trump_suit
            ]
            has_right = any(
                is_right_bower(hand[idx], self._trump_suit) for idx in trump_indices
            )
            has_left = any(
                is_left_bower(hand[idx], self._trump_suit) for idx in trump_indices
            )

            # 0. Both bowers + 5+ trump → lead right bower to draw trump
            if self._lead_bower and has_right and has_left and trump_count >= 5:
                right_bower_idx = next(
                    idx
                    for idx in trump_indices
                    if is_right_bower(hand[idx], self._trump_suit)
                )
                return right_bower_idx

            # 0.25 Suit continuity (#2506)
            if (
                self._suit_continuity
                and self._last_won_lead_suit is not None
                and self._last_won_lead_seat == player_index
            ):
                cont_suit = self._last_won_lead_suit
                cont_indices = [
                    idx
                    for idx in legal_indices
                    if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                    == cont_suit
                ]
                if cont_indices:
                    return max(cont_indices, key=card_value)

            # 0.5 NEW (Cash-A, Fix 1): Cash established sure winners first.
            # Gated by ``cash_a_active`` (suppressed in suit; see §5).
            if cash_a_active:
                sure_winner_leads = [
                    idx
                    for idx in legal_indices
                    if self._is_sure_winner(hand[idx], [], hand)
                ]
                if sure_winner_leads:

                    def _sure_lead_priority(idx: int) -> Tuple[int, int]:
                        eff = effective_suit(
                            hand[idx], self._trump_suit, self._contract_type
                        )
                        return (suit_counts.get(eff, 0), -card_value(idx))

                    return min(sure_winner_leads, key=_sure_lead_priority)

            # 0.75 NEW (Cash-A, Fix 1b): Draw opponent trump before
            # cashing side winners. Suit contracts only.
            # Gated by ``cash_a_active`` (suppressed in suit; see §5).
            if (
                cash_a_active
                and trump_indices
                and self._opponents_might_hold_trump(seat=player_index)
            ):
                return self._draw_trump_lead(trump_indices, hand)

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
            if trump_count >= 4 and trump_indices:
                if not (has_right and has_left):
                    # Cash-A, Fix 2: lead highest trump when flagged on.
                    # Gated by ``cash_a_active`` (suppressed in suit).
                    if cash_a_active:
                        return self._draw_trump_lead(trump_indices, hand)
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

            # Suit continuity (#2506)
            if (
                self._suit_continuity
                and self._last_won_lead_suit is not None
                and self._last_won_lead_seat == player_index
            ):
                cont_suit = self._last_won_lead_suit
                cont_indices = [
                    idx for idx in legal_indices if hand[idx].suit == cont_suit
                ]
                if cont_indices:
                    return max(cont_indices, key=card_value)

            # Void-backed winners (#2627): mirror of GluttonStrategy.
            if cash_a_active:
                void_backed = [
                    idx
                    for idx in legal_indices
                    if self._opponents_void_in_suit(hand[idx].suit, player_index)
                ]
                if void_backed:
                    return max(void_backed, key=card_value)

            if suit_counts:
                longest_suit = max(
                    suit_counts.keys(), key=lambda s: suit_counts.get(s, 0)
                )
                longest_suit_indices = [
                    idx for idx in legal_indices if hand[idx].suit == longest_suit
                ]
                if longest_suit_indices:
                    # Cash-A fallback guard in high/low.
                    if cash_a_active:
                        sure_winner_leads = [
                            idx
                            for idx in legal_indices
                            if self._is_sure_winner(hand[idx], [], hand)
                        ]
                        if sure_winner_leads:
                            return max(sure_winner_leads, key=card_value)
                    return max(longest_suit_indices, key=card_value)

            # Cash-A fallback guard for the empty-suit-counts path.
            if cash_a_active:
                sure_winner_leads = [
                    idx
                    for idx in legal_indices
                    if self._is_sure_winner(hand[idx], [], hand)
                ]
                if sure_winner_leads:
                    return max(sure_winner_leads, key=card_value)

            return max(legal_indices, key=card_value)

    def _choose_discard_smart(
        self,
        hand: List[Card],
        legal_indices: List[int],
    ) -> int:
        """Choose which card to discard — always dump the lowest-value non-trump card."""

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], self._contract_type, self._trump_suit)

        if self._contract_type == "suit" and self._trump_suit is not None:
            non_trump_indices = [
                idx
                for idx in legal_indices
                if effective_suit(hand[idx], self._trump_suit, self._contract_type)
                != self._trump_suit
            ]

            if non_trump_indices:
                # See GluttonStrategy._choose_discard comment re #2300.
                return min(non_trump_indices, key=card_value)

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
        # Defense-in-depth: clear stale inference when contract changes.
        # When on_hand_start() IS called, it already syncs these fields so
        # this check is False and observe_play() data is preserved (#2175).
        if contract_type != self._contract_type or trump_suit != self._trump_suit:
            self._seen_counts = {}
            self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
            self._last_won_lead_suit = None
            self._last_won_lead_seat = None
        self._contract_type = contract_type
        self._trump_suit = trump_suit

        # Fallback reset if on_hand_start wasn't called (backward compat).
        # Catches consecutive same-contract hands where change-detection
        # above doesn't fire.
        if len(hand) == 10 and not plays_so_far:
            self._seen_counts = {}
            self._void_suits_by_seat = {0: set(), 1: set(), 2: set(), 3: set()}
            self._contract_type = contract_type
            self._trump_suit = trump_suit
            self._player_index = player_index
            self._last_won_lead_suit = None
            self._last_won_lead_seat = None

        legal_indices = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)

        def card_value(idx: int) -> int:
            return card_value_for_dump(hand[idx], contract_type, trump_suit)

        # LEADING
        if not plays_so_far:
            if self._smart_leads:
                return self._choose_lead_smart(
                    hand, legal_indices, player_index=player_index
                )
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
