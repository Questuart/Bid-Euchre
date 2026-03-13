"""Tests for R1.5 action-value bidding infrastructure.

Tests enumerate_legal_actions, extract_state_features, extract_action_features,
predict_ols, and ActionValueBidder.
"""

import json
import tempfile

import numpy as np
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    ACTION_FEATURE_NAMES,
    STATE_FEATURE_NAMES,
    ActionValueBidder,
    BidAction,
    BiddingObservation,
    enumerate_legal_actions,
    extract_action_features,
    extract_state_features,
    predict_ols,
)

# ── Fixtures ──────────────────────────────────────────────


def _make_hand() -> list[Card]:
    """Create a valid 10-card hand for testing.

    Uses valid Bid Euchre ranks (T, J, Q, K, A) and suits (C, D, H, S).
    """
    suits = ["C", "D", "H", "S"]
    ranks = ["T", "J", "Q", "K", "A"]
    cards = []
    for i, suit in enumerate(suits):
        for rank in ranks[i : i + 3]:
            cards.append(Card(rank=rank, suit=suit))
            if len(cards) == 10:
                return cards
    # Pad if needed
    while len(cards) < 10:
        cards.append(Card(rank="T", suit="C"))
    return cards[:10]


def _make_obs(
    current_high_bid: int = 0,
    seat: int = 1,
    dealer_seat: int = 0,
    allowed_contracts: tuple[str, ...] = ("C", "D", "H", "S", "HIGH", "LOW"),
    auction_transcript: tuple[dict, ...] = (),
) -> BiddingObservation:
    """Create a BiddingObservation for testing."""
    return BiddingObservation(
        hand=_make_hand(),
        seat=seat,
        dealer_seat=dealer_seat,
        current_high_bid=current_high_bid,
        allowed_contracts=allowed_contracts,
        auction_transcript=auction_transcript,
    )


def _make_mock_artifact(
    pass_bias: float = 0.0,
    suit_bias: float = 1.0,
    high_bias: float = 0.5,
    low_bias: float = 0.5,
) -> dict:
    """Create a minimal action_value_olsa_v1 artifact for testing.

    Uses zero coefficients with specified intercepts so predict_ols
    returns deterministic values for testing action selection.
    """
    n_state = len(STATE_FEATURE_NAMES)
    n_action = len(ACTION_FEATURE_NAMES)

    def _model(n_features: int, intercept: float) -> dict:
        return {
            "coefficients": [0.0] * n_features,
            "intercept": intercept,
            "feature_names": (
                STATE_FEATURE_NAMES + ACTION_FEATURE_NAMES
                if n_features == n_state + n_action
                else STATE_FEATURE_NAMES
            ),
            "r_squared": 0.10,
        }

    return {
        "schema_version": "action_value_olsa_v1",
        "models": {
            "suit": _model(n_state + n_action, suit_bias),
            "high": _model(n_state + n_action, high_bias),
            "low": _model(n_state + n_action, low_bias),
            "pass": _model(n_state, pass_bias),
        },
        "metadata": {
            "context_features": [
                "partner_bid_level",
                "partner_passed",
                "partner_suit_match",
            ],
            "arm": "full",
        },
    }


# ── enumerate_legal_actions ───────────────────────────────


class TestEnumerateLegalActions:
    def test_opening_has_61_actions(self):
        obs = _make_obs(current_high_bid=0)
        actions = enumerate_legal_actions(obs)
        assert len(actions) == 61  # 1 pass + 10 levels * 6 contracts

    def test_after_bid_5_has_31_actions(self):
        obs = _make_obs(current_high_bid=5)
        actions = enumerate_legal_actions(obs)
        assert len(actions) == 31  # 1 pass + 5 levels * 6 contracts

    def test_after_bid_10_only_pass(self):
        obs = _make_obs(current_high_bid=10)
        actions = enumerate_legal_actions(obs)
        assert len(actions) == 1
        assert actions[0].is_pass()

    def test_pass_is_first(self):
        obs = _make_obs(current_high_bid=0)
        actions = enumerate_legal_actions(obs)
        assert actions[0].is_pass()

    def test_ascending_order(self):
        obs = _make_obs(current_high_bid=0)
        actions = enumerate_legal_actions(obs)
        # Skip pass (index 0), check bids ascending by (n, contract_index)
        # Contract order follows allowed_contracts tuple, not alphabetical
        contract_order = {c: i for i, c in enumerate(obs.allowed_contracts)}
        bid_actions = actions[1:]
        for i in range(len(bid_actions) - 1):
            a, b = bid_actions[i], bid_actions[i + 1]
            a_key = (a.n, contract_order[a.contract])
            b_key = (b.n, contract_order[b.contract])
            assert a_key < b_key, f"Actions not in order: {a} before {b}"

    def test_custom_contracts(self):
        obs = _make_obs(current_high_bid=0, allowed_contracts=("HIGH", "LOW"))
        actions = enumerate_legal_actions(obs)
        # 1 pass + 10 levels * 2 contracts = 21
        assert len(actions) == 21
        # All bid actions should be HIGH or LOW
        for action in actions[1:]:
            assert action.contract in {"HIGH", "LOW"}

    def test_after_bid_9_has_7_actions(self):
        obs = _make_obs(current_high_bid=9)
        actions = enumerate_legal_actions(obs)
        assert len(actions) == 7  # 1 pass + 1 level * 6 contracts

    def test_all_actions_are_valid_bid_actions(self):
        obs = _make_obs(current_high_bid=3)
        actions = enumerate_legal_actions(obs)
        for action in actions:
            assert isinstance(action, BidAction)
            if not action.is_pass():
                assert action.n > obs.current_high_bid
                assert action.contract in obs.allowed_contracts


