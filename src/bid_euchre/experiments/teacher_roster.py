"""
Teacher baseline roster validation utilities.

This module provides utilities for loading and validating the teacher baseline
roster manifest (v1), ensuring that all referenced baselines are available and
properly configured.
"""

import importlib
from pathlib import Path
from typing import Any, Dict

import yaml


def load_teacher_roster(path: str | Path) -> Dict[str, Any]:
    """
    Load and validate a teacher baseline roster from YAML file.

    Args:
        path: Path to the roster YAML file

    Returns:
        Validated roster dictionary

    Raises:
        ValueError: If roster validation fails
        FileNotFoundError: If roster file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    path = Path(path)

    # Load YAML
    with open(path, 'r', encoding='utf-8') as f:
        roster = yaml.safe_load(f)

    if roster is None:
        raise ValueError("Empty roster file")

    # Validate roster structure
    _validate_roster_structure(roster)

    # Validate each baseline
    for baseline in roster['baselines']:
        _validate_baseline(baseline, roster_path=path.parent)

    return roster


def _validate_roster_structure(roster: Dict[str, Any]) -> None:
    """Validate the top-level roster structure."""
    required_keys = {'roster_version', 'created', 'description', 'baselines'}

    missing_keys = required_keys - set(roster.keys())
    if missing_keys:
        raise ValueError(f"Roster missing required keys: {missing_keys}")

    if roster['roster_version'] != "1":
        raise ValueError(f"Unsupported roster version: {roster['roster_version']}")

    if not isinstance(roster['baselines'], list):
        raise ValueError("baselines must be a list")

    if not roster['baselines']:
        raise ValueError("baselines list cannot be empty")

    # Check for duplicate IDs
    ids = []
    for b in roster['baselines']:
        if 'id' not in b:
            raise ValueError(f"Baseline missing required 'id' key: {b}")
        ids.append(b['id'])

    if len(ids) != len(set(ids)):
        duplicates = [id for id in ids if ids.count(id) > 1]
        raise ValueError(f"Duplicate baseline IDs found: {duplicates}")


def _validate_baseline(baseline: Dict[str, Any], roster_path: Path) -> None:
    """Validate a single baseline entry."""
    required_keys = {'id', 'display_name', 'kind', 'import_path'}

    missing_keys = required_keys - set(baseline.keys())
    if missing_keys:
        raise ValueError(f"Baseline '{baseline.get('id', 'unknown')}' missing required keys: {missing_keys}")

    if baseline['kind'] not in {'policy', 'artifact_policy'}:
        raise ValueError(f"Baseline '{baseline['id']}' has invalid kind '{baseline['kind']}', must be 'policy' or 'artifact_policy'")

    # Validate import path can be imported
    try:
        module_path, class_name = baseline['import_path'].rsplit('.', 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        if not callable(cls):
            raise ValueError(f"Import path '{baseline['import_path']}' does not point to a callable class")
    except (ImportError, AttributeError, ValueError) as e:
        raise ValueError(f"Cannot import baseline '{baseline['id']}': {e}")

    # Validate artifact_policy specifics
    if baseline['kind'] == 'artifact_policy':
        if 'params' not in baseline:
            raise ValueError(f"artifact_policy baseline '{baseline['id']}' missing required 'params' key")

        params = baseline['params']
        if not isinstance(params, dict):
            raise ValueError(f"artifact_policy baseline '{baseline['id']}' params must be a dict")

        if 'artifact_path' not in params:
            raise ValueError(f"artifact_policy baseline '{baseline['id']}' missing required 'artifact_path' in params")

        artifact_path = Path(params['artifact_path'])
        if not artifact_path.exists():
            raise ValueError(f"artifact_policy baseline '{baseline['id']}' artifact_path does not exist: {artifact_path}")
