import json
import subprocess
import tempfile
from pathlib import Path


class TestRollupComparator:
    """Test rollup comparator behavior for various scenarios."""

    def run_comparator(self, rollup_data, fixture_data):
        """Helper to run comparator with temp files and return exit code and output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Write rollup file
            rollup_file = tmpdir / "rollup.json"
            rollup_file.write_text(json.dumps(rollup_data))

            # Write fixture file
            fixture_file = tmpdir / "fixture.json"
            fixture_file.write_text(json.dumps(fixture_data))

            # Run comparator
            result = subprocess.run(
                [
                    "python", "-m", "scripts.compare_rollup",
                    "--rollup", str(rollup_file),
                    "--fixture", str(fixture_file)
                ],
                capture_output=True,
                text=True,
                cwd=Path.cwd()
            )

            return result.returncode, result.stdout, result.stderr

    def test_match_within_tolerance_exits_zero(self):
        """Test that metrics matching within tolerance exit with code 0."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.25
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.24  # diff = 0.01, exactly at tolerance
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 0
        assert "No drift detected" in stdout

    def test_match_within_tolerance_with_custom_tolerance(self):
        """Test custom per-config tolerance."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.30
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25,
                    "tolerance": 0.10  # custom tolerance allows 0.05 diff
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 0
        assert "No drift detected" in stdout

    def test_metric_drift_beyond_tolerance_exits_one(self):
        """Test that metrics drifting beyond tolerance exit with code 1."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.30
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25  # diff = 0.05, beyond 0.01 tolerance
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 1
        assert "Drift detected:" in stdout
        assert "DRIFT: config1.yaml" in stdout

    def test_unexpected_config_exits_one(self):
        """Test that unexpected configs in rollup cause exit code 1."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.25
                },
                {
                    "config": "unexpected_config.yaml",  # not in fixture
                    "status": "ok",
                    "avg_tricks": 4.50
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 1
        assert "Drift detected:" in stdout
        assert "UNEXPECTED_CONFIG: unexpected_config.yaml" in stdout

    def test_missing_expected_config_exits_one(self):
        """Test that missing expected configs cause exit code 1."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.25
                }
                # config2.yaml is missing from rollup
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25
                },
                "config2.yaml": {
                    "avg_tricks": 4.50
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 1
        assert "Drift detected:" in stdout
        assert "MISSING_CONFIG: config2.yaml" in stdout

    def test_skipped_auction_smoke_config(self):
        """Test that auction_smoke.yaml configs are skipped for drift detection."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.25
                },
                {
                    "config": "auction_smoke.yaml",
                    "status": "ok",
                    "avg_tricks": 10.00  # would normally be drift
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25
                }
                # auction_smoke.yaml not in fixture, but should be skipped
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 0
        assert "No drift detected" in stdout
        assert "SKIPPED_FOR_DRIFT: 1 config(s) - auction_smoke.yaml" in stdout

    def test_failed_config_status_exits_one(self):
        """Test that configs with status != 'ok' cause exit code 1."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "failed",
                    "avg_tricks": 4.25
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 1
        assert "ERROR: Suite has failed configs:" in stderr

    def test_invalid_fixture_config_missing_avg_tricks(self):
        """Test handling of fixture configs missing avg_tricks."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.25
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    # missing avg_tricks
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 1
        assert "Drift detected:" in stdout
        assert "INVALID_FIXTURE_CONFIG: config1.yaml - missing avg_tricks" in stdout

    def test_invalid_fixture_config_invalid_tolerance(self):
        """Test handling of fixture configs with invalid tolerance."""
        rollup_data = {
            "summary": [
                {
                    "config": "config1.yaml",
                    "status": "ok",
                    "avg_tricks": 4.25
                }
            ]
        }

        fixture_data = {
            "schema_version": 0,
            "description": "test fixture",
            "default_tolerance": 0.01,
            "configs": {
                "config1.yaml": {
                    "avg_tricks": 4.25,
                    "tolerance": "invalid"  # should be number
                }
            }
        }

        exit_code, stdout, stderr = self.run_comparator(rollup_data, fixture_data)
        assert exit_code == 1
        assert "Drift detected:" in stdout
        assert "INVALID_FIXTURE_CONFIG: config1.yaml - invalid tolerance: invalid" in stdout
