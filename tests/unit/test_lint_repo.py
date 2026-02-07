"""Tests for artifact discovery lint rules in scripts/lint_repo.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.lint_repo import (
    _is_model_artifact,
    check_artifacts_require_freeze,
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
