"""
Tests for linear_regression bidding artifacts fail-fast behavior.

Ensures that linear_regression artifacts raise NotImplementedError instead
of silently passing, preventing accidental benchmarking of placeholder models.
"""

import tempfile
from pathlib import Path

import pytest

from bid_euchre.models.bidding_artifact import dump_artifact
from bid_euchre.strategy.bidding import ArtifactBidder


class TestLinearRegressionReserved:
    """Test that linear_regression artifacts fail fast with clear error."""

    def test_linear_regression_artifact_fails_at_init(self):
        """Test that instantiating ArtifactBidder with linear_regression raises NotImplementedError."""
        # Create a linear_regression artifact
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
                "description": "Test linear regression artifact"
            }
        }

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            dump_artifact(artifact, temp_path)

            # Should raise NotImplementedError
            with pytest.raises(NotImplementedError, match="linear_regression artifacts are reserved for future work"):
                ArtifactBidder(temp_path)

        finally:
            Path(temp_path).unlink()

    def test_error_message_mentions_supported_alternatives(self):
        """Test that the error message suggests supported alternatives."""
        artifact = {
            "schema_version": "1",
            "model_type": "linear_regression",
            "contract": "H",
            "model_params": {
                "coefficients": [0.1],
                "intercept": 0.0
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            dump_artifact(artifact, temp_path)

            with pytest.raises(NotImplementedError) as exc_info:
                ArtifactBidder(temp_path)

            error_msg = str(exc_info.value)
            assert "strict_raiser_imitation_v1" in error_msg
            assert "heuristics_imitation_v1" in error_msg
            assert "silently pass" in error_msg

        finally:
            Path(temp_path).unlink()
