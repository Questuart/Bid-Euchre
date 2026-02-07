"""Tests for BatchMetadata dataclass and CLI factory."""

import pytest

from bid_euchre.experiments.batch import BatchMetadata


class TestBatchMetadata:
    """Tests for BatchMetadata construction and validation."""

    def test_valid_construction(self):
        bm = BatchMetadata(
            batch_id="test_001",
            batch_role="dataset",
            batch_purpose="exploration",
        )
        assert bm.batch_id == "test_001"
        assert bm.batch_role == "dataset"
        assert bm.batch_purpose == "exploration"

    def test_to_dict_roundtrip(self):
        bm = BatchMetadata(
            batch_id="test_001",
            batch_role="baseline",
            batch_purpose="promotion",
        )
        d = bm.to_dict()
        assert d == {
            "batch_id": "test_001",
            "batch_role": "baseline",
            "batch_purpose": "promotion",
        }

    def test_invalid_role_rejected(self):
        with pytest.raises(ValueError, match="batch_role must be one of"):
            BatchMetadata(
                batch_id="test_001",
                batch_role="unknown",
                batch_purpose="exploration",
            )

    def test_invalid_purpose_rejected(self):
        with pytest.raises(ValueError, match="batch_purpose must be one of"):
            BatchMetadata(
                batch_id="test_001",
                batch_role="dataset",
                batch_purpose="unknown",
            )

    def test_empty_batch_id_rejected(self):
        with pytest.raises(ValueError, match="batch_id must be non-empty"):
            BatchMetadata(
                batch_id="",
                batch_role="dataset",
                batch_purpose="exploration",
            )

    def test_frozen(self):
        bm = BatchMetadata(
            batch_id="test_001",
            batch_role="dataset",
            batch_purpose="exploration",
        )
        with pytest.raises(AttributeError):
            bm.batch_id = "modified"

    def test_all_valid_roles(self):
        for role in ["dataset", "baseline", "challenger", "gate"]:
            bm = BatchMetadata(
                batch_id="test", batch_role=role, batch_purpose="exploration"
            )
            assert bm.batch_role == role

    def test_all_valid_purposes(self):
        for purpose in ["promotion", "exploration", "regression"]:
            bm = BatchMetadata(
                batch_id="test", batch_role="dataset", batch_purpose=purpose
            )
            assert bm.batch_purpose == purpose


class TestFromCliArgs:
    """Tests for BatchMetadata.from_cli_args factory."""

    def test_all_none_returns_none(self):
        result = BatchMetadata.from_cli_args(None, None, None)
        assert result is None

    def test_partial_raises(self):
        with pytest.raises(ValueError, match="all-or-nothing"):
            BatchMetadata.from_cli_args("test_001", None, None)

    def test_partial_raises_two_of_three(self):
        with pytest.raises(ValueError, match="all-or-nothing"):
            BatchMetadata.from_cli_args("test_001", "dataset", None)

    def test_all_provided(self):
        result = BatchMetadata.from_cli_args("test_001", "dataset", "exploration")
        assert result is not None
        assert result.batch_id == "test_001"
        assert result.batch_role == "dataset"
        assert result.batch_purpose == "exploration"

    def test_all_provided_validates_role(self):
        with pytest.raises(ValueError, match="batch_role must be one of"):
            BatchMetadata.from_cli_args("test_001", "bad_role", "exploration")
