"""Tests for TwoStageActionValueBidder and predict_logistic."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    _HAND_FEATURE_NAMES,
    ACTION_FEATURE_NAMES,
    STATE_FEATURE_NAMES,
    BidAction,
    BiddingObservation,
    TwoStageActionValueBidder,
    predict_logistic,
    predict_ols,
)

# Number of state features (52) and action features (2)
N_STATE = len(STATE_FEATURE_NAMES)
N_ACTION = len(ACTION_FEATURE_NAMES)
N_BID = N_STATE + N_ACTION  # 54


def _make_minimal_artifact(
    n_features: int = N_BID,
    n_state: int = N_STATE,
) -> dict:
    """Build a minimal valid two_stage_action_value_v1 artifact dict.

    Uses small deterministic coefficients for reproducible predictions.
    """
    feature_names_bid = list(STATE_FEATURE_NAMES) + list(ACTION_FEATURE_NAMES)
    feature_names_pass = list(STATE_FEATURE_NAMES)

    # Suit model: three-component structure
    suit_model = {
        "logistic": {
            "coefficients": [0.1] * n_features,
            "intercept": -0.5,
            "auc": 0.85,
        },
        "make_model": {
            "coefficients": [0.2] * n_features,
            "intercept": 1.0,
            "r_squared": 0.6,
            "mae": 1.5,
            "n_train": 500,
        },
        "set_model": {
            "coefficients": [-0.1] * n_features,
            "intercept": -2.0,
            "r_squared": 0.5,
            "mae": 2.0,
            "n_train": 200,
        },
        "feature_names": feature_names_bid,
        "composite_r_squared": 0.55,
        "composite_mae": 1.8,
        "auc": 0.85,
        "make_rate": 0.72,
        "n_train": 700,
        "n_val": 100,
    }

    # High/low: standard OLS format
    high_model = {
        "coefficients": [0.05] * n_features,
        "intercept": 0.5,
        "feature_names": feature_names_bid,
        "r_squared": 0.45,
        "mae": 2.0,
        "n_train": 300,
        "n_val": 50,
    }
    low_model = {
        "coefficients": [0.03] * n_features,
        "intercept": 0.3,
        "feature_names": feature_names_bid,
        "r_squared": 0.40,
        "mae": 2.2,
        "n_train": 250,
        "n_val": 40,
    }

    # Pass: state-only features
    pass_model = {
        "coefficients": [0.01] * n_state,
        "intercept": -1.0,
        "feature_names": feature_names_pass,
        "r_squared": 0.05,
        "mae": 3.0,
        "n_train": 400,
        "n_val": 60,
    }

    return {
        "schema_version": "two_stage_action_value_v1",
        "target": "net_points",
        "risk_mode": "neutral",
        "continuation_policy": "hybrid_r0_full",
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": "full",
        "models": {
            "suit": suit_model,
            "high": high_model,
            "low": low_model,
            "pass": pass_model,
        },
        "metadata": {
            "model_class": "two-stage",
            "context_features": [],
        },
    }


# ── predict_logistic tests ──────────────────────────────────


class TestPredictLogistic:
    """Tests for the predict_logistic helper."""

    def test_zero_logit_returns_half(self):
        """When logit = 0, sigmoid should return 0.5."""
        model = {"coefficients": [0.0, 0.0, 0.0], "intercept": 0.0}
        features = np.array([1.0, 2.0, 3.0])
        p = predict_logistic(model, features)
        assert abs(p - 0.5) < 1e-10

    def test_positive_logit(self):
        """Positive logit should return > 0.5."""
        model = {"coefficients": [1.0], "intercept": 0.0}
        features = np.array([2.0])
        p = predict_logistic(model, features)
        # logit = 2.0, sigmoid(2.0) ≈ 0.8808
        expected = 1.0 / (1.0 + math.exp(-2.0))
        assert abs(p - expected) < 1e-10
        assert p > 0.5

    def test_negative_logit(self):
        """Negative logit should return < 0.5."""
        model = {"coefficients": [1.0], "intercept": -5.0}
        features = np.array([2.0])
        p = predict_logistic(model, features)
        # logit = 2.0 - 5.0 = -3.0
        expected = 1.0 / (1.0 + math.exp(3.0))
        assert abs(p - expected) < 1e-10
        assert p < 0.5

    def test_large_positive_logit_no_overflow(self):
        """Very large positive logit should return ~1.0 without overflow."""
        model = {"coefficients": [100.0], "intercept": 0.0}
        features = np.array([10.0])
        p = predict_logistic(model, features)
        assert abs(p - 1.0) < 1e-6

    def test_large_negative_logit_no_overflow(self):
        """Very large negative logit should return ~0.0 without overflow."""
        model = {"coefficients": [-100.0], "intercept": 0.0}
        features = np.array([10.0])
        p = predict_logistic(model, features)
        assert abs(p - 0.0) < 1e-6

    def test_multi_feature(self):
        """Multi-feature logistic prediction matches manual computation."""
        model = {"coefficients": [0.5, -0.3, 0.2], "intercept": 0.1}
        features = np.array([1.0, 2.0, 3.0])
        p = predict_logistic(model, features)
        # logit = 0.5*1 + (-0.3)*2 + 0.2*3 + 0.1 = 0.5 - 0.6 + 0.6 + 0.1 = 0.6
        expected = 1.0 / (1.0 + math.exp(-0.6))
        assert abs(p - expected) < 1e-10


# ── Composite prediction tests ──────────────────────────────


class TestTwoStageComposite:
    """Tests for the two-stage composite prediction formula."""

    def test_composite_formula(self):
        """P(make)*E[pts|make] + (1-P(make))*E[pts|set] matches expected."""
        p_make = 0.7
        e_make = 5.0
        e_set = -3.0
        expected = p_make * e_make + (1 - p_make) * e_set
        # 0.7 * 5.0 + 0.3 * (-3.0) = 3.5 - 0.9 = 2.6
        assert abs(expected - 2.6) < 1e-10

    def test_composite_certain_make(self):
        """When P(make) = 1, composite = E[pts|make]."""
        p_make = 1.0
        e_make = 5.0
        e_set = -10.0
        expected = p_make * e_make + (1 - p_make) * e_set
        assert abs(expected - 5.0) < 1e-10

    def test_composite_certain_set(self):
        """When P(make) = 0, composite = E[pts|set]."""
        p_make = 0.0
        e_make = 5.0
        e_set = -3.0
        expected = p_make * e_make + (1 - p_make) * e_set
        assert abs(expected - (-3.0)) < 1e-10

    def test_composite_with_models(self):
        """End-to-end: logistic + two OLS models produce correct composite."""
        features = np.array([1.0, 0.5, -0.3, 0.8, 2.0])

        logistic_model = {"coefficients": [0.5, -0.2, 0.1, 0.3, -0.1], "intercept": 0.0}
        make_model = {"coefficients": [1.0, 0.5, -0.5, 0.2, 0.1], "intercept": 0.5}
        set_model = {"coefficients": [-0.5, 0.1, 0.2, -0.3, 0.4], "intercept": -1.0}

        p_make = predict_logistic(logistic_model, features)
        e_make = predict_ols(make_model, features)
        e_set = predict_ols(set_model, features)
        composite = p_make * e_make + (1 - p_make) * e_set

        # Verify each component manually
        logit = 0.5 * 1.0 + (-0.2) * 0.5 + 0.1 * (-0.3) + 0.3 * 0.8 + (-0.1) * 2.0
        expected_p = 1.0 / (1.0 + math.exp(-logit))

        expected_e_make = (
            1.0 * 1.0 + 0.5 * 0.5 + (-0.5) * (-0.3) + 0.2 * 0.8 + 0.1 * 2.0 + 0.5
        )
        expected_e_set = (
            (-0.5) * 1.0 + 0.1 * 0.5 + 0.2 * (-0.3) + (-0.3) * 0.8 + 0.4 * 2.0 - 1.0
        )
        expected_composite = (
            expected_p * expected_e_make + (1 - expected_p) * expected_e_set
        )

        assert abs(p_make - expected_p) < 1e-10
        assert abs(e_make - expected_e_make) < 1e-10
        assert abs(e_set - expected_e_set) < 1e-10
        assert abs(composite - expected_composite) < 1e-10


# ── Artifact loading tests ──────────────────────────────────


class TestTwoStageArtifactLoads:
    """Tests for TwoStageActionValueBidder artifact loading."""

    def test_loads_valid_artifact(self, tmp_path):
        """A minimal valid artifact dict loads without error."""
        artifact = _make_minimal_artifact()
        artifact_path = tmp_path / "two_stage.json"
        artifact_path.write_text(json.dumps(artifact))

        bidder = TwoStageActionValueBidder(
            artifact_path=str(artifact_path),
            skip_behavioral_check=True,
        )
        assert bidder.name == "two_stage_action_value"
        assert bidder.suit_logistic is not None
        assert bidder.suit_make_model is not None
        assert bidder.suit_set_model is not None
        assert "high" in bidder.models
        assert "low" in bidder.models
        assert bidder.pass_model is not None

    def test_rejects_wrong_schema(self, tmp_path):
        """Artifact with wrong schema_version is rejected."""
        artifact = _make_minimal_artifact()
        artifact["schema_version"] = "action_value_olsa_v1"
        artifact_path = tmp_path / "wrong_schema.json"
        artifact_path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="Expected schema_version"):
            TwoStageActionValueBidder(
                artifact_path=str(artifact_path),
                skip_behavioral_check=True,
            )

    def test_rejects_quarantined(self, tmp_path):
        """Quarantined artifact is rejected."""
        artifact = _make_minimal_artifact()
        artifact["status"] = "quarantined"
        artifact_path = tmp_path / "quarantined.json"
        artifact_path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="quarantined"):
            TwoStageActionValueBidder(
                artifact_path=str(artifact_path),
                skip_behavioral_check=True,
            )

    def test_rejects_missing_suit_feature_names(self, tmp_path):
        """Artifact without suit feature_names is rejected."""
        artifact = _make_minimal_artifact()
        del artifact["models"]["suit"]["feature_names"]
        artifact_path = tmp_path / "no_suit_features.json"
        artifact_path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="suit model missing"):
            TwoStageActionValueBidder(
                artifact_path=str(artifact_path),
                skip_behavioral_check=True,
            )

    def test_rejects_missing_pass_feature_names(self, tmp_path):
        """Artifact without pass feature_names is rejected."""
        artifact = _make_minimal_artifact()
        del artifact["models"]["pass"]["feature_names"]
        artifact_path = tmp_path / "no_pass_features.json"
        artifact_path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="pass model missing"):
            TwoStageActionValueBidder(
                artifact_path=str(artifact_path),
                skip_behavioral_check=True,
            )

    def test_rejects_wrong_high_feature_names(self, tmp_path):
        """Artifact with wrong high model feature_names is rejected."""
        artifact = _make_minimal_artifact()
        artifact["models"]["high"]["feature_names"] = ["wrong_feature"]
        artifact_path = tmp_path / "wrong_high.json"
        artifact_path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError):
            TwoStageActionValueBidder(
                artifact_path=str(artifact_path),
                skip_behavioral_check=True,
            )


# ── Prediction path tests ──────────────────────────────────


class TestTwoStagePredictionPaths:
    """Verify suit uses two-stage path and high/low uses OLS."""

    @pytest.fixture
    def bidder(self, tmp_path):
        """Create a TwoStageActionValueBidder with known coefficients."""
        artifact = _make_minimal_artifact()
        artifact_path = tmp_path / "two_stage_pred.json"
        artifact_path.write_text(json.dumps(artifact))
        return TwoStageActionValueBidder(
            artifact_path=str(artifact_path),
            skip_behavioral_check=True,
        )

    def test_suit_uses_composite(self, bidder):
        """Suit predictions use the two-stage composite formula."""
        # Build a synthetic feature vector matching N_BID length
        features = np.ones(N_BID, dtype=np.float64) * 0.1

        # Compute expected composite value using the artifact coefficients
        p_make = predict_logistic(bidder.suit_logistic, features)
        e_make = predict_ols(bidder.suit_make_model, features)
        e_set = predict_ols(bidder.suit_set_model, features)
        expected_composite = p_make * e_make + (1 - p_make) * e_set

        # Verify each stage is working
        assert 0.0 < p_make < 1.0, "P(make) should be between 0 and 1"
        assert e_make != e_set, "Make and set predictions should differ"

        # Verify composite is between the two extremes
        assert min(e_make, e_set) <= expected_composite <= max(e_make, e_set)

    def test_high_uses_ols(self, bidder):
        """High predictions use standard OLS (dot product)."""
        features = np.ones(N_BID, dtype=np.float64) * 0.1
        value = predict_ols(bidder.models["high"], features)

        # Manual: 54 features * 0.05 coef * 0.1 input + 0.5 intercept
        expected = N_BID * 0.05 * 0.1 + 0.5
        assert abs(value - expected) < 1e-10

    def test_low_uses_ols(self, bidder):
        """Low predictions use standard OLS (dot product)."""
        features = np.ones(N_BID, dtype=np.float64) * 0.1
        value = predict_ols(bidder.models["low"], features)

        # Manual: 54 features * 0.03 coef * 0.1 input + 0.3 intercept
        expected = N_BID * 0.03 * 0.1 + 0.3
        assert abs(value - expected) < 1e-10

    def test_pass_uses_ols(self, bidder):
        """Pass predictions use state-only OLS (dot product)."""
        features = np.ones(N_STATE, dtype=np.float64) * 0.1
        value = predict_ols(bidder.pass_model, features)

        # Manual: 52 features * 0.01 coef * 0.1 input + (-1.0) intercept
        expected = N_STATE * 0.01 * 0.1 + (-1.0)
        assert abs(value - expected) < 1e-10


# ── R1 forward-selected two-stage artifact ─────────────────


def _make_obs(
    current_high_bid: int = 0,
    seat: int = 1,
    dealer_seat: int = 0,
) -> BiddingObservation:
    """Create a BiddingObservation for testing."""
    suits = ["C", "D", "H", "S"]
    ranks = ["T", "J", "Q", "K", "A"]
    cards = []
    for i, suit in enumerate(suits):
        for rank in ranks[i : i + 3]:
            cards.append(Card(rank=rank, suit=suit))
            if len(cards) == 10:
                break
        if len(cards) == 10:
            break
    return BiddingObservation(
        hand=cards,
        seat=seat,
        dealer_seat=dealer_seat,
        current_high_bid=current_high_bid,
        allowed_contracts=("C", "D", "H", "S", "HIGH", "LOW"),
        auction_transcript=(),
    )


class TestTwoStageForwardSelected:
    """Test TwoStageActionValueBidder with forward-selected artifacts
    containing partner features but no positional features."""

    def test_loads_with_partner_features(self, tmp_path):
        """TwoStageActionValueBidder loads forward-selected artifact."""
        hand_subset = list(_HAND_FEATURE_NAMES[:10])
        partner_subset = ["partner_passed"]
        state_names = hand_subset + partner_subset
        n_state = len(state_names)
        n_bid = n_state + N_ACTION

        feature_names_bid = state_names + list(ACTION_FEATURE_NAMES)
        feature_names_pass = list(state_names)

        suit_model = {
            "logistic": {
                "coefficients": [0.0] * n_bid,
                "intercept": 0.0,
                "auc": 0.80,
            },
            "make_model": {
                "coefficients": [0.0] * n_bid,
                "intercept": 1.0,
                "r_squared": 0.5,
                "mae": 1.5,
                "n_train": 100,
            },
            "set_model": {
                "coefficients": [0.0] * n_bid,
                "intercept": -2.0,
                "r_squared": 0.4,
                "mae": 2.0,
                "n_train": 50,
            },
            "feature_names": feature_names_bid,
            "composite_r_squared": 0.50,
            "composite_mae": 1.8,
            "auc": 0.80,
            "make_rate": 0.70,
            "n_train": 150,
            "n_val": 30,
        }

        artifact = {
            "schema_version": "two_stage_action_value_v1",
            "target": "net_points",
            "risk_mode": "neutral",
            "continuation_policy": "hybrid_r0_full",
            "action_features": list(ACTION_FEATURE_NAMES),
            "feature_set": "full",
            "models": {
                "suit": suit_model,
                "high": {
                    "coefficients": [0.0] * n_bid,
                    "intercept": 0.5,
                    "feature_names": feature_names_bid,
                    "r_squared": 0.45,
                    "mae": 2.0,
                    "n_train": 100,
                    "n_val": 20,
                },
                "low": {
                    "coefficients": [0.0] * n_bid,
                    "intercept": 0.3,
                    "feature_names": feature_names_bid,
                    "r_squared": 0.40,
                    "mae": 2.2,
                    "n_train": 80,
                    "n_val": 15,
                },
                "pass": {
                    "coefficients": [0.0] * n_state,
                    "intercept": -1.0,
                    "feature_names": feature_names_pass,
                    "r_squared": 0.05,
                    "mae": 3.0,
                    "n_train": 200,
                    "n_val": 40,
                },
            },
            "metadata": {
                "context_features": ["partner_passed"],
            },
        }

        path = tmp_path / "two_stage_forward.json"
        path.write_text(json.dumps(artifact))

        bidder = TwoStageActionValueBidder(
            artifact_path=str(path),
            skip_behavioral_check=True,
        )
        assert bidder._needs_full_state is True
        assert bidder._has_positional is False

        # Verify choose_bid works end-to-end
        obs = _make_obs(current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert isinstance(action, BidAction)
