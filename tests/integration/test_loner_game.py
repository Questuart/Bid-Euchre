"""Integration tests for loner trick play (3-player games).

Validates that when a loner bid wins the auction, the declarer's partner
sits out of trick play, each trick has 3 cards, lead rotation skips the
sitting-out player, and regular/moon games remain unaffected.
"""

import random
from collections import defaultdict
from typing import Dict, List

import pytest

from bid_euchre.core.cards import create_deck, deal_hands, shuffle_deck
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy import GreedyStrategy
from bid_euchre.strategy.bidding import BidAction, BiddingObservation, BiddingPolicy


class AlwaysLonerPolicy(BiddingPolicy):
    """A bidding policy that always bids loner with a fixed contract.

    Used for testing loner trick play mechanics. The first player to bid
    wins the auction since loner overcalls everything.
    """

    def __init__(self, contract: str = "H", seat_to_bid: int = 0):
        self.contract = contract
        self.seat_to_bid = seat_to_bid

    @property
    def strategy_id(self) -> str:
        return "always_loner"

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.seat_to_bid:
            return BidAction.loner(self.contract)
        return BidAction.pass_bid()


class AlwaysMoonPolicy(BiddingPolicy):
    """A bidding policy that always bids moon with a fixed contract."""

    def __init__(self, contract: str = "H", seat_to_bid: int = 0):
        self.contract = contract
        self.seat_to_bid = seat_to_bid

    @property
    def strategy_id(self) -> str:
        return "always_moon"

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.seat_to_bid:
            return BidAction.moon(self.contract)
        return BidAction.pass_bid()


class AlwaysRegularPolicy(BiddingPolicy):
    """A bidding policy that always bids a regular bid."""

    def __init__(self, contract: str = "H", bid_n: int = 6, seat_to_bid: int = 0):
        self.contract = contract
        self.bid_n = bid_n
        self.seat_to_bid = seat_to_bid

    @property
    def strategy_id(self) -> str:
        return "always_regular"

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.seat_to_bid:
            return BidAction.bid(self.bid_n, self.contract)
        return BidAction.pass_bid()


class TrackingStrategy(GreedyStrategy):
    """GreedyStrategy that tracks which seats play cards and trick sizes."""

    def __init__(self):
        super().__init__()
        self.plays_by_seat: Dict[int, int] = defaultdict(int)
        self.trick_sizes: List[int] = []
        self._current_trick_plays: int = 0
        self._last_trick_num: int = -1

    def choose_card(self, hand, plays_so_far, contract_type, trump_suit, player_index):
        self.plays_by_seat[player_index] += 1

        # Track trick sizes: when plays_so_far is empty, a new trick started
        if len(plays_so_far) == 0:
            if self._current_trick_plays > 0:
                self.trick_sizes.append(self._current_trick_plays)
            self._current_trick_plays = 1
        else:
            self._current_trick_plays += 1

        return super().choose_card(
            hand=hand,
            plays_so_far=plays_so_far,
            contract_type=contract_type,
            trump_suit=trump_suit,
            player_index=player_index,
        )

    def finalize_trick_tracking(self):
        """Call after the game to record the last trick."""
        if self._current_trick_plays > 0:
            self.trick_sizes.append(self._current_trick_plays)
            self._current_trick_plays = 0


# Partnership map: seat -> partner seat
_PARTNER = {0: 2, 1: 3, 2: 0, 3: 1}


