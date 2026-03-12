"""Tests for the action-value artifact behavioral validation script."""

import json


class TestCheckR2Quality:
    def test_low_r2_returns_warnings(self, tmp_path):
        from scripts.internal.validate_action_value_artifact import check_r2_quality

        artifact = {
            "schema_version": "action_value_olsa_v1",
            "models": {
                "suit": {"r_squared": 0.18},
                "high": {"r_squared": 0.55},
                "low": {"r_squared": 0.55},
                "pass": {"r_squared": 0.04},
            },
        }
        path = tmp_path / "artifact.json"
        path.write_text(json.dumps(artifact))

        warnings = check_r2_quality(str(path))
        assert len(warnings) == 1
        assert "suit" in warnings[0]
        assert "0.18" in warnings[0]

    def test_all_good_r2_no_warnings(self, tmp_path):
        from scripts.internal.validate_action_value_artifact import check_r2_quality

        artifact = {
            "schema_version": "action_value_olsa_v1",
            "models": {
                "suit": {"r_squared": 0.56},
                "high": {"r_squared": 0.53},
                "low": {"r_squared": 0.51},
                "pass": {"r_squared": 0.04},  # pass not checked
            },
        }
        path = tmp_path / "artifact.json"
        path.write_text(json.dumps(artifact))

        warnings = check_r2_quality(str(path))
        assert len(warnings) == 0

    def test_multiple_low_r2_returns_multiple_warnings(self, tmp_path):
        from scripts.internal.validate_action_value_artifact import check_r2_quality

        artifact = {
            "schema_version": "action_value_olsa_v1",
            "models": {
                "suit": {"r_squared": 0.10},
                "high": {"r_squared": 0.15},
                "low": {"r_squared": 0.20},
                "pass": {"r_squared": 0.01},
            },
        }
        path = tmp_path / "artifact.json"
        path.write_text(json.dumps(artifact))

        warnings = check_r2_quality(str(path))
        assert len(warnings) == 3  # suit, high, low all below threshold
