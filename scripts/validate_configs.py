#!/usr/bin/env python3
"""Validate all experiment configs and suites without running them.

This script provides fast, fail-fast validation of YAML configuration files
before they are used in experiments. It catches:
- Invalid YAML syntax
- Missing required fields
- Invalid field values (via ExperimentConfig __post_init__)
- Referenced configs that don't exist (in suite files)

Usage:
    python scripts/validate_configs.py

Exit codes:
    0: All configs valid
    1: Validation errors found
"""

import sys
from pathlib import Path

import yaml

from bid_euchre.experiments.config import ExperimentConfig


def validate_config_file(path: Path) -> list[str]:
    """Load and validate a single config file.

    Args:
        path: Path to YAML config file

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        # Try to instantiate config (triggers __post_init__ validation)
        ExperimentConfig(**data)
    except FileNotFoundError as e:
        errors.append(f"{path}: {e}")
    except yaml.YAMLError as e:
        errors.append(f"{path}: YAML parse error: {e}")
    except TypeError as e:
        errors.append(f"{path}: Config structure error: {e}")
    except ValueError as e:
        errors.append(f"{path}: Validation error: {e}")
    except Exception as e:
        errors.append(f"{path}: Unexpected error: {e}")

    return errors


def validate_suite_file(path: Path) -> list[str]:
    """Load and validate a single suite file.

    Note: SuiteConfig doesn't exist as a dataclass. Instead, validate using
    the same logic as scripts/run_suite.py::load_suite().

    Args:
        path: Path to suite YAML file

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        # Required top-level keys (from run_suite.py)
        required_keys = {"suite_name", "configs", "parameters"}
        missing = required_keys - set(data.keys())
        if missing:
            errors.append(f"{path}: Missing required keys: {missing}")

        # Validate configs is a list
        if "configs" in data and not isinstance(data["configs"], list):
            errors.append(f"{path}: 'configs' must be a list")

        # Validate each config path exists
        if isinstance(data.get("configs"), list):
            for config_name in data["configs"]:
                # Handle both absolute paths and relative refs
                if isinstance(config_name, str):
                    # If it's an absolute path starting with "experiments/configs/"
                    if config_name.startswith("experiments/configs/"):
                        config_path = Path(config_name)
                    else:
                        # Assume it's just a filename
                        config_path = Path("experiments/configs") / config_name

                    if not config_path.exists():
                        errors.append(
                            f"{path}: Referenced config not found: {config_path}"
                        )
                else:
                    errors.append(
                        f"{path}: Config entry must be string, got {type(config_name)}"
                    )

        # Validate parameters section
        if "parameters" in data:
            if not isinstance(data["parameters"], dict):
                errors.append(f"{path}: 'parameters' must be a dict")

        # Validate batch-specific fields (optional, backward compat)
        if "batch_purpose" in data:
            valid_purposes = {"promotion", "regression", "exploration"}
            if data["batch_purpose"] not in valid_purposes:
                errors.append(
                    f"{path}: batch_purpose must be one of {valid_purposes}, "
                    f"got '{data['batch_purpose']}'"
                )

        if "batch_roles" in data:
            if not isinstance(data["batch_roles"], dict):
                errors.append(f"{path}: 'batch_roles' must be a dict")
            elif isinstance(data.get("configs"), list):
                config_filenames = {Path(c).name for c in data["configs"]}
                for key in data["batch_roles"]:
                    if key not in config_filenames:
                        errors.append(
                            f"{path}: batch_roles key '{key}' "
                            f"not found in configs list"
                        )

        if "run_flags" in data:
            if not isinstance(data["run_flags"], dict):
                errors.append(f"{path}: 'run_flags' must be a dict")
            elif isinstance(data.get("configs"), list):
                config_filenames = {Path(c).name for c in data["configs"]}
                for key, flags in data["run_flags"].items():
                    if key not in config_filenames:
                        errors.append(
                            f"{path}: run_flags key '{key}' "
                            f"not found in configs list"
                        )
                    if isinstance(flags, dict) and "extra_args" in flags:
                        if not isinstance(flags["extra_args"], list):
                            errors.append(
                                f"{path}: run_flags['{key}'].extra_args "
                                f"must be a list"
                            )

    except FileNotFoundError as e:
        errors.append(f"{path}: {e}")
    except yaml.YAMLError as e:
        errors.append(f"{path}: YAML parse error: {e}")
    except Exception as e:
        errors.append(f"{path}: Unexpected error: {e}")

    return errors


def main():
    """Main validation logic."""
    errors = []

    # Validate experiment configs
    config_dir = Path("experiments/configs")
    if not config_dir.exists():
        print(f"❌ Config directory not found: {config_dir}")
        sys.exit(1)

    config_files = list(config_dir.glob("*.yaml"))
    for config_file in sorted(config_files):
        errors.extend(validate_config_file(config_file))

    # Validate suite configs
    suite_dir = Path("experiments/suites")
    if suite_dir.exists():
        suite_files = list(suite_dir.glob("*.yaml"))
        for suite_file in sorted(suite_files):
            errors.extend(validate_suite_file(suite_file))

    if errors:
        print("❌ Config validation errors:")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)
    else:
        config_count = len(config_files)
        suite_count = len(list(suite_dir.glob("*.yaml"))) if suite_dir.exists() else 0
        print(f"✅ All configs valid ({config_count} configs, {suite_count} suites)")
        sys.exit(0)


if __name__ == "__main__":
    main()
