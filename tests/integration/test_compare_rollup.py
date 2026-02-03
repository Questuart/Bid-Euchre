"""
Integration tests for compare_rollup.py exit code behavior.

Tests various scenarios:
- Match within tolerance -> exit 0
- Metric delta beyond tolerance -> exit 1
- Unexpected config -> exit 1
- Missing expected config -> exit 1
"""

import json
import subprocess
import sys
from pathlib import Path


class TestCompareRollupExitCodes:
    """Test compare_rollup.py exit code behavior with various scenarios."""

    def test_match_within_tolerance_exits_zero(self, tmp_path: Path) -> None:
        """Test that matching metrics within tolerance exits with code 0."""
        # Create rollup with exact match
        rollup_data = {
            "summary": [
                {
                    "config": "baseline_greedy.yaml",
                    "status": "ok",
                    "avg_tricks": 5.0
                }
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture with same value
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0
                }
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 0
        assert "No drift detected" in result.stdout

    def test_metric_drift_beyond_tolerance_exits_one(self, tmp_path: Path) -> None:
        """Test that metric drift beyond tolerance exits with code 1."""
        # Create rollup with drifted value
        rollup_data = {
            "summary": [
                {
                    "config": "baseline_greedy.yaml",
                    "status": "ok",
                    "avg_tricks": 5.05  # 0.05 difference
                }
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture with smaller tolerance
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,  # 0.05 > 0.01, so should fail
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0
                }
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 1
        assert "DRIFT: baseline_greedy.yaml" in result.stdout

    def test_unexpected_config_exits_one(self, tmp_path: Path) -> None:
        """Test that unexpected configs in rollup exit with code 1."""
        # Create rollup with extra config not in fixture
        rollup_data = {
            "summary": [
                {
                    "config": "baseline_greedy.yaml",
                    "status": "ok",
                    "avg_tricks": 5.0
                },
                {
                    "config": "unexpected_config.yaml",  # Not in fixture
                    "status": "ok",
                    "avg_tricks": 4.5
                }
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture without the unexpected config
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0
                }
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 1
        assert "UNEXPECTED_CONFIG: unexpected_config.yaml" in result.stdout

    def test_missing_expected_config_exits_one(self, tmp_path: Path) -> None:
        """Test that missing expected configs exit with code 1."""
        # Create rollup missing a config that's in fixture
        rollup_data = {
            "summary": [
                {
                    "config": "baseline_greedy.yaml",
                    "status": "ok",
                    "avg_tricks": 5.0
                }
                # Missing: baseline_matchups.yaml
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture with both configs
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0
                },
                "baseline_matchups.yaml": {
                    "avg_tricks": 4.8
                }
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 1
        assert "MISSING_CONFIG: baseline_matchups.yaml" in result.stdout

    def test_failed_run_status_exits_one(self, tmp_path: Path) -> None:
        """Test that failed runs (non-'ok' status) cause immediate exit with code 1."""
        # Create rollup with failed config
        rollup_data = {
            "summary": [
                {
                    "config": "baseline_greedy.yaml",
                    "status": "failed",  # Not 'ok'
                    "avg_tricks": None,
                    "reason": "some error"
                }
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0
                }
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 1
        assert "Suite has failed configs:" in result.stderr
        assert "baseline_greedy.yaml" in result.stderr

    def test_config_specific_tolerance(self, tmp_path: Path) -> None:
        """Test that config-specific tolerance overrides default tolerance."""
        # Create rollup with drifted value
        rollup_data = {
            "summary": [
                {
                    "config": "baseline_greedy.yaml",
                    "status": "ok",
                    "avg_tricks": 5.05  # 0.05 difference
                }
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture with config-specific tolerance that's larger than the difference
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,  # This would fail
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0,
                    "tolerance": 0.1  # This should pass (0.05 < 0.1)
                }
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 0
        assert "No drift detected" in result.stdout

    def test_auction_smoke_skipped_for_drift(self, tmp_path: Path) -> None:
        """Test that auction_smoke.yaml configs are skipped for drift detection."""
        # Create rollup with auction_smoke config
        rollup_data = {
            "summary": [
                {
                    "config": "auction_smoke.yaml",
                    "status": "ok",
                    "avg_tricks": 5.0
                },
                {
                    "config": "baseline_greedy.yaml",
                    "status": "ok",
                    "avg_tricks": 5.0
                }
            ]
        }
        rollup_file = tmp_path / "rollup.json"
        with open(rollup_file, "w") as f:
            json.dump(rollup_data, f)

        # Create fixture without auction_smoke (it should be ignored)
        fixture_data = {
            "schema_version": 0,
            "description": "Test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "baseline_greedy.yaml": {
                    "avg_tricks": 5.0
                }
                # auction_smoke not in fixture - should be OK since it's skipped
            }
        }
        fixture_file = tmp_path / "fixture.json"
        with open(fixture_file, "w") as f:
            json.dump(fixture_data, f)

        # Run comparison
        result = subprocess.run([
            sys.executable, "scripts/compare_rollup.py",
            "--rollup", str(rollup_file),
            "--fixture", str(fixture_file)
        ], capture_output=True, text=True)

        assert result.returncode == 0
        assert "SKIPPED_FOR_DRIFT: 1 config(s) - auction_smoke.yaml" in result.stdout
        assert "No drift detected" in result.stdout
