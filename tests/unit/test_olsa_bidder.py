"""
Unit tests for OLSaBidder.
"""

import json

import numpy as np
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    BiddingObservation,
    HybridOLSaBidder,
    OLSaBidder,
)


def _make_artifact(tmp_path, models=None):
    """Create a minimal OLSa artifact for testing."""
    if models is None:
        models = {
            "suit": {
                "weights": [1.0, 0.5, 0.5],
                "bias": 0.0,
                "feature_names": ["bowers", "trump_count", "offsuit_aces"],
            },
            "high": {
                "weights": [1.0],
                "bias": 0.0,
                "feature_names": ["offsuit_aces"],
            },
            "low": {
                "weights": [1.0],
                "bias": 0.0,
                "feature_names": ["offsuit_tens_count"],
            },
        }

    artifact = {
        "schema_version": "1",
        "artifact_type": "olsa_v1",
        "models": models,
        "metadata": {
            "training_seed": 42,
            "canonical_run_id": "test",
            "git_sha": "test",
            "training_metrics": {},
        },
    }

    path = tmp_path / "olsa_v1.json"
    with open(path, "w") as f:
        json.dump(artifact, f)
    return str(path)


def _make_hybrid_artifact_flat(tmp_path, filename="hybrid_flat.json"):
    """Create a hybrid_olsa_v1 artifact with flat (no off/def) structure."""
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": "r0",
        "payoff_model": {
            "suit": {
                "weights": [1.0, 0.5, 0.5],
                "bias": 0.0,
                "feature_names": ["bowers", "trump_count", "offsuit_aces"],
            },
            "high": {
                "weights": [1.0],
                "bias": 0.0,
                "feature_names": ["offsuit_aces"],
            },
            "low": {
                "weights": [1.0],
                "bias": 0.0,
                "feature_names": ["offsuit_tens_count"],
            },
        },
        "residual_variance": {"suit": 2.5, "high": 1.8, "low": 1.9},
        "risk_lambda": 0.0,
        "context_features": [],
    }
    path = tmp_path / filename
    with open(path, "w") as f:
        json.dump(artifact, f)
    return str(path)


def _make_hybrid_artifact_offdef(tmp_path, filename="hybrid_offdef.json"):
    """Create a hybrid_olsa_v1 artifact with offensive/defensive sub-models."""
    artifact = {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": "r0",
        "payoff_model": {
            "suit": {
                "offensive": {
                    "weights": [1.0, 0.5, 0.5],
                    "bias": 0.0,
                    "feature_names": ["bowers", "trump_count", "offsuit_aces"],
                },
                "defensive": {
                    "weights": [0.3, 0.2, 0.1],
                    "bias": 1.0,
                    "feature_names": ["bowers", "trump_count", "offsuit_aces"],
                },
            },
            "high": {
                "offensive": {
                    "weights": [1.0],
                    "bias": 0.0,
                    "feature_names": ["offsuit_aces"],
                },
                "defensive": {
                    "weights": [0.5],
                    "bias": 0.5,
                    "feature_names": ["offsuit_aces"],
                },
            },
            "low": {
                "offensive": {
                    "weights": [1.0],
                    "bias": 0.0,
                    "feature_names": ["offsuit_tens_count"],
                },
                "defensive": {
                    "weights": [0.4],
                    "bias": 0.3,
                    "feature_names": ["offsuit_tens_count"],
                },
            },
        },
        "residual_variance": {
            "suit": {"offensive": 2.5, "defensive": 3.0},
            "high": {"offensive": 1.8, "defensive": 2.0},
            "low": {"offensive": 1.9, "defensive": 2.1},
        },
        "risk_lambda": 0.0,
        "context_features": [],
    }
    path = tmp_path / filename
    with open(path, "w") as f:
        json.dump(artifact, f)
    return str(path)


