"""
Unit tests for OLSaBidder.
"""

import json

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    BiddingObservation,
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

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
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

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
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

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
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

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
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
        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=4
        )
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
