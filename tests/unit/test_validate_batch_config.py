"""Tests for batch-specific suite validation fields.

Validates the batch_purpose, batch_roles, and run_flags fields
added to validate_suite_file() in scripts/validate_configs.py.
"""

from pathlib import Path

import yaml
from validate_configs import validate_suite_file


def _write_suite(tmp_path: Path, data: dict) -> Path:
    """Write a suite YAML to a temp file and return the path."""
    suite_path = tmp_path / "test_suite.yaml"
    with open(suite_path, "w") as f:
        yaml.safe_dump(data, f)
    return suite_path


class TestBatchFieldValidation:
    """Tests for batch-specific suite validation fields."""

    def _base_suite(self, tmp_path: Path) -> dict:
        """Return a minimal valid suite with batch fields.

        Uses config paths that exist under tmp_path so file-existence
        checks don't pollute the batch-field tests.
        """
        # Create stub config files so file-existence validation passes
        configs_dir = tmp_path / "experiments" / "configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        (configs_dir / "alpha.yaml").touch()
        (configs_dir / "beta.yaml").touch()

        return {
            "suite_name": "test_batch",
            "parameters": {"seed": 42, "n_per": 100},
            "configs": [
                str(configs_dir / "alpha.yaml"),
                str(configs_dir / "beta.yaml"),
            ],
            "batch_purpose": "promotion",
            "batch_roles": {
                "alpha.yaml": "role_a",
                "beta.yaml": "role_b",
            },
            "run_flags": {
                "alpha.yaml": {
                    "extra_args": ["--emit-bidless-dataset"],
                },
            },
        }

    def test_valid_batch_suite(self, tmp_path):
        """Suite with all batch fields valid produces no errors."""
        data = self._base_suite(tmp_path)
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_batch_roles_key_allowed(self, tmp_path):
        """Old-style suite without batch fields passes (backward compat)."""
        data = self._base_suite(tmp_path)
        del data["batch_purpose"]
        del data["batch_roles"]
        del data["run_flags"]
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_batch_roles_key_not_in_configs(self, tmp_path):
        """batch_roles key references config not in configs list -> error."""
        data = self._base_suite(tmp_path)
        data["batch_roles"]["nonexistent.yaml"] = "bad_role"
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert any(
            "batch_roles key 'nonexistent.yaml'" in e and "not found" in e
            for e in errors
        ), f"Expected batch_roles key error, got: {errors}"

    def test_run_flags_key_not_in_configs(self, tmp_path):
        """run_flags key references config not in configs list -> error."""
        data = self._base_suite(tmp_path)
        data["run_flags"]["nonexistent.yaml"] = {
            "extra_args": ["--some-flag"],
        }
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert any(
            "run_flags key 'nonexistent.yaml'" in e and "not found" in e
            for e in errors
        ), f"Expected run_flags key error, got: {errors}"

    def test_invalid_batch_purpose(self, tmp_path):
        """batch_purpose not in {promotion, regression, exploration} -> error."""
        data = self._base_suite(tmp_path)
        data["batch_purpose"] = "invalid_purpose"
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert any(
            "batch_purpose" in e and "invalid_purpose" in e
            for e in errors
        ), f"Expected batch_purpose error, got: {errors}"

    def test_extra_args_not_list(self, tmp_path):
        """run_flags.*.extra_args not a list -> error."""
        data = self._base_suite(tmp_path)
        data["run_flags"]["alpha.yaml"]["extra_args"] = "--not-a-list"
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert any(
            "extra_args" in e and "must be a list" in e
            for e in errors
        ), f"Expected extra_args list error, got: {errors}"

    def test_batch_roles_not_dict(self, tmp_path):
        """batch_roles that is not a dict -> error."""
        data = self._base_suite(tmp_path)
        data["batch_roles"] = ["not", "a", "dict"]
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert any(
            "'batch_roles' must be a dict" in e
            for e in errors
        ), f"Expected batch_roles dict error, got: {errors}"

    def test_run_flags_not_dict(self, tmp_path):
        """run_flags that is not a dict -> error."""
        data = self._base_suite(tmp_path)
        data["run_flags"] = "not_a_dict"
        path = _write_suite(tmp_path, data)
        errors = validate_suite_file(path)
        assert any(
            "'run_flags' must be a dict" in e
            for e in errors
        ), f"Expected run_flags dict error, got: {errors}"

    def test_valid_batch_purposes(self, tmp_path):
        """All three valid batch_purpose values pass validation."""
        for purpose in ("promotion", "regression", "exploration"):
            data = self._base_suite(tmp_path)
            data["batch_purpose"] = purpose
            path = _write_suite(tmp_path, data)
            errors = validate_suite_file(path)
            batch_errors = [e for e in errors if "batch_purpose" in e]
            assert batch_errors == [], (
                f"Purpose '{purpose}' should be valid, got: {batch_errors}"
            )
