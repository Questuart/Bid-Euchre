"""
Unit tests for bidder training pipeline v1.

Tests the deterministic imitation learning pipeline that trains a model
to replicate StrictRaiserBidder behavior and emits validated artifacts.
"""

import json
import tempfile
from pathlib import Path

import pytest

from bid_euchre.models.bidding_artifact import load_artifact, validate_artifact
from bid_euchre.models.train_bidder import (
    FiveHeadFredModel,
    HeuristicsModel,
    StrictRaiserModel,
    create_synthetic_observations_for_heuristics,
    create_synthetic_observations_for_strict_raiser,
    load_bidding_dataset_jsonl,
    train_and_save_model,
    train_fiveheadfred_model,
    train_heuristics_model,
    train_strict_raiser_model,
)
from bid_euchre.strategy.bidding import (
    BiddingObservation,
    RanktheTank,
    StrictRaiserBidder,
)


class TestStrictRaiserModel:
    """Test the StrictRaiserModel class."""

    def test_model_initialization(self):
        """Test model initializes with correct rules."""
        model = StrictRaiserModel()

        expected_rules = {
            "initial_bid": {"n": 3, "contract": "S"},
            "raise_increment": 1,
            "max_bid": 10,
            "contract": "S"
        }
        assert model.rules == expected_rules

    def test_predict_bid_no_current_high(self):
        """Test prediction when current_high_bid is 0."""
        model = StrictRaiserModel()

        prediction = model.predict_bid(0)
        assert prediction == {"n": 3, "contract": "S"}

    def test_predict_bid_can_raise(self):
        """Test prediction when current_high_bid < 10."""
        model = StrictRaiserModel()

        # Test various raise scenarios
        assert model.predict_bid(1) == {"n": 2, "contract": "S"}
        assert model.predict_bid(5) == {"n": 6, "contract": "S"}
        assert model.predict_bid(9) == {"n": 10, "contract": "S"}

    def test_predict_bid_max_reached(self):
        """Test prediction when current_high_bid >= 10."""
        model = StrictRaiserModel()

        assert model.predict_bid(10) is None  # Pass
        assert model.predict_bid(11) is None  # Pass

    def test_to_artifact_dict(self):
        """Test artifact dictionary creation."""
        model = StrictRaiserModel()

        artifact = model.to_artifact_dict("S", seed=42)

        # Check required fields
        assert artifact["schema_version"] == "1"
        assert artifact["model_type"] == "strict_raiser_imitation_v1"
        assert artifact["contract"] == "S"
        assert artifact["model_params"] == model.rules
        assert "metadata" in artifact
        metadata = artifact["metadata"]
        assert metadata["teacher_model"] == "StrictRaiserBidder"
        assert metadata["training_data"] == "fixture dataset"
        assert metadata["training_seed"] == 42

        # Should validate successfully
        validate_artifact(artifact)