# ── predict_ols ───────────────────────────────────────────


class TestPredictOls:
    def test_basic_dot_product(self):
        model = {"coefficients": [1.0, 2.0, 3.0], "intercept": 0.5}
        features = np.array([1.0, 1.0, 1.0])
        result = predict_ols(model, features)
        assert result == pytest.approx(6.5)  # 1+2+3 + 0.5

    def test_no_intercept_defaults_to_zero(self):
        model = {"coefficients": [2.0, 3.0]}
        features = np.array([1.0, 1.0])
        result = predict_ols(model, features)
        assert result == pytest.approx(5.0)

    def test_returns_float(self):
        model = {"coefficients": [1.0], "intercept": 0.0}
        features = np.array([42.0])
        result = predict_ols(model, features)
        assert isinstance(result, float)


# ── extract_state_features ────────────────────────────────


class TestExtractStateFeatures:
    def test_shape_is_52(self):
        obs = _make_obs()
        features = extract_state_features(obs, "suit", "H")
        assert features.shape == (52,)

    def test_shape_matches_feature_names(self):
        obs = _make_obs()
        features = extract_state_features(obs, "high", None)
        assert features.shape == (len(STATE_FEATURE_NAMES),)

    def test_contract_indicators_suit(self):
        obs = _make_obs()
        features = extract_state_features(obs, "suit", "H")
        # is_high=0, is_low=0
        is_high_idx = STATE_FEATURE_NAMES.index("is_high")
        is_low_idx = STATE_FEATURE_NAMES.index("is_low")
        assert features[is_high_idx] == 0.0
        assert features[is_low_idx] == 0.0

    def test_contract_indicators_high(self):
        obs = _make_obs()
        features = extract_state_features(obs, "high", None)
        is_high_idx = STATE_FEATURE_NAMES.index("is_high")
        is_low_idx = STATE_FEATURE_NAMES.index("is_low")
        assert features[is_high_idx] == 1.0
        assert features[is_low_idx] == 0.0

    def test_contract_indicators_low(self):
        obs = _make_obs()
        features = extract_state_features(obs, "low", None)
        is_high_idx = STATE_FEATURE_NAMES.index("is_high")
        is_low_idx = STATE_FEATURE_NAMES.index("is_low")
        assert features[is_high_idx] == 0.0
        assert features[is_low_idx] == 1.0

    def test_none_contract_encoding(self):
        obs = _make_obs()
        features = extract_state_features(obs, "none", None)
        is_high_idx = STATE_FEATURE_NAMES.index("is_high")
        is_low_idx = STATE_FEATURE_NAMES.index("is_low")
        trump_c_idx = STATE_FEATURE_NAMES.index("trump_C")
        # "none" state: is_high=0, is_low=0, all trump dummies=0
        assert features[is_high_idx] == 0.0
        assert features[is_low_idx] == 0.0
        for i in range(4):
            assert features[trump_c_idx + i] == 0.0

    def test_trump_dummies_suit(self):
        obs = _make_obs()
        features = extract_state_features(obs, "suit", "D")
        trump_c_idx = STATE_FEATURE_NAMES.index("trump_C")
        assert features[trump_c_idx] == 0.0  # C
        assert features[trump_c_idx + 1] == 1.0  # D
        assert features[trump_c_idx + 2] == 0.0  # H
        assert features[trump_c_idx + 3] == 0.0  # S

    def test_seat_dummies_dealer(self):
        obs = _make_obs(seat=0, dealer_seat=0)
        features = extract_state_features(obs, "high", None)
        seat_1_idx = STATE_FEATURE_NAMES.index("seat_rel_1")
        # Dealer is reference → all seat dummies = 0
        assert features[seat_1_idx] == 0.0
        assert features[seat_1_idx + 1] == 0.0
        assert features[seat_1_idx + 2] == 0.0

    def test_seat_dummies_left_of_dealer(self):
        obs = _make_obs(seat=1, dealer_seat=0)
        features = extract_state_features(obs, "high", None)
        seat_1_idx = STATE_FEATURE_NAMES.index("seat_rel_1")
        assert features[seat_1_idx] == 1.0  # seat_rel_1
        assert features[seat_1_idx + 1] == 0.0  # seat_rel_2
        assert features[seat_1_idx + 2] == 0.0  # seat_rel_3

    def test_current_high_bid_encoded(self):
        obs = _make_obs(current_high_bid=7)
        features = extract_state_features(obs, "high", None)
        chb_idx = STATE_FEATURE_NAMES.index("current_high_bid")
        assert features[chb_idx] == 7.0

    def test_dtype_is_float64(self):
        obs = _make_obs()
        features = extract_state_features(obs, "suit", "C")
        assert features.dtype == np.float64


