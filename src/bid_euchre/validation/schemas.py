"""
Schema validators for experiment outputs and configurations.

Provides pure Python validation of JSON schemas without external dependencies
(no Pydantic). Validates meta.json, results.json, and rollup.json against
their documented contracts.
"""

from typing import Any, Dict, List


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {errors}")


# =============================================================================
# Meta.json (schema v2) validation
# =============================================================================

REQUIRED_META_FIELDS_V2 = [
    "schema_version",
    "run_id",
    "created_at_utc",
    "git_sha",
    "config_path",
    "config_sha256",
    "is_deterministic",
    "seed",
    "n_per",
]


def validate_meta_v2(meta: Dict[str, Any], raise_on_error: bool = False) -> List[str]:
    """Validate meta.json schema v2.

    Args:
        meta: Loaded meta.json dict
        raise_on_error: If True, raise ValidationError; if False, return errors

    Returns:
        List of error messages (empty if valid)

    Raises:
        ValidationError: If raise_on_error=True and validation fails
    """
    errors = []

    # Check schema_version
    if meta.get("schema_version") != 2:
        errors.append(f"schema_version must be 2, got {meta.get('schema_version')}")

    # Check required fields
    for field in REQUIRED_META_FIELDS_V2:
        if field not in meta:
            errors.append(f"Missing required field: {field}")

    # Type checks
    if "is_deterministic" in meta and not isinstance(meta["is_deterministic"], bool):
        errors.append("is_deterministic must be boolean")

    if "seed" in meta:
        seed = meta["seed"]
        if seed is not None and not isinstance(seed, int):
            errors.append("seed must be int or null")

    if "n_per" in meta and not isinstance(meta["n_per"], int):
        errors.append("n_per must be int")

    # Format checks
    if "created_at_utc" in meta:
        timestamp = meta["created_at_utc"]
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            errors.append("created_at_utc must be ISO-8601 with Z suffix")

    if "config_sha256" in meta:
        sha = meta["config_sha256"]
        if not isinstance(sha, str) or len(sha) != 64:
            errors.append("config_sha256 must be 64-character hex string")

    if errors and raise_on_error:
        raise ValidationError(errors)

    return errors


# =============================================================================
# Results.json validation
# =============================================================================

REQUIRED_RESULTS_FIELDS = [
    "hands",
    "avg_team0",
    "avg_team1",
    "distribution_team0",  # Team 0 tricks distribution
    # Note: distribution_team1 not included (can be inferred from distribution_team0)
]


def validate_results_json(
    results: Dict[str, Any], raise_on_error: bool = False
) -> List[str]:
    """Validate results JSON file (from simulation.py outputs).

    Results files are per-scenario outputs (e.g., results/greedy/suit_H.json).
    See docs/01_core/METRICS.md for field definitions.

    Args:
        results: Loaded results.json dict
        raise_on_error: If True, raise ValidationError; if False, return errors

    Returns:
        List of error messages (empty if valid)

    Raises:
        ValidationError: If raise_on_error=True and validation fails
    """
    errors = []

    # Check required fields
    for field in REQUIRED_RESULTS_FIELDS:
        if field not in results:
            errors.append(f"Missing required field: {field}")

    # Type checks
    if "hands" in results:
        if not isinstance(results["hands"], int) or results["hands"] < 0:
            errors.append("hands must be non-negative integer")

    if "avg_team0" in results:
        avg = results["avg_team0"]
        if not isinstance(avg, (int, float)) or not (0 <= avg <= 10):
            errors.append("avg_team0 must be numeric in range [0, 10]")

    if "avg_team1" in results:
        avg = results["avg_team1"]
        if not isinstance(avg, (int, float)) or not (0 <= avg <= 10):
            errors.append("avg_team1 must be numeric in range [0, 10]")

    # Distribution check (only distribution_team0 is required)
    if "distribution_team0" in results:
        dist = results["distribution_team0"]
        if not isinstance(dist, dict):
            errors.append("distribution_team0 must be a dict")
        else:
            # Validate keys are numeric strings, values are integers
            for k, v in dist.items():
                try:
                    tricks = int(k)
                    if not (0 <= tricks <= 10):
                        errors.append(
                            f"distribution_team0 key '{k}' must be in range [0, 10]"
                        )
                except ValueError:
                    errors.append(f"distribution_team0 key '{k}' must be numeric")

                if not isinstance(v, int) or v < 0:
                    errors.append(
                        f"distribution_team0['{k}'] value must be non-negative integer"
                    )

    if errors and raise_on_error:
        raise ValidationError(errors)

    return errors


# =============================================================================
# Rollup.json (schema v1) validation
# =============================================================================

REQUIRED_ROLLUP_FIELDS_V1 = [
    "schema_version",
    "suite_name",
    "suite_seed",
    "suite_n_per",
    "created_at_utc",
    "configs",
    "summary",
]


def validate_rollup_v1(
    rollup: Dict[str, Any], raise_on_error: bool = False
) -> List[str]:
    """Validate rollup.json schema v1 (from scripts/run_suite.py).

    Rollup files are suite-level summaries that aggregate multiple runs.

    Args:
        rollup: Loaded rollup.json dict
        raise_on_error: If True, raise ValidationError; if False, return errors

    Returns:
        List of error messages (empty if valid)

    Raises:
        ValidationError: If raise_on_error=True and validation fails
    """
    errors = []

    # Check schema_version
    if rollup.get("schema_version") != 1:
        errors.append(f"schema_version must be 1, got {rollup.get('schema_version')}")

    # Check required fields
    for field in REQUIRED_ROLLUP_FIELDS_V1:
        if field not in rollup:
            errors.append(f"Missing required field: {field}")

    # Type checks
    if "suite_seed" in rollup and not isinstance(rollup["suite_seed"], int):
        errors.append("suite_seed must be int")

    if "suite_n_per" in rollup and not isinstance(rollup["suite_n_per"], int):
        errors.append("suite_n_per must be int")

    # Validate configs structure
    if "configs" in rollup:
        if not isinstance(rollup["configs"], list):
            errors.append("configs must be a list")
        else:
            for i, config_entry in enumerate(rollup["configs"]):
                if not isinstance(config_entry, dict):
                    errors.append(f"configs[{i}] must be a dict")
                else:
                    # Check required fields in config entry
                    required_config_fields = ["config_path", "run_id", "status"]
                    for field in required_config_fields:
                        if field not in config_entry:
                            errors.append(f"configs[{i}] missing field: {field}")

    # Validate summary structure
    if "summary" in rollup:
        if not isinstance(rollup["summary"], list):
            errors.append("summary must be a list")
        else:
            for i, summary_entry in enumerate(rollup["summary"]):
                if not isinstance(summary_entry, dict):
                    errors.append(f"summary[{i}] must be a dict")
                else:
                    # Check required summary fields
                    required_summary_fields = [
                        "config",
                        "run_id",
                        "status",
                        "total_hands",
                        "avg_tricks",
                    ]
                    for field in required_summary_fields:
                        if field not in summary_entry:
                            errors.append(f"summary[{i}] missing field: {field}")

    # Format checks
    if "created_at_utc" in rollup:
        timestamp = rollup["created_at_utc"]
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            errors.append("created_at_utc must be ISO-8601 with Z suffix")

    if errors and raise_on_error:
        raise ValidationError(errors)

    return errors
