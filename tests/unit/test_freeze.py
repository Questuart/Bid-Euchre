"""Tests for model artifact freeze/verify utilities."""

import json

import pytest

from bid_euchre.models.freeze import (
    _content_hash,
    freeze_artifact,
    require_frozen,
    verify_frozen,
)


@pytest.fixture
def artifact_file(tmp_path):
    """Create a sample artifact JSON file."""
    path = tmp_path / "artifact.json"
    data = {
        "schema_version": 1,
        "model_type": "olsa",
        "frozen_at": None,
        "contracts": {"suit": {"coef": [1, 2, 3]}},
    }
    path.write_text(json.dumps(data, indent=2))
    return path


class TestFreezeArtifact:
    def test_freeze_sets_fields(self, artifact_file):
        result = freeze_artifact(artifact_file)
        assert result["frozen_at"] is not None
        assert result["artifact_sha256"] is not None
        assert len(result["artifact_sha256"]) == 64  # SHA-256 hex

    def test_freeze_persists_to_file(self, artifact_file):
        freeze_artifact(artifact_file)
        data = json.loads(artifact_file.read_text())
        assert data["frozen_at"] is not None
        assert data["artifact_sha256"] is not None

    def test_freeze_rejects_already_frozen(self, artifact_file):
        freeze_artifact(artifact_file)
        with pytest.raises(ValueError, match="already frozen"):
            freeze_artifact(artifact_file)

    def test_freeze_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            freeze_artifact(tmp_path / "nonexistent.json")

    def test_freeze_preserves_existing_fields(self, artifact_file):
        result = freeze_artifact(artifact_file)
        assert result["model_type"] == "olsa"
        assert result["contracts"]["suit"]["coef"] == [1, 2, 3]

    def test_freeze_writes_sort_keys(self, artifact_file):
        """Frozen file must have deterministic key ordering."""
        freeze_artifact(artifact_file)
        text = artifact_file.read_text()
        data = json.loads(text)
        keys = list(data.keys())
        assert keys == sorted(keys)


class TestVerifyFrozen:
    def test_verify_unfrozen(self, artifact_file):
        assert verify_frozen(artifact_file) is False

    def test_verify_after_freeze(self, artifact_file):
        freeze_artifact(artifact_file)
        assert verify_frozen(artifact_file) is True

    def test_verify_nonexistent(self, tmp_path):
        assert verify_frozen(tmp_path / "nope.json") is False

    def test_verify_corrupt_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        assert verify_frozen(path) is False

    def test_verify_missing_sha(self, artifact_file):
        """Frozen artifact with sha removed should fail verification."""
        freeze_artifact(artifact_file)
        data = json.loads(artifact_file.read_text())
        del data["artifact_sha256"]
        artifact_file.write_text(json.dumps(data))
        assert verify_frozen(artifact_file) is False

    def test_verify_detects_tampered_coefficient(self, artifact_file):
        """Modifying content after freeze must cause verify to fail."""
        freeze_artifact(artifact_file)
        data = json.loads(artifact_file.read_text())
        data["contracts"]["suit"]["coef"] = [99, 99, 99]
        artifact_file.write_text(json.dumps(data, indent=2, sort_keys=True))
        assert verify_frozen(artifact_file) is False

    def test_verify_detects_wrong_hash(self, artifact_file):
        """Replacing artifact_sha256 with a bogus value must fail."""
        freeze_artifact(artifact_file)
        data = json.loads(artifact_file.read_text())
        data["artifact_sha256"] = "0" * 64
        artifact_file.write_text(json.dumps(data, indent=2, sort_keys=True))
        assert verify_frozen(artifact_file) is False

    def test_verify_stable_across_reloads(self, artifact_file):
        """Verification must be idempotent across multiple reads."""
        freeze_artifact(artifact_file)
        assert verify_frozen(artifact_file) is True
        assert verify_frozen(artifact_file) is True
        assert verify_frozen(artifact_file) is True


class TestContentHash:
    def test_excludes_freeze_fields(self):
        """Hash must be identical with and without freeze fields."""
        base = {"model_type": "olsa", "contracts": {"suit": {"coef": [1, 2]}}}
        with_freeze = {
            **base,
            "frozen_at": "2026-01-01T00:00:00Z",
            "artifact_sha256": "abc",
        }
        assert _content_hash(base) == _content_hash(with_freeze)

    def test_detects_content_change(self):
        """Hash must differ when content changes."""
        original = {"model_type": "olsa", "contracts": {"suit": {"coef": [1, 2]}}}
        modified = {"model_type": "olsa", "contracts": {"suit": {"coef": [1, 3]}}}
        assert _content_hash(original) != _content_hash(modified)


class TestRequireFrozen:
    def test_require_strict_raises(self, artifact_file):
        with pytest.raises(ValueError, match="not frozen"):
            require_frozen(artifact_file, strict=True)

    def test_require_non_strict_warns(self, artifact_file):
        with pytest.warns(UserWarning, match="not frozen"):
            require_frozen(artifact_file, strict=False)

    def test_require_passes_when_frozen(self, artifact_file):
        freeze_artifact(artifact_file)
        require_frozen(artifact_file, strict=True)  # Should not raise
