"""Tests for action-value artifact behavioral validation.

Tests the validation gate in scripts/internal/validate_action_value_artifact.py
and the load-time behavioral checks in ActionValueBidder/GBTActionValueBidder.
"""

import json

# Import validator from scripts path
import sys
import tempfile
from pathlib import Path

import pytest

from bid_euchre.strategy.bidding import (
    ACTION_FEATURE_NAMES,
    STATE_FEATURE_NAMES,
    ActionValueBidder,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))
from validate_action_value_artifact import (
    probe_ols_artifact,
    validate_artifact,
    validate_behavioral,
    validate_quality,
    validate_structural,
)

# ── Test Fixtures ──────────────────────────────────────────


def _make_valid_artifact(
    pass_intercept: float = 4.0,
    suit_intercept: float = -3.0,
    high_intercept: float = -1.0,
    low_intercept: float = -1.5,
    suit_r2: float = 0.55,
    high_r2: float = 0.53,
    low_r2: float = 0.51,
    pass_r2: float = 0.04,
) -> dict:
    """Create a valid action_value_olsa_v1 artifact with controllable behavior.

    By default, creates a realistic artifact that:
    - Bids in multiple contract types (different intercepts per family)
    - Prefers moderate bid levels (concave bid_n response)
    - Sometimes passes (pass intercept is competitive for weak hands)
    - Uses hand features to differentiate (bowers/trump_count matter)
    """
    n_state = len(STATE_FEATURE_NAMES)
    n_action = len(ACTION_FEATURE_NAMES)

    # Feature indices we want to give non-zero coefficients
    bowers_idx = list(STATE_FEATURE_NAMES).index("bowers")
    trump_count_idx = list(STATE_FEATURE_NAMES).index("trump_count")
    offsuit_aces_idx = list(STATE_FEATURE_NAMES).index("offsuit_aces")
    is_high_idx = list(STATE_FEATURE_NAMES).index("is_high")
    is_low_idx = list(STATE_FEATURE_NAMES).index("is_low")

    def _bid_model(intercept: float, r2: float, is_suit: bool = False) -> dict:
        coeffs = [0.0] * n_state + [0.0] * n_action
        # Hand features that influence predictions
        coeffs[bowers_idx] = 1.5 if is_suit else 0.3
        coeffs[trump_count_idx] = 0.8 if is_suit else 0.1
        coeffs[offsuit_aces_idx] = 0.6
        coeffs[is_high_idx] = 3.0
        coeffs[is_low_idx] = 2.5
        # Concave bid response: positive linear, negative quadratic
        # Peak around bid 4-5, so model prefers moderate bids
        coeffs[n_state] = 1.0  # bid_n
        coeffs[n_state + 1] = -0.12  # bid_n_sq (peak at ~4.2)
        return {
            "coefficients": coeffs,
            "intercept": intercept,
            "feature_names": list(STATE_FEATURE_NAMES) + list(ACTION_FEATURE_NAMES),
            "r_squared": r2,
            "mae": 2.5,
            "n_train": 50000,
            "n_val": 5000,
        }

    def _pass_model(intercept: float, r2: float) -> dict:
        coeffs = [0.0] * n_state
        # Strong hands decrease pass value (you should bid, not pass)
        coeffs[bowers_idx] = -2.0
        coeffs[trump_count_idx] = -0.8
        coeffs[offsuit_aces_idx] = -0.5
        return {
            "coefficients": coeffs,
            "intercept": intercept,
            "feature_names": list(STATE_FEATURE_NAMES),
            "r_squared": r2,
            "mae": 3.0,
            "n_train": 50000,
            "n_val": 5000,
        }

    return {
        "schema_version": "action_value_olsa_v1",
        "target": "net_points",
        "risk_mode": "neutral",
        "continuation_policy": "hybrid_r0_full",
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": "full",
        "models": {
            "suit": _bid_model(suit_intercept, suit_r2, is_suit=True),
            "high": _bid_model(high_intercept, high_r2),
            "low": _bid_model(low_intercept, low_r2),
            "pass": _pass_model(pass_intercept, pass_r2),
        },
        "metadata": {
            "n_deals": 10000,
            "training_seed": 42,
            "arm": "full",
            "context_features": [
                "partner_bid_level",
                "partner_passed",
                "partner_suit_match",
            ],
            "git_sha": "abc123",
            "created_at_utc": "2026-03-12T00:00:00Z",
        },
    }


