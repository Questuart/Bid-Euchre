"""
Unit tests for bidding policy interface and baseline bidders.
"""

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.experiments.config import BiddingPolicyConfig
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    ArtifactBidder,
    BidAction,
    BiddingObservation,
    ModeloEspecifico,
    StrictRaiserBidder,
)


class TestBidAction:
    """Test BidAction dataclass and validation."""

    def test_pass_action(self):
        """Test creating a pass action."""
        action = BidAction.pass_bid()
        assert action.n == 0
        assert action.contract is None
        assert action.trump_suit is None
        assert action.is_pass()

    def test_bid_action_valid(self):
        """Test creating valid bid actions."""
        # Suit contracts
        action = BidAction.bid(3, "S")
        assert action.n == 3
        assert action.contract == "S"
        assert action.trump_suit is None
        assert not action.is_pass()

        action = BidAction.bid(5, "C")
        assert action.n == 5
        assert action.contract == "C"

        # High/Low contracts
        action = BidAction.bid(7, "HIGH")
        assert action.n == 7
        assert action.contract == "HIGH"

        action = BidAction.bid(8, "LOW")
        assert action.n == 8
        assert action.contract == "LOW"

    def test_bid_action_invalid_n(self):
        """Test invalid bid amounts."""
        with pytest.raises(ValueError, match="Bid amount n must be 0-10"):
            BidAction(n=-1, contract="S")

        with pytest.raises(ValueError, match="Bid amount n must be 0-10"):
            BidAction(n=11, contract="S")

    def test_bid_action_invalid_contract(self):
        """Test invalid contract types."""
        with pytest.raises(ValueError, match="Contract must be one of"):
            BidAction.bid(3, "invalid")

        with pytest.raises(ValueError, match="Contract must be one of"):
            BidAction.bid(3, "suit")  # Old format not allowed

    def test_pass_with_contract_invalid(self):
        """Test that pass cannot have contract."""
        with pytest.raises(ValueError, match="Pass.*must have contract=None"):
            BidAction(n=0, contract="S")

    def test_bid_without_contract_invalid(self):
        """Test that bid must have contract."""
        with pytest.raises(ValueError, match="Bid.*must specify contract"):
            BidAction.bid(3, None)

    def test_trump_suit_not_allowed(self):
        """Test that trump_suit is not used in v1."""
        with pytest.raises(ValueError, match="trump_suit must be None"):
            BidAction(n=3, contract="S", trump_suit="S")

    def test_to_contract_tuple(self):
        """Test conversion to legacy contract format."""
        # Pass
        action = BidAction.pass_bid()
        assert action.to_contract_tuple() == (None, None)

        # Suit contracts
        action = BidAction.bid(3, "S")
        assert action.to_contract_tuple() == ("suit", "S")

        action = BidAction.bid(4, "C")
        assert action.to_contract_tuple() == ("suit", "C")

        # High/Low
        action = BidAction.bid(5, "HIGH")
        assert action.to_contract_tuple() == ("high", None)

        action = BidAction.bid(6, "LOW")
        assert action.to_contract_tuple() == ("low", None)


class TestBiddingObservation:
    """Test BiddingObservation dataclass."""

    def test_observation_creation(self):
        """Test creating a bidding observation."""
        hand = [Card("S", "A"), Card("H", "K")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=2
        )

        assert obs.hand == hand
        assert obs.seat == 0
        assert obs.dealer_seat == 3
        assert obs.current_high_bid == 2
        assert obs.allowed_contracts == ("C", "D", "H", "S", "HIGH", "LOW")


class TestAlwaysPassBidder:
    """Test AlwaysPassBidder."""

    def test_always_passes(self):
        """Test that AlwaysPassBidder always passes."""
        bidder = AlwaysPassBidder()
        hand = [Card("S", "A"), Card("H", "K")]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()

        # Test with existing high bid
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=5
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()


