"""
Structured game logging for Bid Euchre simulations.

Produces JSONL (JSON Lines) output with versioned schema for:
- hand_end: Summary of each completed hand
- trick_end: Per-trick play details (optional, more verbose)

Usage:
    logger = GameLogger(run_id="experiment_1", strategy_id="greedy", level=LogLevel.HAND)
    logger.open("logs/experiment_1.jsonl")

    # In simulation loop:
    logger.log_trick_end(deal_id, trick_num, leader, plays, winner)
    logger.log_hand_end(deal_id, seed, contract, trump, leader, t0, t1, features)

    logger.close()
"""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Current schema version - bump when fields change
# v2 adds `scores` to hand_end records (one scalar score per player).
# v3 adds `hands` to hand_end records (full hand contents for each player).
# v4 adds `winning_bid` to hand_end records.
# v5 adds `dealer_position` and `bidder_position` to hand_end records.
# v6 adds `redeal_flag` and `made_bid` to hand_end records.
# v7 adds `auction_transcript` to hand_end records.
# v8 adds `bid_type`, `exchange_cards_given`, `exchange_cards_received`,
#    and `sitting_out_seat` to hand_end records.
SCHEMA_VERSION = 8


class LogLevel(Enum):
    """Logging verbosity level."""

    NONE = "none"  # No JSONL output
    HAND = "hand"  # hand_end records only
    TRICK = "trick"  # hand_end + trick_end records


@dataclass
class HandEndRecord:
    """Record emitted at the end of each hand."""

    schema_version: int
    event: str
    run_id: str
    strategy_id: str
    deal_id: int
    seed: Optional[int]
    contract: str
    trump: Optional[str]
    leader: int
    t0: int
    t1: int
    features: List[Dict[str, Any]]  # 4 feature dicts, one per player
    scores: Optional[List[int]]  # 4 scalar scores, one per player (schema v2)
    hands: Optional[
        List[List[List[str]]]
    ]  # 4 hands, each card as [suit, rank] (schema v3)
    winning_bid: Optional[int] = None  # The high bid for this hand (schema v4)
    dealer_position: Optional[int] = None  # Dealer seat (0-3) (schema v5)
    bidder_position: Optional[int] = None  # Auction winner seat (0-3) (schema v5)
    redeal_flag: Optional[bool] = (
        None  # True if all players passed (all-pass redeal) (schema v6)
    )
    made_bid: Optional[bool] = None  # True if declaring team made their bid (schema v6)
    auction_transcript: Optional[List[Dict[str, Any]]] = (
        None  # 4-entry list or null (schema v7)
    )
    bid_type: Optional[str] = None  # "regular" | "moon" | "loner" or null (schema v8)
    exchange_cards_given: Optional[List[List[str]]] = (
        None  # Cards given during moon exchange, each as [suit, rank] (schema v8)
    )
    exchange_cards_received: Optional[List[List[str]]] = (
        None  # Cards received during moon exchange, each as [suit, rank] (schema v8)
    )
    sitting_out_seat: Optional[int] = (
        None  # Seat number sitting out during loner (schema v8)
    )
    timestamp: str = ""


@dataclass
class TrickEndRecord:
    """Record emitted at the end of each trick (optional, verbose)."""

    schema_version: int
    event: str
    run_id: str
    deal_id: int
    trick_num: int
    leader: int
    plays: List[List[Any]]  # [[player_idx, suit, rank], ...]
    winner: int
    timestamp: str