def _make_pathological_artifact() -> dict:
    """Create an artifact that always bids 10 (the known failure mode).

    Uses large positive bid_n coefficient so that bid-10 always wins argmax.
    This simulates the stale artifact with R²=0.18 that caused the GBT
    comparison contamination.
    """
    n_state = len(STATE_FEATURE_NAMES)
    n_action = len(ACTION_FEATURE_NAMES)

    def _bid_model() -> dict:
        coeffs = [0.0] * n_state + [0.0] * n_action
        # Large positive bid_n coefficient: bid-10 always wins argmax
        coeffs[n_state] = 5.0  # bid_n
        coeffs[n_state + 1] = 0.0  # bid_n_sq
        return {
            "coefficients": coeffs,
            "intercept": 0.0,
            "feature_names": list(STATE_FEATURE_NAMES) + list(ACTION_FEATURE_NAMES),
            "r_squared": 0.18,
            "mae": 5.0,
            "n_train": 10000,
            "n_val": 1000,
        }

    def _pass_model() -> dict:
        return {
            "coefficients": [0.0] * n_state,
            "intercept": -100.0,  # Pass always loses to any bid
            "feature_names": list(STATE_FEATURE_NAMES),
            "r_squared": 0.02,
            "mae": 6.0,
            "n_train": 10000,
            "n_val": 1000,
        }

    return {
        "schema_version": "action_value_olsa_v1",
        "target": "net_points",
        "risk_mode": "neutral",
        "continuation_policy": "hybrid_r0_full",
        "action_features": list(ACTION_FEATURE_NAMES),
        "feature_set": "full",
        "models": {
            "suit": _bid_model(),
            "high": _bid_model(),
            "low": _bid_model(),
            "pass": _pass_model(),
        },
        "metadata": {
            "n_deals": 1000,
            "training_seed": 42,
            "arm": "full",
            "context_features": [],
            "git_sha": "stale123",
            "created_at_utc": "2025-01-01T00:00:00Z",
        },
    }


