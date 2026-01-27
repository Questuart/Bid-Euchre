"""Unit tests for B0 value model training."""

import json
import os
import tempfile

import numpy as np
import pytest

from bid_euchre.models.train_b0 import (
    B0Model,
    B0TrainingConfig,
    compute_metrics,
    extract_feature_matrix,
    load_b0_model,
    load_bidless_dataset,
    save_b0_model,
    train_b0_model,
    train_ols,
    train_ridge,
)


@pytest.fixture
def sample_bidless_rows():
    """Sample bidless dataset rows for testing."""
    return [
        {
            "hand_id": 0,
            "seat": 0,
            "hand_features": {
                "trump_count": 3,
                "offsuit_aces": 1,
                "hand_value": 2.5,
            },
        },
        {
            "hand_id": 0,
            "seat": 1,
            "hand_features": {
                "trump_count": 2,
                "offsuit_aces": 2,
                "hand_value": 2.0,
            },
        },
        {
            "hand_id": 1,
            "seat": 0,
            "hand_features": {
                "trump_count": 4,
                "offsuit_aces": 0,
                "hand_value": 3.0,
            },
        },
        {
            "hand_id": 1,
            "seat": 1,
            "hand_features": {
                "trump_count": 1,
                "offsuit_aces": 1,
                "hand_value": 1.5,
            },
        },
    ]


@pytest.fixture
def sample_jsonl_file(sample_bidless_rows):
    """Create temporary JSONL file with sample data."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False
    ) as f:
        for row in sample_bidless_rows:
            json.dump(row, f)
            f.write("\n")
        path = f.name

    yield path

    os.unlink(path)


class TestDataLoading:
    """Tests for data loading functions."""

    def test_load_bidless_dataset(self, sample_jsonl_file, sample_bidless_rows):
        """Test loading JSONL dataset."""
        rows = load_bidless_dataset(sample_jsonl_file)

        assert len(rows) == len(sample_bidless_rows)
        assert rows[0]["hand_id"] == 0
        assert "hand_features" in rows[0]

    def test_extract_feature_matrix(self, sample_bidless_rows):
        """Test extracting feature matrix from rows."""
        X, y, feature_names = extract_feature_matrix(sample_bidless_rows)

        assert X.shape[0] == len(sample_bidless_rows)
        assert len(y) == len(sample_bidless_rows)
        assert "trump_count" in feature_names
        assert "offsuit_aces" in feature_names
        # hand_value should not be in features (it's the target)
        assert "hand_value" not in feature_names

    def test_extract_feature_matrix_empty(self):
        """Test error on empty dataset."""
        with pytest.raises(ValueError, match="Empty dataset"):
            extract_feature_matrix([])


class TestTraining:
    """Tests for training functions."""

    def test_train_ols(self):
        """Test OLS training."""
        # Simple linear relationship: y = 2*x1 + 3*x2 + 1
        np.random.seed(42)
        X = np.random.randn(100, 2)
        y = 2 * X[:, 0] + 3 * X[:, 1] + 1

        weights, bias = train_ols(X, y)

        np.testing.assert_array_almost_equal(weights, [2, 3], decimal=5)
        np.testing.assert_almost_equal(bias, 1, decimal=5)

    def test_train_ridge(self):
        """Test Ridge training."""
        # Same setup as OLS but with regularization
        np.random.seed(42)
        X = np.random.randn(100, 2)
        y = 2 * X[:, 0] + 3 * X[:, 1] + 1

        weights, bias = train_ridge(X, y, alpha=0.01)

        # Should be close to OLS solution with small alpha
        np.testing.assert_array_almost_equal(weights, [2, 3], decimal=2)
        np.testing.assert_almost_equal(bias, 1, decimal=2)

    def test_compute_metrics(self):
        """Test metric computation."""
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.1, 2.1, 2.9, 4.1])

        metrics = compute_metrics(y_true, y_pred)

        assert "mse" in metrics
        assert "mae" in metrics
        assert "r2" in metrics
        assert metrics["mse"] < 0.1
        assert metrics["r2"] > 0.9


class TestB0Model:
    """Tests for B0Model class."""

    def test_predict(self):
        """Test single prediction."""
        model = B0Model(
            weights=np.array([2.0, 3.0]),
            bias=1.0,
            feature_names=["f1", "f2"],
            model_type="ridge",
            alpha=1.0,
        )

        result = model.predict({"f1": 1.0, "f2": 1.0})

        assert result == pytest.approx(6.0)  # 2*1 + 3*1 + 1

    def test_predict_batch(self):
        """Test batch prediction."""
        model = B0Model(
            weights=np.array([2.0, 3.0]),
            bias=1.0,
            feature_names=["f1", "f2"],
            model_type="ridge",
            alpha=1.0,
        )

        X = np.array([[1.0, 1.0], [0.0, 0.0]])
        result = model.predict_batch(X)

        np.testing.assert_array_almost_equal(result, [6.0, 1.0])

    def test_to_artifact_dict(self):
        """Test artifact serialization."""
        model = B0Model(
            weights=np.array([2.0, 3.0]),
            bias=1.0,
            feature_names=["f1", "f2"],
            model_type="ridge",
            alpha=1.0,
        )

        artifact = model.to_artifact_dict(seed=42)

        assert artifact["schema_version"] == "1"
        assert "b0_ridge" in artifact["model_type"]
        assert artifact["model_params"]["weights"] == [2.0, 3.0]
        assert artifact["model_params"]["bias"] == 1.0
        assert artifact["metadata"]["training_seed"] == 42


class TestModelPersistence:
    """Tests for model save/load."""

    def test_save_and_load_model(self):
        """Test round-trip save and load."""
        model = B0Model(
            weights=np.array([2.0, 3.0]),
            bias=1.0,
            feature_names=["f1", "f2"],
            model_type="ridge",
            alpha=1.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "model.json")

            save_b0_model(model, path, seed=42)
            loaded = load_b0_model(path)

            np.testing.assert_array_almost_equal(
                loaded.weights, model.weights
            )
            assert loaded.bias == model.bias
            assert loaded.feature_names == model.feature_names


class TestEndToEnd:
    """End-to-end training tests."""

    def test_train_b0_model(self, sample_jsonl_file):
        """Test full training pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "model.json")

            config = B0TrainingConfig(
                dataset_path=sample_jsonl_file,
                output_path=output_path,
                seed=42,
                model_type="ridge",
                alpha=1.0,
                test_split=0.25,  # Use 1 sample for test
            )

            model, metrics = train_b0_model(config)

            assert model is not None
            assert "train" in metrics
            assert "test" in metrics
            assert len(model.feature_names) > 0
