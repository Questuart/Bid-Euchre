"""Tests for artifact discovery and schema lint rules in scripts/lint_repo.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.lint_repo import (
    _is_gate_artifact,
    _is_model_artifact,
    _is_split_manifest,
    check_artifacts_require_freeze,
    check_gate_artifacts_schema,
    check_split_manifest_schema,
)


def _write_json(tmp_path: Path, rel_path: str, obj: object) -> None:
    """Write a JSON object at rel_path under tmp_path."""
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj), encoding="utf-8")


def _write_file(tmp_path: Path, rel_path: str, content: str) -> None:
    """Write raw text at rel_path under tmp_path."""
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# -- _is_model_artifact tests -------------------------------------------------


class TestIsModelArtifact:
    """Tests for the _is_model_artifact helper."""

    def test_olsa_artifact_under_data(self):
        assert _is_model_artifact("data/models/olsa_v1.json") is True

    def test_b0_artifact_under_data(self):
        assert _is_model_artifact("data/models/b0_weights.json") is True

    def test_teacher_artifact_under_data(self):
        assert _is_model_artifact("data/models/teacher_config.json") is True

    def test_case_insensitive_match(self):
        assert _is_model_artifact("data/models/OLSa_V2.json") is True
        assert _is_model_artifact("data/models/B0_FINAL.json") is True
        assert _is_model_artifact("data/models/Teacher_Model.json") is True

    def test_nested_data_path(self):
        assert _is_model_artifact("data/runs/abc/olsa_artifact.json") is True

    def test_not_under_data(self):
        assert _is_model_artifact("src/models/olsa_v1.json") is False

    def test_not_json_extension(self):
        assert _is_model_artifact("data/models/olsa_v1.parquet") is False
        assert _is_model_artifact("data/models/olsa_v1.pkl") is False

    def test_no_pattern_match(self):
        assert _is_model_artifact("data/models/random_config.json") is False
        assert _is_model_artifact("data/models/settings.json") is False

    def test_exempt_meta_json(self):
        assert _is_model_artifact("data/runs/abc/meta.json") is False

    def test_exempt_rollup_json(self):
        assert _is_model_artifact("data/runs/abc/rollup.json") is False

    def test_exempt_canonical_summary(self):
        assert _is_model_artifact("data/runs/abc/canonical_summary.json") is False


# -- check_artifacts_require_freeze tests ------------------------------------


class TestCheckArtifactsRequireFreeze:
    """Tests for the check_artifacts_require_freeze lint rule."""

    def test_frozen_artifact_passes(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/models/olsa_v1.json",
            {
                "frozen_at": "2026-01-15T00:00:00Z",
                "version": "1.0",
            },
        )
        violations = check_artifacts_require_freeze(
            ["data/models/olsa_v1.json"],
            tmp_path,
        )
        assert violations == []

    def test_unfrozen_artifact_fails(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/models/olsa_v1.json",
            {
                "frozen_at": None,
                "version": "1.0",
            },
        )
        violations = check_artifacts_require_freeze(
            ["data/models/olsa_v1.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "artifact-requires-freeze"
        assert "frozen_at is null" in violations[0].message

    def test_missing_frozen_at_field_fails(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/models/b0_weights.json",
            {
                "version": "1.0",
            },
        )
        violations = check_artifacts_require_freeze(
            ["data/models/b0_weights.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "artifact-requires-freeze"

    def test_exempt_files_pass(self, tmp_path: Path):
        _write_json(tmp_path, "data/runs/abc/meta.json", {"some": "data"})
        violations = check_artifacts_require_freeze(
            ["data/runs/abc/meta.json"],
            tmp_path,
        )
        assert violations == []

    def test_non_data_paths_ignored(self, tmp_path: Path):
        _write_json(tmp_path, "src/models/olsa_v1.json", {"frozen_at": None})
        violations = check_artifacts_require_freeze(
            ["src/models/olsa_v1.json"],
            tmp_path,
        )
        assert violations == []

    def test_invalid_json_flagged(self, tmp_path: Path):
        _write_file(tmp_path, "data/models/olsa_bad.json", "not valid json {{{")
        violations = check_artifacts_require_freeze(
            ["data/models/olsa_bad.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "artifact-requires-freeze"
        assert "not valid JSON" in violations[0].message

    def test_nonexistent_file_skipped(self, tmp_path: Path):
        """A file in the changed list that doesn't exist on disk is skipped."""
        violations = check_artifacts_require_freeze(
            ["data/models/olsa_ghost.json"],
            tmp_path,
        )
        assert violations == []

    def test_multiple_artifacts_mixed(self, tmp_path: Path):
        """Frozen and unfrozen artifacts in same batch: only unfrozen flagged."""
        _write_json(
            tmp_path,
            "data/models/olsa_frozen.json",
            {
                "frozen_at": "2026-01-15T00:00:00Z",
            },
        )
        _write_json(
            tmp_path,
            "data/models/b0_unfrozen.json",
            {
                "version": "1.0",
            },
        )
        violations = check_artifacts_require_freeze(
            ["data/models/olsa_frozen.json", "data/models/b0_unfrozen.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].path == "data/models/b0_unfrozen.json"

    def test_non_artifact_json_ignored(self, tmp_path: Path):
        """JSON files under data/ that don't match artifact patterns are ignored."""
        _write_json(tmp_path, "data/models/settings.json", {"frozen_at": None})
        violations = check_artifacts_require_freeze(
            ["data/models/settings.json"],
            tmp_path,
        )
        assert violations == []


# -- _is_gate_artifact tests --------------------------------------------------


class TestIsGateArtifact:
    """Tests for the _is_gate_artifact helper."""

    def test_notebook_gate_matches(self):
        assert _is_gate_artifact("data/runs/abc/notebook_gate.json") is True

    def test_batch_gate_matches(self):
        assert _is_gate_artifact("data/runs/abc/batch_gate.json") is True

    def test_gate_substring_matches(self):
        assert (
            _is_gate_artifact("data/runs/abc/play_policy_gate_aggregate.json") is True
        )

    def test_non_gate_json_ignored(self):
        assert _is_gate_artifact("data/runs/abc/meta.json") is False
        assert _is_gate_artifact("data/runs/abc/rollup.json") is False

    def test_non_data_path_ignored(self):
        assert _is_gate_artifact("src/configs/notebook_gate.json") is False

    def test_non_json_ignored(self):
        assert _is_gate_artifact("data/runs/abc/gate_results.txt") is False


# -- check_gate_artifacts_schema tests ----------------------------------------


class TestCheckGateArtifactsSchema:
    """Tests for the check_gate_artifacts_schema lint rule."""

    def test_valid_pass_gate_passes(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/notebook_gate.json",
            {
                "schema_version": 1,
                "gate_status": "PASS",
                "created_at_utc": "2026-01-15T00:00:00Z",
            },
        )
        violations = check_gate_artifacts_schema(
            ["data/runs/abc/notebook_gate.json"],
            tmp_path,
        )
        assert violations == []

    def test_fail_gate_flagged(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/notebook_gate.json",
            {
                "schema_version": 1,
                "gate_status": "FAIL",
                "created_at_utc": "2026-01-15T00:00:00Z",
            },
        )
        violations = check_gate_artifacts_schema(
            ["data/runs/abc/notebook_gate.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "gate-artifact-schema"
        assert "FAIL" in violations[0].message

    def test_missing_fields_flagged(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/batch_gate.json",
            {"schema_version": 1},
        )
        violations = check_gate_artifacts_schema(
            ["data/runs/abc/batch_gate.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "gate-artifact-schema"
        assert "missing required fields" in violations[0].message

    def test_invalid_json_flagged(self, tmp_path: Path):
        _write_file(tmp_path, "data/runs/abc/notebook_gate.json", "not json {{{")
        violations = check_gate_artifacts_schema(
            ["data/runs/abc/notebook_gate.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "gate-artifact-schema"
        assert "not valid JSON" in violations[0].message

    def test_non_gate_files_ignored(self, tmp_path: Path):
        _write_json(tmp_path, "data/runs/abc/meta.json", {"some": "data"})
        violations = check_gate_artifacts_schema(
            ["data/runs/abc/meta.json"],
            tmp_path,
        )
        assert violations == []

    def test_nonexistent_file_skipped(self, tmp_path: Path):
        violations = check_gate_artifacts_schema(
            ["data/runs/abc/notebook_gate.json"],
            tmp_path,
        )
        assert violations == []

    def test_non_data_path_ignored(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "src/notebook_gate.json",
            {"gate_status": "FAIL"},
        )
        violations = check_gate_artifacts_schema(
            ["src/notebook_gate.json"],
            tmp_path,
        )
        assert violations == []


# -- _is_split_manifest tests -------------------------------------------------


class TestIsSplitManifest:
    """Tests for the _is_split_manifest helper."""

    def test_split_manifest_json_matches(self):
        assert _is_split_manifest("data/runs/abc/split_manifest.json") is True

    def test_split_manifest_v2_matches(self):
        assert _is_split_manifest("data/runs/abc/split_manifest_v2.json") is True

    def test_split_manifest_with_suffix_matches(self):
        assert _is_split_manifest("some/path/split_manifest_train_test.json") is True

    def test_other_json_ignored(self):
        assert _is_split_manifest("data/runs/abc/meta.json") is False
        assert _is_split_manifest("data/runs/abc/manifest.json") is False

    def test_non_json_ignored(self):
        assert _is_split_manifest("data/runs/abc/split_manifest.txt") is False


# -- check_split_manifest_schema tests ----------------------------------------


class TestCheckSplitManifestSchema:
    """Tests for the check_split_manifest_schema lint rule."""

    def test_valid_two_way_passes(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/split_manifest.json",
            {
                "schema_version": 1,
                "split_type": "two_way",
                "split_seed": 42,
                "total_hand_ids": 1000,
                "partition_hashes": {"train": "abc123", "test": "def456"},
            },
        )
        violations = check_split_manifest_schema(
            ["data/runs/abc/split_manifest.json"],
            tmp_path,
        )
        assert violations == []

    def test_valid_three_way_passes(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/split_manifest.json",
            {
                "schema_version": 1,
                "split_type": "three_way",
                "split_seed": 42,
                "total_hand_ids": 1000,
                "partition_hashes": {
                    "train": "abc",
                    "val": "def",
                    "test": "ghi",
                },
            },
        )
        violations = check_split_manifest_schema(
            ["data/runs/abc/split_manifest.json"],
            tmp_path,
        )
        assert violations == []

    def test_invalid_split_type_flagged(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/split_manifest.json",
            {
                "schema_version": 1,
                "split_type": "four_way",
                "split_seed": 42,
                "total_hand_ids": 1000,
                "partition_hashes": {},
            },
        )
        violations = check_split_manifest_schema(
            ["data/runs/abc/split_manifest.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "split-manifest-schema"
        assert "four_way" in violations[0].message

    def test_missing_fields_flagged(self, tmp_path: Path):
        _write_json(
            tmp_path,
            "data/runs/abc/split_manifest.json",
            {"schema_version": 1, "split_type": "two_way"},
        )
        violations = check_split_manifest_schema(
            ["data/runs/abc/split_manifest.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "split-manifest-schema"
        assert "missing required fields" in violations[0].message

    def test_invalid_json_flagged(self, tmp_path: Path):
        _write_file(tmp_path, "data/runs/abc/split_manifest.json", "not json")
        violations = check_split_manifest_schema(
            ["data/runs/abc/split_manifest.json"],
            tmp_path,
        )
        assert len(violations) == 1
        assert violations[0].rule == "split-manifest-schema"
        assert "not valid JSON" in violations[0].message

    def test_non_manifest_files_ignored(self, tmp_path: Path):
        _write_json(tmp_path, "data/runs/abc/meta.json", {"some": "data"})
        violations = check_split_manifest_schema(
            ["data/runs/abc/meta.json"],
            tmp_path,
        )
        assert violations == []

    def test_nonexistent_file_skipped(self, tmp_path: Path):
        violations = check_split_manifest_schema(
            ["data/runs/abc/split_manifest.json"],
            tmp_path,
        )
        assert violations == []