class GameLogger:
    """
    Structured JSONL logger for game events.

    Disabled by default (level=LogLevel.NONE).
    When enabled, writes one JSON object per line to the output file.
    """

    def __init__(
        self,
        run_id: str = "",
        strategy_id: str = "",
        level: LogLevel = LogLevel.NONE,
        output_dir: str = "logs",
    ):
        """
        Initialize the game logger.

        Args:
            run_id: Unique identifier for this run (e.g., "baseline_greedy_20251215")
            strategy_id: Identifier for the strategy being used
            level: Logging verbosity (NONE, HAND, TRICK)
            output_dir: Directory to write log files to
        """
        self.run_id = run_id or self._generate_run_id()
        self.strategy_id = strategy_id
        self.level = level
        self.output_dir = output_dir
        self._file = None
        self._filepath: Optional[str] = None

    def _generate_run_id(self) -> str:
        """Generate a unique run ID based on timestamp."""
        return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.now().isoformat()

    @property
    def is_enabled(self) -> bool:
        """Check if logging is enabled."""
        return self.level != LogLevel.NONE

    @property
    def log_tricks(self) -> bool:
        """Check if trick-level logging is enabled."""
        return self.level == LogLevel.TRICK

    def open(self, filepath: Optional[str] = None) -> "GameLogger":
        """
        Open the log file for writing.

        Args:
            filepath: Path to log file. If None, auto-generates in output_dir.

        Returns:
            self (for chaining)
        """
        if not self.is_enabled:
            return self

        if filepath is None:
            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, f"{self.run_id}.jsonl")

        self._filepath = filepath
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        self._file = open(filepath, "w")

        # Write header record
        header = {
            "schema_version": SCHEMA_VERSION,
            "event": "run_start",
            "run_id": self.run_id,
            "strategy_id": self.strategy_id,
            "log_level": self.level.value,
            "timestamp": self._timestamp(),
        }
        self._write_record(header)

        return self

    def close(self) -> None:
        """Close the log file."""
        if self._file:
            # Write footer record
            footer = {
                "schema_version": SCHEMA_VERSION,
                "event": "run_end",
                "run_id": self.run_id,
                "timestamp": self._timestamp(),
            }
            self._write_record(footer)
            self._file.close()
            self._file = None

    def _write_record(self, record: Dict[str, Any]) -> None:
        """Write a single JSON record to the log file."""
        if self._file:
            self._file.write(json.dumps(record, separators=(",", ":")) + "\n")

    def log_hand_end(
        self,
        deal_id: int,
        seed: Optional[int],
        contract: str,
        trump: Optional[str],
        leader: int,
        t0: int,
        t1: int,
        features: List[Dict[str, Any]],
        scores: Optional[List[int]] = None,
        hands: Optional[List[List[Any]]] = None,
        winning_bid: Optional[int] = None,
        dealer_position: Optional[int] = None,
        bidder_position: Optional[int] = None,
        redeal_flag: Optional[bool] = None,
        made_bid: Optional[bool] = None,
        auction_transcript: Optional[List[Dict[str, Any]]] = None,
        bid_type: Optional[str] = None,
        exchange_cards_given: Optional[List[Any]] = None,
        exchange_cards_received: Optional[List[Any]] = None,
        sitting_out_seat: Optional[int] = None,
    ) -> None:
        """
        Log the completion of a hand.

        Args:
            deal_id: Hand number within this run
            seed: Random seed used for this hand (if known)
            contract: Contract type ("suit", "high", "low")
            trump: Trump suit ("C", "D", "H", "S") or None
            leader: Player who led the first trick (0-3)
            t0: Tricks won by team 0
            t1: Tricks won by team 1
            features: List of 4 feature dicts, one per player
            scores: List of 4 scalar scores, one per player (schema v2+)
            hands: List of 4 hands (each hand is a list of Cards) (schema v3+)
            winning_bid: The high bid for this hand (schema v4+)
            dealer_position: Dealer seat (0-3) (schema v5+)
            bidder_position: Auction winner seat (0-3) (schema v5+)
            redeal_flag: True if all players passed (all-pass redeal) (schema v6+)
            made_bid: True if declaring team made their bid (schema v6+)
            auction_transcript: 4-entry list of per-seat bid actions (schema v7+)
            bid_type: "regular", "moon", or "loner" (schema v8+)
            exchange_cards_given: Cards given during moon exchange (schema v8+)
            exchange_cards_received: Cards received during moon exchange (schema v8+)
            sitting_out_seat: Seat sitting out during loner (schema v8+)
        """
        if not self.is_enabled:
            return

        # Convert Card objects to [suit, rank] lists for JSON serialization
        hands_json: Optional[List[List[List[str]]]] = None
        if hands is not None:
            hands_json = [[[card.suit, card.rank] for card in hand] for hand in hands]

        # Convert exchange Card objects to [suit, rank] lists
        exchange_given_json: Optional[List[List[str]]] = None
        if exchange_cards_given is not None:
            exchange_given_json = [
                [card.suit, card.rank] for card in exchange_cards_given
            ]
        exchange_received_json: Optional[List[List[str]]] = None
        if exchange_cards_received is not None:
            exchange_received_json = [
                [card.suit, card.rank] for card in exchange_cards_received
            ]

        record = HandEndRecord(
            schema_version=SCHEMA_VERSION,
            event="hand_end",
            run_id=self.run_id,
            strategy_id=self.strategy_id,
            deal_id=deal_id,
            seed=seed,
            contract=contract,
            trump=trump,
            leader=leader,
            t0=t0,
            t1=t1,
            features=features,
            scores=scores,
            hands=hands_json,
            winning_bid=winning_bid,
            dealer_position=dealer_position,
            bidder_position=bidder_position,
            redeal_flag=redeal_flag,
            made_bid=made_bid,
            auction_transcript=auction_transcript,
            bid_type=bid_type,
            exchange_cards_given=exchange_given_json,
            exchange_cards_received=exchange_received_json,
            sitting_out_seat=sitting_out_seat,
            timestamp=self._timestamp(),
        )
        self._write_record(asdict(record))

    def log_trick_end(
        self,
        deal_id: int,
        trick_num: int,
        leader: int,
        plays: List[Tuple[int, Any]],  # [(player_idx, Card), ...]
        winner: int,
    ) -> None:
        """
        Log the completion of a trick.

        Only emitted when level=LogLevel.TRICK.

        Args:
            deal_id: Hand number within this run
            trick_num: Trick number within this hand (0-9)
            leader: Player who led this trick (0-3)
            plays: List of (player_idx, Card) tuples in play order
            winner: Player who won the trick (0-3)
        """
        if not self.log_tricks:
            return

        # Convert Card objects to [suit, rank] lists for JSON serialization
        plays_json = [[p[0], p[1].suit, p[1].rank] for p in plays]

        record = TrickEndRecord(
            schema_version=SCHEMA_VERSION,
            event="trick_end",
            run_id=self.run_id,
            deal_id=deal_id,
            trick_num=trick_num,
            leader=leader,
            plays=plays_json,
            winner=winner,
            timestamp=self._timestamp(),
        )
        self._write_record(asdict(record))

    def __enter__(self) -> "GameLogger":
        """Context manager entry."""
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
