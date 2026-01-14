"""
Unit tests for teacher roster manifest validation.

Tests the validation script for teacher roster manifest v1 and artifact schema invariants.
"""

import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import yaml


class TestTeacherRosterManifestValidation:
    """Test teacher roster manifest validation."""

    VALID_MANIFEST = {
        "roster_version": 1,
        "baselines": [
            {
                "id": "strict_raiser",
                "class_name": "StrictRaiserBidder",
                "type": "bidding_policy",
                "params": {}
            },
            {
                "id": "always_pass",
                "class_name": "AlwaysPassBidder",
                "type": "bidding_policy",
                "params": {}
            }
        ]
    }

    def test_valid_manifest_passes_validation(self, tmp_path):
        """Test that a valid manifest passes all validation checks."""
        # Copy the fixture artifact to the temp directory
        fixture_src = Path.cwd() / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst = tmp_path / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(fixture_src, fixture_dst)

        # Create a temporary manifest file
        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(self.VALID_MANIFEST, f)

        # Run the validation script
        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        # Should succeed
        assert result.returncode == 0
        assert "All validations passed!" in result.stdout

    def test_duplicate_baseline_ids_fail(self, tmp_path):
        """Test that manifests with duplicate baseline IDs are rejected."""
        invalid_manifest = deepcopy(self.VALID_MANIFEST)
        invalid_manifest["baselines"].append({
            "id": "strict_raiser",  # Duplicate ID
            "class_name": "AlwaysPassBidder",
            "type": "bidding_policy",
            "params": {}
        })

        # Create a temporary manifest file
        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        # Run the validation script
        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        # Should fail
        assert result.returncode != 0
        assert "Duplicate baseline id: strict_raiser" in result.stderr

    def test_missing_required_top_level_keys_fail(self, tmp_path):
        """Test that manifests missing required top-level keys are rejected."""
        invalid_manifest = {"baselines": []}  # Missing roster_version

        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        assert result.returncode != 0
        assert "Missing required top-level keys" in result.stderr

    def test_wrong_roster_version_fails(self, tmp_path):
        """Test that manifests with wrong roster version are rejected."""
        invalid_manifest = deepcopy(self.VALID_MANIFEST)
        invalid_manifest["roster_version"] = 2

        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        assert result.returncode != 0
        assert "Unsupported roster_version: 2, expected 1" in result.stderr

    def test_empty_baselines_list_fails(self, tmp_path):
        """Test that manifests with empty baselines list are rejected."""
        invalid_manifest = deepcopy(self.VALID_MANIFEST)
        invalid_manifest["baselines"] = []

        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        assert result.returncode != 0
        assert "baselines list cannot be empty" in result.stderr

    def test_baseline_missing_required_keys_fails(self, tmp_path):
        """Test that baselines missing required keys are rejected."""
        invalid_manifest = deepcopy(self.VALID_MANIFEST)
        invalid_manifest["baselines"][0] = {"id": "test"}  # Missing class_name

        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        assert result.returncode != 0
        assert "missing required keys" in result.stderr

    def test_non_importable_class_fails(self, tmp_path):
        """Test that manifests with non-importable classes are rejected."""
        invalid_manifest = deepcopy(self.VALID_MANIFEST)
        invalid_manifest["baselines"][0] = {
            "id": "nonexistent",
            "class_name": "NonExistentClass",
            "type": "bidding_policy",
            "params": {}
        }

        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        assert result.returncode != 0
        assert "Class 'NonExistentClass' not found in module 'bid_euchre.strategy'" in result.stderr

    def test_missing_artifact_file_fails(self, tmp_path):
        """Test that manifests referencing non-existent artifact files are rejected."""
        # Copy the fixture artifact to the temp directory
        fixture_src = Path.cwd() / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst = tmp_path / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(fixture_src, fixture_dst)

        invalid_manifest = deepcopy(self.VALID_MANIFEST)
        invalid_manifest["baselines"].append({
            "id": "artifact_bidder",
            "class_name": "ArtifactBidder",
            "type": "bidding_policy",
            "params": {
                "artifact_path": "nonexistent.json"
            }
        })

        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(invalid_manifest, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        assert result.returncode != 0
        assert "Bidding artifact not found: nonexistent.json" in result.stderr

    def test_script_handles_missing_manifest_file(self, tmp_path):
        """Test that the script succeeds gracefully when manifest file doesn't exist."""
        # Copy the fixture artifact to the temp directory (needed for schema validation)
        fixture_src = Path.cwd() / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst = tmp_path / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(fixture_src, fixture_dst)

        # Don't create the manifest file
        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )

        # Should succeed with a warning (not fail)
        assert result.returncode == 0
        assert "Teacher roster manifest not found" in result.stdout
        assert "This is expected until PR129 lands" in result.stdout
        assert "Bidding artifact schema v1 invariants preserved" in result.stdout

    def test_script_runs_quickly(self, tmp_path):
        """Test that the validation script runs quickly (< 2 seconds)."""
        import time

        # Copy the fixture artifact to the temp directory
        fixture_src = Path.cwd() / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst = tmp_path / "data" / "fixtures" / "bidding_artifact_v1_tiny.json"
        fixture_dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(fixture_src, fixture_dst)

        # Create a valid manifest file
        manifest_path = tmp_path / "experiments" / "baselines" / "teacher_roster_manifest_v1.yaml"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            yaml.dump(self.VALID_MANIFEST, f)

        script_path = Path.cwd() / "scripts" / "validate_teacher_roster_manifest.py"

        start_time = time.time()
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
        )
        end_time = time.time()

        assert result.returncode == 0
        execution_time = end_time - start_time
        assert execution_time < 2.0, f"Script took {execution_time:.2f}s, should be < 2.0s"
