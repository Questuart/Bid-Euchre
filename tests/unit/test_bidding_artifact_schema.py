"""
Schema validation tests for bidding model artifact v1.

These tests ensure the bidding artifact schema is correctly validated
and catches invalid artifacts appropriately.
"""

import json
import tempfile
from pathlib import Path

import pytest

from bid_euchre.models.bidding_artifact import (
    VALID_CONTRACTS,
    dump_artifact,
    load_artifact,
    validate_artifact,
)


class TestBiddingArtifactSchema:
    """Test bidding artifact schema validation."""

    FIXTURE_PATH = Path("data/fixtures/bidding_artifact_v1_tiny.json")

    def test_fixture_exists(self):
        """Ensure the tiny fixture file exists."""
        assert self.FIXTURE_PATH.exists(), f"Fixture file not found: {self.FIXTURE_PATH}"

    def test_valid_fixture_loads_and_validates(self):
        """Test that the fixture artifact loads and validates successfully."""
        artifact = load_artifact(str(self.FIXTURE_PATH))

        # Should not raise an exception
        validate_artifact(artifact)

        # Check required fields are present
        assert artifact["schema_version"] == "1"
        assert artifact["model_type"] == "strict_raiser_imitation_v1"
        assert artifact["contract"] == "H"
        assert isinstance(artifact["model_params"], dict)
        assert "metadata" in artifact

    def test_rejects_missing_required_keys(self):
        """Test that artifacts with missing required keys are rejected."""
        valid_artifact = {
            "schema_version": "1",
            "model_type": "test",
            "contract": "H",
            "model_params": {"test": "value"}
        }

        # Test missing each required field
        for field in ["schema_version", "model_type", "contract", "model_params"]:
            invalid_artifact = {k: v for k, v in valid_artifact.items() if k != field}
            with pytest.raises(ValueError, match=f"Missing required fields.*{field}"):
                validate_artifact(invalid_artifact)

    def test_rejects_invalid_schema_version(self):
        """Test that artifacts with wrong schema version are rejected."""
        artifact = {
            "schema_version": "2",  # Wrong version
            "model_type": "test",
            "contract": "H",
            "model_params": {"test": "value"}
        }
        with pytest.raises(ValueError, match="Unsupported schema version: 2"):
            validate_artifact(artifact)

    def test_rejects_invalid_contract(self):
        """Test that artifacts with invalid contracts are rejected."""
        artifact = {
            "schema_version": "1",
            "model_type": "test",
            "contract": "INVALID",  # Invalid contract
            "model_params": {"test": "value"}
        }
        with pytest.raises(ValueError, match="Invalid contract 'INVALID'"):
            validate_artifact(artifact)

    def test_accepts_all_valid_contracts(self):
        """Test that all valid contracts are accepted."""
        for contract in VALID_CONTRACTS:
            artifact = {
                "schema_version": "1",
                "model_type": "test",
                "contract": contract,
                "model_params": {"test": "value"}
            }
            # Should not raise
            validate_artifact(artifact)

    def test_rejects_non_json_serializable_model_params(self):
        """Test that non-JSON-serializable model_params are rejected."""
        # Test with a set (not JSON-serializable)
        artifact = {
            "schema_version": "1",
            "model_type": "test",
            "contract": "H",
            "model_params": {"invalid": {1, 2, 3}}  # set is not JSON-serializable
        }
        with pytest.raises(ValueError, match="model_params must be JSON-serializable"):
            validate_artifact(artifact)

    def test_rejects_non_json_serializable_metadata(self):
        """Test that non-JSON-serializable metadata is rejected."""
        artifact = {
            "schema_version": "1",
            "model_type": "test",
            "contract": "H",
            "model_params": {"test": "value"},
            "metadata": {"invalid": {1, 2, 3}}  # set is not JSON-serializable
        }
        with pytest.raises(ValueError, match="metadata must be JSON-serializable"):
            validate_artifact(artifact)

    def test_load_artifact_file_not_found(self):
        """Test that load_artifact raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError, match="Artifact file not found"):
            load_artifact("nonexistent_file.json")

    def test_load_artifact_invalid_json(self):
        """Test that load_artifact raises ValueError for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                load_artifact(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_dump_artifact_creates_valid_file(self):
        """Test that dump_artifact creates a valid, loadable file."""
        artifact = {
            "schema_version": "1",
            "model_type": "test_model",
            "contract": "S",
            "model_params": {"param1": 1, "param2": [1, 2, 3]},
            "metadata": {"created": "test"}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            dump_artifact(artifact, temp_path)

            # File should exist
            assert Path(temp_path).exists()

            # Should be loadable and valid
            loaded = load_artifact(temp_path)
            assert loaded == artifact

        finally:
            Path(temp_path).unlink()

    def test_dump_artifact_rejects_invalid_artifact(self):
        """Test that dump_artifact validates before writing."""
        invalid_artifact = {"missing": "fields"}

        with pytest.raises(ValueError):
            dump_artifact(invalid_artifact, "dummy_path.json")

    def test_dump_artifact_stable_formatting(self):
        """Test that dump_artifact produces stable, sorted JSON output."""
        artifact = {
            "schema_version": "1",
            "model_type": "test",
            "contract": "C",
            "model_params": {"z_param": 1, "a_param": 2},
            "metadata": {"z_meta": "last", "a_meta": "first"}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            dump_artifact(artifact, temp_path)

            with open(temp_path, 'r') as f:
                content = f.read()

            # Parse and check it's valid JSON
            parsed = json.loads(content)
            assert parsed == artifact

            # Check formatting (sorted keys, indent=2)
            lines = content.strip().split('\n')
            assert lines[0] == '{'
            assert lines[1].startswith('  "contract":')
            # Keys should be in sorted order at top level

        finally:
            Path(temp_path).unlink()
