"""Unit tests for reporting.validation module."""

import os
import tempfile

import pytest

from bid_euchre.reporting.validation import (
    generate_validation_plots,
    plot_feature_correlation,
    plot_feature_distributions,
    plot_hand_value_by_contract,
)


@pytest.fixture
def sample_features_by_contract():
    """Sample feature data grouped by contract type."""
    return {
        "suit_H": [
            {"trump_count": 3, "offsuit_aces": 1, "hand_value": 2.5},
            {"trump_count": 2, "offsuit_aces": 2, "hand_value": 2.0},
            {"trump_count": 4, "offsuit_aces": 0, "hand_value": 3.0},
        ],
        "high": [
            {"trump_count": 0, "offsuit_aces": 3, "hand_value": 2.8},
            {"trump_count": 0, "offsuit_aces": 2, "hand_value": 2.2},
        ],
        "low": [
            {"trump_count": 0, "offsuit_aces": 0, "hand_value": 1.5},
            {"trump_count": 0, "offsuit_aces": 1, "hand_value": 1.0},
        ],
    }


def test_plot_feature_distributions(sample_features_by_contract):
    """Test feature distribution plot generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = plot_feature_distributions(sample_features_by_contract, tmpdir)

        assert path.endswith("feature_distributions.png")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0


def test_plot_feature_correlation(sample_features_by_contract):
    """Test feature correlation plot generation."""
    # Flatten features
    all_features = []
    for features_list in sample_features_by_contract.values():
        all_features.extend(features_list)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = plot_feature_correlation(all_features, tmpdir)

        assert path.endswith("feature_correlation.png")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0


def test_plot_hand_value_by_contract(sample_features_by_contract):
    """Test hand value box plot generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = plot_hand_value_by_contract(sample_features_by_contract, tmpdir)

        assert path.endswith("hand_value_by_contract.png")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0


def test_generate_validation_plots(sample_features_by_contract):
    """Test generation of all validation plots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        plots = generate_validation_plots(sample_features_by_contract, tmpdir)

        assert "feature_distributions" in plots
        assert "feature_correlation" in plots
        assert "hand_value_by_contract" in plots

        for name, path in plots.items():
            assert os.path.exists(path), f"Missing plot: {name}"
            assert os.path.getsize(path) > 0, f"Empty plot: {name}"


def test_empty_features():
    """Test handling of empty feature data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Empty dict should not crash
        plots = generate_validation_plots({}, tmpdir)
        # May produce empty dict or partial plots
        assert isinstance(plots, dict)


def test_single_feature():
    """Test handling of single feature (can't compute correlation)."""
    features = [{"single_feature": 1.0}]

    with tempfile.TemporaryDirectory() as tmpdir:
        # Should return empty string (can't compute correlation with 1 feature)
        path = plot_feature_correlation(features, tmpdir)
        assert path == ""
