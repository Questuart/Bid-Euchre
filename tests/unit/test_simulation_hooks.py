"""Unit tests for simulation hooks infrastructure."""

from typing import List

from bid_euchre.core.cards import Card
from bid_euchre.sim.hooks import (
    BiddingDecisionEvent,
    HandEndEvent,
    SimulationHooks,
)
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.bidding import RanktheTank


class TestHandEndEvent:
    """Tests for HandEndEvent dataclass."""

    def test_can_create_hand_end_event(self):
        """HandEndEvent can be instantiated with required fields."""
        event = HandEndEvent(
            deal_id=0,
            seed=42,
            hands=[[Card("A", "S")], [Card("K", "H")], [Card("Q", "D")], [Card("J", "C")]],
            dealer_seat=0,
            contract_type="suit",
            trump_suit="S",
            initial_leader=1,
            tricks_team0=6,
            tricks_team1=4,
            scores=[10, 5, 8, 3],
            features=[{"trump_count": 3}, {"trump_count": 1}, {"trump_count": 2}, {"trump_count": 1}],
            winning_bid=5,
            bidder_seat=1,
        )
        assert event.deal_id == 0
        assert event.contract_type == "suit"
        assert event.tricks_team0 == 6

    def test_bidless_scenario_has_none_for_auction_fields(self):
        """In bidless scenarios, auction fields can be None."""
        event = HandEndEvent(
            deal_id=0,
            seed=42,
            hands=[[], [], [], []],
            dealer_seat=None,  # No dealer in bidless
            contract_type="high",
            trump_suit=None,
            initial_leader=0,
            tricks_team0=5,
            tricks_team1=5,
            scores=[0, 0, 0, 0],
            features=[{}, {}, {}, {}],
            winning_bid=None,
            bidder_seat=None,
        )
        assert event.dealer_seat is None
        assert event.winning_bid is None
        assert event.bidder_seat is None


class TestBiddingDecisionEvent:
    """Tests for BiddingDecisionEvent dataclass."""

    def test_can_create_bidding_decision_event(self):
        """BiddingDecisionEvent can be instantiated with required fields."""
        event = BiddingDecisionEvent(
            deal_id=0,
            seat=1,
            hand=[Card("A", "S"), Card("K", "S")],
            dealer_seat=0,
            current_high_bid=3,
            bid_amount=4,
            bid_contract="S",
            is_legal=True,
        )
        assert event.deal_id == 0
        assert event.seat == 1
        assert event.bid_amount == 4
        assert event.bid_contract == "S"

    def test_pass_bid_has_zero_amount(self):
        """Pass bids have bid_amount=0."""
        event = BiddingDecisionEvent(
            deal_id=0,
            seat=2,
            hand=[],
            dealer_seat=0,
            current_high_bid=5,
            bid_amount=0,
            bid_contract=None,
            is_legal=True,
        )
        assert event.bid_amount == 0
        assert event.bid_contract is None


class TestSimulationHooks:
    """Tests for SimulationHooks container."""

    def test_empty_hooks_dont_crash(self):
        """SimulationHooks with no callbacks can fire events safely."""
        hooks = SimulationHooks()
        # These should not raise
        event = HandEndEvent(
            deal_id=0,
            seed=None,
            hands=[[], [], [], []],
            dealer_seat=None,
            contract_type="high",
            trump_suit=None,
            initial_leader=0,
            tricks_team0=5,
            tricks_team1=5,
            scores=[0, 0, 0, 0],
            features=[{}, {}, {}, {}],
            winning_bid=None,
            bidder_seat=None,
        )
        hooks.fire_hand_end(event)

        bid_event = BiddingDecisionEvent(
            deal_id=0,
            seat=0,
            hand=[],
            dealer_seat=0,
            current_high_bid=0,
            bid_amount=0,
            bid_contract=None,
            is_legal=True,
        )
        hooks.fire_bidding_decision(bid_event)

    def test_hand_end_callback_receives_event(self):
        """on_hand_end callback is called with the event."""
        received_events: List[HandEndEvent] = []

        def handler(event: HandEndEvent) -> None:
            received_events.append(event)

        hooks = SimulationHooks(on_hand_end=handler)
        event = HandEndEvent(
            deal_id=42,
            seed=123,
            hands=[[], [], [], []],
            dealer_seat=0,
            contract_type="low",
            trump_suit=None,
            initial_leader=2,
            tricks_team0=4,
            tricks_team1=6,
            scores=[1, 2, 3, 4],
            features=[{}, {}, {}, {}],
            winning_bid=4,
            bidder_seat=2,
        )
        hooks.fire_hand_end(event)

        assert len(received_events) == 1
        assert received_events[0].deal_id == 42
        assert received_events[0].contract_type == "low"

    def test_bidding_decision_callback_receives_event(self):
        """on_bidding_decision callback is called with the event."""
        received_events: List[BiddingDecisionEvent] = []

        def handler(event: BiddingDecisionEvent) -> None:
            received_events.append(event)

        hooks = SimulationHooks(on_bidding_decision=handler)
        event = BiddingDecisionEvent(
            deal_id=0,
            seat=3,
            hand=[Card("A", "H")],
            dealer_seat=0,
            current_high_bid=2,
            bid_amount=5,
            bid_contract="H",
            is_legal=True,
        )
        hooks.fire_bidding_decision(event)

        assert len(received_events) == 1
        assert received_events[0].seat == 3
        assert received_events[0].bid_amount == 5


