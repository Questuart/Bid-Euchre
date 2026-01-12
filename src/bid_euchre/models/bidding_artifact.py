"""
Bidding model artifact schema v1 - JSON-serializable bidding models.

This module provides a deterministic, JSON-serializable format for bidding model artifacts.
Artifacts are stable across runs and can be used to represent trained bidding policies.
"""

import json
import os
from typing import Any, Dict

# Valid contract strings (must match core bidding system)
VALID_CONTRACTS = {"C", "D", "H", "S", "HIGH", "LOW"}


def validate_artifact(obj: Dict[str, Any]) -> None:
    """
    Validate a bidding model artifact dictionary.

    Args:
        obj: The artifact dictionary to validate

    Raises:
        ValueError: If the artifact is invalid with a clear error message
    """
    if not isinstance(obj, dict):
        raise ValueError("Artifact must be a dictionary")

    # Required fields
    required_fields = {"schema_version", "model_type", "contract", "model_params"}
    missing = required_fields - set(obj.keys())
    if missing:
        raise ValueError(f"Missing required fields: {sorted(missing)}")

    # Schema version
    if obj["schema_version"] != "1":
        raise ValueError(f"Unsupported schema version: {obj['schema_version']}, expected '1'")

    # Model type
    if not isinstance(obj["model_type"], str):
        raise ValueError("model_type must be a string")
    if not obj["model_type"].strip():
        raise ValueError("model_type cannot be empty")

    # Contract
    if obj["contract"] not in VALID_CONTRACTS:
        raise ValueError(f"Invalid contract '{obj['contract']}', must be one of: {sorted(VALID_CONTRACTS)}")

    # Model params - must be JSON-serializable
    try:
        json.dumps(obj["model_params"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"model_params must be JSON-serializable: {e}")

    # Optional metadata validation
    if "metadata" in obj:
        try:
            json.dumps(obj["metadata"])
        except (TypeError, ValueError) as e:
            raise ValueError(f"metadata must be JSON-serializable: {e}")


def load_artifact(path: str) -> Dict[str, Any]:
    """
    Load and validate a bidding model artifact from JSON file.

    Args:
        path: Path to the JSON artifact file

    Returns:
        The validated artifact dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the JSON is invalid or artifact fails validation
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Artifact file not found: {path}")

    try:
        with open(path, 'r', encoding='utf-8') as f:
            obj = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in artifact file {path}: {e}")

    validate_artifact(obj)
    return obj


def dump_artifact(obj: Dict[str, Any], path: str) -> None:
    """
    Dump a validated bidding model artifact to a JSON file.

    Creates stable JSON output with sorted keys and consistent formatting.

    Args:
        path: Path where to save the artifact
        obj: The artifact dictionary (will be validated first)

    Raises:
        ValueError: If the artifact is invalid
        OSError: If the directory doesn't exist or file cannot be written
    """
    validate_artifact(obj)

    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Write with stable formatting
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write('\n')  # Add trailing newline
