"""Tests for auction comparator contract compliance.

Validates that run_auction_comparator.py:
1. Does not pass unsupported flags to run_experiment.py
2. Can detect new run directories via before/after snapshot diffing
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "internal"))
from run_auction_comparator import (
    _detect_new_run_dir,
    _snapshot_runs_dir,
    run_experiment,
)


def test_run_experiment_cmd_has_no_run_id_flag(tmp_path):
    """run_experiment() must not pass --run-id to experiments/run_experiment.py."""
    captured_cmd = []

    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)

        class FakeResult:
            returncode = 1
            stderr = "fake"
            stdout = ""

        return FakeResult()

    with patch("run_auction_comparator.subprocess.run", side_effect=fake_run):
        run_experiment(str(tmp_path / "config.yaml"), 42)

    assert "--run-id" not in captured_cmd, (
        "run_experiment() must not pass --run-id to experiments/run_experiment.py. "
        "The runner auto-generates run IDs with timestamps."
    )


def test_run_experiment_cmd_includes_seed(tmp_path):
    """run_experiment() must pass --seed to experiments/run_experiment.py."""
    captured_cmd = []

    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)

        class FakeResult:
            returncode = 1
            stderr = "fake"
            stdout = ""

        return FakeResult()

    with patch("run_auction_comparator.subprocess.run", side_effect=fake_run):
        run_experiment(str(tmp_path / "config.yaml"), 42)

    assert "--seed" in captured_cmd
    seed_idx = captured_cmd.index("--seed")
    assert captured_cmd[seed_idx + 1] == "42"


def test_detect_new_run_dir_single_new(tmp_path):
    """_detect_new_run_dir detects exactly one new directory."""
    before = {"existing_run_1", "existing_run_2"}
    # Create the "new" directory
    (tmp_path / "new_run_abc").mkdir()
    (tmp_path / "existing_run_1").mkdir()
    (tmp_path / "existing_run_2").mkdir()

    result = _detect_new_run_dir(str(tmp_path), before)
    assert result == str(tmp_path / "new_run_abc")


def test_detect_new_run_dir_no_change(tmp_path):
    """_detect_new_run_dir returns None when no new dirs appear."""
    (tmp_path / "existing_run").mkdir()
    before = {"existing_run"}

    result = _detect_new_run_dir(str(tmp_path), before)
    assert result is None


def test_detect_new_run_dir_multiple_new(tmp_path):
    """_detect_new_run_dir returns None when multiple new dirs appear (ambiguous)."""
    before = set()
    (tmp_path / "run_a").mkdir()
    (tmp_path / "run_b").mkdir()

    result = _detect_new_run_dir(str(tmp_path), before)
    assert result is None


def test_detect_new_run_dir_nonexistent_base():
    """_detect_new_run_dir returns None for nonexistent base directory."""
    result = _detect_new_run_dir("/nonexistent/path", set())
    assert result is None


def test_snapshot_runs_dir(tmp_path):
    """_snapshot_runs_dir captures directory names."""
    (tmp_path / "run_1").mkdir()
    (tmp_path / "run_2").mkdir()
    (tmp_path / "some_file.txt").touch()  # Files should be ignored

    snapshot = _snapshot_runs_dir(str(tmp_path))
    assert snapshot == {"run_1", "run_2"}


def test_snapshot_runs_dir_nonexistent():
    """_snapshot_runs_dir returns empty set for nonexistent directory."""
    snapshot = _snapshot_runs_dir("/nonexistent/path")
    assert snapshot == set()


def test_run_experiment_parses_stdout_for_run_dir(tmp_path):
    """run_experiment() parses 'Run directory:' from stdout."""
    run_dir = tmp_path / "data" / "runs" / "test_run_42_20260206"
    run_dir.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        class FakeResult:
            returncode = 0
            stderr = ""
            stdout = f"\n📁 Run directory: {run_dir}\n"

        return FakeResult()

    with patch("run_auction_comparator.subprocess.run", side_effect=fake_run):
        result = run_experiment(str(tmp_path / "config.yaml"), 42)

    assert result == str(run_dir)
