"""Unit tests for the threshold calibration script.

Tests the core functions from calibrate_arc_d_thresholds.py:
extract_null_signal, extract_cvar5_null, calibrate_thresholds, drift_check.
"""

import importlib.util
from pathlib import Path

import numpy as np

# Import calibration script via importlib.util (scripts/internal/ has no __init__.py)
_CALIBRATE_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "calibrate_arc_d_thresholds.py"
)
_spec = importlib.util.spec_from_file_location(
    "calibrate_arc_d_thresholds", _CALIBRATE_SCRIPT
)
_calibrate_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_calibrate_mod)

extract_null_signal = _calibrate_mod.extract_null_signal
extract_cvar5_null = _calibrate_mod.extract_cvar5_null
calibrate_thresholds = _calibrate_mod.calibrate_thresholds
drift_check = _calibrate_mod.drift_check


def _make_h2h_summary(n_bidders: int = 7) -> dict:
    """Create a synthetic H2H battery summary with n_bidders.

    Creates self-play diagonals (near-zero deltas) and cross-play matchups.
    For 7 bidders: 7 self-play + C(7,2)=21 pairs * 2 directions = 42 cross-play.
    """
    bidders = [f"bidder_{i}" for i in range(n_bidders)]
    matchups = {}

    # Self-play diagonals (small deltas centered at 0)
    rng = np.random.default_rng(42)
    for b in bidders:
        key = f"{b}_vs_{b}"
        matchups[key] = {
            "net_eppd_delta": float(rng.normal(0, 0.005)),
            "cvar_5": float(rng.normal(-0.5, 0.05)),
        }

    # Cross-play matchups
    for i, a in enumerate(bidders):
        for j, b in enumerate(bidders):
            if i == j:
                continue
            key = f"{a}_vs_{b}"
            # Make deltas somewhat symmetric: delta(A_vs_B) ~ -delta(B_vs_A) + noise
            base_delta = rng.normal(0, 0.03)
            matchups[key] = {
                "net_eppd_delta": float(base_delta),
                "cvar_5": float(rng.normal(-0.5, 0.05)),
            }

    return {"matchups": matchups}


class TestExtractNullSignal:
    """Tests for extract_null_signal()."""

    def test_null_signal_shape_7_bidders(self):
        """7 self-play + 21 seat-swap pairs = 28 null values."""
        h2h = _make_h2h_summary(n_bidders=7)
        null_signal = extract_null_signal(h2h)

        # 7 self-play absolute deltas
        assert len(null_signal["self_play_deltas"]) == 7
        # C(7,2) = 21 seat-swap residuals
        assert len(null_signal["seat_swap_residuals"]) == 21
        # Total = 7 + 21 = 28
        assert len(null_signal["null_abs_values"]) == 28

    def test_null_signal_shape_3_bidders(self):
        """3 self-play + 3 seat-swap pairs = 6 null values."""
        h2h = _make_h2h_summary(n_bidders=3)
        null_signal = extract_null_signal(h2h)

        assert len(null_signal["self_play_deltas"]) == 3
        assert len(null_signal["seat_swap_residuals"]) == 3  # C(3,2) = 3
        assert len(null_signal["null_abs_values"]) == 6

    def test_self_play_deltas_near_zero(self):
        """Self-play deltas should be near zero for synthetic data."""
        h2h = _make_h2h_summary(n_bidders=7)
        null_signal = extract_null_signal(h2h)

        for delta in null_signal["self_play_deltas"]:
            assert abs(delta) < 0.1, f"Self-play delta too large: {delta}"

    def test_all_null_abs_non_negative(self):
        """All null_abs_values should be >= 0."""
        h2h = _make_h2h_summary(n_bidders=7)
        null_signal = extract_null_signal(h2h)

        for v in null_signal["null_abs_values"]:
            assert v >= 0, f"Negative null_abs value: {v}"

    def test_empty_matchups(self):
        """Empty matchups -> empty null signal."""
        null_signal = extract_null_signal({"matchups": {}})
        assert len(null_signal["null_abs_values"]) == 0
        assert len(null_signal["self_play_deltas"]) == 0
        assert len(null_signal["seat_swap_residuals"]) == 0