def _write_artifact(artifact: dict) -> str:
    """Write artifact to temp file, return path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(artifact, f)
    f.close()
    return f.name


# ── Structural Validation ──────────────────────────────────


class TestStructuralValidation:
    def test_valid_artifact_passes(self):
        artifact = _make_valid_artifact()
        result = validate_structural(artifact, "/tmp/test.json")
        assert result.passed

    def test_wrong_schema_fails(self):
        artifact = _make_valid_artifact()
        artifact["schema_version"] = "hybrid_olsa_v1"
        result = validate_structural(artifact, "/tmp/test.json")
        assert not result.passed

    def test_missing_model_family_fails(self):
        artifact = _make_valid_artifact()
        del artifact["models"]["pass"]
        result = validate_structural(artifact, "/tmp/test.json")
        assert not result.passed

    def test_missing_feature_names_fails(self):
        artifact = _make_valid_artifact()
        del artifact["models"]["suit"]["feature_names"]
        result = validate_structural(artifact, "/tmp/test.json")
        assert not result.passed

    def test_missing_metadata_fields_fails(self):
        artifact = _make_valid_artifact()
        del artifact["metadata"]["training_seed"]
        result = validate_structural(artifact, "/tmp/test.json")
        assert not result.passed

    def test_missing_target_fails(self):
        artifact = _make_valid_artifact()
        del artifact["target"]
        result = validate_structural(artifact, "/tmp/test.json")
        assert not result.passed


# ── Quality Validation ─────────────────────────────────────


class TestQualityValidation:
    def test_valid_r2_passes(self):
        artifact = _make_valid_artifact()
        result = validate_quality(artifact)
        assert result.passed

    def test_low_suit_r2_fails(self):
        artifact = _make_valid_artifact(suit_r2=0.15)
        result = validate_quality(artifact)
        assert not result.passed
        failures = [c for c in result.checks if not c["passed"]]
        assert any("suit" in f["name"] for f in failures)

    def test_pathological_r2_fails(self):
        artifact = _make_pathological_artifact()
        result = validate_quality(artifact)
        assert not result.passed


# ── Behavioral Validation ──────────────────────────────────


class TestBehavioralValidation:
    def test_valid_artifact_passes_behavioral(self):
        artifact = _make_valid_artifact()
        path = _write_artifact(artifact)
        result, stats = validate_behavioral(artifact, path)
        assert result.passed
        assert stats.avg_bid < 8.0
        assert stats.bid_10_rate < 0.30

    def test_pathological_artifact_fails_behavioral(self):
        """Negative control: the known-bad 'always bid 10' artifact fails."""
        artifact = _make_pathological_artifact()
        path = _write_artifact(artifact)
        result, stats = validate_behavioral(artifact, path)
        assert not result.passed
        # Should fail on avg_bid, bid_10_rate, and/or pass_rate
        failures = {c["name"] for c in result.checks if not c["passed"]}
        assert len(failures) > 0

    def test_pathological_has_high_avg_bid(self):
        artifact = _make_pathological_artifact()
        stats = probe_ols_artifact(artifact)
        assert stats.avg_bid >= 8.0

    def test_pathological_has_high_bid_10_rate(self):
        artifact = _make_pathological_artifact()
        stats = probe_ols_artifact(artifact)
        assert stats.bid_10_rate >= 0.30

    def test_pathological_has_low_pass_rate(self):
        artifact = _make_pathological_artifact()
        stats = probe_ols_artifact(artifact)
        assert stats.pass_rate <= 0.01

    def test_valid_artifact_has_contract_diversity(self):
        artifact = _make_valid_artifact()
        stats = probe_ols_artifact(artifact)
        assert stats.contract_diversity >= 2


# ── Full Validation Pipeline ──────────────────────────────


class TestFullValidation:
    def test_valid_artifact_passes_all(self):
        artifact = _make_valid_artifact()
        path = _write_artifact(artifact)
        passed, report = validate_artifact(path)
        assert passed
        assert report["structural"]["n_failed"] == 0
        assert report["quality"]["n_failed"] == 0
        assert report["behavioral"]["n_failed"] == 0

    def test_pathological_artifact_fails(self):
        """End-to-end: the known-bad artifact is rejected."""
        artifact = _make_pathological_artifact()
        path = _write_artifact(artifact)
        passed, report = validate_artifact(path)
        assert not passed

    def test_nonexistent_path_fails(self):
        passed, report = validate_artifact("/nonexistent/path.json")
        assert not passed
        assert "error" in report

    def test_report_includes_behavioral_stats(self):
        artifact = _make_valid_artifact()
        path = _write_artifact(artifact)
        _, report = validate_artifact(path)
        stats = report["behavioral_stats"]
        assert "avg_bid" in stats
        assert "pass_rate" in stats
        assert "bid_10_rate" in stats
        assert stats["n_observations"] > 0


# ── Load-Time Behavioral Check ────────────────────────────


class TestLoadTimeBehavioralCheck:
    def test_valid_artifact_loads_with_check(self):
        """A valid artifact passes the load-time behavioral check."""
        artifact = _make_valid_artifact()
        path = _write_artifact(artifact)
        bidder = ActionValueBidder(artifact_path=path, skip_behavioral_check=False)
        assert bidder is not None

    def test_pathological_artifact_rejected_at_load(self):
        """A pathological artifact is rejected at load time."""
        artifact = _make_pathological_artifact()
        path = _write_artifact(artifact)
        with pytest.raises(ValueError, match="Behavioral sanity check FAILED"):
            ActionValueBidder(artifact_path=path, skip_behavioral_check=False)

    def test_skip_behavioral_check_bypasses(self):
        """skip_behavioral_check=True allows loading pathological artifacts."""
        artifact = _make_pathological_artifact()
        path = _write_artifact(artifact)
        bidder = ActionValueBidder(artifact_path=path, skip_behavioral_check=True)
        assert bidder is not None

    def test_zero_coefficient_artifact_passes_check(self):
        """Zero-coefficient test fixtures pass the behavioral check.

        The check compares bid-10 vs bid-1 predictions. With zero coefficients
        and negative bid_n coefficient, bid-1 has higher predicted value than
        bid-10, so the check passes.
        """
        artifact = _make_valid_artifact()
        path = _write_artifact(artifact)
        # This should not raise
        ActionValueBidder(artifact_path=path, skip_behavioral_check=False)
