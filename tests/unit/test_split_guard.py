"""Tests for split-access enforcement via split_guard.

Tests cover:
- Correct DataFrame filtering for train/val/test splits
- Test-split blocking during HITL (active_split="val")
- Test-split access during blind evaluation (active_split="test")
- Partition hash verification (pass and mismatch)
- Unknown split name rejection
- Two-way manifest handling (no val split)
"""

from pathlib import Path

import pandas as pd
import pytest

from bid_euchre.diagnostics.split_guard import require_split
from bid_euchre.models.splits import create_grouped_split


@pytest.fixture
def sample_parquet(tmp_path: Path) -> Path:
    """Create a small parquet file for testing (100 hands, 4 seats each)."""
    rows = []
    for hand_id in range(100):
        for seat in range(4):
            rows.append({"hand_id": hand_id, "seat": seat, "tricks_won": 5.0})
    df = pd.DataFrame(rows)
    parquet_path = tmp_path / "bidless.parquet"
    df.to_parquet(parquet_path)
    return parquet_path


@pytest.fixture
def sample_df(sample_parquet: Path) -> pd.DataFrame:
    return pd.read_parquet(sample_parquet)


@pytest.fixture
def three_way_split(sample_df, sample_parquet):
    """Create a three-way split and return (df, manifest)."""
    _train, _val, _test, manifest = create_grouped_split(
        sample_df,
        seed=42,
        source_run_id="test_run",
        source_parquet_path=str(sample_parquet),
        split_type="three_way",
    )
    return sample_df, manifest


@pytest.fixture
def two_way_split(sample_df, sample_parquet):
    """Create a two-way split and return (df, manifest)."""
    _train, _val, _test, manifest = create_grouped_split(
        sample_df,
        seed=42,
        source_run_id="test_run",
        source_parquet_path=str(sample_parquet),
        split_type="two_way",
    )
    return sample_df, manifest


class TestRequireSplitReturnsCorrectData:
    """Verify require_split filters to the correct partition."""

    def test_require_val_split_returns_val_data(self, three_way_split):
        df, manifest = three_way_split
        result = require_split(df, manifest, "val", seed=42, active_split="val")
        assert len(result) > 0
        # Val should be roughly 10% of 100 hands * 4 seats = ~40 rows
        assert len(result) < len(df)

    def test_require_train_split_returns_train_data(self, three_way_split):
        df, manifest = three_way_split
        result = require_split(df, manifest, "train", seed=42, active_split="val")
        assert len(result) > 0
        # Train should be the largest partition
        val = require_split(df, manifest, "val", seed=42, active_split="val")
        assert len(result) > len(val)

    def test_splits_are_disjoint(self, three_way_split):
        df, manifest = three_way_split
        train = require_split(df, manifest, "train", seed=42, active_split="test")
        val = require_split(df, manifest, "val", seed=42, active_split="test")
        test = require_split(df, manifest, "test", seed=42, active_split="test")

        train_ids = set(train["hand_id"].unique())
        val_ids = set(val["hand_id"].unique())
        test_ids = set(test["hand_id"].unique())

        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)

    def test_splits_cover_all_data(self, three_way_split):
        df, manifest = three_way_split
        train = require_split(df, manifest, "train", seed=42, active_split="test")
        val = require_split(df, manifest, "val", seed=42, active_split="test")
        test = require_split(df, manifest, "test", seed=42, active_split="test")

        assert len(train) + len(val) + len(test) == len(df)


class TestTestSplitAccessControl:
    """Verify test-split blocking during HITL and access during blind test."""

    def test_require_test_blocked_during_hitl(self, three_way_split):
        df, manifest = three_way_split
        with pytest.raises(ValueError, match="Test split access blocked"):
            require_split(df, manifest, "test", seed=42, active_split="val")

    def test_require_test_allowed_during_blind(self, three_way_split):
        df, manifest = three_way_split
        result = require_split(df, manifest, "test", seed=42, active_split="test")
        assert len(result) > 0


class TestPartitionHashVerification:
    """Verify partition hash checks catch corruption."""

    def test_partition_hash_matches(self, three_way_split):
        df, manifest = three_way_split
        # Should not raise
        require_split(df, manifest, "val", seed=42, active_split="val")

    def test_partition_hash_mismatch_detected(self, three_way_split):
        """Wrong seed produces different partitions -> hash mismatch."""
        df, manifest = three_way_split
        with pytest.raises(ValueError, match="Partition hash mismatch"):
            require_split(df, manifest, "val", seed=99, active_split="val")


class TestEdgeCases:
    """Test error handling for invalid inputs."""

    def test_unknown_split_name_raises(self, three_way_split):
        df, manifest = three_way_split
        with pytest.raises(ValueError, match="Unknown split name"):
            require_split(df, manifest, "foo", seed=42, active_split="val")

    def test_two_way_manifest_no_val(self, two_way_split):
        df, manifest = two_way_split
        with pytest.raises(ValueError, match="not available in a two_way"):
            require_split(df, manifest, "val", seed=42, active_split="val")

    def test_two_way_train_works(self, two_way_split):
        df, manifest = two_way_split
        result = require_split(df, manifest, "train", seed=42, active_split="val")
        assert len(result) > 0

    def test_two_way_test_blocked_during_hitl(self, two_way_split):
        df, manifest = two_way_split
        with pytest.raises(ValueError, match="Test split access blocked"):
            require_split(df, manifest, "test", seed=42, active_split="val")

    def test_two_way_test_allowed_during_blind(self, two_way_split):
        df, manifest = two_way_split
        result = require_split(df, manifest, "test", seed=42, active_split="test")
        assert len(result) > 0
