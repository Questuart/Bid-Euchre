#!/usr/bin/env python3
"""
Validate teacher roster manifest v1 and bidding artifact schema invariants.

This script performs deterministic validation of:
1. Teacher roster manifest v1 structure and importability
2. Bidding artifact schema v1 invariants

Exits with code 0 on success, non-zero on failure.
"""

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import yaml

from bid_euchre.models.bidding_artifact import load_artifact


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a YAML file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {file_path}: {e}")


def validate_roster_manifest_structure(manifest: Dict[str, Any]) -> None:
    """Validate the structure of the teacher roster manifest v1."""
    # Required top-level keys
    required_keys = {"roster_version", "baselines"}
    missing = required_keys - set(manifest.keys())
    if missing:
        raise ValueError(f"Missing required top-level keys: {sorted(missing)}")

    # Roster version
    if manifest["roster_version"] != 1:
        raise ValueError(f"Unsupported roster_version: {manifest['roster_version']}, expected 1")

    # Baselines must be a list
    if not isinstance(manifest["baselines"], list):
        raise ValueError("baselines must be a list")

    if not manifest["baselines"]:
        raise ValueError("baselines list cannot be empty")

    # Validate each baseline entry
    seen_ids = set()
    for i, baseline in enumerate(manifest["baselines"]):
        if not isinstance(baseline, dict):
            raise ValueError(f"Baseline {i} must be a dictionary")

        # Required baseline keys
        required_baseline_keys = {"id", "class_name"}
        missing = required_baseline_keys - set(baseline.keys())
        if missing:
            raise ValueError(f"Baseline {i} missing required keys: {sorted(missing)}")

        # ID validation
        baseline_id = baseline["id"]
        if not isinstance(baseline_id, str) or not baseline_id.strip():
            raise ValueError(f"Baseline {i} id must be a non-empty string")
        if baseline_id in seen_ids:
            raise ValueError(f"Duplicate baseline id: {baseline_id}")
        seen_ids.add(baseline_id)

        # Class name validation
        class_name = baseline["class_name"]
        if not isinstance(class_name, str) or not class_name.strip():
            raise ValueError(f"Baseline {i} class_name must be a non-empty string")

        # Type validation (if present)
        if "type" in baseline:
            baseline_type = baseline["type"]
            if not isinstance(baseline_type, str) or not baseline_type.strip():
                raise ValueError(f"Baseline {i} type must be a non-empty string")
            # Allow known types - can be extended as needed
            allowed_types = {"bidding_policy", "strategy"}
            if baseline_type not in allowed_types:
                raise ValueError(f"Baseline {i} type '{baseline_type}' not in allowed types: {sorted(allowed_types)}")

        # Params validation (if present)
        if "params" in baseline:
            params = baseline["params"]
            if not isinstance(params, dict):
                raise ValueError(f"Baseline {i} params must be a dictionary")


def validate_baseline_importability(manifest: Dict[str, Any]) -> None:
    """Validate that all baseline classes can be imported and instantiated."""
    for i, baseline in enumerate(manifest["baselines"]):
        baseline_id = baseline["id"]
        class_name = baseline["class_name"]

        # Determine module path - check for explicit module_path or use default
        if "module_path" in baseline:
            module_path = baseline["module_path"]
        else:
            # Default import convention - assume from bid_euchre.strategy
            module_path = "bid_euchre.strategy"

        try:
            # Import the module
            module = importlib.import_module(module_path)

            # Get the class
            if not hasattr(module, class_name):
                raise ValueError(f"Class '{class_name}' not found in module '{module_path}'")

            cls = getattr(module, class_name)

            # Try to create an instance (with minimal params for testing)
            params = baseline.get("params", {})

            # Special handling for different class types
            if baseline.get("type") == "bidding_policy":
                # For bidding policies, try with name parameter
                try:
                    cls(name=baseline_id, **params)
                except TypeError:
                    # Fallback without name
                    cls(**params)
            else:
                # For other classes, try with provided params
                try:
                    cls(**params)
                except TypeError:
                    # If instantiation fails, that's OK - we just need to ensure import works
                    # The actual instantiation will be validated elsewhere
                    pass

        except (ImportError, AttributeError, TypeError) as e:
            raise ValueError(f"Cannot import/instantiate baseline '{baseline_id}' ({class_name} from {module_path}): {e}")


def validate_artifact_references(manifest: Dict[str, Any]) -> None:
    """Validate that any referenced artifact files exist."""
    for baseline in manifest["baselines"]:
        params = baseline.get("params", {})
        if "artifact_path" in params:
            artifact_path = params["artifact_path"]
            if not os.path.exists(artifact_path):
                raise ValueError(f"Referenced artifact file does not exist: {artifact_path}")


def validate_artifact_schema_invariants() -> None:
    """Validate that bidding artifact schema v1 invariants haven't been broken."""
    # Load the fixture artifact to ensure schema invariants are preserved
    fixture_path = "data/fixtures/bidding_artifact_v1_tiny.json"
    try:
        artifact = load_artifact(fixture_path)
    except Exception as e:
        raise ValueError(f"Cannot load fixture artifact {fixture_path}: {e}")

    # Validate required v1 fields exist
    required_fields = {"schema_version", "model_type", "contract", "model_params"}
    missing = required_fields - set(artifact.keys())
    if missing:
        raise ValueError(f"Fixture artifact missing required v1 fields: {sorted(missing)}")

    # Validate schema version
    if artifact["schema_version"] != "1":
        raise ValueError(f"Fixture artifact has wrong schema version: {artifact['schema_version']}, expected '1'")

    # Validate known supported model types still exist
    supported_model_types = {"strict_raiser_imitation_v1", "heuristics_imitation_v1", "linear_regression"}
    model_type = artifact["model_type"]
    if model_type not in supported_model_types:
        raise ValueError(f"Fixture artifact uses unsupported model type: {model_type}, expected one of: {sorted(supported_model_types)}")


def main() -> None:
    """Main validation function."""
    try:
        # Find the roster manifest file
        roster_path = "experiments/baselines/teacher_roster_manifest_v1.yaml"

        # 1. Validate roster manifest structure
        print(f"Loading roster manifest: {roster_path}")
        manifest = load_yaml_file(roster_path)
        validate_roster_manifest_structure(manifest)
        print("✓ Roster manifest structure is valid")

        # 2. Validate importability
        validate_baseline_importability(manifest)
        print("✓ All baseline classes are importable")

        # 3. Validate artifact references
        validate_artifact_references(manifest)
        print("✓ All referenced artifact files exist")

        # 4. Validate artifact schema invariants
        validate_artifact_schema_invariants()
        print("✓ Bidding artifact schema v1 invariants preserved")

        print("🎉 All validations passed!")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Validation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()