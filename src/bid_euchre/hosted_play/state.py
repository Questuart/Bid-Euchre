"""Hosted-play state dataclasses and JSON serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bid_euchre.core.cards import Card


def _card_to_data(card: Card) -> list[str]:
    return [card.suit, card.rank]


def _card_from_data(data: list[str] | tuple[str, str]) -> Card:
    if len(data) != 2:
        raise ValueError(f"Expected card payload of length 2, got {data!r}")
    suit, rank = data
    return Card(suit=suit, rank=rank)


def _plays_to_data(plays: list[tuple[int, Card]]) -> list[list[Any]]:
    return [[seat, _card_to_data(card)] for seat, card in plays]


def _plays_from_data(data: list[list[Any]]) -> list[tuple[int, Card]]:
    plays: list[tuple[int, Card]] = []
    for item in data:
        if len(item) != 2:
            raise ValueError(f"Expected play payload of length 2, got {item!r}")
        seat, card = item
        plays.append((int(seat), _card_from_data(card)))
    return plays


@dataclass(eq=True)
class TrickState:
    """Mutable state for the in-progress trick."""

    leader: int
    plays: list[tuple[int, Card]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leader": self.leader,
            "plays": _plays_to_data(self.plays),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrickState":
        return cls(
            leader=int(data["leader"]),
            plays=_plays_from_data(data.get("plays", [])),
        )


@dataclass(eq=True)
class TrickResult:
    """Completed trick record used for replay and resume."""

    leader: int
    plays: list[tuple[int, Card]]
    winner: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "leader": self.leader,
            "plays": _plays_to_data(self.plays),
            "winner": self.winner,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrickResult":
        return cls(
            leader=int(data["leader"]),
            plays=_plays_from_data(data.get("plays", [])),
            winner=int(data["winner"]),
        )


@dataclass(eq=True)
class HandState:
    """Persisted state for a single hosted-play hand."""

    phase: str
    hands: list[list[Card]]
    dealer_seat: int
    deal_id: int
    auction: list[dict[str, Any]] = field(default_factory=list)
    revealed_auction_count: int = 0
    current_high_bid: int = 0
    bidder_seat: int | None = None
    winning_bid: int | None = None
    contract_type: str | None = None
    trump: str | None = None
    current_trick: TrickState | None = None
    completed_tricks: list[TrickResult] = field(default_factory=list)
    paused_after_trick: bool = False
    bid_type: str = "regular"  # "regular" | "moon" | "loner"
    sitting_out_seat: int | None = None  # loner: partner sits out
    exchange_given: list[list[str]] | None = None  # moon: cards given to partner
    exchange_received: list[list[str]] | None = (
        None  # moon: cards received from partner
    )
    exchange_revealed: bool = False  # moon: True once exchange interstitial shown
    exchange_phase: str | None = None  # "selecting" when human is choosing cards
    tricks_team0: int = 0
    tricks_team1: int = 0
    points_team0: int = 0
    points_team1: int = 0
    current_seat: int = 0
    turn_number: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "hands": [[_card_to_data(card) for card in hand] for hand in self.hands],
            "dealer_seat": self.dealer_seat,
            "deal_id": self.deal_id,
            "auction": self.auction,
            "revealed_auction_count": self.revealed_auction_count,
            "current_high_bid": self.current_high_bid,
            "bidder_seat": self.bidder_seat,
            "winning_bid": self.winning_bid,
            "contract_type": self.contract_type,
            "trump": self.trump,
            "bid_type": self.bid_type,
            "sitting_out_seat": self.sitting_out_seat,
            "exchange_given": self.exchange_given,
            "exchange_received": self.exchange_received,
            "exchange_revealed": self.exchange_revealed,
            "exchange_phase": self.exchange_phase,
            "current_trick": (
                None if self.current_trick is None else self.current_trick.to_dict()
            ),
            "completed_tricks": [trick.to_dict() for trick in self.completed_tricks],
            "paused_after_trick": self.paused_after_trick,
            "tricks_team0": self.tricks_team0,
            "tricks_team1": self.tricks_team1,
            "points_team0": self.points_team0,
            "points_team1": self.points_team1,
            "current_seat": self.current_seat,
            "turn_number": self.turn_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HandState":
        return cls(
            phase=data["phase"],
            hands=[
                [_card_from_data(card) for card in hand]
                for hand in data.get("hands", [])
            ],
            dealer_seat=int(data["dealer_seat"]),
            deal_id=int(data["deal_id"]),
            auction=list(data.get("auction", [])),
            revealed_auction_count=int(data.get("revealed_auction_count", 0)),
            current_high_bid=int(data.get("current_high_bid", 0)),
            bidder_seat=(
                None if data.get("bidder_seat") is None else int(data["bidder_seat"])
            ),
            winning_bid=(
                None if data.get("winning_bid") is None else int(data["winning_bid"])
            ),
            contract_type=data.get("contract_type"),
            trump=data.get("trump"),
            bid_type=data.get("bid_type", "regular"),
            sitting_out_seat=(
                None
                if data.get("sitting_out_seat") is None
                else int(data["sitting_out_seat"])
            ),
            exchange_given=data.get("exchange_given"),
            exchange_received=data.get("exchange_received"),
            exchange_revealed=bool(data.get("exchange_revealed", False)),
            exchange_phase=data.get("exchange_phase"),
            current_trick=(
                None
                if data.get("current_trick") is None
                else TrickState.from_dict(data["current_trick"])
            ),
            completed_tricks=[
                TrickResult.from_dict(trick)
                for trick in data.get("completed_tricks", [])
            ],
            paused_after_trick=bool(data.get("paused_after_trick", False)),
            tricks_team0=int(data.get("tricks_team0", 0)),
            tricks_team1=int(data.get("tricks_team1", 0)),
            points_team0=int(data.get("points_team0", 0)),
            points_team1=int(data.get("points_team1", 0)),
            current_seat=int(data.get("current_seat", 0)),
            turn_number=int(data.get("turn_number", 0)),
        )


@dataclass(eq=True)
class MatchState:
    """Persisted state for the full hosted-play match."""

    seed: int
    ai_model: str
    score_human: int = 0
    score_ai: int = 0
    hands_played: int = 0
    current_hand: HandState | None = None
    status: str = "active"
    winner: str | None = None
    dealer_seat: int = 0
    deal_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "ai_model": self.ai_model,
            "score_human": self.score_human,
            "score_ai": self.score_ai,
            "hands_played": self.hands_played,
            "current_hand": (
                None if self.current_hand is None else self.current_hand.to_dict()
            ),
            "status": self.status,
            "winner": self.winner,
            "dealer_seat": self.dealer_seat,
            "deal_id": self.deal_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchState":
        return cls(
            seed=int(data["seed"]),
            ai_model=data["ai_model"],
            score_human=int(data.get("score_human", 0)),
            score_ai=int(data.get("score_ai", 0)),
            hands_played=int(data.get("hands_played", 0)),
            current_hand=(
                None
                if data.get("current_hand") is None
                else HandState.from_dict(data["current_hand"])
            ),
            status=data.get("status", "active"),
            winner=data.get("winner"),
            dealer_seat=int(data.get("dealer_seat", 0)),
            deal_id=int(data.get("deal_id", 0)),
        )
