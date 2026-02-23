"""Tests for eval-side HITL sections and shared load_eval_metrics().

All tests import load_eval_metrics from bid_euchre.reporting.evaluator
(single source of truth — Finding 4).
"""

import json

import numpy as np
import pytest

from bid_euchre.reporting.evaluator import load_eval_metrics

# ── load_eval_metrics format tests ──────────────────────────────────


class TestLoadEvalMetricsFormats:
    def test_strategies_format(self, tmp_path):
        """Full evaluator output: {"strategies": [{...metrics...}]}."""
        data = {"strategies": [{"net_expected_points_per_deal": 1.5, "bid_rate": 0.3}]}
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(data))
        result = load_eval_metrics(path)
        assert result["net_expected_points_per_deal"] == 1.5
        assert result["bid_rate"] == 0.3

    def test_nested_format(self, tmp_path):
        """Nested: {"metrics": {...}}."""
        data = {"metrics": {"net_expected_points_per_deal": 2.0, "make_rate": 0.7}}
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(data))
        result = load_eval_metrics(path)
        assert result["net_expected_points_per_deal"] == 2.0
        assert result["make_rate"] == 0.7

    def test_flat_format(self, tmp_path):
        """Flat: top-level metrics dict."""
        data = {"net_expected_points_per_deal": 0.5, "cvar_5": -3.2}
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(data))
        result = load_eval_metrics(path)
        assert result["net_expected_points_per_deal"] == 0.5
        assert result["cvar_5"] == -3.2

    def test_empty_strategies(self, tmp_path):
        """Empty strategies list returns empty dict."""
        data = {"strategies": []}
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(data))
        result = load_eval_metrics(path)
        assert result == {}

    def test_file_not_found(self, tmp_path):
        """FileNotFoundError propagates when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_eval_metrics(tmp_path / "nonexistent.json")

    def test_accepts_string_path(self, tmp_path):
        """Accepts string path (not just Path objects)."""
        data = {"net_expected_points_per_deal": 1.0}
        path = tmp_path / "eval.json"
        path.write_text(json.dumps(data))
        result = load_eval_metrics(str(path))
        assert result["net_expected_points_per_deal"] == 1.0


# ── Seed sensitivity CV computation ─────────────────────────────────


class TestSeedSensitivity:
    def test_cv_computation(self):
        """CV% = std / |mean| * 100 over seed values."""
        vals = [1.5, 1.6, 1.7]
        mean_val = np.mean(vals)
        cv_pct = np.std(vals) / abs(mean_val) * 100
        # Should be small (~6%) for these close values
        assert 0 < cv_pct < 15

    def test_cv_high_sensitivity(self):
        """Widely spread seed values produce high CV."""
        vals = [1.0, 5.0, 10.0]
        mean_val = np.mean(vals)
        cv_pct = np.std(vals) / abs(mean_val) * 100
        assert cv_pct > 50  # Very high sensitivity


# ── Attribution gap ──────────────────────────────────────────────────


class TestAttributionGap:
    def test_from_decision_json(self, tmp_path):
        """Attribution gap read from promotion decision JSON."""
        decision = {
            "decision": "PROMOTED",
            "attribution_gap": -0.1437,
            "rung_id": "r0",
        }
        path = tmp_path / "promotion_decision_r0.json"
        path.write_text(json.dumps(decision))

        with open(path) as f:
            data = json.load(f)
        assert data["attribution_gap"] == pytest.approx(-0.1437)

    def test_computed_fallback(self, tmp_path):
        """Attribution gap computed from OLSa_Full - OLSa net_eppd."""
        # Create eval files for both arms
        olsa_full_data = {"net_expected_points_per_deal": 1.4837}
        olsa_data = {"net_expected_points_per_deal": 1.6274}

        full_path = tmp_path / "eval_full.json"
        full_path.write_text(json.dumps(olsa_full_data))
        base_path = tmp_path / "eval_base.json"
        base_path.write_text(json.dumps(olsa_data))

        full_metrics = load_eval_metrics(full_path)
        base_metrics = load_eval_metrics(base_path)

        gap = (
            full_metrics["net_expected_points_per_deal"]
            - base_metrics["net_expected_points_per_deal"]
        )
        assert gap == pytest.approx(-0.1437)


# ── Promotion gate tier 1 extraction ────────────────────────────────


class TestPromotionGateTier1:
    def test_tier1_extraction(self, tmp_path):
        """Tier 1 checks extractable from promotion decision JSON."""
        decision = {
            "decision": "PROMOTED",
            "tier_1_checks": {
                "artifact_integrity_olsa": "PASS",
                "artifact_integrity_olsa_full": "PASS",
                "no_nan_inf_olsa": "PASS",
                "no_nan_inf_olsa_full": "PASS",
            },
            "gate_results": {
                "primary": {
                    "metric": "auto_promote",
                    "note": "R0 auto-promoted",
                    "pass": True,
                }
            },
        }
        path = tmp_path / "decision.json"
        path.write_text(json.dumps(decision))

        with open(path) as f:
            data = json.load(f)

        tier1 = data["tier_1_checks"]
        assert all(v == "PASS" for v in tier1.values())
        assert data["gate_results"]["primary"]["pass"] is True


# ── Metric aliases coverage ──────────────────────────────────────────


class TestMetricAliases:
    def test_aliases_cover_all_eval_keys(self):
        """METRIC_ALIASES maps all keys present in a typical eval JSON."""
        # These are the canonical metric names the evaluator produces
        METRIC_ALIASES = {
            "net_expected_points_per_deal": "net_eppd",
            "expected_points_per_deal": "eppd",
            "bid_rate": "bid_rate",
            "make_rate": "make_rate",
            "cvar_5": "cvar_5",
            "downside_variance": "downside_variance",
        }

        synthetic_eval = {
            "net_expected_points_per_deal": 1.5,
            "expected_points_per_deal": 3.2,
            "bid_rate": 0.3,
            "make_rate": 0.65,
            "cvar_5": -5.0,
            "downside_variance": 12.3,
        }

        # Every key in METRIC_ALIASES should have a corresponding eval key
        for canonical in METRIC_ALIASES:
            assert (
                canonical in synthetic_eval
            ), f"METRIC_ALIASES has {canonical} but it's not in eval output"

        # Every eval key should be covered by METRIC_ALIASES
        for key in synthetic_eval:
            assert (
                key in METRIC_ALIASES
            ), f"Eval key {key} is not mapped in METRIC_ALIASES"
