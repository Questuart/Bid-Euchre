"""Match engine for hosted browser-game play.

Drives a step-based match that pauses at human turns and auto-advances AI
turns.  Delegates **all** rule evaluation to existing ``core/``, ``sim/``,
``strategy/``, and ``scoring`` modules — no logic duplication.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

from bid_euchre.core.cards import Card, effective_suit, is_left_bower, is_right_bower
from bid_euchre.core.rules import get_legal_indices, trick_winner
from bid_euchre.scoring import compute_points
from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.exchange import (
    perform_exchange,
    select_mooner_discards,
    select_partner_gifts,
)
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import (
    BidAction,
    BiddingObservation,
    BiddingPolicy,
    enumerate_legal_actions,
)

from .state import HandState, MatchState, TrickResult, TrickState

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HUMAN_SEAT = 0
MATCH_TARGET = 52

# Seats in bidding order relative to dealer: (dealer+1), (dealer+2), (dealer+3), dealer
_NUM_PLAYERS = 4
_TRICKS_PER_HAND = 10


# Display suit order: Spades, Hearts, Diamonds, Clubs
_SUIT_DISPLAY_ORDER: dict[str, int] = {"S": 0, "H": 1, "D": 2, "C": 3}

# Within-suit rank order: J highest, then A-K-Q-T (auction / trump suit)
_RANK_DISPLAY_ORDER: dict[str, int] = {"J": 0, "A": 1, "K": 2, "Q": 3, "T": 4}

# High-contract / non-trump rank order: A highest, then K-Q-J-T
_RANK_DISPLAY_ORDER_HIGH: dict[str, int] = {"A": 0, "K": 1, "Q": 2, "J": 3, "T": 4}

# Low-contract rank order: T highest, then J-Q-K-A
_RANK_DISPLAY_ORDER_LOW: dict[str, int] = {"T": 0, "J": 1, "Q": 2, "K": 3, "A": 4}


def sort_hand_for_display(
    hand: list[Card],
    contract_type: str | None = None,
    trump: str | None = None,
) -> None:
    """Sort a hand **in-place** for human display.

    Grouping:
    - Cards are grouped by effective suit (bowers move to trump group in suit
      contracts).
    - When trump is active, the trump suit appears first; remaining suits
      follow standard order (S > H > D > C).

    Within-suit ordering:
    - Suit contracts (trump suit): right bower > left bower > A > K > Q > (non-bower J) > T
    - Suit contracts (non-trump suits): A > K > Q > J > T
    - High contracts (no trump, A high): A > K > Q > J > T
    - Auction (no contract set): J > A > K > Q > T
    - Low contracts: T > J > Q > K > A
    """

    def _sort_key(card: Card) -> tuple[int, int]:
        # Effective suit for grouping
        if contract_type == "suit" and trump:
            eff = effective_suit(card, trump, contract_type)
        else:
            eff = card.suit

        # Suit ordering — trump first when active
        if contract_type == "suit" and trump and eff == trump:
            suit_key = -1
        else:
            suit_key = _SUIT_DISPLAY_ORDER.get(eff, 99)

        # Rank ordering within suit
        if contract_type == "suit" and trump and eff == trump:
            if is_right_bower(card, trump):
                rank_key = -2
            elif is_left_bower(card, trump):
                rank_key = -1
            else:
                rank_key = _RANK_DISPLAY_ORDER.get(card.rank, 99)
        elif contract_type == "low":
            rank_key = _RANK_DISPLAY_ORDER_LOW.get(card.rank, 99)
        elif contract_type == "high" or (
            contract_type == "suit" and trump and eff != trump
        ):
            # A-high: HIGH contracts have no bowers; non-trump suits in
            # suit contracts also rank A above J.
            rank_key = _RANK_DISPLAY_ORDER_HIGH.get(card.rank, 99)
        else:
            # Auction (contract_type is None) — J-high default
            rank_key = _RANK_DISPLAY_ORDER.get(card.rank, 99)

        return (suit_key, rank_key)

    hand.sort(key=_sort_key)


def _bid_order(dealer_seat: int) -> list[int]:
    """Return the four seats in auction order starting left of dealer."""
    return [(dealer_seat + i + 1) % _NUM_PLAYERS for i in range(_NUM_PLAYERS)]


def _current_bid_rank(hand: HandState) -> int:
    """Compute the bid_rank of the current winning bid.

    Returns -1 if no bid has been placed yet.
    """
    if hand.bidder_seat is None:
        return -1
    type_rank = BidAction._BID_TYPE_RANK.get(hand.bid_type, 0)
    if hand.bid_type == "regular":
        return hand.current_high_bid
    # moon = 11, loner = 12
    return 10 + type_rank


def _next_active_seat(seat: int, sitting_out_seat: int | None) -> int:
    """Return the next clockwise seat, skipping the sitting-out seat."""
    next_seat = (seat + 1) % _NUM_PLAYERS
    if sitting_out_seat is not None and next_seat == sitting_out_seat:
        next_seat = (next_seat + 1) % _NUM_PLAYERS
    return next_seat


def _players_per_trick(sitting_out_seat: int | None) -> int:
    """Return how many players participate in each trick."""
    return 3 if sitting_out_seat is not None else 4


@dataclass
class AIActionEvent:
    """Exact data captured from a single AI decision during auto-advance.

    Populated by ``_advance_ai()`` so that callers (route handlers) can log
    deterministic-replay-grade decision rows without approximation.
    """

    turn_number: int
    seat: int
    phase: str  # "bid" or "play"
    legal_actions: Any  # list[dict] for bids, list[int] for plays
    chosen_action: Any  # dict for bids, int for plays
    game_state: dict[str, Any]


def _build_game_snapshot(hand: Any, seat: int) -> dict[str, Any]:
    """Build a game-state snapshot dict for decision logging."""
    snapshot: dict[str, Any] = {
        "phase": hand.phase,
        "seat": seat,
        "turn_number": hand.turn_number,
        "dealer_seat": hand.dealer_seat,
        "current_high_bid": hand.current_high_bid,
        "auction": list(hand.auction),
        "contract_type": hand.contract_type,
        "trump": hand.trump,
        "bid_type": hand.bid_type,
        "tricks_team0": hand.tricks_team0,
        "tricks_team1": hand.tricks_team1,
        "hand_size": len(hand.hands[seat]),
    }
    if hand.current_trick is not None:
        snapshot["current_trick"] = {
            "leader": hand.current_trick.leader,
            "plays": [
                [s, [card.suit, card.rank]] for s, card in hand.current_trick.plays
            ],
        }
    return snapshot


# ---------------------------------------------------------------------------
# MatchEngine
# ---------------------------------------------------------------------------


class MatchEngine:
    """Step-based match engine for a human vs three AI opponents.

    The human is always at ``HUMAN_SEAT`` (seat 0, team 0 with seat 2).
    AI seats are 1, 2, 3.  The engine pauses whenever it is the human's
    turn to act (bid or play) and auto-advances through all AI turns.

    Moon/loner support:
    - Moon bids trigger a 2-card exchange with the partner, then the partner
      sits out during trick play (3-player tricks).
    - Loner bids cause the declarer's partner to sit out during trick play
      (3-player tricks), with no exchange.
    - Both moon and loner use 3-player trick play; the difference is the
      exchange step.
    - Overcall hierarchy: regular 1-10 < moon < loner.
    """

    def __init__(
        self,
        bidding_policy: BiddingPolicy,
        play_strategy: Strategy,
    ) -> None:
        self.bidding_policy = bidding_policy
        self.play_strategy = play_strategy
        self.last_ai_events: list[AIActionEvent] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_match(self, seed: int, ai_model: str) -> MatchState:
        """Create a new match, deal the first hand, and advance AI."""
        self.last_ai_events = []
        state = MatchState(seed=seed, ai_model=ai_model)
        state.dealer_seat = random.Random(seed).randrange(_NUM_PLAYERS)
        state = self._deal_new_hand(state)
        state = self._advance_ai(state)
        return state

    def submit_human_bid(self, state: MatchState, bid: BidAction) -> MatchState:
        """Process the human's bid, then auto-advance AI."""
        self.last_ai_events = []
        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "auction"
        assert hand.current_seat == HUMAN_SEAT

        state = self._process_bid(state, HUMAN_SEAT, bid)
        state = self._advance_ai(state)
        return state

    def submit_human_card(self, state: MatchState, card_index: int) -> MatchState:
        """Process the human's card play, then auto-advance AI.

        If the human's card completes a trick, pauses **before** AI
        auto-advance so the UI can show the trick result.  Otherwise
        auto-advances AI until the next trick completion or the human's
        next turn.
        """
        self.last_ai_events = []
        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "trick_play"
        assert hand.current_seat == HUMAN_SEAT

        pre_tricks = len(hand.completed_tricks)
        state = self._process_card_play(state, HUMAN_SEAT, card_index)

        hand_after = state.current_hand
        if hand_after is not None and len(hand_after.completed_tricks) > pre_tricks:
            # Human's card completed a trick — pause to show the result
            # before any further AI play.
            if hand_after.phase == "trick_play":
                hand_after.paused_after_trick = True
            return state

        # Trick not yet complete — auto-advance AI to finish the trick
        # (and pause once that trick completes).
        state = self._advance_ai(state)
        return state

    def submit_exchange_selection(
        self, state: MatchState, card_indices: list[int]
    ) -> MatchState:
        """Process the human's moon-exchange card selection.

        The human selects exactly 2 cards from their hand to give.  When the
        human is the mooner they give their 2 worst cards; when the human is
        the partner they give their 2 best cards.  The AI counterpart's
        selection is computed automatically.

        After the exchange the hand transitions through the exchange-reveal
        interstitial and then into trick play.
        """
        self.last_ai_events = []
        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "moon_exchange"
        assert hand.exchange_phase == "selecting"

        if len(card_indices) != 2:
            raise ValueError("Must select exactly 2 cards for moon exchange")

        human_hand = hand.hands[HUMAN_SEAT]
        for idx in card_indices:
            if idx < 0 or idx >= len(human_hand):
                raise ValueError(f"Card index {idx} out of range")

        if card_indices[0] == card_indices[1]:
            raise ValueError("Must select 2 different cards")

        mooner_seat = hand.bidder_seat
        assert mooner_seat is not None
        partner_seat = (mooner_seat + 2) % _NUM_PLAYERS
        contract_type = hand.contract_type or "suit"
        trump = hand.trump

        # Extract human's chosen cards (pop in descending index order)
        sorted_indices = sorted(card_indices, reverse=True)
        human_cards = []
        for idx in sorted_indices:
            human_cards.append(human_hand.pop(idx))

        if HUMAN_SEAT == mooner_seat:
            # Human is mooner — gave 2 cards; AI partner gives 2 best
            ai_hand = hand.hands[partner_seat]
            ai_indices = select_partner_gifts(ai_hand, contract_type, trump)
            ai_cards = []
            for idx in ai_indices:
                ai_cards.append(ai_hand.pop(idx))

            # Swap: mooner gets partner's best, partner gets mooner's discards
            human_hand.extend(ai_cards)
            ai_hand.extend(human_cards)

            cards_given = human_cards  # mooner gave these
            cards_received = ai_cards  # mooner received these
        else:
            # Human is partner — gave 2 cards; AI mooner gives 2 worst
            ai_hand = hand.hands[mooner_seat]
            ai_indices = select_mooner_discards(ai_hand, contract_type, trump)
            ai_cards = []
            for idx in ai_indices:
                ai_cards.append(ai_hand.pop(idx))

            # Swap: mooner gets partner's cards, partner gets mooner's discards
            ai_hand.extend(human_cards)
            human_hand.extend(ai_cards)

            cards_given = ai_cards  # mooner gave these (to partner/human)
            cards_received = human_cards  # mooner received these (from partner/human)

        # Validate post-conditions
        assert len(hand.hands[mooner_seat]) == 10
        assert len(hand.hands[partner_seat]) == 10

        # Store exchange results (from mooner's perspective)
        hand.exchange_given = [[c.suit, c.rank] for c in cards_given]
        hand.exchange_received = [[c.suit, c.rank] for c in cards_received]
        hand.exchange_phase = None

        # Moon: partner sits out during trick play (3-player tricks),
        # just like loner, but exchange happens first.
        hand.sitting_out_seat = (hand.bidder_seat + 2) % _NUM_PLAYERS

        # Transition to trick play with exchange-reveal interstitial
        hand.phase = "trick_play"
        leader = hand.bidder_seat
        hand.current_trick = TrickState(leader=leader)
        hand.current_seat = leader

        # Re-sort human hand with bower awareness
        sort_hand_for_display(hand.hands[HUMAN_SEAT], hand.contract_type, hand.trump)

        # Auto-advance AI just like submit_human_bid/submit_human_card.
        # Without this, the game is stuck when the leader (bidder) is an AI
        # seat because no mechanism triggers AI card play after exchange.
        # However, when the human is sitting out (partner bid moon), defer
        # AI advancement until after the exchange-reveal interstitial —
        # otherwise _advance_ai plays all 10 tricks and the interstitial
        # never shows.  The route layer calls advance_after_exchange_reveal()
        # to trigger the deferred advancement.
        if hand.sitting_out_seat != HUMAN_SEAT:
            state = self._advance_ai(state)

        return state

    def advance_after_exchange_reveal(self, state: MatchState) -> MatchState:
        """Trigger AI advancement after the exchange-reveal interstitial.

        Called by the route layer when ``exchange_revealed`` is set to True.
        For moon hands where the human is sitting out (partner of the mooner),
        AI advancement was deferred from ``submit_exchange_selection`` to allow
        the exchange interstitial to display first.  This method completes the
        deferred advancement.
        """
        self.last_ai_events = []
        state = self._advance_ai(state)
        return state

    def get_legal_bids(self, state: MatchState) -> list[BidAction]:
        """Return legal bids for the current bidder.

        Delegates to ``enumerate_legal_actions`` with moon/loner enabled.
        Overcall hierarchy: regular 1-10 < moon < loner.
        Dealer take-away (match) is supported for moon and loner.
        """
        hand = state.current_hand
        assert hand is not None and hand.phase == "auction"

        seat = hand.current_seat
        obs = BiddingObservation(
            hand=hand.hands[seat],
            seat=seat,
            dealer_seat=hand.dealer_seat,
            current_high_bid=hand.current_high_bid,
            auction_transcript=tuple(hand.auction),
        )
        is_dealer = seat == hand.dealer_seat
        return enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type=hand.bid_type,
            is_dealer=is_dealer,
        )

    def get_legal_plays(self, state: MatchState) -> list[int]:
        """Return legal card indices for the current seat.

        Delegates to ``get_legal_indices()`` from ``core.rules``.
        """
        hand = state.current_hand
        assert hand is not None and hand.phase == "trick_play"
        assert hand.current_trick is not None
        assert hand.contract_type is not None

        seat = hand.current_seat
        return get_legal_indices(
            hand.hands[seat],
            hand.current_trick.plays,
            hand.contract_type,
            hand.trump,
        )

    def get_visible_state(self, state: MatchState) -> dict[str, Any]:
        """Return state visible to the human player.

        Includes: own hand, current trick, completed tricks, scores, auction
        transcript, phase, bid_type, sitting_out_seat, exchange cards.
        Excludes: other players' hands.
        """
        hand = state.current_hand
        result: dict[str, Any] = {
            "status": state.status,
            "winner": state.winner,
            "score_human": state.score_human,
            "score_ai": state.score_ai,
            "hands_played": state.hands_played,
        }

        if hand is None:
            result["phase"] = None
            return result

        result["phase"] = hand.phase
        result["dealer_seat"] = hand.dealer_seat
        result["current_seat"] = hand.current_seat
        result["turn_number"] = hand.turn_number
        result["human_hand"] = [[c.suit, c.rank] for c in hand.hands[HUMAN_SEAT]]
        result["auction"] = list(hand.auction)
        result["contract_type"] = hand.contract_type
        result["trump"] = hand.trump
        result["bid_type"] = hand.bid_type
        result["sitting_out_seat"] = hand.sitting_out_seat
        result["exchange_given"] = hand.exchange_given
        result["exchange_received"] = hand.exchange_received
        result["exchange_phase"] = hand.exchange_phase
        result["current_trick"] = (
            None
            if hand.current_trick is None
            else {
                "leader": hand.current_trick.leader,
                "plays": [
                    [seat, [card.suit, card.rank]]
                    for seat, card in hand.current_trick.plays
                ],
            }
        )
        result["completed_tricks"] = [
            {
                "leader": tr.leader,
                "plays": [[s, [c.suit, c.rank]] for s, c in tr.plays],
                "winner": tr.winner,
                "winning_card": next(
                    ([c.suit, c.rank] for s, c in tr.plays if s == tr.winner),
                    None,
                ),
            }
            for tr in hand.completed_tricks
        ]
        result["tricks_team0"] = hand.tricks_team0
        result["tricks_team1"] = hand.tricks_team1
        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def serialize(state: MatchState) -> dict[str, Any]:
        """Serialize *state* to a JSON-compatible dict."""
        return state.to_dict()

    @staticmethod
    def deserialize(data: dict[str, Any]) -> MatchState:
        """Restore a ``MatchState`` from a serialized dict."""
        return MatchState.from_dict(data)

    # ------------------------------------------------------------------
    # Internal — AI auto-advance
    # ------------------------------------------------------------------

    def resume_ai(self, state: MatchState) -> MatchState:
        """Continue AI advancement after a trick-result pause.

        Clears the ``paused_after_trick`` flag and re-enters the auto-play
        loop.  Called by route handlers when the user clicks **Next** to
        dismiss a trick-result interstitial.
        """
        hand = state.current_hand
        if hand is not None:
            hand.paused_after_trick = False
        self.last_ai_events = []
        return self._advance_ai(state)

    def _advance_ai(self, state: MatchState) -> MatchState:
        """Auto-play AI turns, pausing at every natural stopping point.

        Stopping points (returns immediately when reached):
        * The human's turn to bid or play (unless sitting out).
        * A trick just completed — ``paused_after_trick`` is set so the UI
          can show the result before continuing.
        * The hand ended (phase ``"complete"`` or ``"redeal"``).
        * The match ended (``status == "complete"``).

        Populates ``self.last_ai_events`` with exact decision data for every
        AI action taken during this advance cycle.
        """
        while True:
            # Match finished — nothing to advance
            if state.status == "complete":
                return state

            hand = state.current_hand
            if hand is None:
                return state

            # If human's turn AND human is not sitting out, pause for input
            if hand.current_seat == HUMAN_SEAT:
                if hand.sitting_out_seat != HUMAN_SEAT:
                    return state
                # Human is sitting out (partner bid moon/loner) — skip is handled
                # by _next_active_seat in trick play.  If we reach here during
                # auction, it's the human's normal turn.
                if hand.phase == "auction":
                    return state

            # Hand is complete or redeal — handled by callers already
            if hand.phase in ("complete", "redeal"):
                return state

            seat = hand.current_seat

            if hand.phase == "auction":
                obs = BiddingObservation(
                    hand=hand.hands[seat],
                    seat=seat,
                    dealer_seat=hand.dealer_seat,
                    current_high_bid=hand.current_high_bid,
                    auction_transcript=tuple(hand.auction),
                )
                bid = self.bidding_policy.choose_bid(obs)

                # Capture exact event data before the bid modifies state
                legal_bids = self.get_legal_bids(state)
                self.last_ai_events.append(
                    AIActionEvent(
                        turn_number=hand.turn_number,
                        seat=seat,
                        phase="bid",
                        legal_actions=[
                            {
                                "n": b.n,
                                "contract": b.contract,
                                "bid_type": b.bid_type,
                            }
                            for b in legal_bids
                        ],
                        chosen_action={
                            "n": bid.n,
                            "contract": bid.contract,
                            "bid_type": bid.bid_type,
                        },
                        game_state=_build_game_snapshot(hand, seat),
                    )
                )
                logger.debug(
                    "AI bid: seat=%d n=%d contract=%s bid_type=%s (deal=%d turn=%d)",
                    seat,
                    bid.n,
                    bid.contract,
                    bid.bid_type,
                    state.deal_id,
                    hand.turn_number,
                )

                state = self._process_bid(state, seat, bid)

            elif hand.phase == "trick_play":
                assert hand.current_trick is not None
                assert hand.contract_type is not None

                pre_tricks = len(hand.completed_tricks)

                card_idx = self.play_strategy.choose_card(
                    hand.hands[seat],
                    hand.current_trick.plays,
                    hand.contract_type,
                    hand.trump,
                    seat,
                )

                # Capture exact event data before the play modifies state
                legal_indices = get_legal_indices(
                    hand.hands[seat],
                    hand.current_trick.plays,
                    hand.contract_type,
                    hand.trump,
                )
                self.last_ai_events.append(
                    AIActionEvent(
                        turn_number=hand.turn_number,
                        seat=seat,
                        phase="play",
                        legal_actions=legal_indices,
                        chosen_action=card_idx,
                        game_state=_build_game_snapshot(hand, seat),
                    )
                )
                card = hand.hands[seat][card_idx]
                logger.debug(
                    "AI play: seat=%d card=%s%s (deal=%d turn=%d, %d legal)",
                    seat,
                    card.rank,
                    card.suit,
                    state.deal_id,
                    hand.turn_number,
                    len(legal_indices),
                )

                state = self._process_card_play(state, seat, card_idx)

                # After an AI card play, check if a trick just completed.
                # If so, pause to let the UI show the result.
                hand_after = state.current_hand
                if (
                    hand_after is not None
                    and len(hand_after.completed_tricks) > pre_tricks
                ):
                    if hand_after.phase == "trick_play":
                        hand_after.paused_after_trick = True
                    return state
            else:
                # Unexpected phase — bail to avoid infinite loop
                return state  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal — deal
    # ------------------------------------------------------------------

    def _deal_new_hand(self, state: MatchState) -> MatchState:
        """Generate a new deal and begin the auction phase."""
        hands = generate_deal(state.seed, state.deal_id)
        first_bidder = _bid_order(state.dealer_seat)[0]

        hand = HandState(
            phase="auction",
            hands=hands,
            dealer_seat=state.dealer_seat,
            deal_id=state.deal_id,
            current_seat=first_bidder,
            turn_number=0,
        )
        state.current_hand = hand

        # Sort human hand for display (no trump known yet during auction)
        sort_hand_for_display(hand.hands[HUMAN_SEAT])

        return state

    # ------------------------------------------------------------------
    # Internal — bidding
    # ------------------------------------------------------------------

    def _process_bid(self, state: MatchState, seat: int, bid: BidAction) -> MatchState:
        """Record a single bid and advance the auction."""
        hand = state.current_hand
        assert hand is not None and hand.phase == "auction"

        # Record the auction entry
        entry: dict[str, Any] = {"seat": seat, "n": bid.n}
        if bid.is_pass():
            entry["action"] = "pass"
        else:
            entry["action"] = "bid"
            entry["contract"] = bid.contract
            entry["bid_type"] = bid.bid_type
            # Track the high bidder using overcall hierarchy:
            # regular 1-10 < moon < loner
            if bid.bid_rank() > _current_bid_rank(hand):
                hand.current_high_bid = bid.n
                hand.bidder_seat = seat
                hand.winning_bid = bid.n
                hand.bid_type = bid.bid_type
                ct, ts = bid.to_contract_tuple()
                hand.contract_type = ct
                hand.trump = ts

        hand.auction.append(entry)
        hand.turn_number += 1

        # Check if auction is complete (4 bids)
        if len(hand.auction) >= _NUM_PLAYERS:
            state = self._process_auction_end(state)
        else:
            # Advance to next bidder
            order = _bid_order(hand.dealer_seat)
            next_idx = len(hand.auction)
            hand.current_seat = order[next_idx]

        return state

    def deal_after_redeal(self, state: MatchState) -> MatchState:
        """Advance dealer, deal a new hand, and auto-advance AI after a redeal.

        The route layer calls this after persisting the terminal ``"redeal"``
        hand row.  Separating the redeal marker from the deal gives callers a
        chance to write the old hand state before it is replaced.
        """
        hand = state.current_hand
        assert hand is not None and hand.phase == "redeal"
        state.dealer_seat = (state.dealer_seat + 1) % _NUM_PLAYERS
        state.deal_id += 1
        state = self._deal_new_hand(state)
        state = self._advance_ai(state)
        return state

    def _process_auction_end(self, state: MatchState) -> MatchState:
        """Finalize the auction: set contract, run exchange, or trigger redeal."""
        hand = state.current_hand
        assert hand is not None

        if hand.bidder_seat is None:
            # All passed — mark redeal and return.  The caller (route layer)
            # persists this terminal state, then calls deal_after_redeal()
            # to advance the dealer and start the next hand.
            hand.phase = "redeal"
            return state

        # Moon exchange: mooner gives 2 worst cards, receives partner's 2 best
        if hand.bid_type == "moon":
            mooner_seat = hand.bidder_seat
            partner_seat = (mooner_seat + 2) % _NUM_PLAYERS
            human_involved = HUMAN_SEAT in (mooner_seat, partner_seat)

            if human_involved:
                # Interactive exchange: pause for human to select 2 cards
                hand.phase = "moon_exchange"
                hand.exchange_phase = "selecting"
                # Re-sort human hand so they can see proper card values
                sort_hand_for_display(
                    hand.hands[HUMAN_SEAT], hand.contract_type, hand.trump
                )
                return state

            # AI-only exchange: auto-resolve
            (
                hand.hands[mooner_seat],
                hand.hands[partner_seat],
                cards_given,
                cards_received,
            ) = perform_exchange(
                mooner_hand=hand.hands[mooner_seat],
                partner_hand=hand.hands[partner_seat],
                contract_type=hand.contract_type or "suit",
                trump_suit=hand.trump,
            )
            hand.exchange_given = [[c.suit, c.rank] for c in cards_given]
            hand.exchange_received = [[c.suit, c.rank] for c in cards_received]

        # Moon and loner: partner sits out during trick play (3-player tricks).
        # For moon, this happens AFTER the exchange above.
        if hand.bid_type in ("moon", "loner"):
            hand.sitting_out_seat = (hand.bidder_seat + 2) % _NUM_PLAYERS

        # Contract set — transition to trick play
        hand.phase = "trick_play"
        # Declarer leads first trick (RULES.md §5.1)
        leader = hand.bidder_seat
        hand.current_trick = TrickState(leader=leader)
        hand.current_seat = leader

        # Re-sort human hand with bower awareness now that trump is known
        sort_hand_for_display(hand.hands[HUMAN_SEAT], hand.contract_type, hand.trump)

        return state

    # ------------------------------------------------------------------
    # Internal — card play
    # ------------------------------------------------------------------

    def _process_card_play(
        self, state: MatchState, seat: int, card_index: int
    ) -> MatchState:
        """Play a card from *seat*'s hand and advance the trick."""
        hand = state.current_hand
        assert hand is not None and hand.phase == "trick_play"
        assert hand.current_trick is not None

        # Remove card from hand and add to trick
        card = hand.hands[seat].pop(card_index)
        hand.current_trick.plays.append((seat, card))
        hand.turn_number += 1

        # Check if trick is complete (3 plays for moon/loner, 4 otherwise)
        ppt = _players_per_trick(hand.sitting_out_seat)
        if len(hand.current_trick.plays) >= ppt:
            state = self._process_trick_end(state)
        else:
            # Advance to next active player (skip sitting-out seat)
            hand.current_seat = _next_active_seat(seat, hand.sitting_out_seat)

        return state

    def _process_trick_end(self, state: MatchState) -> MatchState:
        """Determine the trick winner and either start next trick or end hand."""
        hand = state.current_hand
        assert hand is not None and hand.current_trick is not None
        assert hand.contract_type is not None

        # Delegate to core rules for winner determination
        winner = trick_winner(
            hand.current_trick.plays,
            hand.contract_type,
            hand.trump,
        )

        # Record completed trick
        result = TrickResult(
            leader=hand.current_trick.leader,
            plays=list(hand.current_trick.plays),
            winner=winner,
        )
        hand.completed_tricks.append(result)

        # Update team trick counts
        if winner in (0, 2):
            hand.tricks_team0 += 1
        else:
            hand.tricks_team1 += 1

        # Check if hand is complete (10 tricks)
        if len(hand.completed_tricks) >= _TRICKS_PER_HAND:
            state = self._process_hand_end(state)
        else:
            # Winner leads next trick (skip sitting-out seat if needed)
            leader = winner
            if hand.sitting_out_seat is not None and leader == hand.sitting_out_seat:
                leader = _next_active_seat(leader, hand.sitting_out_seat)
            hand.current_trick = TrickState(leader=leader)
            hand.current_seat = leader

        return state

    def _process_hand_end(self, state: MatchState) -> MatchState:
        """Score the hand, update match totals, and check for match end."""
        hand = state.current_hand
        assert hand is not None
        assert hand.winning_bid is not None
        assert hand.bidder_seat is not None

        hand.phase = "complete"
        hand.current_trick = None

        # Use the bid_type tracked on hand state (set during auction)
        bid_type = hand.bid_type

        # Delegate scoring to the canonical function
        pts0, pts1 = compute_points(
            winning_bid=hand.winning_bid,
            bidder_position=hand.bidder_seat,
            tricks_team0=hand.tricks_team0,
            tricks_team1=hand.tricks_team1,
            bid_type=bid_type,
        )
        hand.points_team0 = pts0
        hand.points_team1 = pts1

        # Update match scores
        state.score_human += pts0
        state.score_ai += pts1
        state.hands_played += 1

        # Check for match end (±52)
        if state.score_human >= MATCH_TARGET:
            state.status = "complete"
            state.winner = "human"
            return state
        if state.score_ai >= MATCH_TARGET:
            state.status = "complete"
            state.winner = "ai"
            return state
        # Also check negative threshold
        if state.score_human <= -MATCH_TARGET:
            state.status = "complete"
            state.winner = "ai"
            return state
        if state.score_ai <= -MATCH_TARGET:
            state.status = "complete"
            state.winner = "human"
            return state

        # Keep the hand complete so the game UI can render the hand_result.
        # The next hand is only started when the caller explicitly advances via
        # /next-hand.
        return state

    def advance_to_next_hand(self, state: MatchState) -> MatchState:
        """Advance from a completed hand to the next hand and auto-play AI."""
        hand = state.current_hand
        if hand is None or hand.phase != "complete" or state.status != "active":
            return state

        state.dealer_seat = (state.dealer_seat + 1) % _NUM_PLAYERS
        state.deal_id += 1
        state = self._deal_new_hand(state)
        state = self._advance_ai(state)
        return state