# ── extract_action_features ───────────────────────────────


class TestExtractActionFeatures:
    def test_shape(self):
        features = extract_action_features(5)
        assert features.shape == (2,)

    def test_values(self):
        features = extract_action_features(7)
        assert features[0] == pytest.approx(7.0)
        assert features[1] == pytest.approx(49.0)

    def test_bid_1(self):
        features = extract_action_features(1)
        assert features[0] == pytest.approx(1.0)
        assert features[1] == pytest.approx(1.0)


# ── ActionValueBidder ─────────────────────────────────────


class TestActionValueBidder:
    def _write_artifact(self, artifact: dict) -> str:
        """Write artifact to a temp file and return the path."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(artifact, f)
        f.close()
        return f.name

    def test_loads_valid_artifact(self):
        path = self._write_artifact(_make_mock_artifact())
        bidder = ActionValueBidder(artifact_path=path)
        assert bidder.name == "action_value"
        assert "suit" in bidder.models
        assert "high" in bidder.models
        assert "low" in bidder.models
        assert bidder.pass_model is not None

    def test_rejects_wrong_schema(self):
        artifact = _make_mock_artifact()
        artifact["schema_version"] = "hybrid_olsa_v1"
        path = self._write_artifact(artifact)
        with pytest.raises(ValueError, match="action_value_olsa_v1"):
            ActionValueBidder(artifact_path=path)

    def test_choose_bid_returns_valid_action(self):
        path = self._write_artifact(_make_mock_artifact())
        bidder = ActionValueBidder(artifact_path=path)
        obs = _make_obs(current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert isinstance(action, BidAction)

    def test_choose_bid_selects_highest_value(self):
        # Suit model has highest intercept (1.0) → should pick a suit bid
        path = self._write_artifact(
            _make_mock_artifact(
                pass_bias=-5.0, suit_bias=1.0, high_bias=0.5, low_bias=0.5
            )
        )
        bidder = ActionValueBidder(artifact_path=path)
        obs = _make_obs(current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        contract_type, _ = action.to_contract_tuple()
        assert contract_type == "suit"

    def test_choose_bid_pass_when_best(self):
        # Pass model has highest intercept → should pass
        path = self._write_artifact(
            _make_mock_artifact(
                pass_bias=10.0, suit_bias=-5.0, high_bias=-5.0, low_bias=-5.0
            )
        )
        bidder = ActionValueBidder(artifact_path=path)
        obs = _make_obs(current_high_bid=0)
        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_choose_bid_after_bid_10_must_pass(self):
        path = self._write_artifact(_make_mock_artifact())
        bidder = ActionValueBidder(artifact_path=path)
        obs = _make_obs(current_high_bid=10)
        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_context_features_loaded(self):
        path = self._write_artifact(_make_mock_artifact())
        bidder = ActionValueBidder(artifact_path=path)
        assert bidder.context_features == [
            "partner_bid_level",
            "partner_passed",
            "partner_suit_match",
        ]

    def test_choose_bid_respects_current_high_bid(self):
        # With high current bid, fewer actions available
        path = self._write_artifact(_make_mock_artifact(pass_bias=-10.0, suit_bias=5.0))
        bidder = ActionValueBidder(artifact_path=path)
        obs = _make_obs(current_high_bid=9)
        action = bidder.choose_bid(obs)
        if not action.is_pass():
            assert action.n == 10  # Only legal bid level

    def test_rejects_mismatched_feature_names(self):
        """feature_names validation catches reordered/missing features at load time."""
        artifact = _make_mock_artifact()
        # Scramble the suit model's feature_names
        artifact["models"]["suit"]["feature_names"] = ["wrong_feature"] * (
            len(STATE_FEATURE_NAMES) + len(ACTION_FEATURE_NAMES)
        )
        path = self._write_artifact(artifact)
        with pytest.raises(ValueError):
            ActionValueBidder(artifact_path=path)

    def test_rejects_mismatched_pass_feature_names(self):
        """Pass model feature_names validated separately (state-only, no action features)."""
        artifact = _make_mock_artifact()
        artifact["models"]["pass"]["feature_names"] = ["wrong"] * len(
            STATE_FEATURE_NAMES
        )
        path = self._write_artifact(artifact)
        with pytest.raises(ValueError, match="feature_names mismatch"):
            ActionValueBidder(artifact_path=path)

    def test_rejects_artifact_without_feature_names(self):
        """action_value_olsa_v1 requires feature_names — no legacy compat."""
        artifact = _make_mock_artifact()
        for model in artifact["models"].values():
            del model["feature_names"]
        path = self._write_artifact(artifact)
        with pytest.raises(ValueError, match="missing required 'feature_names'"):
            ActionValueBidder(artifact_path=path)


# ── Pass proxy encoding ───────────────────────────────────


class TestPassProxyEncoding:
    """Verify that pass ("none") encoding uses "high" proxy intentionally
    and produces the expected neutral indicator values."""

    def test_none_uses_high_hand_features(self):
        """Pass features match "high" hand features (no trump dependency)."""
        obs = _make_obs()
        none_features = extract_state_features(obs, "none", None)
        high_features = extract_state_features(obs, "high", None)

        # First 39 elements (hand features) should be identical
        np.testing.assert_array_equal(
            none_features[:39],
            high_features[:39],
            err_msg="Pass hand features should match 'high' proxy",
        )

    def test_none_indicators_all_zero(self):
        """Pass encoding zeroes all contract and trump indicators."""
        obs = _make_obs()
        features = extract_state_features(obs, "none", None)
        is_high_idx = STATE_FEATURE_NAMES.index("is_high")
        is_low_idx = STATE_FEATURE_NAMES.index("is_low")
        trump_c_idx = STATE_FEATURE_NAMES.index("trump_C")

        assert features[is_high_idx] == 0.0
        assert features[is_low_idx] == 0.0
        for i in range(4):
            assert features[trump_c_idx + i] == 0.0

    def test_none_differs_from_high_in_indicators(self):
        """Pass and high share hand features but differ in is_high indicator."""
        obs = _make_obs()
        none_features = extract_state_features(obs, "none", None)
        high_features = extract_state_features(obs, "high", None)
        is_high_idx = STATE_FEATURE_NAMES.index("is_high")

        assert none_features[is_high_idx] == 0.0
        assert high_features[is_high_idx] == 1.0


# ── Artifact Governance ─────────────────────────────────


class TestArtifactGovernance:
    def test_quarantined_artifact_rejected(self, tmp_path):
        """Quarantined artifacts should raise ValueError on load."""
        artifact = _make_mock_artifact()
        artifact["status"] = "quarantined"

        path = tmp_path / "quarantined.json"
        path.write_text(json.dumps(artifact))

        with pytest.raises(ValueError, match="quarantined"):
            ActionValueBidder(str(path))

    def test_active_artifact_accepted(self, tmp_path):
        """Explicit 'active' status should load normally."""
        artifact = _make_mock_artifact()
        artifact["status"] = "active"

        path = tmp_path / "active.json"
        path.write_text(json.dumps(artifact))

        # Should not raise
        bidder = ActionValueBidder(str(path))
        assert bidder is not None

    def test_no_status_field_accepted(self, tmp_path):
        """Missing status field defaults to 'active' (backward compatible)."""
        artifact = _make_mock_artifact()
        assert "status" not in artifact  # default mock has no status

        path = tmp_path / "no_status.json"
        path.write_text(json.dumps(artifact))

        bidder = ActionValueBidder(str(path))
        assert bidder is not None

    def test_low_r2_logs_warning(self, tmp_path, caplog):
        """Low R² triggers a warning log but still loads."""
        import logging

        artifact = _make_mock_artifact()
        # Set low R² on suit model
        artifact["models"]["suit"]["r_squared"] = 0.18

        path = tmp_path / "low_r2.json"
        path.write_text(json.dumps(artifact))

        with caplog.at_level(logging.WARNING, logger="bid_euchre.strategy.bidding"):
            bidder = ActionValueBidder(str(path))

        assert bidder is not None
        assert any("Low R²" in msg for msg in caplog.messages)
        assert any("suit" in msg for msg in caplog.messages)

    def test_high_r2_no_warning(self, tmp_path, caplog):
        """R² above threshold should not trigger warning."""
        import logging

        artifact = _make_mock_artifact()
        for family in ("suit", "high", "low"):
            artifact["models"][family]["r_squared"] = 0.55

        path = tmp_path / "good_r2.json"
        path.write_text(json.dumps(artifact))

        with caplog.at_level(logging.WARNING, logger="bid_euchre.strategy.bidding"):
            ActionValueBidder(str(path))

        assert not any("Low R²" in msg for msg in caplog.messages)