class TestLonerTrickPlay:
    """Test that loner bids produce 3-player trick play."""

    @pytest.mark.parametrize("declarer_seat", [0, 1, 2, 3])
    def test_loner_game_completes(self, declarer_seat):
        """A full loner game completes with 10 tricks of 3 cards each."""
        rng = random.Random(42 + declarer_seat)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[
                AlwaysLonerPolicy(contract="H", seat_to_bid=declarer_seat)
            ]
            * 4,
            hands=hands,
            initial_leader=declarer_seat,
            deal_id=0,
            rng=rng,
        )

        t0, t1 = result[0], result[1]
        # Total tricks must still sum to 10
        assert t0 + t1 == 10, f"Expected 10 total tricks, got {t0 + t1}"

    @pytest.mark.parametrize("declarer_seat", [0, 1, 2, 3])
    def test_partner_never_plays_in_loner(self, declarer_seat):
        """The declarer's partner should not play any cards during loner."""
        rng = random.Random(100 + declarer_seat)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        partner_seat = _PARTNER[declarer_seat]
        tracker = TrackingStrategy()

        play_single_hand(
            contract_type=None,
            bidding_policies=[
                AlwaysLonerPolicy(contract="H", seat_to_bid=declarer_seat)
            ]
            * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=declarer_seat,
            deal_id=0,
            rng=rng,
        )

        # Partner should never have played
        assert tracker.plays_by_seat[partner_seat] == 0, (
            f"Partner (seat {partner_seat}) played {tracker.plays_by_seat[partner_seat]} "
            f"cards, expected 0"
        )

    @pytest.mark.parametrize("declarer_seat", [0, 1, 2, 3])
    def test_active_players_play_10_cards_each(self, declarer_seat):
        """Each active player (non-sitting-out) should play exactly 10 cards."""
        rng = random.Random(200 + declarer_seat)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        partner_seat = _PARTNER[declarer_seat]
        tracker = TrackingStrategy()

        play_single_hand(
            contract_type=None,
            bidding_policies=[
                AlwaysLonerPolicy(contract="H", seat_to_bid=declarer_seat)
            ]
            * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=declarer_seat,
            deal_id=0,
            rng=rng,
        )

        # Active players should have played 10 cards each
        for seat in range(4):
            if seat == partner_seat:
                assert (
                    tracker.plays_by_seat[seat] == 0
                ), f"Sitting-out seat {seat} played {tracker.plays_by_seat[seat]} cards"
            else:
                assert tracker.plays_by_seat[seat] == 10, (
                    f"Active seat {seat} played {tracker.plays_by_seat[seat]} cards, "
                    f"expected 10"
                )

    @pytest.mark.parametrize("declarer_seat", [0, 1, 2, 3])
    def test_loner_tricks_have_3_cards(self, declarer_seat):
        """Each trick in a loner game should have exactly 3 cards."""
        rng = random.Random(400 + declarer_seat)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        tracker = TrackingStrategy()

        play_single_hand(
            contract_type=None,
            bidding_policies=[
                AlwaysLonerPolicy(contract="H", seat_to_bid=declarer_seat)
            ]
            * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=declarer_seat,
            deal_id=0,
            rng=rng,
        )

        tracker.finalize_trick_tracking()

        assert (
            len(tracker.trick_sizes) == 10
        ), f"Expected 10 tricks, got {len(tracker.trick_sizes)}"
        for i, size in enumerate(tracker.trick_sizes):
            assert size == 3, f"Trick {i} had {size} cards, expected 3"

    def test_regular_game_still_works(self):
        """Regular (non-loner) games are unaffected by loner logic."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        tracker = TrackingStrategy()

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysRegularPolicy(contract="H", bid_n=6)] * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        t0, t1 = result[0], result[1]
        assert t0 + t1 == 10

        # All players should have played 10 cards each
        for seat in range(4):
            assert (
                tracker.plays_by_seat[seat] == 10
            ), f"Seat {seat} played {tracker.plays_by_seat[seat]} cards, expected 10"

    def test_moon_game_still_4_players(self):
        """Moon bids should still use 4-player trick play."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        tracker = TrackingStrategy()

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysMoonPolicy(contract="H")] * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        t0, t1 = result[0], result[1]
        assert t0 + t1 == 10

        # All 4 players should have played 10 cards each
        for seat in range(4):
            assert (
                tracker.plays_by_seat[seat] == 10
            ), f"Seat {seat} played {tracker.plays_by_seat[seat]} cards, expected 10"

    def test_fixed_contract_still_4_players(self):
        """Fixed-contract mode (no auction) should still use 4-player tricks."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        tracker = TrackingStrategy()

        result = play_single_hand(
            contract_type="suit",
            trump_suit="H",
            strategy=tracker,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        t0, t1 = result[0], result[1]
        assert t0 + t1 == 10

        for seat in range(4):
            assert (
                tracker.plays_by_seat[seat] == 10
            ), f"Seat {seat} played {tracker.plays_by_seat[seat]} cards, expected 10"

    def test_loner_determinism(self):
        """Same seed + config should produce identical loner results."""
        results = []
        for _ in range(2):
            rng = random.Random(42)
            deck = create_deck()
            shuffle_deck(deck, rng=rng)
            hands = deal_hands(deck, num_players=4, hand_size=10)

            result = play_single_hand(
                contract_type=None,
                bidding_policies=[AlwaysLonerPolicy(contract="H", seat_to_bid=0)] * 4,
                hands=hands,
                initial_leader=0,
                deal_id=0,
                rng=rng,
            )
            results.append((result[0], result[1]))

        assert results[0] == results[1], "Loner games should be deterministic"

    @pytest.mark.parametrize("declarer_seat", [0, 1, 2, 3])
    def test_loner_trick_count_correct(self, declarer_seat):
        """Tricks won should be valid for 3-player games."""
        rng = random.Random(300 + declarer_seat)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[
                AlwaysLonerPolicy(contract="H", seat_to_bid=declarer_seat)
            ]
            * 4,
            hands=hands,
            initial_leader=declarer_seat,
            deal_id=0,
            rng=rng,
        )

        t0, t1 = result[0], result[1]
        # Total must be 10 (10 tricks played)
        assert t0 + t1 == 10
        # Both teams should get at least 0 tricks
        assert t0 >= 0
        assert t1 >= 0

    def test_loner_with_no_trump_contract(self):
        """Loner works with high no-trump contract."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        tracker = TrackingStrategy()

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysLonerPolicy(contract="HIGH", seat_to_bid=0)] * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        t0, t1 = result[0], result[1]
        assert t0 + t1 == 10

        # Partner (seat 2) should not have played
        assert (
            tracker.plays_by_seat[2] == 0
        ), f"Partner played {tracker.plays_by_seat[2]} cards, expected 0"

    @pytest.mark.parametrize("declarer_seat", [0, 1, 2, 3])
    def test_lead_rotation_skips_sitting_out(self, declarer_seat):
        """The lead rotation should never assign the sitting-out player as leader."""
        rng = random.Random(500 + declarer_seat)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        partner_seat = _PARTNER[declarer_seat]
        tracker = TrackingStrategy()

        play_single_hand(
            contract_type=None,
            bidding_policies=[
                AlwaysLonerPolicy(contract="H", seat_to_bid=declarer_seat)
            ]
            * 4,
            strategy=tracker,
            hands=hands,
            initial_leader=declarer_seat,
            deal_id=0,
            rng=rng,
        )

        # Sitting-out partner should never have played (which means they never led)
        assert (
            tracker.plays_by_seat[partner_seat] == 0
        ), f"Partner (seat {partner_seat}) should never play or lead in loner"

        # Total plays should be 30 (3 players x 10 tricks)
        total_plays = sum(tracker.plays_by_seat.values())
        assert total_plays == 30, f"Expected 30 total plays, got {total_plays}"
