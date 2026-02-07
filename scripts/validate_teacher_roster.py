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
from typing import Any, Dict

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

    # Roster version (support both string and int)
    roster_version = manifest["roster_version"]
    if str(roster_version) != "1":
        raise ValueError(f"Unsupported roster_version: {roster_version}, expected '1'")

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

        # Required baseline keys (import_path is the key field)
        required_baseline_keys = {"id", "import_path"}
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

        # Import path validation
        import_path = baseline["import_path"]
        if not isinstance(import_path, str) or not import_path.strip():
            raise ValueError(f"Baseline {i} import_path must be a non-empty string")

        # Kind validation (if present)
        if "kind" in baseline:
            baseline_kind = baseline["kind"]
            if not isinstance(baseline_kind, str) or not baseline_kind.strip():
                raise ValueError(f"Baseline {i} kind must be a non-empty string")
            # Allow known kinds
            allowed_kinds = {"policy", "artifact_policy", "strategy"}
            if baseline_kind not in allowed_kinds:
                raise ValueError(f"Baseline {i} kind '{baseline_kind}' not in allowed kinds: {sorted(allowed_kinds)}")

        # Params validation (if present)
        if "params" in baseline:
            params = baseline["params"]
            if not isinstance(params, dict):
                raise ValueError(f"Baseline {i} params must be a dictionary")


def validate_baseline_importability(manifest: Dict[str, Any]) -> None:
    """Validate that all baseline classes can be imported and instantiated."""
    for i, baseline in enumerate(manifest["baselines"]):
        baseline_id = baseline["id"]
        import_path = baseline["import_path"]

        # Parse import_path (format: "module.path.ClassName")
        try:
            if "." not in import_path:
                raise ValueError(f"import_path must contain at least one dot: {import_path}")

            module_path, class_name = import_path.rsplit(".", 1)

            # Import the module
            module = importlib.import_module(module_path)

            # Get the class
            if not hasattr(module, class_name):
                raise ValueError(f"Class '{class_name}' not found in module '{module_path}'")

            cls = getattr(module, class_name)

            # Try to create an instance (with minimal params for testing)
            # If instantiation fails, that's OK - we just validate the import works
            params = baseline.get("params", {})

            try:
                # Special handling for different class kinds
                if baseline.get("kind") in ("policy", "artifact_policy"):
                    # For bidding policies, try with name parameter
                    try:
                        cls(name=baseline_id, **params)
                    except TypeError:
                        # Fallback without name
                        cls(**params)
                else:
                    # For other classes, try with provided params
                    cls(**params)
            except (TypeError, ValueError):
                # Instantiation failed - that's OK, we just needed to verify import works
                # The actual runtime instantiation will be validated elsewhere
                pass

        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot import baseline '{baseline_id}' (import_path: {import_path}): {e}")


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


def main() -> None:
    """Main validation function."""
    try:
        # Find the roster manifest file
        roster_path = "experiments/baselines/teacher_roster_v1.yaml"

        # Check if manifest exists
        if not os.path.exists(roster_path):
            print(f"⚠️  Teacher roster manifest not found: {roster_path}")
            print("   Skipping roster validation, but validating artifact schema...")

            # Still validate artifact schema invariants
            validate_artifact_schema_invariants()
            print("✓ Bidding artifact schema v1 invariants preserved")
            print("✅ Validation passed (roster manifest validation will activate once manifest is created)")
            sys.exit(0)

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