class TestSimulationWithHooks:
    """Integration tests for hooks with simulate_many_hands."""

    def test_hooks_none_preserves_behavior(self):
        """When hooks=None, simulation works as before."""
        # This should not raise
        result = simulate_many_hands(
            n=10,
            contract_type="suit",
            trump_suit="S",
            seed=42,
            hooks=None,
        )
        assert result["hands"] == 10
        assert result["contract_type"] == "suit"

    def test_hand_end_hook_fires_for_each_hand(self):
        """on_hand_end fires exactly n times for n hands."""
        events: List[HandEndEvent] = []

        def handler(event: HandEndEvent) -> None:
            events.append(event)

        hooks = SimulationHooks(on_hand_end=handler)
        simulate_many_hands(
            n=5,
            contract_type="high",
            trump_suit=None,
            seed=42,
            hooks=hooks,
        )

        assert len(events) == 5
        # Verify each event has correct deal_id
        assert [e.deal_id for e in events] == [0, 1, 2, 3, 4]
        # All should have contract_type="high"
        assert all(e.contract_type == "high" for e in events)

    def test_hand_end_event_has_correct_structure(self):
        """HandEndEvent contains expected fields from simulation."""
        events: List[HandEndEvent] = []

        def handler(event: HandEndEvent) -> None:
            events.append(event)

        hooks = SimulationHooks(on_hand_end=handler)
        simulate_many_hands(
            n=1,
            contract_type="suit",
            trump_suit="H",
            seed=42,
            hooks=hooks,
        )

        assert len(events) == 1
        event = events[0]

        # Check structural properties
        assert event.deal_id == 0
        assert event.seed == 42
        assert len(event.hands) == 4  # 4 players
        assert all(len(h) == 10 for h in event.hands)  # Each has 10 cards
        assert event.contract_type == "suit"
        assert event.trump_suit == "H"
        assert 0 <= event.initial_leader <= 3
        assert event.tricks_team0 + event.tricks_team1 == 10
        assert len(event.scores) == 4
        assert len(event.features) == 4

    def test_bidding_decision_hook_fires_during_auction(self):
        """on_bidding_decision fires for each bid in auction mode."""
        events: List[BiddingDecisionEvent] = []

        def handler(event: BiddingDecisionEvent) -> None:
            events.append(event)

        hooks = SimulationHooks(on_bidding_decision=handler)
        # Auction mode: contract_type=None triggers bidding
        simulate_many_hands(
            n=1,
            contract_type=None,  # Auction mode
            trump_suit=None,
            seed=42,
            bidding_policy=RanktheTank(),
            hooks=hooks,
        )

        # Should have at least 4 bidding decisions (one per seat)
        assert len(events) >= 4
        # All events should have deal_id=0
        assert all(e.deal_id == 0 for e in events)
        # Seats should be 0-3
        seats = {e.seat for e in events}
        assert seats <= {0, 1, 2, 3}

    def test_bidding_decision_has_correct_structure(self):
        """BiddingDecisionEvent has expected fields."""
        events: List[BiddingDecisionEvent] = []

        def handler(event: BiddingDecisionEvent) -> None:
            events.append(event)

        hooks = SimulationHooks(on_bidding_decision=handler)
        simulate_many_hands(
            n=1,
            contract_type=None,
            trump_suit=None,
            seed=42,
            bidding_policy=RanktheTank(),
            hooks=hooks,
        )

        assert len(events) > 0
        event = events[0]

        # Check structural properties
        assert 0 <= event.seat <= 3
        assert 0 <= event.dealer_seat <= 3
        assert event.current_high_bid >= 0
        assert len(event.hand) == 10  # Full hand at bid time
        assert event.bid_amount >= 0
        # Contract is either None (pass) or a valid contract
        if event.bid_amount > 0:
            assert event.bid_contract in {"C", "D", "H", "S", "HIGH", "LOW"}
        else:
            assert event.bid_contract is None

    def test_hooks_dont_affect_results(self):
        """Hooks are purely observational - results should be identical."""
        # Run without hooks
        result_no_hooks = simulate_many_hands(
            n=10,
            contract_type="suit",
            trump_suit="S",
            seed=42,
            hooks=None,
        )

        # Run with hooks
        events: List[HandEndEvent] = []
        hooks = SimulationHooks(on_hand_end=lambda e: events.append(e))
        result_with_hooks = simulate_many_hands(
            n=10,
            contract_type="suit",
            trump_suit="S",
            seed=42,
            hooks=hooks,
        )

        # Results should be identical
        assert result_no_hooks["avg_team0"] == result_with_hooks["avg_team0"]
        assert result_no_hooks["avg_team1"] == result_with_hooks["avg_team1"]
        assert result_no_hooks["distribution_team0"] == result_with_hooks["distribution_team0"]
        assert len(events) == 10

    def test_no_bidding_events_in_bidless_mode(self):
        """No bidding events fire when contract is pre-declared."""
        events: List[BiddingDecisionEvent] = []

        def handler(event: BiddingDecisionEvent) -> None:
            events.append(event)

        hooks = SimulationHooks(on_bidding_decision=handler)
        simulate_many_hands(
            n=5,
            contract_type="suit",  # Pre-declared = no auction
            trump_suit="S",
            seed=42,
            hooks=hooks,
        )

        # No bidding events should fire
        assert len(events) == 0