class TestOLSaBidder:
    """Test OLSaBidder."""

    def test_loads_artifact(self, tmp_path):
        """Test loading a valid OLSa artifact."""
        path = _make_artifact(tmp_path)
        bidder = OLSaBidder(path)
        assert bidder.name == "olsa"
        assert "suit" in bidder.models
        assert "high" in bidder.models
        assert "low" in bidder.models

    def test_strong_suit_hand_bids(self, tmp_path):
        """Test a strong suit hand produces a bid."""
        path = _make_artifact(tmp_path)
        bidder = OLSaBidder(path)

        # 2 bowers + 4 trump + 1 offsuit ace
        # predicted = 1.0*2 + 0.5*4 + 0.5*1 = 4.5 → bid 4
        hand = [
            Card("H", "J"),  # Right bower
            Card("D", "J"),  # Left bower
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "A"),  # Offsuit ace
        ]

        obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.n == 4
        assert action.contract == "H"

    def test_weak_hand_passes(self, tmp_path):
        """Test a weak hand passes."""
        path = _make_artifact(tmp_path)
        bidder = OLSaBidder(path)

        # No bowers, 2 trump, no offsuit aces
        # predicted = 0 + 0.5*2 + 0 = 1.0 → bid 1 < 3, pass
        hand = [
            Card("S", "K"),
            Card("S", "Q"),
            Card("H", "K"),
            Card("D", "Q"),
            Card("C", "T"),
        ]

        obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_high_contract_with_aces(self, tmp_path):
        """Test HIGH contract with enough aces."""
        path = _make_artifact(tmp_path)
        bidder = OLSaBidder(path)

        # 4 aces → predicted_high = 1.0 * 4 = 4.0 → bid 4
        hand = [
            Card("S", "A"),
            Card("H", "A"),
            Card("D", "A"),
            Card("C", "A"),
            Card("S", "K"),
            Card("H", "K"),
            Card("D", "K"),
            Card("C", "K"),
            Card("S", "Q"),
            Card("H", "Q"),
        ]

        obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        # With 4 aces, HIGH should be a strong candidate
        # (suit contracts also evaluated — the best wins)

    def test_low_contract_with_tens(self, tmp_path):
        """Test LOW contract with enough tens."""
        # Use weights that make LOW the only viable contract
        models = {
            "suit": {
                "weights": [0.0, 0.0, 0.0],
                "bias": 0.0,
                "feature_names": ["bowers", "trump_count", "offsuit_aces"],
            },
            "high": {
                "weights": [0.0],
                "bias": 0.0,
                "feature_names": ["offsuit_aces"],
            },
            "low": {
                "weights": [1.0],
                "bias": 0.0,
                "feature_names": ["offsuit_tens_count"],
            },
        }
        path = _make_artifact(tmp_path, models=models)
        bidder = OLSaBidder(path)

        # 4 tens → predicted_low = 1.0 * 4 = 4.0 → bid 4
        hand = [
            Card("S", "T"),
            Card("H", "T"),
            Card("D", "T"),
            Card("C", "T"),
            Card("S", "K"),
            Card("H", "K"),
            Card("D", "K"),
            Card("C", "K"),
            Card("S", "Q"),
            Card("H", "Q"),
        ]

        obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "LOW"
        assert action.n == 4

    def test_strict_increasing_compliance(self, tmp_path):
        """Test that bids comply with strict-increasing rule."""
        path = _make_artifact(tmp_path)
        bidder = OLSaBidder(path)

        # Strong hand that would normally bid 4
        hand = [
            Card("H", "J"),
            Card("D", "J"),
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "A"),
        ]

        # Current high bid is 4, must bid higher or pass
        obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=4)
        action = bidder.choose_bid(obs)
        # predicted=4.5, floor=4, but 4 not > 4, so pass
        assert action.is_pass()

    def test_invalid_artifact_type(self, tmp_path):
        """Test that wrong artifact type raises ValueError."""
        artifact = {
            "schema_version": "1",
            "artifact_type": "wrong_type",
            "models": {},
            "metadata": {},
        }
        path = tmp_path / "wrong.json"
        with open(path, "w") as f:
            json.dump(artifact, f)

        try:
            OLSaBidder(str(path))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "olsa_v1" in str(e)

    def test_config_registration(self, tmp_path):
        """Test OLSaBidder can be created via BiddingPolicyConfig."""
        from bid_euchre.experiments.config import BiddingPolicyConfig

        path = _make_artifact(tmp_path)
        config = BiddingPolicyConfig(
            name="test_olsa",
            class_name="OLSaBidder",
            params={"artifact_path": path},
        )
        bidder = config.create_bidding_policy()
        assert isinstance(bidder, OLSaBidder)
        assert bidder.name == "test_olsa"


