"""Tests for model artifact freeze/verify utilities."""
import json

import pytest

from bid_euchre.models.freeze import freeze_artifact, require_frozen, verify_frozen


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