class TestStrictRaiserBidder:
    """Test StrictRaiserBidder."""

    def test_initial_bid(self):
        """Test bidding 3 when no high bid exists."""
        bidder = StrictRaiserBidder()
        hand = [Card("S", "A"), Card("H", "K")]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert action.n == 3
        assert action.contract == "S"
        assert not action.is_pass()

    def test_raise_bid(self):
        """Test raising existing bids."""
        bidder = StrictRaiserBidder()

        # Raise from 3 to 4
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=3
        )

        action = bidder.choose_bid(obs)
        assert action.n == 4
        assert action.contract == "S"

        # Raise from 8 to 9
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=8
        )

        action = bidder.choose_bid(obs)
        assert action.n == 9
        assert action.contract == "S"

    def test_max_bid_pass(self):
        """Test passing when at maximum bid."""
        bidder = StrictRaiserBidder()

        # Bid 10 when current is 9
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=9
        )

        action = bidder.choose_bid(obs)
        assert action.n == 10
        assert action.contract == "S"
        assert not action.is_pass()

        # Pass when current is 10 (can't bid higher)
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=10
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_contract_tuple_conversion(self):
        """Test that bids convert to correct contract tuples."""
        bidder = StrictRaiserBidder()

        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        contract_type, trump_suit = action.to_contract_tuple()
        assert contract_type == "suit"
        assert trump_suit == "S"


