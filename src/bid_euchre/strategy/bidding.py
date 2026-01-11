"""
Bidding policy interface and related types for Bid Euchre auction mode.

This module provides the canonical interface for bidding in auction games,
where players bid simultaneously for the right to choose contract and trump.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.cards import Card


@dataclass(frozen=True)
class BidAction:
    """
    Represents a bidding action in auction mode.

    Either a pass (n=0) or a bid for n tricks with a specific contract.
    For suit contracts, trump_suit must be specified.
    """
    n: int  # 0 = pass, 1-10 = bid amount
    contract: Optional[str] = None  # contract type or None for passes
    trump_suit: Optional[str] = None  # trump suit for "suit" contracts

    def __post_init__(self):
        """Validate bid action constraints."""
        if self.n < 0 or self.n > 10:
            raise ValueError(f"Bid amount n must be 0-10, got {self.n}")

        if self.n == 0:
            # Pass: contract and trump must be None
            if self.contract is not None:
                raise ValueError(f"Pass (n=0) must have contract=None, got {self.contract}")
            if self.trump_suit is not None:
                raise ValueError(f"Pass (n=0) must have trump_suit=None, got {self.trump_suit}")
        else:
            # Bid: contract must be specified and valid
            if self.contract is None:
                raise ValueError(f"Bid (n={self.n}) must specify contract")
            if self.contract not in {"C", "D", "H", "S", "HIGH", "LOW"}:
                raise ValueError(f"Contract must be one of 'C', 'D', 'H', 'S', 'HIGH', 'LOW', got '{self.contract}'")

            # For suit contracts (C, D, H, S), trump_suit should be None (contract IS the suit)
            # For HIGH/LOW, trump_suit must be None
            if self.trump_suit is not None:
                raise ValueError(f"trump_suit must be None for v1 contracts, got {self.trump_suit}")

    @classmethod
    def pass_bid(cls) -> "BidAction":
        """Create a pass action."""
        return cls(n=0, contract=None, trump_suit=None)

    @classmethod
    def bid(cls, n: int, contract: str) -> "BidAction":
        """Create a bid action."""
        return cls(n=n, contract=contract, trump_suit=None)

    def is_pass(self) -> bool:
        """Return True if this is a pass."""
        return self.n == 0

    def to_contract_tuple(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Convert to the legacy (contract_type, trump_suit) tuple format.

        Returns:
            (contract_type, trump_suit) where:
            - For suit contracts (C, D, H, S): ("suit", contract)
            - For HIGH: ("high", None)
            - For LOW: ("low", None)
            - For pass: (None, None)
        """
        if self.is_pass():
            return None, None
        elif self.contract in {"C", "D", "H", "S"}:
            return "suit", self.contract
        elif self.contract == "HIGH":
            return "high", None
        elif self.contract == "LOW":
            return "low", None
        else:
            raise ValueError(f"Unknown contract: {self.contract}")


@dataclass(frozen=True)
class BiddingObservation:
    """
    Observation provided to bidding policies in auction mode (v1).

    Contains minimal information needed for bidding decisions.
    """
    hand: List[Card]  # Player's current hand
    seat: int  # Player's seat index (0-3)
    dealer_seat: int  # Dealer's seat index (0-3)
    current_high_bid: int  # Current highest bid (0-10, 0 means no bids yet)
    allowed_contracts: Tuple[str, ...] = ("C", "D", "H", "S", "HIGH", "LOW")  # Allowed contract types


class BiddingPolicy(ABC):
    """
    Abstract base class for bidding policies in auction mode.

    Bidding policies decide how to bid based on the current auction state.
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name

    @abstractmethod
    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        """
        Choose a bid action given the current bidding observation.

        Args:
            obs: Current bidding observation

        Returns:
            BidAction to take (pass or bid with contract)
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    def __repr__(self) -> str:
        return str(self)


class AlwaysPassBidder(BiddingPolicy):
    """
    Baseline bidder that always passes (n=0).
    """

    def __init__(self, name: str = "always_pass"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        return BidAction.pass_bid()


class StrictRaiserBidder(BiddingPolicy):
    """
    Baseline bidder that follows strict raising rules.

    - If current_high_bid == 0: bid 3
    - If current_high_bid < 10: bid current_high_bid + 1
    - If current_high_bid >= 10: pass
    - Always bids for "S" (Spades) contract (deterministic choice)
    """

    def __init__(self, name: str = "strict_raiser"):
        super().__init__(name)

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        current = obs.current_high_bid

        if current == 0:
            return BidAction.bid(3, "S")
        elif current < 10:
            return BidAction.bid(current + 1, "S")
        else:
            # current >= 10, cannot raise further
            return BidAction.pass_bid()