class TestFiveHeadFredModel:
    """Test the FiveHeadFredModel class."""

    def test_model_initialization(self):
        """Test model initializes with correct rules."""
        model = FiveHeadFredModel("S")

        expected_rules = {
            "target_bid": 5,
            "contract": "S"
        }
        assert model.rules == expected_rules

    def test_predict_bid_legal_cases(self):
        """Test prediction when 5 is legal (current_high_bid < 5)."""
        model = FiveHeadFredModel("S")

        # Test all cases where 5 > current_high_bid
        assert model.predict_bid(0) == {"n": 5, "contract": "S"}
        assert model.predict_bid(1) == {"n": 5, "contract": "S"}
        assert model.predict_bid(2) == {"n": 5, "contract": "S"}
        assert model.predict_bid(3) == {"n": 5, "contract": "S"}
        assert model.predict_bid(4) == {"n": 5, "contract": "S"}

    def test_predict_bid_illegal_cases(self):
        """Test prediction when 5 is not legal (current_high_bid >= 5)."""
        model = FiveHeadFredModel("S")

        # Test all cases where 5 <= current_high_bid (should pass)
        assert model.predict_bid(5) is None  # Pass
        assert model.predict_bid(6) is None  # Pass
        assert model.predict_bid(7) is None  # Pass
        assert model.predict_bid(8) is None  # Pass
        assert model.predict_bid(9) is None  # Pass
        assert model.predict_bid(10) is None  # Pass

    def test_different_contracts(self):
        """Test model works with different contracts."""
        for contract in ["C", "D", "H", "S", "HIGH", "LOW"]:
            model = FiveHeadFredModel(contract)
            assert model.rules["contract"] == contract
            assert model.predict_bid(0) == {"n": 5, "contract": contract}
            assert model.predict_bid(5) is None

    def test_to_artifact_dict(self):
        """Test artifact dictionary creation."""
        model = FiveHeadFredModel("S")

        artifact = model.to_artifact_dict("S", seed=42)

        # Check required fields
        assert artifact["schema_version"] == "1"
        assert artifact["model_type"] == "fiveheadfred_v1"
        assert artifact["contract"] == "S"
        assert artifact["model_params"] == model.rules
        assert "metadata" in artifact
        metadata = artifact["metadata"]
        assert metadata["teacher_model"] == "FiveHeadFred"
        assert metadata["training_data"] == "deterministic rule"
        assert metadata["training_seed"] == 42

        # Should validate successfully
        validate_artifact(artifact)

    def test_artifact_determinism(self):
        """Test that artifacts are deterministic for a given seed."""
        model1 = FiveHeadFredModel("H")
        model2 = FiveHeadFredModel("H")

        artifact1 = model1.to_artifact_dict("H", seed=123)
        artifact2 = model2.to_artifact_dict("H", seed=123)

        # Should be identical
        assert artifact1 == artifact2

        # Different seeds should produce different timestamps but same structure
        artifact3 = model1.to_artifact_dict("H", seed=456)
        assert artifact1["metadata"]["created_at"] != artifact3["metadata"]["created_at"]
        assert artifact1["model_params"] == artifact3["model_params"]