class TestArtifactBidder:
    """Test ArtifactBidder loading and execution."""

    def test_load_valid_strict_raiser_artifact(self, tmp_path):
        """Test loading a valid strict raiser imitation artifact."""
        from bid_euchre.models.bidding_artifact import dump_artifact

        # Create a valid artifact
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
                "description": "Test artifact"
            }
        }

        # Write to temp file
        artifact_path = tmp_path / "test_artifact.json"
        dump_artifact(artifact, str(artifact_path))

        # Load with ArtifactBidder
        bidder = ArtifactBidder(str(artifact_path))

        assert bidder.name == "artifact_S"
        assert bidder.artifact == artifact
        assert bidder.model_type == "strict_raiser_imitation_v1"

    def test_load_valid_heuristics_artifact(self, tmp_path):
        """Test loading a valid heuristics imitation artifact."""
        from bid_euchre.models.bidding_artifact import dump_artifact

        # Create a valid artifact
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

        # Write to temp file
        artifact_path = tmp_path / "test_heuristics.json"
        dump_artifact(artifact, str(artifact_path))

        # Load with ArtifactBidder
        bidder = ArtifactBidder(str(artifact_path))

        assert bidder.name == "artifact_HIGH"
        assert bidder.model_type == "heuristics_imitation_v1"

    def test_load_invalid_artifact_file_not_found(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError, match="Bidding artifact not found"):
            ArtifactBidder("/non/existent/file.json")

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON."""
        artifact_path = tmp_path / "invalid.json"
        with open(artifact_path, 'w') as f:
            f.write("invalid json {")

        with pytest.raises(ValueError, match="Invalid JSON"):
            ArtifactBidder(str(artifact_path))

    def test_load_invalid_schema_version(self, tmp_path):
        """Test loading artifact with invalid schema version."""
        import json


        artifact = {
            "schema_version": "2",  # Invalid version
            "model_type": "strict_raiser_imitation_v1",
            "contract": "S",
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 10,
                "contract": "S"
            }
        }

        artifact_path = tmp_path / "invalid_schema.json"
        with open(artifact_path, 'w') as f:
            json.dump(artifact, f)

        with pytest.raises(ValueError, match="Unsupported schema version"):
            ArtifactBidder(str(artifact_path))

    def test_load_missing_required_fields(self, tmp_path):
        """Test loading artifact missing required fields."""
        import json

        artifact = {
            "schema_version": "1",
            # Missing model_type, contract, model_params
        }

        artifact_path = tmp_path / "missing_fields.json"
        with open(artifact_path, 'w') as f:
            json.dump(artifact, f)

        with pytest.raises(ValueError, match="Missing required fields"):
            ArtifactBidder(str(artifact_path))

    def test_load_invalid_contract(self, tmp_path):
        """Test loading artifact with invalid contract."""
        import json

        artifact = {
            "schema_version": "1",
            "model_type": "strict_raiser_imitation_v1",
            "contract": "INVALID",  # Invalid contract
            "model_params": {
                "initial_bid": {"n": 3, "contract": "S"},
                "raise_increment": 1,
                "max_bid": 10,
                "contract": "S"
            }
        }

        artifact_path = tmp_path / "invalid_contract.json"
        with open(artifact_path, 'w') as f:
            json.dump(artifact, f)

        with pytest.raises(ValueError, match="Invalid contract"):
            ArtifactBidder(str(artifact_path))

    def test_load_unsupported_model_type(self, tmp_path):
        """Test loading artifact with unsupported model type."""
        from bid_euchre.models.bidding_artifact import dump_artifact

        artifact = {
            "schema_version": "1",
            "model_type": "unsupported_model_type",
            "contract": "S",
            "model_params": {}
        }

        artifact_path = tmp_path / "unsupported_model.json"
        dump_artifact(artifact, str(artifact_path))

        with pytest.raises(ValueError, match="Unsupported model_type"):
            ArtifactBidder(str(artifact_path))

    def test_strict_raiser_bidding_behavior(self, tmp_path):
        """Test that strict raiser imitation behaves like StrictRaiserBidder."""
        from bid_euchre.models.bidding_artifact import dump_artifact

        # Create artifact that replicates StrictRaiserBidder
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

        artifact_bidder = ArtifactBidder(str(artifact_path))
        reference_bidder = StrictRaiserBidder()

        # Test various scenarios
        test_cases = [
            (0, 3),  # Initial bid
            (3, 4),  # Raise by 1
            (5, 6),  # Raise by 1
            (9, 10), # Raise by 1
            (10, None), # Pass (can't raise above 10)
        ]

        for current_high_bid, expected_n in test_cases:
            obs = BiddingObservation(
                hand=[],  # Hand doesn't matter for strict raiser
                seat=0,
                dealer_seat=3,
                current_high_bid=current_high_bid
            )

            artifact_action = artifact_bidder.choose_bid(obs)
            reference_action = reference_bidder.choose_bid(obs)

            if expected_n is None:
                assert artifact_action.is_pass()
                assert reference_action.is_pass()
            else:
                assert artifact_action.n == expected_n
                assert artifact_action.contract == "S"
                assert reference_action.n == expected_n
                assert reference_action.contract == "S"

    def test_heuristics_bidding_behavior(self, tmp_path):
        """Test that heuristics imitation behaves like RanktheTank."""
        from bid_euchre.models.bidding_artifact import dump_artifact

        # Create artifact that replicates RanktheTank
        artifact = {
            "schema_version": "1",
            "model_type": "heuristics_imitation_v1",
            "contract": "S",
            "model_params": {
                "suit_thresholds": {"bid_6": 350, "bid_5": 300, "bid_4": 250, "bid_3": 200},
                "high_low_thresholds": {"bid_5": 40, "bid_4": 30, "bid_3": 20},
                "high_card_ranks": ["A", "K", "Q"],
                "low_card_ranks": ["J", "T"]
            }
        }

        artifact_path = tmp_path / "heuristics.json"
        dump_artifact(artifact, str(artifact_path))

        artifact_bidder = ArtifactBidder(str(artifact_path))

        # Test with a strong hand that should bid
        strong_hand = [
            Card(suit="S", rank="A"), Card(suit="S", rank="K"), Card(suit="S", rank="Q"), Card(suit="S", rank="J"), Card(suit="S", rank="T"),
            Card(suit="H", rank="A"), Card(suit="H", rank="K"), Card(suit="H", rank="Q"), Card(suit="H", rank="J"), Card(suit="H", rank="T")
        ]

        obs = BiddingObservation(
            hand=strong_hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = artifact_bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "S"
        assert action.n >= 3  # Should bid something reasonable

    def test_custom_name(self, tmp_path):
        """Test setting custom bidder name."""
        from bid_euchre.models.bidding_artifact import dump_artifact

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

        artifact_path = tmp_path / "custom_name.json"
        dump_artifact(artifact, str(artifact_path))

        bidder = ArtifactBidder(str(artifact_path), name="my_custom_bidder")
        assert bidder.name == "my_custom_bidder"


class TestBiddingPolicyConfig:
    """Test BiddingPolicyConfig functionality."""

    def test_create_always_pass_bidder(self):
        """Test creating AlwaysPassBidder from config."""
        config = BiddingPolicyConfig(
            name="test_pass",
            class_name="AlwaysPassBidder"
        )

        bidder = config.create_bidding_policy()
        assert bidder.name == "test_pass"
        assert isinstance(bidder, AlwaysPassBidder)

        # Test it always passes
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )
        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_create_artifact_bidder(self, tmp_path):
        """Test creating ArtifactBidder from config."""
        from bid_euchre.models.bidding_artifact import dump_artifact

        # Create artifact
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

        artifact_path = tmp_path / "config_test.json"
        dump_artifact(artifact, str(artifact_path))

        config = BiddingPolicyConfig(
            name="test_artifact",
            class_name="ArtifactBidder",
            params={"artifact_path": str(artifact_path)}
        )

        bidder = config.create_bidding_policy()
        assert bidder.name == "test_artifact"
        assert isinstance(bidder, ArtifactBidder)

    def test_create_artifact_bidder_missing_path(self):
        """Test ArtifactBidder config without artifact_path."""
        config = BiddingPolicyConfig(
            name="test_artifact",
            class_name="ArtifactBidder",
            params={}  # Missing artifact_path
        )

        with pytest.raises(ValueError, match="ArtifactBidder requires 'artifact_path' parameter"):
            config.create_bidding_policy()

    def test_unknown_bidding_policy_class(self):
        """Test unknown bidding policy class."""
        config = BiddingPolicyConfig(
            name="test",
            class_name="UnknownBidder"
        )

        with pytest.raises(ValueError, match="Unknown bidding policy class"):
            config.create_bidding_policy()


class TestModeloEspecifico:
    """Test ModeloEspecifico feature-weighted bidder."""

    def test_strong_hand_bids_correctly(self):
        """Test a strong hand: 2 bowers + 2 trump + 1 offsuit ace = score 4.5 → bid 4."""
        bidder = ModeloEspecifico()

        # Hand: RB(H), LB(H), AH, KH, AS
        # In Hearts trump: 2 bowers, 4 trump total (RB, LB, A, K), 1 offsuit ace (AS)
        # Score = 1.0 * 2 + 0.5 * 4 + 0.5 * 1 = 2 + 2 + 0.5 = 4.5 → bid 4
        hand = [
            Card("H", "J"),  # Right bower
            Card("D", "J"),  # Left bower (Jack of same-color suit)
            Card("H", "A"),  # Trump Ace
            Card("H", "K"),  # Trump King
            Card("S", "A"),  # Offsuit Ace
        ]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.n == 4
        assert action.contract == "H"  # Hearts should score highest

    def test_weak_hand_passes(self):
        """Test a weak hand (score < 3) passes."""
        bidder = ModeloEspecifico()

        # Hand with no bowers, 2 trump, no offsuit aces
        # Score = 0 + 0.5 * 2 + 0 = 1.0 → pass
        hand = [
            Card("S", "K"),  # Trump King
            Card("S", "Q"),  # Trump Queen
            Card("H", "K"),  # Offsuit (not ace)
            Card("D", "Q"),  # Offsuit (not ace)
            Card("C", "T"),  # Offsuit (not ace)
        ]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_contract_selection_highest_score(self):
        """Test that the contract with highest score is selected."""
        bidder = ModeloEspecifico()

        # Hand heavily favoring Spades trump
        # In Spades: RB, LB, A (3 trump, 2 bowers) + 1 offsuit ace
        # Score = 2 + 1.5 + 0.5 = 4.0 → bid 4
        hand = [
            Card("S", "J"),  # Right bower in Spades
            Card("C", "J"),  # Left bower in Spades (Club J)
            Card("S", "A"),  # Trump Ace
            Card("H", "A"),  # Offsuit Ace
            Card("D", "K"),  # Offsuit
        ]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "S"  # Spades should be chosen

    def test_strict_increasing_compliance(self):
        """Test that bids comply with strict-increasing rule."""
        bidder = ModeloEspecifico()

        # Strong hand that would normally bid 4
        hand = [
            Card("H", "J"),
            Card("D", "J"),
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "A"),
        ]

        # Current high bid is 4, so must bid higher or pass
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=4
        )

        action = bidder.choose_bid(obs)
        # Score is 4.5 → floor to 4, but 4 is not > 4, so must pass
        assert action.is_pass()

    def test_borderline_bid_3(self):
        """Test a hand that scores exactly 3 bids 3."""
        bidder = ModeloEspecifico()

        # Need score of exactly 3.0-3.99 for bid 3
        # 0 bowers + 6 trump + 0 offsuit aces = 0 + 3 + 0 = 3.0 → bid 3
        hand = [
            Card("H", "A"),
            Card("H", "K"),
            Card("H", "Q"),
            Card("H", "T"),
            Card("C", "A"),  # This would be offsuit ace, so let's use non-ace
        ]
        # Actually, let's construct it differently:
        # 0 bowers, 6 trump, 0 offsuit aces → 0.5 * 6 = 3.0
        # But we only have 5 cards in test hands sometimes...
        # Let's do: 1 bower (1.0) + 4 trump (2.0) + 0 aces = 3.0
        hand = [
            Card("H", "J"),  # Right bower (1 bower, 1 trump)
            Card("H", "K"),  # Trump
            Card("H", "Q"),  # Trump
            Card("H", "T"),  # Trump → total 4 trump, 1 bower
            Card("D", "K"),  # Offsuit non-ace
        ]
        # Score = 1.0 * 1 + 0.5 * 4 + 0.5 * 0 = 1 + 2 + 0 = 3.0 → bid 3

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.n == 3
        assert action.contract == "H"

    def test_high_contract_bids_with_3_offsuit_aces(self):
        """HIGH with 3+ offsuit aces → bids 3 (score = 1.0 * 3 = 3)."""
        bidder = ModeloEspecifico()

        # In HIGH mode, all cards are offsuit. 3 aces → score 3.0 → bid 3
        hand = [
            Card("S", "A"),
            Card("H", "A"),
            Card("D", "A"),
            Card("C", "K"),
            Card("C", "Q"),
            Card("S", "K"),
            Card("H", "K"),
            Card("D", "K"),
            Card("S", "Q"),
            Card("H", "Q"),
        ]

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "HIGH"
        assert action.n == 3

    def test_high_contract_passes_with_2_offsuit_aces(self):
        """HIGH with 2 offsuit aces → passes (score = 2 < 3)."""
        bidder = ModeloEspecifico()

        # 2 aces → score 2.0 → floor(2.0) = 2 < 3, no suit should score 3 either
        hand = [
            Card("S", "A"),
            Card("H", "A"),
            Card("D", "K"),
            Card("C", "K"),
            Card("C", "Q"),
            Card("S", "Q"),
            Card("H", "Q"),
            Card("D", "Q"),
            Card("S", "T"),
            Card("H", "T"),
        ]

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
        action = bidder.choose_bid(obs)
        # Suit contracts: no bowers, max 2 trump per suit, 1-2 offsuit aces
        # Score for any suit: 0 + 0.5*2 + 0.5*1 = 1.5 at best → pass
        # HIGH: 1.0 * 2 = 2 → pass
        assert action.is_pass()

    def test_low_contract_bids_with_3_offsuit_tens(self):
        """LOW with 3+ offsuit tens → bids 3 (score = 1.0 * 3 = 3)."""
        bidder = ModeloEspecifico()

        # In LOW mode, all cards are offsuit. 3 tens → score 3.0 → bid 3
        hand = [
            Card("S", "T"),
            Card("H", "T"),
            Card("D", "T"),
            Card("C", "Q"),
            Card("C", "K"),
            Card("S", "Q"),
            Card("H", "Q"),
            Card("D", "Q"),
            Card("S", "K"),
            Card("H", "K"),
        ]

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "LOW"
        assert action.n == 3

    def test_low_contract_passes_with_2_offsuit_tens(self):
        """LOW with 2 offsuit tens → passes (score = 2 < 3)."""
        bidder = ModeloEspecifico()

        # 2 tens → score 2.0 → floor(2.0) = 2 < 3
        hand = [
            Card("S", "T"),
            Card("H", "T"),
            Card("D", "Q"),
            Card("C", "Q"),
            Card("C", "K"),
            Card("S", "Q"),
            Card("H", "Q"),
            Card("D", "K"),
            Card("S", "K"),
            Card("H", "K"),
        ]

        obs = BiddingObservation(
            hand=hand, seat=0, dealer_seat=3, current_high_bid=0
        )
        action = bidder.choose_bid(obs)
        # No suit should score 3 either (no bowers, max 2 trump, limited aces)
        assert action.is_pass()
