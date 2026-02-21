"""Tests for offensive/defensive architecture extension (R5a).

Covers backward compatibility with flat artifacts, off/def model loading,
bid generation, detection logic, inconsistency detection, and training.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from bid_euchre.strategy.bidding import BiddingObservation, HybridOLSaBidder


def _make_flat_artifact(tmp_path: Path) -> str:
    """Create a standard flat (pre-R5) hybrid_olsa_v1 artifact."""
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": "r0",
        "payoff_model": {
            "suit": {
                "weights": [0.5, 0.3, 0.2],
                "bias": 3.5,
                "feature_names": ["bowers", "trump_count", "offsuit_aces"],
            },
            "high": {
                "weights": [0.8],
                "bias": 2.5,
                "feature_names": ["offsuit_aces"],
            },
            "low": {
                "weights": [0.7],
                "bias": 2.3,
                "feature_names": ["offsuit_tens_count"],
            },
        },
        "residual_variance": {"suit": 2.5, "high": 1.8, "low": 1.9},
        "risk_lambda": 0.0,
        "context_features": [],
        "training_seed": 42,
        "training_run_id": "test_run",
        "split_type": "three_way",
        "frozen_at": None,
        "artifact_sha256": None,
    }
    path = tmp_path / "flat_artifact.json"
    path.write_text(json.dumps(artifact, indent=2))
    return str(path)


def _make_offdef_artifact(tmp_path: Path) -> str:
    """Create an offensive/defensive (R5) hybrid_olsa_v1 artifact."""
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": "r5",
        "payoff_model": {
            "suit": {
                "offensive": {
                    "weights": [0.6, 0.35, 0.25],
                    "bias": 3.8,
                    "feature_names": ["bowers", "trump_count", "offsuit_aces"],
                },
                "defensive": {
                    "weights": [0.4, 0.25, 0.15],
                    "bias": 2.9,
                    "feature_names": ["bowers", "trump_count", "offsuit_aces"],
                },
            },
            "high": {
                "offensive": {
                    "weights": [0.9],
                    "bias": 2.8,
                    "feature_names": ["offsuit_aces"],
                },
                "defensive": {
                    "weights": [0.7],
                    "bias": 2.2,
                    "feature_names": ["offsuit_aces"],
                },
            },
            "low": {
                "offensive": {
                    "weights": [0.8],
                    "bias": 2.5,
                    "feature_names": ["offsuit_tens_count"],
                },
                "defensive": {
                    "weights": [0.6],
                    "bias": 2.0,
                    "feature_names": ["offsuit_tens_count"],
                },
            },
        },
        "residual_variance": {
            "suit": {"offensive": 2.1, "defensive": 2.9},
            "high": {"offensive": 1.6, "defensive": 2.0},
            "low": {"offensive": 1.7, "defensive": 2.1},
        },
        "risk_lambda": 0.0,
        "context_features": [],
        "training_seed": 42,
        "training_run_id": "test_run",
        "split_type": "three_way",
        "frozen_at": None,
        "artifact_sha256": None,
    }
    path = tmp_path / "offdef_artifact.json"
    path.write_text(json.dumps(artifact, indent=2))
    return str(path)


def _make_inconsistent_artifact(tmp_path: Path) -> str:
    """Create artifact with off/def in payoff_model but flat in residual_variance."""
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": "r5",
        "payoff_model": {
            "suit": {
                "offensive": {
                    "weights": [0.6],
                    "bias": 3.0,
                    "feature_names": ["bowers"],
                },
                "defensive": {
                    "weights": [0.4],
                    "bias": 2.0,
                    "feature_names": ["bowers"],
                },
            },
        },
        "residual_variance": {"suit": 2.5},
        "risk_lambda": 0.0,
        "context_features": [],
        "training_seed": 42,
        "training_run_id": "test_run",
        "split_type": "three_way",
        "frozen_at": None,
        "artifact_sha256": None,
    }
    path = tmp_path / "inconsistent_artifact.json"
    path.write_text(json.dumps(artifact, indent=2))
    return str(path)


def test_flat_model_still_works(tmp_path):
    """Pre-R5 flat artifact loads and produces bids (backward compatibility)."""
    path = _make_flat_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)
    assert not bidder._has_offdef
    assert "suit" in bidder.models

    from bid_euchre.core.cards import Card

    hand = [Card("H", "A")] * 10
    obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
    action = bidder.choose_bid(obs)
    # Should produce a valid action (either bid or pass)
    assert action.is_pass() or action.n >= 3


def test_offdef_model_loads(tmp_path):
    """R5 off/def artifact loads successfully."""
    path = _make_offdef_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)
    assert bidder._has_offdef
    assert "suit" in bidder.models
    assert "offensive" in bidder.models["suit"]
    assert "defensive" in bidder.models["suit"]


def test_offdef_model_produces_bids(tmp_path):
    """R5 off/def artifact produces non-trivial bids."""
    path = _make_offdef_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    from bid_euchre.core.cards import Card

    hand = [Card("H", "A")] * 10
    obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
    action = bidder.choose_bid(obs)
    # Should produce a valid action
    assert action.is_pass() or action.n >= 3


def test_offdef_detection_correct(tmp_path):
    """_has_offdef flag set properly for both flat and off/def artifacts."""
    flat_path = _make_flat_artifact(tmp_path)
    offdef_path = _make_offdef_artifact(tmp_path)

    flat_bidder = HybridOLSaBidder(flat_path)
    offdef_bidder = HybridOLSaBidder(offdef_path)

    assert not flat_bidder._has_offdef
    assert offdef_bidder._has_offdef


def test_inconsistent_structure_raises(tmp_path):
    """Mismatched off/def between payoff_model and residual_variance raises ValueError."""
    path = _make_inconsistent_artifact(tmp_path)
    with pytest.raises(ValueError, match="Inconsistent off/def"):
        HybridOLSaBidder(path)


def test_declaring_param_routes_correctly(tmp_path):
    """_predict with declaring=True uses offensive model, False uses defensive."""
    path = _make_offdef_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    # The offensive and defensive models have different weights/biases
    # so predictions should differ for the same features
    features = {"bowers": 1.0, "trump_count": 5.0, "offsuit_aces": 2.0}

    mu_off = bidder._predict("suit", features, declaring=True)
    mu_def = bidder._predict("suit", features, declaring=False)

    # They should be different (different weights and biases)
    assert mu_off != mu_def
    # Offensive should predict higher (bias 3.8 vs 2.9, higher weights)
    assert mu_off > mu_def


def test_get_sigma_routes_correctly(tmp_path):
    """_get_sigma routes to correct variance by declaring context."""
    path = _make_offdef_artifact(tmp_path)
    bidder = HybridOLSaBidder(path)

    sigma_off = bidder._get_sigma("suit", declaring=True)
    sigma_def = bidder._get_sigma("suit", declaring=False)

    # offensive variance = 2.1, defensive = 2.9
    assert sigma_off == pytest.approx(math.sqrt(2.1))
    assert sigma_def == pytest.approx(math.sqrt(2.9))
    assert sigma_off < sigma_def  # offensive has lower variance


def test_training_offdef_produces_submodels(tmp_path):
    """Training with offensive_defensive=True produces nested sub-models."""
    import pandas as pd

    from bid_euchre.models.train_hybrid_olsa import _train_arm
    from bid_euchre.models.train_olsa import CONTRACT_FEATURES

    rng = np.random.RandomState(42)
    rows = []
    for i in range(200):
        for seat in range(4):
            rows.append(
                {
                    "hand_id": i,
                    "seat": seat,
                    "contract_type": "suit",
                    "tricks_won": 5.0 + rng.normal(0, 1.5),
                    "bowers": rng.randint(0, 3),
                    "trump_count": rng.randint(2, 8),
                    "offsuit_aces": rng.randint(0, 5),
                }
            )
    df = pd.DataFrame(rows)

    # Create a minimal parquet for source path reference
    parquet_path = str(tmp_path / "bidless.parquet")
    df.to_parquet(parquet_path)

    artifact, metrics, _ = _train_arm(
        df,
        CONTRACT_FEATURES,
        seed=42,
        source_run_id="test",
        source_parquet_path=parquet_path,
        split_type="two_way",
        output_dir=str(tmp_path),
        arm_name="test",
        offensive_defensive=True,
    )

    # The artifact's payoff_model should have nested structure
    # Note: only "suit" will be present since we only gave suit data
    if "suit" in artifact["payoff_model"]:
        suit_model = artifact["payoff_model"]["suit"]
        assert "offensive" in suit_model
        assert "defensive" in suit_model
        assert "weights" in suit_model["offensive"]
        assert "weights" in suit_model["defensive"]

    # residual_variance should also be nested
    if "suit" in artifact["residual_variance"]:
        suit_var = artifact["residual_variance"]["suit"]
        assert isinstance(suit_var, dict)
        assert "offensive" in suit_var
        assert "defensive" in suit_var
