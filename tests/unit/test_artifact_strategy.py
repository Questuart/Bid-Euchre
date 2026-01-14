"""
Unit tests for ArtifactGreedyStrategy with teacher artifact support.

Tests verify that ArtifactGreedyStrategy can load and execute teacher-style
artifacts (strict_raiser_imitation_v1, heuristics_imitation_v1) deterministically.
"""


import pytest

from bid_euchre.core.cards import Card
from bid_euchre.models.bidding_artifact import dump_artifact
from bid_euchre.strategy.artifact_strategy import ArtifactGreedyStrategy


class TestArtifactGreedyStrategyTeacherArtifacts:
    """Test ArtifactGreedyStrategy with teacher artifacts."""

    def test_load_strict_raiser_artifact(self, tmp_path):
        """Test loading strict_raiser_imitation_v1 artifact."""
        artifact = {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": "S",
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 10,
                "contract": "S"
            },
            "metadata": {
                "description": "Test strict raiser artifact"
            }
        }

        artifact_path = tmp_path / "strict_raiser.json"
        dump_artifact(artifact, str(artifact_path))

        # Should load without error
        strategy = ArtifactGreedyStrategy(
            name="test_strict",
            artifact_path=str(artifact_path)
        )

        assert strategy.name == "test_strict"
        assert strategy._contract_token == "S"

    def test_load_heuristics_artifact(self, tmp_path):
        """Test loading heuristics_imitation_v1 artifact."""
        artifact = {
            "schema_version": "1",
            "model_type": "heuristics_imitation_v1",
            "contract": "HIGH",
            "model_params": {
                "suit_thresholds": {"bid_6": 350, "bid_5": 300, "bid_4": 250, "bid_3": 200},
                "high_low_thresholds": {"bid_5": 40, "bid_4": 30, "bid_3": 20},
                "high_card_ranks": ["A", "K", "Q"],
                "low_card_ranks": ["J", "T"]
            },
            "metadata": {
                "description": "Test heuristics artifact"
            }
        }

        artifact_path = tmp_path / "heuristics.json"
        dump_artifact(artifact, str(artifact_path))

        # Should load without error
        strategy = ArtifactGreedyStrategy(
            name="test_heuristics",
            artifact_path=str(artifact_path)
        )

        assert strategy.name == "test_heuristics"
        assert strategy._contract_token == "HIGH"

    def test_strict_raiser_decide_bid_initial(self, tmp_path):
        """Test strict_raiser artifact bidding behavior - initial bid."""
        artifact = {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": "S",
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 10,
                "contract": "S"
            }
        }

        artifact_path = tmp_path / "strict_raiser.json"
        dump_artifact(artifact, str(artifact_path))

        strategy = ArtifactGreedyStrategy(
            name="test_strict",
            artifact_path=str(artifact_path)
        )

        # Create a sample hand (content doesn't matter for strict raiser logic)
        hand = [Card("S", "A"), Card("S", "K"), Card("H", "Q"), Card("D", "J"), Card("C", "T")]

        # Test initial bid (current_high_bid = 0)
        bid_amount, contract_type, suit = strategy.decide_bid(
            hand=hand,
            current_high_bid=0,
            current_winner_index=None,
            partner_index=2,
            player_index=0
        )

        assert bid_amount == 3
        assert contract_type == "suit"
        assert suit == "S"

    def test_strict_raiser_decide_bid_raise(self, tmp_path):
        """Test strict_raiser artifact bidding behavior - raising."""
        artifact = {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": "S",
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 6,
                "contract": "S"
            }
        }

        artifact_path = tmp_path / "strict_raiser.json"
        dump_artifact(artifact, str(artifact_path))

        strategy = ArtifactGreedyStrategy(
            name="test_strict",
            artifact_path=str(artifact_path)
        )

        hand = [Card("S", "A"), Card("S", "K"), Card("H", "Q"), Card("D", "J"), Card("C", "T")]

        # Test raising (current_high_bid = 4)
        bid_amount, contract_type, suit = strategy.decide_bid(
            hand=hand,
            current_high_bid=4,
            current_winner_index=1,
            partner_index=2,
            player_index=0
        )

        assert bid_amount == 5  # 4 + 1
        assert contract_type == "suit"
        assert suit == "S"

    def test_strict_raiser_decide_bid_max_reached(self, tmp_path):
        """Test strict_raiser artifact bidding behavior - max bid reached, should pass."""
        artifact = {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": "S",
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 5,
                "contract": "S"
            }
        }

        artifact_path = tmp_path / "strict_raiser.json"
        dump_artifact(artifact, str(artifact_path))

        strategy = ArtifactGreedyStrategy(
            name="test_strict",
            artifact_path=str(artifact_path)
        )

        hand = [Card("S", "A"), Card("S", "K"), Card("H", "Q"), Card("D", "J"), Card("C", "T")]

        # Test max bid (current_high_bid = 5, max_bid = 5)
        bid_amount, contract_type, suit = strategy.decide_bid(
            hand=hand,
            current_high_bid=5,
            current_winner_index=1,
            partner_index=2,
            player_index=0
        )

        assert bid_amount == 0  # Pass
        assert contract_type is None
        assert suit is None

    def test_heuristics_high_contract_bids(self, tmp_path):
        """Test heuristics artifact with HIGH contract - strong hand bids."""
        artifact = {
            "schema_version": "1",
            "model_type": "heuristics_imitation_v1",
            "contract": "HIGH",
            "model_params": {
                "suit_thresholds": {"bid_6": 350, "bid_5": 300, "bid_4": 250, "bid_3": 200},
                "high_low_thresholds": {"bid_5": 40, "bid_4": 30, "bid_3": 20},
                "high_card_ranks": ["A", "K", "Q"],
                "low_card_ranks": ["J", "T"]
            }
        }

        artifact_path = tmp_path / "heuristics.json"
        dump_artifact(artifact, str(artifact_path))

        strategy = ArtifactGreedyStrategy(
            name="test_heuristics",
            artifact_path=str(artifact_path)
        )

        # Strong hand with high cards (using valid ranks: T, J, Q, K, A)
        hand = [Card("S", "A"), Card("H", "A"), Card("D", "K"), Card("C", "K"), Card("S", "Q")]

        bid_amount, contract_type, suit = strategy.decide_bid(
            hand=hand,
            current_high_bid=0,
            current_winner_index=None,
            partner_index=2,
            player_index=0
        )

        # Strong hand should bid (exact amount depends on scoring, but should not pass)
        assert bid_amount > 0
        # Heuristics evaluates all contracts and picks best, so contract could be suit or HIGH/LOW
        assert contract_type in {"suit", "HIGH", "LOW"}
        if contract_type == "suit":
            assert suit in {"C", "D", "H", "S"}
        else:
            assert suit is None  # HIGH/LOW don't specify suit

    def test_linear_regression_fails_fast(self, tmp_path):
        """Test that linear_regression artifacts fail fast with clear error message."""
        artifact = {
            "schema_version": "1",
            "model_type": "linear_regression",
            "contract": "H",
            "model_params": {
                "coefficients": [0.1, 0.2, -0.05],
                "features": ["trump_count", "high_card_points", "suit_length"],
                "intercept": 0.5
            },
            "metadata": {
                "description": "Linear regression test"
            }
        }

        artifact_path = tmp_path / "linear.json"
        dump_artifact(artifact, str(artifact_path))

        # Should fail at initialization with clear error message
        with pytest.raises(NotImplementedError, match="linear_regression artifacts are reserved for future work"):
            ArtifactGreedyStrategy(
                name="test_linear",
                artifact_path=str(artifact_path)
            )

    def test_determinism_strict_raiser(self, tmp_path):
        """Test that strict_raiser artifact produces deterministic results."""
        artifact = {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": "S",
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 10,
                "contract": "S"
            }
        }

        artifact_path = tmp_path / "strict_raiser.json"
        dump_artifact(artifact, str(artifact_path))

        strategy1 = ArtifactGreedyStrategy(
            name="test_strict_1",
            artifact_path=str(artifact_path)
        )
        strategy2 = ArtifactGreedyStrategy(
            name="test_strict_2",
            artifact_path=str(artifact_path)
        )

        hand = [Card("S", "A"), Card("S", "K"), Card("H", "Q"), Card("D", "J"), Card("C", "T")]

        # Test multiple calls produce same result
        result1_a = strategy1.decide_bid(hand, 0, None, 2, 0)
        result1_b = strategy1.decide_bid(hand, 0, None, 2, 0)
        result2 = strategy2.decide_bid(hand, 0, None, 2, 0)

        assert result1_a == result1_b == result2
        assert result1_a == (3, "suit", "S")

    def test_determinism_heuristics(self, tmp_path):
        """Test that heuristics artifact produces deterministic results."""
        artifact = {
            "schema_version": "1",
            "model_type": "heuristics_imitation_v1",
            "contract": "HIGH",
            "model_params": {
                "suit_thresholds": {"bid_6": 350, "bid_5": 300, "bid_4": 250, "bid_3": 200},
                "high_low_thresholds": {"bid_5": 40, "bid_4": 30, "bid_3": 20},
                "high_card_ranks": ["A", "K", "Q"],
                "low_card_ranks": ["J", "T"]
            }
        }

        artifact_path = tmp_path / "heuristics.json"
        dump_artifact(artifact, str(artifact_path))

        strategy = ArtifactGreedyStrategy(
            name="test_heuristics",
            artifact_path=str(artifact_path)
        )

        hand = [Card("S", "A"), Card("S", "K"), Card("H", "Q"), Card("D", "A"), Card("C", "K")]

        # Test multiple calls produce same result
        result1 = strategy.decide_bid(hand, 0, None, 2, 0)
        result2 = strategy.decide_bid(hand, 0, None, 2, 0)
        result3 = strategy.decide_bid(hand, 0, None, 2, 0)

        assert result1 == result2 == result3
