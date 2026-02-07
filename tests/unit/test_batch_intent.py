"""
Unit tests for BatchIntent dataclass and serialization.

Tests:
- Construction and validation
- Serialization round-trip (to_dict / from_dict)
- Backward compatibility (no batch field when flags absent)
- Invalid purpose rejection
"""

import pytest

from bid_euchre.experiments.batch import VALID_BATCH_PURPOSES, BatchIntent


class TestBatchIntentConstruction:
    """Test BatchIntent construction and validation."""

    def test_valid_construction(self) -> None:
        bi = BatchIntent(
            batch_id="promotion_20260210",
            batch_role="dataset_greedy",
            batch_purpose="promotion",
        )
        assert bi.batch_id == "promotion_20260210"
        assert bi.batch_role == "dataset_greedy"
        assert bi.batch_purpose == "promotion"

    def test_all_valid_purposes(self) -> None:
        for purpose in VALID_BATCH_PURPOSES:
            bi = BatchIntent(batch_id="test", batch_role="role", batch_purpose=purpose)
            assert bi.batch_purpose == purpose

    def test_empty_batch_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="batch_id must be non-empty"):
            BatchIntent(batch_id="", batch_role="role", batch_purpose="promotion")

    def test_empty_batch_role_rejected(self) -> None:
        with pytest.raises(ValueError, match="batch_role must be non-empty"):
            BatchIntent(batch_id="test", batch_role="", batch_purpose="promotion")

    def test_invalid_purpose_rejected(self) -> None:
        with pytest.raises(ValueError, match="batch_purpose must be one of"):
            BatchIntent(batch_id="test", batch_role="role", batch_purpose="invalid")

    def test_frozen(self) -> None:
        bi = BatchIntent(batch_id="test", batch_role="role", batch_purpose="promotion")
        with pytest.raises(AttributeError):
            bi.batch_id = "changed"  # type: ignore[misc]


class TestBatchIntentSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_round_trip(self) -> None:
        original = BatchIntent(
            batch_id="promo_42",
            batch_role="dataset_glutton",
            batch_purpose="regression",
        )
        d = original.to_dict()
        restored = BatchIntent.from_dict(d)
        assert restored == original

    def test_to_dict_keys(self) -> None:
        bi = BatchIntent(
            batch_id="test", batch_role="role", batch_purpose="exploration"
        )
        d = bi.to_dict()
        assert set(d.keys()) == {"batch_id", "batch_role", "batch_purpose"}

    def test_from_dict_with_extra_keys(self) -> None:
        """Extra keys in dict should be ignored (forward compat)."""
        d = {
            "batch_id": "test",
            "batch_role": "role",
            "batch_purpose": "promotion",
            "extra_field": "ignored",
        }
        bi = BatchIntent.from_dict(d)
        assert bi.batch_id == "test"

    def test_from_dict_missing_key(self) -> None:
        with pytest.raises(KeyError):
            BatchIntent.from_dict({"batch_id": "test", "batch_role": "role"})


class TestValidBatchPurposes:
    """Test the VALID_BATCH_PURPOSES constant."""

    def test_expected_values(self) -> None:
        assert VALID_BATCH_PURPOSES == {"promotion", "regression", "exploration"}

    def test_is_frozenset(self) -> None:
        assert isinstance(VALID_BATCH_PURPOSES, frozenset)
