"""
Deterministic bidding model training pipeline v1.

This module implements a minimal, deterministic imitation-learning training pipeline
that trains a simple model to imitate StrictRaiserBidder behavior.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..strategy.bidding import BiddingObservation, StrictRaiserBidder
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
            "contract": "S"  # Always bid Spades
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
                "contract": self.rules["initial_bid"]["contract"]
            }
        elif current_high_bid < self.rules["max_bid"]:
            return {
                "n": current_high_bid + self.rules["raise_increment"],
                "contract": self.rules["contract"]
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
                "teacher_model": "StrictRaiserBidder"
            }
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
    with open(path, 'r', encoding='utf-8') as f:
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
        Card("S", "K"), Card("S", "Q"), Card("H", "T"), Card("C", "A"), Card("C", "J")
    ]

    observations = []
    for current_high_bid in range(0, 11):  # 0-10 inclusive
        for seat in range(4):
            for dealer_seat in range(4):
                obs = BiddingObservation(
                    hand=dummy_hand,
                    seat=seat,
                    dealer_seat=dealer_seat,
                    current_high_bid=current_high_bid
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
            teacher_dict = {
                "n": teacher_action.n,
                "contract": teacher_action.contract
            }

        # Validate that model matches teacher
        if teacher_dict != model_prediction:
            raise ValueError(
                f"Model prediction {model_prediction} does not match "
                f"teacher action {teacher_dict} for current_high_bid={obs.current_high_bid}"
            )

    return model


def train_and_save_model(
    contract: str = "S",
    output_path: Optional[str] = None,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Train model and save as bidding artifact.

    Args:
        contract: Contract to train for
        output_path: Path to save artifact (optional)
        seed: Random seed for reproducibility (not used in deterministic model)

    Returns:
        Artifact dictionary
    """
    # Train the model
    model = train_strict_raiser_model(contract)

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
