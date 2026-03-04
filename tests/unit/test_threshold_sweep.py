"""Tests for threshold sweep CLI artifact parsing and selection."""

# Import functions under test using importlib since the script is in scripts/
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "run_threshold_sweep.py"
)
_spec = importlib.util.spec_from_file_location("run_threshold_sweep", str(_SCRIPT_PATH))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["run_threshold_sweep"] = _mod
_spec.loader.exec_module(_mod)

load_model_artifact = _mod.load_model_artifact
predict_tricks = _mod.predict_tricks
evaluate_threshold = _mod.evaluate_threshold
run_sweep = _mod.run_sweep
_aggregate_metrics = _mod._aggregate_metrics


def _make_hybrid_artifact(weights_by_cf, residual_variance):
    """Create a minimal hybrid artifact dict."""
    payoff_model = {}
    for cf, (weights, bias, feature_names) in weights_by_cf.items():
        payoff_model[cf] = {
            "weights": weights,
            "bias": bias,
            "feature_names": feature_names,
        }
    return {
        "artifact_type": "hybrid_olsa_v1",
        "payoff_model": payoff_model,
        "residual_variance": residual_variance,
        "rung_id": "test",
        "schema_version": 1,
    }


class TestLoadModelArtifact:
    def test_hybrid_artifact_extracts_models(self, tmp_path):
        """Hybrid artifact's payoff_model is normalized to 'models' with sigma."""
        artifact = _make_hybrid_artifact(
            weights_by_cf={
                "suit": ([1.0, 0.5], 0.0, ["bowers", "trump_count"]),
                "high": ([1.0], 0.0, ["offsuit_aces"]),
            },
            residual_variance={"suit": 4.0, "high": 9.0},
        )
        path = tmp_path / "artifact.json"
        path.write_text(json.dumps(artifact))

        loaded = load_model_artifact(str(path))

        assert "models" in loaded
        assert set(loaded["models"].keys()) == {"suit", "high"}
        # sigma = sqrt(residual_variance)
        assert loaded["models"]["suit"]["sigma"] == pytest.approx(2.0)
        assert loaded["models"]["high"]["sigma"] == pytest.approx(3.0)
        # Original model data preserved
        assert loaded["models"]["suit"]["weights"] == [1.0, 0.5]
        assert loaded["models"]["suit"]["feature_names"] == ["bowers", "trump_count"]

    def test_hybrid_artifact_missing_variance_defaults_zero(self, tmp_path):
        """If residual_variance is missing for a contract family, sigma=0."""
        artifact = _make_hybrid_artifact(
            weights_by_cf={"suit": ([1.0], 0.0, ["bowers"])},
            residual_variance={},  # No variance for suit
        )
        path = tmp_path / "artifact.json"
        path.write_text(json.dumps(artifact))

        loaded = load_model_artifact(str(path))
        assert loaded["models"]["suit"]["sigma"] == 0.0

    def test_non_hybrid_artifact_uses_models_key(self, tmp_path):
        """Non-hybrid artifacts that already have 'models' key pass through."""
        artifact = {
            "artifact_type": "olsa_v1",
            "models": {
                "suit": {
                    "weights": [1.0],
                    "bias": 0.0,
                    "feature_names": ["bowers"],
                    "sigma": 1.5,
                }
            },
        }
        path = tmp_path / "artifact.json"
        path.write_text(json.dumps(artifact))

        loaded = load_model_artifact(str(path))
        assert loaded["models"]["suit"]["sigma"] == 1.5


class TestRunSweepFailFast:
    def test_empty_models_raises(self):
        """Sweep raises ValueError when no model families found."""
        import pandas as pd

        artifact = {"artifact_type": "olsa_v1", "models": {}}
        df = pd.DataFrame(
            {"deal_id": [1], "contract_type": ["suit"], "tricks_won": [5]}
        )

        with pytest.raises(ValueError, match="No model families found"):
            run_sweep(artifact, df, [0.0, 1.0], seed=42)


class TestAggregateMetrics:
    def test_empty_parts_returns_zeros(self):
        """Empty parts list returns zeroed metrics."""
        result = _aggregate_metrics([])
        assert result["net_eppd"] == 0.0
        assert result["n_total"] == 0

    def test_single_part_passthrough(self):
        """Single contract family metrics pass through correctly."""
        parts = [
            {
                "contract_type": "suit",
                "n": 100,
                "metrics": {
                    "net_eppd": 1.5,
                    "bid_rate": 0.4,
                    "make_rate": 0.8,
                    "n_bid_hands": 40,
                    "n_total": 100,
                },
            }
        ]
        result = _aggregate_metrics(parts)
        assert result["net_eppd"] == pytest.approx(1.5)
        assert result["bid_rate"] == pytest.approx(0.4)
        assert result["n_total"] == 100


class TestPredictTricks:
    def test_linear_prediction(self):
        """predict_tricks applies weights + bias correctly."""
        import pandas as pd

        model = {
            "weights": [2.0, 1.0],
            "bias": 3.0,
            "feature_names": ["f1", "f2"],
        }
        df = pd.DataFrame({"f1": [1.0, 2.0], "f2": [0.5, 1.0]})
        mu = predict_tricks(model, ["f1", "f2"], df)
        # Row 0: 2.0*1.0 + 1.0*0.5 + 3.0 = 5.5
        # Row 1: 2.0*2.0 + 1.0*1.0 + 3.0 = 8.0
        np.testing.assert_allclose(mu, [5.5, 8.0])