class TestOLSaBidderDualFormat:
    """Test OLSaBidder loading hybrid_olsa_v1 artifacts."""

    def test_loads_hybrid_flat(self, tmp_path):
        """OLSaBidder loads flat hybrid_olsa_v1 artifact."""
        path = _make_hybrid_artifact_flat(tmp_path)
        bidder = OLSaBidder(path)
        assert "suit" in bidder.models
        assert "high" in bidder.models
        assert "low" in bidder.models

    def test_loads_hybrid_offdef(self, tmp_path):
        """OLSaBidder loads off/def hybrid_olsa_v1, using offensive sub-model."""
        path = _make_hybrid_artifact_offdef(tmp_path)
        bidder = OLSaBidder(path)
        assert "suit" in bidder.models
        # Verify it used offensive weights (1.0, 0.5, 0.5), not defensive (0.3, 0.2, 0.1)
        np.testing.assert_array_almost_equal(
            bidder.models["suit"]["weights"], [1.0, 0.5, 0.5]
        )
        assert bidder.models["suit"]["bias"] == 0.0

    def test_hybrid_flat_matches_olsa_v1_predictions(self, tmp_path):
        """Flat hybrid and olsa_v1 produce identical predictions for same coefficients."""
        olsa_path = _make_artifact(tmp_path)
        hybrid_path = _make_hybrid_artifact_flat(tmp_path)
        olsa_bidder = OLSaBidder(olsa_path)
        hybrid_bidder = OLSaBidder(hybrid_path, name="olsa_from_hybrid")

        features = {"bowers": 2.0, "trump_count": 4.0, "offsuit_aces": 1.0}
        olsa_pred = olsa_bidder._predict("suit", features)
        hybrid_pred = hybrid_bidder._predict("suit", features)
        assert abs(olsa_pred - hybrid_pred) <= 1e-12

    def test_offdef_uses_offensive_predictions(self, tmp_path):
        """Off/def hybrid uses offensive sub-model for predictions."""
        path = _make_hybrid_artifact_offdef(tmp_path)
        bidder = OLSaBidder(path)
        # offensive: weights=[1.0, 0.5, 0.5], bias=0.0
        features = {"bowers": 2.0, "trump_count": 3.0, "offsuit_aces": 1.0}
        predicted = bidder._predict("suit", features)
        expected = 2.0 * 1.0 + 3.0 * 0.5 + 1.0 * 0.5  # = 4.0
        assert abs(predicted - expected) <= 1e-12

    def test_coefficient_parity_with_hybrid_bidder(self, tmp_path):
        """OLSaBidder._predict matches HybridOLSaBidder._predict for declaring=True.

        This is the core C33 ablation invariant: same coefficients, same linear
        prediction. The only difference is the decision layer (floor vs Gaussian EV).
        """
        # Use flat hybrid artifact (no off/def) for direct comparison
        path = _make_hybrid_artifact_flat(tmp_path)
        olsa_bidder = OLSaBidder(path)
        hybrid_bidder = HybridOLSaBidder(path)

        # Per-contract-family feature dicts (each model has different feature_names)
        features_by_cf = {
            "suit": {"bowers": 1.0, "trump_count": 5.0, "offsuit_aces": 2.0},
            "high": {"offsuit_aces": 3.0},
            "low": {"offsuit_tens_count": 4.0},
        }
        for cf, features in features_by_cf.items():
            olsa_pred = olsa_bidder._predict(cf, features)
            hybrid_pred = hybrid_bidder._predict(cf, features, declaring=True)
            assert abs(olsa_pred - hybrid_pred) <= 1e-12, (
                f"Coefficient parity broken for {cf}: "
                f"OLSa={olsa_pred}, Hybrid={hybrid_pred}"
            )

    def test_coefficient_parity_offdef_with_hybrid_bidder(self, tmp_path):
        """Parity holds for off/def artifacts: OLSa uses offensive, Hybrid uses declaring=True."""
        path = _make_hybrid_artifact_offdef(tmp_path)
        olsa_bidder = OLSaBidder(path)
        hybrid_bidder = HybridOLSaBidder(path)

        features_by_cf = {
            "suit": {"bowers": 1.0, "trump_count": 5.0, "offsuit_aces": 2.0},
            "high": {"offsuit_aces": 3.0},
            "low": {"offsuit_tens_count": 4.0},
        }
        for cf, features in features_by_cf.items():
            olsa_pred = olsa_bidder._predict(cf, features)
            hybrid_pred = hybrid_bidder._predict(cf, features, declaring=True)
            assert abs(olsa_pred - hybrid_pred) <= 1e-12, (
                f"Coefficient parity broken for {cf}: "
                f"OLSa={olsa_pred}, Hybrid={hybrid_pred}"
            )

    def test_strong_hand_bids_from_hybrid(self, tmp_path):
        """OLSaBidder loaded from hybrid_olsa_v1 bids correctly on strong hands."""
        path = _make_hybrid_artifact_offdef(tmp_path)
        bidder = OLSaBidder(path)

        # 2 bowers + 4 trump + 1 offsuit ace
        # offensive: 1.0*2 + 0.5*4 + 0.5*1 = 4.5 → bid 4
        hand = [
            Card("H", "J"),
            Card("D", "J"),
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "A"),
        ]
        obs = BiddingObservation(hand=hand, seat=0, dealer_seat=3, current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.n == 4

    def test_error_message_includes_both_formats(self, tmp_path):
        """Error message mentions both accepted artifact types."""
        artifact = {"artifact_type": "unknown_v9", "models": {}}
        path = tmp_path / "bad.json"
        with open(path, "w") as f:
            json.dump(artifact, f)

        with pytest.raises(ValueError, match="olsa_v1.*hybrid_olsa_v1"):
            OLSaBidder(str(path))
