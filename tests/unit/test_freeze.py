"""Tests for model artifact freeze/verify utilities."""

import json

import pytest

from bid_euchre.models.freeze import (
    content_hash,
    extract_artifact_provenance,
    freeze_artifact,
    freeze_with_provenance,
    require_frozen,
    sha256_file,
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
        assert content_hash(base) == content_hash(with_freeze)

    def test_detects_content_change(self):
        """Hash must differ when content changes."""
        original = {"model_type": "olsa", "contracts": {"suit": {"coef": [1, 2]}}}
        modified = {"model_type": "olsa", "contracts": {"suit": {"coef": [1, 3]}}}
        assert content_hash(original) != content_hash(modified)


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


class TestSha256File:
    def test_returns_64_char_hex(self, artifact_file):
        digest = sha256_file(artifact_file)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("hello")
        assert sha256_file(f1) == sha256_file(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert sha256_file(f1) != sha256_file(f2)


class TestFreezeWithProvenance:
    @pytest.fixture
    def artifact_with_metadata(self, tmp_path):
        """Create a sample artifact with a metadata section."""
        path = tmp_path / "artifact.json"
        data = {
            "schema_version": "action_value_olsa_v1",
            "models": {"suit": {"coef": [1, 2]}},
            "metadata": {
                "training_seed": 42,
                "git_sha": "abc123",
            },
        }
        path.write_text(json.dumps(data, indent=2))
        return path

    def test_injects_provenance_and_freezes(self, artifact_with_metadata):
        provenance = {
            "behavioral_validation": {
                "passed": True,
                "avg_bid": 4.82,
            }
        }
        result = freeze_with_provenance(artifact_with_metadata, provenance)
        assert result["frozen_at"] is not None
        assert result["artifact_sha256"] is not None
        assert result["metadata"]["behavioral_validation"]["passed"] is True
        assert result["metadata"]["behavioral_validation"]["avg_bid"] == 4.82

    def test_provenance_persists_to_file(self, artifact_with_metadata):
        provenance = {"dataset_sha256": "def456"}
        freeze_with_provenance(artifact_with_metadata, provenance)
        data = json.loads(artifact_with_metadata.read_text())
        assert data["metadata"]["dataset_sha256"] == "def456"
        assert data["frozen_at"] is not None

    def test_preserves_existing_metadata(self, artifact_with_metadata):
        provenance = {"dataset_sha256": "def456"}
        result = freeze_with_provenance(artifact_with_metadata, provenance)
        assert result["metadata"]["training_seed"] == 42
        assert result["metadata"]["git_sha"] == "abc123"

    def test_verifies_after_provenance_freeze(self, artifact_with_metadata):
        provenance = {"dataset_sha256": "def456"}
        freeze_with_provenance(artifact_with_metadata, provenance)
        assert verify_frozen(artifact_with_metadata) is True

    def test_rejects_already_frozen(self, artifact_with_metadata):
        freeze_artifact(artifact_with_metadata)
        with pytest.raises(ValueError, match="already frozen"):
            freeze_with_provenance(artifact_with_metadata, {"extra": "data"})

    def test_rejects_missing_metadata(self, tmp_path):
        path = tmp_path / "no_meta.json"
        path.write_text(json.dumps({"schema_version": 1}))
        with pytest.raises(KeyError, match="metadata"):
            freeze_with_provenance(path, {"extra": "data"})

    def test_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            freeze_with_provenance(tmp_path / "nope.json", {})


class TestExtractArtifactProvenance:
    def test_extracts_from_frozen_artifact(self, tmp_path):
        path = tmp_path / "artifact.json"
        data = {
            "schema_version": "action_value_olsa_v1",
            "target": "net_points",
            "models": {
                "suit": {"r_squared": 0.557},
                "high": {"r_squared": 0.533},
                "low": {"r_squared": 0.514},
                "pass": {"r_squared": 0.046},
            },
            "metadata": {
                "model_class": "ols",
                "training_seed": 42,
                "dataset_sha256": "abc123def456ghi789",
                "continuation_artifact_sha256": "xyz789abc012def345",
            },
        }
        path.write_text(json.dumps(data, indent=2))
        freeze_artifact(path)

        prov = extract_artifact_provenance(path)
        assert prov["frozen"] is True
        assert prov["schema_version"] == "action_value_olsa_v1"
        assert prov["target"] == "net_points"
        assert prov["model_class"] == "ols"
        assert prov["training_seed"] == 42
        assert prov["artifact_sha256"] is not None
        assert len(prov["artifact_sha256"]) == 12
        assert prov["dataset_sha256"] == "abc123def456"
        assert prov["continuation_artifact_sha256"] == "xyz789abc012"
        assert prov["r_squared"]["suit"] == 0.557

    def test_extracts_from_unfrozen_artifact(self, tmp_path):
        path = tmp_path / "artifact.json"
        data = {
            "schema_version": "action_value_gbt_v1",
            "target": "net_points",
            "models": {"suit": {"r_squared": 0.6}},
            "metadata": {"model_class": "gbt", "training_seed": 99},
        }
        path.write_text(json.dumps(data))
        prov = extract_artifact_provenance(path)
        assert prov["frozen"] is False
        assert prov["model_class"] == "gbt"
        assert "artifact_sha256" not in prov

    def test_handles_nonexistent_file(self, tmp_path):
        prov = extract_artifact_provenance(tmp_path / "nope.json")
        assert prov["frozen"] is False
        assert "error" in prov

    def test_handles_missing_metadata(self, tmp_path):
        path = tmp_path / "minimal.json"
        path.write_text(json.dumps({"schema_version": 1}))
        prov = extract_artifact_provenance(path)
        assert prov["model_class"] is None
        assert prov["training_seed"] is None

    def test_handles_corrupt_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        prov = extract_artifact_provenance(path)
        assert "error" in prov
