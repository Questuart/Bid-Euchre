"""Tests for BatchIntent dataclass."""

import pytest

from bid_euchre.experiments.batch import BatchIntent


class TestBatchIntentRoundTrip:
    """Test serialization round-trip."""

    def test_to_dict_from_dict_roundtrip(self):
        original = BatchIntent(
            batch_id="promotion_20260210",
            batch_role="dataset_greedy",
            batch_purpose="promotion",
        )
        d = original.to_dict()
        restored = BatchIntent.from_dict(d)
        assert restored == original

    def test_to_dict_keys(self):
        intent = BatchIntent(
            batch_id="regression_42",
            batch_role="baseline",
            batch_purpose="regression",
        )
        d = intent.to_dict()
        assert set(d.keys()) == {"batch_id", "batch_role", "batch_purpose"}
        assert d["batch_id"] == "regression_42"
        assert d["batch_role"] == "baseline"
        assert d["batch_purpose"] == "regression"


class TestBatchIntentValidation:
    """Test validation rules."""

    def test_empty_batch_id_raises(self):
        with pytest.raises(ValueError, match="batch_id must be non-empty"):
            BatchIntent(batch_id="", batch_role="role", batch_purpose="exploration")

    def test_empty_batch_role_raises(self):
        with pytest.raises(ValueError, match="batch_role must be non-empty"):
            BatchIntent(batch_id="id", batch_role="", batch_purpose="exploration")

    def test_invalid_batch_purpose_raises(self):
        with pytest.raises(ValueError, match="batch_purpose must be one of"):
            BatchIntent(batch_id="id", batch_role="role", batch_purpose="invalid")

    @pytest.mark.parametrize("purpose", ["promotion", "regression", "exploration"])
    def test_all_valid_purposes(self, purpose):
        intent = BatchIntent(
            batch_id="test_batch",
            batch_role="test_role",
            batch_purpose=purpose,
        )
        assert intent.batch_purpose == purpose


class TestBatchIntentBackwardCompatibility:
    """Verify backward compatibility: no batch keys when flags absent."""

    def test_no_batch_created_for_none_values(self):
        """When no batch flags are given, BatchIntent should not be created.

        This tests the pattern used in run_experiment.py: only create
        BatchIntent when args.batch_id is truthy.
        """
        batch_id = None
        batch_role = None

        # Simulate the guard in run_experiment.py
        meta = {"run_id": "test_run", "seed": 42}

        if batch_id:
            intent = BatchIntent(
                batch_id=batch_id,
                batch_role=batch_role,
                batch_purpose="exploration",
            )
            meta["batch"] = intent.to_dict()
            meta["intent"] = intent.batch_purpose

        assert "batch" not in meta
        assert "intent" not in meta
