import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.run_suite import aggregate_run_metrics


class TestAggregateRunMetrics:
    """Test suite aggregation logic for run metrics."""

    def test_normal_weighted_average_calculation(self):
        """Test normal case with multiple result files and weighted average."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            # Create strategy directories with result files
            strategy1_dir = results_dir / "strategy1"
            strategy1_dir.mkdir()

            # File 1: 100 hands, avg_team0 = 4.5
            result1 = strategy1_dir / "scenario1.json"
            result1.write_text('{"hands": 100, "avg_team0": 4.5}')

            # File 2: 200 hands, avg_team0 = 5.0
            result2 = strategy1_dir / "scenario2.json"
            result2.write_text('{"hands": 200, "avg_team0": 5.0}')

            # Expected: (4.5 * 100 + 5.0 * 200) / (100 + 200) = (450 + 1000) / 300 = 1450 / 300 = 4.833...
            # Rounded to 2 decimal places: 4.83
            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] == 300
            assert result["avg_tricks"] == 4.83
            assert result["reason"] is None
            assert result["bad_files"] is None

    def test_rounding_behavior(self):
        """Test that avg_tricks is rounded to 2 decimal places."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # Create a calculation that would result in 4.83333...
            result_file = strategy_dir / "test.json"
            result_file.write_text('{"hands": 300, "avg_team0": 4.83333}')

            result = aggregate_run_metrics(run_dir)
            assert result["avg_tricks"] == 4.83  # Should be rounded to 2 decimal places

    def test_missing_hands_key(self):
        """Test handling of files missing 'hands' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # File without hands key
            result_file = strategy_dir / "bad.json"
            result_file.write_text('{"avg_team0": 4.5}')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "missing_key:hands" in result["reason"]
            assert len(result["bad_files"]) == 1
            assert "results/strategy/bad.json" in result["bad_files"]

    def test_missing_avg_team0_key(self):
        """Test handling of files missing 'avg_team0' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # File without avg_team0 key
            result_file = strategy_dir / "bad.json"
            result_file.write_text('{"hands": 100}')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "missing_key:avg_team0" in result["reason"]
            assert len(result["bad_files"]) == 1

    def test_missing_both_keys(self):
        """Test handling of files missing both 'hands' and 'avg_team0' keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # File without both keys
            result_file = strategy_dir / "bad.json"
            result_file.write_text('{"other_key": "value"}')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "missing_key:hands, avg_team0" in result["reason"]
            assert len(result["bad_files"]) == 1

    def test_invalid_json(self):
        """Test handling of malformed JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # Invalid JSON
            result_file = strategy_dir / "bad.json"
            result_file.write_text('{invalid json')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "json_decode_error" in result["reason"]
            assert len(result["bad_files"]) == 1

    def test_zero_hands(self):
        """Test handling of files with zero or negative hands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # File with zero hands
            result_file = strategy_dir / "bad.json"
            result_file.write_text('{"hands": 0, "avg_team0": 4.5}')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "missing_key:hands" in result["reason"]
            assert len(result["bad_files"]) == 1

    def test_negative_hands(self):
        """Test handling of files with negative hands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # File with negative hands
            result_file = strategy_dir / "bad.json"
            result_file.write_text('{"hands": -5, "avg_team0": 4.5}')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "missing_key:hands" in result["reason"]
            assert len(result["bad_files"]) == 1

    def test_mixed_valid_invalid_files(self):
        """Test aggregation with a mix of valid and invalid result files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # Valid file: 100 hands, avg_team0 = 4.0
            valid_file = strategy_dir / "valid.json"
            valid_file.write_text('{"hands": 100, "avg_team0": 4.0}')

            # Invalid file: missing keys
            invalid_file = strategy_dir / "invalid.json"
            invalid_file.write_text('{"other": "data"}')

            # Another valid file: 50 hands, avg_team0 = 5.0
            valid_file2 = strategy_dir / "valid2.json"
            valid_file2.write_text('{"hands": 50, "avg_team0": 5.0}')

            result = aggregate_run_metrics(run_dir)
            # Should aggregate only valid files: (4.0 * 100 + 5.0 * 50) / (100 + 50) = (400 + 250) / 150 = 650 / 150 = 4.333...
            # Rounded to 2 decimal places: 4.33
            assert result["total_hands"] == 150
            assert result["avg_tricks"] == 4.33
            assert result["reason"] is None
            assert result["bad_files"] is None

    def test_empty_results_directory(self):
        """Test behavior when results directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            # No results directory created

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert result["reason"] is None
            assert result["bad_files"] is None

    def test_multiple_bad_files_limited_output(self):
        """Test that bad_files output is limited to 3 entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            results_dir = run_dir / "results"
            results_dir.mkdir()

            strategy_dir = results_dir / "strategy"
            strategy_dir.mkdir()

            # Create 5 bad files
            for i in range(5):
                bad_file = strategy_dir / f"bad{i}.json"
                bad_file.write_text('{"invalid": "data"}')

            result = aggregate_run_metrics(run_dir)
            assert result["total_hands"] is None
            assert result["avg_tricks"] is None
            assert "missing_key:hands, avg_team0" in result["reason"]
            # Should be limited to 3 bad files
            assert len(result["bad_files"]) == 3