class TestExtractCvar5Null:
    """Tests for extract_cvar5_null()."""

    def test_cvar5_residuals_count(self):
        """C(7,2) = 21 pairwise cvar5 residuals for 7 bidders."""
        h2h = _make_h2h_summary(n_bidders=7)
        cvar5_null = extract_cvar5_null(h2h)

        assert len(cvar5_null["cvar5_residuals"]) == 21

    def test_cvar5_residual_std_positive(self):
        """cvar5_residual_std should be positive for non-trivial data."""
        h2h = _make_h2h_summary(n_bidders=7)
        cvar5_null = extract_cvar5_null(h2h)

        assert cvar5_null["cvar5_residual_std"] > 0

    def test_empty_matchups_zero_std(self):
        """Empty matchups -> zero cvar5_residual_std."""
        cvar5_null = extract_cvar5_null({"matchups": {}})
        assert cvar5_null["cvar5_residual_std"] == 0.0
        assert len(cvar5_null["cvar5_residuals"]) == 0


class TestCalibrateThresholds:
    """Tests for calibrate_thresholds()."""

    def test_calibrate_deterministic(self):
        """Fixed input -> fixed output."""
        h2h = _make_h2h_summary(n_bidders=7)
        null1 = extract_null_signal(h2h)
        cvar1 = extract_cvar5_null(h2h)
        result1 = calibrate_thresholds(null1, cvar1, seed=42)

        null2 = extract_null_signal(h2h)
        cvar2 = extract_cvar5_null(h2h)
        result2 = calibrate_thresholds(null2, cvar2, seed=42)

        assert result1["thresholds"] == result2["thresholds"]
        assert (
            result1["calibration_details"]["q95_null_abs"]
            == result2["calibration_details"]["q95_null_abs"]
        )

    def test_quantile_math(self):
        """Known input values -> correct percentiles."""
        # Create known null signal: values from 0 to 0.99 in steps of 0.01
        null_signal = {
            "null_abs_values": [i * 0.01 for i in range(100)],
            "self_play_deltas": [0.0] * 7,
            "seat_swap_residuals": [i * 0.01 for i in range(93)],
        }
        cvar5_null = {"cvar5_residuals": [0.01, 0.02, 0.03], "cvar5_residual_std": 0.01}

        result = calibrate_thresholds(null_signal, cvar5_null, seed=42)

        # 95th percentile of [0, 0.01, ..., 0.99] = ~0.9405
        q95 = result["calibration_details"]["q95_null_abs"]
        assert abs(q95 - 0.9405) < 0.01, f"q95={q95}, expected ~0.9405"

        # delta_floor = max(0.01, q95) = q95 since q95 >> 0.01
        assert result["thresholds"]["delta_floor"] > 0.9

    def test_delta_floor_minimum(self):
        """delta_floor respects 0.01 floor even when q95 is tiny."""
        null_signal = {
            "null_abs_values": [0.001, 0.002, 0.003, 0.004, 0.005],
            "self_play_deltas": [0.001, 0.002],
            "seat_swap_residuals": [0.003, 0.004, 0.005],
        }
        cvar5_null = {"cvar5_residuals": [0.01], "cvar5_residual_std": 0.01}

        result = calibrate_thresholds(null_signal, cvar5_null, seed=42)
        assert result["thresholds"]["delta_floor"] >= 0.01

    def test_regression_threshold_minimum(self):
        """regression_threshold respects 0.05 floor."""
        null_signal = {
            "null_abs_values": [0.001] * 28,
            "self_play_deltas": [0.001] * 7,
            "seat_swap_residuals": [0.001] * 21,
        }
        cvar5_null = {"cvar5_residuals": [0.01], "cvar5_residual_std": 0.01}

        result = calibrate_thresholds(null_signal, cvar5_null, seed=42)
        assert result["thresholds"]["regression_threshold"] >= 0.05

    def test_cvar5_tolerance_formula(self):
        """cvar5_tolerance = max(0.05, 2.0 * std)."""
        # Case 1: std small enough that floor applies
        null_signal = {
            "null_abs_values": [0.01] * 10,
            "self_play_deltas": [0.01] * 5,
            "seat_swap_residuals": [0.01] * 5,
        }
        cvar5_null = {"cvar5_residuals": [0.01, 0.02], "cvar5_residual_std": 0.02}

        result = calibrate_thresholds(null_signal, cvar5_null, seed=42)
        # 2.0 * 0.02 = 0.04 < 0.05 floor
        assert result["thresholds"]["cvar5_tolerance"] == 0.05

        # Case 2: std large enough to exceed floor
        cvar5_null_large = {
            "cvar5_residuals": [0.1, 0.2],
            "cvar5_residual_std": 0.10,
        }
        result2 = calibrate_thresholds(null_signal, cvar5_null_large, seed=42)
        # 2.0 * 0.10 = 0.20 > 0.05 floor
        assert abs(result2["thresholds"]["cvar5_tolerance"] - 0.20) < 0.001

    def test_schema_and_metadata(self):
        """Output has correct schema and metadata fields."""
        h2h = _make_h2h_summary(n_bidders=3)
        null_signal = extract_null_signal(h2h)
        cvar5_null = extract_cvar5_null(h2h)

        result = calibrate_thresholds(null_signal, cvar5_null, seed=42)

        assert result["schema"] == "gate_thresholds_v1"
        assert result["calibration_method"] == "null_distribution_quantiles"
        assert result["seed"] == 42
        assert "thresholds" in result
        assert "calibration_details" in result
        assert result["calibration_details"]["null_distribution_n"] == 6  # 3 + C(3,2)

    def test_empty_null_signal_raises(self):
        """Empty null signal raises ValueError."""
        import pytest

        null_signal = {
            "null_abs_values": [],
            "self_play_deltas": [],
            "seat_swap_residuals": [],
        }
        cvar5_null = {"cvar5_residuals": [], "cvar5_residual_std": 0.0}

        with pytest.raises(ValueError, match="No null signal"):
            calibrate_thresholds(null_signal, cvar5_null, seed=42)


