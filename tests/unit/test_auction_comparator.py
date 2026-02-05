"""
Unit tests for the auction comparator gate logic.
"""

import subprocess
import sys

from scripts.run_auction_comparator import format_report, gate_check


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
            "low": {"expected_points": 1.0, "make_rate": 0.5, "bid_rate": 0.5, "cvar_5": None, "hands_with_bids": 100},
            "high": {"expected_points": 5.0, "make_rate": 0.8, "bid_rate": 0.9, "cvar_5": -1.0, "hands_with_bids": 900},
        }
        report = format_report(metrics, [], seed=42)
        lines = report.split("\n")
        # Find the data rows (after header)
        data_rows = [l for l in lines if l.startswith("| ") and "Bidder" not in l and "---" not in l]
        assert "high" in data_rows[0]
        assert "low" in data_rows[1]


class TestScriptHelp:
    """Smoke test for the comparator script."""

    def test_help_flag(self):
        """Test that the script prints help without errors."""
        result = subprocess.run(
            [sys.executable, "scripts/run_auction_comparator.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--olsa-artifact" in result.stdout
