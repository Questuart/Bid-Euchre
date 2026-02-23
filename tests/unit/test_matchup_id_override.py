"""Tests for the custom matchup_id override in head_to_head_matrix mode.

Validates that the matchup_id field in matchup config entries overrides
the auto-derived matchup_id (which would otherwise be team0_vs_team1 or
seatmap__...).
"""

from pathlib import Path

import yaml


def _load_h2h_config():
    """Load the arc_d_r0_head_to_head.yaml config file."""
    config_path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "configs"
        / "arc_d_r0_head_to_head.yaml"
    )
    assert config_path.exists(), f"Config not found: {config_path}"
    with open(config_path) as f:
        return yaml.safe_load(f)


def test_custom_matchup_id_in_config():
    """Custom matchup_id should be present in each matchup config entry."""
    config = _load_h2h_config()
    matchups = config["matchups"]
    assert len(matchups) == 9, f"Expected 9 matchups, got {len(matchups)}"

    for m in matchups:
        assert "matchup_id" in m, f"Matchup config entry missing matchup_id field: {m}"
        # matchup_id should be a non-empty string
        assert isinstance(m["matchup_id"], str) and len(m["matchup_id"]) > 0

    # Verify all matchup_ids are unique
    ids = [m["matchup_id"] for m in matchups]
    assert len(ids) == len(set(ids)), f"Duplicate matchup_ids found: {ids}"


def test_custom_matchup_id_in_runner_code():
    """run_experiment.py must read and apply custom matchup_id from config."""
    runner_path = (
        Path(__file__).resolve().parents[2] / "experiments" / "run_experiment.py"
    )
    source = runner_path.read_text()
    # Verify the override code exists
    assert (
        'm.get("matchup_id")' in source
    ), "run_experiment.py must read custom matchup_id from matchup config"
    assert (
        "custom_matchup_id" in source
    ), "run_experiment.py must use custom_matchup_id variable for override"
