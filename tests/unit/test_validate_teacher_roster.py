"""
Unit tests for teacher roster manifest validation script.

Tests the validate_teacher_roster.py script functionality.
"""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from scripts.validate_teacher_roster import (
    load_yaml_file,
    main,
    validate_artifact_references,
    validate_artifact_schema_invariants,
    validate_baseline_importability,
    validate_roster_manifest_structure,
)


class TestValidateTeacherRoster:
    """Test teacher roster validation functionality."""

    def test_load_yaml_file_success(self):
        """Test successful YAML file loading."""
        test_data = {"key": "value", "number": 42}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(test_data, f)
            f.flush()

            try:
                result = load_yaml_file(f.name)
                assert result == test_data
            finally:
                os.unlink(f.name)

    def test_load_yaml_file_not_found(self):
        """Test loading non-existent YAML file."""
        with pytest.raises(FileNotFoundError, match="YAML file not found"):
            load_yaml_file("nonexistent_file.yaml")

    def test_load_yaml_file_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            f.flush()

            try:
                with pytest.raises(ValueError, match="Invalid YAML"):
                    load_yaml_file(f.name)
            finally:
                os.unlink(f.name)

    def test_validate_roster_manifest_structure_valid(self):
        """Test validation of valid roster manifest structure."""
        valid_manifest = {
            "roster_version": 1,
            "baselines": [
                {"id": "strict_raiser", "class_name": "StrictRaiserBidder"},
                {"id": "heuristics", "class_name": "HeuristicsBidder", "type": "bidding_policy"}
            ]
        }
        # Should not raise
        validate_roster_manifest_structure(valid_manifest)

    def test_validate_roster_manifest_structure_missing_keys(self):
        """Test validation fails with missing required keys."""
        invalid_manifest = {"baselines": []}
        with pytest.raises(ValueError, match="Missing required top-level keys"):
            validate_roster_manifest_structure(invalid_manifest)

    def test_validate_roster_manifest_structure_wrong_version(self):
        """Test validation fails with wrong roster version."""
        invalid_manifest = {"roster_version": 2, "baselines": []}
        with pytest.raises(ValueError, match="Unsupported roster_version"):
            validate_roster_manifest_structure(invalid_manifest)

    def test_validate_roster_manifest_structure_empty_baselines(self):
        """Test validation fails with empty baselines list."""
        invalid_manifest = {"roster_version": 1, "baselines": []}
        with pytest.raises(ValueError, match="baselines list cannot be empty"):
            validate_roster_manifest_structure(invalid_manifest)

    def test_validate_roster_manifest_structure_duplicate_ids(self):
        """Test validation fails with duplicate baseline IDs."""
        invalid_manifest = {
            "roster_version": 1,
            "baselines": [
                {"id": "duplicate", "class_name": "Class1"},
                {"id": "duplicate", "class_name": "Class2"}
            ]
        }
        with pytest.raises(ValueError, match="Duplicate baseline id"):
            validate_roster_manifest_structure(invalid_manifest)

    def test_validate_roster_manifest_structure_missing_baseline_keys(self):
        """Test validation fails with missing baseline required keys."""
        invalid_manifest = {
            "roster_version": 1,
            "baselines": [{"id": "test"}]  # missing class_name
        }
        with pytest.raises(ValueError, match="missing required keys"):
            validate_roster_manifest_structure(invalid_manifest)

    def test_validate_baseline_importability_valid(self):
        """Test validation of importable baseline classes."""
        # Mock manifest with a real class that should exist
        valid_manifest = {
            "roster_version": 1,
            "baselines": [
                {
                    "id": "strict_raiser",
                    "class_name": "StrictRaiserBidder",
                    "module_path": "bid_euchre.strategy.bidding"
                }
            ]
        }
        # Should not raise (assuming the class exists)
        validate_baseline_importability(valid_manifest)

    def test_validate_baseline_importability_missing_class(self):
        """Test validation fails with non-existent class."""
        invalid_manifest = {
            "roster_version": 1,
            "baselines": [
                {
                    "id": "nonexistent",
                    "class_name": "NonExistentClass",
                    "module_path": "bid_euchre.strategy.bidding"
                }
            ]
        }
        with pytest.raises(ValueError, match="Class 'NonExistentClass' not found"):
            validate_baseline_importability(invalid_manifest)

    def test_validate_artifact_references_valid(self):
        """Test validation of existing artifact references."""
        # Create a temporary file to reference
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            valid_manifest = {
                "roster_version": 1,
                "baselines": [
                    {
                        "id": "test",
                        "class_name": "TestClass",
                        "params": {"artifact_path": temp_path}
                    }
                ]
            }
            # Should not raise
            validate_artifact_references(valid_manifest)
        finally:
            os.unlink(temp_path)

    def test_validate_artifact_references_missing_file(self):
        """Test validation fails with missing artifact file."""
        invalid_manifest = {
            "roster_version": 1,
            "baselines": [
                {
                    "id": "test",
                    "class_name": "TestClass",
                    "params": {"artifact_path": "nonexistent_file.json"}
                }
            ]
        }
        with pytest.raises(ValueError, match="Referenced artifact file does not exist"):
            validate_artifact_references(invalid_manifest)

    def test_validate_artifact_schema_invariants(self):
        """Test validation of artifact schema invariants."""
        # This should pass with the real fixture file
        validate_artifact_schema_invariants()

    @patch('scripts.validate_teacher_roster.os.path.exists')
    @patch('builtins.print')
    def test_main_no_manifest_file(self, mock_print, mock_exists):
        """Test main function when roster manifest doesn't exist."""
        mock_exists.return_value = False

        with patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # Check that appropriate messages were printed
        printed_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Teacher roster manifest not found" in msg for msg in printed_calls)
        assert any("Skipping roster validation" in msg for msg in printed_calls)

    def test_main_with_manifest_file(self):
        """Test main function with valid manifest file (if it exists)."""
        roster_path = "experiments/baselines/teacher_roster_manifest_v1.yaml"

        if os.path.exists(roster_path):
            # If the manifest exists, test that main runs without error
            with patch('builtins.print'), patch('sys.exit') as mock_exit:
                main()
                mock_exit.assert_called_once_with(0)
        else:
            # If manifest doesn't exist, test the no-manifest path
            with patch('builtins.print'), patch('sys.exit') as mock_exit:
                main()
                mock_exit.assert_called_once_with(0)
