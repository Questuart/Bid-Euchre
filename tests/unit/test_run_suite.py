"""
Unit tests for run_suite.py functions.

Tests aggregate_run_metrics function behavior including:
- Weighted average calculations
- Rounding behavior
- Error handling for missing keys/bad JSON
"""

import json

# Import the function we want to test
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from run_suite import aggregate_run_metrics


class TestAggregateRunMetrics:
    """Test aggregate_run_metrics function behavior."""

    def test_perfect_run_single_scenario(self, tmp_path: Path) -> None:
        """Test aggregation with a single scenario file."""
        # Create results directory structure
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create a single result file
        result_data = {
            "hands": 100,
            "avg_team0": 4.5
        }
        with open(results_dir, "w") as f:
            json.dump(result_data, f)

        # Test aggregation
        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] == 100
        assert result["avg_tricks"] == 4.5
        assert result["reason"] is None
        assert result["bad_files"] is None

    def test_weighted_average_multiple_scenarios(self, tmp_path: Path) -> None:
        """Test weighted average calculation across multiple scenarios."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create multiple strategy directories with different scenario files
        scenarios = [
            ("greedy", "suit_C.json", {"hands": 50, "avg_team0": 4.0}),
            ("greedy", "suit_D.json", {"hands": 30, "avg_team0": 5.0}),
            ("greedy", "suit_H.json", {"hands": 20, "avg_team0": 6.0}),
        ]

        for strategy, scenario_file, data in scenarios:
            scenario_path = results_dir / strategy / scenario_file
            scenario_path.parent.mkdir(exist_ok=True)
            with open(scenario_path, "w") as f:
                json.dump(data, f)

        # Test aggregation: (50*4.0 + 30*5.0 + 20*6.0) / (50+30+20) = (200 + 150 + 120) / 100 = 470/100 = 4.7
        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] == 100
        assert result["avg_tricks"] == 4.7
        assert result["reason"] is None
        assert result["bad_files"] is None

    def test_rounding_behavior(self, tmp_path: Path) -> None:
        """Test that averages are rounded to 2 decimal places."""
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create result that would give 4.666... when rounded to 2 decimals
        result_data = {
            "hands": 3,
            "avg_team0": 4.666666
        }
        with open(results_dir, "w") as f:
            json.dump(result_data, f)

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] == 3
        assert result["avg_tricks"] == 4.67  # Should be rounded to 2 decimal places
        assert result["reason"] is None
        assert result["bad_files"] is None

    def test_missing_hands_key(self, tmp_path: Path) -> None:
        """Test handling of result files missing 'hands' key."""
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create result missing 'hands' key
        result_data = {
            "avg_team0": 4.5
        }
        with open(results_dir, "w") as f:
            json.dump(result_data, f)

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] == "missing_key:hands: suit_C.json"
        assert result["bad_files"] == ["results/greedy/suit_C.json"]

    def test_zero_hands(self, tmp_path: Path) -> None:
        """Test handling of result files with hands = 0."""
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create result with hands = 0
        result_data = {
            "hands": 0,
            "avg_team0": 4.5
        }
        with open(results_dir, "w") as f:
            json.dump(result_data, f)

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] == "missing_key:hands: suit_C.json"
        assert result["bad_files"] == ["results/greedy/suit_C.json"]

    def test_missing_avg_team0_key(self, tmp_path: Path) -> None:
        """Test handling of result files missing 'avg_team0' key."""
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create result missing 'avg_team0' key
        result_data = {
            "hands": 100
        }
        with open(results_dir, "w") as f:
            json.dump(result_data, f)

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] == "missing_key:avg_team0: suit_C.json"
        assert result["bad_files"] == ["results/greedy/suit_C.json"]

    def test_both_keys_missing(self, tmp_path: Path) -> None:
        """Test handling when both required keys are missing."""
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create result missing both keys
        result_data = {}
        with open(results_dir, "w") as f:
            json.dump(result_data, f)

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] == "missing_key:hands, avg_team0: suit_C.json"
        assert result["bad_files"] == ["results/greedy/suit_C.json"]

    def test_invalid_json(self, tmp_path: Path) -> None:
        """Test handling of malformed JSON files."""
        results_dir = tmp_path / "results" / "greedy" / "suit_C.json"
        results_dir.parent.mkdir(parents=True)

        # Create invalid JSON
        with open(results_dir, "w") as f:
            f.write("invalid json content")

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] == "json_decode_error: suit_C.json"
        assert result["bad_files"] == ["results/greedy/suit_C.json"]

    def test_multiple_bad_files_limited(self, tmp_path: Path) -> None:
        """Test that bad_files list is limited to 3 entries."""
        results_dir = tmp_path / "results" / "greedy"
        results_dir.mkdir(parents=True)

        # Create 5 bad files
        bad_files = []
        for i in range(5):
            file_path = results_dir / f"suit_{i}.json"
            bad_files.append(file_path)
            # Create invalid JSON
            with open(file_path, "w") as f:
                f.write("invalid json")

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"].startswith("json_decode_error:")
        # Should only include first 3 bad files (sorted)
        assert len(result["bad_files"]) == 3
        expected_files = [f"results/greedy/suit_{i}.json" for i in range(3)]
        assert result["bad_files"] == expected_files

    def test_no_results_directory(self, tmp_path: Path) -> None:
        """Test behavior when results directory doesn't exist."""
        # Don't create results directory
        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] is None
        assert result["bad_files"] is None

    def test_empty_results_directory(self, tmp_path: Path) -> None:
        """Test behavior with empty results directory."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        result = aggregate_run_metrics(tmp_path)

        assert result["total_hands"] is None
        assert result["avg_tricks"] is None
        assert result["reason"] is None
        assert result["bad_files"] is None

    def test_mixed_valid_invalid_files(self, tmp_path: Path) -> None:
        """Test aggregation when some files are valid and some are invalid."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create one valid file
        valid_path = results_dir / "greedy" / "suit_C.json"
        valid_path.parent.mkdir()
        with open(valid_path, "w") as f:
            json.dump({"hands": 100, "avg_team0": 4.5}, f)

        # Create one invalid file
        invalid_path = results_dir / "greedy" / "suit_D.json"
        with open(invalid_path, "w") as f:
            f.write("invalid json")

        result = aggregate_run_metrics(tmp_path)

        # Valid data should be aggregated, invalid files are silently ignored
        # (bad_files are only reported when NO valid data is found)
        assert result["total_hands"] == 100
        assert result["avg_tricks"] == 4.5
        assert result["reason"] is None
        assert result["bad_files"] is None

    def test_deterministic_bad_files_ordering(self, tmp_path: Path) -> None:
        """Test that bad_files are sorted deterministically."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create bad files in non-alphabetical order
        files_to_create = ["suit_Z.json", "suit_A.json", "suit_M.json"]
        for filename in files_to_create:
            file_path = results_dir / "greedy" / filename
            file_path.parent.mkdir(exist_ok=True)
            with open(file_path, "w") as f:
                f.write("invalid json")

        result = aggregate_run_metrics(tmp_path)

        # Should be sorted alphabetically
        expected_files = [
            "results/greedy/suit_A.json",
            "results/greedy/suit_M.json",
            "results/greedy/suit_Z.json"
        ]
        assert result["bad_files"] == expected_files