class TestTrainingPipeline:
    """Test the training pipeline functions."""

    def test_create_synthetic_observations(self):
        """Test creation of synthetic observations for training."""
        observations = create_synthetic_observations_for_strict_raiser()

        # Should have observations for all current_high_bid values (0-10)
        # and all seat/dealer combinations (4x4=16 per bid level)
        expected_count = 11 * 16  # 11 bid levels * 16 seat combinations
        assert len(observations) == expected_count

        # Check that all observations have the expected structure
        for obs in observations:
            assert isinstance(obs, BiddingObservation)
            assert isinstance(obs.hand, list)
            assert len(obs.hand) == 5  # Standard euchre hand size
            assert 0 <= obs.seat <= 3
            assert 0 <= obs.dealer_seat <= 3
            assert 0 <= obs.current_high_bid <= 10

    def test_train_strict_raiser_model(self):
        """Test training the model."""
        model = train_strict_raiser_model("S")

        assert isinstance(model, StrictRaiserModel)

        # Verify model matches StrictRaiserBidder behavior
        teacher = StrictRaiserBidder()

        # Test on synthetic observations
        observations = create_synthetic_observations_for_strict_raiser()
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

            assert model_prediction == teacher_dict, (
                f"Model prediction {model_prediction} != teacher {teacher_dict} "
                f"for current_high_bid={obs.current_high_bid}"
            )

    def test_train_and_save_model(self):
        """Test end-to-end training and saving."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            artifact = train_and_save_model(
                contract="S",
                output_path=output_path,
                seed=42
            )

            # Check artifact was returned
            assert isinstance(artifact, dict)
            validate_artifact(artifact)

            # Check file was created and is valid
            assert Path(output_path).exists()
            loaded_artifact = load_artifact(output_path)
            assert loaded_artifact == artifact

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_train_and_save_model_no_directory(self):
        """Test saving the artifact to the current directory."""
        artifact_name = "artifact_without_dir.json"
        try:
            artifact = train_and_save_model(
                contract="S",
                output_path=artifact_name,
                seed=99
            )

            assert Path(artifact_name).exists()
            loaded = load_artifact(artifact_name)
            assert loaded == artifact
        finally:
            Path(artifact_name).unlink(missing_ok=True)

    def test_determinism_same_seed(self):
        """Test that training with same seed produces identical artifacts."""
        artifacts = [
            train_and_save_model(contract="S", seed=42),
            train_and_save_model(contract="S", seed=42),
        ]

        # Should be identical
        assert artifacts[0] == artifacts[1]

        # Check deterministic metadata
        metadata = artifacts[0]["metadata"]
        assert artifacts[0]["metadata"]["created_at"] == artifacts[1]["metadata"]["created_at"]
        assert metadata["training_seed"] == 42

    def test_different_contracts_produce_different_artifacts(self):
        """Test that different contracts produce different artifacts."""
        artifact_s = train_and_save_model(contract="S", seed=42)
        artifact_h = train_and_save_model(contract="H", seed=42)

        assert artifact_s["contract"] == "S"
        assert artifact_h["contract"] == "H"
        assert artifact_s != artifact_h

    def test_artifact_validation_integration(self):
        """Test that produced artifacts pass full validation."""
        artifact = train_and_save_model(contract="C", seed=42)

        # Should not raise any exceptions
        validate_artifact(artifact)

        # Check all required fields are present and correct
        assert artifact["schema_version"] == "1"
        assert artifact["model_type"] == "strict_raiser_imitation_v1"
        assert artifact["contract"] == "C"
        assert isinstance(artifact["model_params"], dict)
        assert "metadata" in artifact

        # Metadata should have expected fields
        metadata = artifact["metadata"]
        assert "created_at" in metadata
        assert "description" in metadata
        assert "training_data" in metadata
        assert "teacher_model" in metadata


class TestHeuristicsModel:
    """Test the HeuristicsModel class."""

    def test_model_initialization(self):
        """Test model initializes with correct rules."""
        model = HeuristicsModel()

        # Check structure of rules
        assert "suit_thresholds" in model.rules
        assert "high_low_thresholds" in model.rules
        assert "high_card_ranks" in model.rules
        assert "low_card_ranks" in model.rules

        # Check suit thresholds
        assert model.rules["suit_thresholds"]["bid_3"] == 200
        assert model.rules["suit_thresholds"]["bid_6"] == 350

    def test_to_artifact_dict(self):
        """Test artifact dictionary creation."""
        model = HeuristicsModel()

        artifact = model.to_artifact_dict("S", seed=42)

        # Check required fields
        assert artifact["schema_version"] == "1"
        assert artifact["model_type"] == "heuristics_imitation_v1"
        assert artifact["contract"] == "S"
        assert artifact["model_params"] == model.rules
        assert "metadata" in artifact
        metadata = artifact["metadata"]
        assert metadata["teacher_model"] == "RanktheTank"
        assert metadata["training_data"] == "synthetic observations"
        assert metadata["training_seed"] == 42

        # Should validate successfully
        validate_artifact(artifact)


class TestHeuristicsTrainingPipeline:
    """Test the heuristics training pipeline functions."""

    def test_create_synthetic_observations_for_heuristics(self):
        """Test creation of synthetic observations for heuristics training."""
        observations = create_synthetic_observations_for_heuristics()

        # Should have observations for diverse hands
        assert len(observations) > 0

        # Check that all observations have the expected structure
        for obs in observations:
            assert isinstance(obs, BiddingObservation)
            assert isinstance(obs.hand, list)
            assert len(obs.hand) == 5  # Standard euchre hand size
            assert 0 <= obs.seat <= 3
            assert 0 <= obs.dealer_seat <= 3
            assert 0 <= obs.current_high_bid <= 10

    def test_train_heuristics_model(self):
        """Test training the heuristics model."""
        model = train_heuristics_model("S")

        assert isinstance(model, HeuristicsModel)

        # Verify model matches RanktheTank behavior
        teacher = RanktheTank()

        # Test on synthetic observations
        observations = create_synthetic_observations_for_heuristics()
        for obs in observations:
            teacher_action = teacher.choose_bid(obs)
            model_prediction = model.predict_bid(obs)

            # Convert teacher action to dict format
            if teacher_action.is_pass():
                teacher_dict = None
            else:
                teacher_dict = {
                    "n": teacher_action.n,
                    "contract": teacher_action.contract
                }

            assert model_prediction == teacher_dict, (
                f"Model prediction {model_prediction} != teacher {teacher_dict} "
                f"for hand={obs.hand}, current_high_bid={obs.current_high_bid}"
            )

    def test_train_fiveheadfred_model(self):
        """Test training the FiveHeadFred model."""
        model = train_fiveheadfred_model("D")

        assert isinstance(model, FiveHeadFredModel)
        assert model.rules["contract"] == "D"

        # Verify model behavior for all edge cases
        for current_high_bid in range(0, 11):
            prediction = model.predict_bid(current_high_bid)

            if current_high_bid < 5:
                # Should bid 5
                assert prediction == {"n": 5, "contract": "D"}
            else:
                # Should pass
                assert prediction is None

    def test_train_and_save_model_fiveheadfred(self):
        """Test end-to-end training and saving for FiveHeadFred."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            artifact = train_and_save_model(
                contract="H",
                output_path=output_path,
                seed=99,
                teacher="fiveheadfred"
            )

            # Check artifact was returned
            assert isinstance(artifact, dict)
            validate_artifact(artifact)

            # Check model type
            assert artifact["model_type"] == "fiveheadfred_v1"
            assert artifact["contract"] == "H"

            # Check file was created and is valid
            assert Path(output_path).exists()
            loaded_artifact = load_artifact(output_path)
            assert loaded_artifact == artifact

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_train_and_save_model_heuristics(self):
        """Test end-to-end training and saving for heuristics."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            artifact = train_and_save_model(
                contract="S",
                output_path=output_path,
                seed=42,
                teacher="heuristics"
            )

            # Check artifact was returned
            assert isinstance(artifact, dict)
            validate_artifact(artifact)
            assert artifact["model_type"] == "heuristics_imitation_v1"

            # Check file was created and is valid
            assert Path(output_path).exists()
            loaded_artifact = load_artifact(output_path)
            assert loaded_artifact == artifact

        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_determinism_same_seed_heuristics(self):
        """Test that heuristics training with same seed produces identical artifacts."""
        artifacts = [
            train_and_save_model(contract="S", seed=42, teacher="heuristics"),
            train_and_save_model(contract="S", seed=42, teacher="heuristics"),
        ]

        # Should be identical
        assert artifacts[0] == artifacts[1]

        # Check deterministic metadata
        assert artifacts[0]["metadata"]["created_at"] == artifacts[1]["metadata"]["created_at"]
        assert artifacts[0]["metadata"]["training_seed"] == 42

    def test_different_seeds_produce_different_artifacts_heuristics(self):
        """Test that different seeds produce different artifacts (timestamp varies)."""
        artifact_42 = train_and_save_model(contract="S", seed=42, teacher="heuristics")
        artifact_99 = train_and_save_model(contract="S", seed=99, teacher="heuristics")

        # Model params should be identical (deterministic model)
        assert artifact_42["model_params"] == artifact_99["model_params"]

        # But metadata should differ (different created_at due to seed)
        assert artifact_42["metadata"]["created_at"] != artifact_99["metadata"]["created_at"]
        assert artifact_42["metadata"]["training_seed"] == 42
        assert artifact_99["metadata"]["training_seed"] == 99

    def test_artifact_validation_integration_heuristics(self):
        """Test that produced heuristics artifacts pass full validation."""
        artifact = train_and_save_model(contract="H", seed=42, teacher="heuristics")

        # Should not raise any exceptions
        validate_artifact(artifact)

        # Check all required fields are present and correct
        assert artifact["schema_version"] == "1"
        assert artifact["model_type"] == "heuristics_imitation_v1"
        assert artifact["contract"] == "H"
        assert isinstance(artifact["model_params"], dict)
        assert "metadata" in artifact

        # Metadata should have expected fields
        metadata = artifact["metadata"]
        assert "created_at" in metadata
        assert "description" in metadata
        assert "training_data" in metadata
        assert "teacher_model" in metadata
        assert metadata["teacher_model"] == "RanktheTank"


class TestTeacherParameter:
    """Test the teacher parameter in train_and_save_model."""

    def test_strict_raiser_teacher(self):
        """Test training with strict_raiser teacher."""
        artifact = train_and_save_model(
            contract="S",
            seed=42,
            teacher="strict_raiser"
        )

        assert artifact["model_type"] == "strict_raiser_imitation_v1"
        assert artifact["metadata"]["teacher_model"] == "StrictRaiserBidder"

    def test_heuristics_teacher(self):
        """Test training with heuristics teacher."""
        artifact = train_and_save_model(
            contract="S",
            seed=42,
            teacher="heuristics"
        )

        assert artifact["model_type"] == "heuristics_imitation_v1"
        assert artifact["metadata"]["teacher_model"] == "RanktheTank"

    def test_unknown_teacher_raises_error(self):
        """Test that unknown teacher raises ValueError."""
        with pytest.raises(ValueError, match="Unknown teacher type"):
            train_and_save_model(
                contract="S",
                seed=42,
                teacher="unknown_teacher"
            )

    def test_backward_compatibility_default_teacher(self):
        """Test that default teacher is strict_raiser for backward compatibility."""
        artifact = train_and_save_model(contract="S", seed=42)

        # Should default to strict_raiser
        assert artifact["model_type"] == "strict_raiser_imitation_v1"


class TestDatasetLoading:
    """Test dataset loading functionality."""

    FIXTURE_PATH = Path("data/fixtures/bidding_dataset_tiny.jsonl")

    def test_fixture_exists(self):
        """Ensure the tiny fixture file exists."""
        assert self.FIXTURE_PATH.exists(), f"Fixture file not found: {self.FIXTURE_PATH}"

    def test_load_bidding_dataset_jsonl(self):
        """Test loading the JSONL dataset."""
        rows = load_bidding_dataset_jsonl(str(self.FIXTURE_PATH))

        assert isinstance(rows, list)
        assert len(rows) > 0

        # Check structure of loaded data
        for row in rows:
            assert isinstance(row, dict)
            # Should have the expected fields from the dataset schema
            assert "effective_bid_n" in row
            assert "effective_bid_contract" in row
            assert "current_high_bid" in row
            assert "hand_features" in row

    def test_load_empty_file(self):
        """Test loading an empty JSONL file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name

        try:
            rows = load_bidding_dataset_jsonl(temp_path)
            assert rows == []
        finally:
            Path(temp_path).unlink()

    def test_load_invalid_jsonl(self):
        """Test loading invalid JSONL raises appropriate error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("invalid json line\n")
            f.write("another invalid line\n")
            temp_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                load_bidding_dataset_jsonl(temp_path)
        finally:
            Path(temp_path).unlink()


class TestCLIIntegration:
    """Test CLI integration (basic smoke tests)."""

    def test_script_help(self):
        """Test that the CLI script shows help."""

        # This would require running the script, but since we're in a test environment
        # and the script has dependencies, we'll just check the script exists and is executable
        script_path = Path("scripts/train_bidder.py")
        assert script_path.exists()
        assert script_path.stat().st_mode & 0o111  # executable bit set
