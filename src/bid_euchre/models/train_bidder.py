"""
Deterministic bidding model training pipeline v1.

This module implements a minimal, deterministic imitation-learning training pipeline
that trains a simple model to imitate StrictRaiserBidder behavior.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..strategy.bidding import BiddingObservation, RanktheTank, StrictRaiserBidder
from .bidding_artifact import dump_artifact, validate_artifact

DETERMINISTIC_BASE_TIME = datetime(2025, 1, 1, tzinfo=timezone.utc)


class StrictRaiserModel:
    """
    Deterministic model that exactly replicates StrictRaiserBidder logic.

    This is a rule-based model that encodes the bidding strategy as parameters.
    """

    def __init__(self):
        """Initialize with StrictRaiserBidder rules."""
        # Encode the bidding rules as model parameters
        self.rules = {
            "initial_bid": {"n": 3, "contract": "S"},
            "raise_increment": 1,
            "max_bid": 10,
            "contract": "S",  # Always bid Spades
        }

    def predict_bid(self, current_high_bid: int) -> Dict[str, Any]:
        """
        Predict bid action based on current high bid.

        Args:
            current_high_bid: Current highest bid (0-10)

        Returns:
            Dict with 'n' and 'contract' keys, or None for pass
        """
        if current_high_bid == 0:
            return {
                "n": self.rules["initial_bid"]["n"],
                "contract": self.rules["initial_bid"]["contract"],
            }
        elif current_high_bid < self.rules["max_bid"]:
            return {
                "n": current_high_bid + self.rules["raise_increment"],
                "contract": self.rules["contract"],
            }
        else:
            # Pass
            return None

    def to_artifact_dict(self, contract: str, seed: int = 42) -> Dict[str, Any]:
        """
        Convert model to bidding artifact format.

        Args:
            contract: The contract this model is trained for

        Returns:
            Artifact dictionary conforming to schema v1
        """
        created_at = (DETERMINISTIC_BASE_TIME + timedelta(seconds=seed)).isoformat()

        return {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": contract,
            "model_params": self.rules,
            "metadata": {
                "created_at": created_at,
                "description": f"Deterministic imitation of StrictRaiserBidder for {contract} contract",
                "training_data": "fixture dataset",
                "training_seed": seed,
                "teacher_model": "StrictRaiserBidder",
            },
        }


class FiveHeadFredModel:
    """
    Deterministic model that always bids 5 if legal, else passes.

    This is a minimal rule-based model for testing/baseline purposes.
    """

    def __init__(self, contract: str = "S"):
        """
        Initialize with FiveHeadFred rules.

        Args:
            contract: The contract to bid for (default: "S" for Spades)
        """
        # Encode the bidding rules as model parameters
        self.rules = {"target_bid": 5, "contract": contract}

    def predict_bid(self, current_high_bid: int) -> Optional[Dict[str, Any]]:
        """
        Predict bid action based on current high bid.

        Args:
            current_high_bid: Current highest bid (0-10)

        Returns:
            Dict with 'n' and 'contract' keys, or None for pass
        """
        # Bid 5 if legal (strictly greater than current_high_bid)
        if self.rules["target_bid"] > current_high_bid:
            return {"n": self.rules["target_bid"], "contract": self.rules["contract"]}
        else:
            # Pass if 5 is not legal
            return None

    def to_artifact_dict(self, contract: str, seed: int = 42) -> Dict[str, Any]:
        """
        Convert model to bidding artifact format.

        Args:
            contract: The contract this model is trained for
            seed: Random seed for deterministic timestamp

        Returns:
            Artifact dictionary conforming to schema v1
        """
        created_at = (DETERMINISTIC_BASE_TIME + timedelta(seconds=seed)).isoformat()

        return {
            "schema_version": "1",
            "model_type": "fiveheadfred_v1",
            "contract": contract,
            "model_params": self.rules,
            "metadata": {
                "created_at": created_at,
                "description": f"FiveHeadFred baseline: always bids 5 for {contract} if legal, else passes",
                "training_data": "deterministic rule",
                "training_seed": seed,
                "teacher_model": "FiveHeadFred",
            },
        }


def load_bidding_dataset_jsonl(path: str) -> List[Dict[str, Any]]:
    """
    Load bidding dataset from JSONL file.

    Args:
        path: Path to JSONL dataset file

    Returns:
        List of dataset rows
    """
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def create_synthetic_observations_for_strict_raiser() -> List[BiddingObservation]:
    """
    Create synthetic bidding observations to train StrictRaiserBidder imitation.

    Since the fixture dataset only contains passes, we need synthetic observations
    that cover the full bidding range.

    Returns:
        List of synthetic BiddingObservation instances
    """
    from ..core.cards import Card

    # Create a dummy hand for all observations
    dummy_hand = [
        Card("S", "K"),
        Card("S", "Q"),
        Card("H", "T"),
        Card("C", "A"),
        Card("C", "J"),
    ]

    observations = []
    for current_high_bid in range(0, 11):  # 0-10 inclusive
        for seat in range(4):
            for dealer_seat in range(4):
                obs = BiddingObservation(
                    hand=dummy_hand,
                    seat=seat,
                    dealer_seat=dealer_seat,
                    current_high_bid=current_high_bid,
                )
                observations.append(obs)

    return observations


def train_strict_raiser_model(contract: str = "S") -> StrictRaiserModel:
    """
    Train a deterministic model to imitate StrictRaiserBidder.

    Args:
        contract: Contract to train for (default: "S" for Spades)

    Returns:
        Trained StrictRaiserModel instance
    """
    # Create synthetic observations covering all bidding scenarios
    observations = create_synthetic_observations_for_strict_raiser()

    # Initialize model
    model = StrictRaiserModel()

    # "Train" by validating that our model matches StrictRaiserBidder
    teacher = StrictRaiserBidder()

    for obs in observations:
        teacher_action = teacher.choose_bid(obs)
        model_prediction = model.predict_bid(obs.current_high_bid)

        # Convert teacher action to dict format
        if teacher_action.is_pass():
            teacher_dict = None
        else:
            teacher_dict = {"n": teacher_action.n, "contract": teacher_action.contract}

        # Validate that model matches teacher
        if teacher_dict != model_prediction:
            raise ValueError(
                f"Model prediction {model_prediction} does not match "
                f"teacher action {teacher_dict} for current_high_bid={obs.current_high_bid}"
            )

    return model


def train_fiveheadfred_model(contract: str = "S") -> FiveHeadFredModel:
    """
    Train a deterministic model for FiveHeadFred baseline.

    Args:
        contract: Contract to train for (default: "S" for Spades)

    Returns:
        Trained FiveHeadFredModel instance
    """
    # Initialize model
    model = FiveHeadFredModel(contract)

    # Validate the model behavior for all possible current_high_bid values
    for current_high_bid in range(0, 11):  # 0-10 inclusive
        prediction = model.predict_bid(current_high_bid)

        # Verify expected behavior
        if current_high_bid < 5:
            # Should bid 5
            expected = {"n": 5, "contract": contract}
            if prediction != expected:
                raise ValueError(
                    f"Model prediction {prediction} does not match "
                    f"expected {expected} for current_high_bid={current_high_bid}"
                )
        else:
            # Should pass
            if prediction is not None:
                raise ValueError(
                    f"Model should pass for current_high_bid={current_high_bid}, "
                    f"but predicted {prediction}"
                )

    return model


class HeuristicsModel:
    """
    Deterministic model that exactly replicates RanktheTank logic.

    This is a rule-based model that encodes the heuristic bidding strategy
    as parameters, including suit and HIGH/LOW evaluation thresholds.
    """

    def __init__(self):
        """Initialize with RanktheTank rules."""
        # Encode the bidding rules as model parameters
        self.rules = {
            "suit_thresholds": {
                "bid_10": 750,
                "bid_9": 650,
                "bid_8": 550,
                "bid_7": 450,
                "bid_6": 350,
                "bid_5": 300,
                "bid_4": 250,
                "bid_3": 200,
                "bid_2": 150,
                "bid_1": 100,
            },
            "high_low_thresholds": {
                "bid_8": 500,
                "bid_7": 450,
                "bid_6": 400,
                "bid_5": 350,
                "bid_4": 280,
                "bid_3": 200,
                "bid_2": 150,
                "bid_1": 100,
            },
        }

    def predict_bid(self, obs: BiddingObservation) -> Optional[Dict[str, Any]]:
        """
        Predict bid action based on bidding observation.

        Args:
            obs: BiddingObservation with hand and game state

        Returns:
            Dict with 'n' and 'contract' keys, or None for pass
        """
        from ..features.hand_eval import score_hand_scalar

        # Evaluate all contract options
        candidates = []

        # Evaluate suit contracts
        for suit in ["C", "D", "H", "S"]:
            strength = score_hand_scalar(obs.hand, "suit", suit)

            # Map strength to bid amount
            if strength >= self.rules["suit_thresholds"]["bid_10"]:
                bid_n = 10
            elif strength >= self.rules["suit_thresholds"]["bid_9"]:
                bid_n = 9
            elif strength >= self.rules["suit_thresholds"]["bid_8"]:
                bid_n = 8
            elif strength >= self.rules["suit_thresholds"]["bid_7"]:
                bid_n = 7
            elif strength >= self.rules["suit_thresholds"]["bid_6"]:
                bid_n = 6
            elif strength >= self.rules["suit_thresholds"]["bid_5"]:
                bid_n = 5
            elif strength >= self.rules["suit_thresholds"]["bid_4"]:
                bid_n = 4
            elif strength >= self.rules["suit_thresholds"]["bid_3"]:
                bid_n = 3
            elif strength >= self.rules["suit_thresholds"]["bid_2"]:
                bid_n = 2
            elif strength >= self.rules["suit_thresholds"]["bid_1"]:
                bid_n = 1
            else:
                continue  # Too weak

            if bid_n > obs.current_high_bid:
                candidates.append((strength, bid_n, suit))

        # Evaluate HIGH contract (always, regardless of high/low card count)
        strength_high = score_hand_scalar(obs.hand, "high", None)
        if strength_high >= self.rules["high_low_thresholds"]["bid_8"]:
            bid_n = 8
        elif strength_high >= self.rules["high_low_thresholds"]["bid_7"]:
            bid_n = 7
        elif strength_high >= self.rules["high_low_thresholds"]["bid_6"]:
            bid_n = 6
        elif strength_high >= self.rules["high_low_thresholds"]["bid_5"]:
            bid_n = 5
        elif strength_high >= self.rules["high_low_thresholds"]["bid_4"]:
            bid_n = 4
        elif strength_high >= self.rules["high_low_thresholds"]["bid_3"]:
            bid_n = 3
        elif strength_high >= self.rules["high_low_thresholds"]["bid_2"]:
            bid_n = 2
        elif strength_high >= self.rules["high_low_thresholds"]["bid_1"]:
            bid_n = 1
        else:
            bid_n = 0

        if bid_n > obs.current_high_bid:
            candidates.append((strength_high, bid_n, "HIGH"))

        # Evaluate LOW contract (always, regardless of high/low card count)
        strength_low = score_hand_scalar(obs.hand, "low", None)
        if strength_low >= self.rules["high_low_thresholds"]["bid_8"]:
            bid_n = 8
        elif strength_low >= self.rules["high_low_thresholds"]["bid_7"]:
            bid_n = 7
        elif strength_low >= self.rules["high_low_thresholds"]["bid_6"]:
            bid_n = 6
        elif strength_low >= self.rules["high_low_thresholds"]["bid_5"]:
            bid_n = 5
        elif strength_low >= self.rules["high_low_thresholds"]["bid_4"]:
            bid_n = 4
        elif strength_low >= self.rules["high_low_thresholds"]["bid_3"]:
            bid_n = 3
        elif strength_low >= self.rules["high_low_thresholds"]["bid_2"]:
            bid_n = 2
        elif strength_low >= self.rules["high_low_thresholds"]["bid_1"]:
            bid_n = 1
        else:
            bid_n = 0

        if bid_n > obs.current_high_bid:
            candidates.append((strength_low, bid_n, "LOW"))

        # No valid candidates
        if not candidates:
            return None

        # Pick best candidate (highest strength, break ties by highest bid, then alphabetically)
        best = max(candidates, key=lambda x: (x[0], x[1], x[2]))
        _, bid_n, contract = best

        return {"n": bid_n, "contract": contract}

    def to_artifact_dict(self, contract: str, seed: int = 42) -> Dict[str, Any]:
        """
        Convert model to bidding artifact format.

        Args:
            contract: The contract this model is trained for (NOTE: for heuristics, this is nominal)
            seed: Random seed for deterministic timestamp

        Returns:
            Artifact dictionary conforming to schema v1
        """
        created_at = (DETERMINISTIC_BASE_TIME + timedelta(seconds=seed)).isoformat()

        return {
            "schema_version": "1",
            "model_type": "heuristics_imitation_v1",
            "contract": contract,
            "model_params": self.rules,
            "metadata": {
                "created_at": created_at,
                "description": "Deterministic imitation of RanktheTank (v1 baseline)",
                "training_data": "synthetic observations",
                "training_seed": seed,
                "teacher_model": "RanktheTank",
            },
        }


def create_synthetic_observations_for_heuristics() -> List[BiddingObservation]:
    """
    Create synthetic bidding observations to train RanktheTank imitation.

    Creates diverse hands covering different contract preferences and strengths.

    Returns:
        List of synthetic BiddingObservation instances
    """
    from ..core.cards import Card

    # Create diverse hands covering different scenarios
    # Note: Bid Euchre uses T, J, Q, K, A ranks only
    test_hands = [
        # Strong spade hand
        [
            Card("S", "A"),
            Card("S", "K"),
            Card("S", "Q"),
            Card("H", "A"),
            Card("C", "A"),
        ],
        # Strong heart hand
        [
            Card("H", "A"),
            Card("H", "K"),
            Card("H", "J"),
            Card("D", "A"),
            Card("S", "K"),
        ],
        # Mixed weak hand
        [
            Card("C", "T"),
            Card("D", "T"),
            Card("H", "T"),
            Card("S", "T"),
            Card("C", "J"),
        ],
        # High cards (good for HIGH)
        [
            Card("S", "A"),
            Card("H", "K"),
            Card("D", "Q"),
            Card("C", "A"),
            Card("H", "Q"),
        ],
        # Low cards (good for LOW)
        [
            Card("S", "J"),
            Card("H", "T"),
            Card("D", "J"),
            Card("C", "T"),
            Card("S", "T"),
        ],
        # Balanced medium strength
        [
            Card("S", "K"),
            Card("S", "Q"),
            Card("H", "T"),
            Card("C", "A"),
            Card("C", "J"),
        ],
    ]

    observations = []
    for hand in test_hands:
        for current_high_bid in range(0, 11):  # 0-10 inclusive
            for seat in range(4):
                for dealer_seat in range(4):
                    obs = BiddingObservation(
                        hand=hand,
                        seat=seat,
                        dealer_seat=dealer_seat,
                        current_high_bid=current_high_bid,
                    )
                    observations.append(obs)

    return observations


def train_heuristics_model(contract: str = "S") -> HeuristicsModel:
    """
    Train a deterministic model to imitate RanktheTank.

    Args:
        contract: Contract to train for (nominal; heuristics evaluates all contracts)

    Returns:
        Trained HeuristicsModel instance
    """
    # Create synthetic observations covering diverse bidding scenarios
    observations = create_synthetic_observations_for_heuristics()

    # Initialize model
    model = HeuristicsModel()

    # "Train" by validating that our model matches RanktheTank
    teacher = RanktheTank()

    for obs in observations:
        teacher_action = teacher.choose_bid(obs)
        model_prediction = model.predict_bid(obs)

        # Convert teacher action to dict format
        if teacher_action.is_pass():
            teacher_dict = None
        else:
            teacher_dict = {"n": teacher_action.n, "contract": teacher_action.contract}

        # Validate that model matches teacher
        if teacher_dict != model_prediction:
            raise ValueError(
                f"Model prediction {model_prediction} does not match "
                f"teacher action {teacher_dict} for hand={obs.hand}, current_high_bid={obs.current_high_bid}"
            )

    return model


def train_teacher_model(teacher: str, contract: str = "S") -> Any:
    """
    Train a model to imitate the specified teacher.

    Args:
        teacher: Teacher type ("strict_raiser", "heuristics", or "fiveheadfred")
        contract: Contract to train for

    Returns:
        Trained model instance
    """
    if teacher == "strict_raiser":
        return train_strict_raiser_model(contract)
    elif teacher == "heuristics":
        return train_heuristics_model(contract)
    elif teacher == "fiveheadfred":
        return train_fiveheadfred_model(contract)
    else:
        raise ValueError(f"Unknown teacher type: {teacher}")


def train_and_save_model(
    contract: str = "S",
    output_path: Optional[str] = None,
    seed: int = 42,
    teacher: str = "strict_raiser",
) -> Dict[str, Any]:
    """
    Train model and save as bidding artifact.

    Args:
        contract: Contract to train for
        output_path: Path to save artifact (optional)
        seed: Random seed for reproducibility
        teacher: Teacher type ("strict_raiser", "heuristics", or "fiveheadfred")

    Returns:
        Artifact dictionary
    """
    # Train the model
    model = train_teacher_model(teacher, contract)

    # Create artifact
    artifact = model.to_artifact_dict(contract, seed)

    # Validate artifact
    validate_artifact(artifact)

    # Save if path provided
    if output_path:
        artifact_path = output_path
        if not os.path.dirname(artifact_path):
            artifact_path = os.path.join(".", artifact_path)
        dump_artifact(artifact, artifact_path)

    return artifact
