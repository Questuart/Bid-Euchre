"""
Unit tests for teacher baseline roster validation (v1).
"""

from pathlib import Path

import pytest

from src.bid_euchre.experiments.teacher_roster import load_teacher_roster


class TestTeacherRosterV1:
    """Test teacher roster loading and validation."""

    def test_load_valid_roster(self, tmp_path):
        """Test loading a valid roster file."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: test_policy
    display_name: "Test Policy"
    kind: "policy"
    import_path: "src.bid_euchre.strategy.bidding.AlwaysPassBidder"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        roster = load_teacher_roster(roster_file)

        assert roster['roster_version'] == "1"
        assert len(roster['baselines']) == 1
        assert roster['baselines'][0]['id'] == "test_policy"

    def test_duplicate_ids_fail(self, tmp_path):
        """Test that duplicate baseline IDs are rejected."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: duplicate
    display_name: "First"
    kind: "policy"
    import_path: "src.bid_euchre.strategy.bidding.AlwaysPassBidder"
    params: {}
  - id: duplicate
    display_name: "Second"
    kind: "policy"
    import_path: "src.bid_euchre.strategy.bidding.StrictRaiserBidder"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="Duplicate baseline IDs found"):
            load_teacher_roster(roster_file)

    def test_invalid_kind_fails(self, tmp_path):
        """Test that invalid baseline kinds are rejected."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: invalid_kind
    display_name: "Invalid"
    kind: "invalid_type"
    import_path: "src.bid_euchre.strategy.bidding.AlwaysPassBidder"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="has invalid kind 'invalid_type'"):
            load_teacher_roster(roster_file)

    def test_missing_required_keys_fail(self, tmp_path):
        """Test that missing required keys are rejected."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - display_name: "Missing ID"
    kind: "policy"
    import_path: "src.bid_euchre.strategy.bidding.AlwaysPassBidder"
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="Baseline missing required 'id' key"):
            load_teacher_roster(roster_file)

    def test_invalid_import_path_fails(self, tmp_path):
        """Test that invalid import paths are rejected."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: invalid_import
    display_name: "Invalid Import"
    kind: "policy"
    import_path: "nonexistent.module.NonexistentClass"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="Cannot import baseline"):
            load_teacher_roster(roster_file)

    def test_artifact_policy_missing_params_fails(self, tmp_path):
        """Test that artifact_policy without params fails."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: missing_params
    display_name: "Missing Params"
    kind: "artifact_policy"
    import_path: "src.bid_euchre.strategy.bidding.ArtifactBidder"
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="missing required 'params' key"):
            load_teacher_roster(roster_file)

    def test_artifact_policy_missing_artifact_path_fails(self, tmp_path):
        """Test that artifact_policy without artifact_path fails."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: missing_artifact_path
    display_name: "Missing Artifact Path"
    kind: "artifact_policy"
    import_path: "src.bid_euchre.strategy.bidding.ArtifactBidder"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="missing required 'artifact_path' in params"):
            load_teacher_roster(roster_file)

    def test_artifact_policy_nonexistent_artifact_fails(self, tmp_path):
        """Test that artifact_policy with nonexistent artifact path fails."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: nonexistent_artifact
    display_name: "Nonexistent Artifact"
    kind: "artifact_policy"
    import_path: "src.bid_euchre.strategy.bidding.ArtifactBidder"
    params:
      artifact_path: "nonexistent/path.json"
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        with pytest.raises(ValueError, match="artifact_path does not exist"):
            load_teacher_roster(roster_file)

    def test_load_shipped_roster(self):
        """Test loading the actual shipped roster file."""
        roster_path = Path("experiments/baselines/teacher_roster_v1.yaml")

        # This should not raise an exception if the roster is valid
        roster = load_teacher_roster(roster_path)

        assert roster['roster_version'] == "1"
        assert len(roster['baselines']) >= 3  # Should have at least 3 baselines

        # Check that all baselines have unique IDs
        ids = [b['id'] for b in roster['baselines']]
        assert len(ids) == len(set(ids))

        # Check that all required keys are present
        for baseline in roster['baselines']:
            required_keys = {'id', 'display_name', 'kind', 'import_path'}
            assert required_keys.issubset(set(baseline.keys()))
