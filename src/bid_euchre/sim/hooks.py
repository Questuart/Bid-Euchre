"""
Simulation hooks for decoupled instrumentation.

This module provides an event-based callback system for simulation instrumentation.
Consumers (loggers, dataset collectors, feature trackers) can subscribe to events
without the simulation engine needing to import or know about them.

Example usage:
    from bid_euchre.sim.hooks import SimulationHooks, HandEndEvent

    def my_hand_end_handler(event: HandEndEvent) -> None:
        print(f"Hand {event.deal_id} complete: {event.tricks_team0}-{event.tricks_team1}")

    hooks = SimulationHooks(on_hand_end=my_hand_end_handler)
    simulate_many_hands(n=100, contract_type="suit", trump_suit="S", hooks=hooks)
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..core.cards import Card


@dataclass
class HandEndEvent:
    """
    Fired after each hand completes (trick play finished).

    Contains all information needed by dataset collectors, loggers,
    and feature trackers to process the completed hand.
    """

    # Identifiers
    deal_id: int
    seed: Optional[int]

    # Game state (at deal time)
    hands: List[List[Card]]  # 4 starting hands (one per seat, before any cards played)
    dealer_seat: Optional[int]  # Dealer position (0-3), None if bidless scenario

    # Contract (may be declared or auction-determined)
    contract_type: str  # "suit", "high", "low"
    trump_suit: Optional[str]  # Trump suit for suit contracts ("C", "D", "H", "S")

    # Play state
    initial_leader: int  # Who led the first trick (0-3)

    # Outcome
    tricks_team0: int  # Tricks won by team 0 (seats 0, 2)
    tricks_team1: int  # Tricks won by team 1 (seats 1, 3)
    scores: List[int]  # 4 per-player hand strength scores
    features: List[Dict[str, Any]]  # 4 per-player feature dictionaries

    # Auction results (None if bidless scenario)
    winning_bid: Optional[int]  # The winning bid amount (1-10), or None/0 if no bidding
    bidder_seat: Optional[int]  # Seat that won the auction (0-3), or None if no bidding


@dataclass
class BiddingDecisionEvent:
    """
    Fired after each bidding decision during auction.

    Captures the full context of a bidding decision for training
    bidding policies via imitation learning.
    """

    # Identifiers
    deal_id: int
    seat: int  # Which player made this decision (0-3)

    # Context
    hand: List[Card]  # The player's hand at decision time
    dealer_seat: int  # Dealer position (0-3)
    current_high_bid: int  # Highest bid so far (0 means no bids yet)

    # Decision made
    bid_amount: int  # 0 = pass, 1-10 = bid
    bid_contract: Optional[str]  # "C", "D", "H", "S", "HIGH", "LOW", or None for pass

    # Metadata
    is_legal: bool  # Whether this bid was legal (valid amount > current)


@dataclass
class SimulationHooks:
    """
    Container for simulation event callbacks.

    All callbacks are optional. When None, the corresponding events are not fired,
    avoiding any overhead. Callbacks receive immutable event objects and should
    not modify simulation state.
    """

    on_hand_end: Optional[Callable[[HandEndEvent], None]] = None
    on_bidding_decision: Optional[Callable[[BiddingDecisionEvent], None]] = None

    def fire_hand_end(self, event: HandEndEvent) -> None:
        """Fire HandEndEvent if handler is registered."""
        if self.on_hand_end is not None:
            self.on_hand_end(event)

    def fire_bidding_decision(self, event: BiddingDecisionEvent) -> None:
        """Fire BiddingDecisionEvent if handler is registered."""
        if self.on_bidding_decision is not None:
            self.on_bidding_decision(event)