class TestDriftCheck:
    """Tests for drift_check()."""

    def test_drift_within_threshold(self):
        """Drift <= 25% -> no recalibration needed."""
        h2h_quick = _make_h2h_summary(n_bidders=7)
        null_quick = extract_null_signal(h2h_quick)
        cvar5_quick = extract_cvar5_null(h2h_quick)
        quick_thresholds = calibrate_thresholds(null_quick, cvar5_quick, seed=42)

        # Use same data for FULL (drift = 0)
        h2h_full = _make_h2h_summary(n_bidders=7)
        result = drift_check(quick_thresholds, h2h_full)

        assert result["drift_ratio"] <= 0.25
        assert not result["needs_recalibration"]

    def test_drift_exceeds_threshold(self):
        """Drift > 25% -> needs recalibration."""
        # Create QUICK thresholds from small data
        quick_null = {
            "null_abs_values": [0.01] * 28,
            "self_play_deltas": [0.01] * 7,
            "seat_swap_residuals": [0.01] * 21,
        }
        quick_cvar5 = {"cvar5_residuals": [0.01] * 21, "cvar5_residual_std": 0.01}
        quick_thresholds = calibrate_thresholds(quick_null, quick_cvar5, seed=42)

        # Create FULL data with much larger null signal
        full_matchups = {}
        bidders = [f"b{i}" for i in range(7)]
        for b in bidders:
            full_matchups[f"{b}_vs_{b}"] = {
                "net_eppd_delta": 0.10,  # Much larger than QUICK
                "cvar_5": -0.5,
            }
        for i, a in enumerate(bidders):
            for j, b in enumerate(bidders):
                if i != j:
                    full_matchups[f"{a}_vs_{b}"] = {
                        "net_eppd_delta": 0.10,
                        "cvar_5": -0.5,
                    }
        full_summary = {"matchups": full_matchups}

        result = drift_check(quick_thresholds, full_summary)
        assert result["drift_ratio"] > 0.25
        assert result["needs_recalibration"]

    def test_drift_check_empty_full(self):
        """Empty FULL data -> drift_ratio = 0, no recalibration."""
        quick_null = {
            "null_abs_values": [0.01] * 10,
            "self_play_deltas": [0.01] * 5,
            "seat_swap_residuals": [0.01] * 5,
        }
        quick_cvar5 = {"cvar5_residuals": [0.01], "cvar5_residual_std": 0.01}
        quick_thresholds = calibrate_thresholds(quick_null, quick_cvar5, seed=42)

        result = drift_check(quick_thresholds, {"matchups": {}})
        assert result["drift_ratio"] == 0.0
        assert not result["needs_recalibration"]
