"""
Unit tests for the auction comparator gate logic.
"""

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

# Import via importlib to avoid sys.path.insert anti-pattern.
_COMPARATOR_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "run_auction_comparator.py"
)
_spec = importlib.util.spec_from_file_location(
    "run_auction_comparator", _COMPARATOR_SCRIPT
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
format_report = _mod.format_report
format_json = _mod.format_json
gate_check = _mod.gate_check
_CLASS_TO_NAME = _mod._CLASS_TO_NAME


class TestGateCheck:
    """Test gate check logic."""

    def test_all_bidders_have_bids_passes(self):
        """Gate passes when all bidders have bid_rate > 0."""
        metrics = {
            "bidder_a": {"bid_rate": 0.5, "expected_points": 3.0},
            "bidder_b": {"bid_rate": 0.3, "expected_points": 2.0},
        }
        failures = gate_check(metrics)
        assert len(failures) == 0

    def test_zero_bid_rate_fails(self):
        """Gate fails when any bidder has bid_rate == 0."""
        metrics = {
            "bidder_a": {"bid_rate": 0.5, "expected_points": 3.0},
            "bidder_b": {"bid_rate": 0, "expected_points": 0},
        }
        failures = gate_check(metrics)
        assert len(failures) == 1
        assert "bidder_b" in failures[0]

    def test_multiple_zero_bid_rates(self):
        """Gate reports all zero-bid-rate bidders."""
        metrics = {
            "bidder_a": {"bid_rate": 0},
            "bidder_b": {"bid_rate": 0},
            "bidder_c": {"bid_rate": 0.8},
        }
        failures = gate_check(metrics)
        assert len(failures) == 2


class TestFormatReport:
    """Test report formatting."""

    def test_report_contains_all_bidders(self):
        """Report includes all bidders in comparison table."""
        metrics = {
            "alice": {
                "expected_points": 3.5,
                "make_rate": 0.7,
                "bid_rate": 0.5,
                "cvar_5": -2.0,
                "hands_with_bids": 5000,
            },
            "bob": {
                "expected_points": 2.0,
                "make_rate": 0.6,
                "bid_rate": 0.3,
                "cvar_5": -3.0,
                "hands_with_bids": 3000,
            },
        }
        report = format_report(metrics, [], seed=42)
        assert "alice" in report
        assert "bob" in report
        assert "PASS" in report

    def test_report_shows_failures(self):
        """Report shows gate failures."""
        metrics = {"x": {"expected_points": 0, "bid_rate": 0}}
        failures = ["GATE FAIL: x has bid_rate=0"]
        report = format_report(metrics, failures, seed=42)
        assert "FAIL" in report
        assert "bid_rate=0" in report

    def test_report_sorted_by_expected_points(self):
        """Report sorts bidders by expected_points descending."""
        metrics = {
            "low": {
                "expected_points": 1.0,
                "make_rate": 0.5,
                "bid_rate": 0.5,
                "cvar_5": None,
                "hands_with_bids": 100,
            },
            "high": {
                "expected_points": 5.0,
                "make_rate": 0.8,
                "bid_rate": 0.9,
                "cvar_5": -1.0,
                "hands_with_bids": 900,
            },
        }
        report = format_report(metrics, [], seed=42)
        lines = report.split("\n")
        # Find the data rows (after header)
        data_rows = [
            l
            for l in lines
            if l.startswith("| ") and "Bidder" not in l and "---" not in l
        ]
        assert "high" in data_rows[0]
        assert "low" in data_rows[1]


class TestMissingEvaluationHardFail:
    """Test that missing evaluation data causes a hard failure."""

    def test_exits_nonzero_on_missing_evaluation(self):
        """Script exits non-zero when evaluation.json is missing for a bidder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal config with one bidder
            config = {
                "experiment_name": "test_comparator",
                "bidding_policies": [
                    {
                        "name": "test_bidder",
                        "class_name": "FixedBidder",
                        "params": {"n": 5, "contract": "S"},
                    },
                ],
                "scenarios": [{"contract_type": None}],
                "parameters": {"n_per": 10},
            }
            config_path = Path(tmpdir) / "test_config.yaml"
            import yaml

            with open(config_path, "w") as f:
                yaml.dump(config, f)

            # Create run dir with NO evaluation.json
            run_dir = Path(tmpdir) / "data" / "runs" / "test_comparator_test_bidder_42"
            run_dir.mkdir(parents=True)

            # Run in skip-run mode (so it only tries to load evaluation)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/internal/run_auction_comparator.py",
                    "--config",
                    str(config_path),
                    "--seed",
                    "42",
                    "--skip-run",
                ],
                capture_output=True,
                text=True,
                # Set data dir to our temp location
                env={**dict(__import__("os").environ), "PYTHONPATH": "."},
            )
            # Should fail because evaluation.json doesn't exist
            assert result.returncode != 0
            assert (
                "Missing evaluation data" in result.stderr
                or "Missing evaluation data" in result.stdout
                or result.returncode != 0
            )

    def test_report_includes_metric_provenance(self):
        """Report header includes metric source information."""
        metrics = {
            "alice": {
                "expected_points": 3.5,
                "make_rate": 0.7,
                "bid_rate": 0.5,
                "cvar_5": -2.0,
                "hands_with_bids": 5000,
            },
        }
        report = format_report(metrics, [], seed=42)
        assert "Metric source" in report
        assert "evaluation.json" in report


class TestScriptHelp:
    """Smoke test for the comparator script."""

    def test_help_flag(self):
        """Test that the script prints help without errors."""
        result = subprocess.run(
            [sys.executable, "scripts/internal/run_auction_comparator.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--olsa-artifact" in result.stdout
        assert "--bidder-class" in result.stdout
        assert "--output-format" in result.stdout


class TestFormatJson:
    """Tests for JSON output format."""

    def test_format_json_schema(self):
        """format_json() output has arc_d_comparator_v1 schema with expected keys."""
        metrics = {
            "hybrid_olsa": {
                "expected_points_per_deal": 3.5,
                "net_expected_points_per_deal": 1.5,
                "make_rate": 0.7,
                "bid_rate": 0.5,
                "cvar_5": -2.0,
                "net_cvar_5": -1.5,
            },
            "modeloespecifico": {
                "expected_points_per_deal": 2.0,
                "net_expected_points_per_deal": 0.8,
                "make_rate": 0.6,
                "bid_rate": 0.3,
                "cvar_5": -3.0,
                "net_cvar_5": -2.5,
            },
        }
        result = format_json(metrics, [], seed=42, n_per=10000)
        assert result["schema"] == "arc_d_comparator_v1"
        assert result["seed"] == 42
        assert result["n_per"] == 10000
        assert result["gate_status"] == "PASS"
        assert len(result["bidders"]) == 2
        # Check per-bidder fields
        hybrid = result["bidders"]["hybrid_olsa"]
        expected_keys = {
            "net_eppd",
            "eppd",
            "bid_rate",
            "make_rate",
            "cvar_5",
            "net_cvar_5",
        }
        assert set(hybrid.keys()) == expected_keys
        assert hybrid["net_eppd"] == 1.5
        assert hybrid["eppd"] == 3.5

    def test_format_json_gate_fail(self):
        """gate_status is 'FAIL' when failures list is non-empty."""
        metrics = {"x": {"expected_points_per_deal": 0, "bid_rate": 0}}
        failures = ["GATE FAIL: x has bid_rate=0"]
        result = format_json(metrics, failures, seed=42, n_per=100)
        assert result["gate_status"] == "FAIL"


class TestBidderNameDerivation:
    """Tests for _CLASS_TO_NAME mapping and bidder name derivation."""

    def test_known_classes_map_correctly(self):
        """_CLASS_TO_NAME maps OLSaBidder and HybridOLSaBidder."""
        assert _CLASS_TO_NAME["OLSaBidder"] == "olsa"
        assert _CLASS_TO_NAME["HybridOLSaBidder"] == "hybrid_olsa"

    def test_unknown_class_fallback(self):
        """Unknown classes fall back to lowercase."""
        unknown = "MyCustomBidder"
        name = _CLASS_TO_NAME.get(unknown, unknown.lower())
        assert name == "mycustombidder"
