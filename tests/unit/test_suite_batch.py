"""Tests for suite batch propagation and per-config overrides."""

import argparse
from unittest.mock import patch

import pytest

from scripts.run_suite import (
    build_experiment_cmd,
    create_suite_rollup,
    resolve_batch_context,
)
from scripts.validate_configs import validate_suite_file


def _make_args(**overrides):
    """Create a minimal argparse.Namespace for tests."""
    defaults = {
        "batch_id": None,
        "batch_purpose": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_suite(**overrides):
    """Create a minimal suite dict for tests."""
    base = {
        "suite_name": "test_suite",
        "parameters": {"seed": 42, "n_per": 20, "log_level": "none"},
        "configs": [
            "experiments/configs/quick_test.yaml",
            "experiments/configs/baseline_greedy.yaml",
        ],
    }
    base.update(overrides)
    return base


class TestResolveBatchContext:
    """Tests for resolve_batch_context."""

    def test_no_batch_returns_none(self):
        suite = _make_suite()
        args = _make_args()
        batch_id, batch_purpose, config_overrides = resolve_batch_context(
            suite, args, "test_suite", 42
        )
        assert batch_id is None
        assert batch_purpose is None
        assert config_overrides == {}

    def test_suite_yaml_batch_purpose(self):
        suite = _make_suite(batch={"batch_purpose": "promotion"})
        args = _make_args()
        batch_id, batch_purpose, _ = resolve_batch_context(
            suite, args, "test_suite", 42
        )
        assert batch_purpose == "promotion"
        assert batch_id is not None  # auto-generated
        assert batch_id.startswith("test_suite_42_")

    def test_suite_yaml_batch_id_and_purpose(self):
        suite = _make_suite(
            batch={"batch_id": "manual_123", "batch_purpose": "exploration"}
        )
        args = _make_args()
        batch_id, batch_purpose, _ = resolve_batch_context(
            suite, args, "test_suite", 42
        )
        assert batch_id == "manual_123"
        assert batch_purpose == "exploration"

    def test_cli_override_precedence(self):
        suite = _make_suite(
            batch={"batch_id": "yaml_id", "batch_purpose": "exploration"}
        )
        args = _make_args(batch_id="cli_id", batch_purpose="promotion")
        batch_id, batch_purpose, _ = resolve_batch_context(
            suite, args, "test_suite", 42
        )
        assert batch_id == "cli_id"
        assert batch_purpose == "promotion"

    def test_batch_id_without_purpose_fails(self):
        suite = _make_suite()
        args = _make_args(batch_id="orphan_id")
        with pytest.raises(ValueError, match="batch_id provided without batch_purpose"):
            resolve_batch_context(suite, args, "test_suite", 42)

    def test_batch_purpose_auto_generates_id(self):
        suite = _make_suite()
        args = _make_args(batch_purpose="regression")
        batch_id, batch_purpose, _ = resolve_batch_context(
            suite, args, "test_suite", 42
        )
        assert batch_purpose == "regression"
        assert batch_id.startswith("test_suite_42_")

    def test_config_overrides_passed_through(self):
        overrides = {
            "quick_test.yaml": {"batch_role": "dataset", "extra_args": ["--emit-bidless-dataset"]},
        }
        suite = _make_suite(config_overrides=overrides)
        args = _make_args()
        _, _, config_overrides = resolve_batch_context(
            suite, args, "test_suite", 42
        )
        assert config_overrides == overrides


class TestBuildExperimentCmd:
    """Tests for build_experiment_cmd."""

    def test_without_batch(self):
        cmd = build_experiment_cmd(
            "experiments/configs/quick_test.yaml", 42, 20, "none", "data/runs",
            None, None, None, None,
        )
        assert "--batch-id" not in cmd
        assert "--batch-role" not in cmd
        assert "--batch-purpose" not in cmd
        assert "--config" in cmd

    def test_with_batch(self):
        cmd = build_experiment_cmd(
            "experiments/configs/quick_test.yaml", 42, 20, "none", "data/runs",
            "batch_001", "dataset", "promotion", None,
        )
        assert "--batch-id" in cmd
        idx = cmd.index("--batch-id")
        assert cmd[idx + 1] == "batch_001"
        assert "--batch-role" in cmd
        assert "--batch-purpose" in cmd

    def test_with_extra_args(self):
        cmd = build_experiment_cmd(
            "experiments/configs/quick_test.yaml", 42, 20, "none", "data/runs",
            "batch_001", "dataset", "promotion",
            ["--emit-bidless-dataset", "--emit-bidless-outcomes-dataset"],
        )
        assert "--emit-bidless-dataset" in cmd
        assert "--emit-bidless-outcomes-dataset" in cmd

    def test_extra_args_without_batch(self):
        cmd = build_experiment_cmd(
            "experiments/configs/quick_test.yaml", 42, 20, "none", "data/runs",
            None, None, None, ["--force"],
        )
        assert "--force" in cmd
        assert "--batch-id" not in cmd


class TestRollupBatchMetadata:
    """Tests for batch metadata in rollup.json."""

    def test_rollup_without_batch(self, tmp_path):
        suite = _make_suite()
        member_runs = [
            {"config_path": "experiments/configs/quick_test.yaml",
             "run_id": "quick_test_42_20260210", "run_dir": "quick_test_42_20260210",
             "status": "ok", "git_sha": "abc1234"},
        ]
        # Create a fake run dir with results
        run_dir = tmp_path / "quick_test_42_20260210"
        run_dir.mkdir()
        (run_dir / "results").mkdir()

        with patch("scripts.run_suite.get_git_sha", return_value="abc1234"), \
             patch("scripts.run_suite.compute_file_sha256", return_value="deadbeef"):
            rollup_dir = create_suite_rollup(
                suite, "experiments/suites/test.yaml",
                {"seed": 42, "n_per": 20, "log_level": "none"},
                member_runs, tmp_path,
            )

        import json
        rollup = json.loads((rollup_dir / "rollup.json").read_text())
        assert "batch" not in rollup

    def test_rollup_with_batch(self, tmp_path):
        suite = _make_suite(
            config_overrides={
                "quick_test.yaml": {"batch_role": "dataset"},
            }
        )
        member_runs = [
            {"config_path": "experiments/configs/quick_test.yaml",
             "run_id": "quick_test_42_20260210", "run_dir": "quick_test_42_20260210",
             "status": "ok", "git_sha": "abc1234"},
            {"config_path": "experiments/configs/baseline_greedy.yaml",
             "run_id": "baseline_greedy_42_20260210", "run_dir": "baseline_greedy_42_20260210",
             "status": "ok", "git_sha": "abc1234"},
        ]
        for run in member_runs:
            d = tmp_path / run["run_dir"]
            d.mkdir()
            (d / "results").mkdir()

        with patch("scripts.run_suite.get_git_sha", return_value="abc1234"), \
             patch("scripts.run_suite.compute_file_sha256", return_value="deadbeef"):
            rollup_dir = create_suite_rollup(
                suite, "experiments/suites/test.yaml",
                {"seed": 42, "n_per": 20, "log_level": "none"},
                member_runs, tmp_path,
                batch_id="batch_001", batch_purpose="promotion",
                config_overrides=suite.get("config_overrides", {}),
            )

        import json
        rollup = json.loads((rollup_dir / "rollup.json").read_text())
        assert "batch" in rollup
        assert rollup["batch"]["batch_id"] == "batch_001"
        assert rollup["batch"]["batch_purpose"] == "promotion"
        assert rollup["batch"]["config_roles"]["quick_test.yaml"] == "dataset"
        assert rollup["batch"]["config_roles"]["baseline_greedy.yaml"] == "baseline"


class TestValidateSuiteWithBatch:
    """Tests for validate_configs.py suite validation with batch fields."""

    def test_valid_suite_with_batch(self, tmp_path):
        suite_yaml = tmp_path / "test.yaml"
        suite_yaml.write_text(
            "suite_name: test\n"
            "parameters:\n  seed: 42\n  n_per: 20\n"
            "batch:\n  batch_purpose: promotion\n"
            "configs:\n  - experiments/configs/quick_test.yaml\n"
        )
        errors = validate_suite_file(suite_yaml)
        assert errors == []

    def test_invalid_batch_role_in_overrides(self, tmp_path):
        suite_yaml = tmp_path / "test.yaml"
        suite_yaml.write_text(
            "suite_name: test\n"
            "parameters:\n  seed: 42\n  n_per: 20\n"
            "config_overrides:\n"
            "  quick_test.yaml:\n"
            "    batch_role: invalid_role\n"
            "configs:\n  - experiments/configs/quick_test.yaml\n"
        )
        errors = validate_suite_file(suite_yaml)
        assert any("batch_role" in e for e in errors)

    def test_missing_batch_purpose(self, tmp_path):
        suite_yaml = tmp_path / "test.yaml"
        suite_yaml.write_text(
            "suite_name: test\n"
            "parameters:\n  seed: 42\n  n_per: 20\n"
            "batch:\n  batch_id: some_id\n"
            "configs:\n  - experiments/configs/quick_test.yaml\n"
        )
        errors = validate_suite_file(suite_yaml)
        assert any("batch_purpose is required" in e for e in errors)

    def test_invalid_batch_purpose(self, tmp_path):
        suite_yaml = tmp_path / "test.yaml"
        suite_yaml.write_text(
            "suite_name: test\n"
            "parameters:\n  seed: 42\n  n_per: 20\n"
            "batch:\n  batch_purpose: invalid\n"
            "configs:\n  - experiments/configs/quick_test.yaml\n"
        )
        errors = validate_suite_file(suite_yaml)
        assert any("batch_purpose must be one of" in e for e in errors)

    def test_suite_without_batch_unchanged(self, tmp_path):
        suite_yaml = tmp_path / "test.yaml"
        suite_yaml.write_text(
            "suite_name: test\n"
            "parameters:\n  seed: 42\n  n_per: 20\n"
            "configs:\n  - experiments/configs/quick_test.yaml\n"
        )
        errors = validate_suite_file(suite_yaml)
        assert errors == []

    def test_config_override_invalid_key(self, tmp_path):
        """Test validation fails when override key doesn't match any config."""
        suite_path = tmp_path / "suite.yaml"
        config_path = tmp_path / "quick_test.yaml"
        config_path.write_text("strategies: []\nparameters: {}")

        suite_path.write_text(
            "suite_name: test\n"
            "configs:\n"
            "  - quick_test.yaml\n"
            "parameters: {}\n"
            "batch:\n"
            "  batch_purpose: promotion\n"
            "config_overrides:\n"
            "  nonexistent.yaml:\n"  # Does not match quick_test.yaml
            "    batch_role: dataset\n"
        )

        # validate_suite_file returns list[str] of errors, does NOT raise
        errors = validate_suite_file(suite_path)
        assert len(errors) > 0
        assert any("does not match any config" in err for err in errors)

    def test_extra_args_non_string_element(self, tmp_path):
        """Test validation fails when extra_args contains non-string."""
        suite_path = tmp_path / "suite.yaml"
        config_path = tmp_path / "quick_test.yaml"
        config_path.write_text("strategies: []\nparameters: {}")

        suite_path.write_text(
            "suite_name: test\n"
            "configs:\n"
            "  - quick_test.yaml\n"
            "parameters: {}\n"
            "batch:\n"
            "  batch_purpose: promotion\n"
            "config_overrides:\n"
            "  quick_test.yaml:\n"
            "    extra_args: [42, '--flag']\n"  # 42 is not a string
        )

        errors = validate_suite_file(suite_path)
        assert len(errors) > 0
        assert any("must be a string" in err for err in errors)

    def test_config_override_valid(self, tmp_path):
        """Test validation passes with valid override."""
        suite_path = tmp_path / "suite.yaml"
        config_path = tmp_path / "quick_test.yaml"
        config_path.write_text("strategies: []\nparameters: {}")

        suite_path.write_text(
            "suite_name: test\n"
            "configs:\n"
            "  - quick_test.yaml\n"
            "parameters: {}\n"
            "batch:\n"
            "  batch_purpose: exploration\n"
            "config_overrides:\n"
            "  quick_test.yaml:\n"
            "    batch_role: dataset\n"
            "    extra_args: ['--some-flag', '--another-flag']\n"
        )

        errors = validate_suite_file(suite_path)
        assert len(errors) == 0  # Should return empty error list
